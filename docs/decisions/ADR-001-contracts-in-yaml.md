# ADR-001: Data contracts defined in YAML, not enforced in code

**Status**: Accepted  
**Date**: 2024-01  
**Author**: Platform Engineering

---

## Context

When building validation logic for multi-source data platforms, there are two common approaches:

1. **Code-first**: validation rules written as Python functions or class methods
2. **Config-first**: validation rules written as YAML, loaded and executed by a rule engine

The choice has significant implications for maintainability, governance, and team access.

---

## Decision

Data contracts in this platform are defined in `config/contracts.yaml` and executed by the `DataContractEngine` class. No validation logic is written directly in Python files.

---

## Rationale

**1. Business rules should be readable without code context.**  
A data analyst or product owner should be able to read `contracts.yaml` and understand exactly what validation is applied to each source. Python validation code requires understanding the codebase to interpret.

**2. Adding a rule should not require a deployment.**  
In code-first validation, adding a new check (e.g. "this column must be non-null") requires a code change, review, and deployment. In config-first, it requires editing a YAML file. For a platform serving multiple enterprise clients, this matters.

**3. YAML contracts are version-controllable as governance artifacts.**  
A commit history of `contracts.yaml` is a governance audit log — it shows when rules were added, changed, or relaxed, and who approved each change.

**4. Separation of concerns.**  
The `DataContractEngine` class handles *how* to run rules. The YAML file defines *which* rules to run. These are different responsibilities and should live in different places.

---

## Consequences

- All new validation rules must be expressible in the supported rule types (`not_null`, `unique`, `accepted_values`, `min_value`, `max_value`, `not_empty`, `regex_match`)
- Complex cross-column or statistical validation that cannot be expressed in simple rules requires extending the `DataContractEngine` rule library — this is intentional friction that keeps contracts simple
- The YAML schema for contracts must be documented and versioned

---

## Alternatives considered

**Great Expectations**: Considered but rejected for the initial implementation — GE introduces significant infrastructure overhead (data docs site, expectation stores) that is disproportionate for the platform's current scope. The contract engine is designed to be replaceable with GE at a later stage if scale requires it.

**Pandera**: A strong option for DataFrame-level schema validation. May be incorporated as the schema validation layer beneath the contract engine in a future version.
