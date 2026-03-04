"""Tests for the historical_analyzer module — temperature-correlated load (017)."""

from datetime import datetime, timezone

from custom_components.house_battery_control.historical_analyzer import (
    build_historical_profile,
    extract_temp_data,
)

# --- T003: extract_temp_data tests ---


class TestExtractTempData:
    """Test extract_temp_data() — reads temperature from weather entity history."""

    def test_reads_attributes_temperature(self):
        """Weather entities store temperature in attributes.temperature."""
        history = [
            {
                "state": "sunny",
                "last_changed": "2025-02-20T12:00:00+00:00",
                "attributes": {"temperature": 28.5},
            },
            {
                "state": "cloudy",
                "last_changed": "2025-02-20T13:00:00+00:00",
                "attributes": {"temperature": 25.0},
            },
        ]
        result = extract_temp_data(history)
        assert len(result) == 2
        assert result[0]["value"] == 28.5
        assert result[1]["value"] == 25.0

    def test_falls_back_to_numeric_state(self):
        """When no attributes.temperature, falls back to numeric state."""
        history = [
            {
                "state": "22.5",
                "last_changed": "2025-02-20T12:00:00+00:00",
            },
        ]
        result = extract_temp_data(history)
        assert len(result) == 1
        assert result[0]["value"] == 22.5

    def test_skips_unavailable(self):
        """Unavailable/unknown states are skipped."""
        history = [
            {
                "state": "unavailable",
                "last_changed": "2025-02-20T12:00:00+00:00",
                "attributes": {},
            },
            {
                "state": "sunny",
                "last_changed": "2025-02-20T13:00:00+00:00",
                "attributes": {"temperature": 30.0},
            },
        ]
        result = extract_temp_data(history)
        assert len(result) == 1
        assert result[0]["value"] == 30.0

    def test_skips_non_numeric_state_without_attributes(self):
        """Non-numeric state without temperature attribute is skipped."""
        history = [
            {
                "state": "sunny",
                "last_changed": "2025-02-20T12:00:00+00:00",
            },
        ]
        result = extract_temp_data(history)
        assert len(result) == 0

    def test_sorted_by_time(self):
        """Results are sorted by timestamp."""
        history = [
            {
                "state": "sunny",
                "last_changed": "2025-02-20T14:00:00+00:00",
                "attributes": {"temperature": 30.0},
            },
            {
                "state": "sunny",
                "last_changed": "2025-02-20T12:00:00+00:00",
                "attributes": {"temperature": 25.0},
            },
        ]
        result = extract_temp_data(history)
        assert result[0]["value"] == 25.0  # Earlier time first
        assert result[1]["value"] == 30.0

    def test_empty_input(self):
        """Empty list returns empty list."""
        assert extract_temp_data([]) == []

    def test_datetime_objects_as_last_changed(self):
        """Handles datetime objects instead of ISO strings."""
        dt1 = datetime(2025, 2, 20, 12, 0, 0, tzinfo=timezone.utc)
        history = [
            {
                "state": "sunny",
                "last_changed": dt1,
                "attributes": {"temperature": 28.0},
            },
        ]
        result = extract_temp_data(history)
        assert len(result) == 1
        assert result[0]["value"] == 28.0


# --- T004: build_historical_profile with temp_data ---


