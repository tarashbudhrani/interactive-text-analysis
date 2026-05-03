import argparse
import hashlib
import os
import subprocess
from pathlib import Path

from dotenv import load_dotenv

load_dotenv()

DB_PATH = os.getenv("DUCKDB_PATH", "data/supply_chain.duckdb")
FP_PATH = Path(os.getenv("SQUARE_FP_PATH", "data/.square_pipeline_fp"))


def _truthy(name: str) -> bool:
    return os.getenv(name, "").strip().lower() in ("1", "true", "yes")


def _csv_digest() -> str:
    path = os.getenv("MERGE_INVENTORY_CSV", "").strip()
    if path and Path(path).expanduser().is_file():
        data = Path(path).expanduser().read_bytes()
        return hashlib.sha256(data).hexdigest()
    return ""


def _combined_square_fp(cat_df, inv_df, ord_df, db_path: str) -> str:
    """
    Includes DB state of raw_square.orders (scripts/generate_sales.py, etc.) so incremental skips
    still run dbt after local inserts even when the Square API payload is unchanged / empty.
    """
    from ingest.square_ingest import orders_table_digest, square_payload_fingerprint

    base = square_payload_fingerprint(cat_df, inv_df, ord_df)
    ord_state = orders_table_digest(db_path)
    return hashlib.sha256(f"{base}:{_csv_digest()}:{ord_state}".encode()).hexdigest()


def _read_saved_fp() -> str | None:
    try:
        return FP_PATH.read_text().strip()
    except FileNotFoundError:
        return None


def _write_fp(fp: str) -> None:
    FP_PATH.parent.mkdir(parents=True, exist_ok=True)
    FP_PATH.write_text(fp)


def run_square_ingestion() -> bool:
    """Fetch Square and optionally reload DuckDB. Returns True if raw Square tables changed."""
    from ingest.square_ingest import (
        _get_client,
        fetch_catalogue,
        fetch_inventory,
        fetch_orders,
        load_catalogue,
        load_inventory,
        load_orders,
        print_raw_orders_ingest_summary,
    )
    from ingest.merge_inventory_csv import merge_inventory_csv_if_configured

    print("  [Square] Catalogue, inventory, orders...")
    client = _get_client()
    cat_df = fetch_catalogue(client)
    inv_df = fetch_inventory(client, cat_df)
    ord_df = fetch_orders(client)

    fp_new = _combined_square_fp(cat_df, inv_df, ord_df, DB_PATH)
    fp_prev = _read_saved_fp()
    skip_reload = _truthy("SKIP_SQUARE_RELOAD_IF_UNCHANGED")
    db_ok = Path(DB_PATH).is_file()

    if skip_reload and fp_prev == fp_new and db_ok:
        print("  [Square] Payload unchanged — skipping DuckDB writes (SKIP_SQUARE_RELOAD_IF_UNCHANGED=1)")
        return False

    load_catalogue(cat_df, db_path=DB_PATH)
    load_inventory(inv_df, db_path=DB_PATH)
    load_orders(ord_df, db_path=DB_PATH)
    print_raw_orders_ingest_summary(DB_PATH, len(ord_df))
    merge_inventory_csv_if_configured(DB_PATH)
    _write_fp(fp_new)
    print(f"  [Square] Reload complete (fingerprint saved to {FP_PATH})")
    return True


def run_transformation() -> None:
    print("\nRunning dbt build (staging → intermediate → marts)...")
    result = subprocess.run(
        ["dbt", "build", "--profiles-dir", "."],
        capture_output=True,
        text=True,
    )
    print(result.stdout)
    if result.returncode != 0:
        print(result.stderr)
        raise RuntimeError("dbt build failed — see output above")


def run_slack_notifications(dbt_ran: bool) -> None:
    if _truthy("DISABLE_SLACK_ALERTS"):
        print("  [Slack] DISABLED via DISABLE_SLACK_ALERTS=1")
        return
    if not os.getenv("SLACK_WEBHOOK_URL", "").strip():
        print("  [Slack] SKIPPED — add SLACK_WEBHOOK_URL to post to Slack")
        return
    if not dbt_ran:
        print("  [Slack] SKIPPED — dbt did not run (nothing to notify on)")
        return
    try:
        from ingest.slack_alerts import post_all_slack_messages

        post_all_slack_messages()
    except Exception as exc:
        print(f"  [Slack] WARNING — notifications failed: {exc}")


def main(skip_extended_macro_ingest: bool = True) -> None:
    print("=" * 50)
    print("Square inventory pipeline (local POS data only)")
    print("=" * 50)

    square_changed = run_square_ingestion()

    if not skip_extended_macro_ingest:
        try:
            from ingest.census_ingest import fetch_marts, load_to_duckdb as census_load

            key = os.getenv("CENSUS_API_KEY")
            if key:
                census_load(fetch_marts(key))
            else:
                print("  [Census] SKIPPED — no CENSUS_API_KEY")
        except ValueError as e:
            print(f"  [Census] SKIPPED — {e}")

        try:
            from ingest.bls_ingest import fetch_ppi, load_to_duckdb as bls_load

            bls_load(
                fetch_ppi(registration_key=os.getenv("BLS_API_KEY", ""), db_path=DB_PATH),
                db_path=DB_PATH,
            )
        except Exception as exc:
            print(f"  [BLS] SKIPPED — {exc}")

    db_missing = not Path(DB_PATH).is_file()
    skip_dbt = _truthy("SKIP_DBT_IF_RAW_UNCHANGED") and not db_missing
    if skip_dbt and not square_changed:
        print(
            "\nSkipping dbt — Square/raw_orders fingerprint unchanged "
            "(SKIP_DBT_IF_RAW_UNCHANGED=1). Run scripts/generate_sales.py then pipeline again to refresh."
        )
        run_slack_notifications(dbt_ran=False)
        print("\nPipeline complete.")
        return

    run_transformation()
    run_slack_notifications(dbt_ran=True)

    print("\nPipeline complete.")
    print("Dashboard: streamlit run streamlit_app/app.py")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Square inventory pipeline + dbt + Slack")
    parser.add_argument(
        "--with-extended-macro-ingest",
        action="store_true",
        help="Also run Census MARTS + BLS PPI ingestion (optional macro inputs for disabled cost models)",
    )
    args = parser.parse_args()
    main(skip_extended_macro_ingest=not args.with_extended_macro_ingest)
