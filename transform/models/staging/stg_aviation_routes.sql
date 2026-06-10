-- models/staging/stg_aviation_routes.sql
--
-- Staging model for the routes master data.
-- Same rules as the operations staging model: rename, cast, light cleaning, no logic.
--
-- The key thing this model does is normalise the route_id format.
-- The source uses 'XXX_YYY' (underscore) but the operations data uses 'XXX-YYY' (hyphen).
-- We expose BOTH in this staging model so the reconciliation logic in the intermediate
-- layer can join cleanly.
--
-- This is a deliberate pattern: when sources disagree, surface the disagreement explicitly
-- rather than hiding it in a transformation. Future engineers reading this code will
-- understand exactly why two formats exist.

with source as (

    select * from {{ source('raw_aviation', 'aviation_routes') }}

),

renamed_and_typed as (

    select
        -- Original identifier from source (XXX_YYY format)
        route_id as routes_route_id,

        -- Normalised identifier matching ops data format (XXX-YYY format)
        -- This is the key reconciliation column for downstream joins
        replace(route_id, '_', '-') as ops_route_id,

        -- Human-readable route code
        route_code,

        -- Route components
        origin_iata,
        destination_iata,

        -- Metadata
        primary_airline as airline_code,
        destination_name,
        route_type,
        region,

        -- Status
        active

    from source

)

select * from renamed_and_typed
