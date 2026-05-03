#!/usr/bin/env python3
"""
Generate synthetic Square-style order lines into raw_square.orders for local testing.

Uses ALDI-themed SKUs. Prefers matching rows from raw_square.catalogue (variation_id + price);
if none exist, falls back to demo variation_ids so inserts still succeed.

Examples:
  python scripts/generate_sales.py              # one batch (5–10 rows), then exit
  python scripts/generate_sales.py --loop       # every 5 hours by default
  python scripts/generate_sales.py --loop --interval-hours 2
"""
from __future__ import annotations

import argparse
import random
import sys
import time
import uuid
from datetime import datetime, timezone
from pathlib import Path

import duckdb

_ROOT = Path(__file__).resolve().parents[1]
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

from ingest.square_ingest import SIMULATED_ORDER_VARIATION_PREFIX

# ---------------------------------------------------------------------------
# ALDI SKU catalog (reference list — align catalogue rows in DuckDB when possible)
# ---------------------------------------------------------------------------
ALDI_PRODUCTS: list[dict[str, str | float]] = [
    {"sku": "ALDI-MLK-01", "default_price": 3.49},
    {"sku": "ALDI-EGG-12", "default_price": 4.29},
    {"sku": "ALDI-BRD-WH", "default_price": 1.99},
    {"sku": "ALDI-CHS-SH", "default_price": 3.99},
    {"sku": "ALDI-APL-6P", "default_price": 4.49},
    {"sku": "ALDI-BAN-LB", "default_price": 0.59},
    {"sku": "ALDI-OAT-QT", "default_price": 2.99},
    {"sku": "ALDI-YOG-4P", "default_price": 2.49},
    {"sku": "ALDI-HAM-SL", "default_price": 5.99},
    {"sku": "ALDI-JCE-64", "default_price": 3.79},
]


def _project_root() -> Path:
    return Path(__file__).resolve().parents[1]


def _db_path(cli_path: str | None) -> Path:
    if cli_path:
        return Path(cli_path).expanduser()
    return _project_root() / "data" / "supply_chain.duckdb"


def _resolve_products(con: duckdb.DuckDBPyConnection) -> list[tuple[str, str, float]]:
    """
    Returns list of (variation_id, sku, unit_price).
    """
    resolved: list[tuple[str, str, float]] = []
    skus = [str(p["sku"]) for p in ALDI_PRODUCTS]
    price_map = {str(p["sku"]): float(p["default_price"]) for p in ALDI_PRODUCTS}

    rows: list = []
    try:
        placeholders = ",".join(["?" for _ in skus])
        rows = con.execute(
            f"""
            SELECT variation_id, sku, COALESCE(price_money, 0)::DOUBLE AS price_money
            FROM raw_square.catalogue
            WHERE sku IN ({placeholders})
            """,
            skus,
        ).fetchall()
    except Exception:
        # Missing raw_square.catalogue or empty — use fallbacks below
        rows = []

    seen: set[str] = set()
    for variation_id, sku, price in rows:
        if not variation_id or not sku:
            continue
        unit = float(price) if float(price) > 0 else price_map.get(sku, 0.0)
        if unit <= 0:
            unit = price_map.get(sku, 1.0)
        resolved.append((str(variation_id), str(sku), unit))
        seen.add(sku)

    for p in ALDI_PRODUCTS:
        sku = str(p["sku"])
        if sku in seen:
            continue
        demo_vid = f"{SIMULATED_ORDER_VARIATION_PREFIX}{sku}"
        unit = float(p["default_price"])
        resolved.append((demo_vid, sku, unit))

    if not resolved:
        raise RuntimeError("No products could be resolved for synthetic orders.")
    if len(resolved) > len(seen) and not seen:
        print(
            "  [generate_sales] No ALDI SKUs in raw_square.catalogue — using local demo variation_ids. "
            "Add matching catalogue rows in Square for real IDs.",
            file=sys.stderr,
        )
    return resolved


