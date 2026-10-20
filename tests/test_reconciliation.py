"""
Tests for reconciliation modules.
"""
import pytest
import pandas as pd
from src.reconciliation import cross_system_matcher, quantity_checker, timestamp_validator, exception_report

@pytest.fixture
def sample_data():
    wms_orders = pd.DataFrame({
        "order_id": ["o1", "o2", "o3"],
        "order_status": ["delivered", "delivered", "shipped"],
        "order_purchase_timestamp": ["2023-01-01 10:00:00", "2023-01-02 10:00:00", "2023-01-03 10:00:00"],
        "order_approved_at": ["2023-01-01 11:00:00", "2023-01-02 11:00:00", "2023-01-03 11:00:00"],
        "order_delivered_carrier_date": ["2023-01-05 10:00:00", "2023-01-06 10:00:00", None],
        "order_delivered_customer_date": ["2023-01-04 10:00:00", "2023-01-08 10:00:00", None] # o1 has delivery before carrier
    })
    wms_order_items = pd.DataFrame({
        "order_id": ["o1", "o1", "o2"], 
        "product_id": ["p1", "p2", "p3"],
        "price": [10.0, 20.0, 30.0]
    })
    tms_shipments = pd.DataFrame({
        "order_id": ["o1", "o4"],
        "item_count": [2, 1],
        "carrier_handoff_date": ["2023-01-05 10:00:00", "2023-01-06 10:00:00"]
    })
    erp_items = pd.DataFrame({
        "product_id": ["p1", "p2"] # p3 is missing
    })
    return wms_orders, tms_shipments, erp_items, wms_order_items

def test_missing_tms_shipment(sample_data):
    wms_orders, tms_shipments, erp_items, wms_order_items = sample_data
    df = cross_system_matcher.match_orders_across_systems(wms_orders, tms_shipments, erp_items, wms_order_items)
    missing_tms = df[df["exception_type"] == "MISSING_TMS_SHIPMENT"]
    assert len(missing_tms) > 0
    assert "o2" in missing_tms["order_id"].values

def test_orphan_tms_shipment(sample_data):
    wms_orders, tms_shipments, erp_items, wms_order_items = sample_data
    df = cross_system_matcher.match_orders_across_systems(wms_orders, tms_shipments, erp_items, wms_order_items)
    orphan_tms = df[df["exception_type"] == "ORPHAN_TMS_SHIPMENT"]
    assert len(orphan_tms) > 0
    assert "o4" in orphan_tms["order_id"].values

def test_missing_erp_product(sample_data):
    wms_orders, tms_shipments, erp_items, wms_order_items = sample_data
    df = cross_system_matcher.match_orders_across_systems(wms_orders, tms_shipments, erp_items, wms_order_items)
    missing_erp = df[df["exception_type"] == "MISSING_ERP_PRODUCT"]
    assert len(missing_erp) > 0
    assert "p3" in missing_erp["product_id"].values

def test_quantity_mismatch():
    wms_items = pd.DataFrame({"order_id": ["o1", "o1", "o1"]}) # 3 items
    tms_shipments = pd.DataFrame({"order_id": ["o1"], "item_count": [2]}) # 2 items
    df = quantity_checker.check_quantity_mismatches(wms_items, tms_shipments)
    assert len(df) > 0
    assert df["order_id"].iloc[0] == "o1"
    assert df["exception_type"].iloc[0] == "QUANTITY_MISMATCH"

def test_timestamp_sequence(sample_data):
    wms_orders, tms_shipments, _, _ = sample_data
    df = timestamp_validator.validate_timestamps(wms_orders, tms_shipments)
    assert len(df) > 0
    assert "o1" in df["order_id"].values
    assert "TIMESTAMP_SEQUENCE_VIOLATION" in df["exception_type"].values

def test_exception_report_consolidation(sample_data):
    wms_orders, tms_shipments, erp_items, wms_order_items = sample_data
    cross_df = cross_system_matcher.match_orders_across_systems(wms_orders, tms_shipments, erp_items, wms_order_items)
    qty_df = quantity_checker.check_quantity_mismatches(wms_order_items, tms_shipments)
    ts_df = timestamp_validator.validate_timestamps(wms_orders, tms_shipments)
    price_df = pd.DataFrame()
    
    report = exception_report.generate_exception_report(cross_df, qty_df, price_df, ts_df)
    assert len(report) > 0
    assert "exception_id" in report.columns
    assert "detected_at" in report.columns
