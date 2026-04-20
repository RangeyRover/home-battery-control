# Implementation Plan: Solver Synthetic Integration

## 1. Technical Context
- **Objective:** Extend the FSM solver's planning horizon by appending the 24-hour synthetic analog data to the end of the existing actual forecasts (price, export, and load).
- **Current State:** `coordinator.py::_build_solver_inputs` hardcodes `n = 288` (24 hours). If `rates_list` has fewer than 288 elements, it forward-fills the last value. If it has more, it ignores them (Wait, the loop is `range(n)` so it truncates to 288).
- **Target State:** Compute `n` dynamically based on the length of actual data plus the remaining time until the end of "Tomorrow" using the synthetic analog curves.

## 2. Architecture & Approach
### 2.1 Calculating Dynamic `n`
- Instead of `n = 288`, we will determine `n` dynamically.
- `actual_rates_len = len(rates_list)`
- Determine the local time of the last actual rate. Let's say `last_rate_time`.
- Since synthetic data represents "Tomorrow", we will only append synthetic data for times *after* `last_rate_time` up until 23:55 Tomorrow.
- If `last_rate_time` is already beyond Tomorrow, we don't append anything (or just let it extend as far as we have actual rates).

**Step-by-step logic in `coordinator.py`:**
1. Right before `align_forecasts`, we generate an `extended_rates_timeline` by appending mock rate dicts to `rates_list`.
```python
    extended_rates = list(rates_timeline)
    if synthetic_pricing_curve and extended_rates:
        last_rate = extended_rates[-1]["start"]
        target_end = dt_util.now().replace(hour=23, minute=55, second=0, microsecond=0) + timedelta(days=1)
        
        current = last_rate + timedelta(minutes=5)
        while current <= target_end:
            tod_idx = (current.hour * 60 + current.minute) // 5
            extended_rates.append({
                "start": current,
                "end": current + timedelta(minutes=5),
                "import_price": synthetic_pricing_curve[tod_idx],
                "export_price": synthetic_export_curve[tod_idx],
                "synthetic": True,
                "synthetic_load_kw": synthetic_load_curve[tod_idx] if synthetic_load_curve else 0.0
            })
            current += timedelta(minutes=5)
```
2. Then we just use `extended_rates` instead of `rates_list` in `align_forecasts` and `_build_solver_inputs`.
3. In `_build_solver_inputs`, change `n = len(rates_list)`.
4. And for Load, `load_forecast` might be short. Inside `_build_solver_inputs`, instead of `load_kwh[-1]`, we check if the `extended_rates[i]` is `"synthetic": True`, and if so, use `extended_rates[i]["synthetic_load_kw"] * step_hours`.

This approach is VERY clean. It leverages the existing dynamically sized FSM and `align_forecasts` perfectly!

## 3. Data Model Changes
None. The FSM is already capable of variable plan lengths.

## 4. API Contracts
None.

## 5. Verification Plan
- Unit tests to verify that `extended_rates` correctly appends synthetic data.
- Unit tests to verify `_build_solver_inputs` gracefully maps `synthetic_load_curve` to the extended intervals.

## Needs Clarification
None.
