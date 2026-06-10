-- models/intermediate/int_flights_enriched.sql
--
-- INTERMEDIATE LAYER
-- ==================
-- Purpose: Apply business logic, join sources, prepare data for marts.
--
-- What intermediate models DO:
--   - Join staging models together
--   - Apply business rules (e.g. "a flight is 'on time' if delay <= 15 min")
--   - Build reusable building blocks used by multiple marts
--   - Reconcile differences between source systems
--
-- What intermediate models DO NOT DO:
--   - Aggregate to final reporting grain
--   - Calculate KPIs that go directly to dashboards
--   - Get queried by end users
--
-- Materialisation: 'ephemeral' — dbt compiles this model INTO downstream models
-- as a CTE rather than creating a table or view. This keeps the warehouse clean
-- and signals that this is a transformation step, not a final output.
--
-- The key business logic in this model:
--   1. Reconcile the route_id mismatch between operations and routes systems
--   2. Add the canonical 'is_on_time' flag using a 15-minute threshold
--   3. Categorise delay severity into bands

with operations as (

    select * from {{ ref('stg_aviation_operations') }}

),

routes as (

    select * from {{ ref('stg_aviation_routes') }}

),

joined as (

    select
        ops.flight_id,
        ops.flight_number,
        ops.airline_code,
        ops.origin_iata,
        ops.destination_iata,
        ops.flight_date,
        ops.scheduled_departure_time,
        ops.departure_delay_minutes,
        ops.flight_status,
        ops.delay_cause,
        ops.aircraft_type,

        -- Route enrichment from master data
        ops.ops_route_id as route_id,
        routes.route_type,
        routes.region as destination_region,
        routes.destination_name,

        -- Data quality flag — flights without a route master entry indicate
        -- either a new route not yet registered, or a data quality issue
        case
            when routes.routes_route_id is null then true
            else false
        end as is_unmapped_route

    from operations as ops
    left join routes
        on ops.ops_route_id = routes.ops_route_id

),

with_business_logic as (

    select
        *,

        -- Industry-standard OTP definition: on time = within 15 minutes of schedule
        -- This is the SINGLE PLACE this rule is defined.
        -- All downstream metrics that mention 'on time' must reference this.
        case
            when flight_status = 'cancelled' then null
            when departure_delay_minutes <= 15 then true
            else false
        end as is_on_time,

        -- Delay severity bands
        case
            when flight_status = 'cancelled' then 'cancelled'
            when departure_delay_minutes <= 15 then 'on_time'
            when departure_delay_minutes <= 60 then 'minor_delay'
            when departure_delay_minutes <= 180 then 'significant_delay'
            else 'severe_delay'
        end as delay_severity_band,

        -- Carrier-attributable delay flag (used for accountability metrics)
        case
            when delay_cause in ('carrier', 'aircraft_turnaround') then true
            when delay_cause in ('weather', 'atc', 'security') then false
            else null
        end as is_carrier_attributable

    from joined

)

select * from with_business_logic
