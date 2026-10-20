"""
Tests for the ERP API.
"""
import pytest
from fastapi.testclient import TestClient
import pandas as pd
from pathlib import Path
import os

from erp_api.main import app
from erp_api.data_loader import store

@pytest.fixture(autouse=True)
def setup_erp_store(tmp_path):
    """Fixture to create sample CSVs for the ERP API and load them into the store."""
    data_dir = tmp_path / "data"
    data_dir.mkdir()
    
    products_df = pd.DataFrame({
        "product_id": ["p1", "p2", "p3", "p4", "p5"],
        "product_category_name": ["cat1", "cat2", "cat1", "cat3", "cat2"],
        "product_weight_g": [100, 200, 150, 300, 250]
    })
    products_df.to_csv(data_dir / "erp_products.csv", index=False)
    
    cats_df = pd.DataFrame({
        "product_category_name": ["cat1", "cat2", "cat3"],
        "product_category_name_english": ["cat1_en", "cat2_en", "cat3_en"]
    })
    cats_df.to_csv(data_dir / "erp_categories.csv", index=False)
    
    store.load_data(data_dir)
    yield data_dir

@pytest.fixture
def client():
    return TestClient(app)

def test_health_endpoint(client):
    response = client.get("/health")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "ok"
    assert "timestamp" in data

def test_list_items(client):
    response = client.get("/items/")
    assert response.status_code == 200
    data = response.json()
    assert "items" in data
    assert len(data["items"]) > 0

def test_list_items_pagination(client):
    response = client.get("/items/?skip=1&limit=2")
    assert response.status_code == 200
    data = response.json()
    assert len(data["items"]) <= 2

def test_get_item_by_id(client):
    response = client.get("/items/p1")
    assert response.status_code == 200
    data = response.json()
    assert data["product_id"] == "p1"

def test_get_item_not_found(client):
    response = client.get("/items/nonexistent")
    assert response.status_code == 404

def test_list_categories(client):
    response = client.get("/items/categories")
    assert response.status_code == 200
    data = response.json()
    assert "categories" in data
    assert "cat1" in data["categories"]

def test_filter_by_category(client):
    response = client.get("/items/?category=cat1")
    assert response.status_code == 200
    data = response.json()
    assert len(data["items"]) > 0
    for item in data["items"]:
        assert item["product_category"] == "cat1"
