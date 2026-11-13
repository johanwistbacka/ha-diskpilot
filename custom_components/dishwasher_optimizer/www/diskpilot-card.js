/* Diskpilot: bundled Home Assistant card, no external assets or dependencies. */
const managerUrl = new URL("./profile-manager.js", import.meta.url);
managerUrl.search = new URL(import.meta.url).search;
const { renderProfileControls } = await import(managerUrl.href);
const registrationUrl = new URL("./profile-registration.js", import.meta.url);
registrationUrl.search = new URL(import.meta.url).search;
const { renderRegistration } = await import(registrationUrl.href);
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
    const signature = JSON.stringify(state.map(s => { const {registration, ...attributes}=s.attributes;return [s.state,attributes,registration?.stage]; }));
    const current=entries.find(s=>s.attributes.diskpilot_entry_id===entry);
    if(current)this._registrationUpdate?.(current.attributes);
    if (signature !== this._signature) { this._signature = signature; this.render(); }
  }
  getCardSize() { return 4; }
  getGridOptions() { return { columns: 12, rows: "auto", min_columns: 6 }; }
  async service(entryId, service, data) {
    const result = await this._hass.callWS({type:"call_service",domain:"dishwasher_optimizer",service,service_data:{entry_id:entryId,...data},return_response:true});
    return result.response;
  }
  render() {
    if (!this._config || !this._hass) return;
    if (!this.shadowRoot) this.attachShadow({ mode: "open" });
    const root = this.shadowRoot;
    const card = root.querySelector("ha-card") || el("ha-card");
    const active = root.activeElement;
    const editing = active?.matches('input, select, button, summary') ? {
      node: active,
      label: active.getAttribute("aria-label"),
      key: active.getAttribute("data-focus-key"),
      start: active.selectionStart,
      end: active.selectionEnd,
      direction: active.selectionDirection,
    } : null;
    this._openPrograms ||= new Set();
    // Capture native disclosure state before a price update replaces its DOM.
    for (const details of root.querySelectorAll("details.program")) {
      const key = details.dataset.programKey;
      if (details.open) this._openPrograms.add(key);
      else this._openPrograms.delete(key);
    }
    root.replaceChildren();
    const style = el("style");
    style.textContent = `
      ha-card { padding: 20px; color: var(--primary-text-color); }
      h2 { font-size: 21px; margin: 0 0 6px; font-weight: 600; }
      h3 { font-size: 16px; margin: 24px 0 8px; }
      p { margin: 6px 0 14px; line-height: 1.5; }
      .muted, .note { color: var(--secondary-text-color); font-size: 13px; overflow-wrap:anywhere; }
      details.program { margin: 0; border-bottom: 1px solid var(--divider-color); }
      .program > summary { display:grid;grid-template-columns:minmax(0,1fr) auto 12px;gap:4px 12px;align-items:center;min-height:64px;padding:12px 2px;box-sizing:border-box;line-height:1.45;list-style:none; }
      .program > summary::-webkit-details-marker { display:none; }
      .program > summary::after { content:"";grid-column:3;grid-row:1 / 3;width:7px;height:7px;border:solid var(--secondary-text-color);border-width:0 2px 2px 0;transform:rotate(45deg);justify-self:center; }
      .program[open] > summary::after { transform:rotate(225deg); }
      .program-name { grid-column:1;grid-row:1;min-width:0;overflow-wrap:anywhere;font-size:15px;font-weight:600; }
      .cost { grid-column:2;grid-row:1;font-size:20px;font-weight:600;white-space:nowrap; }
      .start { grid-column:1 / 3;grid-row:2;color:var(--secondary-text-color);font-size:13px; }
      .program-body { padding:0 2px 12px; }
      .program-body p:last-child { margin-bottom:0; }
      dl { display: grid; grid-template-columns: 1fr 1fr; gap: 8px 16px; margin: 10px 0 0; }
      dt { color: var(--secondary-text-color); font-size: 12px; } dd { margin: 2px 0 0; font-size: 14px; }
      .run { padding: 10px 0; border-bottom: 1px solid var(--divider-color); }
      .controls { display: flex; flex-wrap: wrap; gap: 8px; align-items: center; margin-top: 8px; }
      select, button, input[type=text], input[type=datetime-local] { font: inherit; font-size: 14px; min-height: 44px; padding: 8px 10px; border-radius: 8px; box-sizing:border-box;max-width:100%; }
      input[type=text], input[type=datetime-local] { background:var(--card-background-color);color:var(--primary-text-color);border:1px solid var(--divider-color); }
      .registration-body { display:grid;gap:12px;min-width:0; } .registration-grid {display:grid;grid-template-columns:repeat(2,minmax(0,1fr));gap:12px;} .registration-field {display:grid;gap:6px;min-width:0;font-size:13px;} .registration-field input,.registration-field select {width:100%;min-width:0;} .registration-chart svg {height:auto;display:block;} .registration-chart {color:var(--primary-color);min-width:0;} .registration-body h3,.registration-body p {margin:0;} .registration-body .review {margin:0;} .secondary {background:transparent;color:var(--primary-color);border:1px solid var(--divider-color);} input[type=range] {min-height:44px;accent-color:var(--primary-color);} .registration-save {justify-self:start;}
      @media(max-width:480px){.registration-grid{grid-template-columns:1fr;}input[type=datetime-local],input[type=text]{font-size:16px;}}
      details { margin:18px 0; } summary { cursor:pointer;min-height:44px;line-height:44px; } a {color:var(--primary-color);}
      .review { display:flex;align-items:center;gap:10px;min-height:44px;margin:12px 0; } .review input {width:22px;height:22px;flex-shrink:0;}
      .preview { padding:12px;border:1px solid var(--divider-color);border-radius:8px;margin:12px 0; } svg {width:100%;height:70px;color:var(--primary-color);}
      select { background: var(--card-background-color); color: var(--primary-text-color); border: 1px solid var(--divider-color); }
      button { background: var(--primary-color); color: var(--text-primary-color, white); border: 0; cursor: pointer; }
      button:disabled { opacity: .6; cursor: wait; } button:focus-visible, select:focus-visible, input:focus-visible, summary:focus-visible { outline: 3px solid var(--primary-color); outline-offset: 3px; }
      .error { color: var(--error-color); } .message { margin: 8px 0; min-height: 20px; }
      @media (max-width: 350px) { ha-card { padding: 14px; } dl { grid-template-columns: 1fr; } }
    `;
    root.append(style);
    card.replaceChildren();
    root.append(card);
    card.append(el("h2", this._config.title || "Diskpilot"));
    const list = statuses(this._hass);
    const status = this._config.entry_id ? list.find(s => s.attributes.diskpilot_entry_id === this._config.entry_id) : list[0];
    if (!status) { card.append(el("p", "Lägg till Diskpilot-integrationen för din diskmaskin.")); return; }
    const entryId = status.attributes.diskpilot_entry_id;
    const profiles = status.attributes.profiles || [];
    const states = Object.values(this._hass.states).filter(s => s.attributes.diskpilot_entry_id === entryId && s.attributes.program);
    const running = status.attributes.registration?.stage === "recording" ? "Registrering pågår" : status.attributes.registration?.stage === "review" ? "Utkast väntar på granskning" : status.state === "planner" ? "Planering med sparade profiler · effektmätning avstängd" : status.state === "running" ? "Körning pågår" : status.state === "source_unavailable" ? "Effektsensorn är inte tillgänglig" : "Redo att registrera nästa körning";
    card.append(el("p", running, "muted"));
    for (const profile of profiles) {
      const program=profile.id;
      const sensor = states.find(s => s.attributes.program === program);
      const a = sensor?.attributes || {};
      const section = el("details", undefined, "program");
      const key = `${entryId}:${program}`;
      section.dataset.programKey = key;
      section.open = this._openPrograms.has(key);
      section.addEventListener("toggle", () => {
        if (!section.isConnected) return;
        if (section.open) this._openPrograms.add(key);
        else this._openPrograms.delete(key);
      });
      const heading = el("summary");
      heading.setAttribute("data-focus-key", key);
      heading.append(el("span", profile.name, "program-name"));
      const cost = sensor && !["unknown", "unavailable"].includes(sensor.state) ? Number(sensor.state) : null;
      heading.append(el("span", cost !== null ? `${number(cost)} ${a.currency || "SEK"}` : "—", "cost"));
      heading.append(el("span", a.optimal_start ? `Starta helst ${time(a.optimal_start, this._hass)}` : "Starttid saknas", "start"));
      section.append(heading);
      const body = el("div", undefined, "program-body");
      const dl = el("dl");
      for (const [label, value] of [
        ["Åter i vila", time(a.optimal_end, this._hass)],
        ["Energi", a.energy_kwh != null ? `${number(a.energy_kwh, 3)} kWh` : "—"],
        ["Underlag", a.sample_count === 1 ? "1 märkt körning" : `${a.sample_count || 0} märkta körningar`],
      ]) { const group = el("div"); group.append(el("dt", label), el("dd", value)); dl.append(group); }
      body.append(dl);
      if (a.status !== "ok") body.append(el("p", STATUS[a.status] || "Samlar underlag", "note"));
      else if (a.sample_count === 1) body.append(el("p", "Första uppskattningen · baserad på en körning", "note"));
      if (a.saving != null) body.append(el("p", `Beräknad besparing mot start nu: ${number(a.saving)} ${a.currency}`, "note"));
      body.append(el("p", "Sluttiden avser återgång till viloläge. När disken är klar behöver verifieras separat.", "note"));
      section.append(body);
      card.append(section);
    }
    if(!profiles.length)card.append(el("p","Lägg till egna profiler och importera deras körningar för att börja planera."));
    renderProfileControls.call(this,card,entryId,profiles,el,number);
    renderRegistration.call(this,card,entryId,profiles,status.attributes,el,number);
    // HA can refresh these sensors while the user is typing a profile name.
    if (editing) {
      const replacement = editing.node.isConnected ? editing.node : [...root.querySelectorAll('input, select, button, summary')].find(input => editing.key ? input.getAttribute("data-focus-key") === editing.key : editing.label && input.getAttribute("aria-label") === editing.label);
      if (replacement) {
        replacement.focus({preventScroll:true});
        if (typeof editing.start === "number" && typeof replacement.setSelectionRange === "function") replacement.setSelectionRange(editing.start, editing.end, editing.direction);
      }
    }
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
      for (const [value, label] of [["unassigned","Ej märkt"],...profiles.map(p=>[p.id,p.name])]) {
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
