"""
Store management routes.
"""

import asyncio
from fastapi import APIRouter, Request, Form, Depends, HTTPException
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates

from ..dependencies import get_db, require_auth
from ..db import Store, SyncStatus, TriggerType, generate_uuid
from ..processor import run_specific_store

router = APIRouter(prefix="/stores", dependencies=[Depends(require_auth)])
templates = Jinja2Templates(directory="app/templates")


@router.get("", response_class=HTMLResponse)
async def list_stores(request: Request):
    """List all stores."""
    db = get_db()
    stores = await db.get_stores()
    
    return templates.TemplateResponse(
        "stores/list.html",
        {"request": request, "stores": stores}
    )


@router.get("/new", response_class=HTMLResponse)
async def new_store_form(request: Request):
    """Show form to create new store."""
    return templates.TemplateResponse(
        "stores/create.html",
        {"request": request, "error": None}
    )


@router.post("/new")
async def create_store(
    request: Request,
    name: str = Form(...),
    shopify_domain: str = Form(...),
    api_token: str = Form(...)
):
    """Create a new store."""
    db = get_db()
    
    if not name or not shopify_domain or not api_token:
        return templates.TemplateResponse(
            "stores/create.html",
            {"request": request, "error": "All fields are required"},
            status_code=400
        )
    
    # Clean up domain
    shopify_domain = shopify_domain.strip().lower()
    if not shopify_domain.endswith(".myshopify.com"):
        if ".myshopify.com" not in shopify_domain:
            shopify_domain = f"{shopify_domain}.myshopify.com"
    
    try:
        store = Store(
            id=generate_uuid(),
            name=name.strip(),
            shopify_domain=shopify_domain,
            api_token=api_token.strip()
        )
        
        await db.create_store(store)
        return RedirectResponse(url="/stores", status_code=303)
        
    except Exception as e:
        return templates.TemplateResponse(
            "stores/create.html",
            {"request": request, "error": f"Failed to create store: {e}"},
            status_code=500
        )


@router.get("/{store_id}", response_class=HTMLResponse)
async def edit_store_form(request: Request, store_id: str):
    """Show form to edit a store."""
    db = get_db()
    store = await db.get_store(store_id)
    
    if not store:
        raise HTTPException(status_code=404, detail="Store not found")
    
    return templates.TemplateResponse(
        "stores/edit.html",
        {"request": request, "store": store, "error": None, "success": None}
    )


@router.post("/{store_id}")
async def update_store(
    request: Request,
    store_id: str,
    name: str = Form(...),
    shopify_domain: str = Form(...),
    is_paused: bool = Form(False),
    api_token: str = Form(None)
):
    """Update a store."""
    db = get_db()
    
    store = await db.get_store(store_id)
    if not store:
        raise HTTPException(status_code=404, detail="Store not found")
    
    # Clean up domain
    shopify_domain = shopify_domain.strip().lower()
    if not shopify_domain.endswith(".myshopify.com"):
        if ".myshopify.com" not in shopify_domain:
            shopify_domain = f"{shopify_domain}.myshopify.com"
    
    try:
        update_data = {
            "name": name.strip(),
            "shopify_domain": shopify_domain,
            "is_paused": is_paused
        }
        
        # Only update token if provided
        if api_token and api_token.strip():
            update_data["api_token"] = api_token.strip()
        
        await db.update_store(store_id, **update_data)
        store = await db.get_store(store_id)
        
        return templates.TemplateResponse(
            "stores/edit.html",
            {"request": request, "store": store, "error": None, "success": "Store updated successfully"}
        )
        
    except Exception as e:
        return templates.TemplateResponse(
            "stores/edit.html",
            {"request": request, "store": store, "error": f"Failed to update: {e}", "success": None},
            status_code=500
        )


@router.post("/{store_id}/delete")
async def delete_store(request: Request, store_id: str):
    """Delete a store."""
    db = get_db()
    
    store = await db.get_store(store_id)
    if not store:
        raise HTTPException(status_code=404, detail="Store not found")
    
    await db.delete_store(store_id)
    return RedirectResponse(url="/stores", status_code=303)


@router.post("/{store_id}/pause")
async def toggle_pause(request: Request, store_id: str):
    """Toggle store pause status."""
    db = get_db()
    
    store = await db.get_store(store_id)
    if not store:
        raise HTTPException(status_code=404, detail="Store not found")
    
    await db.update_store(store_id, is_paused=not store.is_paused)
    return RedirectResponse(url="/stores", status_code=303)


@router.post("/{store_id}/sync")
async def trigger_sync(request: Request, store_id: str):
    """Trigger sync for a single store."""
    db = get_db()
    
    store = await db.get_store(store_id)
    if not store:
        raise HTTPException(status_code=404, detail="Store not found")
    
    if store.is_paused:
        return templates.TemplateResponse(
            "stores/edit.html",
            {"request": request, "store": store, "error": "Cannot sync paused store", "success": None},
            status_code=400
        )
    
    # Run sync in background
    asyncio.create_task(run_specific_store(store_id, db, TriggerType.MANUAL))
    
    return RedirectResponse(url=f"/logs", status_code=303)
