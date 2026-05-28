-- Gold (risk): portfolio default rate and exposure by segment, long format so a
-- dashboard can pivot on any dimension. Grain: one row per (segment_dimension,
-- segment_value).

with borrowers as (

    select * from {{ ref('dim_borrower') }}

),

labelled as (

    select
        b.*,
        u.is_default
    from borrowers as b
    inner join {{ ref('stg_uci__credit_default') }} as u on b.client_id = u.client_id

),

segmented as (

    select
        'age_band' as segment_dimension,
        age_band as segment_value,
        is_default,
        credit_limit
    from labelled
    union all
    select
        'credit_limit_band',
        credit_limit_band,
        is_default,
        credit_limit
    from labelled
    union all
    select
        'education_level',
        education_level,
        is_default,
        credit_limit
    from labelled
    union all
    select
        'sex',
        sex,
        is_default,
        credit_limit
    from labelled
    union all
    select
        'marital_status',
        marital_status,
        is_default,
        credit_limit
    from labelled
    union all
    select
        'region',
        region,
        is_default,
        credit_limit
    from labelled

)

select
    segment_dimension,
    segment_value,
    count(*) as n_clients,
    sum(is_default) as n_default,
    round(avg(is_default), 4) as default_rate,
    round(avg(credit_limit), 2) as avg_credit_limit,
    sum(credit_limit) as total_credit_limit_exposure
from segmented
group by 1, 2
order by 1, 2
