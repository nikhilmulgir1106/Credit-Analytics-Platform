-- Governance: RISK_ANALYST view of borrowers — PII unmasked under policy.
-- This role is explicitly authorized to see exact age and credit limit.
-- Grain: one row per client.

select * from {{ ref('dim_borrower') }}
