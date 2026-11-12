/* Diskpilot: bundled Home Assistant card, no external assets or dependencies. */
const PROGRAMS = { P2: "P2 · 70 °C", P3: "P3 · Snabb", P4: "P4 · Eco" };
const STATUS = {
  needs_labelled_run: "Behöver en märkt körning",
  needs_saved_profile: "Behöver en sparad programprofil",
  not_configured: "Välj prissensor i integrationens inställningar",
  unavailable: "Prissensorn är inte tillgänglig",
  no_intervals: "Prissensorn saknar prisintervall",
  invalid_format: "Kontrollera prissensorns format i inställningarna",
  insufficient_price_coverage: "Priser saknas för en hel körning inom tidsgränsen",
};
function el(tag, text, className) {
  const node = document.createElement(tag);
  if (text !== undefined) node.textContent = text;
  if (className) node.className = className;
  return node;
}
function statuses(hass) {
  return Object.values(hass?.states || {}).filter(s => s.attributes.diskpilot_entry_id && "recent_runs" in s.attributes);
}
function time(value, hass) {
  return value ? new Date(value).toLocaleString(hass.locale?.language || "sv-SE", {
    timeZone: hass.config?.time_zone || "Europe/Stockholm", month: "short", day: "numeric", hour: "2-digit", minute: "2-digit",
  }) : "—";
}
function number(value, digits = 2) {
  return typeof value === "number" && Number.isFinite(value) ? value.toLocaleString("sv-SE", { maximumFractionDigits: digits }) : "—";
}

class DiskpilotCard extends HTMLElement {
  static getConfigElement() { return document.createElement("diskpilot-card-editor"); }
  static getStubConfig(hass) { return { entry_id: statuses(hass)[0]?.attributes.diskpilot_entry_id }; }
  setConfig(config) { this._config = { ...config }; this.render(); }
  set hass(hass) {
    this._hass = hass;
    // Avoid losing focus or an unsaved program selection on unrelated HA updates.
    const entries = statuses(hass);
    const entry = this._config?.entry_id || entries[0]?.attributes.diskpilot_entry_id;
    for (const run of entries.find(s => s.attributes.diskpilot_entry_id === entry)?.attributes.recent_runs || []) {
      if (this._drafts?.[run.run_id] === (run.program || "unassigned")) delete this._drafts[run.run_id];
    }
    const state = Object.values(hass.states).filter(s => s.attributes.diskpilot_entry_id === entry);
    const signature = JSON.stringify(state.map(s => [s.state, s.attributes]));
    if (signature !== this._signature) { this._signature = signature; this.render(); }
  }
  getCardSize() { return 8; }
  getGridOptions() { return { columns: 12, rows: 8, min_columns: 6 }; }
  render() {
    if (!this._config || !this._hass) return;
    if (!this.shadowRoot) this.attachShadow({ mode: "open" });
    const root = this.shadowRoot;
    root.replaceChildren();
    const style = el("style");
    style.textContent = `
      ha-card { padding: 20px; color: var(--primary-text-color); }
      h2 { font-size: 21px; margin: 0 0 6px; font-weight: 600; }
      h3 { font-size: 16px; margin: 24px 0 8px; }
      p { margin: 6px 0 14px; line-height: 1.5; }
      .muted, .note { color: var(--secondary-text-color); font-size: 13px; }
      .program { padding: 14px 0; border-bottom: 1px solid var(--divider-color); }
      .heading { display: flex; gap: 12px; justify-content: space-between; align-items: baseline; }
      .cost { font-size: 22px; font-weight: 600; white-space: nowrap; }
      dl { display: grid; grid-template-columns: 1fr 1fr; gap: 8px 16px; margin: 10px 0 0; }
      dt { color: var(--secondary-text-color); font-size: 12px; } dd { margin: 2px 0 0; font-size: 14px; }
      .run { padding: 10px 0; border-bottom: 1px solid var(--divider-color); }
      .controls { display: flex; flex-wrap: wrap; gap: 8px; align-items: center; margin-top: 8px; }
      select, button { font: inherit; font-size: 14px; min-height: 44px; padding: 8px 10px; border-radius: 8px; }
      select { background: var(--card-background-color); color: var(--primary-text-color); border: 1px solid var(--divider-color); }
      button { background: var(--primary-color); color: var(--text-primary-color, white); border: 0; cursor: pointer; }
      button:disabled { opacity: .6; cursor: wait; } button:focus-visible, select:focus-visible { outline: 3px solid var(--primary-color); outline-offset: 3px; }
      .error { color: var(--error-color); } .message { margin: 8px 0; min-height: 20px; }
      @media (max-width: 350px) { ha-card { padding: 14px; } dl { grid-template-columns: 1fr; } }
    `;
    root.append(style);
    const card = el("ha-card");
    root.append(card);
    card.append(el("h2", this._config.title || "Diskpilot"));
    const list = statuses(this._hass);
    const status = this._config.entry_id ? list.find(s => s.attributes.diskpilot_entry_id === this._config.entry_id) : list[0];
    if (!status) { card.append(el("p", "Lägg till Diskpilot-integrationen för din diskmaskin.")); return; }
    const entryId = status.attributes.diskpilot_entry_id;
    const states = Object.values(this._hass.states).filter(s => s.attributes.diskpilot_entry_id === entryId && s.attributes.program);
    const running = status.state === "planner" ? "Planering med sparade profiler · effektmätning avstängd" : status.state === "running" ? "Körning pågår" : status.state === "source_unavailable" ? "Effektsensorn är inte tillgänglig" : "Redo att registrera nästa körning";
    card.append(el("p", running, "muted"));
    for (const program of Object.keys(PROGRAMS)) {
      const sensor = states.find(s => s.attributes.program === program);
      const a = sensor?.attributes || {};
      const section = el("section", undefined, "program");
      const heading = el("div", undefined, "heading");
      heading.append(el("strong", PROGRAMS[program]));
      const cost = sensor && !["unknown", "unavailable"].includes(sensor.state) ? Number(sensor.state) : null;
      heading.append(el("span", cost !== null ? `${number(cost)} ${a.currency || "SEK"}` : "—", "cost"));
      section.append(heading);
      const dl = el("dl");
      for (const [label, value] of [
        ["Bästa start", time(a.optimal_start, this._hass)], ["Åter i vila", time(a.optimal_end, this._hass)],
        ["Energi", a.energy_kwh != null ? `${number(a.energy_kwh, 3)} kWh` : "—"],
        ["Underlag", a.sample_count === 1 ? "1 märkt körning" : `${a.sample_count || 0} märkta körningar`],
      ]) { const group = el("div"); group.append(el("dt", label), el("dd", value)); dl.append(group); }
      section.append(dl);
      if (a.status !== "ok") section.append(el("p", STATUS[a.status] || "Samlar underlag", "note"));
      else if (a.sample_count === 1) section.append(el("p", "Första uppskattningen · baserad på en körning", "note"));
      if (a.saving != null) section.append(el("p", `Beräknad besparing mot start nu: ${number(a.saving)} ${a.currency}`, "note"));
      card.append(section);
    }
    card.append(el("p", "Sluttiden avser återgång till viloläge. När disken är klar behöver verifieras separat.", "note"));
    if (status.state === "planner") return;
    card.append(el("h3", "Senaste körningarna"));
    const message = el("div", this._message || "", "message");
    message.setAttribute("role", "status"); message.setAttribute("aria-live", "polite");
    card.append(message);
    const runs = status.attributes.recent_runs || [];
    if (!runs.length) card.append(el("p", status.state === "planner" ? "Importera sparade profiler eller anslut en effektmätare när du vill samla nya körningar." : "Här visas körningarna när de har avslutats och viloläget har bekräftats.", "muted"));
    for (const run of runs.slice(0, 5)) {
      const row = el("div", undefined, "run");
      row.append(el("div", `${time(run.started_at, this._hass)} · ${number(run.energy_kwh, 3)} kWh · ${number(run.duration_minutes, 0)} min`));
      if (run.issues?.length) row.append(el("p", "Ofullständig mätning · används inte för programprofilen", "note"));
      const controls = el("div", undefined, "controls");
      const select = el("select");
      select.setAttribute("aria-label", `Program för körningen ${time(run.started_at, this._hass)}`);
      for (const [value, label] of Object.entries({ unassigned: "Ej märkt", ...PROGRAMS })) {
        const option = el("option", label); option.value = value; select.append(option);
      }
      select.value = this._drafts?.[run.run_id] || run.program || "unassigned";
      select.addEventListener("change", () => { (this._drafts ||= {})[run.run_id] = select.value; });
      const button = el("button", "Spara program");
      button.addEventListener("click", async () => {
        button.disabled = true;
        try {
          await this._hass.callService("dishwasher_optimizer", "label_run", { entry_id: entryId, run_id: run.run_id, program: select.value });
          this._message = "Programmet är sparat. Profilen har uppdaterats.";
          this.render();
        } catch (error) { message.textContent = `Kunde inte spara: ${error.message || error}`; message.classList.add("error"); }
        finally { button.disabled = false; }
      });
      controls.append(select, button); row.append(controls); card.append(row);
    }
  }
}

