"""Web Dashboard for House Battery Control.

Provides:
- Dashboard view with power flow SVG + status
- Plan table (24h look-ahead, 5-min intervals)
- JSON API for status + health check

Registers with HA's built-in aiohttp server via hass.http.register_view().
"""
import logging
from datetime import datetime, timedelta
from typing import Any

import yaml
from aiohttp import web
from homeassistant.components.http import HomeAssistantView
from homeassistant.util import dt as dt_util

from .const import DOMAIN

_LOGGER = logging.getLogger(__name__)


# ============================================================
# DATA HELPERS (pure functions, tested independently)
# ============================================================

def build_plan_table(data: dict[str, Any]) -> list[dict[str, Any]]:
    """Build a plan table from coordinator data.

    Returns a list of row dicts with columns matching system_requirements.md 2.2:
    Time, Import Rate, Export Rate, FSM State, Inverter Limit,
    PV Forecast, Load Forecast, Air Temp Forecast, SoC Forecast,
    Interval Cost, Cumulative Total.
    """
    rates = data.get("rates", [])
    solar_forecast = data.get("solar_forecast", [])
    load_forecast = data.get("load_forecast", [])
    weather = data.get("weather", [])
    capacity = data.get("capacity", 27.0)
    inverter_limit = data.get("inverter_limit", 10.0)
    state = data.get("state", "IDLE")
    soc = data.get("soc", 50.0)

    # Pre-parse Solar by Hour
    solar_by_hour = {}
    for s in solar_forecast:
        if not isinstance(s, dict):
            continue
        start_str = s.get("period_start") or s.get("start", "")
        if not start_str:
            continue
        try:
            st = dt_util.parse_datetime(start_str)
            if st:
                key = (st.year, st.month, st.day, st.hour)
                val = float(s.get("pv_estimate", s.get("kw", 0.0)))
                solar_by_hour[key] = solar_by_hour.get(key, 0.0) + val
        except (ValueError, TypeError):
            pass

    # Pre-parse Load
    parsed_loads = []
    for lf in load_forecast:
        if not isinstance(lf, dict):
            continue
        start_str = lf.get("start", "")
        if not start_str:
            continue
        try:
            st = dt_util.parse_datetime(start_str)
            if st:
                parsed_loads.append({"start": st, "kw": float(lf.get("kw", 0.0))})
        except (ValueError, TypeError):
            pass

    # Pre-parse Weather
    parsed_weather = []
    for w in weather:
        if not isinstance(w, dict):
            continue
        if "datetime" in w and isinstance(w["datetime"], datetime):
            parsed_weather.append(w)
        else:
            w_time = w.get("datetime")
            if isinstance(w_time, str):
                w_time = dt_util.parse_datetime(w_time)
            if isinstance(w_time, datetime):
                parsed_weather.append({"datetime": w_time, "temperature": w.get("temperature")})

    table = []
    cumulative = 0.0

    for rate in rates:
        start = rate["start"]
        end = rate.get("end", start + timedelta(minutes=30))
        price = rate.get("import_price", rate.get("price", 0.0))
        export_price = rate.get("export_price", price * 0.8)

        if not isinstance(start, datetime) or not isinstance(end, datetime):
            continue

        duration_mins = max(1, int((end - start).total_seconds() / 60.0))
        duration_hours = duration_mins / 60.0

        # Solar forecast lookup (average of all overlapping blocks)
        matched_solar = [
            float(s.get("pv_estimate", s.get("kw", 0.0)))
            for s in solar_forecast
            if isinstance(s, dict)
            and dt_util.parse_datetime(s.get("period_start", "") if isinstance(s.get("period_start", ""), str) else (s.get("period_start").isoformat() if s.get("period_start") else s.get("start", "").isoformat() if not isinstance(s.get("start", ""), str) else s.get("start", "")))
            and start <= dt_util.parse_datetime(s.get("period_start", "") if isinstance(s.get("period_start", ""), str) else (s.get("period_start").isoformat() if s.get("period_start") else s.get("start", "").isoformat() if not isinstance(s.get("start", ""), str) else s.get("start", ""))) < end
        ]
        
        # Determine average power in kW for this row
        pv_kw_avg = sum(matched_solar) / len(matched_solar) if matched_solar else 0.0
        
        # Calculate true energy in kWh for this row
        pv_kwh = pv_kw_avg * duration_hours

        # Load forecast lookup (average of all overlapping blocks)
        matched_loads = [lf["kw"] for lf in parsed_loads if start <= lf["start"] < end]
        load_kw_avg = sum(matched_loads) / len(matched_loads) if matched_loads else 0.0

        # Temperature lookup (nearest neighbor)
        temp_c = None
        if parsed_weather:
            closest = min(parsed_weather, key=lambda w: abs((start - w["datetime"]).total_seconds()))
            temp_c = closest.get("temperature")

        # Net power flow for interval cost
        net_import_kw = load_kw_avg - pv_kw_avg  # positive = importing
        interval_kwh = net_import_kw * duration_hours
        interval_cost = interval_kwh * price / 100.0  # price is c/kWh → dollars

        # SoC forecast (simplified: linear projection based on net flow)
        soc_delta = (net_import_kw * -1.0) * duration_hours / capacity * 100.0
        soc = max(0.0, min(100.0, soc + soc_delta))

        cumulative += interval_cost

        # Inverter limit as % of max
        inverter_pct = min(100.0, (abs(net_import_kw) / inverter_limit) * 100.0) if inverter_limit > 0 else 0.0

        table.append({
            "Time": start.strftime("%H:%M") if isinstance(start, datetime) else str(start),
            "Import Rate": f"{price:.1f}",
            "Export Rate": f"{export_price:.1f}",
            "FSM State": state,
            "Inverter Limit": f"{inverter_pct:.0f}%",
            "PV Forecast": f"{pv_kwh:.2f}",
            "Load Forecast": f"{load_kw_avg:.2f}",
            "Air Temp Forecast": f"{temp_c:.1f}°C" if temp_c is not None else "—",
            "SoC Forecast": f"{soc:.1f}%",
            "Interval Cost": f"${interval_cost:.4f}",
            "Cumulative Total": f"${cumulative:.2f}",
        })

    return table


