"""
ingestion/schema_registry.py

Schema registry — tracks source schema versions across pipeline runs.

When a source schema changes (columns added, renamed, or removed),
the registry detects the drift and logs it before it can silently
break downstream transformations.

This is a lightweight implementation. At scale, replace the JSON
file store with a database table or a dedicated schema registry
service (e.g. Confluent Schema Registry for event-driven pipelines).
"""

import json
import logging
from datetime import datetime
from pathlib import Path
from typing import Optional

logger = logging.getLogger(__name__)

REGISTRY_PATH = Path("observability/schema_registry.json")


class SchemaRegistry:
    """
    Stores the last-known schema version per source and flags changes.

    A schema change is not necessarily an error — sources change.
    But a silent schema change that breaks a pipeline is a failure.
    The registry makes schema changes loud, not silent.
    """

    def __init__(self, registry_path: Path = REGISTRY_PATH):
        self.registry_path = registry_path
        self.registry_path.parent.mkdir(parents=True, exist_ok=True)
        self._store: dict = self._load()

    def _load(self) -> dict:
        if self.registry_path.exists():
            with open(self.registry_path) as f:
                return json.load(f)
        return {}

    def _save(self) -> None:
        with open(self.registry_path, "w") as f:
            json.dump(self._store, f, indent=2, default=str)

    def check_and_update(self, source_id: str, current_version: str) -> dict:
        """
        Compare the current schema version against the registered version.
        Updates the registry and returns a change report.

        Returns:
            {
                "source_id": str,
                "status": "new" | "unchanged" | "changed",
                "previous_version": str | None,
                "current_version": str,
                "changed_at": str | None,
            }
        """
        existing = self._store.get(source_id)

        if existing is None:
            # First time seeing this source
            self._store[source_id] = {
                "version": current_version,
                "first_seen": datetime.utcnow().isoformat(),
                "last_seen": datetime.utcnow().isoformat(),
                "change_history": [],
            }
            self._save()
            logger.info(f"[SchemaRegistry] New source registered: {source_id} @ {current_version}")
            return {
                "source_id": source_id,
                "status": "new",
                "previous_version": None,
                "current_version": current_version,
                "changed_at": None,
            }

        previous_version = existing["version"]

        if current_version == previous_version:
            self._store[source_id]["last_seen"] = datetime.utcnow().isoformat()
            self._save()
            return {
                "source_id": source_id,
                "status": "unchanged",
                "previous_version": previous_version,
                "current_version": current_version,
                "changed_at": None,
            }

        # Schema changed
        changed_at = datetime.utcnow().isoformat()
        self._store[source_id]["change_history"].append({
            "from_version": previous_version,
            "to_version": current_version,
            "detected_at": changed_at,
        })
        self._store[source_id]["version"] = current_version
        self._store[source_id]["last_seen"] = changed_at
        self._save()

        logger.warning(
            f"[SchemaRegistry] SCHEMA CHANGE DETECTED: {source_id} "
            f"{previous_version} → {current_version}. "
            f"Review transform/staging models for this source."
        )
        return {
            "source_id": source_id,
            "status": "changed",
            "previous_version": previous_version,
            "current_version": current_version,
            "changed_at": changed_at,
        }

    def get_history(self, source_id: str) -> Optional[dict]:
        return self._store.get(source_id)

    def list_all(self) -> dict:
        return self._store
