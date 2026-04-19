import {
  LitElement,
  html,
  css,
} from "https://unpkg.com/lit-element@2.4.0/lit-element.js?module";

export class HBCDashboard extends LitElement {
  static get properties() {
    return {
      data: { type: Object },
    };
  }

  constructor() {
    super();
    this.data = {};
  }

  _calculateSummaryStats() {
    const plan = this.data.plan || [];
    if (plan.length === 0) {
      return { avgImport: "0.00", avgExport: "0.00", totalPV: "0.0", totalLoad: "0.0" };
    }

    const parseNum = (str) => parseFloat(String(str).replace(/[^0-9.-]+/g, "")) || 0;

    let sumImport = 0;
    let sumExport = 0;
    let sumPVKw = 0;
    let sumLoadKw = 0;

    plan.forEach(r => {
      sumImport += parseNum(r["Import Rate"]);
      sumExport += parseNum(r["Export Rate"]);
      sumPVKw += parseNum(r["PV Forecast"]);
      sumLoadKw += parseNum(r["Load Forecast"]);
    });

    const count = plan.length;
    return {
      avgImport: (sumImport / count).toFixed(2),
      avgExport: (sumExport / count).toFixed(2),
      // kW to kWh over 5-minute intervals (divide by 12)
      totalPV: (sumPVKw / 12).toFixed(1),
      totalLoad: (sumLoadKw / 12).toFixed(1)
    };
  }

  _formatLastUpdate() {
    const raw = this.data.last_update;
    if (!raw) return "—";
    try {
      const d = new Date(raw);
      if (isNaN(d.getTime())) return raw;
      return d.toLocaleString([], { dateStyle: "short", timeStyle: "medium" });
    } catch (e) {
      return raw;
    }
  }

  render() {
    const d = this.data;
    const soc = d.soc !== undefined ? d.soc : 0;
    const solar = d.solar_power !== undefined ? d.solar_power : 0;
    const grid = d.grid_power !== undefined ? d.grid_power : 0;
    const load = d.load_power !== undefined ? d.load_power : 0;
    const battery = d.battery_power !== undefined ? d.battery_power : 0;
    const price = d.current_price !== undefined ? d.current_price : 0;
    const plan = d.plan || [];
    const export_price = plan.length > 0 ? parseFloat(plan[0]["Export Rate"] || 0) : 0;
    const import_today = d.import_today !== undefined ? d.import_today : 0;
    const export_today = d.export_today !== undefined ? d.export_today : 0;
    const state = d.state || "IDLE";
    const reason = d.reason || "";
    const noImportPeriods = d.no_import_periods || "";
    const observationMode = d.observation_mode || false;
    const summaryStats = this._calculateSummaryStats();

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
            <div class="flow-icon">⚡</div>
            <div class="flow-value">${battery}</div>
            <div class="flow-label">Battery kW</div>
          </div>
          <div class="flow-item house">
            <div class="flow-icon">🏠</div>
            <div class="flow-value">${load}</div>
            <div class="flow-label">House kW</div>
          </div>
          <div class="flow-item soc-item">
            <div class="flow-icon">🔋</div>
            <div class="flow-value">${soc}%</div>
            <div class="flow-label">SoC</div>
          </div>
        </div>
      </div>
      <div class="card">
        <div class="status-grid">
          <div class="stat">
            <div class="stat-value">${price}</div>
            <div class="stat-label">Import c/kWh</div>
          </div>
          <div class="stat">
            <div class="stat-value">${export_price}</div>
            <div class="stat-label">Export c/kWh</div>
          </div>
          <div class="stat">
            <div class="stat-value">${import_today}</div>
            <div class="stat-label">Import kWh</div>
          </div>
          <div class="stat">
            <div class="stat-value">${export_today}</div>
            <div class="stat-label">Export kWh</div>
          </div>
          <div class="stat">
            <div class="state-badge">${state}</div>
            <div class="stat-label">${reason}</div>
          </div>
        </div>
      </div>
      ${(noImportPeriods || observationMode) ? html`
      <div class="constraints-bar">
        ${observationMode ? html`<span class="constraint-badge observation">👁 Observation Mode</span>` : ''}
        ${noImportPeriods ? html`<span class="constraint-badge no-import">🚫 No-Import: ${noImportPeriods}</span>` : ''}
      </div>
      ` : ''}
      <div class="card">
        <h2>24-Hour Forecast Summary</h2>
        <div class="status-grid">
          <div class="stat">
            <div class="stat-value">${summaryStats.avgImport}</div>
            <div class="stat-label">Avg Import c/kWh</div>
          </div>
          <div class="stat">
            <div class="stat-value">${summaryStats.avgExport}</div>
            <div class="stat-label">Avg Export c/kWh</div>
          </div>
          <div class="stat">
            <div class="stat-value">${summaryStats.totalPV}</div>
            <div class="stat-label">Total Gen kWh</div>
          </div>
          <div class="stat">
            <div class="stat-value">${summaryStats.totalLoad}</div>
            <div class="stat-label">Total Load kWh</div>
          </div>
          <div class="stat">
            <div class="stat-value">${(d.acquisition_cost || 0).toFixed(2)}</div>
            <div class="stat-label">Acq Cost c/kWh</div>
          </div>
        </div>
      </div>
      <div class="meta" style="text-align: center; padding: 8px 0; opacity: 0.6; font-size: 0.85em;">
        Plan last ran: ${this._formatLastUpdate()}
      </div>
    `;
  }

  static get styles() {
    return css`
      :host {
        display: block;
        font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif;
      }
      .card {
        background: #1a1a3e;
        border-radius: 12px;
        padding: 20px;
        margin-bottom: 16px;
        box-shadow: 0 4px 12px rgba(0, 0, 0, 0.4);
        color: #e0e0e0;
      }
      h2 {
        color: #00d4ff;
        margin: 0 0 16px;
        font-size: 18px;
        font-weight: 500;
        user-select: none;
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

      /* Active Constraints Bar */
      .constraints-bar {
        display: flex;
        gap: 10px;
        flex-wrap: wrap;
        padding: 8px 0;
      }
      .constraint-badge {
        display: inline-block;
        padding: 6px 14px;
        border-radius: 16px;
        font-size: 13px;
        font-weight: 600;
      }
      .constraint-badge.no-import {
        background: linear-gradient(135deg, #ff8c00, #cc6600);
        color: #fff;
      }
      .constraint-badge.observation {
        background: linear-gradient(135deg, #ff4444, #cc0000);
        color: #fff;
      }
      .meta {
        color: #e0e0e0;
      }
    `;
  }
}

customElements.define("hbc-dashboard", HBCDashboard);
