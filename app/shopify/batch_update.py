"""
Batch update operations for Shopify products.
"""

import asyncio
import logging
from typing import Dict, List

from app.shopify.client import ShopifyClient, ShopifyClientError
from app.shopify.mutations import PRODUCT_VARIANTS_BULK_UPDATE

logger = logging.getLogger(__name__)


async def batch_update_variants(
    client: ShopifyClient,
    updates_by_product: Dict[str, List[dict]],
    delay_seconds: float = 0.5
) -> Dict[str, any]:
    """
    Update product variant prices in batches with rate limiting.
    
    Args:
        client: ShopifyClient instance
        updates_by_product: Dict mapping product_id to list of variant updates
                           Each update should have {"id": variant_id, "compareAtPrice": price}
        delay_seconds: Delay between API calls to respect rate limits
        
    Returns:
        Dict with "success_count", "error_count", and "errors_by_product"
    """
    success_count = 0
    error_count = 0
    errors_by_product: Dict[str, str] = {}
    
    total = len(updates_by_product)
    processed = 0
    
    for product_id, variants in updates_by_product.items():
        try:
            # Execute mutation
            data = await client.execute(
                PRODUCT_VARIANTS_BULK_UPDATE,
                variables={
                    "productId": product_id,
                    "variants": variants
                }
            )
            
            # Check for user errors
            result = data.get("productVariantsBulkUpdate", {})
            user_errors = result.get("userErrors", [])
            
            if user_errors:
                error_msgs = [e.get("message", str(e)) for e in user_errors]
                errors_by_product[product_id] = "; ".join(error_msgs)
                error_count += 1
                logger.warning(f"Failed to update {product_id}: {error_msgs}")
            else:
                success_count += 1
                logger.debug(f"Updated {len(variants)} variants for {product_id}")
            
            # Progress reporting
            processed += 1
            if processed % 100 == 0 or processed == total:
                logger.info(f"Progress: {processed}/{total} products ({int(processed/total*100)}%)")
            
            # Rate limiting delay
            if delay_seconds > 0:
                await asyncio.sleep(delay_seconds)
                
        except ShopifyClientError as e:
            errors_by_product[product_id] = str(e)
            error_count += 1
            logger.error(f"Error updating {product_id}: {e}")
        except Exception as e:
            errors_by_product[product_id] = f"Unexpected error: {e}"
            error_count += 1
            logger.exception(f"Unexpected error updating {product_id}")
    
    logger.info(f"Batch update complete: {success_count} succeeded, {error_count} failed")
    
    return {
        "success_count": success_count,
        "error_count": error_count,
        "errors_by_product": errors_by_product
    }
