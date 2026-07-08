# Implementation Plan: 058 - Fix Amber Express Mapping & Solar Guard Refinement

## Goal Description

1. **Amber Express Fix**: Address the disconnect between the UI configuration and the backend parsing logic. When "Use Amber Express" is toggled, the user correctly inputs the detailed Amber Express sensors into the "Current Import/Export" fields as instructed by the UI. However, the `RatesManager` incorrectly attempts to extract the 24-hour nested forecast array from the standard forecast entities instead. This causes a fallback to generic pricing (`per_kwh`).
2. **Solar Guard**: Verify and refine the `solcast_today` guard logic to ensure that on days with extremely poor expected solar yield, the battery proactively charges from the grid to 100% ahead of the evening peak.

## Proposed Changes

### Configuration Mapping Fix

#### [MODIFY] [strings.json](file:///C:/Users/markn/OneDrive%20-%20IXL%20Signalling/0-01%20AI%20Programming/AI%20Coding/House%20Battery%20Control/custom_components/house_battery_control/strings.json)
- Update the wording for `use_amber_express` in both `step.energy` and `options.step.energy` to be more explicit: `"Use Amber Express advanced pricing (if detailed sensors configured)"`.

#### [MODIFY] [coordinator.py](file:///C:/Users/markn/OneDrive%20-%20IXL%20Signalling/0-01%20AI%20Programming/AI%20Coding/House%20Battery%20Control/custom_components/house_battery_control/coordinator.py)
Update `RatesManager` instantiation to correctly pass the "Current" (detailed) entities when Amber Express mode is active:
- Read `use_amber_express = config.get(CONF_USE_AMBER_EXPRESS, False)`
- For import entity: conditionally pick `CONF_CURRENT_IMPORT_PRICE_ENTITY` if `use_amber_express` is True, with a safe fallback to `CONF_IMPORT_PRICE_ENTITY`.
- For export entity: conditionally pick `CONF_CURRENT_EXPORT_PRICE_ENTITY` if `use_amber_express` is True, with a safe fallback to `CONF_EXPORT_PRICE_ENTITY`.

### Solar Guard Verification & Tests

#### [MODIFY] [tests/test_renewables_guard.py](file:///C:/Users/markn/OneDrive%20-%20IXL%20Signalling/0-01%20AI%20Programming/AI%20Coding/House%20Battery%20Control/tests/test_renewables_guard.py)
- The Solar Guard feature (`Feature 056`) is already physically present in the code in `renewables_guard.py` (via `solcast_today`). I will write explicit unit tests to ensure that when `solcast_today` is below the configured threshold, the Guard triggers correctly and outputs the daytime deadline indices for the FSM.

## Verification Plan

### Automated Tests
- Run `pytest tests/test_renewables_guard.py` to prove the Solcast Today guard effectively triggers the daytime deadline.

### Manual Verification
- A visual review of the `Amber Express` fix directly addressing the user's report (the plan will now show the interpolated detailed prices like `1.6011` for low-renewable export intervals rather than the `per_kwh` generic forecast).
