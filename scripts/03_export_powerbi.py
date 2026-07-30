"""
Export processed data to Power BI-ready CSV files.

Reads from data/processed/ and outputs fact/dimension tables to data/powerbi/
following a star-schema design for Power BI consumption.
"""
import argparse
import logging
import sys
from pathlib import Path

import pandas as pd

# Ensure project root is on sys.path for imports
project_root = Path(__file__).resolve().parent.parent
if str(project_root) not in sys.path:
    sys.path.insert(0, str(project_root))

from src.utils.helpers import load_config, get_project_root

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)


def export_to_powerbi() -> None:
    """Export processed pipeline results to Power BI-ready CSV files."""
    root_dir = get_project_root()
    config = load_config()

    processed_dir = root_dir / config.get("data_paths", {}).get("processed", "data/processed")
    pbi_dir = root_dir / config.get("data_paths", {}).get("powerbi", "data/powerbi")
    raw_dir = root_dir / config.get("data_paths", {}).get("raw", "data/raw")

    if not processed_dir.exists():
        logger.error(f"Processed directory not found at {processed_dir}. Run the pipeline first.")
        return

    pbi_dir.mkdir(parents=True, exist_ok=True)
    logger.info(f"Exporting data from {processed_dir} to {pbi_dir}...")

    # -------------------------------------------------------
    # Load all processed data files
    # -------------------------------------------------------
    try:
        wms_orders = pd.read_csv(processed_dir / "wms_orders_processed.csv")
        wms_items = pd.read_csv(processed_dir / "wms_order_items_processed.csv")
        erp_products = pd.read_csv(processed_dir / "erp_products_processed.csv")
        tms_shipments = pd.read_csv(processed_dir / "tms_shipments_processed.csv")
        exceptions = pd.read_csv(processed_dir / "exceptions.csv")
        abc_classes = pd.read_csv(processed_dir / "abc_classification.csv")
        kpi_summary = pd.read_csv(processed_dir / "kpi_summary.csv")
    except FileNotFoundError as e:
        logger.error(f"Missing required processed file: {e}")
        logger.error("Run scripts/02_run_pipeline.py first.")
        return

    # Load optional KPI detail files
    cycle_time = _safe_load(processed_dir / "cycle_time.csv")
    fill_rate = _safe_load(processed_dir / "fill_rate.csv")
    dock_to_ship = _safe_load(processed_dir / "dock_to_ship.csv")
    otd = _safe_load(processed_dir / "on_time_delivery.csv")

    # -------------------------------------------------------
    # FACT: fact_orders.csv
    # Order-level with all timestamps and KPI columns
    # -------------------------------------------------------
    logger.info("Building fact_orders...")
    fact_orders = wms_orders.copy()

    # Merge cycle time
    if cycle_time is not None and "cycle_time_days" in cycle_time.columns:
        ct_cols = ["order_id", "cycle_time_days"]
        ct_cols = [c for c in ct_cols if c in cycle_time.columns]
        fact_orders = fact_orders.merge(cycle_time[ct_cols], on="order_id", how="left")

    # Merge dock-to-ship
    if dock_to_ship is not None and "dock_to_ship_hours" in dock_to_ship.columns:
        dts_cols = ["order_id", "dock_to_ship_hours"]
        dts_cols = [c for c in dts_cols if c in dock_to_ship.columns]
        fact_orders = fact_orders.merge(dock_to_ship[dts_cols], on="order_id", how="left")

    # Merge on-time delivery
    if otd is not None and "on_time" in otd.columns:
        otd_cols = ["order_id", "on_time"]
        otd_cols = [c for c in otd_cols if c in otd.columns]
        fact_orders = fact_orders.merge(otd[otd_cols], on="order_id", how="left")

    # Merge fill rate
    if fill_rate is not None and "fill_rate" in fill_rate.columns:
        fr_cols = ["order_id", "items_ordered", "items_delivered", "fill_rate"]
        fr_cols = [c for c in fr_cols if c in fill_rate.columns]
        fact_orders = fact_orders.merge(fill_rate[fr_cols], on="order_id", how="left")

    # Merge TMS carrier/delivery info
    tms_merge_cols = [c for c in ["order_id", "carrier_handoff_date", "delivered_date",
                                   "estimated_delivery_date", "item_count", "total_freight"]
                      if c in tms_shipments.columns]
    if "order_id" in tms_merge_cols:
        fact_orders = fact_orders.merge(
            tms_shipments[tms_merge_cols].drop_duplicates(subset=["order_id"]),
            on="order_id", how="left", suffixes=("", "_tms")
        )

    fact_orders.to_csv(pbi_dir / "fact_orders.csv", index=False)
    logger.info(f"  fact_orders: {len(fact_orders):,} rows")

    # -------------------------------------------------------
    # FACT: fact_order_items.csv
    # Line-item detail with ABC class
    # -------------------------------------------------------
    logger.info("Building fact_order_items...")
    abc_merge_cols = [c for c in ["product_id", "abc_class", "total_revenue", "rank"]
                      if c in abc_classes.columns]
    fact_items = wms_items.merge(
        abc_classes[abc_merge_cols], on="product_id", how="left"
    ) if "product_id" in abc_merge_cols else wms_items.copy()
    fact_items.to_csv(pbi_dir / "fact_order_items.csv", index=False)
    logger.info(f"  fact_order_items: {len(fact_items):,} rows")

    # -------------------------------------------------------
    # DIM: dim_products.csv
    # Product master with ABC class
    # -------------------------------------------------------
    logger.info("Building dim_products...")
    dim_products = erp_products.merge(
        abc_classes[abc_merge_cols], on="product_id", how="left"
    ) if "product_id" in abc_merge_cols else erp_products.copy()
    dim_products.to_csv(pbi_dir / "dim_products.csv", index=False)
    logger.info(f"  dim_products: {len(dim_products):,} rows")

    # -------------------------------------------------------
    # DIM: dim_sellers.csv
    # Seller info from TMS
    # -------------------------------------------------------
    logger.info("Building dim_sellers...")
    seller_cols = [c for c in ["seller_id", "seller_city", "seller_state"]
                   if c in tms_shipments.columns]
    if seller_cols:
        dim_sellers = tms_shipments[seller_cols].drop_duplicates()
        dim_sellers.to_csv(pbi_dir / "dim_sellers.csv", index=False)
        logger.info(f"  dim_sellers: {len(dim_sellers):,} rows")
    else:
        logger.warning("  Seller columns not found in TMS data, skipping dim_sellers.")

    # -------------------------------------------------------
    # DIM: dim_customers.csv
    # Customer info — load from raw Olist customers data
    # -------------------------------------------------------
    logger.info("Building dim_customers...")
    raw_customers_path = raw_dir / "olist_customers_dataset.csv"
    if raw_customers_path.exists():
        raw_customers = pd.read_csv(raw_customers_path)
        # Keep only customers present in our orders
        order_customer_ids = set(wms_orders["customer_id"].unique()) if "customer_id" in wms_orders.columns else set()
        dim_customers = raw_customers[raw_customers["customer_id"].isin(order_customer_ids)].copy()
        customer_keep_cols = [c for c in ["customer_id", "customer_unique_id", "customer_zip_code_prefix",
                                           "customer_city", "customer_state"]
                              if c in dim_customers.columns]
        dim_customers = dim_customers[customer_keep_cols].drop_duplicates(subset=["customer_id"])
        dim_customers.to_csv(pbi_dir / "dim_customers.csv", index=False)
        logger.info(f"  dim_customers: {len(dim_customers):,} rows")
    else:
        # Fallback: extract from TMS shipments
        cust_cols = [c for c in ["order_id", "customer_city", "customer_state"]
                     if c in tms_shipments.columns]
        if cust_cols:
            dim_customers = tms_shipments[cust_cols].drop_duplicates()
            dim_customers.to_csv(pbi_dir / "dim_customers.csv", index=False)
            logger.info(f"  dim_customers (from TMS): {len(dim_customers):,} rows")
        else:
            logger.warning("  Customer data not available, skipping dim_customers.")

    # -------------------------------------------------------
    # FACT: fact_exceptions.csv
    # -------------------------------------------------------
    logger.info("Building fact_exceptions...")
    exceptions.to_csv(pbi_dir / "fact_exceptions.csv", index=False)
    logger.info(f"  fact_exceptions: {len(exceptions):,} rows")

    # -------------------------------------------------------
    # FACT: fact_kpi_summary.csv
    # -------------------------------------------------------
    logger.info("Building fact_kpi_summary...")
    kpi_summary.to_csv(pbi_dir / "fact_kpi_summary.csv", index=False)
    logger.info(f"  fact_kpi_summary: {len(kpi_summary):,} rows")

    # -------------------------------------------------------
    # DATA DICTIONARY
    # -------------------------------------------------------
    logger.info("Building data_dictionary...")
    data_dict = _build_data_dictionary()
    pd.DataFrame(data_dict).to_csv(pbi_dir / "data_dictionary.csv", index=False)
    logger.info(f"  data_dictionary: {len(data_dict)} entries")

    logger.info("=" * 50)
    logger.info("Power BI export completed successfully!")
    logger.info(f"Output directory: {pbi_dir}")
    logger.info("=" * 50)


