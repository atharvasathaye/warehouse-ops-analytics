"""
Script to split raw Olist CSVs into three system feeds (WMS, TMS, ERP) with injected drift.
"""
import logging
import json
import random
from pathlib import Path
from datetime import timedelta
import pandas as pd
import numpy as np

# Ensure src modules can be imported
import sys
project_root_str = str(Path(__file__).parent.parent.resolve())
if project_root_str not in sys.path:
    sys.path.append(project_root_str)

from src.utils.helpers import load_config, get_project_root

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(name)s: %(message)s")
logger = logging.getLogger(__name__)

def inject_wms_drift(
    orders: pd.DataFrame, 
    order_items: pd.DataFrame, 
    payments: pd.DataFrame, 
    config: dict, 
    manifest: dict
) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    """Inject drift into WMS feed data."""
    logger.info("Injecting drift into WMS feed...")
    drift_conf = config.get("drift_injection", {})
    random.seed(drift_conf.get("random_seed", 42))
    np.random.seed(drift_conf.get("random_seed", 42))
    
    # 1. Drop order items
    drop_pct = drift_conf.get("wms_drop_pct", 0.02)
    drop_count = int(len(order_items) * drop_pct)
    drop_indices = np.random.choice(order_items.index, drop_count, replace=False)
    dropped_items = order_items.loc[drop_indices, "order_id"].tolist()
    order_items_drifted = order_items.drop(drop_indices)
    
    manifest["wms"] = {
        "dropped_items_count": drop_count,
        "dropped_items_pct": drop_pct * 100,
        "dropped_order_ids_sample": dropped_items[:10]
    }
    logger.info(f"Dropped {drop_count} WMS order items ({drop_pct * 100:.1f}%)")
    
    # 2. Jitter timestamps
    jitter_hours = drift_conf.get("timestamp_jitter_hours", 2)
    jitter_pct = drift_conf.get("timestamp_jitter_pct", 0.03)
    orders_drifted = orders.copy()
    
    # Ensure datetime type
    orders_drifted["order_approved_at"] = pd.to_datetime(orders_drifted["order_approved_at"], errors="coerce")
    valid_mask = orders_drifted["order_approved_at"].notna()
    
    jitter_count = int(valid_mask.sum() * jitter_pct)
    valid_indices = orders_drifted[valid_mask].index
    jitter_indices = np.random.choice(valid_indices, jitter_count, replace=False)
    
    jitters = [timedelta(hours=random.uniform(-jitter_hours, jitter_hours)) for _ in range(jitter_count)]
    orders_drifted.loc[jitter_indices, "order_approved_at"] += jitters
    
    manifest["wms"]["timestamp_jitter_count"] = jitter_count
    logger.info(f"Jittered timestamps on {jitter_count} WMS orders")
    
    # 3. Price rounding discrepancies
    price_rounding_error = drift_conf.get("price_rounding_error", 0.01)
    price_error_pct = drift_conf.get("price_error_pct", 0.01)
    
    price_error_count = int(len(order_items_drifted) * price_error_pct)
    price_indices = np.random.choice(order_items_drifted.index, price_error_count, replace=False)
    
    errors = np.random.uniform(-price_rounding_error, price_rounding_error, price_error_count)
    order_items_drifted.loc[price_indices, "price"] += errors
    order_items_drifted["price"] = order_items_drifted["price"].round(2)
    
    manifest["wms"]["price_rounding_error_count"] = price_error_count
    logger.info(f"Introduced price rounding errors on {price_error_count} WMS items")
    
    return orders_drifted, order_items_drifted, payments.copy()

