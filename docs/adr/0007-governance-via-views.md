# ADR-007 — Governance via role-scoped views in local mode

**Status:** accepted

**Context.** The production governance model uses Snowflake dynamic masking
policies, row-access policies, and RBAC. DuckDB is embedded/single-file and has
no equivalent role-session enforcement.

**Decision.** Simulate governance with **role-scoped dbt views** in a
`governance` schema:
- masking → the [`mask()`](../../dbt/macros/mask.sql) macro applied in
  `gov_*_analyst` views (analyst) vs an unmasked `gov_*_risk_analyst` view;
- row-access → `gov_dim_borrower_regional` filters on `var('access_region')`.

The production Snowflake DDL is kept in [`governance/`](../../governance) as the
documented target (not executed locally).

**Consequences.** Masking and row-access are demonstrable and dbt-tested
(singular tests assert PII is masked and rows are filtered), with lineage. The
contrast is "different views per role" rather than "one table, policy by session
role" — a faithful local stand-in that ports to Snowflake policies later.
