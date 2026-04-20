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
      </div>
    `;
  }
}

customElements.define('hbc-outlook', HBCOutlook);
