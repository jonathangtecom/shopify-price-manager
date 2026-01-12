"""
Sync processor for a single store.
"""

import asyncio
import logging
import traceback
from collections import defaultdict
from datetime import datetime, timedelta, timezone
from typing import Dict, List, Set

from ..db import SQLiteDatabase, Store, SyncLog, SyncStatus, LogStatus, TriggerType
from ..shopify import (
    ShopifyClient, BulkOperationsManager, ShopifyClientError, BulkOperationError,
    batch_update_variants
)
from .rules import calculate_compare_at_price, should_update_variant, SALES_LOOKBACK_DAYS

logger = logging.getLogger(__name__)


class SyncError(Exception):
    """Error during sync process."""
    pass


async def sync_store(
    store: Store,
    db: SQLiteDatabase,
    triggered_by: TriggerType = TriggerType.MANUAL
) -> SyncLog:
    """
    Run the complete sync process for a single store.
    """
    log = await db.create_log(store.id, store.name, triggered_by)
    logger.info(f"Starting sync for store '{store.name}' (log: {log.id})")
    
    await db.update_store_sync_status(store.id, SyncStatus.RUNNING)
    
    stats = {
        "products_processed": 0,
        "products_price_set": 0,
        "products_price_cleared": 0,
        "products_unchanged": 0
    }
    
    client = None
    
    try:
        # Create Shopify client using token from store
        client = ShopifyClient(store.shopify_domain, store.api_token)
        bulk_ops = BulkOperationsManager(client)
        
        now = datetime.now(timezone.utc)
        sales_cutoff = now - timedelta(days=SALES_LOOKBACK_DAYS)
        
        # Step 1: Clean up old sold products
        deleted = await db.cleanup_old_sold_products(store.id, sales_cutoff)
        if deleted > 0:
            logger.info(f"Cleaned up {deleted} old sold product records")
        
        # Step 2: Determine order fetch range
        if store.last_sync_at is None:
            orders_since = sales_cutoff
            logger.info(f"First sync - fetching orders since {orders_since}")
        else:
            orders_since = store.last_sync_at
            logger.info(f"Incremental sync - fetching orders since {orders_since}")
        
        # Step 3: Fetch orders via bulk operation
        logger.info("Fetching orders...")
        sold_products = await fetch_orders_and_extract_products(bulk_ops, orders_since)
        logger.info(f"Found {len(sold_products)} products in orders")
        
        # Step 4: Update sold products table
        if sold_products:
            products_list = [
                {"product_id": pid, "sold_at": date}
                for pid, date in sold_products.items()
            ]
            await db.bulk_upsert_sold_products(store.id, products_list)
        
        # Step 5: Build sold products set
        sold_product_ids = await db.get_sold_product_ids(store.id, sales_cutoff)
        logger.info(f"Total products sold in last {SALES_LOOKBACK_DAYS} days: {len(sold_product_ids)}")
        
        # Step 6: Fetch all active products
        logger.info("Fetching products...")
        products = await fetch_products(bulk_ops)
        logger.info(f"Found {len(products)} active products")
        
        stats["products_processed"] = len(products)
        
        # Step 7: Evaluate each variant
        updates_by_product: Dict[str, List[dict]] = defaultdict(list)
        
        for product in products:
            product_id = product["id"]
            created_at = product["created_at"]
            
            for variant in product.get("variants", []):
                variant_id = variant["id"]
                current_price = variant["price"]
                current_compare_at = variant.get("compare_at_price")
                
                new_compare_at = calculate_compare_at_price(
                    variant_price=current_price,
                    product_id=product_id,
                    product_created_at=created_at,
                    sold_product_ids=sold_product_ids,
                    current_time=now
                )
                
                if should_update_variant(current_compare_at, new_compare_at):
                    updates_by_product[product_id].append({
                        "id": variant_id,
                        "compareAtPrice": new_compare_at
                    })
                    
                    if new_compare_at is not None:
                        stats["products_price_set"] += 1
                    else:
                        stats["products_price_cleared"] += 1
                else:
                    stats["products_unchanged"] += 1
        
        # Step 8: Apply updates
        total_updates = sum(len(v) for v in updates_by_product.values())
        logger.info(f"Applying {total_updates} variant updates...")
        
        if updates_by_product:
            result = await batch_update_variants(client, updates_by_product, delay_seconds=0.3)
            
            if result["errors_by_product"]:
                logger.warning(f"Some updates failed: {len(result['errors_by_product'])} products had errors")
        
        logger.info(
            f"Sync completed: {stats['products_price_set']} set, "
            f"{stats['products_price_cleared']} cleared, "
            f"{stats['products_unchanged']} unchanged"
        )
        
        await db.update_log(
            log.id,
            finished_at=datetime.now(timezone.utc),
            status=LogStatus.SUCCESS,
            **stats
        )
        
        await db.update_store_sync_status(store.id, SyncStatus.SUCCESS, last_sync_at=now)
        
        return await db.get_log(log.id)
        
    except Exception as e:
        logger.error(f"Sync failed for store '{store.name}': {e}")
        logger.debug(traceback.format_exc())
        
        await db.update_log(
            log.id,
            finished_at=datetime.now(timezone.utc),
            status=LogStatus.FAILED,
            error_message=str(e),
            error_details=traceback.format_exc(),
            **stats
        )
        
        await db.update_store_sync_status(store.id, SyncStatus.FAILED)
        raise SyncError(f"Sync failed: {e}") from e
        
    finally:
        if client:
            await client.close()


async def fetch_orders_and_extract_products(
    bulk_ops: BulkOperationsManager,
    since_date: datetime
) -> Dict[str, datetime]:
    """Fetch orders via bulk operation and extract product IDs."""
    parsed_orders = await bulk_ops.fetch_orders_since(since_date)
    
    products: Dict[str, datetime] = {}
    
    for order in parsed_orders:
        for product_id in order.product_ids:
            if product_id not in products or order.created_at > products[product_id]:
                products[product_id] = order.created_at
    
    return products


async def fetch_products(bulk_ops: BulkOperationsManager) -> List[dict]:
    """Fetch all active products via bulk operation."""
    parsed_products = await bulk_ops.fetch_active_products()
    
    products = []
    for parsed in parsed_products:
        products.append({
            "id": parsed.product_id,
            "created_at": parsed.created_at,
            "variants": parsed.variants
        })
    
    return products
