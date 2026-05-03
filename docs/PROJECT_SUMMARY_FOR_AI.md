# Project summary (handoff for another AI)

Use this document to onboard another assistant or reviewer to **what we are building** and **what exists in the repo today**.

---

## Product: Retail inventory monitor

**Audience:** Small retailers using **Square** as POS.

**Scope:** **Internal Square inventory and local sales data only** — catalogue, stock counts, order lines, velocity, days of cover, and reorder recommendations. No Federal Reserve / macro-economic feeds.

**Core operational outputs:**

1. **Sales velocity** — how fast each SKU/variation sells (from Square orders).
2. **Current inventory** — on-hand quantities from Square Inventory API (joined to catalogue).
3. **Reorder signal** — approximate **days until stockout** (inventory ÷ 30-day velocity), urgency tiers, and suggested reorder quantities.

**Delivery surfaces:**

- **Streamlit** dashboards (velocity, inventory, reorder).
- **Slack** via Incoming Webhook (reorder alerts + optional second message with sales pulse).
- **GitHub Actions** scheduled pipeline + DuckDB artifact upload.

---

## Architecture

| Layer | Technology | Role |
|--------|------------|------|
| Raw data | DuckDB (`data/supply_chain.duckdb`) | `raw_square.*` |
| Ingest | Python (`ingest/`) | Square catalogue, inventory, orders (~90d); optional CSV merge |
| Transform | dbt Core + dbt-duckdb | Staging → intermediate velocity → `mart_stock_position` → `mart_reorder_signal`; freshness metadata |
| UI | Streamlit (`streamlit_app/`) | Reads marts/views from DuckDB |
| Notifications | `requests` → Slack webhook | After successful `dbt build` |

---

## What is implemented

### Pipeline orchestrator (`run_pipeline.py`)

- **Square** ingest with **content fingerprint** (`square_payload_fingerprint` in `ingest/square_ingest.py`) that **excludes `loaded_at`** so hashes reflect real POS data, not ingestion time.
- Fingerprint file: `data/.square_pipeline_fp` (under `data/`, gitignored).
- Optional incremental behavior:
  - `SKIP_SQUARE_RELOAD_IF_UNCHANGED=1`
  - `SKIP_DBT_IF_RAW_UNCHANGED=1`
- Optional **`MERGE_INVENTORY_CSV`**: merges SKU-based quantity adjustments via `ingest/merge_inventory_csv.py` after Square writes.
- **Census + BLS “extended macro” ingest** is **off by default**; enable with `python run_pipeline.py --with-extended-macro-ingest` (feeds optional disabled cost/pressure models, not FRED).

### Slack (`ingest/slack_alerts.py`)

- **`SLACK_WEBHOOK_URL`** required to send.
- **First message:** low-stock / reorder rows from `mart_reorder_signal`.
- **Second message:** 7d/30d units, revenue, order count, top movers—disable with **`SLACK_ENABLE_SALES_METRICS=0`**.
- **`DISABLE_SLACK_ALERTS=1`** disables all Slack sends.
- **`SLACK_NOTIFY_WHEN_CLEAR=1`** sends reorder thread even when there are zero reorder rows (“all clear” style).

### dbt (`models/`)

**Active path:**

- `stg_square__orders`, `stg_square__inventory` → `int_daily_sales_velocity` → `mart_stock_position` → `mart_reorder_signal`
- `mart_pipeline_metadata` — freshness over **Square** sources only.

**Removed from the project:** FRED / RETAILIRSA, `stg_fred__inventory_ratio`, `mart_industry_benchmark`, and related staging.

**Disabled by default** (`dbt_project.yml`, `+enabled: false`):

- `mart_cost_pressure` (Census + BLS)
- `stg_bls__ppi`, `stg_census__retail_sales`

### Streamlit (`streamlit_app/`)

- **`app.py`** — home KPIs, pipeline freshness table, navigation, sample velocity chart.
- **`pages/1_Sales_velocity.py`**, **`2_Current_inventory.py`**, **`3_Reorder_signals.py`**.

### CI (`.github/workflows/daily_inventory_pipeline.yml`)

- Daily cron plus **`workflow_dispatch`**.
- Secrets: **`SQUARE_ACCESS_TOKEN`**, optional **`SLACK_WEBHOOK_URL`**.
- Uploads **`data/supply_chain.duckdb`** as a workflow artifact (short retention).

---

## Configuration reference

See **`.env.example`**. Common variables:

| Variable | Purpose |
|----------|---------|
| `SQUARE_ACCESS_TOKEN` | Square API token |
| `SQUARE_ENVIRONMENT` | `sandbox` vs production-style token pairing |
| `SLACK_WEBHOOK_URL` | Slack Incoming Webhook |
| `SLACK_ENABLE_SALES_METRICS` | `0` = reorder-only Slack |
| `DISABLE_SLACK_ALERTS` | `1` = no Slack |
| `MERGE_INVENTORY_CSV` | Path to optional SKU quantity CSV |
| `SKIP_SQUARE_RELOAD_IF_UNCHANGED` / `SKIP_DBT_IF_RAW_UNCHANGED` | Incremental skips when DuckDB + fingerprint persist |

---

## Repository layout (short)

```
ingest/           # Square, CSV merge, Slack
models/           # dbt SQL
run_pipeline.py   # Single entrypoint
streamlit_app/    # Dashboard
profiles.yml, dbt_project.yml
docs/             # This file
.github/workflows/
```

---

## Known limitations / ops notes

- **Square sandbox** may have no catalogue or orders until items and transactions exist; pipeline can succeed with **zero rows** in `raw_square.*`, leaving Streamlit sparse.
- **GitHub Actions** runners typically do **not** persist `data/` between jobs unless you restore/cache artifacts or external storage.

---

## Commands

```bash
pip install -r requirements.txt
cp .env.example .env   # then fill secrets

python run_pipeline.py
streamlit run streamlit_app/app.py

# Optional extended macro ingest (Census + BLS for disabled cost model only):
python run_pipeline.py --with-extended-macro-ingest
```

---

*Last aligned with Square-only scope (no FRED / RETAILIRSA).*
