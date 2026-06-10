-- models/staging/stg_aviation_operations.sql
--
-- STAGING LAYER
-- =============
-- Purpose: Take raw source data and clean it just enough to be usable.
--
-- What staging models DO:
--   - Rename columns to a consistent naming convention
--   - Cast types explicitly
--   - Filter out clearly invalid rows (e.g. obvious test data)
--   - Apply minimal cleaning (trim whitespace, standardise case)
--
-- What staging models DO NOT DO:
--   - Join to other tables
--   - Apply business logic
--   - Aggregate
--   - Calculate metrics
--
-- The rule: one source → one staging model. This keeps lineage clean and
-- makes it obvious where any transformation originates.
--
-- The 'config' block at the top can override defaults from dbt_project.yml.
-- Here we leave it as a view (default for staging) — fast, always fresh.

with source as (

    select * from {{ source('raw_aviation', 'aviation_operations') }}

),

renamed_and_typed as (

    select
        -- Identifiers
        flight_id,
        flight_number,
        airline_iata as airline_code,

        -- Route info — note we KEEP the source format here, reconciliation happens later
        origin_iata,
        destination_iata,
        route_id as ops_route_id,

        -- Timing
        cast(flight_date as date) as flight_date,
        scheduled_departure as scheduled_departure_time,
        cast(departure_delay_minutes as integer) as departure_delay_minutes,

        -- Status & delay attribution
        lower(trim(flight_status)) as flight_status,
        lower(trim(coalesce(delay_cause, 'none'))) as delay_cause,

        -- Aircraft
        aircraft_type

    from source

    -- Filter rows that should never reach downstream models
    -- Note: contract validation already catches these — this is defence in depth
    where flight_id is not null

)

select * from renamed_and_typed
