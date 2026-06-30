"""Constants for the House Battery Control integration."""

DOMAIN = "house_battery_control"

# Config Keys
CONF_BATTERY_SOC_ENTITY = "battery_soc_entity"
CONF_BATTERY_POWER_ENTITY = "battery_power_entity"
CONF_BATTERY_POWER_INVERT = "battery_power_invert"
CONF_SOLAR_ENTITY = "solar_entity"
CONF_GRID_ENTITY = "grid_entity"
CONF_GRID_POWER_INVERT = "grid_power_invert"
CONF_IMPORT_PRICE_ENTITY = "import_price_entity"
CONF_EXPORT_PRICE_ENTITY = "export_price_entity"
CONF_USE_AMBER_EXPRESS = "use_amber_express"
CONF_CURRENT_IMPORT_PRICE_ENTITY = "current_import_price_entity"
CONF_CURRENT_EXPORT_PRICE_ENTITY = "current_export_price_entity"
CONF_WEATHER_ENTITY = "weather_entity"
CONF_SOLCAST_TODAY_ENTITY = "solcast_today_entity"
CONF_SOLCAST_TOMORROW_ENTITY = "solcast_tomorrow_entity"
CONF_LOAD_POWER_ENTITY = "load_power_entity"
CONF_LOAD_TODAY_ENTITY = "load_today_entity"
CONF_IMPORT_TODAY_ENTITY = "import_today_entity"
CONF_EXPORT_TODAY_ENTITY = "export_today_entity"

# Telemetry Cost Tracker Keys
CONF_TRACKER_IMPORT_PRICE = "tracker_import_price"
CONF_TRACKER_EXPORT_PRICE = "tracker_export_price"

# Load Prediction Calibrations
CONF_LOAD_SENSITIVITY_HIGH_TEMP = "load_high_temp_sensitivity"  # kW per deg above threshold
CONF_LOAD_SENSITIVITY_LOW_TEMP = "load_low_temp_sensitivity"  # kW per deg below threshold
CONF_LOAD_HIGH_TEMP_THRESHOLD = "load_high_temp_threshold"  # e.g. 25C
CONF_LOAD_LOW_TEMP_THRESHOLD = "load_low_temp_threshold"  # e.g. 15C
CONF_LOAD_CACHE_TTL = "load_cache_ttl_minutes"  # Cache refresh interval in minutes

# Calibration
CONF_BATTERY_CAPACITY = "battery_capacity"
CONF_BATTERY_CHARGE_RATE_MAX = "battery_rate_max"
CONF_INVERTER_LIMIT_MAX = "inverter_limit"
CONF_RESERVE_SOC = "reserve_soc"

# Control (Teslemetry/PW)
CONF_ALLOW_CHARGE_FROM_GRID_ENTITY = "allow_charge_entity"
CONF_ALLOW_EXPORT_ENTITY = "allow_export_entity"

# Scripts (Spec 3.6)
CONF_SCRIPT_CHARGE = "script_charge"
CONF_SCRIPT_CHARGE_STOP = "script_charge_stop"
CONF_SCRIPT_DISCHARGE = "script_discharge"
CONF_SCRIPT_DISCHARGE_STOP = "script_discharge_stop"

# Observation Mode
CONF_OBSERVATION_MODE = "observation_mode"

# Acquisition Cost Override (one-shot)
CONF_ACQ_COST_OVERRIDE = "acq_cost_override"
CONF_ACQ_COST_OVERRIDE_VALUE = "acq_cost_override_value"

# No-Import Periods (demand charge windows)
CONF_NO_IMPORT_PERIODS = "no_import_periods"

# Config Keys for Feature 054
CONF_ROUND_TRIP_EFFICIENCY = "round_trip_efficiency"
CONF_EXPORT_MARGIN = "export_margin"

# Config Keys for Feature 055 (Low Renewables Guard)
CONF_GUARD_RENEWABLES_THRESHOLD = "guard_renewables_threshold"
CONF_GUARD_OVERNIGHT_DEADLINE = "guard_overnight_deadline"
CONF_GUARD_DAYTIME_DEADLINE = "guard_daytime_deadline"
CONF_GUARD_PEAK_SOLAR = "guard_peak_solar"
CONF_GUARD_TRIGGER_MODE = "guard_trigger_mode"
CONF_GUARD_LOW_SOLAR_THRESHOLD = "guard_low_solar_threshold"

# Panel
CONF_PANEL_ADMIN_ONLY = "panel_admin_only"

# Default Values
DEFAULT_BATTERY_CAPACITY = 27.0
DEFAULT_BATTERY_RATE_MAX = 6.3
DEFAULT_INVERTER_LIMIT = 10.0
DEFAULT_RESERVE_SOC = 0.0
DEFAULT_PANEL_ADMIN_ONLY = True
DEFAULT_CURRENCY = "c/kWh"
DEFAULT_ROUND_TRIP_EFFICIENCY = 0.90
DEFAULT_EXPORT_MARGIN = 0.0
DEFAULT_SCAN_INTERVAL = 300
# 5 minutes
DEFAULT_LOAD_CACHE_TTL = 360  # 6 hours in minutes
DEFAULT_USE_AMBER_EXPRESS = False
DEFAULT_SOLCAST_TODAY = "sensor.solcast_pv_forecast_today"
DEFAULT_SOLCAST_TOMORROW = "sensor.solcast_pv_forecast_tomorrow"

# Feature 055 Defaults
DEFAULT_GUARD_RENEWABLES_THRESHOLD = 30.0
DEFAULT_GUARD_OVERNIGHT_DEADLINE = "05:00"
DEFAULT_GUARD_DAYTIME_DEADLINE = "15:00"
DEFAULT_GUARD_PEAK_SOLAR = 40.0
DEFAULT_GUARD_TRIGGER_MODE = "OR"
DEFAULT_GUARD_LOW_SOLAR_THRESHOLD = 50.0

# States (match System Requirements §16)
STATE_CHARGE_GRID = "CHARGE_GRID"
STATE_DISCHARGE_GRID = "DISCHARGE_GRID"
STATE_SELF_CONSUMPTION = "SELF_CONSUMPTION"
STATE_ERROR = "ERROR"

# Attributes
ATTR_STATE_REASON = "reason"
ATTR_PLAN_HTML = "plan_html"
