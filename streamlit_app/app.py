import altair as alt
import pandas as pd
import streamlit as st

from db import connect

st.set_page_config(page_title="Retail inventory monitor", layout="wide")
st.title("Retail inventory monitor")
st.caption("Square POS — velocity, on-hand inventory, and reorder timing from your own sales data.")

try:
    con = connect()
    meta = con.execute("SELECT * FROM mart_pipeline_metadata ORDER BY source_table").df()
    pulse = con.execute(
        """
        SELECT
          SUM(CASE WHEN order_date >= CURRENT_DATE - INTERVAL '7 days'
              THEN quantity_sold END) AS units_7d,
          SUM(CASE WHEN order_date >= CURRENT_DATE - INTERVAL '30 days'
              THEN quantity_sold END) AS units_30d,
          COUNT(DISTINCT CASE WHEN order_date >= CURRENT_DATE - INTERVAL '7 days'
                  THEN order_id END) AS orders_7d
        FROM stg_square__orders
        """
    ).df()
    reorder_n = con.execute("SELECT COUNT(*) FROM mart_reorder_signal").fetchone()[0]
    con.close()
except Exception as exc:
    st.error(f"Could not read DuckDB — run `python run_pipeline.py` first.\n\n{exc}")
    st.stop()

u7 = int(pulse["units_7d"].iloc[0] or 0)
u30 = int(pulse["units_30d"].iloc[0] or 0)
o7 = int(pulse["orders_7d"].iloc[0] or 0)

c1, c2, c3, c4 = st.columns(4)
c1.metric("Units sold (7d)", f"{u7:,}")
c2.metric("Units sold (30d)", f"{u30:,}")
c3.metric("Orders (7d)", f"{o7:,}")
c4.metric("Active reorder SKUs", f"{int(reorder_n):,}", help="Rows in mart_reorder_signal")

st.divider()
st.subheader("Pipeline freshness")
st.dataframe(meta, use_container_width=True, hide_index=True)

st.divider()
st.subheader("Quick navigation")
st.markdown(
    """
- **Sales velocity** — how fast each SKU sells (7d vs 30d trend).
- **Current inventory** — on-hand quantities by location with coverage buckets.
- **Reorder signals** — estimated days until stockout and suggested reorder urgency.
"""
)

try:
    con = connect()
    top = con.execute(
        """
        SELECT item_name,
               ROUND(avg_daily_units_sold_30d, 2) AS velocity_30d,
               quantity_on_hand AS qoh,
               ROUND(dsi, 1) AS days_cover
        FROM mart_stock_position
        WHERE avg_daily_units_sold_30d > 0
        ORDER BY avg_daily_units_sold_30d DESC
        LIMIT 12
        """
    ).df()
    con.close()
    chart = (
        alt.Chart(top)
        .mark_bar()
        .encode(
            x=alt.X("velocity_30d:Q", title="Avg units / day (30d)"),
            y=alt.Y("item_name:N", sort="-x", title=""),
            tooltip=["item_name", "velocity_30d", "qoh", "days_cover"],
        )
        .properties(height=320)
    )
    st.altair_chart(chart, use_container_width=True)
except Exception:
    pass