def _insert_batch(con: duckdb.DuckDBPyConnection, products: list[tuple[str, str, float]], n: int) -> int:
    now = datetime.now(timezone.utc)
    inserted = 0
    for _ in range(n):
        vid, sku, unit_price = random.choice(products)
        qty = random.randint(1, 5)
        # small price jitter (e.g. promos)
        line_total = round(qty * unit_price * random.uniform(0.95, 1.05), 2)
        order_id = str(uuid.uuid4())
        con.execute(
            """
            INSERT INTO raw_square.orders
                (order_id, variation_id, quantity_sold, total_money, created_at, loaded_at)
            VALUES (?, ?, ?, ?, ?, ?)
            """,
            [order_id, vid, qty, line_total, now, now],
        )
        inserted += 1
    return inserted


def _orders_table_needs_rebuild(con: duckdb.DuckDBPyConnection) -> bool:
    """True if table is missing or has a legacy/broken schema (e.g. INTEGER ids from an empty seed)."""
    try:
        rows = con.execute("DESCRIBE raw_square.orders").fetchall()
    except Exception:
        return True
    if not rows:
        return True
    types = {r[0].lower(): str(r[1]).upper() for r in rows}
    oi = types.get("order_id", "")
    vi = types.get("variation_id", "")
    # Square uses string ids; timestamps must not be stored as INTEGER
    if "INT" in oi and "VAR" not in oi:
        return True
    if "INT" in vi and "VAR" not in vi:
        return True
    if "INT" in types.get("created_at", ""):
        return True
    if "INT" in types.get("total_money", "") and "DOUBLE" not in types.get("total_money", ""):
        return True
    return False


def _ensure_orders_table(con: duckdb.DuckDBPyConnection) -> None:
    con.execute("CREATE SCHEMA IF NOT EXISTS raw_square")
    if _orders_table_needs_rebuild(con):
        con.execute("DROP TABLE IF EXISTS raw_square.orders")
        print(
            "  [generate_sales] Recreated raw_square.orders with VARCHAR/TIMESTAMP columns "
            "(legacy INTEGER schema detected). Re-run pipeline Square ingest if you need API orders.",
            file=sys.stderr,
        )
    con.execute(
        """
        CREATE TABLE IF NOT EXISTS raw_square.orders (
            order_id VARCHAR,
            variation_id VARCHAR,
            quantity_sold INTEGER,
            total_money DOUBLE,
            created_at TIMESTAMP,
            loaded_at TIMESTAMP
        )
        """
    )


def run_once(db_path: Path, count: int | None = None) -> int:
    if not db_path.parent.is_dir():
        db_path.parent.mkdir(parents=True, exist_ok=True)

    n = count if count is not None else random.randint(5, 10)
    con = duckdb.connect(str(db_path))
    try:
        _ensure_orders_table(con)
        products = _resolve_products(con)
        inserted = _insert_batch(con, products, n)
    finally:
        con.close()

    ts = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC")
    print(f"[{ts}] Inserted {inserted} synthetic order line(s) into {db_path}")
    return inserted


def main() -> None:
    parser = argparse.ArgumentParser(description="Insert synthetic ALDI order lines into raw_square.orders")
    parser.add_argument(
        "--db",
        dest="db_path",
        default=None,
        help="Path to DuckDB file (default: <repo>/data/supply_chain.duckdb)",
    )
    parser.add_argument(
        "--count",
        type=int,
        default=None,
        help="Exact number of rows to insert (default: random 5–10)",
    )
    parser.add_argument(
        "--loop",
        action="store_true",
        help="Run repeatedly every --interval-hours instead of once",
    )
    parser.add_argument(
        "--interval-hours",
        type=float,
        default=5.0,
        help="Sleep interval when --loop is set (default: 5)",
    )
    args = parser.parse_args()
    db_path = _db_path(args.db_path)

    if not args.loop:
        run_once(db_path, args.count)
        return

    print(
        f"Loop mode: inserting every {args.interval_hours} hour(s). Ctrl+C to stop.",
        file=sys.stderr,
    )
    while True:
        try:
            run_once(db_path, args.count)
        except KeyboardInterrupt:
            print("\nStopped.", file=sys.stderr)
            raise SystemExit(0)
        except Exception as exc:
            print(f"Error: {exc}", file=sys.stderr)
        time.sleep(max(args.interval_hours, 0.01) * 3600.0)


if __name__ == "__main__":
    main()
