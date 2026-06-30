"""
lin_fsm.py — LP FSM (SciPy HiGHS)
===================================
Implements all system requirements from specs/03-lp-fsm-system/system_requirements.md.
"""
try:
    from .base import BatteryStateMachine, FSMContext, FSMResult
except ImportError:
    from base import BatteryStateMachine, FSMContext, FSMResult

import logging
import math
import statistics
from datetime import time

import numpy as np
from scipy.optimize import linprog

_LOGGER = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
#  No-Import Period helpers (Feature 010)
# ---------------------------------------------------------------------------
def _parse_no_import_periods(config_str: str) -> list[tuple[time, time]]:
    """Parse comma-separated 'HH:MM-HH:MM' strings into (start, end) time tuples.

    Returns empty list for empty/None input. Invalid entries are logged and skipped.
    """
    if not config_str or not config_str.strip():
        return []
    periods = []
    for part in config_str.split(","):
        part = part.strip()
        if "-" not in part:
            _LOGGER.warning(f"Invalid no-import period (no dash): '{part}'")
            continue
        try:
            start_str, end_str = part.split("-", 1)
            sh, sm = map(int, start_str.strip().split(":"))
            eh, em = map(int, end_str.strip().split(":"))
            periods.append((time(sh, sm), time(eh, em)))
        except (ValueError, IndexError) as e:
            _LOGGER.warning(f"Invalid no-import period '{part}': {e}")
            continue
    return periods


def _is_in_no_import_period(t: time, periods: list[tuple[time, time]]) -> bool:
    """Check if a local time falls within any no-import period.

    Handles midnight-spanning windows (e.g. 22:00-06:00).
    """
    for start, end in periods:
        if start <= end:
            # Normal window: e.g. 15:00-21:00
            if start <= t < end:
                return True
        else:
            # Midnight wrap: e.g. 22:00-06:00
            if t >= start or t < end:
                return True
    return False


# ---------------------------------------------------------------------------
#  FakeBattery — §6 of system requirements
# ---------------------------------------------------------------------------
class FakeBattery:
    """Lightweight battery model constructed from FSMContext config."""

    def __init__(
        self,
        capacity: float,
        current_charge: float,
        charge_limit: float,
        discharge_limit: float,
        charging_efficiency: float = 0.95,
        discharging_efficiency: float = 0.95,
    ):
        self.capacity = capacity
        self.current_charge = current_charge          # fraction 0-1
        self.charging_power_limit = charge_limit      # kW
        self.discharging_power_limit = discharge_limit  # kW
        self.charging_efficiency = charging_efficiency
        self.discharging_efficiency = discharging_efficiency


