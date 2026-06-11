# Getting started on Windows

This guide walks you through running the platform locally on Windows.
No Docker required for the first run just Python and a terminal.

---

## Prerequisites

- Python 3.10 or higher ([python.org](https://python.org))
- Git ([git-scm.com](https://git-scm.com))
- A terminal: use **Command Prompt**, **PowerShell**, or **Windows Terminal**

---

## Step 1 — Clone the repo

```cmd
git clone https://github.com/yourusername/tessera-data-platform.git
cd tessera-data-platform
```

---

## Step 2 — Create a virtual environment

```cmd
python -m venv venv
venv\Scripts\activate
```

You should see `(venv)` in your terminal prompt.

---

## Step 3 — Install dependencies

```cmd
pip install -r requirements.txt
```

This installs: pandas, prefect, dbt-duckdb, fastapi, uvicorn, pytest, and all other dependencies.
First install takes 2–3 minutes.

---

## Step 4 — Generate demo data

```cmd
python data\generate_demo_data.py
```

Expected output:
```
Generating demo aviation data...
  aviation_operations.csv — 2,000 records → data/demo/aviation_operations.csv
  aviation_routes.csv     — 10 records    → data/demo/aviation_routes.csv
```

---

## Step 5 — Run the contract tests

```cmd
pytest tests\test_contracts.py -v
```

All tests should pass. This confirms the validation engine is working correctly.

---

## Step 6 — Run the pipeline

```cmd
set PYTHONPATH=.
python orchestration\pipeline_dag.py --source all --mode demo
```

Watch the structured logs — you will see each stage execute:
ingestion → validation → merge → lineage → monitoring.

Contract violations in the demo data are intentional — they demonstrate
the platform catching bad data before it reaches the transform layer.

---

## Step 7 — Start the API

```cmd
uvicorn serving.api:app --reload
```

Then open your browser:
- `http://localhost:8000/docs` — interactive API documentation
- `http://localhost:8000/metrics` — full metric registry
- `http://localhost:8000/health` — platform health status
- `http://localhost:8000/health/metrics-audit` — governance audit

---

## Step 8 — Generate dbt docs (optional)

```cmd
cd transform
dbt deps
dbt docs generate
dbt docs serve
```

Opens a browser with full data lineage documentation.

---

## Troubleshooting

**`ModuleNotFoundError`**: Make sure `PYTHONPATH` is set to the project root.
```cmd
set PYTHONPATH=.
```

**`FileNotFoundError` for demo data**: Run Step 4 first.

**`prefect` command not found**: Make sure your virtual environment is activated (`venv\Scripts\activate`).
