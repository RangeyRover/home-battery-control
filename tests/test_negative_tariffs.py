"""Feature 063: independent energy/cash oracles, written before production changes.

Load the calculation package without starting Home Assistant integrations.
"""

import importlib
import json
import math
import sys
import types
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1] / "custom_components/house_battery_control"
PACKAGE = "_hbc_calculation_tests"
if PACKAGE not in sys.modules:
    package = types.ModuleType(PACKAGE)
    package.__path__ = [str(ROOT)]
    sys.modules[PACKAGE] = package
legacy = importlib.import_module(f"{PACKAGE}.fsm.lin_fsm")
solver = legacy


def run(buy, sell, load=None, pv=None, capacity=1, soc=0, eta=1, **kw):
    battery = legacy.FakeBattery(capacity, soc, 12, 12, eta, eta)
    return solver.LinearBatteryController().propose_state_of_charge(
        battery, buy, sell, load or [0] * len(buy), pv or [0] * len(buy), **kw
    )


def check_balance(rows, initial, capacity, eta=1):
    stored = initial
    cash = 0
    for row in rows:
        imp, exp = row["grid_import_kwh"], row["grid_export_kwh"]
        charge, discharge = row["charge_kwh"], row["discharge_kwh"]
        assert min(imp, exp) <= 1e-6
        assert min(charge, discharge) <= 1e-6
        assert imp + row["pv"] / 12 + discharge == pytest.approx(
            row["load"] / 12 + charge + exp, abs=1e-6
        )
        stored += eta * charge - discharge / eta
        assert 0 <= stored + 1e-6 <= capacity + 2e-6
        assert row["target_soc"] == pytest.approx(100 * stored / capacity)
        assert row["net_grid"] == pytest.approx((imp - exp) * 12)
        cash += imp * row["import_price"] - exp * row["export_price"]
        assert row["cumulative_cost"] == pytest.approx(cash)
    return cash


@pytest.mark.parametrize("buy", [-0.4, 0, 0.3])
@pytest.mark.parametrize("sell", [-0.2, 0])
def test_no_battery_export_with_full_battery_and_solar(buy, sell):
    _, _, rows = run(
        [buy] * 24,
        [sell] * 24,
        [0.125] * 24,
        [0.4] * 24,
        capacity=27,
        soc=1,
        acquisition_cost=-0.25,
    )
    assert rows
    assert all(r["state"] != "DISCHARGE_GRID" for r in rows)
    check_balance(rows, 27, 27)


def test_negative_import_has_a_real_destination():
    _, _, rows = run([-0.15], [-0.2], [0.125], soc=1)
    assert rows
    check_balance(rows, 1, 1)
    assert rows[0]["grid_import_kwh"] == pytest.approx(0.125)


@pytest.mark.parametrize("buy,expected_charge,expected_cash", [(-0.1, 0, 0), (-0.4, 1, -0.1)])
def test_paid_charge_includes_later_solar_spill(buy, expected_charge, expected_cash):
    target, _, rows = run([buy, 0.2], [-0.3, -0.3], pv=[0, 1])
    assert rows
    assert target == pytest.approx(expected_charge)
    assert rows[-1]["target_soc"] == pytest.approx(100)
    assert check_balance(rows, 0, 1) == pytest.approx(expected_cash)


def test_efficiency_and_combined_power_limit():
    _, _, rows = run([-0.4, 0.5, 0.5], [-0.2, 0.2, 0.2], load=[0, 0.5, 0.5], eta=0.9)
    assert rows
    check_balance(rows, 0, 1, 0.9)
    assert all(r["discharge_kwh"] <= 1 + 1e-6 for r in rows)


def test_zero_margin_boundary_never_exports_battery():
    _, _, rows = run([0.1] * 2, [0.05] * 2, soc=1, export_margin=0.05)
    assert rows
    assert all(r["state"] != "DISCHARGE_GRID" for r in rows)


def test_first_target_and_row_agree():
    target, _, rows = run([-0.4, 0.2], [-0.2, -0.2], pv=[0, 0.5])
    assert rows and target * 100 == pytest.approx(rows[0]["target_soc"])
    check_balance(rows, 0, 1)


@pytest.mark.parametrize("bad", [float("nan"), float("inf")])
def test_invalid_input_returns_no_plan(bad):
    _, _, rows = run([bad], [0.2])
    assert rows == []


def test_invalid_successful_solver_result_is_rejected(monkeypatch):
    import numpy as np

    def invalid(c, **kwargs):
        return types.SimpleNamespace(success=True, x=np.zeros(len(c)), fun=0)

    monkeypatch.setattr(solver, "linprog", invalid)
    _, _, rows = run([0.3], [0.1], soc=1)
    assert rows == []


def test_solver_timeout_returns_no_plan(monkeypatch):
    monkeypatch.setattr(
        solver,
        "linprog",
        lambda *a, **k: types.SimpleNamespace(success=False, message="time limit"),
    )
    target, _, rows = run([-0.4], [-0.2], soc=0.5)
    assert rows == [] and target == 0.5


def test_reserve_and_no_import_remain_constraints():
    _, _, rows = run(
        [0.3, 0.3], [0.2, 0.2], load=[0.2, 0.2], soc=1, reserve_soc=50, no_import_steps={0, 1}
    )
    assert rows
    check_balance(rows, 1, 1)
    assert all(r["target_soc"] >= 50 - 1e-6 for r in rows)
    assert all(r["grid_import_kwh"] <= 1e-6 for r in rows)


