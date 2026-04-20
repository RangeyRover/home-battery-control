import { LitElement, html, css, svg } from 'https://unpkg.com/lit-element@2.5.1/lit-element.js?module';

class HBCOutlook extends LitElement {
  static get properties() {
    return {
      hass: { type: Object },
      state: { type: Object },
    };
  }

  static get styles() {
    return css`
      :host {
        display: block;
        padding: 16px;
        color: #e0e0e0;
        font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif;
      }
      details {
        background: #1a1a3e;
        padding: 20px;
        margin-bottom: 16px;
        border-radius: 12px;
        box-shadow: 0 4px 12px rgba(0,0,0,0.4);
      }
      summary {
        font-weight: 500;
        cursor: pointer;
        font-size: 18px;
        color: #00d4ff;
        outline: none;
        user-select: none;
        margin-bottom: 10px;
      }
      .empty-state {
        padding: 20px;
        text-align: center;
        color: #8888aa;
        font-style: italic;
      }
      ul.dates-list {
        list-style-type: none;
        padding: 0;
        margin: 0;
      }
      ul.dates-list li {
        padding: 6px 0;
        color: #e0e0e0;
        border-bottom: 1px solid #2a2a5e;
      }
      ul.dates-list li:last-child {
        border-bottom: none;
      }
      .graph-container {
        width: 100%;
        margin-top: 15px;
        display: flex;
        flex-direction: column;
        gap: 20px;
      }
      .chart-wrapper {
        position: relative;
        width: 100%;
        height: 120px;
        border-bottom: 1px solid #2a2a5e;
      }
      .chart-header {
        display: flex;
        justify-content: space-between;
        align-items: baseline;
        margin-bottom: 5px;
      }
      .chart-title {
        font-size: 14px;
        margin: 0;
      }
      .chart-minmax {
        font-size: 11px;
        color: #8888aa;
      }
      .axis-label {
        position: absolute;
        right: 0;
        font-size: 10px;
        color: #555577;
      }
      .axis-label.max { top: 25px; }
      .axis-label.min { bottom: 5px; }
      .x-axis-labels {
        display: flex;
        justify-content: space-between;
        width: calc(100% - 30px);
        margin-top: 4px;
        font-size: 10px;
        color: #555577;
      }
      .table-wrap {
        overflow-x: auto;
        max-height: 400px;
        margin-top: 15px;
      }
      table {
        width: 100%;
        border-collapse: collapse;
        font-size: 13px;
      }
      th {
        background: #12122a;
        color: #00d4ff;
        padding: 8px;
        text-align: left;
        position: sticky;
        top: 0;
      }
      td {
        padding: 6px 8px;
        border-bottom: 1px solid #2a2a5e;
      }
      tr:nth-child(even) {
        background: #15153a;
      }
    `;
  }

  render() {
    if (!this.state || !this.state.synthetic_analog_days || this.state.synthetic_analog_days.length === 0) {
      return html`
        <div class="empty-state">Waiting for synthetic outlook data...</div>
      `;
    }

    const analogDays = this.state.synthetic_analog_days;
    const importCurve = this.state.synthetic_pricing_curve || [];
    const exportCurve = this.state.synthetic_export_curve || [];
    const loadCurve = this.state.synthetic_load_curve || [];

    return html`
      <details class="analog-days" open>
        <summary>Analog Days Used</summary>
        <p style="color: #8888aa; font-size: 0.9em; margin-top: 0; margin-bottom: 10px;">These 5 historical days closely matched tomorrow's predicted solar yield.</p>
        <ul class="dates-list">
          ${analogDays.map(day => {
            const dateStr = day.date ? new Date(day.date).toLocaleDateString() : day;
            const yieldStr = day.pv_yield !== undefined ? day.pv_yield.toFixed(1) : '?';
            return html`<li>${dateStr} (Yield: ${yieldStr} kWh)</li>`;
          })}
        </ul>
      </details>

      <details class="outlook-graphs" open>
        <summary>Synthesized 24-Hour Trends</summary>
        <div class="graph-container">
          ${this._renderSingleChart("Import Price Curve (c/kWh)", importCurve, "#00d4ff")}
          ${this._renderSingleChart("Export Price Curve (c/kWh)", exportCurve, "#00ff88")}
          ${this._renderSingleChart("Load Profile (kW)", loadCurve, "#ffaa00")}
        </div>
      </details>
      
      ${this._renderRawDataTable(importCurve, exportCurve, loadCurve)}
    `;
  }

