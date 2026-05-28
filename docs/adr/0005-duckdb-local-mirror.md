# ADR-005 — DuckDB as the local mirror of Snowflake

**Status:** accepted

**Context.** The production target is Snowflake, but the project must build and
run fully on a MacBook Air M2 with 8 GB RAM at zero cost. Snowflake SQL and
DuckDB SQL are near-identical, and DuckDB streams larger-than-RAM data.

**Decision.** Use DuckDB (`warehouse/creditpulse.duckdb`) as the local warehouse
via `dbt-duckdb`. Keep all transformation logic in dbt so the same models target
Snowflake later with only a profile change.

**Consequences.** Cloud-free development parity; the design is validated locally
before any spend. DuckDB lacks Snowflake-native RBAC, masking, and row-access —
those are simulated (see [ADR-007](0007-governance-via-views.md)). The
multi-GB Lending Club tape is read by DuckDB streaming, never loaded into pandas.