def build_status_data(data: dict[str, Any]) -> dict[str, Any]:
    """Pass through ALL coordinator data for API diagnostics (spec 2.4).

    Returns the full coordinator dict with safe defaults for
    sensors, last_update, and update_count.
    """
    result = dict(data)
    # Ensure diagnostic defaults for backward compat
    result.setdefault("sensors", [])
    result.setdefault("last_update", None)
    result.setdefault("update_count", 0)
    return result


def build_power_flow_svg(
    solar_kw: float, grid_kw: float, battery_kw: float,
    load_kw: float, soc: float
) -> str:
    """Generate an SVG power flow diagram.

    Layout: Solar (top-left), Grid (bottom-right),
    Battery (bottom-left), House (centre).
    Lines show energy direction with labels.
    """
    def _arrow_line(x1, y1, x2, y2, label, kw, color):
        if abs(kw) < 0.01:
            return ""
        return (
            f'<line x1="{x1}" y1="{y1}" x2="{x2}" y2="{y2}" '
            f'stroke="{color}" stroke-width="2" marker-end="url(#arrow)"/>'
            f'<text x="{(x1+x2)//2}" y="{(y1+y2)//2 - 5}" '
            f'fill="{color}" font-size="12" text-anchor="middle">{label}: {abs(kw):.1f} kW</text>'
        )

    def _node(cx, cy, label, value, color):
        return (
            f'<circle cx="{cx}" cy="{cy}" r="40" fill="none" stroke="{color}" stroke-width="2"/>'
            f'<text x="{cx}" y="{cy-5}" fill="{color}" font-size="14" '
            f'font-weight="bold" text-anchor="middle">{label}</text>'
            f'<text x="{cx}" y="{cy+15}" fill="{color}" font-size="12" text-anchor="middle">{value}</text>'
        )

    lines = []

    # Nodes: Solar(80,60), House(200,120), Battery(80,200), Grid(320,200)
    lines.append(_node(80, 60, "PV", f"{solar_kw:.1f} kW", "#f59e0b"))
    lines.append(_node(200, 120, "House", f"{load_kw:.1f} kW", "#3b82f6"))
    lines.append(_node(80, 200, "Battery", f"{soc:.0f}%", "#10b981"))
    lines.append(_node(320, 200, "Grid", f"{grid_kw:.1f} kW", "#ef4444"))

    # Arrows
    if solar_kw > 0:
        lines.append(_arrow_line(120, 70, 160, 110, "Solar", solar_kw, "#f59e0b"))
    if battery_kw > 0:  # charging
        lines.append(_arrow_line(160, 130, 120, 190, "Charge", battery_kw, "#10b981"))
    elif battery_kw < 0:  # discharging
        lines.append(_arrow_line(120, 190, 160, 130, "Discharge", battery_kw, "#10b981"))
    if grid_kw > 0:  # importing
        lines.append(_arrow_line(280, 200, 240, 140, "Import", grid_kw, "#ef4444"))
    elif grid_kw < 0:  # exporting
        lines.append(_arrow_line(240, 140, 280, 200, "Export", grid_kw, "#ef4444"))

    body = "\n".join(lines)
    return (
        '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 400 280" '
        'style="max-width:400px;font-family:sans-serif;">'
        '<defs><marker id="arrow" markerWidth="8" markerHeight="6" refX="8" refY="3" orient="auto">'
        '<polygon points="0 0, 8 3, 0 6" fill="#666"/></marker></defs>'
        f'{body}'
        '</svg>'
    )


