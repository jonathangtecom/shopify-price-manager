"""
Runner for executing sync across multiple stores.
"""

import asyncio
import logging
from dataclasses import dataclass
from typing import List, Optional

from ..db import SQLiteDatabase, Store, SyncLog, TriggerType
from .sync import sync_store, SyncError

logger = logging.getLogger(__name__)


@dataclass
class SyncResult:
    """Result of a store sync."""
    store: Store
    log: Optional[SyncLog]
    error: Optional[str]
    
    @property
    def success(self) -> bool:
        return self.error is None


async def run_single_store(
    store: Store,
    db: SQLiteDatabase,
    triggered_by: TriggerType = TriggerType.SCHEDULER
) -> SyncResult:
    """Run sync for a single store with error handling."""
    try:
        log = await sync_store(store, db, triggered_by)
        return SyncResult(store=store, log=log, error=None)
    except SyncError as e:
        logger.error(f"Sync failed for '{store.name}': {e}")
        return SyncResult(store=store, log=None, error=str(e))
    except Exception as e:
        logger.exception(f"Unexpected error syncing '{store.name}'")
        return SyncResult(store=store, log=None, error=f"Unexpected error: {e}")


async def run_all_stores(
    db: SQLiteDatabase,
    triggered_by: TriggerType = TriggerType.SCHEDULER,
    max_concurrent: int = 5
) -> List[SyncResult]:
    """Run sync for all active stores in parallel."""
    stores = await db.get_active_stores()
    
    if not stores:
        logger.info("No active stores to sync")
        return []
    
    logger.info(f"Starting sync for {len(stores)} stores")
    
    semaphore = asyncio.Semaphore(max_concurrent)
    
    async def sync_with_semaphore(store: Store) -> SyncResult:
        async with semaphore:
            return await run_single_store(store, db, triggered_by)
    
    tasks = [sync_with_semaphore(store) for store in stores]
    results = await asyncio.gather(*tasks)
    
    successful = sum(1 for r in results if r.success)
    failed = len(results) - successful
    
    logger.info(f"Sync completed: {successful} successful, {failed} failed")
    
    return results


async def run_specific_store(
    store_id: str,
    db: SQLiteDatabase,
    triggered_by: TriggerType = TriggerType.MANUAL
) -> SyncResult:
    """Run sync for a specific store by ID."""
    store = await db.get_store(store_id)
    
    if not store:
        raise ValueError(f"Store not found: {store_id}")
    
    if store.is_paused:
        raise ValueError(f"Store '{store.name}' is paused")
    
    return await run_single_store(store, db, triggered_by)
