-- tests/assert_otp_rate_within_realistic_range.sql
--
-- A 'singular test' in dbt is a SQL query that returns rows when a test FAILS.
-- If the query returns zero rows, the test passes.
--
-- Singular tests are for assertions that don't fit the standard column-level
-- tests (unique, not_null, accepted_values). They're how you encode
-- business-level data quality rules.
--
-- This test asserts that OTP rates are within a sane realistic range.
-- An OTP of 102% or -5% would indicate a calculation bug, not a real-world
-- data point. Catching these in CI prevents bad numbers from reaching dashboards.

select
    flight_date,
    route_id,
    on_time_performance_rate

from {{ ref('mart_route_performance_daily') }}

where
    on_time_performance_rate < 0
    or on_time_performance_rate > 100
