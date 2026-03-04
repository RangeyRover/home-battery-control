# Troubleshooting

Common issues and their solutions.

---

## Dashboard Shows No Data

**Symptoms**: HBC panel loads but shows blank cards or "N/A" values.

**Causes**:
1. **Sensor entities not configured correctly** — Check Settings → Devices → House Battery Control and verify all configured entities show valid states (not "unavailable" or "unknown")
2. **Integration not loaded** — Check HA logs for `house_battery_control` errors: Settings → System → Logs → search for `hbc`
3. **First run delay** — The integration needs one full 5-minute cycle to populate data. Wait 5 minutes after initial setup.

**Fix**: Verify your entity IDs are correct in the integration options. The most common mistake is selecting the wrong entity from a list of similarly-named sensors.

---

## FSM Is Stuck in SELF_CONSUMPTION

**Symptoms**: `sensor.hbc_state` shows "SELF_CONSUMPTION" permanently, no battery commands are sent.

**Causes**:
1. **No tariff data** — The Amber Electric integration isn't providing forecast data. Check that your import/export price sensors have a `forecast` attribute with future prices.
2. **No solar forecast** — Solcast sensors are empty. Check that `sensor.solcast_pv_forecast_today` has a `forecast` attribute.
3. **Solver finds inaction optimal** — If prices are flat and solar is zero, SELF_CONSUMPTION may genuinely be the optimal choice.
4. **No control scripts configured** — HBC is in observation/debug mode. Configure scripts in Step 3 to enable control.

**Fix**: Navigate to `/hbc/api/status` (admin auth required) and check the `sensor_diagnostics` section for any sensors showing `available: false`.

---

## Battery Power Shows Wrong Direction

**Symptoms**: The power flow diagram shows the battery charging when it's actually discharging, or vice versa.

**Fix**: Toggle the **Invert Battery Power** option in Settings → Integrations → House Battery Control → Configure → Telemetry.

Different inverter brands report power direction differently. Positive values should mean discharging (power flowing out of battery). If your sensor reports charging as positive, enable inversion.

---

## Grid Power Direction Is Wrong

**Symptoms**: Grid import shows as export on the dashboard, or vice versa.

**Fix**: Toggle the **Invert Grid Power** option in Telemetry settings. The convention is positive = importing from grid.

---

## Panel Not Visible in Sidebar

**Symptoms**: After installation, there's no "HBC" entry in the left sidebar.

**Causes**:
1. **Admin-only mode** — By default, the panel is only visible to admin users. Check you're logged in as an admin.
2. **Panel visibility setting** — Go to Configure → Control Services and check the "Panel Visible to Admins Only" toggle. Turn it OFF to make the panel visible to all users.
3. **Integration not loaded** — Check Settings → Devices & Services for the House Battery Control card.

---

## 401 Unauthorized on API Endpoints

**Symptoms**: Visiting `/hbc/api/status` or `/hbc/api/ping` returns "401: Unauthorized".

**This is expected behaviour.** All HBC API endpoints require admin authentication. Access them through the HBC panel (which handles auth automatically) or use a valid Bearer token.

---

## Sensors Show "Unavailable"

**Symptoms**: HBC sensors show "unavailable" in the entity list.

**Causes**:
1. **Prerequisite integration not set up** — HBC depends on Amber Electric, Solcast, and Tesla integrations. If any are missing or misconfigured, their sensors will be unavailable.
2. **Entity ID changed** — If you renamed or reconfigured a prerequisite integration, the entity IDs may have changed. Update them in HBC's configuration.
3. **Integration error** — Check HA logs for `house_battery_control` ERROR entries.

**Fix**: Go to Settings → Integrations → House Battery Control → Configure and verify all entity IDs are valid.

---

## HBC Without Amber or Solcast

**Symptoms**: Integration loads but the solver doesn't seem to optimise effectively.

**Explanation**: HBC still loads and runs without Amber or Solcast, but with reduced capabilities:

- **Without Amber**: No price forecast is available. The solver sees flat/zero prices and defaults to `SELF_CONSUMPTION` — it has no price signal to arbitrage against.
- **Without Solcast**: No solar forecast. The solver assumes zero PV generation, which may cause excessive grid charging during cheap windows that solar would have covered for free.

HBC will not crash or refuse to load — it gracefully degrades. Check `/hbc/api/status` → `sensor_diagnostics` to see which data sources are available.

---

## Getting Help

- **GitHub Issues**: [Report a bug](https://github.com/RangeyRover/home-battery-control/issues)
- **GitHub Discussions**: [Ask a question](https://github.com/RangeyRover/home-battery-control/discussions)
- **Diagnostics API**: Visit `/hbc/api/status` for full system state including sensor availability
