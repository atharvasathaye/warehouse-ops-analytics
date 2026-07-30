"""
Data loading and storage for the ERP API.
"""

from pathlib import Path
from typing import List, Optional

import pandas as pd
import numpy as np

def load_item_master(data_path: Path) -> pd.DataFrame:
    """
    Loads products and translation datasets and merges them.
    
    Supports two file naming conventions:
    - Raw Olist: olist_products_dataset.csv + product_category_name_translation.csv
    - Staged/drifted: erp_products.csv + erp_categories.csv
    
    Args:
        data_path (Path): Path to the data directory containing the CSV files.
        
    Returns:
        pd.DataFrame: Merged item master DataFrame.
    """
    # Try staged filenames first, then raw filenames
    products_file = data_path / "erp_products.csv"
    translations_file = data_path / "erp_categories.csv"
    
    if not products_file.exists():
        products_file = data_path / "olist_products_dataset.csv"
        translations_file = data_path / "product_category_name_translation.csv"
    
    if not products_file.exists():
        return pd.DataFrame()
        
    products_df = pd.read_csv(products_file)
    
    if translations_file.exists():
        translations_df = pd.read_csv(translations_file)
        # Merge on product_category_name
        merged_df = pd.merge(
            products_df, 
            translations_df, 
            on="product_category_name", 
            how="left"
        )
    else:
        merged_df = products_df
        merged_df["product_category_name_english"] = None
        
    # Rename columns to match Pydantic model
    rename_mapping = {
        "product_category_name": "product_category",
        "product_category_name_english": "product_category_english",
        "product_weight_g": "weight_g",
        "product_length_cm": "length_cm",
        "product_height_cm": "height_cm",
        "product_width_cm": "width_cm"
    }
    
    # Only rename columns that actually exist
    existing_renames = {k: v for k, v in rename_mapping.items() if k in merged_df.columns}
    merged_df.rename(columns=existing_renames, inplace=True)
    
    # Replace NaN with None for JSON serialization
    merged_df = merged_df.replace({np.nan: None})
    return merged_df

class ItemMasterStore:
    """Singleton-like store for item master data."""
    
    _instance = None
    
    def __new__(cls):
        if cls._instance is None:
            cls._instance = super(ItemMasterStore, cls).__new__(cls)
            cls._instance._df = pd.DataFrame()
            cls._instance._items = []
        return cls._instance
        
    def load_data(self, raw_data_path: Path) -> None:
        """
        Loads data into the store.
        
        Args:
            raw_data_path (Path): Path to the raw data directory.
        """
        self._df = load_item_master(raw_data_path)
        if not self._df.empty:
            self._items = self._df.to_dict(orient="records")
        else:
            self._items = []
            
    def get_item(self, product_id: str) -> Optional[dict]:
        """
        Retrieves a single item by product_id.
        
        Args:
            product_id (str): The product ID to retrieve.
            
        Returns:
            Optional[dict]: Item dictionary if found, else None.
        """
        for item in self._items:
            if item.get("product_id") == product_id:
                return item
        return None
        
    def get_items(self, category: Optional[str] = None, skip: int = 0, limit: int = 100) -> tuple[List[dict], int]:
        """
        Retrieves a paginated list of items, optionally filtered by category.
        
        Args:
            category (Optional[str], optional): Category to filter by. Defaults to None.
            skip (int, optional): Number of items to skip. Defaults to 0.
            limit (int, optional): Maximum items to return. Defaults to 100.
            
        Returns:
            tuple[List[dict], int]: A tuple containing the list of items and total count.
        """
        filtered_items = self._items
        if category:
            filtered_items = [
                item for item in self._items 
                if item.get("product_category") == category or item.get("product_category_english") == category
            ]
            
        total = len(filtered_items)
        paginated_items = filtered_items[skip:skip + limit]
        return paginated_items, total
        
    def get_categories(self) -> tuple[List[str], int]:
        """
        Retrieves a list of unique categories.
        
        Returns:
            tuple[List[str], int]: A tuple containing the list of categories and total count.
        """
        if self._df.empty:
            return [], 0
            
        # Get unique values from product_category, ignoring None/NaN
        categories = sorted([
            cat for cat in self._df["product_category"].unique() 
            if pd.notna(cat)
        ])
        return categories, len(categories)
        
    def count(self) -> int:
        """
        Returns the total number of items in the store.
        
        Returns:
            int: Total item count.
        """
        return len(self._items)

# Global instance for easier import and usage
store = ItemMasterStore()
