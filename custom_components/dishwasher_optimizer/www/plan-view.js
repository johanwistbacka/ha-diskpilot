/* Card-local planning. Every cost comes from the backend's existing energy engine. */
const dataUrl = new URL("./plan-data.js", import.meta.url);
dataUrl.search = new URL(import.meta.url).search;
const {
  localInput,
  repeatedTimeOffset,
  relativeTime,
  coverageMessage,
  priceRange,
  powerSegments,
  chartDomain,
  LatestPlanRequests,
} = await import(dataUrl.href);
let instance = 0;
const palette = [
  "#039be5",
  "#a66dd4",
  "#008f83",
  "#cf791d",
  "#d96a9a",
  "#8c8176",
];
const ns = "http://www.w3.org/2000/svg";
const svgNode = (tag, attrs = {}, text) => {
  const n = document.createElementNS(ns, tag);
  for (const [k, v] of Object.entries(attrs)) n.setAttribute(k, v);
  if (text !== undefined) n.textContent = text;
  return n;
};
const statuses = {
  updating: "Prisunderlaget uppdateras.",
  not_configured: "Välj en prissensor i integrationens inställningar.",
  unavailable: "Prissensorn är inte tillgänglig.",
  no_intervals: "Prissensorn saknar prisintervall.",
  invalid_format: "Kontrollera prissensorns format i inställningarna.",
  grid_unavailable: "Eltariff-källan är inte tillgänglig.",
  grid_unsupported:
    "Eltariff: nätenergitariffen stöds inte eller saknar säker giltighet. Tidsstyrda/dynamiska nätpriser stöds ännu inte.",
  grid_no_coverage: "Nätavgift eller energiskatt saknas för prisperioden.",
  currency_mismatch: "Priskällornas valuta eller enhet stämmer inte överens.",
  spot_includes_fees:
    "Nord Pool-sensorn har redan avgiftspåslag. Använd en ren spotpriskälla eller en färdig totalprislista.",
};
const css = `
.plan-view{--plan-low:var(--success-color,#36884d);--plan-mid:var(--warning-color,#c69900);--plan-high:var(--error-color,#d7473e);color:var(--primary-text-color);min-width:0;container-type:inline-size}
.plan-view [hidden]{display:none!important}
.plan-head{display:flex;gap:14px;align-items:end;flex-wrap:wrap;margin-bottom:10px}
.plan-title{display:flex;align-items:baseline;gap:9px;flex-basis:100%}.plan-title h2{font-size:20px;margin:0;font-weight:600}.plan-title small{font-size:12px;color:var(--secondary-text-color)}
.plan-start{display:flex;align-items:end;gap:8px;width:100%;min-width:0;flex-wrap:wrap}
.plan-shortcuts{display:flex;gap:5px;flex-wrap:wrap}.plan-view button:disabled{cursor:default}
.plan-field{display:grid;gap:4px;flex:1 1 180px;min-width:0;font-size:12px;color:var(--secondary-text-color)}
.plan-view .plan-date{font-size:14px;text-align:left;color:var(--primary-text-color);min-height:38px}
.plan-view input[type=datetime-local]{width:100%;min-width:0;font-size:14px;min-height:38px;padding:5px 7px}
.plan-view button{min-height:36px;padding:5px 9px;font-size:12px}
.plan-shortcuts button[aria-pressed=true],.plan-zoom button[aria-pressed=true]{background:var(--secondary-background-color);color:var(--primary-color);border-color:transparent}
.plan-status{font-size:12px;color:var(--secondary-text-color);margin:0 0 12px;line-height:1.4}
.plan-columns,.plan-row>summary{display:grid;grid-template-columns:minmax(85px,1fr) 100px 110px 9px;gap:9px;align-items:center}
.plan-columns{font-size:12px;color:var(--secondary-text-color);padding-bottom:5px}.plan-columns span{text-align:right}
.plan-view .plan-sort{font-size:12px;border:0;background:transparent;color:var(--secondary-text-color);padding:0;min-width:0;min-height:36px;width:100%}
.plan-row{margin:0;border-top:1px solid var(--divider-color)}
.plan-row>summary{min-height:62px;box-sizing:border-box;padding:9px 0;line-height:1.35;list-style:none;font-size:14px}
.plan-row>summary::-webkit-details-marker,.plan-graph>summary::-webkit-details-marker,.plan-conditions>summary::-webkit-details-marker,.plan-basis>summary::-webkit-details-marker{display:none}
.plan-row>summary::after{content:'⌄';color:var(--secondary-text-color);grid-column:4}.plan-row[open]>summary::after{content:'⌃'}
.plan-name-group{display:flex;align-items:center;gap:8px;min-width:0}.plan-row-swatch{display:inline-block;width:5px;height:23px;flex:none;border-radius:2px}
.plan-name{min-width:0;overflow-wrap:anywhere;font-weight:500}
.plan-cost-group{text-align:right}.plan-limit{display:block;font-size:11px;color:var(--warning-color);margin-top:2px}.plan-cost{text-align:right;white-space:nowrap;font-size:16px;font-weight:600;font-variant-numeric:tabular-nums}.plan-cost[data-missing=true]{font-size:12px;font-weight:400;color:var(--secondary-text-color)}
.plan-best{text-align:right;font-size:12px;font-variant-numeric:tabular-nums}.plan-best-price{display:block;font-size:14px;margin-bottom:2px;white-space:nowrap}.plan-best>span:last-child{color:var(--secondary-text-color)}
.plan-body{padding:0 0 12px 13px;display:flex;flex-wrap:wrap;gap:6px 14px;font-size:12px;color:var(--secondary-text-color)}.plan-body-notes{display:contents}.plan-body p{flex-basis:100%;margin:0;font-size:12px}
.plan-coverage{color:var(--warning-color);flex-basis:100%}
.plan-graph,.plan-conditions,.plan-basis{border-top:1px solid var(--divider-color);margin:3px 0 0}
.plan-graph>summary,.plan-conditions>summary,.plan-basis>summary{min-height:42px;line-height:1.4;display:flex;align-items:center;justify-content:space-between;font-size:13px;font-weight:500;list-style:none}
.plan-graph>summary::after,.plan-conditions>summary::after,.plan-basis>summary::after{content:'⌄';color:var(--secondary-text-color)}
.plan-graph[open]>summary::after,.plan-conditions[open]>summary::after,.plan-basis[open]>summary::after{content:'⌃'}
.plan-graph-tools{display:flex;justify-content:space-between;gap:5px;flex-wrap:wrap;margin-bottom:6px;align-items:center}
.plan-zoom{display:flex;gap:3px}.plan-zoom button{border:0;min-height:32px;padding:4px 7px}
.plan-legend{display:flex;align-items:center;gap:3px 5px;flex-wrap:wrap;font-size:12px;min-width:0}.plan-legend>span,.plan-view .curve-toggle{display:inline-flex;align-items:center;gap:5px}
.plan-view .curve-toggle{background:transparent;color:var(--secondary-text-color);border:0;min-height:30px;padding:3px 5px;font-size:12px;max-width:150px;overflow-wrap:anywhere}
.plan-view .curve-toggle[aria-pressed=false]{opacity:.55;text-decoration:line-through}.plan-view .curve-name{overflow:hidden;text-overflow:ellipsis;white-space:nowrap}
.plan-swatch{display:inline-block;width:14px;height:0;border-top:2px solid;flex:none}.plan-price-swatch{height:3px;border:0;width:18px;background:linear-gradient(90deg,var(--plan-low),var(--plan-mid),var(--plan-high))}
.plan-chart{position:relative;min-width:0}.plan-chart svg{display:block;width:100%;height:auto;font-size:11px;color:var(--secondary-text-color);overflow:visible}.plan-chart svg text{fill:var(--secondary-text-color)}
.plan-chart .grid{stroke:var(--divider-color);stroke-width:1}.plan-chart .start-line{stroke:var(--secondary-text-color);stroke-width:1;stroke-dasharray:3 4}.plan-motion{transition:transform 300ms ease}
.plan-scale{display:flex;justify-content:space-between;gap:4px 12px;flex-wrap:wrap;font-size:11px;color:var(--secondary-text-color);font-variant-numeric:tabular-nums;margin:0 0 9px}.plan-color-bar{display:inline-block;vertical-align:middle;width:35px;height:3px;margin:0 5px;background:linear-gradient(90deg,var(--plan-low),var(--plan-mid),var(--plan-high))}
.plan-message{font-size:12px;line-height:1.4;margin:5px 0!important;color:var(--secondary-text-color)}.plan-message:empty{display:none}
.plan-tooltip{position:absolute;z-index:2;max-width:min(240px,90%);white-space:pre-line;pointer-events:none;background:var(--card-background-color);color:var(--primary-text-color);border:1px solid var(--divider-color);border-radius:6px;padding:7px 9px;font-size:12px;box-shadow:0 2px 8px #0002}
.plan-retry{margin-top:5px}.plan-chart svg:focus-visible{outline:2px solid var(--primary-color);outline-offset:2px}
.plan-deadline{display:flex;gap:9px;align-items:center;flex-wrap:wrap;margin-bottom:9px}.plan-deadline-label{display:flex;gap:6px;align-items:center;font-size:13px}.plan-deadline input[type=datetime-local]{flex:1 1 190px;width:auto}.plan-deadline input[type=checkbox]{width:18px;height:18px;accent-color:var(--primary-color)}
.plan-basis p{font-size:12px;margin:0 0 8px;line-height:1.4;color:var(--secondary-text-color)}.plan-basis a{display:inline-block;font-size:12px;margin:0 0 9px}
@container(max-width:430px){.plan-start{gap:7px}.plan-field{flex-basis:100%}.plan-view input[type=datetime-local]{font-size:16px;min-height:40px}.plan-columns,.plan-row>summary{grid-template-columns:minmax(48px,1fr) 80px 82px 8px;gap:5px}.plan-best{font-size:11px}.plan-best-price{font-size:13px}.plan-cost{font-size:15px}.plan-name{font-size:13px}.plan-row>summary{min-height:65px}.plan-chart svg{font-size:11px}}
@media(pointer:coarse){.plan-view button,.plan-view select,.plan-view input[type=datetime-local]{min-height:44px}.plan-view .curve-toggle{min-height:44px}}
@media(prefers-reduced-motion:reduce){.plan-motion{transition:none}}
`;

