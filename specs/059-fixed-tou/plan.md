# Implementation Plan: Fixed TOU Support

**Branch**: `059-fixed-tou` | **Date**: 2026-07-11 | **Spec**: [spec.md](./spec.md)
**Input**: Feature specification from `/specs/059-fixed-tou/spec.md`

## Summary

Implement Fixed TOU (Time of Use) generation native to the House Battery Control integration. A new global "Pricing Mode" toggle will isolate Dynamic Pricing (Amber) from Fixed TOU in `config_flow.py`. When Fixed TOU is selected, the system relies on user-provided static rates and times to generate a 48-hour forward-looking Amber-style JSON forecast array dynamically using the Home Assistant OS local timezone. 

Per user directive, this implementation strictly follows **TDD (Test-Driven Development)**: all tests for the config flow mode switch and the solver input generator must be written and validated before the core logic is implemented.

## Technical Context

**Language/Version**: Python 3.12+ (Home Assistant Environment)  
**Primary Dependencies**: Home Assistant Core (`config_entries`, `voluptuous`, `dt_util`)  
**Storage**: Config Entry data (`core.config_entries`)  
**Testing**: `pytest`, `pytest-homeassistant-custom-component`, `pytest-asyncio`  
**Target Platform**: Home Assistant OS / Core  
**Project Type**: Home Assistant Custom Integration  
**Performance Goals**: Generate 48-hour forecast in < 50ms per tick  
**Constraints**: Must accurately map UTC to local timezone across DST boundaries.

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

- [x] No complex architectural bloat. Keeps data model local to the integration.
- [x] No external APIs required.
- [x] Follows TDD mandate explicitly.

## Project Structure

### Documentation (this feature)

```text
specs/059-fixed-tou/
├── spec.md              
├── plan.md              # This file
├── checklists/requirements.md
```

### Source Code

```text
custom_components/house_battery_control/
├── config_flow.py       # Update with Pricing Mode branch
├── const.py             # Add CONF_PRICING_MODE and CONF_FIXED_TOU_*
├── coordinator.py       # Branch RatesManager logic based on Pricing Mode
├── fixed_tou.py         # NEW: Contains FixedTOUGenerator class

tests/
├── test_config_flow.py  # Add tests for Fixed TOU isolation
├── test_fixed_tou.py    # NEW: Add tests for generator and DST handling
├── test_coordinator.py  # Update to test the solver input switch
```

## Phase 1: Technical Design & Contracts

### 1. Data Model Additions (`const.py`)
New configuration keys to be added to the schema:
- `CONF_PRICING_MODE`: Enum (`"Amber Dynamic"`, `"Fixed TOU"`)
- `CONF_FIXED_TOU_PEAK_START`: Time (e.g., `"16:00"`)
- `CONF_FIXED_TOU_PEAK_END`: Time (e.g., `"20:00"`)
- `CONF_FIXED_TOU_PEAK_PRICE`: Float
- `CONF_FIXED_TOU_OFFPEAK_START`: Time
- `CONF_FIXED_TOU_OFFPEAK_END`: Time
- `CONF_FIXED_TOU_OFFPEAK_PRICE`: Float
- `CONF_FIXED_TOU_SHOULDER_PRICE`: Float

### 2. Config Flow Isolation (`config_flow.py`)
- **Step 1 (New)**: `async_step_pricing_mode`: Prompts user to select `"Amber Dynamic"` or `"Fixed TOU"`.
- **Step 2 (Branching)**: 
  - If `"Amber Dynamic"`: Proceeds to existing `async_step_energy` requiring entity IDs.
  - If `"Fixed TOU"`: Proceeds to new `async_step_fixed_tou` requiring time/price schedules.

### 3. Generator Logic (`fixed_tou.py`)
Create a `FixedTOUGenerator` class.
- **Method**: `generate_forecast(config: dict, start_time: datetime, hours: int = 48) -> list[dict]`
- **Behavior**: Uses HA `dt_util.now()` timezone. Loops over 5-minute blocks for the requested duration. Maps the block's local time to the configured Peak, Shoulder, or Off-Peak periods. Returns the array formatted identically to the Amber JSON structure (`start_time`, `end_time`, `per_kwh`).

### 4. Integration Point (`coordinator.py` - `RatesManager`)
- Read `self.config.get(CONF_PRICING_MODE)`.
- If `"Fixed TOU"`, bypass sensor state fetching and call `FixedTOUGenerator.generate_forecast()`.

## Phase 2: TDD Testing Plan (Mandatory First Steps)

Before writing the application code, the following tests MUST be written and fail (Red phase):

### Test Group 1: Config Flow Isolation (`test_config_flow.py`)
1. **Test**: Selecting "Fixed TOU" hides Amber entity fields and shows TOU schedule fields.
2. **Test**: Selecting "Amber Dynamic" behaves as legacy, requiring entity IDs.
3. **Test**: Saving Fixed TOU configuration successfully writes data to `mock_hass.config_entries`.

### Test Group 2: Solver Input Switch (`test_coordinator.py`)
1. **Test**: When `CONF_PRICING_MODE` is "Fixed TOU", `RatesManager` successfully generates a valid 48-hour array without looking up Amber entities.
2. **Test**: The solver natively accepts the `RatesManager` output when driven by Fixed TOU (integration test).

### Test Group 3: Fixed TOU Generator & Timezones (`test_fixed_tou.py`)
1. **Test**: Generator creates exactly 48 hours of 5-minute blocks (576 blocks).
2. **Test**: Price correctly maps to Peak, Shoulder, and Off-Peak based on the configured local time windows.
3. **Test (DST Boundary)**: Mock HA local time to cross a Daylight Saving Time boundary (e.g., Australia/Sydney on first Sunday of October/April). Assert that the UTC `start_time` and `end_time` block markers shift smoothly to preserve the correct *local* schedule without missing or duplicating blocks.

---

> [!IMPORTANT]
> The next step is `/05-speckit.tasks` to convert this plan into `tasks.md`. When executing the tasks, we will strictly enforce the **tests before code** mandate.
