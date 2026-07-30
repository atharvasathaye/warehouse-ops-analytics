# Warehouse Operations Analytics

A data engineering and analytics pipeline that reconciles warehouse operations data across multiple systems (WMS, ERP, TMS). It identifies cross-system discrepancies, computes operational KPIs, and exports dimensional models ready for Power BI.

## Overview

Modern distribution hubs rarely run on a single system. Data drift between the Warehouse Management System (WMS), Enterprise Resource Planning (ERP), and Transportation Management System (TMS) leads to hidden operational inefficiencies. 

This project simulates that environment by taking the [Olist E-commerce Dataset](https://www.kaggle.com/datasets/olistbr/brazilian-ecommerce), splitting it into three distinct system feeds with injected data drift, and then running a reconciliation pipeline to detect anomalies and calculate KPIs.

### Core Features

- **Multi-System Ingestion**: Consumes CSV batch data (WMS), REST API endpoints (ERP), and JSON payloads (TMS).
- **Data Reconciliation**: Identifies orphaned records, quantity mismatches, price anomalies, and timeline violations between systems.
- **KPI Engine**: Calculates inventory turns, ABC classification, fill rates, order cycle times, and dock-to-ship metrics.
- **Dimensional Modeling**: Outputs clean `fact` and `dim` tables in a Star Schema format for direct Power BI consumption.

## Dashboard Preview
The analytical outputs are visualized in a Power BI dashboard tracking exceptions and operational KPIs. 

📄 **[View the Dashboard Export (PDF)](dashboards/Warehouse_Operations_Dashboard.pdf)**

*(Note: To view the interactive dashboard, download `dashboards/Warehouse_Operations_Dashboard.pbix` and open it with Power BI Desktop).*

## Architecture

Data flows through four primary phases:

1. **Prep/Split**: Raw data is split into WMS, TMS, and ERP datasets. Controlled "drift" (missing records, timestamp jitter) is injected.
2. **Ingestion**: The pipeline loads data from local storage and the local ERP FastAPI service.
3. **Reconciliation & KPIs**: Pandas-based analytical engine processes the feeds to generate exception reports and compute metrics.
4. **Export**: Results are formatted into a dimensional model and saved to `data/powerbi/`.

## Installation

Requires Python 3.10+.

```bash
# Clone repository
git clone https://github.com/yourusername/warehouse-ops-analytics.git
cd warehouse-ops-analytics

# Create virtual environment
python -m venv .venv
source .venv/bin/activate  # On Windows use: .venv\Scripts\activate

# Install dependencies
pip install -r requirements.txt
```

## Setup & Execution

### 1. Data Preparation
Download the Olist dataset from [Kaggle](https://www.kaggle.com/datasets/olistbr/brazilian-ecommerce) and extract the CSV files into `data/raw/`.

Run the split script to generate the system feeds and inject drift:
```bash
python scripts/01_split_to_feeds.py
```

### 2. Start the ERP Service
The ERP item master is served via a FastAPI application. Start it in a separate terminal:
```bash
uvicorn erp_api.main:app --reload
```

### 3. Run the Pipeline
Execute the main pipeline to ingest data, run reconciliation, and compute KPIs:
```bash
python scripts/02_run_pipeline.py
```
*(Use `--skip-api` to bypass the FastAPI service and read ERP data directly from disk).*

### 4. Export for Power BI
Format the processed outputs into a dimensional schema:
```bash
python scripts/03_export_powerbi.py
```
The final CSVs will be available in `data/powerbi/`, alongside a `data_dictionary.csv`.

## Configuration

Pipeline parameters (tolerances, drift percentages, API URLs) are managed in `config/settings.yaml`. 
You can override environment-specific variables (like API endpoints) using a `.env` file (see `.env.example`).

## License

MIT License. See [LICENSE](LICENSE) for details.