def test_adapter_target_matches_corrected_charge():
    base = importlib.import_module(f"{PACKAGE}.fsm.base")
    context = base.FSMContext(
        soc=0,
        solar_production=0,
        load_power=0,
        grid_voltage=240,
        current_price=-0.4,
        forecast_solar=[],
        forecast_load=[],
        forecast_price=[],
        config={"battery_capacity": 13.5, "battery_rate_max": 12, "round_trip_efficiency": 1},
        solver_inputs=base.SolverInputs([-0.4, 0.2], [-0.3, -0.3], [0, 0], [0, 13.5]),
    )
    result = solver.LinearBatteryStateMachine().calculate_next_state(context)
    assert result.future_plan
    assert result.target_soc == pytest.approx(result.future_plan[0]["target_soc"])
    assert result.state == result.future_plan[0]["state"]


def test_reference_timeout_cannot_be_overridden_by_deadline(monkeypatch):
    original = solver.linprog
    calls = 0

    def timeout_on_reference(*args, **kwargs):
        nonlocal calls
        calls += 1
        if calls == 1:
            return original(*args, **kwargs)
        return types.SimpleNamespace(success=False, status=1, message="time limit")

    monkeypatch.setattr(solver, "linprog", timeout_on_reference)
    _, _, rows = run([-0.4, 0.2], [-0.3, -0.3], guard_deadline_steps=[2])
    assert calls >= 2
    assert rows == []


@pytest.mark.parametrize("args", [([0.1], [0.2, 0.3], [0], [0]), ([0.1], [0.2], [-1], [0])])
def test_missing_or_invalid_energy_is_not_fabricated(args):
    assert run(*args)[2] == []


def test_economic_tie_prefers_no_paid_charge():
    _, _, rows = run([-0.3, 0.2], [-0.3, -0.3], pv=[0, 1])
    assert rows[0]["grid_charge_kwh"] == pytest.approx(0, abs=1e-6)
    assert check_balance(rows, 0, 1) == pytest.approx(0, abs=1e-6)


def test_paid_charge_with_available_space():
    _, _, rows = run([-0.4, 0.2], [-0.3, -0.3], pv=[0, 0.5], capacity=2)
    assert rows[0]["grid_charge_kwh"] == pytest.approx(1)
    assert check_balance(rows, 0, 2) == pytest.approx(-0.4)


@pytest.mark.parametrize("soc", [0, 0.5, 1])
def test_observed_tariffs_with_explicit_synthetic_energy(soc):
    data = json.loads(
        (Path(__file__).parent / "fixtures/negative_tariffs_20261011.json").read_text()
    )
    samples = data["samples"]
    assert all(0 <= s["buy"]["age_seconds"] < 1800 for s in samples)
    assert all(0 <= s["sell"]["age_seconds"] < 1800 for s in samples)
    buy = [s["buy"]["value"] for s in samples]
    sell = [s["sell"]["value"] for s in samples]
    _, _, rows = run(
        buy,
        sell,
        load=[0.125] * len(buy),
        pv=[0.4] * len(buy),
        capacity=27,
        soc=soc,
        eta=0.95,
        acquisition_cost=-0.25,
    )
    assert len(rows) == len(samples)
    check_balance(rows, 27 * soc, 27, 0.95)
    assert all(r["battery_export_kwh"] <= 1e-6 for r in rows if r["export_price"] <= 0)


def test_day_horizon_completes_with_negative_midday_tariffs():
    n = 288
    buy = [-0.25 if 90 <= i < 180 else 0.3 for i in range(n)]
    sell = [-0.2 if 80 <= i < 200 else 0.08 for i in range(n)]
    pv = [
        max(0, 4 * math.sin(math.pi * (i - 72) / 144)) / 12 if 72 <= i <= 216 else 0
        for i in range(n)
    ]
    battery = legacy.FakeBattery(27, 0.5, 6.3, 10)
    _, _, rows = solver.LinearBatteryController().propose_state_of_charge(
        battery, buy, sell, [0.125] * n, pv, acquisition_cost=0.1
    )
    assert len(rows) == n, "A representative day must solve within the controller budget"
    check_balance(rows, 13.5, 27, 0.95)


def test_uncertain_reference_bound_cannot_claim_charging_savings(monkeypatch):
    original = solver.linprog
    calls = 0

    def uncertain_reference(*args, **kwargs):
        nonlocal calls
        calls += 1
        result = original(*args, **kwargs)
        if calls >= 2:
            result.mip_dual_bound = -100.0
        return result

    monkeypatch.setattr(solver, "linprog", uncertain_reference)
    _, _, rows = run([-0.4, 0.2], [-0.3, -0.3], pv=[0, 1])
    assert calls >= 2
    assert rows[0]["grid_charge_kwh"] <= 1e-6


def test_adapter_independently_rejects_negative_export_recommendation(monkeypatch):
    base = importlib.import_module(f"{PACKAGE}.fsm.base")
    context = base.FSMContext(
        soc=50,
        solar_production=0,
        load_power=0,
        grid_voltage=240,
        current_price=-0.4,
        forecast_solar=[],
        forecast_load=[],
        forecast_price=[],
        config={},
        solver_inputs=base.SolverInputs([-0.4], [-0.3], [0], [0]),
    )
    fsm = solver.LinearBatteryStateMachine()
    monkeypatch.setattr(
        fsm.controller,
        "propose_state_of_charge",
        lambda **kw: (0.4, -1, [{"state": "DISCHARGE_GRID"}]),
    )
    result = fsm.calculate_next_state(context)
    assert result.state == "SELF_CONSUMPTION"
    assert result.limit_kw == 0
    assert not result.future_plan