class TestBuildHistoricalProfileWithTemp:
    """Test build_historical_profile() returns dual format {load_kw, avg_temp}."""

    def _make_load_data(self, base_ts, intervals, kwh_per_interval=0.1):
        """Helper: create load data with consistent energy increments."""
        data = []
        for i in range(intervals + 1):
            data.append({
                "time": base_ts + i * 300,
                "value": i * kwh_per_interval,
            })
        return data

    def _make_temp_data(self, base_ts, intervals, constant_temp=25.0):
        """Helper: create constant temperature data."""
        data = []
        for i in range(intervals + 1):
            data.append({
                "time": base_ts + i * 300,
                "value": constant_temp,
            })
        return data

    def test_returns_dict_format_with_temp(self):
        """With temp_data, profile returns {load_kw, avg_temp} per slot."""
        base_ts = datetime(2025, 2, 20, 12, 0, 0, tzinfo=timezone.utc).timestamp()
        load_data = self._make_load_data(base_ts, 3)
        temp_data = self._make_temp_data(base_ts, 3, constant_temp=28.0)

        profile = build_historical_profile(
            load_data, target_tz=timezone.utc, is_energy_sensor=True,
            temp_data=temp_data,
        )

        assert len(profile) > 0
        for slot, data in profile.items():
            assert "load_kw" in data
            assert "avg_temp" in data
            assert data["avg_temp"] is not None
            assert abs(data["avg_temp"] - 28.0) < 1.0

    def test_returns_none_temp_without_temp_data(self):
        """Without temp_data, profile returns avg_temp: None."""
        base_ts = datetime(2025, 2, 20, 12, 0, 0, tzinfo=timezone.utc).timestamp()
        load_data = self._make_load_data(base_ts, 3)

        profile = build_historical_profile(
            load_data, target_tz=timezone.utc, is_energy_sensor=True,
        )

        assert len(profile) > 0
        for slot, data in profile.items():
            assert "load_kw" in data
            assert "avg_temp" in data
            assert data["avg_temp"] is None

    def test_load_values_unchanged(self):
        """Load kW values should be same regardless of temp_data presence."""
        base_ts = datetime(2025, 2, 20, 12, 0, 0, tzinfo=timezone.utc).timestamp()
        load_data = self._make_load_data(base_ts, 3)
        temp_data = self._make_temp_data(base_ts, 3, constant_temp=30.0)

        profile_with = build_historical_profile(
            load_data, target_tz=timezone.utc, is_energy_sensor=True,
            temp_data=temp_data,
        )
        profile_without = build_historical_profile(
            load_data, target_tz=timezone.utc, is_energy_sensor=True,
        )

        for slot in profile_with:
            assert slot in profile_without
            assert abs(profile_with[slot]["load_kw"] - profile_without[slot]["load_kw"]) < 0.001

    def test_varying_temperature_averaged(self):
        """Temperature data across multiple days is averaged per slot."""
        base_ts = datetime(2025, 2, 20, 12, 0, 0, tzinfo=timezone.utc).timestamp()
        load_data = self._make_load_data(base_ts, 3)

        # Temperature varies: 20, 25, 30, 35
        temp_data = [
            {"time": base_ts, "value": 20.0},
            {"time": base_ts + 300, "value": 25.0},
            {"time": base_ts + 600, "value": 30.0},
            {"time": base_ts + 900, "value": 35.0},
        ]

        profile = build_historical_profile(
            load_data, target_tz=timezone.utc, is_energy_sensor=True,
            temp_data=temp_data,
        )

        # Each slot should have a temperature value
        for slot, data in profile.items():
            assert data["avg_temp"] is not None


# --- Direct interpolate() tests ---


class TestInterpolate:
    """Direct tests for interpolate() — linear interpolation of time-series data."""

    def test_empty_data_returns_zero(self):
        from custom_components.house_battery_control.historical_analyzer import interpolate
        assert interpolate(100.0, []) == 0.0

    def test_single_point_returns_value(self):
        from custom_components.house_battery_control.historical_analyzer import interpolate
        data = [{"time": 100.0, "value": 5.0}]
        assert interpolate(100.0, data) == 5.0
        assert interpolate(200.0, data) == 5.0  # any time returns same value

    def test_before_first_returns_first(self):
        from custom_components.house_battery_control.historical_analyzer import interpolate
        data = [
            {"time": 100.0, "value": 10.0},
            {"time": 200.0, "value": 20.0},
        ]
        assert interpolate(50.0, data) == 10.0

    def test_midpoint_interpolation(self):
        from custom_components.house_battery_control.historical_analyzer import interpolate
        data = [
            {"time": 100.0, "value": 10.0},
            {"time": 200.0, "value": 20.0},
        ]
        assert interpolate(150.0, data) == 15.0

    def test_after_last_returns_last(self):
        from custom_components.house_battery_control.historical_analyzer import interpolate
        data = [
            {"time": 100.0, "value": 10.0},
            {"time": 200.0, "value": 20.0},
        ]
        assert interpolate(300.0, data) == 20.0


# --- Direct parse_isoformat() tests ---


class TestParseIsoformat:
    """Direct tests for parse_isoformat() — ISO datetime string parsing."""

    def test_z_suffix(self):
        from custom_components.house_battery_control.historical_analyzer import parse_isoformat
        result = parse_isoformat("2025-02-20T12:00:00Z")
        assert result.year == 2025
        assert result.month == 2
        assert result.day == 20
        assert result.hour == 12
        assert result.tzinfo is not None

    def test_utc_offset(self):
        from custom_components.house_battery_control.historical_analyzer import parse_isoformat
        result = parse_isoformat("2025-02-20T12:00:00+10:30")
        assert result.hour == 12
        assert result.tzinfo is not None