export function renderPlanning(
  card,
  entryId,
  profiles,
  status,
  el,
  number,
  zonedTimestamp,
) {
  if (this._planEntry !== entryId) {
    this._planState?.queue?.dispose();
    this._planState?.observer?.disconnect();
    this._planEntry = entryId;
    this._planState = {
      id: ++instance,
      entryId,
      followNow: true,
      fixed: null,
      editing: false,
      waiting: false,
      error: "",
      inputError: "",
      deadlineError: "",
      finishBy: null,
      deadlineEnabled: false,
      expiredBest: false,
      refreshProgram: null,
      data: null,
      rows: new Map(),
      hidden: new Set(),
      nodes: null,
      queue: null,
      geometry: null,
      revision: null,
      zoom: "all",
      sort: "program",
      order: [],
      sortPending: false,
    };
  }
  const f = this._planState;
  f.hass = this._hass;
  f.status = status;
  f.profiles = profiles;
  if (
    status.price_status === "updating" &&
    f.invalidatedRevision !== status.plan_revision
  ) {
    f.invalidatedRevision = status.plan_revision;
    f.queue?.invalidate();
    f.data = null;
    f.geometry = null;
    f.nodes?.chart.replaceChildren();
    f.nodes?.legend.replaceChildren();
    f.nodes?.scale.replaceChildren();
  }
  if (!f.hass.user?.is_admin) {
    f.queue?.dispose();
    f.queue = null;
    f.data = null;
    f.waiting = false;
    f.geometry = null;
    f.nodes?.chart.replaceChildren();
    f.nodes?.legend.replaceChildren();
    f.nodes?.scale.replaceChildren();
  }
  const valid = () => this._planState === f && !f.closed;
  const zone = () => f.hass.config?.time_zone || "Europe/Stockholm";
  const unit = () => (f.currency === "SEK" ? "kr" : f.currency || "SEK");
  const format = (seconds, compact = false) =>
    Number.isFinite(seconds)
      ? new Date(seconds * 1000).toLocaleString(
          f.hass.locale?.language || "sv-SE",
          {
            timeZone: zone(),
            ...(compact
              ? { day: "2-digit", month: "2-digit" }
              : { day: "numeric", month: "short" }),
            hour: "2-digit",
            minute: "2-digit",
          },
        )
      : "—";
  const amount = (value) =>
    Number.isFinite(value)
      ? `${value.toLocaleString("sv-SE", { minimumFractionDigits: 2, maximumFractionDigits: 2 })} ${unit()}`
      : "—";
  if (!f.nodes) {
    const node = el("section", undefined, "plan-view"),
      style = el("style");
    style.textContent = css;
    node.append(style);
    const head = el("div", undefined, "plan-head"),
      title = el("div", undefined, "plan-title"),
      h2 = el("h2"),
      mode = el("small");
    title.append(h2, mode);
    const controls = el("div", undefined, "plan-start"),
      label = el("div", undefined, "plan-field"),
      input = el("input");
    input.type = "datetime-local";
    input.setAttribute("aria-label", "Planerad start");
    input.dataset.focusKey = "planning-start";
    const dateButton = el("button", "", "secondary plan-date");
    dateButton.type = "button";
    dateButton.dataset.focusKey = "planning-date";
    dateButton.setAttribute("aria-expanded", "false");
    const dateEditor = el("div", undefined, "plan-date-editor");
    dateEditor.id = `planning-date-${f.id}`;
    dateEditor.hidden = true;
    dateEditor.append(input);
    dateButton.setAttribute("aria-controls", dateEditor.id);
    label.append(el("span", "Planerad start"), dateButton, dateEditor);
    const offset = el("span");
    offset.id = `planning-offset-${f.id}`;
    offset.hidden = true;
    input.setAttribute("aria-describedby", offset.id);
    label.append(offset);
    const shortcuts = el("div", undefined, "plan-shortcuts"),
      earlier = el("button", "−1 h", "secondary"),
      now = el("button", "Nu", "secondary"),
      later = el("button", "+1 h", "secondary");
    for (const [button, key, caption] of [
      [earlier, "earlier", "Flytta starten en timme bakåt"],
      [now, "now", "Använd aktuell tid som start"],
      [later, "later", "Flytta starten en timme framåt"],
    ]) {
      button.type = "button";
      button.dataset.focusKey = `planning-${key}`;
      button.setAttribute("aria-label", caption);
    }
    shortcuts.append(earlier, now, later);
    controls.append(label, shortcuts);
    head.append(title, controls);
    const info = el("div", undefined, "plan-status");
    const columns = el("div", undefined, "plan-columns");
    const sort = el("select", undefined, "plan-sort");
    sort.setAttribute("aria-label", "Sortera program");
    sort.dataset.focusKey = "planning-sort";
    for (const [value, caption] of [
      ["program", "Programordning"],
      ["price", "Lägst kostnad"],
    ]) {
      const option = el("option", caption);
      option.value = value;
      sort.append(option);
    }
    columns.append(sort, el("span", "Vid vald start"), el("span", "Billigast"));
    const rows = el("div");
    const graph = el("details", undefined, "plan-graph");
    graph.open = true;
    const summary = el("summary", "Pris och förbrukning");
    summary.dataset.focusKey = "planning-graph";
    const legend = el("div", undefined, "plan-legend"),
      chart = el("div", undefined, "plan-chart"),
      scale = el("div", undefined, "plan-scale"),
      message = el("p", "", "plan-message"),
      retry = el("button", "Försök igen", "secondary plan-retry");
    retry.type = "button";
    retry.hidden = true;
    message.setAttribute("role", "status");
    message.setAttribute("aria-live", "polite");
    const graphTools = el("div", undefined, "plan-graph-tools"),
      zoomControls = el("div", undefined, "plan-zoom"),
      zoomAll = el("button", "Alla priser", "secondary"),
      zoomRun = el("button", "Körningen", "secondary");
    for (const [button, mode] of [
      [zoomAll, "all"],
      [zoomRun, "run"],
    ]) {
      button.type = "button";
      button.dataset.focusKey = `planning-zoom-${mode}`;
      button.addEventListener("click", () => {
        f.zoom = mode;
        draw();
      });
    }
    zoomControls.append(zoomAll, zoomRun);
    graphTools.append(zoomControls, legend);
    graph.append(summary, graphTools, chart, scale);
    const conditions = el("details", undefined, "plan-conditions"),
      conditionsSummary = el("summary", "Planeringsvillkor"),
      deadlineLabel = el("label", undefined, "plan-deadline-label"),
      deadlineToggle = el("input"),
      deadlineInput = el("input"),
      deadlineMessage = el("p", "", "plan-message");
    conditionsSummary.dataset.focusKey = "planning-conditions";
    deadlineToggle.type = "checkbox";
    deadlineToggle.dataset.focusKey = "planning-deadline-toggle";
    deadlineLabel.append(deadlineToggle, el("span", "Åter i vila senast"));
    deadlineInput.type = "datetime-local";
    deadlineInput.value = localInput(Date.now() / 1000 + 43200, zone());
    deadlineInput.setAttribute("aria-label", "Åter i vila senast");
    deadlineInput.dataset.focusKey = "planning-deadline";
    const deadlineBody = el("div", undefined, "plan-deadline");
    deadlineBody.append(deadlineLabel, deadlineInput);
    conditions.append(conditionsSummary, deadlineBody, deadlineMessage);
    const basis = el("details", undefined, "plan-basis"),
      basisSummary = el("summary", "Prisunderlag"),
      basisText = el("p"),
      basisDeadline = el("p"),
      settings = el("a", "Prisinställningar");
    settings.href = "/config/integrations/integration/dishwasher_optimizer";
    basisSummary.dataset.focusKey = "planning-basis";
    basis.append(basisSummary, basisText, basisDeadline, settings);
    node.append(
      head,
      info,
      columns,
      rows,
      message,
      retry,
      graph,
      conditions,
      basis,
    );
    f.nodes = {
      node,
      h2,
      mode,
      input,
      dateButton,
      dateEditor,
      offset,
      now,
      earlier,
      later,
      sort,
      columns,
      info,
      rows,
      graph,
      legend,
      chart,
      scale,
      message,
      retry,
      zoomAll,
      zoomRun,
      conditions,
      deadlineToggle,
      deadlineInput,
      deadlineMessage,
      basis,
      basisText,
      basisDeadline,
      settings,
    };
    dateButton.addEventListener("click", () => {
      dateEditor.hidden = !dateEditor.hidden;
      dateButton.setAttribute("aria-expanded", String(!dateEditor.hidden));
      if (!dateEditor.hidden) input.focus();
    });
    sort.addEventListener("change", () => {
      f.sort = sort.value;
      f.sortPending = true;
      draw();
    });
    input.addEventListener("input", () => {
      f.editing = true;
      f.error = "";
      f.inputError = "";
      input.setCustomValidity("");
      input.removeAttribute("aria-invalid");
      f.expiredBest = false;
      f.refreshProgram = null;
      f.queue?.invalidate();
      f.waiting = false;
      draw();
    });
    input.addEventListener("change", () => {
      try {
        const iso = zonedTimestamp(input.value, zone());
        if (Date.parse(iso) < Date.now() - 60000)
          throw Error("Välj en framtida starttid eller tryck Nu.");
        input.setCustomValidity("");
        input.removeAttribute("aria-invalid");
        f.inputError = "";
        f.fixed = iso;
        f.followNow = false;
        f.editing = false;
        f.expiredBest = false;
        f.refreshProgram = null;
        f.sortPending = true;
        request(true);
      } catch (error) {
        f.inputError = error.message || String(error);
        input.setCustomValidity(f.inputError);
        input.setAttribute("aria-invalid", "true");
        draw();
      }
    });
    deadlineToggle.addEventListener("change", () => {
      f.deadlineEnabled = deadlineToggle.checked;
      updateDeadline();
    });
    deadlineInput.addEventListener("input", () => {
      if (!f.deadlineEnabled) return;
      f.deadlineError = "Bekräfta datum och klockslag för tidsgränsen.";
      f.queue?.invalidate();
      f.waiting = false;
      draw();
    });
    deadlineInput.addEventListener("change", () => updateDeadline());
    now.addEventListener("click", () => chooseStart(null));
    earlier.addEventListener("click", () => shiftStart(-3600));
    later.addEventListener("click", () => shiftStart(3600));
    retry.addEventListener("click", () => request(true));
    graph.addEventListener("toggle", () => {
      if (graph.open) drawPlot();
    });
    if (typeof ResizeObserver !== "undefined") {
      f.observer = new ResizeObserver(() => drawPlot());
      f.observer.observe(chart);
    }
  }
  const n = f.nodes;
  card.append(n.node);
  function chooseStart(seconds) {
    if (!f.hass.user?.is_admin) return;
    const current = Date.now() / 1000;
    f.followNow = seconds === null;
    f.fixed = f.followNow ? null : new Date(seconds * 1000).toISOString();
    f.editing = false;
    f.error = "";
    f.inputError = "";
    f.expiredBest = false;
    f.refreshProgram = null;
    f.sortPending = true;
    n.input.setCustomValidity("");
    n.input.removeAttribute("aria-invalid");
    n.input.value = localInput(f.followNow ? current : seconds, zone());
    request(true);
  }
  function updateDeadline() {
    try {
      const finish = f.deadlineEnabled
        ? zonedTimestamp(n.deadlineInput.value, zone())
        : null;
      if (finish && Date.parse(finish) <= Date.now())
        throw Error("Välj en framtida tidsgräns.");
      f.finishBy = finish;
      f.deadlineError = "";
      n.deadlineInput.setCustomValidity("");
      n.deadlineInput.removeAttribute("aria-invalid");
      f.sortPending = true;
      request(true);
    } catch (error) {
      f.deadlineError = error.message || String(error);
      n.deadlineInput.setCustomValidity(f.deadlineError);
      n.deadlineInput.setAttribute("aria-invalid", "true");
      f.queue?.invalidate();
      f.waiting = false;
      draw();
    }
  }
  function shiftStart(delta) {
    if (f.editing) return;
    const current = Date.now() / 1000,
      selected = f.followNow
        ? current
        : Math.max(current, Date.parse(f.fixed) / 1000);
    const shifted = selected + delta;
    chooseStart(shifted <= current ? null : shifted);
  }
  function request(force = false) {
    if (
      !valid() ||
      !n.node.isConnected ||
      !f.hass.user?.is_admin ||
      f.editing ||
      f.deadlineError
    )
      return;
    if (!f.queue)
      f.queue = new LatestPlanRequests(
        (input) => thisCard.service(entryId, "get_plan", input),
        (data) => {
          if (!valid()) return;
          if (
            data?.entry_id !== entryId ||
            !Array.isArray(data.profiles) ||
            !Array.isArray(data.prices) ||
            !Number.isFinite(data.now) ||
            !Number.isFinite(data.selected_start)
          )
            throw Error("Ogiltigt planeringssvar.");
          f.data = data;
          f.waiting = false;
          f.error = "";
          f.refreshProgram = null;
          draw();
        },
        (error) => {
          if (!valid()) return;
          f.waiting = false;
          f.error = error.message || String(error);
          draw();
        },
      );
    const key = JSON.stringify([f.status.plan_revision, f.fixed, f.finishBy]);
    if (force) f.queue.invalidate();
    if (force || key !== f.queue.key) {
      const input = f.followNow ? {} : { started_at: f.fixed };
      if (f.refreshProgram !== null) input.refresh_program = f.refreshProgram;
      if (f.finishBy !== null) input.finish_by = f.finishBy;
      f.waiting = true;
      f.error = "";
      f.queue.request(key, input);
      draw();
    }
  }
  const thisCard = this;
  function draw() {
    if (!valid()) return;
    const admin = Boolean(f.hass.user?.is_admin);
    n.h2.textContent = thisCard._config.title || "Diskpilot";
    n.mode.textContent =
      f.status.registration?.stage === "recording"
        ? "Registrering pågår"
        : f.status.registration?.stage === "review"
          ? "Utkast väntar på granskning"
          : f.status.start_pending
            ? "Kontrollerar diskstart"
            : statusState() === "running"
              ? "Körning pågår"
              : statusState() === "source_unavailable"
                ? "Effektsensorn saknas"
                : "Planering";
    n.input.disabled = !admin;
    n.dateButton.disabled = !admin;
    n.now.disabled = !admin;
    n.earlier.disabled =
      !admin || f.editing || f.followNow || Date.parse(f.fixed) <= Date.now();
    n.later.disabled = !admin || f.editing;
    n.now.setAttribute("aria-pressed", String(f.followNow && !f.editing));
    n.zoomAll.disabled = n.zoomRun.disabled = !admin;
    n.zoomAll.setAttribute("aria-pressed", String(f.zoom === "all"));
    n.zoomRun.setAttribute("aria-pressed", String(f.zoom === "run"));
    n.sort.value = f.sort;
    n.conditions.hidden = !admin;
    n.deadlineToggle.checked = f.deadlineEnabled;
    n.deadlineInput.disabled = !admin || !f.deadlineEnabled;
    n.deadlineMessage.textContent = f.deadlineError;
    const changedZone = f.inputZone !== zone();
    f.inputZone = zone();
    if (changedZone && f.editing) {
      f.editing = false;
      f.error = "";
      f.inputError = "";
      n.input.setCustomValidity("");
      n.input.removeAttribute("aria-invalid");
    }
    if (changedZone && f.finishBy) {
      n.deadlineInput.value = localInput(Date.parse(f.finishBy) / 1000, zone());
      f.deadlineError = "";
      n.deadlineInput.setCustomValidity("");
      n.deadlineInput.removeAttribute("aria-invalid");
    }
    const selected = f.followNow
      ? !f.waiting && !f.error && f.data?.selected_start != null
        ? f.data.selected_start
        : Date.now() / 1000
      : Date.parse(f.fixed) / 1000;
    if (!f.editing) {
      const localTime = localInput(selected, zone());
      if (changedZone || n.node.getRootNode().activeElement !== n.input)
        n.input.value = localTime;
      n.offset.textContent = repeatedTimeOffset(selected, zone(), localTime);
    }
    n.offset.hidden = f.editing || !n.offset.textContent;
    n.dateButton.textContent =
      relativeTime(selected, Date.now() / 1000, zone()) +
      (f.followNow ? " · Nu" : "") +
      " ⌄";
    const updating = f.status.price_status === "updating";
    const data = updating ? null : f.data;
    f.currency = data?.currency || nativeProfiles()[0]?.currency || "SEK";
    const prices = data?.prices || [];
    let lastPrice = null;
    for (const p of prices) lastPrice = Math.max(lastPrice ?? p[1], p[1]);
    n.info.textContent = !admin
      ? "Billigaste kostnad och start · enligt programsensorerna"
      : data
        ? `${lastPrice ? "Elpriser till " + relativeTime(lastPrice, Date.now() / 1000, zone()).toLocaleLowerCase("sv-SE") : statuses[data.price_status] || "Framtida priser saknas."}`
        : updating
          ? statuses.updating
          : "Planering med sparade profiler";
    n.columns.children[1].textContent = admin ? "Vid vald start" : "Kostnad";
    n.basisText.textContent = updating
      ? statuses.updating
      : data?.price_basis || f.status.price_basis || "Prisunderlag saknas.";
    n.basisDeadline.textContent = data
      ? `Billigaste start söks för körningar som återgår till vila senast ${format(data.planning_deadline)}. Beräkningen kräver kända elpriser för hela körningen.`
      : "";
    n.settings.hidden = !admin;
    const source = data?.profiles || nativeProfiles();
    const ids = new Set(source.map((p) => p.id));
    for (const [id, row] of f.rows)
      if (!ids.has(id)) {
        row.section.remove();
        f.rows.delete(id);
      }
    source.forEach((p, index) => {
      let row = f.rows.get(p.id);
      if (!row) {
        const section = el("details", undefined, "plan-row");
        const summary = el("summary");
        summary.dataset.focusKey = `plan-${entryId}-${p.id}`;
        const name = el("span", "", "plan-name"),
          value = el("span", "", "plan-cost"),
          nameGroup = el("span", undefined, "plan-name-group"),
          swatch = el("span", undefined, "plan-row-swatch");
        nameGroup.append(swatch, name);
        const costGroup = el("span", undefined, "plan-cost-group"),
          limit = el("span", "Efter tidsgränsen", "plan-limit");
        costGroup.append(value, limit);
        limit.hidden = true;
        const best = el("span", "", "plan-best"),
          bestTime = el("span"),
          bestPrice = el("span", "", "plan-best-price");
        best.append(bestPrice, bestTime);
        summary.append(nameGroup, costGroup, best);

        const body = el("div", undefined, "plan-body");
        const detailName = el("span"),
          energy = el("span"),
          duration = el("span");
        const samples = el("span"),
          selectedEnd = el("span"),
          coverage = el("span", "", "plan-coverage");
        const bestButton = el("button", "Välj billigaste start", "secondary");
        bestButton.type = "button";
        bestButton.dataset.focusKey = `planning-best-${entryId}-${p.id}`;
        const notes = el("div", undefined, "plan-body-notes");
        body.append(
          detailName,
          energy,
          duration,
          samples,
          selectedEnd,
          bestButton,
          coverage,
          notes,
        );
        section.append(summary, body);
        row = {
          section,
          summary,
          name,
          value,
          bestTime,
          bestPrice,
          body,
          detailName,
          energy,
          duration,
          samples,
          selectedEnd,
          coverage,
          swatch,
          limit,
          bestButton,
          notes,
          optimalStart: null,
        };
        bestButton.addEventListener("click", () => {
          if (bestButton.disabled || (f.refreshProgram !== null && f.waiting))
            return;
          if (row.optimalStart <= Date.now() / 1000) {
            f.expiredBest = true;
            f.refreshProgram = p.id;
            request(true);
            return;
          }
          chooseStart(row.optimalStart);
        });
        f.rows.set(p.id, row);
      }
      if (row.section.parentNode !== n.rows) n.rows.append(row.section);
      row.name.textContent = p.name;
      const cost = updating ? null : p.cost,
        optimalStart = updating ? null : p.optimal_start;
      const value = updating
        ? null
        : admin
          ? !f.waiting &&
            !f.editing &&
            !f.error &&
            !f.inputError &&
            !f.deadlineError
            ? p.selected_cost
            : null
          : cost;
      const missing =
        admin &&
        data &&
        !updating &&
        !f.waiting &&
        !f.editing &&
        !f.error &&
        !f.inputError &&
        !f.deadlineError &&
        p.sample_count &&
        p.selected_cost === null;
      row.value.textContent = missing ? "Pris saknas" : amount(value);
      row.value.setAttribute("data-missing", String(Boolean(missing)));
      row.bestTime.textContent = Number.isFinite(optimalStart)
        ? relativeTime(optimalStart, Date.now() / 1000, zone())
        : "—";
      row.bestPrice.textContent = Number.isFinite(cost) ? amount(cost) : "";
      row.limit.hidden =
        !admin ||
        p.meets_finish_by !== false ||
        f.waiting ||
        f.editing ||
        Boolean(f.error || f.inputError || f.deadlineError);
      row.summary.setAttribute(
        "aria-label",
        `${p.name}, ${admin ? "kostnad vid vald start" : "billigaste kostnad"} ${amount(value)}, billigast ${format(optimalStart)}, ${amount(cost)}`,
      );
      row.detailName.textContent = p.name;
      row.energy.textContent = `Energi: ${p.energy_kwh == null ? "—" : number(p.energy_kwh, 3) + " kWh"}`;
      row.duration.textContent = `Tid: ${p.duration_seconds == null ? "—" : number(p.duration_seconds / 60, 1) + " min"}`;
      row.samples.textContent = `Underlag: ${p.sample_count || 0} märkta körningar`;
      row.selectedEnd.textContent = `Åter i vila vid vald start: ${format(f.waiting || f.editing || f.error ? null : p.selected_end)}`;
      const coverage = missing ? coverageMessage(p, data) : "";
      row.coverage.textContent = coverage;
      row.coverage.hidden = !coverage;
      row.optimalStart = optimalStart;
      const bestAtCalculation =
        Number.isFinite(optimalStart) && optimalStart === data?.now;
      row.bestButton.hidden = !admin || bestAtCalculation;
      row.bestButton.disabled =
        !admin ||
        updating ||
        bestAtCalculation ||
        !Number.isFinite(optimalStart);
      if (
        row.bestButton.disabled &&
        n.node.getRootNode().activeElement === row.bestButton
      )
        row.summary.focus();
      row.bestButton.setAttribute(
        "aria-label",
        `Välj billigaste start för ${p.name}`,
      );

      const notes = [];
      if (admin && bestAtCalculation)
        notes.push(
          el(
            "p",
            "Billigast vid beräkningen var att starta direkt. Använd Nu för att jämföra.",
          ),
        );
      if (Number.isFinite(value) && Number.isFinite(cost)) {
        notes.push(
          el(
            "span",
            `Spara ${amount(Math.max(0, value - cost))} vid billigaste start`,
          ),
        );
      }
      if (
        admin &&
        p.meets_finish_by === false &&
        !f.waiting &&
        !f.editing &&
        !f.error &&
        !f.deadlineError
      )
        notes.push(
          el(
            "p",
            "Vald start återgår till vila efter din tidsgräns.",
            "plan-coverage",
          ),
        );
      if (
        admin &&
        f.finishBy &&
        !Number.isFinite(optimalStart) &&
        p.sample_count &&
        !f.waiting &&
        !f.deadlineError
      )
        notes.push(
          el("p", "Ingen start med fullständiga priser ryms före tidsgränsen."),
        );
      if (!p.sample_count)
        notes.push(el("p", "Behöver en komplett märkt körning."));
      else if (p.sample_count === 1)
        notes.push(el("p", "Första uppskattningen · baserad på en körning."));
      notes.push(
        el(
          "p",
          "Beräknat från sparade minutprofiler. Åter i vila är inte verifierad färdigtid.",
        ),
      );
      row.notes.replaceChildren(...notes);
      row.color = palette[index % palette.length];
      row.swatch.style.backgroundColor = row.color;
      row.dash = ["", "5 3", "2 3", "8 3", "5 2 1 2", "1 2"][index % 6];
    });
    if (!f.order.length || (f.sortPending && !f.waiting)) {
      const ordered = [...source];
      if (f.sort === "price")
        ordered.sort(
          (a, b) =>
            (admin ? (a.selected_cost ?? Infinity) : (a.cost ?? Infinity)) -
            (admin ? (b.selected_cost ?? Infinity) : (b.cost ?? Infinity)),
        );
      f.order = ordered.map((p) => p.id);
      f.sortPending = false;
    }
    for (const id of ids) if (!f.order.includes(id)) f.order.push(id);
    f.order = f.order.filter((id) => ids.has(id));
    const displayed = [...n.rows.children];
    if (
      displayed.some(
        (node, index) => node !== f.rows.get(f.order[index])?.section,
      )
    ) {
      const focused = n.node.getRootNode().activeElement;
      for (const id of f.order) n.rows.append(f.rows.get(id).section);
      if (focused?.isConnected) focused.focus({ preventScroll: true });
    }
    const progress =
      f.refreshProgram !== null
        ? "Startförslaget har passerat. Uppdaterar förslaget…"
        : "Beräknar vald start…";
    const result =
      data && data.price_status !== "ok"
        ? statuses[data.price_status] || "Framtida priser saknas."
        : data && source.some((p) => p.sample_count && p.selected_cost === null)
          ? "Elpriserna täcker inte hela körningen för alla program. Se programdetaljerna."
          : "";
    const settledMessage = f.expiredBest
      ? `Startförslaget har passerat. Förslaget har uppdaterats. ${result}`.trimEnd()
      : result;
    n.retry.hidden = !f.error || !admin;
    n.message.textContent = !admin
      ? "Graf och valbar start kräver administratör, eftersom profilkurvorna är skyddade."
      : f.inputError
        ? `${f.inputError} Välj en starttid eller tryck Nu.`
        : f.deadlineError
          ? f.deadlineError
          : updating
            ? statuses.updating
            : f.error
              ? `Kunde inte hämta planeringen: ${f.error}`
              : f.editing
                ? "Välj och bekräfta starttiden."
                : f.waiting
                  ? progress
                  : settledMessage;
    n.chart.hidden = Boolean(
      updating ||
        f.waiting ||
        f.editing ||
        f.error ||
        f.inputError ||
        f.deadlineError,
    );
    n.legend.hidden = n.chart.hidden;
    n.scale.hidden = n.chart.hidden;
    n.graph.setAttribute("aria-busy", String(f.waiting));
    drawPlot();
  }
  function statusState() {
    return (
      thisCard._hass.states &&
      Object.values(thisCard._hass.states).find(
        (s) =>
          s.attributes.diskpilot_entry_id === entryId &&
          "recent_runs" in s.attributes,
      )?.state
    );
  }
  function nativeProfiles() {
    const entities = Object.values(f.hass.states).filter(
      (s) =>
        s.attributes.diskpilot_entry_id === entryId && s.attributes.program,
    );
    return f.profiles.map((p) => {
      const a =
        entities.find((s) => s.attributes.program === p.id)?.attributes || {};
      return {
        id: p.id,
        name: p.name,
        ...a,
        cost: Number.isFinite(
          Number(entities.find((s) => s.attributes.program === p.id)?.state),
        )
          ? Number(entities.find((s) => s.attributes.program === p.id)?.state)
          : null,
        duration_seconds: a.duration_minutes * 60,
        optimal_start: a.optimal_start
          ? Date.parse(a.optimal_start) / 1000
          : null,
        optimal_end: a.optimal_end ? Date.parse(a.optimal_end) / 1000 : null,
      };
    });
  }
  function drawPlot() {
    if (
      !valid() ||
      f.status.price_status === "updating" ||
      !n.graph.open ||
      !f.data ||
      !f.hass.user?.is_admin
    )
      return;
    const view = f.data,
      width = Math.floor(n.chart.clientWidth);
    if (width < 160) return;
    const domain = chartDomain(view, f.zoom, f.hidden),
      range = priceRange(view.prices),
      height = width < 440 ? 175 : 190;
    const key = JSON.stringify([
      width,
      domain,
      view.currency,
      zone(),
      view.prices,
      view.profiles.map((p) => [p.id, p.name, p.duration_seconds, p.energy_wh]),
    ]);
    if (key !== f.geometry) {
      const focused = n.node.getRootNode().activeElement === f.svg;
      f.geometry = key;
      f.groups = new Map();
      const left = 40,
        right = 43,
        top = 25,
        bottom = 38,
        pw = width - left - right,
        ph = height - top - bottom,
        span = domain.end - domain.start;
      const low = Math.min(0, range?.min || 0),
        high = Math.max(0, range?.max || 0),
        pad = high === low ? 1 : 0;
      const py = (v) => top + ph * (1 - (v - low) / (high - low + pad));
      let peak = 1;
      for (const p of view.profiles)
        for (const seg of powerSegments(p, 0)) peak = Math.max(peak, seg.watts);
      peak *= 1.1;
      const wy = (v) => top + ph * (1 - v / peak),
        x = (t) => left + (pw * (t - domain.start)) / span,
        rx = (t) => left + (pw * t) / span;
      f.geometryInfo = { left, right, top, pw, ph, span, domain };
      const svg = svgNode("svg", {
        viewBox: `0 0 ${width} ${height}`,
        height,
        role: "img",
        tabindex: "0",
        "data-focus-key": `planning-chart-${entryId}`,
        "aria-label":
          "Elpris och beräknad effekt i W. Använd höger och vänster pil för att läsa värden; Esc stänger värderutan.",
      });
      svg.append(
        svgNode(
          "desc",
          {},
          "Priskurvan färgas relativt lägsta och högsta tillgängliga pris. Programkurvorna är beräknade från sparade minutprofiler. Saknade prisintervall ritas som luckor.",
        ),
      );
      const defs = svgNode("defs"),
        clip = svgNode("clipPath", { id: `plan-clip-${f.id}` });
      clip.append(svgNode("rect", { x: left, y: top, width: pw, height: ph }));
      defs.append(clip);
      const gradientId = `plan-price-${f.id}`;
      if (range && !range.flat) {
        const gradient = svgNode("linearGradient", {
          id: gradientId,
          gradientUnits: "userSpaceOnUse",
          x1: 0,
          x2: 0,
          y1: py(range.max),
          y2: py(range.min),
        });
        for (const [offset, color] of [
          ["0%", "var(--plan-high)"],
          ["50%", "var(--plan-mid)"],
          ["100%", "var(--plan-low)"],
        ])
          gradient.append(svgNode("stop", { offset, "stop-color": color }));
        defs.append(gradient);
      }
      svg.append(defs);
      for (let i = 0; i < 3; i++) {
        const yy = top + (ph * i) / 2;
        svg.append(
          svgNode("line", {
            x1: left,
            x2: width - right,
            y1: yy,
            y2: yy,
            class: "grid",
          }),
          svgNode(
            "text",
            { x: left - 5, y: yy + 4, "text-anchor": "end" },
            number(high + pad - ((high - low + pad) * i) / 2, 2),
          ),
          svgNode(
            "text",
            { x: width - right + 5, y: yy + 4 },
            number(peak * (1 - i / 2), 0),
          ),
        );
      }
      svg.append(
        svgNode("text", { x: left, y: 12 }, `${view.currency}/kWh`),
        svgNode(
          "text",
          { x: width - right, y: 12, "text-anchor": "end" },
          "Effekt · W",
        ),
      );
      const ticks = width < 440 ? 3 : 4;
      let previousDate = "";
      for (let i = 0; i <= ticks; i++) {
        const t = domain.start + (span * i) / ticks,
          date = new Date(t * 1000).toLocaleDateString("sv-SE", {
            timeZone: zone(),
            day: "numeric",
            month: "numeric",
          });
        svg.append(
          svgNode(
            "text",
            {
              x: x(t),
              y: height - 7,
              "text-anchor": i === 0 ? "start" : i === ticks ? "end" : "middle",
            },
            new Date(t * 1000).toLocaleTimeString("sv-SE", {
              timeZone: zone(),
              hour: "2-digit",
              minute: "2-digit",
            }),
          ),
        );
        if (date !== previousDate)
          svg.append(
            svgNode(
              "text",
              {
                x: x(t),
                y: height - 20,
                "text-anchor":
                  i === 0 ? "start" : i === ticks ? "end" : "middle",
              },
              date,
            ),
          );
        previousDate = date;
      }
      const drawing = svgNode("g", { "clip-path": `url(#plan-clip-${f.id})` });
      svg.append(drawing);
      // Each interval is its own segment: a missing price never becomes zero or a bridge.
      let pricePath = "",
        previous = null;
      for (const [a, b, value] of view.prices) {
        if (previous && previous[1] === a)
          pricePath += `L ${x(a)} ${py(value)} L ${x(b)} ${py(value)} `;
        else pricePath += `M ${x(a)} ${py(value)} L ${x(b)} ${py(value)} `;
        previous = [a, b, value];
      }
      drawing.append(
        svgNode("path", {
          d: pricePath,
          fill: "none",
          stroke: range?.flat ? "var(--plan-mid)" : `url(#${gradientId})`,
          "stroke-width": 3.5,
          "stroke-linejoin": "round",
        }),
      );
      for (const p of view.profiles) {
        const row = f.rows.get(p.id),
          g = svgNode("g", { class: "plan-motion" });
        const segments = powerSegments(p, 0);
        let d = "";
        for (const seg of segments)
          d += `${d ? "L" : "M"} ${rx(seg.start)} ${wy(seg.watts)} L ${rx(seg.end)} ${wy(seg.watts)} `;
        if (segments.length) d += `L ${rx(p.duration_seconds)} ${wy(0)}`;
        g.append(
          svgNode("path", {
            d,
            fill: "none",
            stroke: row.color,
            "stroke-width": 2,
            "stroke-dasharray": row.dash,
          }),
        );
        drawing.append(g);
        f.groups.set(p.id, g);
      }
      const marker = svgNode("g", { class: "plan-motion" });
      marker.append(
        svgNode("line", {
          x1: left,
          x2: left,
          y1: top,
          y2: top + ph,
          class: "start-line",
        }),
      );
      drawing.append(marker);
      f.marker = marker;
      const tip = el("div", "", "plan-tooltip");
      tip.id = `plan-tooltip-${f.id}`;
      tip.hidden = true;
      tip.setAttribute("role", "tooltip");
      svg.setAttribute("aria-describedby", tip.id);
      const show = (t, clientX = null, clientY = null) => {
        f.inspect = Math.max(domain.start, Math.min(domain.end - 0.001, t));
        const price = view.prices.find(
          ([a, b]) => a <= f.inspect && b > f.inspect,
        );
        const lines = [
          format(f.inspect),
          price
            ? `Elpris: ${number(price[2], 3)} ${view.currency}/kWh`
            : "Pris saknas",
        ];
        for (const p of f.data.profiles)
          if (!f.hidden.has(p.id)) {
            const seg = powerSegments(p, f.data.selected_start).find(
              (p) => p.start <= f.inspect && p.end > f.inspect,
            );
            lines.push(
              `${p.name}: ${p.sample_count ? `${seg ? number(seg.watts, 0) : "0"} W` : "underlag saknas"}`,
            );
          }
        tip.textContent = lines.join("\n");
        tip.hidden = false;
        tip.style.left = `${Math.min(Math.max(0, (clientX ?? width / 2) - left), Math.max(0, width - 245))}px`;
        tip.style.top = `${Math.max(12, Math.min(70, clientY ?? 30))}px`;
      };
      svg.addEventListener("pointermove", (event) => {
        const r = svg.getBoundingClientRect();
        show(
          domain.start + ((event.clientX - r.left - left) / pw) * span,
          event.clientX - r.left,
          event.clientY - r.top,
        );
      });
      svg.addEventListener("pointerleave", () => {
        tip.hidden = true;
      });
      svg.addEventListener("keydown", (event) => {
        if (["ArrowLeft", "ArrowRight", "Home", "End"].includes(event.key)) {
          event.preventDefault();
          const step = event.key === "ArrowLeft" ? -900 : 900;
          show(
            event.key === "Home"
              ? domain.start
              : event.key === "End"
                ? domain.end - 0.001
                : (f.inspect ?? f.data.selected_start) + step,
          );
        } else if (event.key === "Escape") tip.hidden = true;
      });
      svg.addEventListener("blur", () => {
        tip.hidden = true;
      });
      f.svg = svg;
      n.chart.replaceChildren(svg, tip);
      if (focused) svg.focus({ preventScroll: true });
      n.legend.replaceChildren();
      const priceLabel = el("span");
      priceLabel.append(
        el("span", undefined, "plan-swatch plan-price-swatch"),
        el("span", "Elpris"),
      );
      n.legend.append(priceLabel);
      for (const p of view.profiles) {
        const row = f.rows.get(p.id),
          button = el("button", undefined, "curve-toggle");
        const caption = el("span", p.name, "curve-name");
        button.append(caption);
        button.title = p.name;
        button.type = "button";
        button.setAttribute("aria-label", `Visa eller dölj ${p.name} i grafen`);
        const swatch = el("span", undefined, "plan-swatch");
        swatch.style.borderTopColor = row.color;
        swatch.style.borderTopStyle = row.dash ? "dashed" : "solid";
        button.prepend(swatch);
        button.dataset.focusKey = `planning-curve-${entryId}-${p.id}`;
        button.addEventListener("click", () => {
          if (f.hidden.has(p.id)) f.hidden.delete(p.id);
          else f.hidden.add(p.id);
          drawPlot();
          f.rows.get(p.id)?.legend?.focus({ preventScroll: true });
        });
        row.legend = button;
        n.legend.append(button);
      }
      n.scale.replaceChildren();
      if (range) {
        const rangeLabel = el("span");
        rangeLabel.append(
          document.createTextNode(
            range.flat
              ? `Oförändrat pris: ${number(range.min, 3)} ${view.currency}/kWh`
              : `Lägst ${number(range.min, 3)}`,
          ),
        );
        if (!range.flat)
          rangeLabel.append(
            el("span", undefined, "plan-color-bar"),
            document.createTextNode(
              `Högst ${number(range.max, 3)} ${view.currency}/kWh`,
            ),
          );
        n.scale.append(rangeLabel, el("span", "Relativt prognosen"));
      }
    }
    const translate =
      ((view.selected_start - f.geometryInfo.domain.start) /
        f.geometryInfo.span) *
      f.geometryInfo.pw;
    for (const p of view.profiles) {
      const g = f.groups.get(p.id);
      if (g) {
        g.style.transform = `translateX(${translate}px)`;
        g.style.display = f.hidden.has(p.id) ? "none" : "";
      }
      f.rows
        .get(p.id)
        ?.legend?.setAttribute("aria-pressed", String(!f.hidden.has(p.id)));
    }
    f.marker.style.transform = `translateX(${translate}px)`;
  }
  this._planningDisconnect = () => {
    f.queue?.dispose();
    f.queue = null;
    f.observer?.disconnect();
  };
  this._planningConnect = () => {
    f.observer?.observe(n.chart);
    request(true);
  };
  draw();
  request();
}
