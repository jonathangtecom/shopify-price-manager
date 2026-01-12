#!/usr/bin/env python3
"""
Cron job script to run scheduled sync for all active stores.
Add to crontab: 0 1 * * * cd /path/to/app && /path/to/venv/bin/python scripts/run_sync.py

This runs the sync as a standalone script, not through the web server.
"""

import asyncio
import logging
import sys
import os

# Add parent directory to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.config import settings
from app.db import SQLiteDatabase, TriggerType
from app.processor import run_all_stores

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)

logger = logging.getLogger(__name__)


async def main():
    logger.info("Starting scheduled sync...")
    
    db = SQLiteDatabase(settings.database_path)
    await db.initialize()
    
    try:
        results = await run_all_stores(db, TriggerType.SCHEDULER)
        
        successful = sum(1 for r in results if r.success)
        failed = len(results) - successful
        
        logger.info(f"Sync completed: {successful} successful, {failed} failed")
        
        if failed > 0:
            for r in results:
                if not r.success:
                    logger.error(f"  {r.store.name}: {r.error}")
            sys.exit(1)
            
    finally:
        await db.close()


if __name__ == "__main__":
    asyncio.run(main())
