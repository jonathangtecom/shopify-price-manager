"""
Pydantic models for database entities.
API tokens stored directly in SQLite (encrypted at rest on VPS).
"""

from datetime import datetime
from enum import Enum
from typing import Optional
from pydantic import BaseModel, Field
import uuid


class SyncStatus(str, Enum):
    """Status of a store's last sync."""
    IDLE = "idle"
    RUNNING = "running"
    SUCCESS = "success"
    FAILED = "failed"


class LogStatus(str, Enum):
    """Status of a sync log entry."""
    RUNNING = "running"
    SUCCESS = "success"
    FAILED = "failed"


class TriggerType(str, Enum):
    """What triggered the sync."""
    SCHEDULER = "scheduler"
    MANUAL = "manual"


def generate_uuid() -> str:
    """Generate a new UUID string."""
    return str(uuid.uuid4())


class Store(BaseModel):
    """A Shopify store configuration."""
    id: str = Field(default_factory=generate_uuid)
    name: str
    shopify_domain: str  # e.g., "mystore.myshopify.com"
    api_token: str  # Shopify Admin API token (shpat_...)
    is_paused: bool = False
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)
    last_sync_at: Optional[datetime] = None
    last_sync_status: SyncStatus = SyncStatus.IDLE


class StoreCreate(BaseModel):
    """Input for creating a new store."""
    name: str
    shopify_domain: str
    api_token: str


class StoreUpdate(BaseModel):
    """Input for updating a store."""
    name: Optional[str] = None
    shopify_domain: Optional[str] = None
    is_paused: Optional[bool] = None
    api_token: Optional[str] = None


class SyncLog(BaseModel):
    """A log entry for a sync execution."""
    id: str = Field(default_factory=generate_uuid)
    store_id: str
    store_name: str
    started_at: datetime = Field(default_factory=datetime.utcnow)
    finished_at: Optional[datetime] = None
    status: LogStatus = LogStatus.RUNNING
    triggered_by: TriggerType = TriggerType.MANUAL
    
    # Statistics
    products_processed: int = 0
    products_price_set: int = 0
    products_price_cleared: int = 0
    products_unchanged: int = 0
    
    # Error information
    error_message: Optional[str] = None
    error_details: Optional[str] = None


class SoldProduct(BaseModel):
    """Tracks products that have been sold (for incremental sync)."""
    id: str = Field(default_factory=generate_uuid)
    store_id: str
    product_id: str  # Shopify product GID
    last_sold_at: datetime
