-- Gold (ml): single wide feature table feeding the default-prediction model, so
-- training and serving share one governed definition. Grain: one row per client.

with src as (

    select * from {{ ref('stg_uci__credit_default') }}

),

borrowers as (

    select
        client_id,
        age_band,
        credit_limit_band
    from {{ ref('dim_borrower') }}

),

features as (

    select
        s.client_id,

        -- Raw attributes (encoders applied in the ML step).
        s.credit_limit,
        s.age,
        s.sex_code,
        s.education_code,
        s.marriage_code,

        -- Repayment-status aggregates across the 6 months.
        (
            s.repay_status_m1 + s.repay_status_m2 + s.repay_status_m3
            + s.repay_status_m4 + s.repay_status_m5 + s.repay_status_m6
        ) / 6.0 as avg_repay_status,
        greatest(
            s.repay_status_m1, s.repay_status_m2, s.repay_status_m3,
            s.repay_status_m4, s.repay_status_m5, s.repay_status_m6
        ) as max_repay_status,
        (
            cast(s.repay_status_m1 > 0 as int) + cast(s.repay_status_m2 > 0 as int)
            + cast(s.repay_status_m3 > 0 as int) + cast(s.repay_status_m4 > 0 as int)
            + cast(s.repay_status_m5 > 0 as int) + cast(s.repay_status_m6 > 0 as int)
        ) as months_delinquent,

        -- Billing / payment aggregates.
        (
            s.bill_amt_m1 + s.bill_amt_m2 + s.bill_amt_m3
            + s.bill_amt_m4 + s.bill_amt_m5 + s.bill_amt_m6
        ) as total_bill_amt,
        (
            s.pay_amt_m1 + s.pay_amt_m2 + s.pay_amt_m3
            + s.pay_amt_m4 + s.pay_amt_m5 + s.pay_amt_m6
        ) as total_pay_amt,

        -- Average utilization across the 6 statements.
        case
            when s.credit_limit > 0 then round(
                ((
                    s.bill_amt_m1 + s.bill_amt_m2 + s.bill_amt_m3
                    + s.bill_amt_m4 + s.bill_amt_m5 + s.bill_amt_m6
                ) / 6.0) / s.credit_limit, 4
            )
        end as avg_utilization,

        b.age_band,
        b.credit_limit_band,

        s.is_default

    from src as s
    inner join borrowers as b on s.client_id = b.client_id

),

final as (

    select
        *,
        case
            when total_bill_amt > 0
                then round(total_pay_amt / total_bill_amt, 4)
        end as pay_to_bill_ratio
    from features

)

select * from final
