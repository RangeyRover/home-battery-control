import {
  LitElement,
  html,
  css,
} from "https://unpkg.com/lit-element@2.4.0/lit-element.js?module";

export class HBCSensors extends LitElement {
  static get properties() {
    return {
      data: { type: Object },
      _sensorsHidden: { type: Boolean },
    };
  }

  constructor() {
    super();
    this.data = {};
    this._sensorsHidden = localStorage.getItem("hbc_sensors_hidden") === "true";
  }

  _toggleSensors() {
    this._sensorsHidden = !this._sensorsHidden;
    localStorage.setItem("hbc_sensors_hidden", this._sensorsHidden);
  }

  render() {
    const sensors = this.data.sensors || [];
    if (sensors.length === 0) return html``;

    return html`
      <div class="card">
        <h2 
          @click=${this._toggleSensors} 
          style="cursor: pointer; display: flex; justify-content: space-between; align-items: center;"
        >
          Sensor Status
          <span style="font-size: 0.8em; transform: rotate(${this._sensorsHidden ? '-90deg' : '0deg'}); transition: transform 0.2s;">▼</span>
        </h2>
        
        ${this._sensorsHidden ? html`` : html`
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
        `}
        <div class="meta">
          Last update: ${this.data.last_update || "—"} |
          Update #${this.data.update_count || 0}
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
      h2 {
        color: #00d4ff;
        margin: 0 0 16px;
        font-size: 18px;
        font-weight: 500;
        user-select: none;
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

customElements.define("hbc-sensors", HBCSensors);
