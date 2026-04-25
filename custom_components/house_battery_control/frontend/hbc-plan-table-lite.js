import {
  LitElement,
  html,
  css,
} from "https://unpkg.com/lit-element@2.4.0/lit-element.js?module";

export class HBCPlanTableLite extends LitElement {
  static get properties() {
    return {
      hass: { type: Object },
      _planData: { type: Array },
      _planResolution: { type: String },
      _hiddenCols: { type: Array },
      _loading: { type: Boolean },
      _error: { type: String },
      _lastUpdate: { type: String },
    };
  }

  constructor() {
    super();
    this._planData = [];
    this._planResolution = "30min";
    this._hiddenCols = JSON.parse(localStorage.getItem("hbc_hidden_cols") || "[]");
    this._loading = false;
    this._error = "";
    this._lastUpdate = "—";
  }

  connectedCallback() {
    super.connectedCallback();
    if (this.hass) {
      this._fetchPlan();
    }
  }

  updated(changedProps) {
    super.updated(changedProps);
    if (changedProps.has("hass") && this.hass && this._planData.length === 0 && !this._loading) {
      this._fetchPlan();
    }
  }

  async _fetchPlan() {
    this._loading = true;
    this._error = "";
    try {
      const resp = await this.hass.fetchWithAuth("/hbc/api/plan");
      if (!resp.ok) throw new Error(`HTTP ${resp.status}`);
      const json = await resp.json();
      
      // Convert columnar matrix to array of row objects
      const columns = json.columns || [];
      const rows = json.rows || [];
      const plan = rows.map(rowArr => {
        const obj = {};
        columns.forEach((col, idx) => {
          obj[col] = rowArr[idx];
        });
        return obj;
      });
      
      this._planData = plan;
      this._lastUpdate = new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' });
    } catch (err) {
      this._error = err.message || String(err);
    }
    this._loading = false;
  }

  _switchResolution(res) {
    this._planResolution = res;
  }

  _toggleCol(col) {
    let hidden = [...this._hiddenCols];
    if (hidden.includes(col)) {
      hidden = hidden.filter(c => c !== col);
    } else {
      hidden.push(col);
    }
    this._hiddenCols = hidden;
    localStorage.setItem("hbc_hidden_cols", JSON.stringify(hidden));
  }

