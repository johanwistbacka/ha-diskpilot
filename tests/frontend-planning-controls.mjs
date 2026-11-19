import assert from "node:assert/strict";
import test from "node:test";
import { renderPlanning, el, tick, deferred } from "./renderer-harness.mjs";

const epoch = Date.parse("2026-11-19T11:00:00Z") / 1000;
function setup({ admin = true, load } = {}) {
  const calls = [],
    profiles = [
      {
        id: "long",
        name: "Lång",
        sample_count: 2,
        duration_seconds: 7200,
        energy_wh: [10],
        energy_kwh: 0.01,
        cost: 0.5,
        selected_cost: 1,
        optimal_start: epoch + 3600,
        selected_end: epoch + 7200,
      },
      {
        id: "short",
        name: "Kort",
        sample_count: 2,
        duration_seconds: 1200,
        energy_wh: [10],
        energy_kwh: 0.01,
        cost: 0.2,
        selected_cost: 0.3,
        optimal_start: epoch + 3600,
        selected_end: epoch + 1200,
      },
    ];
  const response = {
    entry_id: "e",
    now: epoch,
    selected_start: epoch,
    currency: "SEK",
    price_status: "ok",
    price_basis: "Nord Pool + Eltariff + påslag",
    planning_deadline: epoch + 86400,
    prices: [[epoch, epoch + 3600, 3]],
    profiles,
  };
  const card = {
    _config: {},
    _hass: {
      user: { is_admin: admin },
      config: { time_zone: "Europe/Stockholm" },
      locale: { language: "sv-SE" },
      states: {},
    },
    service: (entry, service, input) => {
      calls.push({ entry, service, input });
      return load
        ? load(response, calls.length, input)
        : Promise.resolve(response);
    },
  };
  const root = el("article");
  const draw = (revision = 1, status = "ok") =>
    renderPlanning.call(
      card,
      root,
      "e",
      profiles,
      { plan_revision: revision, price_status: status },
      el,
      String,
      (value) => {
        if (!value) throw Error("Ange datum och klockslag.");
        return new Date(
          value.endsWith("Z") ? value : value + "Z",
        ).toISOString();
      },
    );
  draw();
  return {
    card,
    calls,
    draw,
    response,
    profiles,
    get state() {
      return card._planState;
    },
  };
}

test("local invalid start has actionable guidance and Nu recovers without a fetch-error retry", async () => {
  const h = setup();
  await tick();
  const n = h.state.nodes;
  n.input.value = "";
  n.input.fire("input");
  n.input.fire("change");
  assert.match(n.message.textContent, /Ange datum och klockslag.*tryck Nu/);
  assert.doesNotMatch(n.message.textContent, /Kunde inte hämta/);
  assert.equal(n.retry.hidden, true);
  assert.equal(h.calls.length, 1);
  assert.equal(n.input.attrs["aria-invalid"], "true");
  assert.equal(h.state.rows.get("long").value.textContent, "—");
  n.now.click();
  await tick();
  assert.deepEqual(h.calls.at(-1).input, {});
  assert.equal(n.input.attrs["aria-invalid"], undefined);
  assert.equal(h.state.rows.get("long").value.textContent, "1,00 kr");
  h.card._planningDisconnect();
});

test("network failure retains retry and price basis appears once", async () => {
  const h = setup({
    load: (data, count) =>
      count === 1
        ? Promise.reject(Error("Anslutningen bröts"))
        : Promise.resolve(data),
  });
  await tick();
  const n = h.state.nodes;
  assert.equal(n.retry.hidden, false);
  n.retry.click();
  await tick();
  assert.equal(n.retry.hidden, true);
  assert.equal(h.calls.length, 2);
  assert.equal(n.basisText.textContent, h.response.price_basis);
  assert.doesNotMatch(h.state.rows.get("long").body.textContent, /Nord Pool/);
  n.basis.open = true;
  h.draw(2);
  await tick();
  assert.equal(n.basis.open, true);
  h.card._planningDisconnect();
});

