# Feature Specification: Solver Synthetic Integration

## 1. Feature Description
Integrate the 48-hour synthetic outlook data directly into the battery control solver path. The system will append synthesized price and load data to the end of the known actual forecast data, extending the solver's look-ahead horizon to cover the next day. The solver will use actual forecasts where available, relying on synthetic data only to fill in the gaps up to the 48-hour mark.

## 2. User Scenarios & Testing

**Scenario 1: Extending a Partial Forecast**
- *Given* the system has actual price and load forecasts for the next 18 hours.
- *When* the solver input is prepared.
- *Then* the system appends 30 hours of synthetic data to the end, resulting in a 48-hour plan length.

**Scenario 2: Full Forecast Available**
- *Given* the system has actual price and load forecasts for a full 48 hours.
- *When* the solver input is prepared.
- *Then* the system uses the actual data entirely without appending any synthetic data.

**Scenario 3: Short Forecast Available**
- *Given* the system only has 2 hours of actual forecast remaining (e.g., late at night).
- *When* the solver input is prepared.
- *Then* the system appends 46 hours of synthetic data, providing the solver with a clear view of tomorrow's peaks.

## 3. Functional Requirements

1. **Data Append Logic**: The system MUST append synthesized price, export price, and load data to the solver input arrays *only* after the actual forecast data has been exhausted.
2. **Prioritization of Actuals**: The system MUST NOT overwrite any actual forecast data with synthetic data.
3. **Variable Plan Length Support**: The solver MUST gracefully handle varying plan lengths resulting from the append operation, ensuring out-of-bounds errors do not occur.
4. **Data Synchronization**: The length of the appended price, export, and load arrays MUST perfectly match so that each interval corresponds correctly.

## 4. Success Criteria

- The battery optimizer extends its planning horizon seamlessly past the end of the actual forecast.
- No actual forecast data is ever discarded in favor of synthetic data.
- The system continues to operate without crashing or array-length mismatch errors during plan generation.

## 5. Assumptions & Dependencies

- **Assumption**: The existing solver (DP/LP FSM) is already capable of handling dynamically sized input arrays (varying plan lengths) natively.
- **Dependency**: The synthetic generation feature (Feature 037/046) is successfully generating 48 hours of baseline data.

## 6. Needs Clarification

None.
