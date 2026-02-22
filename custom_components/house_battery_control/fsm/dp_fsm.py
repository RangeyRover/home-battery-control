"""
MIT License

Copyright (c) 2018 Guilllermo Barbadillo (ironbar)

Permission is hereby granted, free of charge, to any person obtaining a copy
of this software and associated documentation files (the "Software"), to deal
in the Software without restriction, including without limitation the rights
to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
copies of the Software, and to permit persons to whom the Software is
furnished to do so, subject to the following conditions:

The above copyright notice and this permission notice shall be included in all
copies or substantial portions of the Software.

THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
SOFTWARE.

This module is a heavily adapted version of the original ironbar BatteryController
submission, modified for 5-minute ticks and integrated into the Home Assistant FSM.
"""

import logging
from functools import lru_cache

import numpy as np

from .base import BatteryStateMachine, FSMContext, FSMResult

_LOGGER = logging.getLogger(__name__)

CACHE_MAX_SIZE = 2**20

class Period(object):
    def __init__(self, price_sell, price_buy, load, pv, balance, timesteps=None):
        self.price_sell = price_sell
        self.price_buy = price_buy
        self.load = load
        self.pv = pv
        self.balance = balance
        self.timesteps = timesteps
        self._len = len(price_buy)

    def __len__(self):
        return self._len

class FakeBattery:
    def __init__(self, capacity, current_charge, charge_limit, discharge_limit):
        self.capacity = capacity
        # charge state in percentage (0-1)
        self.current_charge = current_charge
        self.charging_power_limit = charge_limit
        self.discharging_power_limit = discharge_limit
        self.charging_efficiency = 0.95
        self.discharging_efficiency = 0.95

