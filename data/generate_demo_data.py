"""
data/generate_demo_data.py

Generates realistic aviation operations demo data for local development.

Run this once before running the pipeline:
    python data/generate_demo_data.py

Produces two CSV files that mirror the fragmented source pattern
this platform was built to solve:
  - aviation_operations.csv  (flight-level ops data, source A)
  - aviation_routes.csv      (route master data, source B)

The two sources use different identifiers for the same routes,
requiring the platform's canonical model to reconcile them which
is intentional. It demonstrates the fragmentation problem
concretely, not hypothetically.
"""

import pandas as pd
import numpy as np
import random
from pathlib import Path
from datetime import datetime, timedelta

SEED = 42
random.seed(SEED)
np.random.seed(SEED)

OUTPUT_DIR = Path(__file__).parent / "demo"
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)


ROUTES = [
    ("DXB", "LHR", "EK", "London Heathrow"),
    ("AUH", "JFK", "EY", "New York JFK"),
    ("DXB", "CDG", "EK", "Paris Charles de Gaulle"),
    ("AUH", "LHR", "EY", "London Heathrow"),
    ("DXB", "SIN", "EK", "Singapore Changi"),
    ("AUH", "SYD", "EY", "Sydney Kingsford Smith"),
    ("DXB", "BOM", "EK", "Mumbai Chhatrapati"),
    ("AUH", "DEL", "EY", "Delhi Indira Gandhi"),
    ("DXB", "NRT", "EK", "Tokyo Narita"),
    ("AUH", "DOH", "EY", "Doha Hamad"),
]

DELAY_CAUSES = ["carrier", "weather", "atc", "security", "aircraft_turnaround", None]
DELAY_CAUSE_WEIGHTS = [0.30, 0.20, 0.15, 0.05, 0.15, 0.15]


def generate_flight_ops(n_records: int = 2000) -> pd.DataFrame:
    """
    Generates flight-level operations records.
    Includes realistic delay distributions and intentional data quality
    issues (a small percentage of nulls, edge cases) to exercise contract validation.
    """
    records = []
    base_date = datetime(2024, 1, 1)

    for i in range(n_records):
        route = random.choice(ROUTES)
        origin, dest, airline, dest_name = route

        flight_date = base_date + timedelta(days=random.randint(0, 364))
        flight_number = f"{airline}{random.randint(100, 999)}"
        flight_id = f"{flight_number}_{flight_date.strftime('%Y%m%d')}"

        # Realistic delay distribution: most flights on time, long tail
        is_delayed = random.random() < 0.28
        if is_delayed:
            delay_minutes = int(np.random.exponential(scale=35))
            delay_minutes = min(delay_minutes, 480)
            status = "delayed"
            delay_cause = random.choices(DELAY_CAUSES, weights=DELAY_CAUSE_WEIGHTS)[0]
        else:
            delay_minutes = random.randint(-5, 5)
            status = "on_time"
            delay_cause = None

        # Small percentage cancelled
        if random.random() < 0.02:
            status = "cancelled"
            delay_minutes = 0
            delay_cause = random.choice(["weather", "carrier"])

        # Intentional data quality issues for contract testing (~2% of records)
        if random.random() < 0.01:
            flight_id = None   # triggers not_null contract violation
        if random.random() < 0.005:
            status = "unknown"  # triggers accepted_values violation

        records.append({
            "flight_id": flight_id,
            "flight_number": flight_number,
            "airline_iata": airline,
            "origin_iata": origin,
            "destination_iata": dest,
            "flight_date": flight_date.strftime("%Y-%m-%d"),
            "scheduled_departure": f"{random.randint(0,23):02d}:{random.choice(['00','15','30','45'])}",
            "departure_delay_minutes": delay_minutes,
            "flight_status": status,
            "delay_cause": delay_cause,
            "aircraft_type": random.choice(["B777", "A380", "B787", "A350", "A320"]),
        })

    df = pd.DataFrame(records)

    # Note: route_id in ops uses a different format than in routes master
    # This is the fragmentation problem — two sources, two identifier conventions
    df["route_id"] = df["origin_iata"] + "-" + df["destination_iata"]

    return df


def generate_routes_master() -> pd.DataFrame:
    """
    Generates the route master reference data.
    Note: route_id format here is origin_destination (underscore, not hyphen)
    This deliberate mismatch with ops data requires the transform layer to reconcile.
    """
    records = []
    for i, (origin, dest, airline, dest_name) in enumerate(ROUTES):
        records.append({
            "route_id": f"{origin}_{dest}",           # underscore — different from ops hyphen
            "route_code": f"{origin}-{dest}",          # human-readable alternate
            "origin_iata": origin,
            "destination_iata": dest,
            "primary_airline": airline,
            "destination_name": dest_name,
            "route_type": random.choice(["long_haul", "medium_haul", "short_haul"]),
            "region": random.choice(["Europe", "Americas", "Asia Pacific", "Middle East"]),
            "active": True,
        })
    return pd.DataFrame(records)


if __name__ == "__main__":
    print("Generating demo aviation data...")

    ops_df = generate_flight_ops(n_records=2000)
    ops_path = OUTPUT_DIR / "aviation_operations.csv"
    ops_df.to_csv(ops_path, index=False)
    print(f"  aviation_operations.csv — {len(ops_df):,} records → {ops_path}")

    routes_df = generate_routes_master()
    routes_path = OUTPUT_DIR / "aviation_routes.csv"
    routes_df.to_csv(routes_path, index=False)
    print(f"  aviation_routes.csv     — {len(routes_df):,} records → {routes_path}")

    print("\nData quality issues seeded (intentional, for contract validation demo):")
    null_ids = ops_df["flight_id"].isna().sum()
    bad_status = (~ops_df["flight_status"].isin(["on_time", "delayed", "cancelled", "diverted"])).sum()
    print(f"  ~{null_ids} null flight_ids")
    print(f"  ~{bad_status} invalid status values")
    print("\nRun the pipeline:")
    print("  python orchestration/pipeline_dag.py --source all --mode demo")
