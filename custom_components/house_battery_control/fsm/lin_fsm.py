from .base import BatteryStateMachine, FSMContext, FSMResult
import logging

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

        # Ortools
        from ortools.linear_solver import pywraplp
        solver = pywraplp.Solver("B", pywraplp.Solver.GLOP_LINEAR_PROGRAMMING)
         
        # Variables: all are continous
        charge = [solver.NumVar(0.0, limit, "c"+str(i)) for i in range(number_step)] 
        
        dis_charge_home = []
        dis_charge_grid = []
        for i in range(number_step):
            # Home discharge is strictly bounded by the net energy requirement
            # It cannot exceed the physical home load (otherwise it would be grid export)
            max_home_kwh = max(0.0, energy[i])
            # Grid discharge is bounded by whatever inverter capacity is left over
            max_grid_kwh = max(0.0, dis_limit - max_home_kwh)
            
            dis_charge_home.append(solver.NumVar(-max_home_kwh, 0.0, "dh"+str(i)))
            dis_charge_grid.append(solver.NumVar(-max_grid_kwh, 0.0, "dg"+str(i)))
        
        battery_power = [solver.NumVar(0.0, capacity, "b"+str(i)) for i in range(number_step+1)]
        grid = [solver.NumVar(0.0, solver.infinity(), "g"+str(i)) for i in range(number_step)] 
        
        # Objective function
        objective = solver.Objective()
        for i in range(number_step):
            objective.SetCoefficient(grid[i], price_buy[i] - price_sell[i])
            objective.SetCoefficient(charge[i], price_sell[i] + price_buy[i] / 1000.)
            # mathematically separate objective values
            objective.SetCoefficient(dis_charge_home[i], price_buy[i])
            objective.SetCoefficient(dis_charge_grid[i], price_sell[i])
        # This mathematically forces the solver to prefer holding energy (and obtaining the reward)
        # over discharging to the grid for a price that is less than what it cost to acquire.
        # We use a negative coefficient because we are minimizing total system cost.
        objective.SetCoefficient(battery_power[-1], -max(0.001, acquisition_cost))
        
        objective.SetMinimization()
         
        # 3 Constraints
        c_grid = [None] * number_step
        c_power = [None] * (number_step+1)
         
        # first constraint
        c_power[0] = solver.Constraint(current, current)
        c_power[0].SetCoefficient(battery_power[0], 1)
         
        for i in range(0, number_step):
            # second constraint
            c_grid[i] = solver.Constraint(energy[i], solver.infinity())
            c_grid[i].SetCoefficient(grid[i], 1)
            c_grid[i].SetCoefficient(charge[i], -1)
            c_grid[i].SetCoefficient(dis_charge_home[i], -1)
            c_grid[i].SetCoefficient(dis_charge_grid[i], -1)
            # third constraint
            c_power[i+1] = solver.Constraint( 0, 0)
            c_power[i+1].SetCoefficient(charge[i], charging_efficiency)
            c_power[i+1].SetCoefficient(dis_charge_home[i], discharging_efficiency)
            c_power[i+1].SetCoefficient(dis_charge_grid[i], discharging_efficiency)
            c_power[i+1].SetCoefficient(battery_power[i], 1)
            c_power[i+1].SetCoefficient(battery_power[i+1], -1)

        #solve the model
        status = solver.Solve()

        if status != pywraplp.Solver.OPTIMAL:
            _LOGGER.warning("Linear solver could not find optimal solution.")
            return battery.current_charge, 0.0, 0.0, 0.0

        return battery_power[1].solution_value() / capacity, objective.Value(), abs(dis_charge_home[0].solution_value()), abs(dis_charge_grid[0].solution_value())


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
