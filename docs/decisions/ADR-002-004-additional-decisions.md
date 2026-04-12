# ADR-002: DuckDB over PostgreSQL for local transform

**Status**: Accepted  
**Date**: 2024-01

## Decision
Use DuckDB as the local OLAP engine for the transform layer, with dbt on top.

## Rationale
- **Zero infrastructure**: DuckDB runs in-process — no server, no connection management, no Docker dependency for local development
- **Columnar performance**: DuckDB is optimised for analytical queries (aggregations, window functions) — the transform layer's primary workload
- **dbt compatibility**: dbt supports DuckDB natively, so the transform layer can be migrated to Snowflake, BigQuery, or Redshift by changing the dbt profile — no SQL rewrites required
- **Reproducibility**: any contributor can clone the repo and run `dbt run` immediately, with no database setup

## Consequence
DuckDB is for development and moderate-scale production. If the platform exceeds ~50GB of processed data per run, evaluate migration to a cloud warehouse using the existing dbt project unchanged.

---

# ADR-003: Prefect over Airflow for orchestration

**Status**: Accepted  
**Date**: 2024-01

## Decision
Use Prefect for pipeline orchestration instead of Apache Airflow.

## Rationale
- **Setup overhead**: Airflow requires a metadata database, scheduler, webserver, and worker — typically 4+ services. Prefect runs with `prefect server start` or connects to Prefect Cloud with zero local infrastructure
- **Python-native**: Prefect flows are standard Python functions decorated with `@flow` and `@task` — no DAG DSL to learn, no templating language, no XCom workarounds
- **Dynamic flows**: Prefect handles dynamic task generation (e.g. one task per source) naturally. Airflow requires complex patterns to achieve the same
- **Stack versatility signal**: Most candidates default to Airflow. Using Prefect demonstrates that tool selection is based on requirements, not convention

## Consequence
Engineers familiar only with Airflow will have a short ramp-up. Prefect's documentation is comprehensive. The flow structure in `pipeline_dag.py` is intentionally readable for engineers from any orchestration background.

---

# ADR-004: Metric store separated from reporting layer

**Status**: Accepted  
**Date**: 2024-01

## Decision
Maintain a dedicated metric store (`config/metrics.yaml` + `MetricStore` class) that is the authoritative source of metric definitions, separate from any reporting or dashboard layer.

## Rationale
- **The core problem this platform solves** is fragmented, conflicting data definitions. A metric store is the structural solution to that problem — not a reporting convenience
- Without a metric store, metric definitions live in: dashboard filters, spreadsheet formulas, analyst notebooks, and verbal agreements. They diverge silently
- With a metric store, every metric has exactly one definition, one owner, and one version. Disagreements about what a number means are resolved by reading the store, not by escalating to a meeting
- The API's `/metrics/{name}` endpoint enforces this: if a metric is not in the store, it cannot be served. This creates the right incentive — register your metrics properly or they will not appear in outputs

## Consequence
Every new KPI must be added to `config/metrics.yaml` before it can be referenced in transformations or served via the API. This is intentional friction. Undocumented metrics are a data governance failure, not a data engineering shortcut.
