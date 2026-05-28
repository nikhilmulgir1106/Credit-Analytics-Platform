{#
    Reusable PII/CONFIDENTIAL masking. In local DuckDB mode, masking is applied
    in role-scoped views (governance schema) rather than via Snowflake dynamic
    masking policies — the production equivalent lives in governance/masking_policies.sql.

    methods:
      email     -> mask the local part:  jane@x.com  ->  ****@x.com
      ip        -> fully redact:          ***.***.***.***
      null      -> NULL (varchar columns)
      null_int  -> NULL (integer columns)
      full      -> ***MASKED*** (default)
#}
{% macro mask(column, method='full') %}
    {%- if method == 'email' -%}
        regexp_replace({{ column }}, '^[^@]*', '****')
    {%- elif method == 'ip' -%}
        '***.***.***.***'
    {%- elif method == 'null' -%}
        cast(null as varchar)
    {%- elif method == 'null_int' -%}
        cast(null as integer)
    {%- else -%}
        '***MASKED***'
    {%- endif -%}
{% endmacro %}