  _calculateSummaryStats() {
    const plan = this._planData || [];
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
      totalPV: (sumPVKw / 12).toFixed(1),
      totalLoad: (sumLoadKw / 12).toFixed(1)
    };
  }

  render() {
    if (this._loading && this._planData.length === 0) {
      return html`<div class="card"><p>Loading plan data...</p></div>`;
    }
    if (this._error) {
      return html`<div class="card err-card"><p>Error loading plan: ${this._error}</p></div>`;
    }

    const plan = this._planData || [];
    if (plan.length === 0) {
      return html`<div class="card"><p>No plan data available yet.</p></div>`;
    }

    const cols = [
      "Time", "Local Time", "Import", "Export", "State", "Limit", 
      "Net Grid", "PV", "Load", "Temp", "Temp Δ", "Load Adj.", 
      "SoC", "Cost", "Cumul. Cost", "Acq. Cost",
    ];

    const parseNum = (str) => parseFloat(String(str).replace(/[^0-9.-]+/g, "")) || 0;

    const formatCostStr = (valStr) => {
      if (valStr === undefined || valStr === null) return "$0.00.0";
      const num = typeof valStr === "number" ? valStr : parseNum(valStr);
      if (isNaN(num)) return "$0.00.0";
      if (num === 0) return "$0.00.0";
      const abs = Math.abs(num);
      const sign = num < 0 ? "-$" : "$";
      let str;
      if (abs < 10) {
        const base = abs.toFixed(3);
        str = base.slice(0, 4) + "." + base.slice(4);
      }
      else if (abs < 100) str = abs.toFixed(2);
      else if (abs < 1000) str = abs.toFixed(1);
      else str = abs.toFixed(0);
      return sign + str;
    };

    let rows = [];

    if (this._planResolution === "5min") {
      rows = plan.map((r) => {
        return {
          time: r["Time"] || "—",
          localTime: r["Local Time"] || "—",
          synthetic: r["Synthetic"] || false,
          imp: r["Import Rate"] || "0.0",
          exp: r["Export Rate"] || "0.0",
          state: r["FSM State"] || "—",
          limit: r["Inverter Limit"] || "0%",
          grid: r["Net Grid"] || "0.00",
          pv: r["PV Forecast"] || "0.00",
          ld: r["Load Forecast"] || "0.00",
          temp: r["Air Temp Forecast"] || "—",
          tempDelta: r["Temp Delta"] || "—",
          loadAdj: r["Load Adj."] || "0.00",
          soc: r["SoC Forecast"] || "—",
          cost: formatCostStr(r["Interval Cost"]),
          cumul: formatCostStr(r["Cumul. Cost"]),
          acq: formatCostStr(r["Acq. Cost"]),
        };
      });
    } else {
      let currentChunk = [];
      for (let i = 0; i < plan.length; i++) {
        const r = plan[i];
        currentChunk.push(r);

        const timeStr = r["Time"] || "";
        const isBoundary = timeStr.endsWith(":25") || timeStr.endsWith(":55");
        const isLast = i === plan.length - 1;

        if (isBoundary || isLast) {
          const chunk = currentChunk;
          currentChunk = [];
          if (chunk.length === 0) continue;

          const time = chunk[0]["Time"] || "—";
          const localTime = chunk[0]["Local Time"] || "—";

           let state = "SELF_CONSUMPTION";
          let limit = "0%";
          const chargeReq = chunk.find(row => row["FSM State"] === "CHARGE_GRID");
          const dischargeReq = chunk.find(row => row["FSM State"] === "DISCHARGE_GRID");

          if (chargeReq) {
            state = "CHARGE_GRID";
            limit = chargeReq["Inverter Limit"] || "100%";
          } else if (dischargeReq) {
            state = "DISCHARGE_GRID";
            limit = dischargeReq["Inverter Limit"] || "100%";
          }

          const imp = (chunk.reduce((s, row) => s + parseNum(row["Import Rate"]), 0) / chunk.length).toFixed(2);
          const exp = (chunk.reduce((s, row) => s + parseNum(row["Export Rate"]), 0) / chunk.length).toFixed(2);
          const grid = (chunk.reduce((s, row) => s + parseNum(row["Net Grid"]), 0) / chunk.length).toFixed(2);
          const pv = (chunk.reduce((s, row) => s + parseNum(row["PV Forecast"]), 0) / chunk.length).toFixed(2);
          const ld = (chunk.reduce((s, row) => s + parseNum(row["Load Forecast"]), 0) / chunk.length).toFixed(2);
          const tempNum = (chunk.reduce((s, row) => s + parseNum(row["Air Temp Forecast"]), 0) / chunk.length).toFixed(1);
          const temp = chunk[0]["Air Temp Forecast"] === "—" ? "—" : `${tempNum}°C`;

          const lastRow = chunk[chunk.length - 1];
          const soc = lastRow["SoC Forecast"] || "—";
          const costRaw = chunk.reduce((s, row) => s + parseNum(row["Interval Cost"]), 0);
          const cost = formatCostStr(costRaw);
          const cumul = formatCostStr(lastRow["Cumul. Cost"]);
          const acq = formatCostStr(chunk.reduce((s, row) => s + parseNum(row["Acq. Cost"]), 0) / chunk.length);

          const tempDeltaNum = (chunk.reduce((s, row) => s + parseNum(row["Temp Delta"]), 0) / chunk.length).toFixed(1);
          const tempDelta = chunk[0]["Temp Delta"] === "—" ? "—" : `${tempDeltaNum}°C`;
          const loadAdj = (chunk.reduce((s, row) => s + parseNum(row["Load Adj."]), 0) / chunk.length).toFixed(2);
          const synthetic = chunk[0]["Synthetic"] || false;

           rows.push({ time, localTime, synthetic, imp, exp, state, limit, grid, pv, ld, temp, tempDelta, loadAdj, soc, cost, cumul, acq });
        }
      }
    }

    const summaryStats = this._calculateSummaryStats();
    const footerKeys = {
      "Time": "24h Summary:", "Local Time": "", "Import": summaryStats.avgImport, "Export": summaryStats.avgExport,
      "State": "", "Limit": "", "Net Grid": "", "PV": summaryStats.totalPV + " kwh", "Load": summaryStats.totalLoad + " kwh",
      "Temp": "", "Temp Δ": "", "Load Adj.": "", "SoC": "", "Cost": "", "Cumul. Cost": "", "Acq. Cost": "",
    };

    return html`
      <div class="card table-card">
        <div class="header" style="margin-bottom: 12px; display: flex; justify-content: space-between; align-items: baseline;">
          <div>
            <h2 style="margin-bottom: 0;">24-Hour Plan <span style="font-size: 0.55em; font-weight: normal; opacity: 0.5; margin-left: 12px;">Fetched: ${this._lastUpdate}</span></h2>
            <div class="tabs">
              <button class="${this._planResolution === "5min" ? "active" : ""}" @click=${() => this._switchResolution("5min")}>5 Min</button>
              <button class="${this._planResolution === "30min" ? "active" : ""}" @click=${() => this._switchResolution("30min")}>30 Min</button>
            </div>
          </div>
          <button @click=${this._fetchPlan} class="refresh-btn" ?disabled=${this._loading}>
            ${this._loading ? 'Refreshing...' : 'Refresh Plan'}
          </button>
        </div>
        
        <div class="column-toggles">
          ${cols.map(c => html`
            <button
              class="${this._hiddenCols.includes(c) ? '' : 'active'}"
              style="background: ${this._hiddenCols.includes(c) ? 'transparent' : 'var(--primary-color)'}; color: ${this._hiddenCols.includes(c) ? 'inherit' : 'var(--text-primary-color, white)'}; border: 1px solid ${this._hiddenCols.includes(c) ? 'var(--divider-color, rgba(150,150,150,0.4))' : 'var(--primary-color)'}; border-radius: 4px; padding: 4px 8px; font-size: 0.8em; cursor: pointer; opacity: ${this._hiddenCols.includes(c) ? '0.5' : '1'}; transition: 0.2s ease;"
              @click=${() => this._toggleCol(c)}
            >${c}</button>
          `)}
        </div>

        <div class="table-wrap">
          <table>
            <thead>
              <tr>${cols.filter(c => !this._hiddenCols.includes(c)).map((c) => html`<th>${c}</th>`)}</tr>
            </thead>
            <tbody>
              ${rows.map((r) => {
                const colKeys = {
                  "Time": r.time, "Local Time": r.synthetic && r.localTime !== "—" ? `${r.localTime}*` : r.localTime, "Import": r.imp, "Export": r.exp,
                  "State": r.state, "Limit": r.limit, "Net Grid": r.grid, "PV": r.pv, "Load": r.ld,
                  "Temp": r.temp, "Temp Δ": r.tempDelta, "Load Adj.": r.loadAdj, "SoC": r.soc,
                  "Cost": r.cost, "Cumul. Cost": r.cumul, "Acq. Cost": r.acq,
                };
                return html`
                  <tr class="${r.state === 'SELF_CONSUMPTION' ? 'state-self' : r.state === 'CHARGE_GRID' ? 'state-charge' : r.state === 'DISCHARGE_GRID' ? 'state-discharge' : ''} ${r.synthetic ? 'state-synthetic' : ''}">
                    ${cols.filter(c => !this._hiddenCols.includes(c)).map(c => html`<td>${colKeys[c]}</td>`)}
                  </tr>
                `;
              })}
            </tbody>
            <tfoot>
              <tr style="font-weight: bold; background: rgba(255,255,255,0.05);">
                ${cols.filter(c => !this._hiddenCols.includes(c)).map(c => html`<td>${footerKeys[c] || ""}</td>`)}
              </tr>
            </tfoot>
          </table>
        </div>
        <div style="font-size: 0.8em; opacity: 0.7; margin-top: 12px; font-style: italic;">
          * Synthetic Forecast Period (Historical Analog Fallback)
        </div>
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
      .err-card {
        background: #3e1a1a;
        color: #ff6b6b;
      }
      h2 {
        color: #00d4ff;
        margin: 0 0 16px;
        font-size: 18px;
        font-weight: 500;
        user-select: none;
      }
      .refresh-btn {
        background: #2a2a5e;
        color: #e0e0e0;
        border: 1px solid #444488;
        padding: 6px 12px;
        border-radius: 4px;
        cursor: pointer;
        font-size: 12px;
        transition: 0.2s ease;
      }
      .refresh-btn:hover:not([disabled]) {
        background: #444488;
      }
      .refresh-btn[disabled] {
        opacity: 0.5;
        cursor: not-allowed;
      }
      .tabs {
        display: flex;
        gap: 4px;
        background: #12122a;
        border-radius: 8px;
        padding: 4px;
        width: fit-content;
        margin-top: 8px;
      }
      .tabs button {
        background: transparent;
        color: #8888aa;
        border: none;
        padding: 6px 16px;
        border-radius: 6px;
        cursor: pointer;
        font-size: 13px;
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
      .column-toggles {
        display: flex;
        flex-wrap: wrap;
        gap: 6px;
        padding: 0 16px 12px 16px;
        border-bottom: 1px solid rgba(255,255,255,0.1);
        margin-bottom: 12px;
      }
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
      tr.state-self {
        background-color: rgba(0, 212, 255, 0.15) !important;
      }
      tr.state-charge {
        background-color: rgba(0, 255, 136, 0.15) !important;
      }
      tr.state-discharge {
        background-color: rgba(255, 107, 107, 0.15) !important;
      }
    `;
  }
}

customElements.define("hbc-plan-table-lite", HBCPlanTableLite);
