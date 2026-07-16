# Implementation Plan: UX Sensor Units

**Branch**: `061-ux-sensor-units` | **Date**: 2026-07-16 | **Spec**: [spec.md](file:///C:/Users/markn/OneDrive%20-%20IXL%20Signalling/0-01%20AI%20Programming/AI%20Coding/House%20Battery%20Control/specs/061-ux-sensor-units/spec.md)
**Input**: Feature specification from `/specs/061-ux-sensor-units/spec.md`
**Constraints**: SDD, TDD, Tests before code.

## Summary

Improve the configuration flow UX by clearly labeling whether sensors should be Power (W/kW) or Energy (Wh/kWh). Add unit-awareness to the backend so sensors reporting in `W` or `Wh` are automatically scaled to `kW` or `kWh` by dividing by 1000. This auto-scaling ensures the backend equations and the frontend dashboard remain robust regardless of the user's sensor unit configurations.

## Technical Context

**Language/Version**: Python 3.12 (Home Assistant Custom Component)  
**Primary Dependencies**: Home Assistant core APIs  
**Testing**: Pytest (TDD required - write tests before code)  
**Target Platform**: Home Assistant OS / Core  
**Project Type**: Home Assistant Integration (Backend + Frontend Config Flow)  

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

No constitution file found, proceeding with standard Home Assistant architectural patterns.

## Project Structure

### Documentation (this feature)

```text
specs/061-ux-sensor-units/
├── plan.md              # This file
├── research.md          # Research output
├── data-model.md        # Data models
├── quickstart.md        # Feature instructions
├── tasks.md             # Tasks to be implemented
```

### Source Code

```text
custom_components/house_battery_control/
├── config_flow.py       # Needs updated schema / descriptions for config fields
├── strings.json         # Needs updated English translations for the config flow
├── translations/en.json # Needs updated English translations for the config flow
├── coordinator.py       # Needs to fetch unit_of_measurement and scale values if W/Wh
├── sensor.py            # If dashboard sensors pass-through raw data, they need to reflect the normalized kW/kWh values
tests/
├── test_coordinator.py  # Tests for unit scaling (TDD)
```

**Structure Decision**: Standard Home Assistant Custom Component structure.

## Proposed Changes

### 1. Translations Update (config_flow UX)
Update `strings.json` and `translations/en.json` to include explicit explanations for every sensor field.
- **Power Sensors** (Solar, Grid, Battery, Load): Add description explaining it expects an instantaneous rate in Watts (W) or Kilowatts (kW).
- **Energy Sensors** (Solar Today, Load Today, etc): Add description explaining it expects an accumulated amount in Watt-hours (Wh) or Kilowatt-hours (kWh).

### 2. Auto-scaling Logic in `coordinator.py`
Add logic in `coordinator.py` to read the state object instead of just the state string, so we can access `state.attributes.get('unit_of_measurement')`.
- If the unit is `W` or `Wh`, divide the float value by 1000.
- If the unit is missing, assume `kW` or `kWh` to preserve backwards compatibility.

### 3. TDD - Tests Before Code
- Create unit tests in `tests/` verifying that `_get_sensor_value` (or equivalent method in `coordinator.py`) properly scales values when the mocked state object has a `unit_of_measurement` of `W`.
- Run tests (they should fail).
- Implement code.
- Run tests (they should pass).

## Verification Plan

### Automated Tests
- The commands of any automated tests you'll run: `pytest tests/test_coordinator.py` (specifically targeting the new scaling logic).

### Manual Verification
- Deploy to a local Home Assistant instance.
- Configure a mock sensor reporting `3000` with unit `W`.
- Verify the integration dashboard displays `3.0 kW`.
- Verify the config flow UI shows the new descriptive text for Power vs Energy.
