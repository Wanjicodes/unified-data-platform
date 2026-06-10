-- macros/calculate_otp_rate.sql
--
-- Custom macros are reusable SQL functions that compile into your models.
-- They are the dbt equivalent of writing a Python function once and
-- calling it from many places.
--
-- This macro encapsulates the on-time performance calculation logic so
-- if the OTP definition ever changes (e.g. industry moves to a 10-minute
-- threshold), it gets updated in ONE place.
--
-- Usage in a model:
--   select route_id, {{ calculate_otp_rate('is_on_time', 'flight_status') }} as otp_rate
--
-- This pattern is how you implement governance at the SQL layer:
--   metric definitions live in a macro library, models call the macros,
--   and changing the definition is a small, safe diff rather than a
--   search-and-replace across dozens of files.

{% macro calculate_otp_rate(otp_flag_column, status_column) %}

    round(
        100.0 * count_if({{ otp_flag_column }} = true)::float
        / nullif(count_if({{ status_column }} != 'cancelled'), 0),
        2
    )

{% endmacro %}
