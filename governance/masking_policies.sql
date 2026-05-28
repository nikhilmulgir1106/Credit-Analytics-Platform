-- =============================================================================
-- CreditPulse — Dynamic data masking (PRODUCTION TARGET: Snowflake)
-- -----------------------------------------------------------------------------
-- NOT run in local DuckDB mode. Local equivalent: the masking macro
-- dbt/macros/mask.sql applied in models/governance/gov_*_analyst.sql.
--
-- Masking policies return clear values to CP_RISK_ANALYST and masked values to
-- everyone else (CP_ANALYST). Policies are attached to PII/CONFIDENTIAL columns
-- identified by object tags (see object tagging below).
-- =============================================================================

USE ROLE CP_GOVERNANCE;

-- Numeric: exact value hidden, NULL returned to unauthorized roles.
CREATE OR REPLACE MASKING POLICY mask_int_confidential AS (val NUMBER) RETURNS NUMBER ->
    CASE WHEN CURRENT_ROLE() IN ('CP_RISK_ANALYST', 'CP_ADMIN') THEN val ELSE NULL END;

-- Email: local part redacted.
CREATE OR REPLACE MASKING POLICY mask_email AS (val STRING) RETURNS STRING ->
    CASE WHEN CURRENT_ROLE() IN ('CP_RISK_ANALYST', 'CP_ADMIN') THEN val
         ELSE REGEXP_REPLACE(val, '^[^@]*', '****') END;

-- IP: fully redacted.
CREATE OR REPLACE MASKING POLICY mask_ip AS (val STRING) RETURNS STRING ->
    CASE WHEN CURRENT_ROLE() IN ('CP_RISK_ANALYST', 'CP_ADMIN') THEN val
         ELSE '***.***.***.***' END;

-- Attach policies to columns.
ALTER TABLE CREDITPULSE_PROD.MARTS.DIM_BORROWER
    MODIFY COLUMN age          SET MASKING POLICY mask_int_confidential,
    MODIFY COLUMN credit_limit SET MASKING POLICY mask_int_confidential;

ALTER TABLE CREDITPULSE_PROD.MARTS.FCT_PAYMENT
    MODIFY COLUMN borrower_email SET MASKING POLICY mask_email,
    MODIFY COLUMN borrower_ip    SET MASKING POLICY mask_ip;

-- Object tagging / classification (drives catalog + which policy applies).
CREATE TAG IF NOT EXISTS data_classification ALLOWED_VALUES 'PII', 'CONFIDENTIAL', 'PUBLIC';
ALTER TABLE CREDITPULSE_PROD.MARTS.DIM_BORROWER
    MODIFY COLUMN age          SET TAG data_classification = 'PII',
    MODIFY COLUMN credit_limit SET TAG data_classification = 'CONFIDENTIAL';
