-- Governance: row-access policy demonstration. A regional analyst sees only
-- borrowers in their assigned region (var 'access_region', default 'west'), and
-- inherits the analyst PII masking by building on gov_dim_borrower_analyst.
-- Run with a different region:  dbt build --vars '{access_region: north}'

select *
from {{ ref('gov_dim_borrower_analyst') }}
where region = '{{ var("access_region", "west") }}'
