import os
import sqlite3
from unittest.mock import MagicMock

import pytest
from custom_components.house_battery_control.rates_predictor import SyntheticRatesPredictor

DB_PATH = os.environ.get("HBC_TEST_DB_PATH", "tests/test_data/home-assistant_v2.db")

class MockResult:
    def __init__(self, rows):
        self._rows = rows
    def fetchall(self):
        return self._rows
    def fetchone(self):
        return self._rows[0] if self._rows else None

class MockConnection:
    def __init__(self, sqlite_conn):
        self.sqlite_conn = sqlite_conn

    def execute(self, stmt, params=None):
        cur = self.sqlite_conn.cursor()
        # sqlalchemy text() wrappers have .text attribute
        query = stmt.text if hasattr(stmt, "text") else str(stmt)
        # convert named parameters to tuple or dict if needed, but for our simple tests we might pass them as dict
        if params is None:
            params = {}
        # Actually sqlalchemy execution usually expects dict params, e.g. execute(text("..."), {"a": 1})
        # sqlite3 executes can take a dict for named parameters: :a
        cur.execute(query, params)
        return MockResult(cur.fetchall())

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        pass

class MockEngine:
    def __init__(self, sqlite_conn):
        self.sqlite_conn = sqlite_conn

    def connect(self):
        return MockConnection(self.sqlite_conn)

@pytest.fixture(scope="module")
def db_conn():
    if not os.path.exists(DB_PATH):
        pytest.skip(f"Database file not found at {DB_PATH}. Skipping online analog DB tests.")
    conn = sqlite3.connect(DB_PATH)
    yield conn
    conn.close()

@pytest.fixture
def mock_hass(db_conn):
    hass = MagicMock()
    # Mock recorder get_instance
    recorder_instance = MagicMock()
    recorder_instance.engine = MockEngine(db_conn)

    # We patch homeassistant.components.recorder.get_instance
    return hass, recorder_instance

@pytest.mark.parametrize("target_kwh", [28, 26, 24, 22, 20, 18, 16, 14])
def test_online_analog_db_search(mock_hass, target_kwh, monkeypatch):
    hass, recorder_instance = mock_hass

    # Patch get_instance
    import custom_components.house_battery_control.rates_predictor as rp
    monkeypatch.setattr(rp, "get_instance", lambda h: recorder_instance, raising=False)
    monkeypatch.setattr(rp.history, "get_significant_states", lambda hass, start, end, entity_ids=None: {}, raising=False)

    predictor = SyntheticRatesPredictor(
        hass,
        solcast_entity_id="sensor.solcast_pv_forecast_forecast_today",
        import_price_entity_id="sensor.amber_general_price",
        export_price_entity_id="sensor.amber_feed_in_price",
        load_entity_id="sensor.powerwall_load_export"
    )

    # execute the blocking call directly as this runs in the executor usually
    results = predictor._run_analog_search(target_kwh)

    assert len(results) == 5
    for day in results:
        assert len(day.pricing_curve) == 288
        assert len(day.export_curve) == 288
        assert len(day.load_curve) == 288