def _safe_load(path: Path) -> pd.DataFrame | None:
    """Load a CSV if it exists, else return None."""
    if path.exists():
        return pd.read_csv(path)
    logger.warning(f"Optional file not found: {path}")
    return None


def _build_data_dictionary() -> list[dict]:
    """Build a comprehensive data dictionary for all exported tables."""
    return [
        # fact_orders
        {"table": "fact_orders", "column": "order_id", "type": "string", "description": "Unique order identifier"},
        {"table": "fact_orders", "column": "customer_id", "type": "string", "description": "Customer identifier for this order"},
        {"table": "fact_orders", "column": "order_status", "type": "string", "description": "Current order status (delivered, shipped, canceled, etc.)"},
        {"table": "fact_orders", "column": "order_purchase_timestamp", "type": "datetime", "description": "Timestamp when the order was placed"},
        {"table": "fact_orders", "column": "order_approved_at", "type": "datetime", "description": "Timestamp when payment was approved"},
        {"table": "fact_orders", "column": "order_delivered_carrier_date", "type": "datetime", "description": "Timestamp when order was handed to carrier (WMS)"},
        {"table": "fact_orders", "column": "order_delivered_customer_date", "type": "datetime", "description": "Timestamp when order was delivered to customer (WMS)"},
        {"table": "fact_orders", "column": "order_estimated_delivery_date", "type": "datetime", "description": "Estimated delivery date at purchase time"},
        {"table": "fact_orders", "column": "cycle_time_days", "type": "float", "description": "Order cycle time from purchase to delivery (days)"},
        {"table": "fact_orders", "column": "dock_to_ship_hours", "type": "float", "description": "Time from approval to carrier handoff (hours)"},
        {"table": "fact_orders", "column": "on_time", "type": "boolean", "description": "Whether delivery was on or before estimated date"},
        {"table": "fact_orders", "column": "fill_rate", "type": "float", "description": "Ratio of items delivered vs items ordered"},
        # fact_order_items
        {"table": "fact_order_items", "column": "order_id", "type": "string", "description": "Order identifier (FK to fact_orders)"},
        {"table": "fact_order_items", "column": "product_id", "type": "string", "description": "Product identifier (FK to dim_products)"},
        {"table": "fact_order_items", "column": "seller_id", "type": "string", "description": "Seller identifier (FK to dim_sellers)"},
        {"table": "fact_order_items", "column": "price", "type": "float", "description": "Item unit price"},
        {"table": "fact_order_items", "column": "freight_value", "type": "float", "description": "Shipping cost for this item"},
        {"table": "fact_order_items", "column": "abc_class", "type": "string", "description": "ABC velocity classification (A/B/C)"},
        # dim_products
        {"table": "dim_products", "column": "product_id", "type": "string", "description": "Unique product identifier"},
        {"table": "dim_products", "column": "product_category", "type": "string", "description": "Product category (Portuguese)"},
        {"table": "dim_products", "column": "product_category_english", "type": "string", "description": "Product category (English)"},
        {"table": "dim_products", "column": "weight_g", "type": "float", "description": "Product weight in grams"},
        {"table": "dim_products", "column": "abc_class", "type": "string", "description": "ABC velocity classification (A/B/C)"},
        # dim_sellers
        {"table": "dim_sellers", "column": "seller_id", "type": "string", "description": "Unique seller identifier"},
        {"table": "dim_sellers", "column": "seller_city", "type": "string", "description": "Seller city"},
        {"table": "dim_sellers", "column": "seller_state", "type": "string", "description": "Seller state code"},
        # dim_customers
        {"table": "dim_customers", "column": "customer_id", "type": "string", "description": "Unique customer identifier per order"},
        {"table": "dim_customers", "column": "customer_city", "type": "string", "description": "Customer city"},
        {"table": "dim_customers", "column": "customer_state", "type": "string", "description": "Customer state code"},
        # fact_exceptions
        {"table": "fact_exceptions", "column": "exception_id", "type": "string", "description": "Unique exception identifier (EXC-NNNN)"},
        {"table": "fact_exceptions", "column": "exception_type", "type": "string", "description": "Type of exception detected"},
        {"table": "fact_exceptions", "column": "severity", "type": "string", "description": "Severity level (CRITICAL/WARNING/INFO)"},
        {"table": "fact_exceptions", "column": "source_system", "type": "string", "description": "System(s) involved in the exception"},
        {"table": "fact_exceptions", "column": "order_id", "type": "string", "description": "Associated order ID (if applicable)"},
        {"table": "fact_exceptions", "column": "description", "type": "string", "description": "Human-readable exception description"},
        # fact_kpi_summary
        {"table": "fact_kpi_summary", "column": "kpi_name", "type": "string", "description": "Name of the KPI metric"},
        {"table": "fact_kpi_summary", "column": "value", "type": "float", "description": "Computed KPI value"},
        {"table": "fact_kpi_summary", "column": "period", "type": "string", "description": "Time period for the KPI"},
        {"table": "fact_kpi_summary", "column": "unit", "type": "string", "description": "Unit of measurement"},
    ]


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Export processed data to Power BI-ready format.")
    parser.parse_args()
    export_to_powerbi()
