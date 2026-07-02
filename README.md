# ApexFinance: Personal Finance Web App

A comprehensive Personal Finance Dashboard built using **FastAPI** (Python) for the backend logic and data services, **SQLite** for persistence, and **HTML/CSS/Vanilla JS** (utilizing **Chart.js** and **FontAwesome**) for a premium glassmorphic dashboard interface.

---

## Features

1. **KPI Scoreboard**: Real-time display of Net Worth, Normalized Monthly Income, Consolidated Obligations, and Unified Monthly Cash Flow.
2. **Interactive Cash Flow Allocation**: Doughnut chart visualizing the distribution of income across Fixed, Discretionary, Debt Payments, Savings, and remaining Cash Flow.
3. **Debt Acceleration Simulator**: Interactive Snowball payoff tracker demonstrating the interest and timeline savings when applying extra principal payments (lowest balance first).
4. **Compound Growth Forecaster**: Reactive slider-based line chart showing future wealth accumulation of savings portfolios over time.
5. **CSV statement ETL wizard**: Ingestion tool allowing column-mapping selection, duplicate detection via deterministic SHA-256 hashes, and automatic categorization.
6. **Unified CRUD**: Complete forms to add or remove income streams, debts, fixed expenses, discretionary items, and savings goals dynamically.

---

## Installation & Setup

1. **Activate the Virtual Environment**:
   ```bash
   source venv/bin/activate
   ```

2. **Install Dependencies**:
   ```bash
   pip install -r requirements.txt
   ```

3. **Start the FastAPI Web Server**:
   ```bash
   uvicorn main:app --host 127.0.0.1 --port 8000 --reload
   ```

4. **Open the Application**:
   Go to **[http://127.0.0.1:8000](http://127.0.0.1:8000)** in your web browser.

---

## Technical Architecture

* **Database Persistence (`schema.sql` & SQLite)**: Auto-seeding database schema executing cascading rules, integrity constraints, and database indexing on hashes and categories.
* **Math Services (`finance_service.py`)**: Normalized frequency calculations, double-counting mitigation for linked fixed-assets/debts, and compound interest calculations.
* **ETL Pipeline (`etl_pipeline.py`)**: Ingestion service handling header-to-column mappings, date format parsing, clean transaction currency conversion, and SHA-256 deduplication.
