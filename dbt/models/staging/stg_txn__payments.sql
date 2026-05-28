-- Silver: staging for the synthetic payment-events feed. Cleaning only.
-- Grain: one row per transaction.

with source as (

    select * from {{ source('raw', 'transactions') }}

),

renamed as (

    select
        cast(txn_id as varchar) as txn_id,
        cast(borrower_id as integer) as client_id,
        cast(txn_ts as timestamp) as txn_ts,
        cast(amount as double) as amount,
        cast(channel as varchar) as channel,
        cast(txn_type as varchar) as txn_type,
        cast(status as varchar) as status,

        -- Synthetic PII — masked downstream in the governance layer.
        cast(borrower_email as varchar) as borrower_email,
        cast(borrower_ip as varchar) as borrower_ip,

        _load_date as load_date,
        _loaded_at as loaded_at

    from source

)

select * from renamed
qualify row_number() over (partition by txn_id order by loaded_at desc) = 1