# ---------------------------------------------------------------------------
#  LinearBatteryController — core LP solver (SciPy translation of GLOP source)
# ---------------------------------------------------------------------------
class LinearBatteryController:
    """
    Translates the original GLOP competition LP formulation into SciPy's linprog.

    Variable layout (1D vector x):
        g[0..N-1]   grid import          bounds: [0, ∞)
        c[0..N-1]   battery charge       bounds: [0, charge_limit_kwh]
        dh[0..N-1]  discharge to home    bounds: [-max_home_kwh, 0]
        dg[0..N-1]  discharge to grid    bounds: [-max_grid_kwh, 0]
        s[0..N-1]   forced solar export  bounds: [0, ∞)   (Feature 032)
        b[0..N]     battery state        bounds: [safe_lb, capacity]
    """

    def __init__(self):
        self.step = 288  # Default, overridden dynamically by calculate_next_state

    def propose_state_of_charge(
        self,
        battery: FakeBattery,
        price_buy: list[float],
        price_sell: list[float],
        load_forecast: list[float],
        pv_forecast: list[float],
        acquisition_cost: float = 0.0,
        cumulative_cost: float = 0.0,
        reserve_soc: float = 0.0,
        no_import_steps: set[int] | None = None,
        export_margin: float = 0.0,
        guard_deadline_steps: list[int] | None = None,
    ):
        number_step = len(price_buy)
        self.step = number_step

        # --- Physical parameters ---
        capacity = battery.capacity
        eta_in = battery.charging_efficiency
        eta_out = 1.0 / battery.discharging_efficiency
        current = capacity * battery.current_charge
        charge_limit = battery.charging_power_limit * (5.0 / 60.0)   # kW → kWh per step
        dis_limit = battery.discharging_power_limit * (5.0 / 60.0)

        # --- Net energy requirement per step ---
        energy = [load_forecast[i] - pv_forecast[i] for i in range(number_step)]

        # --- Variable offsets ---
        g_off = 0
        c_off = number_step
        dh_off = 2 * number_step
        dg_off = 3 * number_step
        s_off = 4 * number_step       # Feature 032: forced solar export (spill)
        b_off = 5 * number_step
        num_vars = 5 * number_step + (number_step + 1)

        # --- Objective function (§7 of system requirements) ---
        obj = np.zeros(num_vars)

        _blocked = no_import_steps or set()
        bounds = [None] * num_vars  # Pre-allocate for indexed assignment

        for i in range(number_step):
            # Grid import (g): raw price, no-import periods, negative price cap
            obj[g_off + i] = price_buy[i]
            if i in _blocked:
                bounds[g_off + i] = (0.0, 0.0)
            elif price_buy[i] < 0:
                bounds[g_off + i] = (0.0, load_forecast[i] + charge_limit)
            else:
                bounds[g_off + i] = (0.0, None)

            # Charge (c): opportunity cost + tiebreaker — §7.2
            obj[c_off + i] = max(0.001, price_sell[i]) + max(0.0, price_buy[i]) / 1000.0
            bounds[c_off + i] = (0.0, charge_limit)

            # Discharge to home (dh): opportunity cost = max(ε, sell_price)
            sell_opp = max(0.001, price_sell[i])
            obj[dh_off + i] = sell_opp
            max_home = max(0.0, energy[i])
            bounds[dh_off + i] = (-max_home, 0.0)

            # Discharge to grid (dg): opportunity cost = max(ε, sell_price - export_margin)
            sell_opp_grid = max(0.001, price_sell[i] - export_margin)
            obj[dg_off + i] = sell_opp_grid
            max_grid = max(0.0, dis_limit - max_home)
            bounds[dg_off + i] = (-max_grid, 0.0)

            # Forced solar export / spill (s) — Feature 032 FR-007
            # Costed mathematically to penalize negative-export-price solar periods.
            # Feature 035: Negative export prices (e.g. -0.05) must translate to a
            # positive penalty (+0.05) to avoid mathematically rewarding the LP for spilling.
            # Positive export prices naturally cost 0 here (opportunity cost handled by c).
            obj[s_off + i] = max(0.0, -price_sell[i])
            max_spill = max(0.0, pv_forecast[i] - load_forecast[i])
            bounds[s_off + i] = (0.0, max_spill)

        # Battery state bounds with dynamic feasibility gradient — §8
        # Terminal valuation — §9: computed from raw acquisition_cost
        median_buy = statistics.median(price_buy) if price_buy else acquisition_cost
        blended = (median_buy + acquisition_cost) / 2.0
        terminal_valuation = max(acquisition_cost, blended)

        reserve_kwh = capacity * (reserve_soc / 100.0)
        for i in range(number_step + 1):
            if i == number_step:
                # Terminal valuation — §9 (prevents full discharge)
                obj[b_off + i] = -max(0.001, terminal_valuation)
            else:
                obj[b_off + i] = 0.0
            physically_accessible = current + i * charge_limit * eta_in
            safe_lb = min(reserve_kwh, physically_accessible)
            bounds[b_off + i] = (safe_lb, capacity)

        # Apply guard deadlines (Phase 4)
        if guard_deadline_steps:
            for deadline_idx in guard_deadline_steps:
                if 0 <= deadline_idx < (number_step + 1):
                    bounds[b_off + deadline_idx] = (capacity, capacity)

        # --- Inequality constraints ---
        # Row 0..N-1: grid balance  g[i] - c[i] - dh[i] - dg[i] >= energy[i]
        #   Rewrite: -g[i] + c[i] + dh[i] + dg[i] <= -energy[i]
        # Row N..2N-1: spill floor  s[i] >= -energy[i] - c[i]   (Feature 032)
        #   Rewrite: -s[i] - c[i] <= energy[i]
        n_ub = 2 * number_step
        a_ub = np.zeros((n_ub, num_vars))
        b_ub = np.zeros(n_ub)
        for i in range(number_step):
            # Grid balance row
            a_ub[i, g_off + i] = -1.0
            a_ub[i, c_off + i] = 1.0
            a_ub[i, dh_off + i] = 1.0
            a_ub[i, dg_off + i] = 1.0
            b_ub[i] = -energy[i]

            # Spill floor row — FR-008
            a_ub[number_step + i, s_off + i] = -1.0
            a_ub[number_step + i, c_off + i] = -1.0
            b_ub[number_step + i] = energy[i]

        # --- Equality constraints: battery dynamics ---
        # b[0] = current
        # b[i+1] = b[i] + c[i]*eta_in + dh[i]*eta_out + dg[i]*eta_out
        a_eq = np.zeros((number_step + 1, num_vars))
        b_eq = np.zeros(number_step + 1)

        a_eq[0, b_off] = 1.0
        b_eq[0] = current

        for i in range(number_step):
            a_eq[i + 1, c_off + i] = eta_in
            a_eq[i + 1, dh_off + i] = eta_out
            a_eq[i + 1, dg_off + i] = eta_out
            a_eq[i + 1, b_off + i] = 1.0
            a_eq[i + 1, b_off + i + 1] = -1.0
            b_eq[i + 1] = 0.0

        # --- Solve ---
        res = linprog(obj, A_ub=a_ub, b_ub=b_ub, A_eq=a_eq, b_eq=b_eq,
                      bounds=bounds, method="highs")

        if not res.success:
            _LOGGER.warning("LP solver failed: %s", res.message)
            return battery.current_charge, 0.0, []

        # --- Extract first-step outputs ---
        b_1 = res.x[b_off + 1]
        objective_value = res.fun

        # --- Build 288-step future plan sequence ---
        running_capacity = battery.current_charge
        running_cost = acquisition_cost
        running_cum_cost = cumulative_cost
        soc_correction = 0.0  # BUG-025B: accumulate energy retained by gate
        sequence = []

        for i in range(number_step):
            step_b = min(res.x[b_off + i + 1] + soc_correction, capacity)
            step_c = res.x[c_off + i]
            step_g = res.x[g_off + i]
            step_dh = abs(res.x[dh_off + i])
            step_dg = abs(res.x[dg_off + i])

            # --- SoC-cap plan guard — FR-001/FR-002 (Feature 032) ---
            # Clamp charge to available battery headroom so the plan never
            # shows phantom CHARGE_GRID at 100 % SoC.
            headroom = capacity - step_b          # kWh left before full
            if headroom <= 0:
                # FR-001: battery full — zero out charge & matching grid import
                charge_reduction = step_c
                step_c = 0.0
                step_g = max(0.0, step_g - charge_reduction)
            else:
                max_charge = headroom / eta_in     # pre-efficiency clamp (Q1)
                if step_c > max_charge:
                    # FR-002: nearly full — clamp to headroom
                    charge_reduction = step_c - max_charge
                    step_c = max_charge
                    step_g = max(0.0, step_g - charge_reduction)

            # --- Acquisition cost tracking — §12 (uses raw unclamped prices) ---
            if step_c > 0.001:
                charge_from_grid = min(step_c, step_g)
                charge_cost = charge_from_grid * price_buy[i]
                current_value = running_capacity * running_cost
                new_value = current_value + charge_cost
                new_capacity = running_capacity + step_c
                if new_capacity > 0:
                    running_cost = new_value / new_capacity
            running_capacity = step_b

            # --- Net grid flow — §11.2 (energy balance, inherently handles degeneracy) ---
            net_grid_kwh = load_forecast[i] - pv_forecast[i] + step_c - step_dh - step_dg
            net_grid_kw = net_grid_kwh * (60.0 / 5.0)

            # --- State classification — §11.3 (solver variables, same approach as §10.2) ---
            if step_dg > 0.005:
                state = "DISCHARGE_GRID"
            elif step_c > 0.005 and step_g > 0.005:
                state = "CHARGE_GRID"
            else:
                state = "SELF_CONSUMPTION"

            # --- Acquisition cost gate — FR-001: row-by-row check ---
            # Applies export_margin so that effective sell (after margin) must exceed acq cost
            if state == "DISCHARGE_GRID" and price_sell[i] - export_margin < running_cost:
                # FR-002: Battery retains energy — adjust state for subsequent steps
                soc_correction += step_dg  # BUG-025B: carry forward to future steps
                running_capacity = running_capacity + step_dg
                step_b = min(running_capacity, capacity)  # BUG-025B: correct SoC forecast
                step_dg = 0.0
                state = "SELF_CONSUMPTION"
                # FR-005: Recalculate net grid without export
                net_grid_kwh = load_forecast[i] - pv_forecast[i] + step_c - step_dh - step_dg
                net_grid_kw = net_grid_kwh * (60.0 / 5.0)

            # --- Cumulative cost tracking — §3.4 (raw prices, net grid flow) ---
            if net_grid_kwh > 0:
                running_cum_cost += net_grid_kwh * price_buy[i]
            else:
                running_cum_cost += net_grid_kwh * price_sell[i]

            sequence.append({
                "target_soc": (step_b / capacity) * 100.0,
                "state": state,
                "net_grid": net_grid_kw,
                "load": load_forecast[i] * (60.0 / 5.0),
                "pv": pv_forecast[i] * (60.0 / 5.0),
                "import_price": price_buy[i],
                "export_price": price_sell[i],
                "acquisition_cost": running_cost,
                "cumulative_cost": running_cum_cost,
            })

        return b_1 / capacity, objective_value, sequence