# ============================================================
# HA HTTP VIEWS
# ============================================================

class HBCDashboardView(HomeAssistantView):
    """Main dashboard: power flow + status."""

    url = "/hbc"
    name = "hbc:dashboard"
    requires_auth = False

    async def get(self, request: web.Request) -> web.Response:
        hass = request.app["hass"]
        data = self._get_coordinator_data(hass)

        svg = build_power_flow_svg(
            solar_kw=data.get("solar_power", 0),
            grid_kw=data.get("grid_power", 0),
            battery_kw=data.get("battery_power", 0),
            load_kw=data.get("load_power", 0),
            soc=data.get("soc", 0),
        )

        status = build_status_data(data)

        html = f"""<!DOCTYPE html>
<html><head><title>House Battery Control</title>
<style>
body {{ font-family: -apple-system, BlinkMacSystemFont, sans-serif; margin: 20px; background: #1a1a2e; color: #e0e0e0; }}
.card {{ background: #16213e; border-radius: 12px; padding: 20px; margin: 10px 0; box-shadow: 0 4px 6px rgba(0,0,0,0.3); }}
h1 {{ color: #e94560; margin: 0 0 20px; }}
.status {{ display: grid; grid-template-columns: repeat(auto-fit, minmax(150px, 1fr)); gap: 10px; }}
.stat {{ background: #0f3460; border-radius: 8px; padding: 12px; text-align: center; }}
.stat-value {{ font-size: 24px; font-weight: bold; color: #e94560; }}
.stat-label {{ font-size: 12px; color: #a0a0a0; margin-top: 4px; }}
.state-badge {{ display: inline-block; padding: 4px 12px; border-radius: 20px; background: #e94560; color: white; font-weight: bold; }}
nav {{ margin-bottom: 20px; }}
nav a {{ color: #e94560; margin-right: 15px; text-decoration: none; }}
nav a:hover {{ text-decoration: underline; }}
</style></head><body>
<nav><a href="/hbc">Dashboard</a> <a href="/hbc/plan">Plan</a></nav>
<h1>House Battery Control</h1>
<div class="card">{svg}</div>
<div class="card">
<div class="status">
  <div class="stat"><div class="stat-value">{status['soc']:.0f}%</div><div class="stat-label">SoC</div></div>
  <div class="stat"><div class="stat-value">{status['solar_power']:.1f}</div><div class="stat-label">Solar kW</div></div>
  <div class="stat"><div class="stat-value">{status['grid_power']:.1f}</div><div class="stat-label">Grid kW</div></div>
  <div class="stat"><div class="stat-value">{status['load_power']:.1f}</div><div class="stat-label">Load kW</div></div>
  <div class="stat"><div class="stat-value">{status['current_price']:.1f}</div><div class="stat-label">Price c/kWh</div></div>
  <div class="stat"><div class="state-badge">{status['state']}</div><div class="stat-label">{status['reason']}</div></div>
</div></div>
</body></html>"""

        return web.Response(text=html, content_type="text/html")

    def _get_coordinator_data(self, hass) -> dict:
        domain_data = hass.data.get(DOMAIN, {})
        for entry_data in domain_data.values():
            coord = entry_data.get("coordinator")
            if coord and coord.data:
                return coord.data
        return {}