class PeriodOptimizer(object):
    def __init__(self, period, battery, allow_end_optimization=True):
        self.period = period
        self.battery = battery
        self.period_summary = summarize_period(period, battery)
        self._initial_battery_charge = self.battery.current_charge

        self.original_cost = None
        self.baseline_cost = None
        self.policy = None
        self.cost = None
        self.max_charge_variations = self._compute_max_charge_variation()
        self.balance_matches = self._compute_exact_balance_match()
        self.is_low_price = self._compute_is_low_price(3)
        self.is_wait_condition = self._compute_is_low_price(1)
        self.allow_end_optimization = allow_end_optimization

    def optimize(self):
        # We need to use integer epochs here: 0, 1, ..., len
        initial_charge = float(self.battery.current_charge)
        self.cost, self.policy = self._find_best_cost_and_policy(initial_charge, 0, len(self.period_summary))
        return self.policy

    @lru_cache(maxsize=CACHE_MAX_SIZE)
    def _find_best_cost_and_policy(self, initial_charge, initial_epoch, end_epoch):
        initial_charge = round(initial_charge, 5) # Prevent cache miss due to floats
        if initial_epoch == end_epoch:
            return 0, []

        target_charge_range = self._get_target_battery_range(initial_charge, initial_epoch)
        costs = []
        paths = []
        for target_charge in target_charge_range:
            cost = self._block_cost(initial_charge, target_charge, initial_epoch)
            ret = self._find_best_cost_and_policy(target_charge, initial_epoch+1, end_epoch)
            costs.append(cost + ret[0])
            paths.append([target_charge] + ret[1])

        if not costs:
            return 999999, []

        min_index = np.argmin(costs)
        return costs[min_index], paths[min_index]

    @lru_cache(maxsize=CACHE_MAX_SIZE)
    def _get_target_battery_range(self, current_charge, block_idx):
        balance_match = self.balance_matches[block_idx]
        target_battery_range = [current_charge + balance_match]

        max_battery_charge, max_battery_discharge = self.max_charge_variations[block_idx]

        # FIX: Always allow the solver to explore doing nothing (idling)
        target_battery_range.append(current_charge)

        if balance_match > 0:
            pass
        else:
            if self.is_wait_condition[block_idx]:
                if block_idx < len(self.period_summary) - 1:
                    next_balance_match = self.balance_matches[block_idx+1]
                    target_battery = - next_balance_match
                    battery_change = target_battery - current_charge
                    if target_battery - current_charge > 0:
                        battery_change = np.minimum(battery_change, max_battery_charge)
                    else:
                        battery_change = np.maximum(battery_change, max_battery_discharge)
                    target_battery_range.append(current_charge + battery_change)

        if self.is_low_price[block_idx]:
            target_battery_range.append(current_charge + max_battery_charge)

        optimize_end = self.allow_end_optimization and len(self.period_summary) - block_idx < 4
        if optimize_end:
            target_battery_range.append(current_charge + max_battery_discharge)
            target_battery_range.append(current_charge)

        target_battery_range = np.clip(target_battery_range, 0, 1).round(5)
        target_battery_range = np.unique(target_battery_range)
        return target_battery_range

    @lru_cache(maxsize=CACHE_MAX_SIZE)
    def _block_cost(self, current_charge, target_charge, block_idx):
        battery_energy = (target_charge - current_charge)*self.battery.capacity
        if battery_energy > 0:
            battery_energy /= self.battery.charging_efficiency
        else:
            battery_energy *= self.battery.discharging_efficiency
        balance = self.period_summary.balance[block_idx]
        total_balance = balance + battery_energy

        if total_balance < 0:
            price_sell = self.period_summary.price_sell[block_idx]
            cost = total_balance*price_sell
        else:
            price_buy = self.period_summary.price_buy[block_idx]
            cost = total_balance*price_buy
        return cost/1000

    def _compute_max_charge_variation(self):
        max_charge_variations = []
        for block_idx, _ in enumerate(self.period_summary.balance):
            # ADAPTATION: 5-minute ticks -> hours = timesteps * (5/60)
            hours = self.period_summary.timesteps[block_idx] * (5.0 / 60.0)
            max_battery_charge = hours*self.battery.charging_power_limit/self.battery.capacity*self.battery.charging_efficiency
            max_battery_discharge = hours*(-self.battery.discharging_power_limit)/self.battery.capacity/self.battery.discharging_efficiency
            # Ensure discharge is negative logic
            if max_battery_discharge > 0:
                max_battery_discharge = -max_battery_discharge
            max_charge_variations.append((max_battery_charge, max_battery_discharge))
        return max_charge_variations

    def _compute_exact_balance_match(self):
        balance_matches = []
        for block_idx, _ in enumerate(self.period_summary.balance):
            battery_change = energy_to_battery_change(-self.period_summary.balance[block_idx], self.battery)
            max_battery_charge, max_battery_discharge = self.max_charge_variations[block_idx]
            if battery_change > 0:
                balance_matches.append(np.minimum(battery_change, max_battery_charge))
            else:
                balance_matches.append(np.maximum(battery_change, max_battery_discharge))
        return balance_matches

    def _compute_is_low_price(self, n_blocks):
        prices = self.period_summary.price_buy
        is_low_price = np.zeros_like(prices)
        if len(prices) > n_blocks:
            for i in range(1, n_blocks + 1):
                mask = prices[:-i] < prices[i:]
                is_low_price[:-i][mask] = 1
        return is_low_price

    def get_fine_grain_policy(self, n_steps_required=None):
        fine_grain_policy = []
        policy = [self._initial_battery_charge] + self.policy
        timestep_idx = 0
        for i, n_steps in enumerate(self.period_summary.timesteps):
            block_timestep_balances = self.period.balance[timestep_idx:timestep_idx + n_steps]
            fine_grain_policy += get_fine_grain_policy_for_block(
                i, policy, self.period_summary.balance, block_timestep_balances, self.battery)
            timestep_idx += n_steps
            if n_steps_required is not None and timestep_idx >= n_steps_required:
                break
        return fine_grain_policy

    def get_fine_grain_policy_for_timestep(self, timestep_idx, timestep_balance, current_charge):
        policy = [self._initial_battery_charge] + self.policy
        if len(policy) < 2:
            return current_charge # Failsafe

        next_charge = get_fine_grain_policy_for_timestep(
            timestep_idx, policy, balances=self.period_summary.balance,
            timestep_balance=timestep_balance, battery=self.battery,
            block_length=self.period_summary.timesteps[0],
            current_charge=current_charge)
        return next_charge


