-- =============================================================================
-- CreditPulse — Row-access policies (PRODUCTION TARGET: Snowflake)
-- -----------------------------------------------------------------------------
-- NOT run in local DuckDB mode. Local equivalent: models/governance/
-- gov_dim_borrower_regional.sql filters rows by the `access_region` var.
--
-- A row-access policy restricts which rows a role can see. Here, regional
-- analysts only see borrowers in their mapped region; CP_RISK_ANALYST and
-- CP_ADMIN see all rows. The region->role mapping lives in a governance table.
-- =============================================================================

USE ROLE CP_GOVERNANCE;

-- Entitlement table: which role may see which region.
CREATE TABLE IF NOT EXISTS CREDITPULSE_PROD.GOVERNANCE.region_entitlements (
    role_name STRING,
    region    STRING
);

CREATE OR REPLACE ROW ACCESS POLICY rap_borrower_region
    AS (region STRING) RETURNS BOOLEAN ->
        CURRENT_ROLE() IN ('CP_RISK_ANALYST', 'CP_ADMIN')
        OR EXISTS (
            SELECT 1 FROM CREDITPULSE_PROD.GOVERNANCE.region_entitlements e
            WHERE e.role_name = CURRENT_ROLE()
              AND e.region = region
        );

ALTER TABLE CREDITPULSE_PROD.MARTS.DIM_BORROWER
    ADD ROW ACCESS POLICY rap_borrower_region ON (region);
