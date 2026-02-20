"""Web Dashboard for House Battery Control.

Provides:
- Dashboard view with power flow SVG + status
- Plan table (24h look-ahead, 5-min intervals)
- JSON API for status + health check

Registers with HA's built-in aiohttp server via hass.http.register_view().
"""
import logging
from datetime import datetime
from typing import Any

from aiohttp import web
from homeassistant.components.http import HomeAssistantView

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

    table = []
    cumulative = 0.0

    for i, rate in enumerate(rates):
        start = rate["start"]
        price = rate.get("price", 0.0)

        # Solar forecast lookup (by index, matching 5-min intervals)
        pv_kw = 0.0
        if i < len(solar_forecast):
            pv_kw = solar_forecast[i].get("kw", 0.0) if isinstance(solar_forecast[i], dict) else 0.0

        # Load forecast lookup
        load_kw = 0.0
        if i < len(load_forecast):
            load_kw = load_forecast[i] if isinstance(load_forecast[i], (int, float)) else 0.0

        # Temperature forecast lookup (nearest hour match)
        temp_c = None
        if weather and isinstance(start, datetime):
            closest = weather[0]
            min_diff = abs((start - closest["datetime"]).total_seconds()) if "datetime" in closest else float("inf")
            for w in weather:
                if "datetime" in w:
                    diff = abs((start - w["datetime"]).total_seconds())
                    if diff < min_diff:
                        min_diff = diff
                        closest = w
            temp_c = closest.get("temperature")

        # Net power flow for interval cost (5 min = 1/12 hour)
        net_import_kw = load_kw - pv_kw  # positive = importing
        interval_kwh = net_import_kw * (5.0 / 60.0)
        interval_cost = interval_kwh * price / 100.0  # price is c/kWh → dollars

        # SoC forecast (simplified: linear projection based on net flow)
        soc_delta = (net_import_kw * -1.0) * (5.0 / 60.0) / capacity * 100.0
        soc = max(0.0, min(100.0, soc + soc_delta))

        cumulative += interval_cost

        # Inverter limit as % of max
        inverter_pct = min(100.0, (abs(net_import_kw) / inverter_limit) * 100.0) if inverter_limit > 0 else 0.0

        table.append({
            "Time": start.strftime("%H:%M") if isinstance(start, datetime) else str(start),
            "Import Rate": f"{price:.1f}",
            "Export Rate": f"{price * 0.8:.1f}",  # Simplified: export = 80% of import
            "FSM State": state,
            "Inverter Limit": f"{inverter_pct:.0f}%",
            "PV Forecast": f"{pv_kw:.2f}",
            "Load Forecast": f"{load_kw:.2f}",
            "Air Temp Forecast": f"{temp_c:.1f}°C" if temp_c is not None else "—",
            "SoC Forecast": f"{soc:.1f}%",
            "Interval Cost": f"${interval_cost:.4f}",
            "Cumulative Total": f"${cumulative:.2f}",
        })

    return table


def build_status_data(data: dict[str, Any]) -> dict[str, Any]:
    """Extract status fields for the JSON API."""
    return {
        "soc": data.get("soc", 0.0),
        "solar_power": data.get("solar_power", 0.0),
        "grid_power": data.get("grid_power", 0.0),
        "battery_power": data.get("battery_power", 0.0),
        "load_power": data.get("load_power", 0.0),
        "current_price": data.get("current_price", 0.0),
        "state": data.get("state", "IDLE"),
        "reason": data.get("reason", ""),
    }


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
    requires_auth = True

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
    requires_auth = True

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
            "SoC Forecast", "Interval Cost", "Cumulative Total",
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
    requires_auth = True

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
