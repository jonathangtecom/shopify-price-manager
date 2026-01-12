"""
Shopify Bulk Operations handler.

Manages submitting, polling, and downloading bulk operation results.
"""

import asyncio
import json
import logging
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any, AsyncIterator, Dict, List, Optional

import httpx

from app.shopify.client import ShopifyClient, ShopifyClientError
from app.shopify.queries import (
    BULK_OPERATION_STATUS_QUERY,
    build_orders_bulk_query,
    build_products_bulk_query,
)

logger = logging.getLogger(__name__)


class BulkOperationError(ShopifyClientError):
    """Error during bulk operation."""
    pass


class BulkOperationTimeout(BulkOperationError):
    """Bulk operation timed out."""
    pass


@dataclass
class BulkOperationResult:
    """Result of a completed bulk operation."""

    operation_id: str
    status: str
    object_count: int
    file_size: int
    url: Optional[str]
    partial_url: Optional[str]
    error_code: Optional[str]


@dataclass
class ParsedOrder:
    """Parsed order data from bulk operation."""

    order_id: str
    created_at: datetime
    product_ids: List[str]


@dataclass
class ParsedProduct:
    """Parsed product data from bulk operation."""

    product_id: str
    created_at: datetime
    variants: List[Dict[str, Any]]


class BulkOperationsManager:
    """
    Manages Shopify bulk operations for efficient large-scale data retrieval.
    """

    # Polling configuration
    INITIAL_POLL_INTERVAL = 5  # seconds
    MAX_POLL_INTERVAL = 60  # seconds
    POLL_INTERVAL_MULTIPLIER = 1.5
    MAX_POLL_TIME = 3600 * 2  # 2 hours max

    def __init__(self, client: ShopifyClient):
        """
        Initialize bulk operations manager.
        
        Args:
            client: Shopify GraphQL client
        """
        self.client = client

    async def fetch_orders_since(
        self, since_date: datetime
    ) -> List[ParsedOrder]:
        """
        Fetch all orders since a given date using bulk operations.
        
        Args:
            since_date: Fetch orders created on or after this date
            
        Returns:
            List of parsed order data with product IDs
        """
        # Format date for Shopify query
        date_str = since_date.strftime("%Y-%m-%d")
        logger.info(f"Starting bulk fetch of orders since {date_str}")

        # Submit bulk operation
        query = build_orders_bulk_query(date_str)
        result = await self._run_bulk_operation(query)

        if not result.url:
            logger.info("No orders found in date range")
            return []

        # Download and parse results
        orders = await self._download_and_parse_orders(result.url)
        logger.info(f"Fetched {len(orders)} orders with sales data")

        return orders

    async def fetch_active_products(self) -> List[ParsedProduct]:
        """
        Fetch all active products using bulk operations.
        
        Returns:
            List of parsed product data with variants
        """
        logger.info("Starting bulk fetch of active products")

        # Submit bulk operation
        query = build_products_bulk_query()
        result = await self._run_bulk_operation(query)

        if not result.url:
            logger.info("No active products found")
            return []

        # Download and parse results
        products = await self._download_and_parse_products(result.url)
        logger.info(f"Fetched {len(products)} active products")

        return products

    async def _run_bulk_operation(self, mutation: str) -> BulkOperationResult:
        """
        Submit and wait for a bulk operation to complete.
        
        Args:
            mutation: The bulkOperationRunQuery mutation
            
        Returns:
            BulkOperationResult with status and download URL
        """
        # Submit the operation
        data = await self.client.execute(mutation)

        # Extract operation info
        bulk_op = data.get("bulkOperationRunQuery", {})
        user_errors = bulk_op.get("userErrors", [])

        if user_errors:
            error_msgs = [e.get("message", str(e)) for e in user_errors]
            raise BulkOperationError(f"Bulk operation failed: {error_msgs}")

        operation = bulk_op.get("bulkOperation", {})
        operation_id = operation.get("id")

        if not operation_id:
            raise BulkOperationError("No operation ID returned")

        logger.info(f"Bulk operation started: {operation_id}")

        # Poll until complete
        return await self._poll_operation(operation_id)

    async def _poll_operation(self, operation_id: str) -> BulkOperationResult:
        """
        Poll a bulk operation until it completes.
        
        Args:
            operation_id: The bulk operation GID
            
        Returns:
            BulkOperationResult when complete
        """
        poll_interval = self.INITIAL_POLL_INTERVAL
        total_time = 0

        # Use currentBulkOperation query (works across API versions)
        poll_query = '''
        query {
          currentBulkOperation {
            id
            status
            errorCode
            objectCount
            fileSize
            url
            partialDataUrl
          }
        }
        '''

        while total_time < self.MAX_POLL_TIME:
            data = await self.client.execute(poll_query)

            operation = data.get("currentBulkOperation", {})
            status = operation.get("status", "UNKNOWN")

            logger.debug(
                f"Bulk operation {operation_id}: {status}, "
                f"objects: {operation.get('objectCount', 0)}"
            )

            if status == "COMPLETED":
                return BulkOperationResult(
                    operation_id=operation_id,
                    status=status,
                    object_count=int(operation.get("objectCount", 0)),
                    file_size=int(operation.get("fileSize", 0)),
                    url=operation.get("url"),
                    partial_url=operation.get("partialDataUrl"),
                    error_code=None,
                )

            if status == "FAILED":
                error_code = operation.get("errorCode", "UNKNOWN")
                partial_url = operation.get("partialDataUrl")

                raise BulkOperationError(
                    f"Bulk operation failed with error: {error_code}. "
                    f"Partial data may be available at: {partial_url}"
                )

            if status == "CANCELED":
                raise BulkOperationError("Bulk operation was canceled")

            if status not in ("CREATED", "RUNNING"):
                raise BulkOperationError(f"Unexpected status: {status}")

            # Wait and poll again
            await asyncio.sleep(poll_interval)
            total_time += poll_interval
            poll_interval = min(
                poll_interval * self.POLL_INTERVAL_MULTIPLIER,
                self.MAX_POLL_INTERVAL,
            )

        raise BulkOperationTimeout(
            f"Bulk operation did not complete within {self.MAX_POLL_TIME}s"
        )

    async def _download_jsonl(self, url: str) -> AsyncIterator[Dict[str, Any]]:
        """
        Download and stream JSONL file line by line.
        
        Args:
            url: The download URL
            
        Yields:
            Parsed JSON objects from each line
        """
        async with httpx.AsyncClient() as client:
            async with client.stream("GET", url) as response:
                response.raise_for_status()

                buffer = ""
                async for chunk in response.aiter_text():
                    buffer += chunk
                    while "\n" in buffer:
                        line, buffer = buffer.split("\n", 1)
                        line = line.strip()
                        if line:
                            try:
                                yield json.loads(line)
                            except json.JSONDecodeError as e:
                                logger.warning(f"Failed to parse line: {e}")

                # Handle last line without newline
                if buffer.strip():
                    try:
                        yield json.loads(buffer.strip())
                    except json.JSONDecodeError as e:
                        logger.warning(f"Failed to parse final line: {e}")

    async def _download_and_parse_orders(
        self, url: str
    ) -> List[ParsedOrder]:
        """
        Download and parse order data from JSONL.
        
        The JSONL format from bulk operations has nested objects flattened
        with __parentId references. We need to reconstruct the relationships.
        
        Args:
            url: Download URL for JSONL file
            
        Returns:
            List of ParsedOrder objects
        """
        orders: Dict[str, ParsedOrder] = {}

        async for obj in self._download_jsonl(url):
            obj_id = obj.get("id", "")
            parent_id = obj.get("__parentId")

            if obj_id.startswith("gid://shopify/Order/"):
                # This is an order
                created_at_str = obj.get("createdAt", "")
                try:
                    created_at = datetime.fromisoformat(
                        created_at_str.replace("Z", "+00:00")
                    )
                except (ValueError, AttributeError):
                    created_at = datetime.utcnow()

                orders[obj_id] = ParsedOrder(
                    order_id=obj_id,
                    created_at=created_at,
                    product_ids=[],
                )

            elif "product" in obj and parent_id:
                # This is a line item with product reference
                # Format: {'product': {'id': 'gid://shopify/Product/...'}, '__parentId': 'order_id'}
                product_id = obj.get("product", {}).get("id")
                if product_id and parent_id in orders:
                    # Avoid duplicates - a product may appear multiple times in same order
                    if product_id not in orders[parent_id].product_ids:
                        orders[parent_id].product_ids.append(product_id)

        return list(orders.values())

    async def _download_and_parse_products(
        self, url: str
    ) -> List[ParsedProduct]:
        """
        Download and parse product data from JSONL.
        
        Args:
            url: Download URL for JSONL file
            
        Returns:
            List of ParsedProduct objects
        """
        products: Dict[str, ParsedProduct] = {}

        async for obj in self._download_jsonl(url):
            obj_id = obj.get("id", "")
            parent_id = obj.get("__parentId")

            if obj_id.startswith("gid://shopify/Product/"):
                # This is a product
                created_at_str = obj.get("createdAt", "")
                try:
                    created_at = datetime.fromisoformat(
                        created_at_str.replace("Z", "+00:00")
                    )
                except (ValueError, AttributeError):
                    created_at = datetime.now(timezone.utc)

                products[obj_id] = ParsedProduct(
                    product_id=obj_id,
                    created_at=created_at,
                    variants=[],
                )

            elif obj_id.startswith("gid://shopify/ProductVariant/"):
                # This is a variant - attach to parent product
                if parent_id and parent_id in products:
                    products[parent_id].variants.append({
                        "id": obj_id,
                        "price": obj.get("price"),
                        "compare_at_price": obj.get("compareAtPrice"),
                    })

        return list(products.values())
