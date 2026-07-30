import json
import logging
from pathlib import Path
import pandas as pd

logger = logging.getLogger(__name__)

def ingest_tms(staged_path: Path) -> pd.DataFrame:
    """
    Ingest TMS shipments data from staged JSON file.
    
    Reads shipments.json, flattens to DataFrame, parses dates,
    and validates schema.
    
    Args:
        staged_path: Path to the staged TMS directory.
        
    Returns:
        pd.DataFrame: DataFrame containing shipments data.
    """
    logger.info(f"Ingesting TMS feed from {staged_path}")
    
    file_path = staged_path / "shipments.json"
    
    if not file_path.exists():
        raise FileNotFoundError(f"TMS shipments file not found at {file_path}")
        
    with open(file_path, "r") as f:
        data = json.load(f)
        
    df = pd.DataFrame(data)
    
    # Validate schema
    expected_columns = {
        "shipment_id", "order_id", "seller_id", "seller_city", "seller_state",
        "customer_city", "customer_state", "carrier_handoff_date", 
        "delivered_date", "estimated_delivery_date", "item_count", "total_freight"
    }
    
    if not expected_columns.issubset(df.columns):
        missing = expected_columns - set(df.columns)
        logger.warning(f"TMS shipments DataFrame missing expected columns: {missing}")
        
    # Parse datetimes
    date_columns = ["carrier_handoff_date", "delivered_date", "estimated_delivery_date"]
    for col in date_columns:
        if col in df.columns:
            df[col] = pd.to_datetime(df[col], errors="coerce")
            
    # Ensure numeric columns
    if "item_count" in df.columns:
        df["item_count"] = pd.to_numeric(df["item_count"], errors="coerce")
    if "total_freight" in df.columns:
        df["total_freight"] = pd.to_numeric(df["total_freight"], errors="coerce")
        
    logger.info(f"Ingested {len(df):,} TMS shipment records.")
    return df
