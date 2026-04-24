from datetime import datetime, timezone

from custom_components.house_battery_control.diagnostics import build_diagnostic_plan_table


class DummyCoordinator:
    def __init__(self):
        self.config = {"battery_capacity": 10.0}

def test_diagnostics_synthetic_flag():
    coord = DummyCoordinator()

    t0 = datetime(2026, 4, 24, 15, 0, tzinfo=timezone.utc)
    t1 = datetime(2026, 4, 24, 15, 30, tzinfo=timezone.utc)

    # Simulate a rates timeline where one is live and one is synthetic
    rates = [
        {"start": t0, "end": t1, "import_price": 0.1, "export_price": 0.05, "synthetic": False},
        {"start": t1, "end": t1, "import_price": 0.2, "export_price": 0.10, "synthetic": True},
    ]

    # Dummy FSM future plan (needs to match length of rates)
    future_plan = [
        {"state": "SELF_CONSUMPTION", "target_soc": 50.0},
        {"state": "SELF_CONSUMPTION", "target_soc": 40.0},
    ]

    table = build_diagnostic_plan_table(
        coordinator=coord,
        rates=rates,
        solar_forecast=[],
        load_forecast=[],
        weather=[],
        current_soc=60.0,
        future_plan=future_plan,
    )

    assert len(table) == 2

    # The first row shouldn't be synthetic
    assert table[0].get("Synthetic") is False, "Row 0 should not be synthetic"

    # The second row MUST be synthetic
    assert table[1].get("Synthetic") is True, f"Row 1 should be synthetic, but got {table[1].get('Synthetic')}"
    print("SUCCESS: Synthetic flag is present in the diagnostic table.")

if __name__ == "__main__":
    test_diagnostics_synthetic_flag()
