import {
  LitElement,
  html,
  css,
} from "https://unpkg.com/lit-element@2.4.0/lit-element.js?module";

class HBCPanel extends LitElement {
  static get properties() {
    return {
      hass: { type: Object },
      narrow: { type: Boolean },
      panel: { type: Object },
      _activeTab: { type: String },
      _data: { type: Object },
      _error: { type: String },
      _loading: { type: Boolean },
    };
  }

  constructor() {
    super();
    this._activeTab = "dashboard";
    this._data = {};
    this._error = "";
    this._loading = true;
    this._interval = null;
  }

  connectedCallback() {
    super.connectedCallback();
    this._fetchData();
    this._interval = setInterval(() => this._fetchData(), 30000);
  }

  disconnectedCallback() {
    super.disconnectedCallback();
    if (this._interval) clearInterval(this._interval);
  }

  async _fetchData() {
    try {
      const resp = await fetch("/hbc/api/status");
      if (!resp.ok) throw new Error(`HTTP ${resp.status}`);
      this._data = await resp.json();
      this._error = "";
    } catch (e) {
      this._error = e.message;
    }
    this._loading = false;
  }

  _switchTab(tab) {
    this._activeTab = tab;
  }

  // ── Dashboard Tab ──────────────────────────────────────
  _renderDashboard() {
    const d = this._data;
    const soc = (d.soc || 0).toFixed(0);
    const solar = (d.solar_power || 0).toFixed(1);
    const grid = (d.grid_power || 0).toFixed(1);
    const load = (d.load_power || 0).toFixed(1);
    const battery = (d.battery_power || 0).toFixed(1);
    const price = (d.current_price || 0).toFixed(1);
    const state = d.state || "IDLE";
    const reason = d.reason || "";

    return html`
      <div class="card">
        <h2>Power Flow</h2>
        <div class="flow-grid">
          <div class="flow-item solar">
            <div class="flow-icon">☀️</div>
            <div class="flow-value">${solar}</div>
            <div class="flow-label">Solar kW</div>
          </div>
          <div class="flow-item grid-item">
            <div class="flow-icon">🔌</div>
            <div class="flow-value">${grid}</div>
            <div class="flow-label">Grid kW</div>
          </div>
          <div class="flow-item battery-item">
            <div class="flow-icon">🔋</div>
            <div class="flow-value">${battery}</div>
            <div class="flow-label">Battery kW</div>
          </div>
          <div class="flow-item house">
            <div class="flow-icon">🏠</div>
            <div class="flow-value">${load}</div>
            <div class="flow-label">House kW</div>
          </div>
        </div>
      </div>
      <div class="card">
        <div class="status-grid">
          <div class="stat">
            <div class="stat-value">${soc}%</div>
            <div class="stat-label">SoC</div>
          </div>
          <div class="stat">
            <div class="stat-value">${price}</div>
            <div class="stat-label">Price c/kWh</div>
          </div>
          <div class="stat">
            <div class="state-badge">${state}</div>
            <div class="stat-label">${reason}</div>
          </div>
        </div>
      </div>
      ${this._renderSensors()}
    `;
  }

  // ── Sensor Diagnostics (Spec 2.4) ─────────────────────
  _renderSensors() {
    const sensors = this._data.sensors || [];
    if (sensors.length === 0) return html``;

    return html`
      <div class="card">
        <h2>Sensor Status</h2>
        <table>
          <thead><tr><th>Entity</th><th>State</th><th>Status</th></tr></thead>
          <tbody>
            ${sensors.map(
      (s) => html`
                <tr>
                  <td>${s.entity_id}</td>
                  <td>${s.state}</td>
                  <td>
                    <span class="badge ${s.available ? "ok" : "err"}">
                      ${s.available ? "✓" : "✗"}
                    </span>
                  </td>
                </tr>
              `
    )}
          </tbody>
        </table>
        <div class="meta">
          Last update: ${this._data.last_update || "—"} |
          Update #${this._data.update_count || 0}
        </div>
      </div>
    `;
  }

  // ── Plan Tab ───────────────────────────────────────────
  _renderPlan() {
    const plan = this._data.plan || [];

    if (plan.length === 0) {
      return html`<div class="card"><p>No plan data available yet.</p></div>`;
    }

    const cols = [
      "Time",
      "Local Time",
      "Import",
      "Export",
      "State",
      "Limit",
      "PV",
      "Load",
      "Temp",
      "SoC",
      "Cost",
      "Total",
    ];

    const rows = plan.map((r) => {
      return {
        time: r["Time"] || "—",
        localTime: r["Local Time"] || "—",
        imp: r["Import Rate"] || "0.0",
        exp: r["Export Rate"] || "0.0",
        state: r["FSM State"] || "—",
        limit: r["Inverter Limit"] || "0%",
        pv: r["PV Forecast"] || "0.00",
        ld: r["Load Forecast"] || "0.00",
        temp: r["Air Temp Forecast"] || "—",
        soc: r["SoC Forecast"] || "—",
        cost: r["Interval Cost"] || "$0.0000",
        total: r["Cumulative Total"] || "$0.00",
      };
    });

    return html`
      <div class="card table-card">
        <h2>24-Hour Plan</h2>
        <div class="table-wrap">
          <table>
            <thead>
              <tr>
                ${cols.map((c) => html`<th>${c}</th>`)}
              </tr>
            </thead>
            <tbody>
              ${rows.map(
      (r) => html`
                  <tr>
                    <td>${r.time}</td>
                    <td>${r.localTime}</td>
                    <td>${r.imp}</td>
                    <td>${r.exp}</td>
                    <td>${r.state}</td>
                    <td>${r.limit}</td>
                    <td>${r.pv}</td>
                    <td>${r.ld}</td>
                    <td>${r.temp}</td>
                    <td>${r.soc}</td>
                    <td>${r.cost}</td>
                    <td>${r.total}</td>
                  </tr>
                `
    )}
            </tbody>
          </table>
        </div>
      </div>
    `;
  }

