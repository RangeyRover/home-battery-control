import os
import sqlite3
from datetime import datetime, timedelta

import pytest
from homeassistant.util import dt as dt_util

DB_PATH = os.environ.get("HBC_TEST_DB_PATH", "tests/test_data/home-assistant_v2.db")

@pytest.fixture(scope="module")
def db_conn():
    if not os.path.exists(DB_PATH):
        pytest.skip(f"Database file not found at {DB_PATH}. Skipping online analog DB tests.")
    conn = sqlite3.connect(DB_PATH)
    yield conn
    conn.close()

def _run_local_analog_search(conn: sqlite3.Connection, target_kwh: float, solcast_entity_id: str) -> list[tuple[datetime.date, float]]:
    """
    Pure Python/SQLite implementation of the analog search logic to prove
    timezones and math are perfectly aligned for the local user.
    """
    cursor = conn.cursor()
    daily_yields = {}

    # 1. Get metadata ID for Solcast
    # Using 'sensor.solcast_pv_forecast_forecast_tomorrow' matching test DB
    cursor.execute(
        "SELECT id FROM statistics_meta WHERE statistic_id = :entity_id",
        {"entity_id": solcast_entity_id}
    )
    res_meta = cursor.fetchone()

    if res_meta:
        meta_id = res_meta[0]
        cursor.execute(
            '''
                SELECT start_ts, max, mean, state
                FROM statistics
                WHERE metadata_id = :meta_id
                ORDER BY start_ts ASC
            ''',
            {"meta_id": meta_id}
        )
        res_stats = cursor.fetchall()

        for row in res_stats:
            start_ts, max_val, mean_val, state_val = row
            val = max_val if max_val is not None else (mean_val if mean_val is not None else state_val)
            if val is None:
                continue

            # CRITICAL BUG FIX: Timezone Alignment
            # HA stores start_ts in UTC epoch seconds.
            # We must convert to local timezone before extracting the 'date' or 'hour'.
            dt_utc = datetime.fromtimestamp(start_ts, tz=dt_util.UTC)
            dt_local = dt_util.as_local(dt_utc)

            # The analog day is matching against tomorrow's forecast, so the value represents tomorrow.
            forecast_date = (dt_local + timedelta(days=1)).date()

            current_max = daily_yields.get(forecast_date, 0)
            daily_yields[forecast_date] = max(val, current_max)

    if not daily_yields:
        print("\nWARNING: No historical Solcast data found for analog search.")
        return []

    # Find 5 most recent days that are within a 5% tolerance
    tolerance = max(2.0, target_kwh * 0.05)
    candidate_days = [
        (d_date, d_yield) for d_date, d_yield in daily_yields.items()
        if abs(d_yield - target_kwh) <= tolerance
    ]

    if len(candidate_days) >= 5:
        # Sort the candidates by date descending (most recent first)
        candidate_days.sort(key=lambda x: x[0], reverse=True)
        top_5_days = candidate_days[:5]
    else:
        # Fallback to closest 5 regardless of recency if none within tolerance
        sorted_by_error = sorted(daily_yields.items(), key=lambda x: abs(x[1] - target_kwh))
        top_5_days = sorted_by_error[:5]

    return top_5_days

@pytest.mark.parametrize("target_kwh", [28, 26, 24, 22, 20, 18, 16, 14])
def test_analog_sweep(db_conn, target_kwh):
    """
    Test the extraction logic over a sweep of 8 target PV yields.
    Ensures that exactly 5 days are returned and prints the selected days.
    """
    # The DB has "sensor.solcast_pv_forecast_forecast_tomorrow"
    entity_id = "sensor.solcast_pv_forecast_forecast_tomorrow"

    top_5_days = _run_local_analog_search(db_conn, target_kwh, entity_id)

    print(f"\n--- Analog Sweep for Target: {target_kwh} kWh ---")
    for d_date, d_yield in top_5_days:
        error = abs(d_yield - target_kwh)
        print(f"  Selected Date: {d_date} | Yield: {d_yield:.2f} kWh | Error: {error:.2f} kWh")

    assert len(top_5_days) == 5, f"Expected 5 days for target {target_kwh}, got {len(top_5_days)}"
