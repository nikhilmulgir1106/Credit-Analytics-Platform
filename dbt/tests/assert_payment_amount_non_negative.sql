-- Custom singular test: payment amounts must never be negative.
-- Returns offending rows; the test fails if any are returned.
select
    txn_id,
    amount
from {{ ref('stg_txn__payments') }}
where amount < 0