  render() {
    if (this._loading) {
      return html`<div class="root"><p>Loading...</p></div>`;
    }
    if (this._error) {
      return html`<div class="root"><div class="card err-card">Error: ${this._error}</div></div>`;
    }

    return html`
      <div class="root">
        <div class="header">
          <h1>⚡ House Battery Control</h1>
          <div class="tabs">
            <button
              class="${this._activeTab === "dashboard" ? "active" : ""}"
              @click=${() => this._switchTab("dashboard")}
            >
              Dashboard
            </button>
            <button
              class="${this._activeTab === "plan" ? "active" : ""}"
              @click=${() => this._switchTab("plan")}
            >
              Plan
            </button>
          </div>
        </div>
        ${this._activeTab === "dashboard"
        ? this._renderDashboard()
        : this._renderPlan()}
      </div>
    `;
  }

  static get styles() {
    return css`
      :host {
        display: block;
        background: #0f0f23;
        color: #e0e0e0;
        min-height: 100vh;
        font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto,
          sans-serif;
      }
      .root {
        max-width: 1200px;
        margin: 0 auto;
        padding: 20px;
      }
      .header {
        display: flex;
        align-items: center;
        justify-content: space-between;
        margin-bottom: 20px;
        flex-wrap: wrap;
        gap: 12px;
      }
      h1 {
        color: #00d4ff;
        margin: 0;
        font-size: 24px;
      }
      h2 {
        color: #00d4ff;
        margin: 0 0 16px;
        font-size: 18px;
      }
      .tabs {
        display: flex;
        gap: 4px;
        background: #1a1a3e;
        border-radius: 8px;
        padding: 4px;
      }
      .tabs button {
        background: transparent;
        color: #8888aa;
        border: none;
        padding: 8px 20px;
        border-radius: 6px;
        cursor: pointer;
        font-size: 14px;
        transition: all 0.2s;
      }
      .tabs button.active {
        background: #00d4ff;
        color: #0f0f23;
        font-weight: 600;
      }
      .tabs button:hover:not(.active) {
        color: #e0e0e0;
      }
      .card {
        background: #1a1a3e;
        border-radius: 12px;
        padding: 20px;
        margin-bottom: 16px;
        box-shadow: 0 4px 12px rgba(0, 0, 0, 0.4);
      }
      .err-card {
        background: #3e1a1a;
        color: #ff6b6b;
      }

      /* Power Flow Grid */
      .flow-grid {
        display: grid;
        grid-template-columns: repeat(auto-fit, minmax(140px, 1fr));
        gap: 12px;
      }
      .flow-item {
        background: #12122a;
        border-radius: 10px;
        padding: 16px;
        text-align: center;
        border: 1px solid #2a2a5e;
        transition: transform 0.2s;
      }
      .flow-item:hover {
        transform: translateY(-2px);
      }
      .flow-icon {
        font-size: 28px;
        margin-bottom: 8px;
      }
      .flow-value {
        font-size: 28px;
        font-weight: 700;
        color: #00d4ff;
      }
      .flow-label {
        font-size: 12px;
        color: #8888aa;
        margin-top: 4px;
      }
      .solar .flow-value {
        color: #ffd700;
      }
      .battery-item .flow-value {
        color: #00ff88;
      }

      /* Status Grid */
      .status-grid {
        display: grid;
        grid-template-columns: repeat(auto-fit, minmax(120px, 1fr));
        gap: 12px;
      }
      .stat {
        text-align: center;
      }
      .stat-value {
        font-size: 24px;
        font-weight: 700;
        color: #00d4ff;
      }
      .stat-label {
        font-size: 12px;
        color: #8888aa;
        margin-top: 4px;
      }
      .state-badge {
        display: inline-block;
        padding: 6px 16px;
        border-radius: 20px;
        background: linear-gradient(135deg, #00d4ff, #0088cc);
        color: #0f0f23;
        font-weight: 700;
        font-size: 14px;
      }

      /* Tables */
      .table-card {
        overflow: hidden;
      }
      .table-wrap {
        overflow-x: auto;
      }
      table {
        width: 100%;
        border-collapse: collapse;
        font-size: 13px;
      }
      th {
        background: #12122a;
        color: #00d4ff;
        padding: 10px 8px;
        text-align: left;
        white-space: nowrap;
        position: sticky;
        top: 0;
      }
      td {
        padding: 8px;
        border-bottom: 1px solid #2a2a5e;
      }
      tr:nth-child(even) {
        background: #15153a;
      }
      .badge {
        display: inline-block;
        width: 20px;
        height: 20px;
        border-radius: 50%;
        text-align: center;
        line-height: 20px;
        font-size: 12px;
      }
      .badge.ok {
        background: #00ff88;
        color: #0f0f23;
      }
      .badge.err {
        background: #ff6b6b;
        color: #0f0f23;
      }
      .meta {
        margin-top: 12px;
        font-size: 11px;
        color: #666688;
      }
    `;
  }
}

customElements.define("hbc-panel", HBCPanel);
