"""
Shopify GraphQL Admin API client.
"""

import asyncio
import logging
from typing import Any, Dict, Optional

import httpx

logger = logging.getLogger(__name__)


class ShopifyClientError(Exception):
    """Base exception for Shopify client errors."""
    pass


class ShopifyAuthError(ShopifyClientError):
    """Authentication error."""
    pass


class ShopifyRateLimitError(ShopifyClientError):
    """Rate limit exceeded."""

    def __init__(self, message: str, retry_after: Optional[float] = None):
        super().__init__(message)
        self.retry_after = retry_after


class ShopifyClient:
    """
    Async HTTP client for Shopify GraphQL Admin API.
    
    Handles authentication, rate limiting, and retries.
    """

    API_VERSION = "2025-01"
    MAX_RETRIES = 5
    BASE_RETRY_DELAY = 1.0  # seconds

    def __init__(self, shop_domain: str, access_token: str):
        """
        Initialize Shopify client.
        
        Args:
            shop_domain: Store domain (e.g., "mystore.myshopify.com")
            access_token: Admin API access token
        """
        # Clean domain
        domain = shop_domain
        if domain.startswith("https://"):
            domain = domain[8:]
        elif domain.startswith("http://"):
            domain = domain[7:]
        domain = domain.rstrip("/")

        self.shop_domain = domain
        self.access_token = access_token
        self.graphql_url = (
            f"https://{domain}/admin/api/{self.API_VERSION}/graphql.json"
        )

        self._client: Optional[httpx.AsyncClient] = None

    async def _get_client(self) -> httpx.AsyncClient:
        """Get or create HTTP client."""
        if self._client is None or self._client.is_closed:
            self._client = httpx.AsyncClient(
                timeout=httpx.Timeout(60.0, connect=10.0),
                headers={
                    "Content-Type": "application/json",
                    "X-Shopify-Access-Token": self.access_token,
                },
            )
        return self._client

    async def close(self) -> None:
        """Close the HTTP client."""
        if self._client and not self._client.is_closed:
            await self._client.aclose()
            self._client = None

    async def execute(
        self,
        query: str,
        variables: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """
        Execute a GraphQL query/mutation with retry logic.
        
        Args:
            query: GraphQL query or mutation string
            variables: Optional variables for the query
            
        Returns:
            The 'data' portion of the GraphQL response
            
        Raises:
            ShopifyAuthError: If authentication fails
            ShopifyRateLimitError: If rate limit exceeded after retries
            ShopifyClientError: For other errors
        """
        client = await self._get_client()
        payload = {"query": query}
        if variables:
            payload["variables"] = variables

        last_error: Optional[Exception] = None

        for attempt in range(self.MAX_RETRIES):
            try:
                response = await client.post(self.graphql_url, json=payload)

                # Handle HTTP errors
                if response.status_code == 401:
                    raise ShopifyAuthError(
                        f"Authentication failed for {self.shop_domain}"
                    )

                if response.status_code == 429:
                    retry_after = float(
                        response.headers.get("Retry-After", self.BASE_RETRY_DELAY)
                    )
                    raise ShopifyRateLimitError(
                        "Rate limit exceeded", retry_after=retry_after
                    )

                response.raise_for_status()

                # Parse response
                result = response.json()

                # Check for GraphQL errors
                if "errors" in result and result["errors"]:
                    errors = result["errors"]
                    error_messages = [e.get("message", str(e)) for e in errors]

                    # Check for throttling in GraphQL errors
                    if any("throttl" in msg.lower() for msg in error_messages):
                        raise ShopifyRateLimitError(
                            f"GraphQL throttled: {error_messages}"
                        )

                    raise ShopifyClientError(
                        f"GraphQL errors: {error_messages}"
                    )

                # Log rate limit status if available
                if "extensions" in result and "cost" in result["extensions"]:
                    cost = result["extensions"]["cost"]
                    throttle = cost.get("throttleStatus", {})
                    available = throttle.get("currentlyAvailable", 0)
                    if available < 100:
                        logger.warning(
                            f"Low rate limit points: {available} available"
                        )

                return result.get("data", {})

            except ShopifyAuthError:
                # Don't retry auth errors
                raise

            except ShopifyRateLimitError as e:
                last_error = e
                delay = e.retry_after or (
                    self.BASE_RETRY_DELAY * (2 ** attempt)
                )
                logger.warning(
                    f"Rate limited, waiting {delay:.1f}s "
                    f"(attempt {attempt + 1}/{self.MAX_RETRIES})"
                )
                await asyncio.sleep(delay)

            except httpx.RequestError as e:
                last_error = ShopifyClientError(f"Request error: {e}")
                delay = self.BASE_RETRY_DELAY * (2 ** attempt)
                logger.warning(
                    f"Request error, retrying in {delay:.1f}s: {e}"
                )
                await asyncio.sleep(delay)

            except Exception as e:
                last_error = ShopifyClientError(f"Unexpected error: {e}")
                logger.error(f"Unexpected error: {e}")
                raise last_error

        # All retries exhausted
        raise last_error or ShopifyClientError("Max retries exceeded")

    async def __aenter__(self):
        """Async context manager entry."""
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Async context manager exit."""
        await self.close()
