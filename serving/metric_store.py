"""
metric_store.py

The metric store is the authoritative registry of every KPI in the platform.

Each metric has:
  - A unique name
  - An owner (team or person accountable for its definition)
  - A calculation definition
  - Thresholds for alerting
  - A refresh cadence
  - A version (definitions change — this tracks when and why)

This is not a reporting layer. This is a governance layer.
The metric store answers: "What does this number mean, who owns it,
and how was it calculated?" — questions that fragmented data environments
can never answer without it.
"""

import yaml
import logging
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional
import pandas as pd

logger = logging.getLogger(__name__)

CONFIG_PATH = Path(__file__).parent.parent / "config" / "metrics.yaml"


@dataclass
class MetricDefinition:
    name: str
    display_name: str
    owner: str
    description: str
    calculation: str          # Human-readable formula or SQL expression
    unit: str                 # e.g. "percentage", "count", "currency_aed"
    refresh_cadence: str      # e.g. "daily", "weekly"
    version: str
    thresholds: dict = field(default_factory=dict)
    tags: list[str] = field(default_factory=list)
    notes: str = ""

    def to_dict(self) -> dict:
        return {
            "name": self.name,
            "display_name": self.display_name,
            "owner": self.owner,
            "description": self.description,
            "calculation": self.calculation,
            "unit": self.unit,
            "refresh_cadence": self.refresh_cadence,
            "version": self.version,
            "thresholds": self.thresholds,
            "tags": self.tags,
            "notes": self.notes,
        }


class MetricStore:
    """
    Loads metric definitions from config/metrics.yaml and provides
    a governed interface for querying and listing metrics.

    Why a metric store?
    In fragmented environments, the same metric gets defined
    differently in different places — finance calculates retention
    differently from marketing, and both differ from ops.
    The metric store makes one definition the authority.
    """

    def __init__(self, config_path: Path = CONFIG_PATH):
        self._metrics: dict[str, MetricDefinition] = {}
        self._load(config_path)

    def _load(self, config_path: Path) -> None:
        with open(config_path) as f:
            raw = yaml.safe_load(f)

        for m in raw.get("metrics", []):
            defn = MetricDefinition(
                name=m["name"],
                display_name=m["display_name"],
                owner=m["owner"],
                description=m["description"],
                calculation=m["calculation"],
                unit=m["unit"],
                refresh_cadence=m["refresh_cadence"],
                version=m.get("version", "1.0.0"),
                thresholds=m.get("thresholds", {}),
                tags=m.get("tags", []),
                notes=m.get("notes", ""),
            )
            self._metrics[defn.name] = defn

        logger.info(f"MetricStore loaded {len(self._metrics)} metric definitions")

    def get(self, metric_name: str) -> Optional[MetricDefinition]:
        metric = self._metrics.get(metric_name)
        if not metric:
            logger.warning(f"MetricStore: '{metric_name}' not found — is it defined in metrics.yaml?")
        return metric

    def list_all(self) -> list[MetricDefinition]:
        return list(self._metrics.values())

    def list_by_tag(self, tag: str) -> list[MetricDefinition]:
        return [m for m in self._metrics.values() if tag in m.tags]

    def list_by_owner(self, owner: str) -> list[MetricDefinition]:
        return [m for m in self._metrics.values() if m.owner == owner]

    def to_dataframe(self) -> pd.DataFrame:
        """Export the full metric registry as a DataFrame — useful for audits."""
        return pd.DataFrame([m.to_dict() for m in self._metrics.values()])

    def validate_metric_exists(self, metric_name: str) -> bool:
        """
        Use this in pipeline validation to assert that any metric
        referenced in a report or dashboard is actually registered.
        Unregistered metrics are a data governance failure.
        """
        exists = metric_name in self._metrics
        if not exists:
            logger.error(
                f"Metric '{metric_name}' is referenced but not registered in the metric store. "
                f"This is a governance violation — add it to config/metrics.yaml."
            )
        return exists
