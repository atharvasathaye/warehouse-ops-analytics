"""
Router for item-related API endpoints.
"""

from typing import Optional

from fastapi import APIRouter, HTTPException, Query

from erp_api.models import CategoryListResponse, ItemListResponse, ItemResponse
from erp_api.data_loader import store

router = APIRouter(prefix="/items", tags=["items"])

@router.get("/", response_model=ItemListResponse, description="Get a paginated list of items")
def get_items(
    category: Optional[str] = Query(None, description="Filter items by category"),
    skip: int = Query(0, ge=0, description="Number of items to skip"),
    limit: int = Query(100, ge=1, le=1000, description="Maximum number of items to return")
) -> ItemListResponse:
    """
    Retrieves a paginated list of items, optionally filtered by category.
    """
    items, total = store.get_items(category=category, skip=skip, limit=limit)
    return ItemListResponse(
        items=items,
        total=total,
        skip=skip,
        limit=limit
    )

@router.get("/categories", response_model=CategoryListResponse, description="Get a list of all item categories")
def get_categories() -> CategoryListResponse:
    """
    Retrieves a list of all unique categories.
    """
    categories, total = store.get_categories()
    return CategoryListResponse(
        categories=categories,
        total=total
    )

@router.get("/{product_id}", response_model=ItemResponse, description="Get a single item by ID")
def get_item(product_id: str) -> ItemResponse:
    """
    Retrieves a single item by its product ID.
    Raises 404 if the item is not found.
    """
    item = store.get_item(product_id)
    if not item:
        raise HTTPException(status_code=404, detail=f"Item with id '{product_id}' not found")
    return ItemResponse(**item)
