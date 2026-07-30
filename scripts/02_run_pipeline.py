"""
Full pipeline orchestrator for Warehouse Operations Analytics.

Orchestrates the complete data pipeline:
1. Ingest data from WMS (CSV), ERP (API or file fallback), and TMS (JSON)
2. Run cross-system reconciliation and exception detection
3. Compute warehouse KPIs
4. Save all results to the processed directory
"""
import argparse
import logging
import sys
from pathlib import Path

import pandas as pd
import yaml

# Ensure project root is on sys.path for imports
project_root = Path(__file__).resolve().parent.parent
if str(project_root) not in sys.path:
    sys.path.insert(0, str(project_root))

from src.ingestion import wms_ingest, erp_ingest, tms_ingest
from src.reconciliation import cross_system_matcher, quantity_checker, timestamp_validator, exception_report
from src.kpis import inventory_metrics, order_metrics, delivery_metrics, productivity_metrics
from src.utils.helpers import load_config, get_project_root, ensure_directories

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)


def run_pipeline(dry_run: bool = False, skip_api: bool = False) -> None:
    """Run the complete analytical pipeline.

    Args:
        dry_run: If True, only validate data existence without processing.
        skip_api: If True, skip ERP API ingestion and use file fallback.
    """
    root_dir = get_project_root()
    config = load_config()

    # Resolve paths from config
    staged_dir = root_dir / config.get("data_paths", {}).get("staged", "data/staged")
    processed_dir = root_dir / config.get("data_paths", {}).get("processed", "data/processed")
    processed_dir.mkdir(parents=True, exist_ok=True)

    wms_staged = staged_dir / "wms"
    erp_staged = staged_dir / "erp"
    tms_staged = staged_dir / "tms"

    # --- Dry Run: validate data existence only ---
    if dry_run:
        logger.info("=== DRY RUN: Validating data existence ===")
        all_ok = True
        for name, path in [("WMS", wms_staged), ("ERP", erp_staged), ("TMS", tms_staged)]:
            if path.exists():
                file_count = len(list(path.iterdir()))
                logger.info(f"  {name} directory exists at {path} ({file_count} files)")
            else:
                logger.error(f"  {name} directory MISSING at {path}")
                all_ok = False
        if all_ok:
            logger.info("All staged data directories found. Ready to run.")
        else:
            logger.error("Some data directories are missing. Run scripts/01_split_to_feeds.py first.")
        return

    # =========================================================
    # PHASE 1: DATA INGESTION
    # =========================================================
    logger.info("=" * 60)
    logger.info("PHASE 1: DATA INGESTION")
    logger.info("=" * 60)

    # --- WMS Ingestion (CSV) ---
    logger.info("Ingesting WMS data from CSV...")
    wms_orders, wms_order_items, wms_payments = wms_ingest.ingest_wms(wms_staged)
    logger.info(f"  WMS: {len(wms_orders):,} orders, {len(wms_order_items):,} items, {len(wms_payments):,} payments")

    # --- ERP Ingestion (API with file fallback) ---
    import os
    erp_api_config = config.get("erp_api", {})
    erp_url = os.getenv("ERP_API_BASE_URL") or erp_api_config.get("base_url", "http://localhost:8000")
    erp_page_size = int(os.getenv("ERP_API_PAGE_SIZE") or erp_api_config.get("page_size", 100))
    erp_timeout = int(os.getenv("ERP_API_TIMEOUT") or erp_api_config.get("timeout_seconds", 30))
    erp_retries = int(os.getenv("ERP_API_RETRIES") or erp_api_config.get("max_retries", 3))

    if skip_api:
        logger.info("Skipping ERP API (--skip-api flag set). Using file fallback.")
        erp_items = erp_ingest.ingest_erp_file(erp_staged)
    else:
        try:
            logger.info(f"Ingesting ERP data from API at {erp_url}...")
            erp_items = erp_ingest.ingest_erp_api(
                base_url=erp_url,
                page_size=erp_page_size,
                timeout=erp_timeout,
                max_retries=erp_retries,
            )
        except Exception as e:
            logger.warning(f"ERP API ingestion failed: {e}. Falling back to file ingestion.")
            erp_items = erp_ingest.ingest_erp_file(erp_staged)
    logger.info(f"  ERP: {len(erp_items):,} products")

    # --- TMS Ingestion (JSON) ---
    logger.info("Ingesting TMS data from JSON...")
    tms_shipments = tms_ingest.ingest_tms(tms_staged)
    logger.info(f"  TMS: {len(tms_shipments):,} shipments")

    # =========================================================
    # PHASE 2: RECONCILIATION & EXCEPTION DETECTION
    # =========================================================
    logger.info("=" * 60)
    logger.info("PHASE 2: RECONCILIATION & EXCEPTION DETECTION")
    logger.info("=" * 60)

    thresholds = config.get("thresholds", {})
    conflict_hours = thresholds.get("timestamp_conflict_hours", 2.0)
    price_tolerance = thresholds.get("price_mismatch_tolerance", 0.05)

    # Cross-system matching
    logger.info("Running cross-system order/item matching...")
    cross_exceptions = cross_system_matcher.match_orders_across_systems(
        wms_orders=wms_orders,
        tms_shipments=tms_shipments,
        erp_items=erp_items,
        wms_order_items=wms_order_items,
    )
    logger.info(f"  Cross-system exceptions: {len(cross_exceptions)}")

    # Quantity mismatches
    logger.info("Checking quantity mismatches...")
    qty_exceptions = quantity_checker.check_quantity_mismatches(
        wms_order_items=wms_order_items,
        tms_shipments=tms_shipments,
    )
    logger.info(f"  Quantity exceptions: {len(qty_exceptions)}")

    # Price anomalies
    logger.info("Checking price anomalies...")
    price_exceptions = quantity_checker.check_price_mismatches(
        wms_order_items=wms_order_items,
        erp_items=erp_items,
        tolerance=price_tolerance,
    )
    logger.info(f"  Price exceptions: {len(price_exceptions)}")

    # Timestamp validation
    logger.info("Validating timestamps...")
    ts_exceptions = timestamp_validator.validate_timestamps(
        wms_orders=wms_orders,
        tms_shipments=tms_shipments,
        conflict_threshold_hours=conflict_hours,
    )
    logger.info(f"  Timestamp exceptions: {len(ts_exceptions)}")

    # Generate consolidated exception report
    logger.info("Generating consolidated exception report...")
    exception_df = exception_report.generate_exception_report(
        cross_system_exceptions=cross_exceptions,
        quantity_exceptions=qty_exceptions,
        price_exceptions=price_exceptions,
        timestamp_exceptions=ts_exceptions,
    )
    exception_path = processed_dir / "exceptions.csv"
    exception_report.save_exception_report(exception_df, exception_path)
    logger.info(f"  Total exceptions: {len(exception_df)} → saved to {exception_path}")

    # =========================================================
    # PHASE 3: KPI COMPUTATION
    # =========================================================
    logger.info("=" * 60)
    logger.info("PHASE 3: KPI COMPUTATION")
    logger.info("=" * 60)

    abc_config = config.get("abc_classification", {})
    prod_config = config.get("productivity", {})

    # Inventory metrics
    logger.info("Computing inventory turns...")
    inv_turns_df = inventory_metrics.calculate_inventory_turns(
        order_items=wms_order_items,
        orders=wms_orders,
    )
    logger.info(f"  Inventory turns: {len(inv_turns_df)} monthly periods")

    logger.info("Computing ABC velocity classification...")
    abc_df = inventory_metrics.classify_abc(
        order_items=wms_order_items,
        a_threshold=abc_config.get("a_threshold", 0.80),
        b_threshold=abc_config.get("b_threshold", 0.95),
    )
    logger.info(f"  ABC classified: {len(abc_df)} products")

    # Order metrics
    logger.info("Computing order cycle time...")
    cycle_time_df = order_metrics.calculate_order_cycle_time(orders=wms_orders)
    logger.info(f"  Cycle time computed for {len(cycle_time_df)} orders")

    logger.info("Computing fill rate...")
    fill_rate_df = order_metrics.calculate_fill_rate(
        wms_order_items=wms_order_items,
        orders=wms_orders,
    )
    logger.info(f"  Fill rate computed for {len(fill_rate_df)} orders")

    # Delivery metrics
    logger.info("Computing dock-to-ship duration...")
    dock_ship_df = delivery_metrics.calculate_dock_to_ship(orders=wms_orders)
    logger.info(f"  Dock-to-ship computed for {len(dock_ship_df)} orders")

    logger.info("Computing on-time delivery...")
    otd_df = delivery_metrics.calculate_on_time_delivery(orders=wms_orders)
    logger.info(f"  OTD computed for {len(otd_df)} orders")

    # Productivity metrics
    logger.info("Computing picks per hour (simulated)...")
    picks_df = productivity_metrics.calculate_picks_per_hour(
        order_items=wms_order_items,
        orders=wms_orders,
        seconds_per_pick=prod_config.get("seconds_per_pick", 45),
    )
    logger.info(f"  Picks/hour computed for {len(picks_df)} days")

    # =========================================================
    # PHASE 4: SAVE RESULTS
    # =========================================================
    logger.info("=" * 60)
    logger.info("PHASE 4: SAVING RESULTS")
    logger.info("=" * 60)

    # Save processed source data
    wms_orders.to_csv(processed_dir / "wms_orders_processed.csv", index=False)
    wms_order_items.to_csv(processed_dir / "wms_order_items_processed.csv", index=False)
    wms_payments.to_csv(processed_dir / "wms_payments_processed.csv", index=False)
    erp_items.to_csv(processed_dir / "erp_products_processed.csv", index=False)
    tms_shipments.to_csv(processed_dir / "tms_shipments_processed.csv", index=False)

    # Save KPI outputs
    abc_df.to_csv(processed_dir / "abc_classification.csv", index=False)
    inv_turns_df.to_csv(processed_dir / "inventory_turns.csv", index=False)
    cycle_time_df.to_csv(processed_dir / "cycle_time.csv", index=False)
    fill_rate_df.to_csv(processed_dir / "fill_rate.csv", index=False)
    dock_ship_df.to_csv(processed_dir / "dock_to_ship.csv", index=False)
    otd_df.to_csv(processed_dir / "on_time_delivery.csv", index=False)
    picks_df.to_csv(processed_dir / "picks_per_hour.csv", index=False)

    # Build KPI summary table
    kpi_rows = []

    # Inventory turns (latest month)
    if not inv_turns_df.empty:
        latest_turns = inv_turns_df.iloc[-1]
        kpi_rows.append({"kpi_name": "Inventory Turns (Annualized)", "value": round(float(latest_turns.get("turns", 0)), 2), "period": str(latest_turns.get("period", "N/A")), "unit": "turns/year"})
        kpi_rows.append({"kpi_name": "Days on Hand", "value": round(float(latest_turns.get("days_on_hand", 0)), 1), "period": str(latest_turns.get("period", "N/A")), "unit": "days"})

    # Cycle time
    if not cycle_time_df.empty and "cycle_time_days" in cycle_time_df.columns:
        ct = cycle_time_df["cycle_time_days"].dropna()
        kpi_rows.append({"kpi_name": "Avg Order Cycle Time", "value": round(ct.mean(), 1), "period": "Overall", "unit": "days"})
        kpi_rows.append({"kpi_name": "Median Order Cycle Time", "value": round(ct.median(), 1), "period": "Overall", "unit": "days"})
        kpi_rows.append({"kpi_name": "P90 Order Cycle Time", "value": round(ct.quantile(0.90), 1), "period": "Overall", "unit": "days"})

    # Fill rate
    if not fill_rate_df.empty and "fill_rate" in fill_rate_df.columns:
        overall_fill = fill_rate_df["fill_rate"].mean() * 100
        kpi_rows.append({"kpi_name": "Fill Rate", "value": round(overall_fill, 1), "period": "Overall", "unit": "%"})

    # OTD
    if not otd_df.empty and "on_time" in otd_df.columns:
        otd_pct = otd_df["on_time"].mean() * 100
        kpi_rows.append({"kpi_name": "On-Time Delivery", "value": round(otd_pct, 1), "period": "Overall", "unit": "%"})

    # Dock-to-ship
    if not dock_ship_df.empty and "dock_to_ship_hours" in dock_ship_df.columns:
        dts = dock_ship_df["dock_to_ship_hours"].dropna()
        kpi_rows.append({"kpi_name": "Avg Dock-to-Ship", "value": round(dts.mean(), 1), "period": "Overall", "unit": "hours"})

    # Picks/hour
    if not picks_df.empty and "picks_per_hour" in picks_df.columns:
        avg_pph = picks_df["picks_per_hour"].mean()
        kpi_rows.append({"kpi_name": "Avg Picks/Hour", "value": round(avg_pph, 1), "period": "Overall", "unit": "picks/hour"})

    # Exception count
    kpi_rows.append({"kpi_name": "Total Exceptions", "value": len(exception_df), "period": "Overall", "unit": "count"})

    kpi_summary = pd.DataFrame(kpi_rows)
    kpi_summary.to_csv(processed_dir / "kpi_summary.csv", index=False)

    logger.info(f"All results saved to {processed_dir}")

    # =========================================================
    # SUMMARY REPORT
    # =========================================================
    print("\n" + "=" * 60)
    print("  WAREHOUSE OPERATIONS ANALYTICS — PIPELINE SUMMARY")
    print("=" * 60)
    print(f"\n  Data Ingested:")
    print(f"    WMS:  {len(wms_orders):>8,} orders | {len(wms_order_items):>8,} items")
    print(f"    ERP:  {len(erp_items):>8,} products")
    print(f"    TMS:  {len(tms_shipments):>8,} shipments")
    print(f"\n  Exceptions Detected: {len(exception_df):,}")
    if not exception_df.empty:
        severity_counts = exception_df["severity"].value_counts()
        for sev in ["CRITICAL", "WARNING", "INFO"]:
            if sev in severity_counts.index:
                print(f"    {sev}: {severity_counts[sev]:,}")
    print(f"\n  KPI Summary:")
    print(kpi_summary.to_string(index=False))
    print("\n" + "=" * 60 + "\n")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="Run the Warehouse Operations Analytics Pipeline."
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Validate data existence without processing.",
    )
    parser.add_argument(
        "--skip-api",
        action="store_true",
        help="Skip ERP API ingestion and use file fallback.",
    )
    args = parser.parse_args()

    run_pipeline(dry_run=args.dry_run, skip_api=args.skip_api)
