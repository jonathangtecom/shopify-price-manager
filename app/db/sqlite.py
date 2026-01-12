"""
SQLite database implementation.
Simple and direct - no abstraction layers.
"""

import aiosqlite
from datetime import datetime
from typing import List, Optional, Set
import os

from .models import (
    Store, SyncLog, SyncStatus, LogStatus, TriggerType,
    generate_uuid
)


class SQLiteDatabase:
    """SQLite database for all operations."""
    
    def __init__(self, db_path: str):
        self.db_path = db_path
        self._connection: Optional[aiosqlite.Connection] = None
    
    async def _get_connection(self) -> aiosqlite.Connection:
        """Get or create database connection."""
        if self._connection is None:
            os.makedirs(os.path.dirname(self.db_path) or ".", exist_ok=True)
            self._connection = await aiosqlite.connect(self.db_path)
            self._connection.row_factory = aiosqlite.Row
        return self._connection
    
    async def initialize(self) -> None:
        """Create database tables."""
        conn = await self._get_connection()
        
        await conn.executescript("""
            CREATE TABLE IF NOT EXISTS stores (
                id TEXT PRIMARY KEY,
                name TEXT NOT NULL,
                shopify_domain TEXT NOT NULL,
                api_token TEXT NOT NULL,
                is_paused INTEGER NOT NULL DEFAULT 0,
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL,
                last_sync_at TEXT,
                last_sync_status TEXT NOT NULL DEFAULT 'idle'
            );
            
            CREATE TABLE IF NOT EXISTS sync_logs (
                id TEXT PRIMARY KEY,
                store_id TEXT NOT NULL,
                store_name TEXT NOT NULL,
                started_at TEXT NOT NULL,
                finished_at TEXT,
                status TEXT NOT NULL DEFAULT 'running',
                triggered_by TEXT NOT NULL,
                products_processed INTEGER NOT NULL DEFAULT 0,
                products_price_set INTEGER NOT NULL DEFAULT 0,
                products_price_cleared INTEGER NOT NULL DEFAULT 0,
                products_unchanged INTEGER NOT NULL DEFAULT 0,
                error_message TEXT,
                error_details TEXT,
                FOREIGN KEY (store_id) REFERENCES stores(id) ON DELETE CASCADE
            );
            
            CREATE TABLE IF NOT EXISTS sold_products (
                id TEXT PRIMARY KEY,
                store_id TEXT NOT NULL,
                product_id TEXT NOT NULL,
                last_sold_at TEXT NOT NULL,
                FOREIGN KEY (store_id) REFERENCES stores(id) ON DELETE CASCADE,
                UNIQUE(store_id, product_id)
            );
            
            CREATE INDEX IF NOT EXISTS idx_sync_logs_store_id ON sync_logs(store_id);
            CREATE INDEX IF NOT EXISTS idx_sync_logs_started_at ON sync_logs(started_at DESC);
            CREATE INDEX IF NOT EXISTS idx_sold_products_store_id ON sold_products(store_id);
            CREATE INDEX IF NOT EXISTS idx_sold_products_last_sold ON sold_products(store_id, last_sold_at);
        """)
        await conn.commit()
    
    async def close(self) -> None:
        """Close database connection."""
        if self._connection:
            await self._connection.close()
            self._connection = None
    
    # ===== Helper Methods =====
    
    def _row_to_store(self, row: aiosqlite.Row) -> Store:
        """Convert a database row to a Store model."""
        # Parse datetimes and remove timezone info to avoid comparison issues
        created_at = datetime.fromisoformat(row["created_at"])
        if created_at.tzinfo is not None:
            created_at = created_at.replace(tzinfo=None)
        
        updated_at = datetime.fromisoformat(row["updated_at"])
        if updated_at.tzinfo is not None:
            updated_at = updated_at.replace(tzinfo=None)
        
        last_sync_at = None
        if row["last_sync_at"]:
            last_sync_at = datetime.fromisoformat(row["last_sync_at"])
            if last_sync_at.tzinfo is not None:
                last_sync_at = last_sync_at.replace(tzinfo=None)
        
        return Store(
            id=row["id"],
            name=row["name"],
            shopify_domain=row["shopify_domain"],
            api_token=row["api_token"],
            is_paused=bool(row["is_paused"]),
            created_at=created_at,
            updated_at=updated_at,
            last_sync_at=last_sync_at,
            last_sync_status=SyncStatus(row["last_sync_status"])
        )
    
    def _row_to_log(self, row: aiosqlite.Row) -> SyncLog:
        """Convert a database row to a SyncLog model."""
        # Parse datetimes and remove timezone info to avoid comparison issues
        started_at = datetime.fromisoformat(row["started_at"])
        if started_at.tzinfo is not None:
            started_at = started_at.replace(tzinfo=None)
        
        finished_at = None
        if row["finished_at"]:
            finished_at = datetime.fromisoformat(row["finished_at"])
            if finished_at.tzinfo is not None:
                finished_at = finished_at.replace(tzinfo=None)
        
        return SyncLog(
            id=row["id"],
            store_id=row["store_id"],
            store_name=row["store_name"],
            started_at=started_at,
            finished_at=finished_at,
            status=LogStatus(row["status"]),
            triggered_by=TriggerType(row["triggered_by"]),
            products_processed=row["products_processed"],
            products_price_set=row["products_price_set"],
            products_price_cleared=row["products_price_cleared"],
            products_unchanged=row["products_unchanged"],
            error_message=row["error_message"],
            error_details=row["error_details"]
        )
    
    # ===== Store Operations =====
    
    async def get_stores(self) -> List[Store]:
        conn = await self._get_connection()
        cursor = await conn.execute("SELECT * FROM stores ORDER BY name")
        rows = await cursor.fetchall()
        return [self._row_to_store(row) for row in rows]
    
    async def get_store(self, store_id: str) -> Optional[Store]:
        conn = await self._get_connection()
        cursor = await conn.execute("SELECT * FROM stores WHERE id = ?", (store_id,))
        row = await cursor.fetchone()
        return self._row_to_store(row) if row else None
    
    async def get_active_stores(self) -> List[Store]:
        conn = await self._get_connection()
        cursor = await conn.execute("SELECT * FROM stores WHERE is_paused = 0 ORDER BY name")
        rows = await cursor.fetchall()
        return [self._row_to_store(row) for row in rows]
    
    async def create_store(self, store: Store) -> Store:
        conn = await self._get_connection()
        await conn.execute(
            """
            INSERT INTO stores (id, name, shopify_domain, api_token, is_paused, 
                               created_at, updated_at, last_sync_at, last_sync_status)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                store.id,
                store.name,
                store.shopify_domain,
                store.api_token,
                int(store.is_paused),
                store.created_at.isoformat(),
                store.updated_at.isoformat(),
                store.last_sync_at.isoformat() if store.last_sync_at else None,
                store.last_sync_status.value
            )
        )
        await conn.commit()
        return store
    
    async def update_store(self, store_id: str, **kwargs) -> Optional[Store]:
        if not kwargs:
            return await self.get_store(store_id)
        
        updates = []
        values = []
        
        field_mapping = {
            "name": "name",
            "shopify_domain": "shopify_domain",
            "api_token": "api_token",
            "is_paused": "is_paused",
            "last_sync_at": "last_sync_at",
            "last_sync_status": "last_sync_status"
        }
        
        for key, value in kwargs.items():
            if key in field_mapping:
                updates.append(f"{field_mapping[key]} = ?")
                if key == "is_paused":
                    values.append(int(value))
                elif key == "last_sync_at" and value is not None:
                    values.append(value.isoformat() if isinstance(value, datetime) else value)
                elif key == "last_sync_status":
                    values.append(value.value if isinstance(value, SyncStatus) else value)
                else:
                    values.append(value)
        
        updates.append("updated_at = ?")
        values.append(datetime.utcnow().isoformat())
        values.append(store_id)
        
        conn = await self._get_connection()
        await conn.execute(f"UPDATE stores SET {', '.join(updates)} WHERE id = ?", values)
        await conn.commit()
        
        return await self.get_store(store_id)
    
    async def delete_store(self, store_id: str) -> bool:
        conn = await self._get_connection()
        await conn.execute("DELETE FROM sold_products WHERE store_id = ?", (store_id,))
        await conn.execute("DELETE FROM sync_logs WHERE store_id = ?", (store_id,))
        cursor = await conn.execute("DELETE FROM stores WHERE id = ?", (store_id,))
        await conn.commit()
        return cursor.rowcount > 0
    
    async def update_store_sync_status(
        self,
        store_id: str,
        status: SyncStatus,
        last_sync_at: Optional[datetime] = None
    ) -> None:
        conn = await self._get_connection()
        
        if last_sync_at:
            await conn.execute(
                "UPDATE stores SET last_sync_status = ?, last_sync_at = ?, updated_at = ? WHERE id = ?",
                (status.value, last_sync_at.isoformat(), datetime.utcnow().isoformat(), store_id)
            )
        else:
            await conn.execute(
                "UPDATE stores SET last_sync_status = ?, updated_at = ? WHERE id = ?",
                (status.value, datetime.utcnow().isoformat(), store_id)
            )
        
        await conn.commit()
    
    # ===== Log Operations =====
    
    async def get_logs(
        self,
        store_id: Optional[str] = None,
        status: Optional[LogStatus] = None,
        limit: int = 50,
        offset: int = 0
    ) -> List[SyncLog]:
        conn = await self._get_connection()
        
        query = "SELECT * FROM sync_logs WHERE 1=1"
        params = []
        
        if store_id:
            query += " AND store_id = ?"
            params.append(store_id)
        
        if status:
            query += " AND status = ?"
            params.append(status.value)
        
        query += " ORDER BY started_at DESC LIMIT ? OFFSET ?"
        params.extend([limit, offset])
        
        cursor = await conn.execute(query, params)
        rows = await cursor.fetchall()
        return [self._row_to_log(row) for row in rows]
    
    async def get_log(self, log_id: str) -> Optional[SyncLog]:
        conn = await self._get_connection()
        cursor = await conn.execute("SELECT * FROM sync_logs WHERE id = ?", (log_id,))
        row = await cursor.fetchone()
        return self._row_to_log(row) if row else None
    
    async def create_log(
        self,
        store_id: str,
        store_name: str,
        triggered_by: TriggerType
    ) -> SyncLog:
        log = SyncLog(
            store_id=store_id,
            store_name=store_name,
            triggered_by=triggered_by
        )
        
        conn = await self._get_connection()
        await conn.execute(
            """
            INSERT INTO sync_logs (id, store_id, store_name, started_at, finished_at,
                                  status, triggered_by, products_processed, products_price_set,
                                  products_price_cleared, products_unchanged, error_message, error_details)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                log.id, log.store_id, log.store_name, log.started_at.isoformat(),
                None, log.status.value, log.triggered_by.value, 0, 0, 0, 0, None, None
            )
        )
        await conn.commit()
        return log
    
    async def update_log(self, log_id: str, **kwargs) -> Optional[SyncLog]:
        if not kwargs:
            return await self.get_log(log_id)
        
        updates = []
        values = []
        
        for key, value in kwargs.items():
            updates.append(f"{key} = ?")
            if key == "finished_at" and isinstance(value, datetime):
                values.append(value.isoformat())
            elif key == "status" and isinstance(value, LogStatus):
                values.append(value.value)
            else:
                values.append(value)
        
        values.append(log_id)
        
        conn = await self._get_connection()
        await conn.execute(f"UPDATE sync_logs SET {', '.join(updates)} WHERE id = ?", values)
        await conn.commit()
        
        return await self.get_log(log_id)
    
    # ===== Sold Products Operations =====
    
    async def cleanup_old_sold_products(self, store_id: str, cutoff_date: datetime) -> int:
        conn = await self._get_connection()
        cursor = await conn.execute(
            "DELETE FROM sold_products WHERE store_id = ? AND last_sold_at < ?",
            (store_id, cutoff_date.isoformat())
        )
        await conn.commit()
        return cursor.rowcount
    
    async def bulk_upsert_sold_products(self, store_id: str, products: List[dict]) -> None:
        if not products:
            return
        
        conn = await self._get_connection()
        
        for product in products:
            await conn.execute(
                """
                INSERT INTO sold_products (id, store_id, product_id, last_sold_at)
                VALUES (?, ?, ?, ?)
                ON CONFLICT(store_id, product_id) DO UPDATE SET
                    last_sold_at = MAX(last_sold_at, excluded.last_sold_at)
                """,
                (
                    generate_uuid(),
                    store_id,
                    product["product_id"],
                    product["sold_at"].isoformat() if isinstance(product["sold_at"], datetime) else product["sold_at"]
                )
            )
        
        await conn.commit()
    
    async def get_sold_product_ids(self, store_id: str, since_date: datetime) -> Set[str]:
        conn = await self._get_connection()
        cursor = await conn.execute(
            "SELECT product_id FROM sold_products WHERE store_id = ? AND last_sold_at >= ?",
            (store_id, since_date.isoformat())
        )
        rows = await cursor.fetchall()
        return {row["product_id"] for row in rows}
