-- Silver: one staging model per source. Cleaning only — type casts, renames to
-- project naming standard, dedupe on the natural key. No business logic, no joins.
-- Grain: one row per credit card client.

with source as (

    select * from {{ source('raw', 'uci_credit_default') }}

),

renamed as (

    select
        cast(id as integer) as client_id,
        cast(limit_bal as integer) as credit_limit,
        cast(sex as integer) as sex_code,
        cast(education as integer) as education_code,
        cast(marriage as integer) as marriage_code,
        cast(age as integer) as age,

        -- Repayment status by month, most-recent (m1) to oldest (m6).
        cast(pay_0 as integer) as repay_status_m1,
        cast(pay_2 as integer) as repay_status_m2,
        cast(pay_3 as integer) as repay_status_m3,
        cast(pay_4 as integer) as repay_status_m4,
        cast(pay_5 as integer) as repay_status_m5,
        cast(pay_6 as integer) as repay_status_m6,

        -- Bill statement amount by month (m1 most recent).
        cast(bill_amt1 as double) as bill_amt_m1,
        cast(bill_amt2 as double) as bill_amt_m2,
        cast(bill_amt3 as double) as bill_amt_m3,
        cast(bill_amt4 as double) as bill_amt_m4,
        cast(bill_amt5 as double) as bill_amt_m5,
        cast(bill_amt6 as double) as bill_amt_m6,

        -- Amount paid by month (m1 most recent).
        cast(pay_amt1 as double) as pay_amt_m1,
        cast(pay_amt2 as double) as pay_amt_m2,
        cast(pay_amt3 as double) as pay_amt_m3,
        cast(pay_amt4 as double) as pay_amt_m4,
        cast(pay_amt5 as double) as pay_amt_m5,
        cast(pay_amt6 as double) as pay_amt_m6,

        cast("default payment next month" as integer) as is_default,

        _load_date as load_date,
        _loaded_at as loaded_at

    from source

)

select * from renamed
-- Dedupe on natural key, keeping the most recently loaded row.
qualify row_number() over (partition by client_id order by loaded_at desc) = 1