# ---------------------------------------------------------------------------
#  LinearBatteryStateMachine — adapter for FSMContext/FSMResult interface
# ---------------------------------------------------------------------------
class LinearBatteryStateMachine(BatteryStateMachine):
    """
    Wraps LinearBatteryController to satisfy the BatteryStateMachine ABC.
    This is the entry point for both hybrid_tester.py and coordinator.py.
    """

    def __init__(self):
        self.controller = LinearBatteryController()

    def calculate_next_state(self, context: FSMContext) -> FSMResult:
        # --- Fail-fast if solver_inputs not populated (FR-008) ---
        if context.solver_inputs is None:
            return FSMResult(
                state="ERROR",
                limit_kw=0.0,
                reason="solver_inputs not populated by coordinator",
            )

        # Force dynamic step horizon based on populated inputs
        number_step = len(context.solver_inputs.price_buy)
        self.controller.step = number_step

        # --- Read pre-built arrays from solver_inputs (Feature 024) ---
        si = context.solver_inputs
        price_buy = list(si.price_buy)
        price_sell = list(si.price_sell)
        load_f = list(si.load_kwh)
        pv_f = list(si.pv_kwh)
        no_import_steps = si.no_import_steps if si.no_import_steps else set()

        # --- Battery model — §6 ---
        capacity = max(13.5, context.config.get("battery_capacity",
                       context.config.get("capacity_kwh", 27.0)))
        limit_kw_charge = float(context.config.get("battery_rate_max", 6.3))
        limit_kw_discharge = float(context.config.get("inverter_limit", 10.0))
        current_soc = max(0.0, min(100.0, context.soc)) / 100.0

        rte = float(context.config.get("round_trip_efficiency", 0.90))
        one_way_eff = math.sqrt(rte)

        battery = FakeBattery(
            capacity=capacity,
            current_charge=current_soc,
            charge_limit=limit_kw_charge,
            discharge_limit=limit_kw_discharge,
            charging_efficiency=one_way_eff,
            discharging_efficiency=one_way_eff,
        )

        try:
            target_soc_frac, projected_cost, sequence = (
                self.controller.propose_state_of_charge(
                    battery=battery,
                    price_buy=price_buy,
                    price_sell=price_sell,
                    load_forecast=load_f,
                    pv_forecast=pv_f,
                    acquisition_cost=context.acquisition_cost,
                    cumulative_cost=context.cumulative_cost,
                    reserve_soc=float(context.config.get("reserve_soc", 0.0)),
                    no_import_steps=no_import_steps if no_import_steps else None,
                    export_margin=float(context.config.get("export_margin", 0.0)),
                    guard_deadline_steps=si.guard_deadline_steps,
                )
            )
        except Exception as e:
            _LOGGER.error("LP Solver failed: %s", e)
            return FSMResult(state="ERROR", limit_kw=0.0, reason=f"Solver Error: {e}")

        if target_soc_frac is None:
            return FSMResult(state="ERROR", limit_kw=0.0, reason="Solver returned None")

        target_soc_frac = float(target_soc_frac)

        # --- FR-001 (026): Single state source from sequence[0] ---
        if sequence:
            state_0 = sequence[0]["state"]
        else:
            state_0 = "SELF_CONSUMPTION"  # FR-003: safe default

        # --- Immediate action limit_kw — FR-002: calculation unchanged ---
        target_delta_kwh = (target_soc_frac - current_soc) * capacity
        power_kw = target_delta_kwh * 12.0  # kWh per 5-min → kW

        if state_0 == "CHARGE_GRID" and power_kw > 0.01:
            req = power_kw / battery.charging_efficiency
            limit_kw = round(min(limit_kw_charge, req), 2)
        elif state_0 == "DISCHARGE_GRID" and power_kw < -0.01:
            req = abs(power_kw) * battery.discharging_efficiency
            limit_kw = round(min(limit_kw_discharge, req), 2)
        else:
            limit_kw = 0.0

        reason_map = {
            "CHARGE_GRID": "LP Optimized Charge",
            "DISCHARGE_GRID": "LP Optimized Grid Export",
            "SELF_CONSUMPTION": "LP Optimized Self-Consumption",
        }

        return FSMResult(
            state=state_0,
            limit_kw=limit_kw,
            reason=reason_map.get(state_0, "LP Optimization: No action needed"),
            target_soc=target_soc_frac * 100.0,
            projected_cost=projected_cost,
            future_plan=sequence,
        )
