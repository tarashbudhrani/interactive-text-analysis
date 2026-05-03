import hashlib
import os
from pathlib import Path

import duckdb
import pandas as pd
from datetime import datetime, timedelta, timezone
from dotenv import load_dotenv

load_dotenv()

# Variation ids from scripts/generate_sales.py when no Square catalogue match — used for summaries + skip logic
SIMULATED_ORDER_VARIATION_PREFIX = "local-demo-"


def square_payload_fingerprint(
    cat_df: pd.DataFrame, inv_df: pd.DataFrame, ord_df: pd.DataFrame
) -> str:
    """
    Stable fingerprint of Square catalogue + inventory + orders payloads.
    Ignores loaded_at so ingestion timestamps do not force redundant pipeline runs.
    """
    def _blob(frame: pd.DataFrame, cols: list[str]) -> bytes:
        if frame.empty:
            return b"empty"
        present = [c for c in cols if c in frame.columns]
        sub = frame[present].copy().fillna("")
        for c in sub.columns:
            sub[c] = sub[c].astype(str)
        sub = sub.sort_values(by=list(sub.columns)).reset_index(drop=True)
        return pd.util.hash_pandas_object(sub, index=False).values.tobytes()

    h = hashlib.sha256()
    h.update(
        _blob(
            cat_df,
            ["item_id", "variation_id", "variation_name", "sku", "price_money", "item_name"],
        )
    )
    h.update(
        _blob(
            inv_df,
            ["variation_id", "location_id", "quantity", "calculated_at"],
        )
    )
    h.update(
        _blob(
            ord_df,
            ["order_id", "variation_id", "quantity_sold", "total_money", "created_at"],
        )
    )
    return h.hexdigest()


def orders_table_digest(db_path: str) -> str:
    """
    Hash of current raw_square.orders content (count + max timestamps).
    Mixed with the API fingerprint so runs after scripts/generate_sales.py invalidate incremental skips
    and dbt still runs when the sandbox returns 0 orders but the DB has simulator rows.
    """
    if not Path(db_path).is_file():
        return "no_database_file"
    con = duckdb.connect(db_path, read_only=True)
    try:
        row = con.execute(
            """
            select count(*)::bigint,
                   coalesce(max(loaded_at)::varchar, ''),
                   coalesce(max(created_at)::varchar, '')
            from raw_square.orders
            """
        ).fetchone()
    except Exception:
        return "no_orders_table"
    finally:
        con.close()
    if not row:
        return "empty_orders_table"
    return hashlib.sha256("|".join(str(x) for x in row).encode()).hexdigest()


def print_raw_orders_ingest_summary(db_path: str, api_line_count: int) -> None:
    """Log how many order lines are in DuckDB after ingest (API batch + any persisted local/simulator rows)."""
    try:
        con = duckdb.connect(db_path, read_only=True)
        try:
            total = con.execute("select count(*) from raw_square.orders").fetchone()[0]
            sim_pat = SIMULATED_ORDER_VARIATION_PREFIX + "%"
            sim = con.execute(
                    """
                    select count(*) from raw_square.orders
                    where cast(variation_id as varchar) like ?
                    """,
                    [sim_pat],
                ).fetchone()[0]
        finally:
            con.close()
    except Exception as exc:
        print(f"  [Square] raw_square.orders summary unavailable ({exc})")
        return
    print(
        f"  [Square] raw_square.orders: {int(total)} row(s) in DB | "
        f"API batch this run: {api_line_count} line(s) | "
        f"{int(sim)} with simulator prefix `{SIMULATED_ORDER_VARIATION_PREFIX}`*"
    )
    if api_line_count == 0 and int(total) > 0:
        print(
            "  [Square] Sandbox returned no API orders — existing DB rows (e.g. generate_sales.py) "
            "are kept; dbt will use them."
        )


def _get_client():
    from square import Square
    from square.environment import SquareEnvironment

    token = os.getenv("SQUARE_ACCESS_TOKEN")
    if not token:
        raise ValueError("SQUARE_ACCESS_TOKEN not set in .env")

    env_str = os.getenv("SQUARE_ENVIRONMENT", "sandbox").lower()
    env = SquareEnvironment.SANDBOX if "sandbox" in env_str else SquareEnvironment.PRODUCTION
    return Square(token=token, environment=env)


def fetch_catalogue(client) -> pd.DataFrame:
    items = {}       # item_id → item_name
    variations = []

    for obj in client.catalog.list(types="ITEM,ITEM_VARIATION"):
        if obj.type == "ITEM":
            name = ""
            if obj.item_data:
                name = obj.item_data.name or ""
            items[obj.id] = name
        elif obj.type == "ITEM_VARIATION":
            vd = obj.item_variation_data
            if not vd:
                continue
            price_cents = 0
            if vd.price_money and vd.price_money.amount:
                price_cents = vd.price_money.amount
            variations.append({
                "item_id":        vd.item_id or "",
                "variation_id":   obj.id,
                "variation_name": vd.name or "",
                "sku":            vd.sku or "",
                "price_money":    price_cents / 100,
            })

    if not variations:
        return pd.DataFrame(
            columns=["item_id", "variation_id", "variation_name", "sku",
                     "price_money", "item_name", "loaded_at"]
        )

    df = pd.DataFrame(variations)
    df["item_name"] = df["item_id"].map(items).fillna("")
    df["loaded_at"] = datetime.now(timezone.utc)
    return df


