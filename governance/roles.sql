-- =============================================================================
-- CreditPulse — RBAC role hierarchy (PRODUCTION TARGET: Snowflake)
-- -----------------------------------------------------------------------------
-- This file documents the production governance model. It is NOT run in local
-- DuckDB mode — DuckDB is single-file/embedded and has no Snowflake-style RBAC.
-- Locally, the same intent is demonstrated with role-scoped views in the dbt
-- `governance` schema (models/governance/*.sql).
--
-- Hierarchy (least privilege):
--   CP_ADMIN
--    ├── CP_LOADER        : write RAW (bronze) only
--    ├── CP_TRANSFORMER   : build STAGING + MARTS
--    └── CP_GOVERNANCE    : owns masking + row-access policies
--          ├── CP_ANALYST       : read MARTS, PII masked
--          └── CP_RISK_ANALYST  : read MARTS, PII unmasked under policy
-- =============================================================================

USE ROLE SECURITYADMIN;

CREATE ROLE IF NOT EXISTS CP_ADMIN;
CREATE ROLE IF NOT EXISTS CP_LOADER;
CREATE ROLE IF NOT EXISTS CP_TRANSFORMER;
CREATE ROLE IF NOT EXISTS CP_GOVERNANCE;
CREATE ROLE IF NOT EXISTS CP_ANALYST;
CREATE ROLE IF NOT EXISTS CP_RISK_ANALYST;

-- Role inheritance.
GRANT ROLE CP_LOADER       TO ROLE CP_ADMIN;
GRANT ROLE CP_TRANSFORMER  TO ROLE CP_ADMIN;
GRANT ROLE CP_GOVERNANCE   TO ROLE CP_ADMIN;
GRANT ROLE CP_ANALYST      TO ROLE CP_GOVERNANCE;
GRANT ROLE CP_RISK_ANALYST TO ROLE CP_GOVERNANCE;

-- Schema-level privileges (least privilege).
GRANT USAGE ON DATABASE CREDITPULSE_PROD TO ROLE CP_LOADER;
GRANT ALL   ON SCHEMA   CREDITPULSE_PROD.RAW     TO ROLE CP_LOADER;

GRANT USAGE ON DATABASE CREDITPULSE_PROD TO ROLE CP_TRANSFORMER;
GRANT ALL   ON SCHEMA   CREDITPULSE_PROD.STAGING TO ROLE CP_TRANSFORMER;
GRANT ALL   ON SCHEMA   CREDITPULSE_PROD.MARTS   TO ROLE CP_TRANSFORMER;

-- Analysts read only governed gold marts — never RAW or STAGING.
GRANT USAGE  ON DATABASE CREDITPULSE_PROD              TO ROLE CP_ANALYST;
GRANT USAGE  ON SCHEMA   CREDITPULSE_PROD.MARTS        TO ROLE CP_ANALYST;
GRANT SELECT ON ALL TABLES IN SCHEMA CREDITPULSE_PROD.MARTS TO ROLE CP_ANALYST;
GRANT ROLE   CP_ANALYST TO ROLE CP_RISK_ANALYST;  -- risk analyst is a superset
