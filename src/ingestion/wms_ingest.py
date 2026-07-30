import logging
from pathlib import Path
import pandas as pd

logger = logging.getLogger(__name__)

def ingest_wms(staged_path: Path) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    """
    Ingest WMS data feeds from the staged directory.
    
    Reads wms_orders.csv, wms_order_items.csv, wms_payments.csv.
    Normalizes columns and parses timestamps.
    
    Args:
        staged_path: Path to the staged WMS directory.
        
    Returns:
        tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
            (orders_df, order_items_df, payments_df)
    """
    logger.info(f"Ingesting WMS feeds from {staged_path}")
    
    orders_file = staged_path / "wms_orders.csv"
    items_file = staged_path / "wms_order_items.csv"
    payments_file = staged_path / "wms_payments.csv"
    
    if not all(p.exists() for p in [orders_file, items_file, payments_file]):
        raise FileNotFoundError("One or more WMS staged files are missing.")
        
    orders_df = pd.read_csv(orders_file)
    items_df = pd.read_csv(items_file)
    payments_df = pd.read_csv(payments_file)
    for df in [orders_df, items_df, payments_df]:
        df.columns = [str(c).strip().lower() for c in df.columns]
    expected_orders = {"order_id", "customer_id", "order_status", "order_purchase_timestamp"}
    expected_items = {"order_id", "order_item_id", "product_id", "price"}
    expected_payments = {"order_id", "payment_type", "payment_value"}
    
    if not expected_orders.issubset(orders_df.columns):
        logger.warning(f"Orders DataFrame missing expected columns. Found: {orders_df.columns}")
    if not expected_items.issubset(items_df.columns):
        logger.warning(f"Order Items DataFrame missing expected columns. Found: {items_df.columns}")
    if not expected_payments.issubset(payments_df.columns):
        logger.warning(f"Payments DataFrame missing expected columns. Found: {payments_df.columns}")
    time_cols = [
        "order_purchase_timestamp", 
        "order_approved_at", 
        "order_delivered_carrier_date",
        "order_delivered_customer_date", 
        "order_estimated_delivery_date"
    ]
    for col in time_cols:
        if col in orders_df.columns:
            orders_df[col] = pd.to_datetime(orders_df[col], errors="coerce")
    if "shipping_limit_date" in items_df.columns:
        items_df["shipping_limit_date"] = pd.to_datetime(items_df["shipping_limit_date"], errors="coerce")
        
    logger.info(f"Ingested {len(orders_df):,} WMS orders.")
    logger.info(f"Ingested {len(items_df):,} WMS order items.")
    logger.info(f"Ingested {len(payments_df):,} WMS payments.")
    
    return orders_df, items_df, payments_df