def summarize_period(period, battery=None):
    balance, price_buy, price_sell, timesteps = [], [], [], []
    energy_balance = period.balance
    if battery is not None:
        # ADAPTATION: Multiply by 5/60 to translate kW to kWh for a 5 min chunk
        energy_balance = np.clip(
            energy_balance, -battery.discharging_power_limit*(5.0/60.0), battery.charging_power_limit*(5.0/60.0))

    start_points, end_points = find_division_points(period)
    for start, end in zip(start_points, end_points):
        balance.append((energy_balance[start:end]).sum())
        price_buy.append(period.price_buy[start])
        price_sell.append(period.price_sell[start])
        timesteps.append(end-start)

    period = Period(np.asarray(price_sell), np.asarray(price_buy), None, None, np.asarray(balance), timesteps)
    return period

def find_division_points(period):
    price_buy_change_points = _find_price_change_points(period.price_buy)
    price_sell_change_points = _find_price_change_points(period.price_sell)
    balance_change_points = _find_balance_change_points(period)

    # Pad to length
    division_points = price_buy_change_points + price_sell_change_points + balance_change_points
    division_points = np.arange(len(division_points))[division_points > 0] + 1
    start_points = [0] + division_points.tolist()
    end_points = division_points.tolist() + [len(period)]
    return start_points, end_points

def _find_price_change_points(prices):
    if len(prices) < 2:
        return np.array([])
    price_change_points = prices[:-1] - prices[1:]
    price_change_points[price_change_points != 0] = 1
    return price_change_points

def _find_balance_change_points(period):
    energy_balance = period.balance
    if len(energy_balance) < 2:
        return np.array([])
    energy_balance = np.sign(energy_balance)
    balance_change_points = energy_balance[:-1] - energy_balance[1:]
    balance_change_points[balance_change_points != 0] = 1
    return balance_change_points

def get_fine_grain_policy_for_block(i, policy, balances, timestep_balances, battery):
    battery_change = policy[i+1] - policy[i]
    balance = balances[i]
    initial_charge = policy[i]
    n_steps = len(timestep_balances)

    if battery_change == 0:
        return [initial_charge]*n_steps
    elif balance*battery_change < 0:
        return _sincronize_battery_and_system(
            initial_charge=policy[i], final_charge=policy[i+1], balance=balance,
            battery=battery, timestep_balances=timestep_balances)
    else:
        return _distribute_change_over_timesteps(n_steps, initial_charge=policy[i],
                                                 final_charge=policy[i+1])

def _sincronize_battery_and_system(initial_charge, final_charge, balance, battery, timestep_balances):
    battery_energy = battery_change_to_energy(final_charge - initial_charge, battery)
    if balance == 0:
        return [initial_charge]*len(timestep_balances)
    ratio = battery_energy / balance
    fine_grain_policy = []
    previous_charge = initial_charge
    for timestep_balance in timestep_balances:
        battery_change = _timestep_balance_to_battery_change(timestep_balance, ratio, battery)
        current_charge = previous_charge + battery_change
        fine_grain_policy.append(current_charge)
        previous_charge = current_charge
    fine_grain_policy = np.clip(fine_grain_policy, np.min((initial_charge, final_charge)),
                                np.max((initial_charge, final_charge))).tolist()
    return fine_grain_policy

def _timestep_balance_to_battery_change(timestep_balance, ratio, battery):
    timestep_balance *= ratio
    # ADAPTATION: 5 min chunk
    timestep_balance = apply_battery_power_limit(timestep_balance, 5.0/60.0, battery)
    battery_change = energy_to_battery_change(timestep_balance, battery)
    return battery_change

