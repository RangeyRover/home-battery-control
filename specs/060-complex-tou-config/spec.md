# 060 Complex TOU Config

## Problem Statement

The current Fixed Time-of-Use (TOU) configuration only supports a single contiguous Peak window and a single Off-peak window for import prices, with no configurable parameters for Feed-in Tariffs (FiT). This structure fails to accommodate complex energy plans, such as those with multiple peak periods per day (e.g., 6:00 AM - 10:00 AM and 3:00 PM - 1:00 AM) and distinct FiT rates (e.g., Morning Peak FiT, Evening Peak FiT, and Off-Peak FiT). Users with these complex schedules currently cannot accurately model their tariffs, leading to suboptimal battery dispatch logic.

## Target Audience

Users on Fixed Time-of-Use tariffs that feature multiple peak/off-peak windows or dynamic, time-based export rates.

## User Scenarios & Testing

### Scenario 1: Configuring Multiple Import Peaks
- **Setup:** A user has a tariff with Peak prices from 6 AM - 10 AM and 3 PM - 1 AM.
- **Action:** The user enters the integration configuration for Fixed TOU.
- **Result:** The user is able to define both Peak windows accurately, along with Shoulder and Off-Peak times.

### Scenario 2: Configuring Time-of-Use Export Tariffs (FiT)
- **Setup:** A user has a tariff with an Evening Peak FiT from 5 PM - 9 PM, and a base FiT for all other times.
- **Action:** The user configures the Fixed TOU export pricing within the integration.
- **Result:** The user can specify the time window for the Evening Peak FiT and set the base rate for all other times, resulting in an accurate 48-hour export price forecast.

## Functional Requirements

- **FR-1:** The integration configuration must allow users to define a set of predefined import pricing blocks (up to 10), each with a start time, end time, and price (c/kWh).
- **FR-2:** The integration configuration must allow users to define a set of predefined export pricing blocks (FiT) (up to 10), each with a start time, end time, and price (c/kWh).
- **FR-3:** The Fixed TOU generator must combine these blocks to generate a continuous 48-hour forecast that correctly reflects both import and export prices for any given 5-minute interval.
- **FR-4:** The configuration flow must validate that the provided periods cover exactly 24 hours (00:00 to 00:00) with no gaps and no overlaps. Unused periods are ignored. If validation fails, the configuration cannot be saved.
- **FR-5:** Periods cannot cross midnight. If a pricing tier spans across midnight (e.g., 3:00 PM to 1:00 AM), the user must configure it as two separate periods (3:00 PM to 00:00, and 00:00 to 1:00 AM).

The UI will utilize a fixed set of predefined period fields (up to 10 for Import, 10 for Export) to manage complexity while maintaining compatibility with Home Assistant's Config Flow. Validation logic will ignore blank fields, but will strictly enforce that the sum of the populated periods totals exactly 24 hours (starting at 00:00 and ending at 00:00) without gaps or overlaps before allowing the configuration to be saved.

## Non-Functional Requirements

- The forecasting logic must execute quickly (under 1 second) so it doesn't delay integration startup or updates.

## Success Criteria

- Users can successfully configure complex TOU schedules (e.g., two peak import periods and two peak export periods) without workarounds.
- The generated 48-hour forecast accurately applies both import and export prices at the correct times of the day, handling midnight roll-overs appropriately.

## Dependencies & Assumptions

- **Assumptions:** Users understand their tariff structures. We assume times are evaluated in the local timezone of the Home Assistant instance, accounting for DST.
- **Breaking Change:** This new configuration schema (with up to 10 periods) replaces the legacy 3-tier Fixed TOU schema (`fixed_tou_peak_start`, etc.). Existing Fixed TOU configurations will not be automatically migrated and users on this mode will need to re-enter their configuration after upgrading. Configuration is otherwise retained across standard updates.
