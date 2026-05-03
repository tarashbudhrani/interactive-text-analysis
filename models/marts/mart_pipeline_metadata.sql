with square_catalogue_meta as (
    select 'raw_square.catalogue'           as source_table, max(loaded_at) as last_loaded_at
    from {{ source('raw_square', 'catalogue') }}
),

square_inventory_meta as (
    select 'raw_square.inventory_counts' as source_table, max(loaded_at) as last_loaded_at
    from {{ source('raw_square', 'inventory_counts') }}
),

square_orders_meta as (
    select 'raw_square.orders'             as source_table, max(loaded_at) as last_loaded_at
    from {{ source('raw_square', 'orders') }}
),

unioned as (
    select * from square_catalogue_meta
    union all select * from square_inventory_meta
    union all select * from square_orders_meta
)

select
    source_table,
    last_loaded_at,
    case
        when last_loaded_at >= now() - interval '2 hours'   then 'FRESH'
        when last_loaded_at >= now() - interval '24 hours'  then 'STALE'
        else                                                     'VERY_STALE'
    end as freshness_status
from unioned
order by source_table