class DiskpilotEditor extends HTMLElement {
  setConfig(config) { this._config = { ...config }; this.render(); }
  set hass(hass) { this._hass = hass; this.render(); }
  render() {
    if (!this._config || !this._hass) return;
    if (!this.shadowRoot) this.attachShadow({ mode: "open" });
    this.shadowRoot.replaceChildren();
    const form = document.createElement("ha-form");
    form.hass = this._hass;
    form.data = this._config;
    form.schema = [
      { name: "title", selector: { text: {} } },
      { name: "entry_id", required: true, selector: { select: { options: statuses(this._hass).map(s => ({ value: s.attributes.diskpilot_entry_id, label: s.attributes.friendly_name || s.entity_id })) } } },
    ];
    form.computeLabel = schema => schema.name === "title" ? "Rubrik" : "Diskmaskin";
    form.addEventListener("value-changed", event => {
      event.stopPropagation();
      this._config = { ...this._config, ...event.detail.value };
      this.dispatchEvent(new CustomEvent("config-changed", { detail: { config: this._config }, bubbles: true, composed: true }));
    });
    this.shadowRoot.append(form);
  }
}
if (!customElements.get("diskpilot-card")) customElements.define("diskpilot-card", DiskpilotCard);
if (!customElements.get("diskpilot-card-editor")) customElements.define("diskpilot-card-editor", DiskpilotEditor);
window.customCards ||= [];
if (!window.customCards.some(card => card.type === "diskpilot-card")) window.customCards.push({
  type: "diskpilot-card", name: "Diskpilot", description: "Programkostnad, bästa start och märkning av diskmaskinens körningar", preview: true,
});
