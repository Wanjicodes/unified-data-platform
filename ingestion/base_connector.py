"""
base_connector.py

Abstract base class for all data source connectors.
Every source — regardless of type — implements this interface.
This is the contract that makes multi-source ingestion composable.
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any
import pandas as pd
import logging

logger = logging.getLogger(__name__)


@dataclass
class IngestionResult:
    """Structured result from any connector run."""
    source_id: str
    records_fetched: int
    schema_version: str
    fetched_at: datetime
    success: bool
    data: pd.DataFrame
    errors: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_log_dict(self) -> dict:
        return {
            "source_id": self.source_id,
            "records_fetched": self.records_fetched,
            "schema_version": self.schema_version,
            "fetched_at": self.fetched_at.isoformat(),
            "success": self.success,
            "error_count": len(self.errors),
            "warning_count": len(self.warnings),
        }


class BaseConnector(ABC):
    """
    Abstract connector interface.

    All source connectors — CSV, API, database, flat file —
    implement this interface so the pipeline layer never needs
    to know what it is pulling from.

    Design principle: swap sources without touching pipeline logic.
    """

    def __init__(self, source_id: str, config: dict):
        self.source_id = source_id
        self.config = config
        self._validate_config()

    @abstractmethod
    def _validate_config(self) -> None:
        """Raise ValueError if required config keys are missing."""
        pass

    @abstractmethod
    def fetch(self) -> pd.DataFrame:
        """
        Pull raw data from the source.
        Returns a DataFrame. Never transforms — that is the transform layer's job.
        """
        pass

    @abstractmethod
    def get_schema_version(self) -> str:
        """
        Return the current schema version string for this source.
        Used by the schema registry to detect upstream changes.
        """
        pass

    def run(self) -> IngestionResult:
        """
        Execute the full ingestion cycle with structured logging.
        Call this — not fetch() — from the pipeline.
        """
        started_at = datetime.utcnow()
        errors = []
        warnings = []

        try:
            logger.info(f"[{self.source_id}] Starting ingestion")
            df = self.fetch()
            schema_version = self.get_schema_version()

            if df.empty:
                warnings.append("Source returned zero records — check source availability")

            result = IngestionResult(
                source_id=self.source_id,
                records_fetched=len(df),
                schema_version=schema_version,
                fetched_at=started_at,
                success=True,
                data=df,
                warnings=warnings,
            )
            logger.info(f"[{self.source_id}] Ingestion complete: {result.to_log_dict()}")
            return result

        except Exception as e:
            logger.error(f"[{self.source_id}] Ingestion failed: {str(e)}")
            errors.append(str(e))
            return IngestionResult(
                source_id=self.source_id,
                records_fetched=0,
                schema_version="unknown",
                fetched_at=started_at,
                success=False,
                data=pd.DataFrame(),
                errors=errors,
            )
