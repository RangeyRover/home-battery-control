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
        color: var(--primary-text-color, #e0e0e0);
        font-family: var(--paper-font-body1_-_font-family, -apple-system, BlinkMacSystemFont, Roboto, sans-serif);
      }
      details {
        background: var(--card-background-color, #16213e);
        padding: 15px;
        margin-bottom: 15px;
        border-radius: 8px;
        box-shadow: 0 4px 6px rgba(0,0,0,0.3);
      }
      summary {
        font-weight: bold;
        cursor: pointer;
        padding: 5px;
        font-size: 1.1em;
        color: #e94560;
        outline: none;
      }
      .empty-state {
        padding: 20px;
        text-align: center;
        color: #a0a0a0;
        font-style: italic;
      }
      ul.dates-list {
        list-style-type: none;
        padding-left: 10px;
      }
      ul.dates-list li {
        padding: 4px 0;
        color: #a0a0a0;
      }
      .graph-container {
        width: 100%;
        height: 300px;
        margin-top: 15px;
      }
      .legend {
        display: flex;
        justify-content: center;
        gap: 20px;
        margin-top: 10px;
        font-size: 0.9em;
      }
      .legend-item {
        display: flex;
        align-items: center;
        gap: 5px;
      }
      .color-box {
        width: 12px;
        height: 12px;
        border-radius: 2px;
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
        <p style="color: #a0a0a0; font-size: 0.9em; margin-top: 5px;">These 5 historical days closely matched tomorrow's predicted solar yield.</p>
        <ul class="dates-list">
          ${analogDays.map(date => html`<li>${date}</li>`)}
        </ul>
      </details>

      <details class="outlook-graphs" open>
        <summary>Synthesized 24-Hour Trends</summary>
        <div class="graph-container">
          ${this._renderGraph(importCurve, exportCurve, loadCurve)}
        </div>
        <div class="legend">
          <div class="legend-item">
            <div class="color-box" style="background: #ef4444;"></div>
            <span>Import Price</span>
          </div>
          <div class="legend-item">
            <div class="color-box" style="background: #10b981;"></div>
            <span>Export Price</span>
          </div>
          <div class="legend-item">
            <div class="color-box" style="background: #3b82f6;"></div>
            <span>Load (kW)</span>
          </div>
        </div>
      </details>
    `;
  }

  _renderGraph(importCurve, exportCurve, loadCurve) {
    const width = 800;
    const height = 250;
    const padding = 20;
    
    // Calculate max values for scaling
    // We scale price and load independently to fit the same height
    const maxPrice = Math.max(0.1, ...importCurve, ...exportCurve);
    const maxLoad = Math.max(0.1, ...loadCurve);
    
    const scaleX = (width - 2 * padding) / 287; // 288 points = 287 intervals

    // Function to generate SVG points from an array
    const getPoints = (array, maxY) => {
      if (!array || array.length === 0) return "";
      const scaleY = (height - 2 * padding) / maxY;
      return array.map((val, idx) => {
        const x = padding + idx * scaleX;
        const y = height - padding - (val * scaleY);
        return `${x},${y}`;
      }).join(' ');
    };

    const importPoints = getPoints(importCurve, maxPrice);
    const exportPoints = getPoints(exportCurve, maxPrice);
    const loadPoints = getPoints(loadCurve, maxLoad);

    return svg`
      <svg viewBox="0 0 ${width} ${height}" preserveAspectRatio="none" style="width: 100%; height: 100%;">
        <!-- Grid lines -->
        <line x1="${padding}" y1="${height - padding}" x2="${width - padding}" y2="${height - padding}" stroke="#333" stroke-width="1"/>
        <line x1="${padding}" y1="${padding}" x2="${padding}" y2="${height - padding}" stroke="#333" stroke-width="1"/>
        
        <!-- Curves -->
        <polyline points="${exportPoints}" fill="none" stroke="#10b981" stroke-width="2" vector-effect="non-scaling-stroke"/>
        <polyline points="${importPoints}" fill="none" stroke="#ef4444" stroke-width="2" vector-effect="non-scaling-stroke"/>
        <polyline points="${loadPoints}" fill="none" stroke="#3b82f6" stroke-width="2" vector-effect="non-scaling-stroke"/>
      </svg>
    `;
  }
}

customElements.define('hbc-outlook', HBCOutlook);
