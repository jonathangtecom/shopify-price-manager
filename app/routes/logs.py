"""
Log viewing routes.
"""

from fastapi import APIRouter, Request, Depends, HTTPException, Query
from fastapi.responses import HTMLResponse, PlainTextResponse
from fastapi.templating import Jinja2Templates
from typing import Optional
from datetime import datetime

from ..dependencies import get_db, require_auth
from ..db import LogStatus

router = APIRouter(prefix="/logs", dependencies=[Depends(require_auth)])
templates = Jinja2Templates(directory="app/templates")

# Add custom Jinja2 filters
def format_datetime(value):
    """Format datetime for display."""
    if isinstance(value, datetime):
        return value.strftime('%Y-%m-%d %H:%M')
    return str(value)

templates.env.filters['format_datetime'] = format_datetime


@router.get("", response_class=HTMLResponse)
async def list_logs(
    request: Request,
    store_id: Optional[str] = Query(None),
    status: Optional[str] = Query(None),
    page: int = Query(1, ge=1)
):
    """List sync logs with filtering."""
    db = get_db()
    
    status_filter = None
    if status and status != "all":
        try:
            status_filter = LogStatus(status)
        except ValueError:
            pass
    
    limit = 25
    offset = (page - 1) * limit
    
    logs = await db.get_logs(
        store_id=store_id if store_id and store_id != "all" else None,
        status=status_filter,
        limit=limit + 1,
        offset=offset
    )
    
    has_next = len(logs) > limit
    logs = logs[:limit]
    
    stores = await db.get_stores()
    
    return templates.TemplateResponse(
        "logs/list.html",
        {
            "request": request,
            "logs": logs,
            "stores": stores,
            "selected_store": store_id or "all",
            "selected_status": status or "all",
            "page": page,
            "has_prev": page > 1,
            "has_next": has_next
        }
    )


@router.get("/{log_id}", response_class=HTMLResponse)
async def view_log(request: Request, log_id: str):
    """View a single log entry."""
    db = get_db()
    
    log = await db.get_log(log_id)
    if not log:
        raise HTTPException(status_code=404, detail="Log not found")
    
    return templates.TemplateResponse(
        "logs/detail.html",
        {"request": request, "log": log}
    )


@router.get("/{log_id}/download", response_class=PlainTextResponse)
async def download_log(log_id: str):
    """Download a log entry as a text file."""
    db = get_db()
    
    log = await db.get_log(log_id)
    if not log:
        raise HTTPException(status_code=404, detail="Log not found")
    
    # Format log as text
    lines = [
        "="*80,
        f"SYNC LOG: {log.store_name}",
        "="*80,
        "",
        f"Log ID:        {log.id}",
        f"Store:         {log.store_name}",
        f"Status:        {log.status.value.upper()}",
        f"Triggered By:  {log.triggered_by.value.capitalize()}",
        f"Started:       {log.started_at.strftime('%Y-%m-%d %H:%M:%S')}",
        f"Finished:      {log.finished_at.strftime('%Y-%m-%d %H:%M:%S') if log.finished_at else 'N/A'}",
    ]
    
    if log.finished_at:
        duration = (log.finished_at - log.started_at).total_seconds()
        lines.append(f"Duration:      {duration:.1f} seconds")
    
    lines.extend([
        "",
        "-"*80,
        "STATISTICS",
        "-"*80,
        "",
        f"Products Processed:    {log.products_processed}",
        f"Prices Set/Updated:    {log.products_price_set}",
        f"Prices Cleared:        {log.products_price_cleared}",
        f"Unchanged:             {log.products_unchanged}",
    ])
    
    if log.error_message:
        lines.extend([
            "",
            "-"*80,
            "ERROR DETAILS",
            "-"*80,
            "",
            f"Message: {log.error_message}",
        ])
        
        if log.error_details:
            lines.extend([
                "",
                "Stack Trace:",
                "-"*80,
                log.error_details,
            ])
    
    lines.append("")
    lines.append("="*80)
    
    content = "\n".join(lines)
    
    # Create filename from store name and timestamp
    filename = f"sync_log_{log.store_name.replace(' ', '_')}_{log.started_at.strftime('%Y%m%d_%H%M%S')}.txt"
    
    return PlainTextResponse(
        content=content,
        headers={"Content-Disposition": f'attachment; filename="{filename}"'}
    )
