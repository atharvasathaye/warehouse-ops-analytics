import logging
import time
from pathlib import Path
import pandas as pd
import httpx

logger = logging.getLogger(__name__)

def ingest_erp_file(staged_path: Path) -> pd.DataFrame:
    """
    Fallback method to ingest ERP data directly from staged CSV files.
    
    Args:
        staged_path: Path to the staged ERP directory.
        
    Returns:
        pd.DataFrame: DataFrame containing joined product and category data.
    """
    logger.info(f"Ingesting ERP data from local files at {staged_path}")
    
    products_file = staged_path / "erp_products.csv"
    categories_file = staged_path / "erp_categories.csv"
    
    if not products_file.exists() or not categories_file.exists():
        raise FileNotFoundError("ERP staged files (products or categories) are missing.")
        
    products = pd.read_csv(products_file)
    categories = pd.read_csv(categories_file)
    
    df = products.merge(categories, on="product_category_name", how="left")
    
    # Rename columns to match expected schema
    rename_map = {
        "product_category_name": "product_category",
        "product_category_name_english": "product_category_english",
        "product_weight_g": "weight_g",
        "product_length_cm": "length_cm",
        "product_height_cm": "height_cm",
        "product_width_cm": "width_cm"
    }
    df = df.rename(columns=rename_map)
    
    expected_cols = [
        "product_id", "product_category", "product_category_english", 
        "weight_g", "length_cm", "height_cm", "width_cm"
    ]
    
    # Select available columns
    available_cols = [c for c in expected_cols if c in df.columns]
    df = df[available_cols]
    
    logger.info(f"Ingested {len(df):,} ERP product records from file.")
    return df

def ingest_erp_api(base_url: str, page_size: int = 100, timeout: int = 30, max_retries: int = 3) -> pd.DataFrame:
    """
    Ingest ERP product data from a REST API endpoint with pagination and retries.
    
    Args:
        base_url: The base URL for the ERP API (e.g., http://localhost:8000/api/v1).
        page_size: Number of records to fetch per page.
        timeout: Request timeout in seconds.
        max_retries: Maximum number of retry attempts for failed requests.
        
    Returns:
        pd.DataFrame: DataFrame containing product data.
    """
    logger.info(f"Ingesting ERP data from API: {base_url}/items")
    all_items = []
    skip = 0
    page_num = 0
    
    with httpx.Client(timeout=timeout) as client:
        while True:
            url = f"{base_url}/items"
            params = {"skip": skip, "limit": page_size}
            
            success = False
            items = []
            for attempt in range(1, max_retries + 1):
                try:
                    page_num += 1
                    logger.debug(f"Fetching page {page_num} (skip={skip}, attempt {attempt})")
                    response = client.get(url, params=params)
                    response.raise_for_status()
                    
                    data = response.json()
                    items = data.get("items", [])
                    if items:
                        all_items.extend(items)
                        
                    success = True
                    break
                    
                except (httpx.RequestError, httpx.HTTPStatusError) as e:
                    logger.warning(f"API request failed on attempt {attempt}: {e}")
                    if attempt < max_retries:
                        sleep_time = 2 ** attempt  # Exponential backoff
                        logger.info(f"Retrying in {sleep_time} seconds...")
                        time.sleep(sleep_time)
                    else:
                        logger.error(f"Max retries reached for skip={skip}.")
                        raise
                        
            if not success or not items or len(items) < page_size:
                # Reached end of results
                break
                
            skip += page_size
            
    df = pd.DataFrame(all_items)
    logger.info(f"Ingested {len(df):,} ERP product records from API across {page_num} pages.")
    
    expected_cols = [
        "product_id", "product_category", "product_category_english", 
        "weight_g", "length_cm", "height_cm", "width_cm"
    ]
    
    if not df.empty:
        # Filter strictly for available expected columns
        available_cols = [c for c in expected_cols if c in df.columns]
        df = df[available_cols]
    
    return df
