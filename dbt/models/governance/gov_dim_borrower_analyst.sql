-- Governance: ANALYST view of borrowers — least privilege.
-- Exact age (PII) and exact credit_limit (CONFIDENTIAL) are masked; the
-- non-identifying bands and demographic labels are retained for analysis.
-- Grain: one row per client.

select
    client_id,

    {{ mask('credit_limit', 'null_int') }} as credit_limit,
    credit_limit_band,

    sex_code,
    sex,
    education_code,
    education_level,
    marriage_code,
    marital_status,

    {{ mask('age', 'null_int') }} as age,
    age_band,

    region

from {{ ref('dim_borrower') }}
