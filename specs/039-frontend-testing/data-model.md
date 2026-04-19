# Phase 1: Data Model & Contracts

This feature primarily sets up a testing framework. The data models relevant here are the mock data structures required to render the LitElement components correctly during tests.

## HBC Component Data Payload Model (Mock Schema)
The components expect a `data` property with the following shape:

```json
{
  "soc": 55.5,
  "solar_power": 3.2,
  "grid_power": -1.5,
  "load_power": 1.7,
  "battery_power": 0.0,
  "current_price": 15.2,
  "import_today": 12.4,
  "export_today": 5.1,
  "state": "SELF_CONSUMPTION",
  "reason": "Supporting household load",
  "no_import_periods": "",
  "observation_mode": false,
  "last_update": "2026-04-19T10:00:00Z",
  "sensors": [
    { "entity_id": "sensor.example", "state": "OK", "available": true }
  ],
  "plan": [
    {
      "Time": "10:00",
      "Local Time": "10:00 AM",
      "Import Rate": "15.0",
      "Export Rate": "5.0",
      "FSM State": "SELF_CONSUMPTION",
      "Inverter Limit": "0%",
      "Net Grid": "-1.00",
      "PV Forecast": "3.00",
      "Load Forecast": "2.00",
      "Air Temp Forecast": "22.5",
      "Temp Delta": "0.0",
      "Load Adj.": "0.0",
      "SoC Forecast": "55.0",
      "Interval Cost": "0.0",
      "Cumul. Cost": "1.50",
      "Acq. Cost": "10.0"
    }
  ]
}
```

## API Contracts
There are no new HTTP API endpoints being introduced. The contract is strictly the internal Web Component property binding (`.data=${payload}`) established in `hbc-panel.js`.
