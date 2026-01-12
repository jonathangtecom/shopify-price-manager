"""
Sync trigger API routes.
"""

import asyncio
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from typing import Optional

from ..dependencies import get_db, require_auth
from ..db import TriggerType
from ..processor import run_all_stores, run_specific_store

router = APIRouter(prefix="/api/sync", dependencies=[Depends(require_auth)])


class SyncResponse(BaseModel):
    message: str
    store_id: Optional[str] = None
    success: bool


@router.post("/all", response_model=SyncResponse)
async def sync_all_stores():
    """Trigger sync for all active stores."""
    db = get_db()
    
    stores = await db.get_active_stores()
    
    # Run in background
    asyncio.create_task(run_all_stores(db, TriggerType.MANUAL))
    
    return SyncResponse(
        message=f"Sync started for {len(stores)} stores",
        success=True
    )


@router.post("/{store_id}", response_model=SyncResponse)
async def sync_single_store(store_id: str):
    """Trigger sync for a single store."""
    db = get_db()
    
    store = await db.get_store(store_id)
    if not store:
        raise HTTPException(status_code=404, detail="Store not found")
    
    if store.is_paused:
        raise HTTPException(status_code=400, detail="Store is paused")
    
    asyncio.create_task(run_specific_store(store_id, db, TriggerType.MANUAL))
    
    return SyncResponse(
        message=f"Sync started for '{store.name}'",
        store_id=store_id,
        success=True
    )


@router.get("/status")
async def get_sync_status():
    """Get current sync status across all stores."""
    db = get_db()
    
    stores = await db.get_stores()
    running = [s for s in stores if s.last_sync_status.value == "running"]
    
    return {
        "total_stores": len(stores),
        "active_stores": len([s for s in stores if not s.is_paused]),
        "running_syncs": len(running),
        "running_store_names": [s.name for s in running]
    }
