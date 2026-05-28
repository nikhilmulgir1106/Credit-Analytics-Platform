-- Gold (core): payment-history fact, unpivoted from the wide UCI monthly columns.
-- Grain: one row per client per statement month (month_index 1=most recent .. 6=oldest).

with src as (

    select * from {{ ref('stg_uci__credit_default') }}

),

unpivoted as (

    select
        client_id,
        credit_limit,
        1 as month_index,
        repay_status_m1 as repay_status,
        bill_amt_m1 as bill_amt,
        pay_amt_m1 as pay_amt
    from src
    union all
    select
        client_id,
        credit_limit,
        2,
        repay_status_m2,
        bill_amt_m2,
        pay_amt_m2
    from src
    union all
    select
        client_id,
        credit_limit,
        3,
        repay_status_m3,
        bill_amt_m3,
        pay_amt_m3
    from src
    union all
    select
        client_id,
        credit_limit,
        4,
        repay_status_m4,
        bill_amt_m4,
        pay_amt_m4
    from src
    union all
    select
        client_id,
        credit_limit,
        5,
        repay_status_m5,
        bill_amt_m5,
        pay_amt_m5
    from src
    union all
    select
        client_id,
        credit_limit,
        6,
        repay_status_m6,
        bill_amt_m6,
        pay_amt_m6
    from src

)

select
    md5(client_id::varchar || '-' || month_index::varchar) as payment_history_id,
    client_id,
    month_index,
    repay_status,
    repay_status > 0 as is_delinquent,
    bill_amt,
    pay_amt,
    case when credit_limit > 0 then round(bill_amt / credit_limit, 4) end as utilization
from unpivoted
