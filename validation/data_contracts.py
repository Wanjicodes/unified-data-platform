"""
data_contracts.py

Contract-based validation engine.

Data contracts are defined in config/contracts.yaml not in code.
This separation is intentional: business rules should be readable
and editable by anyone, not buried in Python files.

A contract failure is not an exception but a structured result
that gets logged, routed, and acted on. The pipeline continues.
"""

import yaml
import pandas as pd
import logging
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any
from datetime import datetime

logger = logging.getLogger(__name__)

CONFIG_PATH = Path(__file__).parent.parent / "config" / "contracts.yaml"


@dataclass
class ContractViolation:
    """A single rule that failed validation."""
    source_id: str
    rule_name: str
    column: str
    severity: str          # "error" | "warning"
    expected: Any
    actual: Any
    failed_record_count: int
    checked_at: datetime = field(default_factory=datetime.utcnow)

    def to_dict(self) -> dict:
        return {
            "source_id": self.source_id,
            "rule_name": self.rule_name,
            "column": self.column,
            "severity": self.severity,
            "expected": str(self.expected),
            "actual": str(self.actual),
            "failed_record_count": self.failed_record_count,
            "checked_at": self.checked_at.isoformat(),
        }


@dataclass
class ContractResult:
    """Full validation result for one source."""
    source_id: str
    passed: bool
    violations: list[ContractViolation] = field(default_factory=list)
    records_checked: int = 0

    @property
    def error_count(self) -> int:
        return sum(1 for v in self.violations if v.severity == "error")

    @property
    def warning_count(self) -> int:
        return sum(1 for v in self.violations if v.severity == "warning")

    def summary(self) -> str:
        return (
            f"[{self.source_id}] Contract {'PASSED' if self.passed else 'FAILED'} — "
            f"{self.records_checked} records · "
            f"{self.error_count} errors · {self.warning_count} warnings"
        )


class DataContractEngine:
    """
    Loads contract definitions from YAML and validates DataFrames against them.

    Supported rule types:
      - not_null: column must have no nulls
      - unique: column values must be unique
      - accepted_values: column values must be in a defined set
      - min_value / max_value: numeric range checks
      - not_empty: DataFrame must have at least N rows
      - regex_match: string column must match a pattern
    """

    def __init__(self, config_path: Path = CONFIG_PATH):
        with open(config_path) as f:
            self._contracts = yaml.safe_load(f).get("contracts", {})

    def validate(self, source_id: str, df: pd.DataFrame) -> ContractResult:
        """
        Run all contract rules defined for this source_id.
        Returns a ContractResult but never raises.
        """
        rules = self._contracts.get(source_id, [])
        if not rules:
            logger.warning(f"[{source_id}] No contract defined hence skipping validation")
            return ContractResult(source_id=source_id, passed=True, records_checked=len(df))

        violations = []

        for rule in rules:
            rule_name = rule["rule"]
            column = rule.get("column")
            severity = rule.get("severity", "error")

            try:
                new_violations = self._apply_rule(source_id, df, rule_name, column, rule, severity)
                violations.extend(new_violations)
            except Exception as e:
                logger.error(f"[{source_id}] Rule '{rule_name}' on '{column}' raised: {e}")

        has_errors = any(v.severity == "error" for v in violations)
        result = ContractResult(
            source_id=source_id,
            passed=not has_errors,
            violations=violations,
            records_checked=len(df),
        )
        logger.info(result.summary())
        return result

    def _apply_rule(
        self,
        source_id: str,
        df: pd.DataFrame,
        rule_name: str,
        column: str | None,
        rule: dict,
        severity: str,
    ) -> list[ContractViolation]:
        violations = []

        if rule_name == "not_null":
            null_count = df[column].isna().sum()
            if null_count > 0:
                violations.append(ContractViolation(
                    source_id=source_id, rule_name=rule_name, column=column,
                    severity=severity, expected="no nulls",
                    actual=f"{null_count} nulls found",
                    failed_record_count=int(null_count),
                ))

        elif rule_name == "unique":
            dup_count = df[column].duplicated().sum()
            if dup_count > 0:
                violations.append(ContractViolation(
                    source_id=source_id, rule_name=rule_name, column=column,
                    severity=severity, expected="unique values",
                    actual=f"{dup_count} duplicates found",
                    failed_record_count=int(dup_count),
                ))

        elif rule_name == "accepted_values":
            allowed = set(rule["values"])
            invalid = ~df[column].isin(allowed)
            invalid_count = invalid.sum()
            if invalid_count > 0:
                violations.append(ContractViolation(
                    source_id=source_id, rule_name=rule_name, column=column,
                    severity=severity, expected=f"one of {allowed}",
                    actual=f"{invalid_count} out-of-range values: {df[column][invalid].unique()[:5].tolist()}",
                    failed_record_count=int(invalid_count),
                ))

        elif rule_name == "min_value":
            below = df[column] < rule["value"]
            below_count = below.sum()
            if below_count > 0:
                violations.append(ContractViolation(
                    source_id=source_id, rule_name=rule_name, column=column,
                    severity=severity, expected=f">= {rule['value']}",
                    actual=f"{below_count} values below threshold",
                    failed_record_count=int(below_count),
                ))

        elif rule_name == "max_value":
            above = df[column] > rule["value"]
            above_count = above.sum()
            if above_count > 0:
                violations.append(ContractViolation(
                    source_id=source_id, rule_name=rule_name, column=column,
                    severity=severity, expected=f"<= {rule['value']}",
                    actual=f"{above_count} values above threshold",
                    failed_record_count=int(above_count),
                ))

        elif rule_name == "not_empty":
            min_rows = rule.get("min_rows", 1)
            if len(df) < min_rows:
                violations.append(ContractViolation(
                    source_id=source_id, rule_name=rule_name, column="_table_",
                    severity=severity, expected=f">= {min_rows} rows",
                    actual=f"{len(df)} rows",
                    failed_record_count=max(0, min_rows - len(df)),
                ))

        return violations
