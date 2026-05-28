-- Gold (core): conformed borrower dimension.
-- Grain: one row per client. Descriptive attributes + derived segments only;
-- the default outcome lives in the risk mart and ML feature table, not here.

with clients as (

    select * from {{ ref('stg_uci__credit_default') }}

)

select
    client_id,
    credit_limit,

    sex_code,
    case sex_code when 1 then 'male' when 2 then 'female' else 'unknown' end as sex,

    education_code,
    case education_code
        when 1 then 'graduate_school'
        when 2 then 'university'
        when 3 then 'high_school'
        else 'other_unknown'
    end as education_level,

    marriage_code,
    case marriage_code
        when 1 then 'married'
        when 2 then 'single'
        when 3 then 'other'
        else 'unknown'
    end as marital_status,

    age,
    case
        when age < 30 then '<30'
        when age < 40 then '30-39'
        when age < 50 then '40-49'
        when age < 60 then '50-59'
        else '60+'
    end as age_band,

    case
        when credit_limit < 50000 then '<50k'
        when credit_limit < 150000 then '50k-150k'
        when credit_limit < 300000 then '150k-300k'
        else '300k+'
    end as credit_limit_band,

    -- Synthetic region (deterministic from client_id) — a non-PII attribute used
    -- to demonstrate row-access policies in the governance layer.
    case client_id % 4
        when 0 then 'north'
        when 1 then 'south'
        when 2 then 'east'
        else 'west'
    end as region

from clients
