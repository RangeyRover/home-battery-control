# Feature Specification: Fix Timezone Offset in Synthetic Array Integration

## 1. Feature Description
The Home Battery Control (HBC) plan currently appends synthesized 48-hour arrays to the rates timeline. However, the time indices lookup between the plan generation (which uses UTC time hours) and the synthetic array generation (which is aligned to Local Time indices 0-287) are misaligned. This timezone mismatch results in the load and pricing values being offset (shifted) in the 48-hour plan timeline when looking forward. 

This feature will correct the `tod_idx` mapping in `coordinator.py` to correctly resolve the local time representation of the interval before determining the array index.

## 2. User Scenarios
* **Scenario 1:** The user checks the 48-hour outlook plan table at any time of day. The predicted load curves and price curves visually line up with expected local patterns (e.g. high load during local evening peak), rather than being shifted backwards or forwards by the UTC timezone offset.

## 3. Functional Requirements
1. **Timezone Context Awareness:** When appending synthetic array values (`synthetic_pricing_curve`, `synthetic_export_curve`, `synthetic_load_curve`) into the `extended_rates_timeline`, the system must calculate the lookup index `tod_idx` based on the local timezone equivalent of the `start` UTC datetime.
2. **Backward Compatibility:** The existing UTC timestamp format of `extended_rates_timeline` items must be preserved (e.g. `start` and `end` remain in UTC) so the solver can still parse them.
3. **No Synthetic Logic Modification:** The algorithm for generating the synthetic arrays inside `rates_predictor.py` must remain unchanged as it already correctly outputs arrays normalized to local time midnights.

## 4. Success Criteria
* The load and price arrays appended to the `plan` timeline table align perfectly with the "Raw Synthesized Data" debug table indices based on local time.
* The system continues to solve and generate a plan without crashing.
* Tests validate the timezone index alignment.

## 5. Assumptions & Dependencies
* The Home Assistant system `dt_util` time utility correctly returns the local timezone of the configured location.
* The synthesized arrays contain exactly 288 elements mapping from local midnight (00:00) to local end-of-day (23:55) in 5-minute intervals.
