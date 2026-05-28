-- Governance gate: the regional row-access view must only expose its region.
-- Returns offending rows; the test fails if any are returned.

select client_id
from {{ ref('gov_dim_borrower_regional') }}
where region <> '{{ var("access_region", "west") }}'