def fetch_inventory(client, catalogue_df: pd.DataFrame) -> pd.DataFrame:
    if catalogue_df.empty:
        print("  [Square] Catalogue empty — skipping inventory fetch")
        return pd.DataFrame(
            columns=["variation_id", "location_id", "quantity", "calculated_at",
                     "item_name", "sku", "price_money", "loaded_at"]
        )

    variation_ids = catalogue_df["variation_id"].dropna().tolist()
    all_counts = []

    for count in client.inventory.batch_get_counts(catalog_object_ids=variation_ids):
        all_counts.append({
            "variation_id":  count.catalog_object_id,
            "location_id":   count.location_id,
            "quantity":      int(float(count.quantity or "0")),
            "calculated_at": count.calculated_at,
        })

    if not all_counts:
        print("  [Square] No inventory counts returned")
        return pd.DataFrame(
            columns=["variation_id", "location_id", "quantity", "calculated_at",
                     "item_name", "sku", "price_money", "loaded_at"]
        )

    df = pd.DataFrame(all_counts)
    df = df.merge(
        catalogue_df[["variation_id", "item_name", "sku", "price_money"]],
        on="variation_id",
        how="left",
    )
    df["loaded_at"] = datetime.now(timezone.utc)
    return df


def fetch_orders(client) -> pd.DataFrame:
    start_at = (datetime.now(timezone.utc) - timedelta(days=90)).isoformat()

    locs_resp = client.locations.list()
    location_ids = [loc.id for loc in (locs_resp.locations or [])]

    if not location_ids:
        print("  [Square] No locations found — skipping orders fetch")
        return pd.DataFrame(
            columns=["order_id", "variation_id", "quantity_sold",
                     "total_money", "created_at", "loaded_at"]
        )

    all_line_items = []
    cursor = None

    while True:
        kwargs = {
            "location_ids": location_ids,
            "query": {
                "filter": {
                    "date_time_filter": {
                        "created_at": {"start_at": start_at}
                    }
                },
                "sort": {"sort_field": "CREATED_AT", "sort_order": "ASC"},
            },
        }
        if cursor:
            kwargs["cursor"] = cursor

        resp = client.orders.search(**kwargs)

        for order in (resp.orders or []):
            for item in (order.line_items or []):
                amount = 0
                if item.total_money and item.total_money.amount:
                    amount = item.total_money.amount
                all_line_items.append({
                    "order_id":      order.id,
                    "variation_id":  item.catalog_object_id or "",
                    "quantity_sold": int(float(item.quantity or "0")),
                    "total_money":   amount / 100,
                    "created_at":    order.created_at,
                })

        cursor = resp.cursor
        if not cursor:
            break

    if not all_line_items:
        print("  [Square] No orders found in the last 90 days — table will be empty")
        return pd.DataFrame(
            columns=["order_id", "variation_id", "quantity_sold",
                     "total_money", "created_at", "loaded_at"]
        )

    df = pd.DataFrame(all_line_items)
    df["loaded_at"] = datetime.now(timezone.utc)
    return df


def _upsert(con, df: pd.DataFrame, table_name: str, keys: list[str]) -> int:
    schema, table = table_name.split(".", 1)
    con.execute(f"CREATE SCHEMA IF NOT EXISTS {schema}")
    con.execute(f"""
        CREATE TABLE IF NOT EXISTS {table_name} AS
        SELECT * FROM df WHERE 1=0
    """)

    if not df.empty:
        key_filter = " AND ".join(
            f"{table_name}.{k} IN (SELECT {k} FROM df)" for k in keys
        )
        con.execute(f"DELETE FROM {table_name} WHERE {key_filter}")
        con.execute(f"INSERT INTO {table_name} SELECT * FROM df")

    return con.execute(f"SELECT COUNT(*) FROM {table_name}").fetchone()[0]


def load_catalogue(df: pd.DataFrame, db_path: str = "data/supply_chain.duckdb") -> None:
    os.makedirs("data", exist_ok=True)
    con = duckdb.connect(db_path)
    count = _upsert(con, df, "raw_square.catalogue", ["variation_id"])
    print(f"  raw_square.catalogue: {count} rows")
    con.close()


def load_inventory(df: pd.DataFrame, db_path: str = "data/supply_chain.duckdb") -> None:
    os.makedirs("data", exist_ok=True)
    con = duckdb.connect(db_path)
    count = _upsert(con, df, "raw_square.inventory_counts", ["variation_id", "location_id"])
    print(f"  raw_square.inventory_counts: {count} rows")
    con.close()


def load_orders(df: pd.DataFrame, db_path: str = "data/supply_chain.duckdb") -> None:
    """
    Upsert Square API order lines into raw_square.orders.

    If the API returns **no rows** (typical in an empty sandbox), ``df`` is empty: ``_upsert`` does
    not delete anything, so rows inserted locally (e.g. ``scripts/generate_sales.py``) remain and dbt
    can still build velocity from ``raw_square.orders``.
    """
    os.makedirs("data", exist_ok=True)
    con = duckdb.connect(db_path)
    count = _upsert(con, df, "raw_square.orders", ["order_id", "variation_id"])
    print(f"  raw_square.orders: {count} rows (total table; includes any local/simulator rows)")
    con.close()


if __name__ == "__main__":
    client = _get_client()
    print("Fetching Square data...")

    print("  Fetching catalogue...")
    cat_df = fetch_catalogue(client)
    load_catalogue(cat_df)

    print("  Fetching inventory counts...")
    inv_df = fetch_inventory(client, cat_df)
    load_inventory(inv_df)

    print("  Fetching orders (last 90 days)...")
    ord_df = fetch_orders(client)
    load_orders(ord_df)

    print("Square ingestion complete.")