def build_tms_feed(
    orders: pd.DataFrame, 
    order_items: pd.DataFrame, 
    sellers: pd.DataFrame, 
    customers: pd.DataFrame, 
    config: dict,
    manifest: dict
) -> list[dict]:
    """Build TMS feed and inject drift."""
    logger.info("Building TMS feed...")
    drift_conf = config.get("drift_injection", {})
    random.seed(drift_conf.get("random_seed", 42))
    
    # Filter for delivered orders
    delivered = orders[orders["order_status"] == "delivered"].copy()
    
    # Aggregate item counts and freight
    item_agg = order_items.groupby("order_id").agg(
        item_count=("order_item_id", "count"),
        total_freight=("freight_value", "sum"),
        seller_id=("seller_id", "first") # Assuming single seller per order for simplicity
    ).reset_index()
    
    # Merge data
    df = delivered.merge(item_agg, on="order_id", how="inner")
    df = df.merge(customers[["customer_id", "customer_city", "customer_state"]], on="customer_id", how="left")
    df = df.merge(sellers[["seller_id", "seller_city", "seller_state"]], on="seller_id", how="left")
    
    # Format dates
    for col in ["order_delivered_carrier_date", "order_delivered_customer_date", "order_estimated_delivery_date"]:
        df[col] = pd.to_datetime(df[col], errors="coerce").dt.strftime("%Y-%m-%dT%H:%M:%S")
        
    records = []
    for _, row in df.iterrows():
        records.append({
            "shipment_id": f"SHP-{str(row['order_id'])[:8]}",
            "order_id": row["order_id"],
            "seller_id": row["seller_id"],
            "seller_city": row["seller_city"],
            "seller_state": row["seller_state"],
            "customer_city": row["customer_city"],
            "customer_state": row["customer_state"],
            "carrier_handoff_date": row["order_delivered_carrier_date"],
            "delivered_date": row["order_delivered_customer_date"],
            "estimated_delivery_date": row["order_estimated_delivery_date"],
            "item_count": int(row["item_count"]) if pd.notna(row["item_count"]) else 0,
            "total_freight": float(row["total_freight"]) if pd.notna(row["total_freight"]) else 0.0
        })
        
    logger.info(f"Built {len(records)} initial TMS shipment records")
    
    # Inject Drift
    # 1. Drop shipments
    drop_pct = drift_conf.get("tms_drop_pct", 0.01)
    drop_count = int(len(records) * drop_pct)
    if drop_count > 0:
        drop_indices = set(random.sample(range(len(records)), drop_count))
        records_drifted = [r for i, r in enumerate(records) if i not in drop_indices]
    else:
        records_drifted = records[:]
        
    manifest["tms"] = {
        "dropped_shipments_count": drop_count,
        "dropped_shipments_pct": drop_pct * 100
    }
    logger.info(f"Dropped {drop_count} TMS shipment records ({drop_pct * 100:.1f}%)")
    
    # 2. Shift carrier handoff dates
    shift_pct = drift_conf.get("tms_shift_pct", 0.02)
    shift_hours = drift_conf.get("tms_shift_hours", 24)
    shift_count = int(len(records_drifted) * shift_pct)
    
    if shift_count > 0:
        shift_indices = random.sample(range(len(records_drifted)), shift_count)
        shifted = 0
        for idx in shift_indices:
            r = records_drifted[idx]
            if r["carrier_handoff_date"] and str(r["carrier_handoff_date"]) != "NaT":
                try:
                    dt = pd.to_datetime(r["carrier_handoff_date"])
                    dt += timedelta(hours=random.uniform(-shift_hours, shift_hours))
                    r["carrier_handoff_date"] = dt.strftime("%Y-%m-%dT%H:%M:%S")
                    shifted += 1
                except Exception:
                    pass
        
        manifest["tms"]["shifted_handoff_date_count"] = shifted
        logger.info(f"Shifted carrier handoff dates on {shifted} TMS records")
        
    return records_drifted

