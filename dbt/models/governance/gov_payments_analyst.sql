-- Governance: ANALYST view of payment events — synthetic PII masked.
-- Email local-part and IP address are redacted; transaction facts are retained.
-- Grain: one row per transaction.

select
    txn_id,
    client_id,
    txn_ts,
    amount,
    channel,
    txn_type,
    status,

    {{ mask('borrower_email', 'email') }} as borrower_email,
    {{ mask('borrower_ip', 'ip') }} as borrower_ip

from {{ ref('stg_txn__payments') }}