  _renderSingleChart(title, curve, color) {
    if (!curve || curve.length === 0) {
      return html`
        <div>
          <div class="chart-header">
            <h3 class="chart-title" style="color: ${color};">${title}</h3>
          </div>
          <div class="chart-wrapper" style="height: 50px;">
            <div style="color: #888;">No data</div>
          </div>
        </div>
      `;
    }

    const maxVal = Math.max(...curve);
    const minVal = Math.min(...curve);
    const width = 800;
    const height = 90;
    const padding = 5;

    // Scale logic
    const scaleX = width / Math.max(1, curve.length - 1);
    const rangeY = maxVal - minVal || 1; // avoid div by 0
    const scaleY = (height - 2 * padding) / rangeY;

    const points = curve.map((val, idx) => {
      const x = idx * scaleX;
      const y = height - padding - ((val - minVal) * scaleY);
      return `${x},${y}`;
    }).join(' ');

    return html`
      <div>
        <div class="chart-header">
          <h3 class="chart-title" style="color: ${color};">${title}</h3>
          <span class="chart-minmax">Min: ${minVal.toFixed(1)} | Max: ${maxVal.toFixed(1)}</span>
        </div>
        <div class="chart-wrapper">
          <div class="axis-label max">${maxVal.toFixed(1)}</div>
          <div class="axis-label min">${minVal.toFixed(1)}</div>
          <svg viewBox="0 0 ${width} ${height}" preserveAspectRatio="none" style="width: calc(100% - 30px); height: 100%;">
            <polyline points="${points}" fill="none" stroke="${color}" stroke-width="2" vector-effect="non-scaling-stroke"/>
          </svg>
        </div>
        <div class="x-axis-labels">
          <span>00:00</span>
          <span>06:00</span>
          <span>12:00</span>
          <span>18:00</span>
          <span>24:00</span>
        </div>
      </div>
    `;
  }

  _renderRawDataTable(importCurve, exportCurve, loadCurve) {
    if (!importCurve || importCurve.length === 0) return html``;
    
    const rows = [];
    const len = Math.max(importCurve.length, exportCurve.length, loadCurve.length);
    for (let i = 0; i < len; i++) {
      const hour = Math.floor((i * 5) / 60).toString().padStart(2, '0');
      const min = ((i * 5) % 60).toString().padStart(2, '0');
      const timeStr = `${hour}:${min}`;
      rows.push({
        time: timeStr,
        imp: importCurve[i] !== undefined ? importCurve[i].toFixed(4) : "—",
        exp: exportCurve[i] !== undefined ? exportCurve[i].toFixed(4) : "—",
        ld: loadCurve[i] !== undefined ? loadCurve[i].toFixed(4) : "—",
      });
    }

    return html`
      <details class="raw-data-table">
        <summary>Raw Synthesized Data (Debug)</summary>
        <div class="table-wrap">
          <table>
            <thead>
              <tr>
                <th>Time</th>
                <th>Import (c/kWh)</th>
                <th>Export (c/kWh)</th>
                <th>Load (kW)</th>
              </tr>
            </thead>
            <tbody>
              ${rows.map(r => html`
                <tr>
                  <td>${r.time}</td>
                  <td>${r.imp}</td>
                  <td>${r.exp}</td>
                  <td>${r.ld}</td>
                </tr>
              `)}
            </tbody>
          </table>
        </div>
      </details>
    `;
  }
}

customElements.define('hbc-outlook', HBCOutlook);