def inject_erp_drift(products: pd.DataFrame, translations: pd.DataFrame, config: dict, manifest: dict) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Inject drift into ERP data."""
    logger.info("Injecting drift into ERP feed...")
    drift_conf = config.get("drift_injection", {})
    random.seed(drift_conf.get("random_seed", 42))
    np.random.seed(drift_conf.get("random_seed", 42))
    
    # 1. Drop products
    drop_pct = drift_conf.get("erp_drop_pct", 0.01)
    drop_count = int(len(products) * drop_pct)
    drop_indices = np.random.choice(products.index, drop_count, replace=False)
    products_drifted = products.drop(drop_indices)
    
    manifest["erp"] = {
        "dropped_products_count": drop_count,
        "dropped_products_pct": drop_pct * 100
    }
    logger.info(f"Dropped {drop_count} ERP products ({drop_pct * 100:.1f}%)")
    
    # 2. Alter category names
    translations_drifted = translations.copy()
    alter_pct = drift_conf.get("erp_category_alter_pct", 0.005)
    alter_count = max(1, int(len(translations_drifted) * alter_pct))
    
    alter_indices = np.random.choice(translations_drifted.index, alter_count, replace=False)
    translations_drifted.loc[alter_indices, "product_category_name_english"] += " [v2]"
    
    manifest["erp"]["altered_category_count"] = alter_count
    logger.info(f"Altered {alter_count} ERP category names")
    
    # Merge translation to create a unified view for ERP if needed, but returning both
    return products_drifted, translations_drifted

def main() -> None:
    """Main execution function."""
    root_dir = get_project_root()
    config = load_config()
    
    raw_dir = root_dir / "data" / "raw"
    staged_dir = root_dir / "data" / "staged"
    
    wms_dir = staged_dir / "wms"
    tms_dir = staged_dir / "tms"
    erp_dir = staged_dir / "erp"
    
    for d in [wms_dir, tms_dir, erp_dir]:
        d.mkdir(parents=True, exist_ok=True)
        
    manifest = {}
    
    # Load raw data
    logger.info("Loading raw CSV files...")
    try:
        orders = pd.read_csv(raw_dir / "olist_orders_dataset.csv")
        order_items = pd.read_csv(raw_dir / "olist_order_items_dataset.csv")
        payments = pd.read_csv(raw_dir / "olist_order_payments_dataset.csv")
        customers = pd.read_csv(raw_dir / "olist_customers_dataset.csv")
        sellers = pd.read_csv(raw_dir / "olist_sellers_dataset.csv")
        products = pd.read_csv(raw_dir / "olist_products_dataset.csv")
        translations = pd.read_csv(raw_dir / "product_category_name_translation.csv")
    except FileNotFoundError as e:
        logger.error(f"Failed to load raw data: {e}")
        logger.error("Please run scripts/00_download_data.py first and ensure data is downloaded.")
        sys.exit(1)
        
    # Process WMS
    wms_orders, wms_items, wms_payments = inject_wms_drift(orders, order_items, payments, config, manifest)
    wms_orders.to_csv(wms_dir / "wms_orders.csv", index=False)
    wms_items.to_csv(wms_dir / "wms_order_items.csv", index=False)
    wms_payments.to_csv(wms_dir / "wms_payments.csv", index=False)
    logger.info("WMS feed saved successfully.")
    
    # Process TMS
    tms_records = build_tms_feed(orders, order_items, sellers, customers, config, manifest)
    with open(tms_dir / "shipments.json", "w") as f:
        json.dump(tms_records, f, indent=2)
    logger.info("TMS feed saved successfully.")
    
    # Process ERP
    erp_products, erp_categories = inject_erp_drift(products, translations, config, manifest)
    erp_products.to_csv(erp_dir / "erp_products.csv", index=False)
    erp_categories.to_csv(erp_dir / "erp_categories.csv", index=False)
    logger.info("ERP feed saved successfully.")
    
    # Save manifest
    with open(staged_dir / "drift_manifest.json", "w") as f:
        json.dump(manifest, f, indent=2)
    logger.info("Drift manifest saved.")
    
    logger.info("Data splitting and drift injection completed!")

if __name__ == "__main__":
    main()
