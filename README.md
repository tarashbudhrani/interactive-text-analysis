# Retail inventory monitor (Square + Streamlit + Slack)

Plug-and-play pipeline for small retailers using **Square** as the POS source of truth: pull catalogue, inventory counts, and recent orders; compute **sales velocity**, **days of cover**, and **reorder signals** from **your own Square data**; explore everything in **Streamlit**; optionally notify **Slack**.

## What runs by default

| Layer | Purpose |
|--------|--------|
| Square API | Catalogue, inventory on hand, order lines (90 days) |
| dbt | `mart_stock_position`, `mart_reorder_signal`, freshness metadata |
| Slack | Message **1**: low-stock / reorder rows · Message **2**: 7d/30d sales pulse + top movers (toggle off with `SLACK_ENABLE_SALES_METRICS=0`) |

CSV uploads through Square’s dashboard stay inside Square; if you maintain a side spreadsheet, set `MERGE_INVENTORY_CSV` to merge SKU quantities into `raw_square.inventory_counts` after each Square sync (see `ingest/merge_inventory_csv.py`).

## Quickstart

```bash
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
# add SQUARE_ACCESS_TOKEN (and SLACK_WEBHOOK_URL if you use Slack)

python run_pipeline.py
streamlit run streamlit_app/app.py
```

## GitHub Actions (every 24 hours)

Workflow: [`.github/workflows/daily_inventory_pipeline.yml`](.github/workflows/daily_inventory_pipeline.yml)

**Repository secrets**

- `SQUARE_ACCESS_TOKEN` — required  
- `SLACK_WEBHOOK_URL` — optional  

Optional **Variables** (Settings → Secrets and variables → Actions → Variables): e.g. `SQUARE_ENVIRONMENT=production`.

Each successful run uploads `data/supply_chain.duckdb` as an artifact (14-day retention) so you can wire a hosted Streamlit/other consumer without checking the DB into git.

### Skipping work when POS data did not change

For self-hosted runners or advanced setups where `data/supply_chain.duckdb` and `data/.square_pipeline_fp` persist between runs:

```bash
export SKIP_SQUARE_RELOAD_IF_UNCHANGED=1
export SKIP_DBT_IF_RAW_UNCHANGED=1
python run_pipeline.py
```

Fingerprints ignore `loaded_at` timestamps so incidental ingestion noise does not invalidate the comparison.

## Slack rollout (“one by one”)

1. **Reorder alerts** — always sent first when `mart_reorder_signal` has rows (or when `SLACK_NOTIFY_WHEN_CLEAR=1` for an “all clear” ping).  
2. **Sales pulse** — second webhook message with 7d/30d units/revenue/order counts and top movers; disable with `SLACK_ENABLE_SALES_METRICS=0`.

Global kill-switch: `DISABLE_SLACK_ALERTS=1`.

## Project layout

```
├── ingest/
│   ├── square_ingest.py       # Square → DuckDB raw_* layers
│   ├── merge_inventory_csv.py # Optional SKU CSV overlay
│   └── slack_alerts.py        # Webhook notifications
├── models/                    # dbt staging / marts
├── run_pipeline.py            # Orchestrator
├── streamlit_app/             # Velocity, inventory, reorder
└── .github/workflows/         # Daily schedule + artifact upload
```

## Phase 2 (off by default)

Extended Census + BLS ingestion and cost/pressure models stay in the repo but are **disabled** in `dbt_project.yml`. Turn them on only if you intentionally run:

```bash
python run_pipeline.py --with-extended-macro-ingest
```
