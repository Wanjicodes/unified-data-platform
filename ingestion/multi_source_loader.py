"""
multi_source_loader.py

Orchestrates ingestion across multiple sources in parallel.
Sources are defined in config/sources.yaml — adding a new source
requires no code changes, only a config entry and a connector class.
"""

import yaml
import importlib
import pandas as pd
import logging
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path
from typing import Optional

from ingestion.base_connector import BaseConnector, IngestionResult

logger = logging.getLogger(__name__)

CONFIG_PATH = Path(__file__).parent.parent / "config" / "sources.yaml"


def load_sources_config(config_path: Path = CONFIG_PATH) -> dict:
    with open(config_path) as f:
        return yaml.safe_load(f)


def resolve_connector(connector_class_path: str) -> type[BaseConnector]:
    """
    Dynamically load a connector class from its dotted path string.
    e.g. 'ingestion.connectors.csv_connector.CsvConnector'
    """
    module_path, class_name = connector_class_path.rsplit(".", 1)
    module = importlib.import_module(module_path)
    return getattr(module, class_name)


def run_ingestion(
    source_ids: Optional[list[str]] = None,
    max_workers: int = 4,
) -> dict[str, IngestionResult]:
    """
    Run ingestion for all configured sources (or a subset).
    Returns a dict of source_id → IngestionResult.

    Failures are captured per-source — one bad source does not
    stop ingestion for the rest. This is intentional.
    """
    config = load_sources_config()
    sources = config.get("sources", {})

    if source_ids:
        sources = {k: v for k, v in sources.items() if k in source_ids}

    if not sources:
        raise ValueError("No sources matched. Check config/sources.yaml.")

    results: dict[str, IngestionResult] = {}

    def _run_single(source_id: str, source_config: dict) -> tuple[str, IngestionResult]:
        connector_class = resolve_connector(source_config["connector"])
        connector = connector_class(source_id=source_id, config=source_config)
        return source_id, connector.run()

    with ThreadPoolExecutor(max_workers=max_workers) as executor:
        futures = {
            executor.submit(_run_single, sid, scfg): sid
            for sid, scfg in sources.items()
        }
        for future in as_completed(futures):
            source_id = futures[future]
            try:
                sid, result = future.result()
                results[sid] = result
                status = "OK" if result.success else "FAILED"
                logger.info(f"[{sid}] {status} — {result.records_fetched} records")
            except Exception as e:
                logger.error(f"[{source_id}] Unexpected error: {e}")

    _log_ingestion_summary(results)
    return results


def merge_results(results: dict[str, IngestionResult]) -> pd.DataFrame:
    """
    Combine successful ingestion results into a single DataFrame.
    Adds source_id column for downstream lineage tracking.
    """
    frames = []
    for source_id, result in results.items():
        if result.success and not result.data.empty:
            df = result.data.copy()
            df["_source_id"] = source_id
            df["_ingested_at"] = result.fetched_at
            df["_schema_version"] = result.schema_version
            frames.append(df)

    if not frames:
        logger.warning("No successful ingestion results to merge.")
        return pd.DataFrame()

    return pd.concat(frames, ignore_index=True)


def _log_ingestion_summary(results: dict[str, IngestionResult]) -> None:
    total = len(results)
    succeeded = sum(1 for r in results.values() if r.success)
    total_records = sum(r.records_fetched for r in results.values() if r.success)
    logger.info(
        f"Ingestion summary: {succeeded}/{total} sources succeeded · "
        f"{total_records:,} total records loaded"
    )
