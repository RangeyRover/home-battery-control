import logging

from .base import BatteryStateMachine, FSMContext, FSMResult

_LOGGER = logging.getLogger(__name__)

class LinearBatteryController(object):
    def __init__(self):
        self.step = 288 # For 24 hour 5 min resolution

    def propose_state_of_charge(self,
                                site_id,
                                timestamp,
                                battery,
                                actual_previous_load,
                                actual_previous_pv_production,
                                price_buy,
                                price_sell,
                                load_forecast,
                                pv_forecast,
                                acquisition_cost=0.0):


        self.step -= 1
        if (self.step == 1): return 0
        if (self.step > 1): number_step = min(288, self.step)

        #
        energy = [None] * number_step

        for i in range(number_step):
            # Energy array tracks net load requirements
            energy[i] = load_forecast[i] - pv_forecast[i]
        #battery
        capacity = battery.capacity
        charging_efficiency = battery.charging_efficiency
        discharging_efficiency = 1. / battery.discharging_efficiency
        current = capacity * battery.current_charge
        limit = battery.charging_power_limit
        dis_limit = battery.discharging_power_limit

        # Convert kw limits to kwh limits per 5 min step
        limit = limit * (5.0 / 60.0)
        dis_limit = dis_limit * (5.0 / 60.0)

        # SciPy Migration (replaces ortools)
        import numpy as np
        from scipy.optimize import linprog

        N = number_step
        num_vars = 5 * N + 1

        # Determine bounds
        bounds = []
        # c_i
        for i in range(N):
            bounds.append((0.0, limit))
        # dh_i
        for i in range(N):
            max_home_kwh = max(0.0, energy[i])
            bounds.append((-max_home_kwh, 0.0))
        # dg_i
        for i in range(N):
            max_home_kwh = max(0.0, energy[i])
            max_grid_kwh = max(0.0, dis_limit - max_home_kwh)
            bounds.append((-max_grid_kwh, 0.0))
        # g_i
        for i in range(N):
            bounds.append((0.0, None))
        # b_i
        for i in range(N + 1):
            bounds.append((0.0, capacity))

        # Objective 'c'
        c_obj = np.zeros(num_vars)
        for i in range(N):
            c_obj[i] = price_sell[i] + price_buy[i] / 1000.0                   # c_i
            c_obj[N + i] = price_buy[i]                                        # dh_i
            c_obj[2*N + i] = price_sell[i]                                     # dg_i
            c_obj[3*N + i] = price_buy[i] - price_sell[i]                      # g_i
        c_obj[5*N] = -max(0.001, acquisition_cost)                             # b_N (last one)

        # Inequality Constraints A_ub x <= b_ub
        # -g_i + c_i + dh_i + dg_i <= -energy[i]
        A_ub = np.zeros((N, num_vars))
        b_ub = np.zeros(N)
        for i in range(N):
            A_ub[i, i] = 1.0           # c_i
            A_ub[i, N + i] = 1.0       # dh_i
            A_ub[i, 2*N + i] = 1.0     # dg_i
            A_ub[i, 3*N + i] = -1.0    # g_i
            b_ub[i] = -energy[i]

        # Equality Constraints A_eq x == b_eq
        # 1. b_0 == current
        # 2. eff_c * c_i + eff_d * dh_i + eff_d * dg_i + b_i - b_{i+1} == 0
        A_eq = np.zeros((1 + N, num_vars))
        b_eq = np.zeros(1 + N)

        A_eq[0, 4*N] = 1.0
        b_eq[0] = current

        for i in range(N):
            A_eq[1 + i, i] = charging_efficiency                # c_i
            A_eq[1 + i, N + i] = discharging_efficiency         # dh_i
            A_eq[1 + i, 2*N + i] = discharging_efficiency       # dg_i
            A_eq[1 + i, 4*N + i] = 1.0                          # b_i
            A_eq[1 + i, 4*N + i + 1] = -1.0                     # b_{i+1}
            b_eq[1 + i] = 0.0

        # Run SciPy Linprog
        res = linprog(c_obj, A_ub=A_ub, b_ub=b_ub, A_eq=A_eq, b_eq=b_eq, bounds=bounds, method='highs')

        if not res.success:
            _LOGGER.warning("Linear solver could not find optimal solution: %s", res.message)
            return battery.current_charge, 0.0, 0.0, 0.0

        return res.x[4*N + 1] / capacity, float(res.fun), float(abs(res.x[N])), float(abs(res.x[2*N]))


class FakeBattery:
    def __init__(self, capacity, current_charge, charge_limit, discharge_limit, charging_efficiency=0.95, discharging_efficiency=0.95):
        self.capacity = capacity
        # charge state in percentage (0-1)
        self.current_charge = current_charge
        self.charging_power_limit = charge_limit
        self.discharging_power_limit = discharge_limit
        self.charging_efficiency = charging_efficiency
        self.discharging_efficiency = discharging_efficiency