def _distribute_change_over_timesteps(n_steps, initial_charge, final_charge):
    fine_grain_policy = np.linspace(final_charge, initial_charge, n_steps, endpoint=False)
    fine_grain_policy = fine_grain_policy[::-1].tolist()
    return fine_grain_policy

def get_fine_grain_policy_for_timestep(timestep_idx, policy, balances,
                                       timestep_balance, battery, block_length,
                                       current_charge):
    block_idx = 0
    initial_charge = policy[block_idx]
    final_charge = policy[block_idx+1]
    battery_change = final_charge - initial_charge
    balance = balances[block_idx]

    remaining_steps = block_length - timestep_idx
    if remaining_steps < 1:
        return current_charge

    if timestep_balance != 0 and timestep_balance * balance < 0:
        return current_charge

    if battery_change == 0:
        return current_charge
    elif balance*battery_change < 0:
        battery_energy = battery_change_to_energy(final_charge - initial_charge, battery)
        if balance == 0:
            return current_charge
        ratio = battery_energy / balance
        r_batt_change = _timestep_balance_to_battery_change(timestep_balance, ratio, battery)
        next_charge = current_charge + r_batt_change
        next_charge = np.clip(next_charge, np.min((initial_charge, final_charge)),
                                    np.max((initial_charge, final_charge))).tolist()
        return next_charge
    else:
        return (final_charge - current_charge)/remaining_steps + current_charge

def battery_change_to_energy(battery_change, battery):
    energy = battery_change*battery.capacity
    is_charging = energy > 0
    if is_charging:
        energy /= battery.charging_efficiency
    else:
        energy *= battery.discharging_efficiency
    return energy

def energy_to_battery_change(energy, battery):
    is_charging = energy > 0
    if is_charging:
        energy *= battery.charging_efficiency
    else:
        energy /= battery.discharging_efficiency
    battery_change = energy / battery.capacity
    return battery_change

def apply_battery_power_limit(energy, hours, battery):
    return np.clip(energy, -battery.discharging_power_limit*hours, battery.charging_power_limit*hours)

# ==========================================================
# WRAPPER FOR FSM
# ==========================================================

class DpBatteryController(object):
    def __init__(self):
        self.epoch = 0
        self.optimizer = None
        self.timestep_idx = 0
        self.before_previous_balance = None

        # 5-min intervals: 12 per hr * 24 hr = 288
        self.PERIOD_DURATION = 288
        self.FORECAST_LENGTH = 288

    def propose_state_of_charge(self, battery, current_balance, price_sell, price_buy, pv_forecast, load_forecast):
        # We completely bypass the Keras coefficient logic and rely only on the actual DP math
        epochs_to_end = self.PERIOD_DURATION - self.epoch

        balance = load_forecast - pv_forecast
        balance[0] = current_balance

        if epochs_to_end < self.FORECAST_LENGTH:
            price_sell = price_sell[:epochs_to_end]
            price_buy = price_buy[:epochs_to_end]
            load_forecast = load_forecast[:epochs_to_end]
            pv_forecast = pv_forecast[:epochs_to_end]
            balance = balance[:epochs_to_end]

        period = Period(price_sell, price_buy, load_forecast, pv_forecast, balance)

        optimizer = PeriodOptimizer(period, battery, allow_end_optimization=False)
        self.optimizer = optimizer
        optimizer.optimize()

        next_state = optimizer.get_fine_grain_policy_for_timestep(
            self.timestep_idx, current_balance, battery.current_charge)

        # Failsafe
        if next_state is None:
            next_state = battery.current_charge

        self.timestep_idx = 0  # Re-evaluate perfectly every tick in FSM
        self.epoch += 1
        return next_state