test("late-start missing prices are per program and never become zero", async () => {
  const h = setup();
  await tick();
  h.profiles[0].selected_cost = null;
  h.profiles[0].meets_finish_by = false;
  h.draw(2);
  await tick();
  const long = h.state.rows.get("long"),
    short = h.state.rows.get("short");
  assert.equal(long.value.textContent, "Pris saknas");
  assert.match(long.coverage.textContent, /slutar efter sista/);
  assert.equal(short.value.textContent, "0,30 kr");
  assert.equal(short.coverage.hidden, true);
  assert.match(long.notes.textContent, /efter din tidsgräns/);
  h.card._planningDisconnect();
});

test("local sorting, graph zoom and stable profile identity survive an automatic price update", async () => {
  const h = setup();
  await tick();
  const n = h.state.nodes;
  n.sort.value = "price";
  n.sort.fire("change");
  assert.deepEqual(h.state.order, ["short", "long"]);
  const short = h.state.rows.get("short");
  short.section.open = true;
  const color = short.color;
  n.zoomRun.click();
  assert.equal(h.state.zoom, "run");
  assert.equal(h.calls.length, 1);
  h.profiles[0].selected_cost = 0.1;
  h.profiles[1].selected_cost = 5;
  h.draw(2);
  await tick();
  assert.deepEqual(h.state.order, ["short", "long"]);
  assert.equal(short.section.open, true);
  assert.equal(short.color, color);
  n.sort.fire("change");
  assert.deepEqual(h.state.order, ["long", "short"]);
  assert.equal(n.zoomRun.attrs["aria-pressed"], "true");
  h.card._planningDisconnect();
});

test("deadline intent survives a delayed response and a start change; disabling removes it", async () => {
  const held = deferred();
  const h = setup({
    load: (data, count, input) =>
      count === 2
        ? held.promise
        : Promise.resolve({
            ...data,
            selected_start: input.started_at
              ? Date.parse(input.started_at) / 1000
              : epoch,
            finish_by: input.finish_by
              ? Date.parse(input.finish_by) / 1000
              : null,
          }),
  });
  await tick();
  const n = h.state.nodes;
  n.deadlineInput.value = "2099-01-01T23:00";
  n.deadlineToggle.checked = true;
  n.deadlineToggle.fire("change");
  assert.equal(h.calls.at(-1).input.finish_by, "2099-01-01T23:00:00.000Z");
  n.later.click();
  held.resolve(h.response);
  await tick();
  assert.equal(h.calls.at(-1).input.finish_by, "2099-01-01T23:00:00.000Z");
  assert.ok(h.calls.at(-1).input.started_at);
  n.deadlineToggle.checked = false;
  n.deadlineToggle.fire("change");
  await tick();
  assert.equal(h.calls.at(-1).input.finish_by, undefined);
  h.card._planningDisconnect();
});

test("invalid deadline cancels pending data and recovers by disabling the condition", async () => {
  const h = setup();
  await tick();
  const n = h.state.nodes;
  n.deadlineInput.value = "";
  n.deadlineToggle.checked = true;
  n.deadlineToggle.fire("change");
  assert.equal(h.calls.length, 1);
  assert.equal(n.deadlineInput.attrs["aria-invalid"], "true");
  assert.equal(h.state.rows.get("long").value.textContent, "—");
  assert.equal(n.chart.hidden, true);
  n.deadlineToggle.checked = false;
  n.deadlineToggle.fire("change");
  await tick();
  assert.equal(h.calls.length, 2);
  assert.equal(h.state.deadlineError, "");
  h.card._planningDisconnect();
});

test("non-admin does not send planning or deadline requests", async () => {
  const h = setup({ admin: false });
  await tick();
  assert.equal(h.calls.length, 0);
  assert.equal(h.state.nodes.dateButton.disabled, true);
  assert.equal(h.state.nodes.conditions.hidden, true);
  assert.equal(h.state.nodes.zoomRun.disabled, true);
  assert.equal(h.state.rows.get("short").bestButton.disabled, true);
  h.card._planningDisconnect();
});