class LinearBatteryStateMachine(BatteryStateMachine):
    """
    Implementation using pywraplp solver.
    """
    def __init__(self):
        self.controller = LinearBatteryController()

    def calculate_next_state(self, context: FSMContext) -> FSMResult:
        forecast_len = min(
            len(context.forecast_price), len(context.forecast_solar), len(context.forecast_load)
        )
        if forecast_len < 1:
            return FSMResult(state="IDLE", limit_kw=0.0, reason="Forecast too short")

        number_step = min(forecast_len, 288)

        # Always reset step count in loop for stateless evaluation
        self.controller.step = number_step

        price_buy = [0.0] * number_step
        price_sell = [0.0] * number_step
        for t in range(number_step):
            if isinstance(context.forecast_price[t], dict):
                price_buy[t] = float(context.forecast_price[t].get("import_price", 0.0))
                price_sell[t] = float(context.forecast_price[t].get("export_price", 0.0))
            else:
                price_buy[t] = float(context.current_price)
                price_sell[t] = float(context.current_price * 0.8)

        load_f = [0.0] * number_step
        pv_f = [0.0] * number_step
        for t in range(number_step):
            if isinstance(context.forecast_solar[t], dict):
                pv_f[t] = float(context.forecast_solar[t].get("kw", 0.0))
            else:
                pv_f[t] = float(context.forecast_solar[t])

            if isinstance(context.forecast_load[t], dict):
                load_f[t] = float(context.forecast_load[t].get("kw", 0.0))
            else:
                load_f[t] = float(context.forecast_load[t])

        # Convert kW to kWh for the discrete step bounds
        load_f = [kw * (5.0 / 60.0) for kw in load_f]
        pv_f = [kw * (5.0 / 60.0) for kw in pv_f]

        # Splice current instantaneous context into the first array slot (T=0)
        # Using integration footprint compatible with base BatteryStateMachine
        current_load_kwh = context.load_power * (5.0 / 60.0)
        current_pv_kwh = context.solar_production * (5.0 / 60.0)
        load_f[0] = current_load_kwh
        pv_f[0] = current_pv_kwh

        capacity = max(
            13.5, context.config.get("battery_capacity", context.config.get("capacity_kwh", 27.0))
        )
        limit_kw_charge = float(context.config.get("battery_rate_max", 6.3))
        limit_kw_discharge = float(context.config.get("inverter_limit", 10.0))
        current_soc_perc = max(0.0, min(100.0, context.soc)) / 100.0

        import math
        # Extract Round Trip Efficiency (RTE) from config. Default to 0.90 if missing.
        rte = float(context.config.get("round_trip_efficiency", 0.90))
        # Mathematical one-way efficiency is the square root of the round trip efficiency
        one_way_eff = math.sqrt(rte)

        battery = FakeBattery(
            capacity=capacity,
            current_charge=current_soc_perc,
            charge_limit=limit_kw_charge,
            discharge_limit=limit_kw_discharge,
            charging_efficiency=one_way_eff,
            discharging_efficiency=one_way_eff
        )

        try:
            target_soc_perc, projected_cost, raw_home_dis, raw_grid_dis = self.controller.propose_state_of_charge(
                site_id=0,
                timestamp="00:00",
                battery=battery,
                actual_previous_load=0,
                actual_previous_pv_production=0,
                price_buy=price_buy,
                price_sell=price_sell,
                load_forecast=load_f,
                pv_forecast=pv_f,
                acquisition_cost=context.acquisition_cost
            )
        except Exception as e:
            _LOGGER.error("Linear Solver failed: %s", e)
            return FSMResult(state="IDLE", limit_kw=0.0, reason=f"Solver Error: {e}")

        if target_soc_perc is None:
            return FSMResult(state="IDLE", limit_kw=0.0, reason="Solver returned None")

        target_soc_perc = float(target_soc_perc)

        # Convert the Target SoC percentage back into an FSM Action Limit Kw
        target_delta_kwh = (target_soc_perc - current_soc_perc) * capacity

        # Convert kwh to kw (5 minute intervals means * 12)
        power_kw = target_delta_kwh * 12.0

        if power_kw > 0.1:
            req_power = power_kw / battery.charging_efficiency
            return FSMResult(
                state="CHARGE_GRID",
                limit_kw=round(min(limit_kw_charge, req_power), 2),
                reason="LP Optimized Charge",
                target_soc=target_soc_perc * 100.0,
                projected_cost=projected_cost
            )
        elif power_kw < -0.1:
            req_power = abs(power_kw) * battery.discharging_efficiency
            net_grid_export = raw_grid_dis / (5.0/60.0)
            net_home_offset = raw_home_dis / (5.0/60.0)

            if net_grid_export > net_home_offset:
                return FSMResult(
                    state="DISCHARGE_GRID",
                    limit_kw=round(min(limit_kw_discharge, req_power), 2),
                    reason="LP Optimized Grid Export",
                    target_soc=target_soc_perc * 100.0,
                    projected_cost=projected_cost
                )
            else:
                return FSMResult(
                    state="DISCHARGE_HOME",
                    limit_kw=round(min(limit_kw_discharge, req_power), 2),
                    reason="LP Optimized Home Discharge",
                    target_soc=target_soc_perc * 100.0,
                    projected_cost=projected_cost
                )

        return FSMResult(
            state="IDLE",
            limit_kw=0.0,
            reason="LP Optimization: Idle optimal",
            target_soc=target_soc_perc * 100.0,
            projected_cost=projected_cost
        )