class DpBatteryStateMachine(BatteryStateMachine):
    """
    Experimental implementation using Dynamic Programming translation from Data Competition.
    """
    def __init__(self):
        self.controller = DpBatteryController()

    def calculate_next_state(self, context: FSMContext) -> FSMResult:
        forecast_len = min(
            len(context.forecast_price),
            len(context.forecast_solar),
            len(context.forecast_load)
        )
        if forecast_len < 1:
            return FSMResult(state="IDLE", limit_kw=0.0, reason="Forecast too short")

        number_step = min(forecast_len, 288)
        self.controller.PERIOD_DURATION = number_step
        self.controller.FORECAST_LENGTH = number_step

        price_buy = np.zeros(number_step)
        price_sell = np.zeros(number_step)
        for t in range(number_step):
            if isinstance(context.forecast_price[t], dict):
                price_buy[t] = float(context.forecast_price[t].get("import_price", 0.0))
                price_sell[t] = float(context.forecast_price[t].get("export_price", 0.0))
            else:
                price_buy[t] = float(context.current_price)
                price_sell[t] = float(context.current_price * 0.8)

        load_f = np.zeros(number_step)
        pv_f = np.zeros(number_step)
        for t in range(number_step):
            if isinstance(context.forecast_solar[t], dict):
                pv_f[t] = float(context.forecast_solar[t].get("kw", 0.0))
            else:
                pv_f[t] = float(context.forecast_solar[t])

            if isinstance(context.forecast_load[t], dict):
                load_f[t] = float(context.forecast_load[t].get("kw", 0.0))
            else:
                load_f[t] = float(context.forecast_load[t])

        capacity = max(13.5, context.config.get("battery_capacity", context.config.get("capacity_kwh", 27.0)))
        limit_kw = max(6.3, context.config.get("inverter_limit", context.config.get("inverter_limit_kw", 10.0)))
        current_soc_perc = max(0.0, min(100.0, context.soc)) / 100.0

        battery = FakeBattery(
            capacity=capacity,
            current_charge=current_soc_perc,
            charge_limit=limit_kw,
            discharge_limit=limit_kw
        )

        current_balance = context.load_power - context.solar_production

        # To avoid infinite cache explosion across ticks, clear the cache inside the FSM
        c1 = PeriodOptimizer._find_best_cost_and_policy
        if hasattr(c1, "cache_clear"):
            c1.cache_clear()
        c2 = PeriodOptimizer._get_target_battery_range
        if hasattr(c2, "cache_clear"):
            c2.cache_clear()
        c3 = PeriodOptimizer._block_cost
        if hasattr(c3, "cache_clear"):
            c3.cache_clear()

        try:
            target_soc_perc = self.controller.propose_state_of_charge(
                battery, current_balance, price_sell, price_buy, pv_f, load_f
            )
        except Exception as e:
            _LOGGER.error("DP Solver failed: %s", e)
            return FSMResult(state="IDLE", limit_kw=0.0, reason=f"DP Solver Error: {e}")

        if target_soc_perc is None:
            return FSMResult(state="IDLE", limit_kw=0.0, reason="DP returned None")

        target_soc_perc = float(target_soc_perc)

        # Convert the DP Target SoC percentage into an FSM Action Limit Kw
        target_delta_kwh = (target_soc_perc - current_soc_perc) * capacity

        # Convert kwh to kw (5 minute intervals means * 12)
        power_kw = target_delta_kwh * 12.0

        if power_kw > 0.1:
            req_power = power_kw / battery.charging_efficiency
            return FSMResult(state="CHARGE_GRID", limit_kw=round(min(limit_kw, req_power), 2), reason="DP Optimized Charge")
        elif power_kw < -0.1:
            req_power = abs(power_kw) * battery.discharging_efficiency
            return FSMResult(state="DISCHARGE_HOME", limit_kw=round(min(limit_kw, req_power), 2), reason="DP Optimized Discharge")

        return FSMResult(state="IDLE", limit_kw=0.0, reason="DP Optimization: Idle optimal")
