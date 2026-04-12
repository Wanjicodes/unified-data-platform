"""
observability/monitors.py

Pipeline health monitors.

Evaluates ingestion and validation results after each run
and produces a structured health report. Designed to plug into
alerting systems (Slack, email, PagerDuty) without coupling
the pipeline to any specific notification tool.
"""

import logging
from dataclasses import dataclass, field
from datetime import datetime

logger = logging.getLogger(__name__)


@dataclass
class PipelineHealthReport:
    run_id: str
    evaluated_at: datetime
    total_sources: int
    ingestion_failures: list[str]
    contract_failures: list[str]
    warnings: list[str]
    overall_status: str       # "healthy" | "degraded" | "failed"

    def to_dict(self) -> dict:
        return {
            "run_id": self.run_id,
            "evaluated_at": self.evaluated_at.isoformat(),
            "total_sources": self.total_sources,
            "ingestion_failures": self.ingestion_failures,
            "contract_failures": self.contract_failures,
            "warnings": self.warnings,
            "overall_status": self.overall_status,
        }

    def log_summary(self) -> None:
        logger.info(
            f"[Monitor] Pipeline health: {self.overall_status.upper()} — "
            f"{self.total_sources} sources · "
            f"{len(self.ingestion_failures)} ingestion failures · "
            f"{len(self.contract_failures)} contract failures"
        )
        for w in self.warnings:
            logger.warning(f"[Monitor] {w}")


class PipelineMonitor:
    """
    Post-run health evaluator.

    Design principle: monitoring logic lives here, not scattered
    across pipeline tasks. The pipeline runs; the monitor judges.
    """

    def evaluate(
        self,
        ingestion_results: dict,
        contract_results: dict,
        run_id: str = "unknown",
    ) -> PipelineHealthReport:

        ingestion_failures = [
            sid for sid, r in ingestion_results.items() if not r.success
        ]
        contract_failures = [
            sid for sid, r in contract_results.items() if not r.passed
        ]
        warnings = []

        # Warn if any source had zero records
        for sid, result in ingestion_results.items():
            if result.success and result.records_fetched == 0:
                warnings.append(f"[{sid}] Ingested successfully but returned 0 records")

        # Warn if contract warnings exist even on passing sources
        for sid, result in contract_results.items():
            if result.passed and result.warning_count > 0:
                warnings.append(
                    f"[{sid}] Contract passed with {result.warning_count} warning(s) — review before next run"
                )

        # Determine overall status
        if ingestion_failures or contract_failures:
            overall_status = "failed" if ingestion_failures else "degraded"
        elif warnings:
            overall_status = "degraded"
        else:
            overall_status = "healthy"

        report = PipelineHealthReport(
            run_id=run_id,
            evaluated_at=datetime.utcnow(),
            total_sources=len(ingestion_results),
            ingestion_failures=ingestion_failures,
            contract_failures=contract_failures,
            warnings=warnings,
            overall_status=overall_status,
        )
        report.log_summary()
        return report
