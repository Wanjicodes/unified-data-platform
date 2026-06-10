# transform/

The dbt transform layer of the unified data platform.

This is where raw, validated source data becomes governed, decision-ready outputs.

## What this folder does

It applies the **staging → intermediate → marts** pattern to data that has already passed through the ingestion and validation layers of the pipeline. By the time data reaches dbt, it has been:

1. Pulled from source systems by the ingestion layer
2. Validated against data contracts in the validation layer
3. Lineage-tagged and version-stamped by the observability layer

dbt then takes that clean input and produces the trusted outputs the platform serves through its API.

## How to run it locally

From the `transform/` folder, with the project Python environment activated:

```bash
# Install dbt packages (only needed once)
dbt deps

# Compile and run all models
dbt run

# Run all tests (column tests, singular tests, custom assertions)
dbt test

# Build everything in one command (run + test)
dbt build

# Generate documentation site and open it in browser
dbt docs generate
dbt docs serve
```

## How the layers work

### `models/staging/`
**One model per source.** Light cleaning only — rename, type cast, remove obviously invalid rows. No business logic, no joins, no aggregation. Materialised as views.

### `models/intermediate/`
**Reusable building blocks.** Where business rules are applied (e.g. the OTP threshold of 15 minutes). Where sources are reconciled (e.g. matching the two route_id formats). Materialised as ephemeral — compiled into downstream models rather than persisted.

### `models/marts/`
**Decision-ready outputs.** Aggregated to a clear grain (e.g. one row per route per day). Get queried directly by dashboards and APIs. Every metric here corresponds to a definition in `config/metrics.yaml` — that registry is the source of truth, this layer is one of the places those definitions are physically computed.

## Why this structure matters

The staging-intermediate-marts pattern is the standard approach in production analytics engineering, and there are concrete reasons:

- **Lineage is obvious.** Anyone reading the code can see how a number was built — staging shows what the source looks like, intermediate shows the business rules, marts show the final aggregation.

- **Changes are local.** If a source column gets renamed, you change it in staging and downstream models keep working. If a business rule changes (e.g. the OTP threshold moves to 10 minutes), you change it in intermediate.

- **Testing happens at every layer.** Bugs get caught at the layer closest to where they originate, not after they've corrupted final outputs.

- **The same project moves to any warehouse.** This dbt project runs on DuckDB locally. It would run on Snowflake, BigQuery, or Postgres in production with only a profile change — the model code itself is portable.

## Files worth reading first

- `models/sources.yml` — explicit declarations of every raw source the project depends on
- `models/intermediate/int_flights_enriched.sql` — where most of the business logic lives
- `models/marts/mart_route_performance_daily.sql` — what a final output looks like
- `macros/calculate_otp_rate.sql` — example of encoding metric logic as reusable SQL
- `tests/assert_otp_rate_within_realistic_range.sql` — example of a custom data quality assertion
