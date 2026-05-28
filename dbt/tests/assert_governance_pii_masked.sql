-- Governance gate: the analyst views must never expose masked PII.
-- Returns offending rows; the test fails if any are returned.

select
    'age_not_masked' as violation,
    client_id::varchar as id
from {{ ref('gov_dim_borrower_analyst') }}
where age is not null

union all
select
    'credit_limit_not_masked',
    client_id::varchar
from {{ ref('gov_dim_borrower_analyst') }}
where credit_limit is not null

union all
select
    'email_not_masked',
    txn_id
from {{ ref('gov_payments_analyst') }}
where borrower_email not like '****@%'

union all
select
    'ip_not_masked',
    txn_id
from {{ ref('gov_payments_analyst') }}
where borrower_ip <> '***.***.***.***'
