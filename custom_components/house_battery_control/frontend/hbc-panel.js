import {
  LitElement,
  html,
  css,
} from "https://unpkg.com/lit-element@2.4.0/lit-element.js?module";

import "./hbc-dashboard.js";
import "./hbc-sensors.js";
import "./hbc-plan-table.js";

// Module-level recovery: after extended idle, HA may destroy the panel element
// without recreating it. Detect tab focus and reload if panel is missing.
document.addEventListener("visibilitychange", () => {
  if (document.visibilityState !== "visible") return;
  if (!location.pathname.startsWith("/hbc-panel")) return;
  // Minimal delay for event loop to settle, then reload if panel is missing
  setTimeout(() => {
    if (!document.querySelector("hbc-panel")) {
      location.reload();
    }
  }, 100);
});

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
    this._fallbackInterval = null;
    this._lastFetch = 0;
  }

  connectedCallback() {
    super.connectedCallback();
    this._fetchData();
    // 60s fallback timer for edge cases where entity state doesn't change (FR-004)
    this._fallbackInterval = setInterval(() => this._fetchData(), 60000);
  }

  disconnectedCallback() {
    super.disconnectedCallback();
    if (this._fallbackInterval) clearInterval(this._fallbackInterval);
  }

  // Push-driven: react to HA hass changes instead of polling (FR-001, fixes #12)
  updated(changedProps) {
    super.updated(changedProps);
    if (!changedProps.has("hass")) return;
    const oldHass = changedProps.get("hass");
    if (!oldHass) {
      // First hass assignment — fetch immediately
      this._fetchData();
      return;
    }
    const oldState = oldHass.states["sensor.hbc_state"];
    const newState = this.hass.states["sensor.hbc_state"];
    if (!oldState || !newState) return;
    if (oldState.state !== newState.state || oldState.last_updated !== newState.last_updated) {
      this._debouncedFetch();
    }
  }

  // 10s debounce to avoid redundant fetches (FR-003)
  _debouncedFetch() {
    const now = Date.now();
    if (this._lastFetch && (now - this._lastFetch) < 10000) return;
    this._lastFetch = now;
    this._fetchData();
  }

  async _fetchData() {
    try {
      if (!this.hass) {
        this._error = "Home Assistant connection not available";
        this._loading = false;
        return;
      }
      // Use HA's fetchWithAuth which auto-refreshes expired tokens (fixes #7)
      let resp = await this.hass.fetchWithAuth("/hbc/api/status");
      if (resp.status === 401) {
        // Tab may have been idle — HA reconnects WebSocket on focus.
        // Rapid retry: 500ms apart, up to 5 attempts (fixes #11)
        for (let i = 0; i < 5; i++) {
          await new Promise(r => setTimeout(r, 500));
          if (!this.hass) break;
          resp = await this.hass.fetchWithAuth("/hbc/api/status");
          if (resp.status !== 401) break;
        }
        if (resp.status === 401) {
          this._error = "Insufficient permissions — admin access required";
          this._loading = false;
          return;
        }
      }
      if (!resp.ok) throw new Error(`HTTP ${resp.status}`);
      this._data = await resp.json();
      this._error = "";
    } catch (e) {
      this._error = e.message || String(e);
    }
    this._loading = false;
  }

  _switchTab(tab) {
    this._activeTab = tab;
  }

  _toggleMenu() {
    this.dispatchEvent(new Event("hass-toggle-menu", {
      bubbles: true,
      composed: true,
    }));
  }

  render() {
    if (this._loading) {
      return html`<div class="root"><p>Loading...</p></div>`;
    }
    if (this._error) {
      return html`<div class="root"><div class="card err-card">Error: ${this._error}</div></div>`;
    }

    return html`
      <div class="toolbar">
        <button class="menu-btn" @click=${this._toggleMenu} aria-label="Menu">
          <svg viewBox="0 0 24 24" width="24" height="24" fill="currentColor">
            <path d="M3 18h18v-2H3v2zm0-5h18v-2H3v2zm0-7v2h18V6H3z"/>
          </svg>
        </button>
        <span class="toolbar-title">House Battery Control</span>
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
      <div class="root">
        ${this._activeTab === "dashboard"
          ? html`
              <hbc-dashboard .data=${this._data}></hbc-dashboard>
              <hbc-sensors .data=${this._data}></hbc-sensors>
            `
          : html`
              <hbc-plan-table .data=${this._data}></hbc-plan-table>
            `}
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
        font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif;
      }
      .toolbar {
        display: flex;
        align-items: center;
        gap: 12px;
        padding: 8px 16px;
        background: #1a1a3e;
        border-bottom: 1px solid #2a2a5e;
        position: sticky;
        top: 0;
        z-index: 10;
      }
      .menu-btn {
        background: none;
        border: none;
        color: #e0e0e0;
        cursor: pointer;
        padding: 8px;
        border-radius: 50%;
        display: flex;
        align-items: center;
        justify-content: center;
        transition: background 0.2s;
      }
      .menu-btn:hover {
        background: rgba(255, 255, 255, 0.1);
      }
      .toolbar-title {
        color: #00d4ff;
        font-size: 18px;
        font-weight: 600;
        flex: 1;
      }
      .root {
        max-width: 1200px;
        margin: 0 auto;
        padding: 20px;
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
      .err-card {
        background: #3e1a1a;
        color: #ff6b6b;
        padding: 20px;
        border-radius: 12px;
      }
    `;
  }
}

customElements.define("hbc-panel", HBCPanel);
