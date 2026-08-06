# Warehouse Operations Analytics

Data engineering and analytics pipeline designed to reconcile warehouse operations data across disparate systems (WMS, ERP, TMS). The pipeline identifies cross-system discrepancies, computes operational KPIs, and exports dimensional models optimized for Power BI reporting.

## Overview

Distribution hubs frequently utilize disparate software platforms. Data inconsistencies across Warehouse Management Systems (WMS), Enterprise Resource Planning (ERP), and Transportation Management Systems (TMS) lead to operational inefficiencies.

This project simulates multi-system data drift using the [Olist E-commerce Dataset](https://www.kaggle.com/datasets/olistbr/brazilian-ecommerce). The dataset is partitioned into three system feeds with controlled data drift, followed by automated reconciliation procedures to detect anomalies and evaluate core metrics.

### Core Features

- **Multi-System Ingestion**: Ingests CSV batch data (WMS), REST API endpoints (ERP), and JSON payloads (TMS).
- **Data Reconciliation**: Detects orphaned records, quantity mismatches, price anomalies, and timeline sequence violations.
- **KPI Engine**: Computes inventory turnover, ABC classification, fill rates, order cycle times, and dock-to-ship metrics.
- **Dimensional Modeling**: Exports cleaned `fact` and `dim` tables in a Star Schema format for Power BI consumption.

## Dashboard Preview

Analytical outputs are aggregated and visualized in a Power BI dashboard tracking operational KPIs and exceptions.

- **[View the Dashboard Export (PDF)](dashboards/Warehouse_Operations_Dashboard.pdf)**

*(Note: To view the interactive model, open `dashboards/Warehouse_Operations_Dashboard.pbix` with Power BI Desktop).*

## Architecture

Data flows through four primary pipeline stages:

1. **Preparation and Partitioning**: Raw data is split into WMS, TMS, and ERP feeds. Controlled drift (missing records, timestamp jitter) is introduced.
2. **Ingestion**: The pipeline loads data from local storage and the ERP FastAPI service.
3. **Reconciliation and Metrics**: A Pandas analytics engine processes the feeds, generates exception reports, and calculates operational metrics.
4. **Export**: Processed output is structured into a dimensional model and written to `data/powerbi/`.

## Getting Started

### Prerequisites

- Python 3.10+

### Installation

Clone the repository and set up the environment:

```bash
git clone https://github.com/atharvasathaye/warehouse-ops-analytics.git
cd warehouse-ops-analytics

python -m venv .venv
source .venv/bin/activate  # On Windows: .venv\Scripts\activate

pip install -r requirements.txt
```

## Execution Workflow

### 1. Data Preparation

Download the Olist dataset from [Kaggle](https://www.kaggle.com/datasets/olistbr/brazilian-ecommerce) and place the CSV files in `data/raw/`.

Execute the partition script to generate system feeds and inject controlled drift:

```bash
python scripts/01_split_to_feeds.py
```

### 2. ERP Service Execution

The ERP item master is exposed via a FastAPI application. Start the server in a separate process:

```bash
uvicorn erp_api.main:app --reload
```

### 3. Pipeline Execution

Run the ingestion, reconciliation, and KPI calculation pipeline:

```bash
python scripts/02_run_pipeline.py
```

*(Use the `--skip-api` flag to read ERP data directly from disk).*

### 4. Power BI Export

Structure processed outputs into dimensional schema tables:

```bash
python scripts/03_export_powerbi.py
```

Output CSV files and `data_dictionary.csv` will be generated in `data/powerbi/`.

## Configuration

Pipeline settings (tolerances, drift parameters, API endpoints) are configured in `config/settings.yaml`. Environment variables can be defined using a `.env` file based on `.env.example`.

## License

MIT License. See [LICENSE](LICENSE) for details.

## Author

Atharva Sathaye
