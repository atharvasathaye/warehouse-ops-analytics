"""
Tests for KPI computation modules.
"""
import pytest
import pandas as pd
from src.kpis import inventory_metrics, order_metrics, delivery_metrics, productivity_metrics

def test_abc_classification():
    order_items = pd.DataFrame({
        "product_id": ["p1", "p1", "p2", "p3"],
        "price": [100.0, 100.0, 50.0, 10.0]
    })
    df = inventory_metrics.classify_abc(order_items)
    assert "abc_class" in df.columns
    p1_class = df[df["product_id"] == "p1"]["abc_class"].iloc[0]
    assert p1_class == "A"

def test_inventory_turns():
    orders = pd.DataFrame({
        "order_id": ["o1"],
        "order_status": ["delivered"],
        "order_purchase_timestamp": ["2023-01-01 10:00:00"]
    })
    order_items = pd.DataFrame({
        "order_id": ["o1"],
        "product_id": ["p1"],
        "price": [100.0]
    })
    df = inventory_metrics.calculate_inventory_turns(order_items, orders)
    assert "turns" in df.columns
    assert len(df) > 0

def test_cycle_time():
    orders = pd.DataFrame({
        "order_id": ["o1"],
        "order_status": ["delivered"],
        "order_purchase_timestamp": ["2023-01-01 10:00:00"],
        "order_delivered_customer_date": ["2023-01-05 10:00:00"]
    })
    df = order_metrics.calculate_order_cycle_time(orders)
    assert df.loc[df["order_id"] == "o1", "cycle_time_days"].iloc[0] == 4.0
    assert df.attrs["cycle_time_stats"]["mean"] == 4.0

def test_fill_rate():
    orders = pd.DataFrame({
        "order_id": ["o1"],
        "order_status": ["delivered"]
    })
    order_items = pd.DataFrame({
        "order_id": ["o1"],
        "product_id": ["p1"]
    })
    df = order_metrics.calculate_fill_rate(order_items, orders)
    assert "fill_rate" in df.columns
    assert df.attrs["overall_fill_rate"] == 1.0

def test_on_time_delivery():
    orders = pd.DataFrame({
        "order_id": ["o1", "o2"],
        "order_status": ["delivered", "delivered"],
        "order_delivered_customer_date": ["2023-01-05", "2023-01-10"],
        "order_estimated_delivery_date": ["2023-01-06", "2023-01-09"]
    })
    df = delivery_metrics.calculate_on_time_delivery(orders)
    assert "on_time" in df.columns
    assert df.attrs["otd_percentage"] == 50.0

def test_dock_to_ship():
    orders = pd.DataFrame({
        "order_id": ["o1"],
        "order_status": ["delivered"],
        "order_approved_at": ["2023-01-01 10:00:00"],
        "order_delivered_carrier_date": ["2023-01-02 10:00:00"]
    })
    df = delivery_metrics.calculate_dock_to_ship(orders)
    assert df.loc[df["order_id"] == "o1", "dock_to_ship_hours"].iloc[0] == 24.0

def test_picks_per_hour():
    orders = pd.DataFrame({
        "order_id": ["o1"],
        "order_purchase_timestamp": ["2023-01-01 10:00:00"]
    })
    order_items = pd.DataFrame({
        "order_id": ["o1"],
        "product_id": ["p1"]
    })
    df = productivity_metrics.calculate_picks_per_hour(order_items, orders, seconds_per_pick=60)
    assert len(df) == 1
    assert df["picks_per_hour"].iloc[0] == 60.0
