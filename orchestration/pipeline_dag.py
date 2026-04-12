"""
pipeline_dag.py

Prefect flow definitions for the full platform pipeline.

Each stage is a separate task — independently retryable, independently logged.
A failure in validation does not kill ingestion results.
A failure in one source does not kill other sources.

This is production pipeline discipline: fail loudly, fail specifically,
recover precisely.

Run locally:
    python orchestration/pipeline_dag.py --source all --mode demo
"""

import argparse
import logging
from datetime import datetime
from prefect import flow, task, get_run_logger
from prefect.task_runners import ConcurrentTaskRunner

from ingestion.multi_source_loader import run_ingestion, merge_results
from validation.data_contracts import DataContractEngine
from observability.lineage import LineageTracker
from observability.monitors import PipelineMonitor

logging.basicConfig(level=logging.INFO)


# ── Tasks ──────────────────────────────────────────────────────────────────────

@task(name="ingest-sources", retries=2, retry_delay_seconds=30)
def task_ingest(source_ids: list[str] | None = None):
    logger = get_run_logger()
    logger.info(f"Starting ingestion: sources={source_ids or 'all'}")
    results = run_ingestion(source_ids=source_ids)
    failed = [sid for sid, r in results.items() if not r.success]
    if failed:
        logger.warning(f"Sources failed ingestion: {failed}")
    return results


@task(name="validate-contracts")
def task_validate(ingestion_results: dict):
    logger = get_run_logger()
    engine = DataContractEngine()
    contract_results = {}

    for source_id, result in ingestion_results.items():
        if not result.success or result.data.empty:
            logger.warning(f"[{source_id}] Skipping validation — ingestion did not succeed")
            continue
        contract_result = engine.validate(source_id, result.data)
        contract_results[source_id] = contract_result
        if not contract_result.passed:
            logger.error(
                f"[{source_id}] Contract FAILED — "
                f"{contract_result.error_count} errors, {contract_result.warning_count} warnings"
            )

    return contract_results


@task(name="merge-and-stage")
def task_merge(ingestion_results: dict, contract_results: dict):
    logger = get_run_logger()

    # Only merge sources that passed contract validation
    clean_sources = {
        sid: result
        for sid, result in ingestion_results.items()
        if sid in contract_results and contract_results[sid].passed
    }

    if not clean_sources:
        logger.error("No sources passed contract validation — pipeline halted at merge stage")
        return None

    merged = merge_results(clean_sources)
    logger.info(f"Merged {len(merged):,} records from {len(clean_sources)} validated sources")
    return merged


@task(name="record-lineage")
def task_record_lineage(ingestion_results: dict, contract_results: dict, run_id: str):
    tracker = LineageTracker()
    for source_id, result in ingestion_results.items():
        tracker.record(
            source_id=source_id,
            run_id=run_id,
            records_in=result.records_fetched,
            contract_passed=contract_results.get(source_id, None) is not None
            and contract_results[source_id].passed,
            schema_version=result.schema_version,
            ingested_at=result.fetched_at,
        )


@task(name="run-monitors")
def task_monitor(ingestion_results: dict, contract_results: dict):
    monitor = PipelineMonitor()
    monitor.evaluate(ingestion_results, contract_results)


# ── Flow ───────────────────────────────────────────────────────────────────────

@flow(
    name="unified-data-platform-pipeline",
    task_runner=ConcurrentTaskRunner(),
    description="Full ingestion → validation → merge → lineage → monitoring pipeline",
)
def run_pipeline(
    source_ids: list[str] | None = None,
    mode: str = "production",
):
    logger = get_run_logger()
    run_id = f"run_{datetime.utcnow().strftime('%Y%m%d_%H%M%S')}"
    logger.info(f"Pipeline started: run_id={run_id} · mode={mode} · sources={source_ids or 'all'}")

    ingestion_results = task_ingest(source_ids)
    contract_results = task_validate(ingestion_results)
    merged_data = task_merge(ingestion_results, contract_results)
    task_record_lineage(ingestion_results, contract_results, run_id)
    task_monitor(ingestion_results, contract_results)

    logger.info(f"Pipeline complete: run_id={run_id}")
    return {
        "run_id": run_id,
        "sources_ingested": len(ingestion_results),
        "sources_validated": len(contract_results),
        "merge_successful": merged_data is not None,
    }


# ── CLI entry point ────────────────────────────────────────────────────────────

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Run the unified data platform pipeline")
    parser.add_argument("--source", nargs="+", default=None, help="Source IDs to run (default: all)")
    parser.add_argument("--mode", default="production", choices=["production", "demo"])
    args = parser.parse_args()

    result = run_pipeline(
        source_ids=args.source if args.source != ["all"] else None,
        mode=args.mode,
    )
    print(f"\nPipeline result: {result}")
