# CreditPulse — Data Dictionary

Business definitions for the gold (MARTS) and governance layers as currently
built on DuckDB. Classification drives masking: **PII** and **CONFIDENTIAL**
columns are masked from the analyst role (see [governance](../governance)).

> Source: UCI "Default of Credit Card Clients" (Taiwan, 2005), 30,000 clients.
> `repay_status_m1..m6` use the original UCI scale (-2 = no credit use, -1 = paid
> in full, 0 = revolving credit, 1..9 = months past due). `m1` = most recent month.

## `dim_borrower` — conformed borrower dimension
Grain: one row per client.

| Column | Type | Classification | Definition |
| --- | --- | --- | --- |
| client_id | INT | — | Borrower natural key. |
| credit_limit | INT | CONFIDENTIAL | Credit limit (NT dollars). |
| credit_limit_band | STR | PUBLIC | Banded limit: `<50k`, `50k-150k`, `150k-300k`, `300k+`. |
| sex_code / sex | INT/STR | PII | 1=male, 2=female. |
| education_code / education_level | INT/STR | PII | graduate_school / university / high_school / other_unknown. |
| marriage_code / marital_status | INT/STR | PII | married / single / other / unknown. |
| age | INT | PII | Client age in years. |
| age_band | STR | PUBLIC | `<30`, `30-39`, `40-49`, `50-59`, `60+`. |
| region | STR | PUBLIC | Synthetic geographic region (row-access attribute): north/south/east/west. |

## `fct_payment_history` — payment-history fact
Grain: one row per client per statement month (`month_index` 1..6).

| Column | Type | Definition |
| --- | --- | --- |
| payment_history_id | STR | Surrogate key, md5(client_id + month_index). |
| client_id | INT | FK → dim_borrower. |
| month_index | INT | 1 = most recent statement month .. 6 = oldest. |
| repay_status | INT | UCI repayment status for the month. |
| is_delinquent | BOOL | repay_status > 0. |
| bill_amt | DOUBLE | Bill statement amount (NT dollars). |
| pay_amt | DOUBLE | Amount paid (NT dollars). |
| utilization | DOUBLE | bill_amt / credit_limit. |

## `mart_portfolio_risk` — default rate & exposure by segment
Grain: one row per (`segment_dimension`, `segment_value`). Long format for pivoting.

| Column | Type | Definition |
| --- | --- | --- |
| segment_dimension | STR | age_band / credit_limit_band / education_level / sex / marital_status / region. |
| segment_value | STR | The segment value. |
| n_clients | INT | Clients in the segment. |
| n_default | INT | Clients who defaulted next month. |
| default_rate | DOUBLE | n_default / n_clients (0..1). |
| avg_credit_limit | DOUBLE | Mean credit limit in the segment. |
| total_credit_limit_exposure | BIGINT | Sum of credit limits in the segment. |

## `feature_default_prediction` — ML feature table
Grain: one row per client. Single governed feature definition shared by training and serving.

| Column | Type | Definition |
| --- | --- | --- |
| client_id | INT | Borrower key. |
| credit_limit, age, sex_code, education_code, marriage_code | INT | Raw attributes (encoded in the ML step). |
| avg_repay_status | DOUBLE | Mean repayment status across 6 months. |
| max_repay_status | INT | Worst (max) repayment status. |
| months_delinquent | INT | Count of months with repay_status > 0 (0..6). |
| total_bill_amt / total_pay_amt | DOUBLE | 6-month sums. |
| avg_utilization | DOUBLE | Mean (avg bill / credit_limit). |
| pay_to_bill_ratio | DOUBLE | total_pay_amt / total_bill_amt. |
| age_band, credit_limit_band | STR | Segment bands. |
| **is_default** | INT | **Training label** — 1 if the client defaulted next month, else 0. |

## Governance views (`governance` schema)

| View | Role | Policy applied |
| --- | --- | --- |
| gov_dim_borrower_risk_analyst | RISK_ANALYST | PII unmasked (authorized). |
| gov_dim_borrower_analyst | ANALYST | `age` and `credit_limit` masked to NULL; bands retained. |
| gov_payments_analyst | ANALYST | `borrower_email` local part → `****`; `borrower_ip` → `***.***.***.***`. |
| gov_dim_borrower_regional | Regional ANALYST | Analyst masking + row-access filter to `var('access_region')` (default `west`). |

## Operational (`meta` schema)

| Object | Definition |
| --- | --- |
| meta.dq_results | One row per Great Expectations expectation per run (run-stamped, append-only). |
| meta.mart_data_quality | Per run/table/severity summary: checks, passed, failed, pass_rate, is_latest. |