class HBCPlanView(HomeAssistantView):
    """24-hour plan table."""

    url = "/hbc/plan"
    name = "hbc:plan"
    requires_auth = False

    async def get(self, request: web.Request) -> web.Response:
        hass = request.app["hass"]
        data = self._get_coordinator_data(hass)
        table = build_plan_table(data)

        rows_html = ""
        for row in table:
            cells = "".join(f"<td>{row[c]}</td>" for c in [
                "Time", "Import Rate", "Export Rate", "FSM State",
                "Inverter Limit", "PV Forecast", "Load Forecast",
                "Air Temp Forecast", "SoC Forecast", "Interval Cost",
                "Cumulative Total",
            ])
            rows_html += f"<tr>{cells}</tr>\n"

        headers = "".join(f"<th>{c}</th>" for c in [
            "Time", "Import Rate", "Export Rate", "FSM State",
            "Inverter Limit", "PV Forecast", "Load Forecast",
            "Air Temp Forecast", "SoC Forecast", "Interval Cost",
            "Cumulative Total",
        ])

        html = f"""<!DOCTYPE html>
<html><head><title>HBC Plan</title>
<style>
body {{ font-family: -apple-system, BlinkMacSystemFont, sans-serif; margin: 20px; background: #1a1a2e; color: #e0e0e0; }}
h1 {{ color: #e94560; }}
table {{ width: 100%; border-collapse: collapse; background: #16213e; border-radius: 8px; overflow: hidden; }}
th {{ background: #0f3460; color: #e94560; padding: 10px 8px; text-align: left; font-size: 12px; }}
td {{ padding: 8px; border-bottom: 1px solid #1a1a2e; font-size: 12px; }}
tr:nth-child(even) {{ background: #1a2744; }}
nav {{ margin-bottom: 20px; }}
nav a {{ color: #e94560; margin-right: 15px; text-decoration: none; }}
</style></head><body>
<nav><a href="/hbc">Dashboard</a> <a href="/hbc/plan">Plan</a></nav>
<h1>24-Hour Plan</h1>
<table><thead><tr>{headers}</tr></thead><tbody>{rows_html}</tbody></table>
</body></html>"""

        return web.Response(text=html, content_type="text/html")

    def _get_coordinator_data(self, hass) -> dict:
        domain_data = hass.data.get(DOMAIN, {})
        for entry_data in domain_data.values():
            coord = entry_data.get("coordinator")
            if coord and coord.data:
                return coord.data
        return {}


class HBCApiStatusView(HomeAssistantView):
    """JSON API: current system status."""

    url = "/hbc/api/status"
    name = "hbc:api:status"
    requires_auth = False

    async def get(self, request: web.Request) -> web.Response:
        hass = request.app["hass"]
        data = self._get_coordinator_data(hass)
        status = build_status_data(data)
        return self.json(status)

    def _get_coordinator_data(self, hass) -> dict:
        domain_data = hass.data.get(DOMAIN, {})
        for entry_data in domain_data.values():
            coord = entry_data.get("coordinator")
            if coord and coord.data:
                return coord.data
        return {}


class HBCApiPingView(HomeAssistantView):
    """JSON API: health check."""

    url = "/hbc/api/ping"
    name = "hbc:api:ping"
    requires_auth = False

    async def get(self, request: web.Request) -> web.Response:
        return self.json({"status": "ok"})


class HBCConfigYamlView(HomeAssistantView):
    """YAML Config Export API (S2)."""

    url = "/hbc/api/config-yaml"
    name = "hbc:api:config-yaml"
    requires_auth = False

    async def get(self, request: web.Request) -> web.Response:
        hass = request.app["hass"]

        # Get config from the first entry we find
        config_data = {}
        domain_data = hass.data.get(DOMAIN, {})
        for entry_data in domain_data.values():
            if "config" in entry_data:
                config_data = dict(entry_data["config"])
                break

        yaml_text = yaml.dump(config_data, default_flow_style=False, sort_keys=True)
        return web.Response(text=yaml_text, content_type="text/yaml")
