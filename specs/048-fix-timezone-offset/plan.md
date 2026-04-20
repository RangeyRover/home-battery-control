# Implementation Plan: Fix Timezone Offset in Synthetic Array Integration

## User Review Required
No major architectural decisions. This is a targeted timezone mapping bug fix.

## Open Questions
None.

## Proposed Changes

### coordinator.py

#### [MODIFY] coordinator.py
Update the temporal lookup logic when appending synthesized arrays to the rate timeline. 
Convert the `current` UTC datetime into the local timezone before evaluating the `hour` and `minute` components for the index.
```python
        current = last_rate + timedelta(minutes=5)
        while current <= target_end:
            # Convert UTC current to local timezone to calculate the correct Time-of-Day index
            local_current = dt_util.as_local(current)
            tod_idx = (local_current.hour * 60 + local_current.minute) // 5
            
            extended_rates_timeline.append({
                "start": current,  # Keep UTC for solver bounds
                "end": current + timedelta(minutes=5),
                "import_price": synthetic_pricing_curve[tod_idx],
                "export_price": synthetic_export_curve[tod_idx],
                "synthetic": True,
                "synthetic_load_kw": synthetic_load_curve[tod_idx] if synthetic_load_curve else 0.0
            })
            current += timedelta(minutes=5)
```

### Validation Tests

#### [MODIFY] tests/test_coordinator.py
Add a test or modify existing ones to ensure that when `extended_rates_timeline` is appended, the `import_price`, `export_price`, and `synthetic_load_kw` matches the array index corresponding to the *local* time representation of the appended chunk.

## Verification Plan
1. Run `pytest tests/test_coordinator.py` and `pytest tests/test_fsm_lin.py` to ensure no regression.
2. The user will verify visually that the appended rows in the Plan table now line up correctly with the Raw Synthesized Data table based on local time.
