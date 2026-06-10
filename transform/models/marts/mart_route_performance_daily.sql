-- models/marts/mart_route_performance_daily.sql
--
-- MART LAYER
-- ==========
-- Purpose: Decision-ready outputs aggregated to the grain that decisions are made at.
--
-- What mart models DO:
--   - Aggregate to a clear, named grain (here: one row per route per day)
--   - Calculate the metrics defined in the metric store
--   - Get queried directly by dashboards, APIs, and analysts
--   - Stand alone — fully understandable without needing to read upstream models
--
-- What mart models DO NOT DO:
--   - Apply business rules that aren't in the metric store
--   - Get joined together to create new metrics on the fly (that's a sign you need
--     a new mart, or a new intermediate)
--
-- Materialisation: 'table' — dbt creates a physical table that's fast to query.
--
-- Naming convention: mart_<subject>_<grain>
--   - subject: route_performance
--   - grain: daily
--
-- Every metric calculated here corresponds to a metric registered in
-- config/metrics.yaml — that registry is the source of truth for definitions,
-- and this model is one of the places where those definitions are physically computed.

with flights as (

    select * from {{ ref('int_flights_enriched') }}

),

aggregated as (

    select
        flight_date,
        route_id,
        origin_iata,
        destination_iata,
        destination_region,

        -- Volume metrics
        count(*) as total_flights,
        count_if(flight_status = 'cancelled') as cancelled_flights,
        count_if(flight_status != 'cancelled') as operated_flights,

        -- On-time performance — references metric: on_time_performance_rate
        -- Definition: % of operated flights with delay <= 15 min
        round(
            100.0 * count_if(is_on_time = true)::float
            / nullif(count_if(flight_status != 'cancelled'), 0),
            2
        ) as on_time_performance_rate,

        -- Average delay — references metric: average_delay_minutes
        -- Definition: mean delay across delayed flights only (delay > 0)
        round(
            avg(case when departure_delay_minutes > 0 then departure_delay_minutes end),
            1
        ) as average_delay_minutes,

        -- Delay attribution — references metric: delay_attribution_rate
        -- Definition: % of delay events caused by carrier vs external factors
        round(
            100.0 * count_if(is_carrier_attributable = true)::float
            / nullif(count_if(is_carrier_attributable is not null), 0),
            2
        ) as carrier_caused_delay_rate,

        -- Severity distribution
        count_if(delay_severity_band = 'minor_delay') as minor_delay_flights,
        count_if(delay_severity_band = 'significant_delay') as significant_delay_flights,
        count_if(delay_severity_band = 'severe_delay') as severe_delay_flights,

        -- Data quality signal — should be 0 in clean data
        count_if(is_unmapped_route = true) as unmapped_route_flights

    from flights
    group by 1, 2, 3, 4, 5

)

select * from aggregated
