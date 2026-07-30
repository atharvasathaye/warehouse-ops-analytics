"""
Pydantic models for the ERP API.
"""

from typing import List, Optional

from pydantic import BaseModel, Field

class ItemBase(BaseModel):
    """Base model for an item/product."""
    product_id: str = Field(..., description="Unique product identifier")
    product_category: Optional[str] = Field(None, description="Original product category name")
    product_category_english: Optional[str] = Field(None, description="English translation of product category name")
    weight_g: Optional[float] = Field(None, description="Product weight in grams")
    length_cm: Optional[float] = Field(None, description="Product length in centimeters")
    height_cm: Optional[float] = Field(None, description="Product height in centimeters")
    width_cm: Optional[float] = Field(None, description="Product width in centimeters")
    product_name_length: Optional[int] = Field(None, description="Length of the product name")
    product_description_length: Optional[int] = Field(None, description="Length of the product description")
    product_photos_qty: Optional[int] = Field(None, description="Quantity of product photos")

class ItemResponse(ItemBase):
    """Model for an item response."""
    pass

class ItemListResponse(BaseModel):
    """Model for a paginated list of items."""
    items: List[ItemResponse] = Field(..., description="List of items in the current page")
    total: int = Field(..., description="Total number of items available")
    skip: int = Field(..., description="Number of items skipped")
    limit: int = Field(..., description="Maximum number of items returned")

class CategoryListResponse(BaseModel):
    """Model for a list of categories."""
    categories: List[str] = Field(..., description="List of unique categories")
    total: int = Field(..., description="Total number of categories")

class HealthResponse(BaseModel):
    """Model for API health status."""
    status: str = Field(..., description="Health status string")
    item_count: int = Field(..., description="Number of items loaded in the store")
    timestamp: str = Field(..., description="Current server timestamp")
