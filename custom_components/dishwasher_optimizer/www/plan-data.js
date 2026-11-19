/* Pure planning helpers; no network, DOM or persistent state. */
export function localInput(seconds, zone) {
  const parts = new Intl.DateTimeFormat("sv-SE", {
    timeZone: zone,
    year: "numeric",
    month: "2-digit",
    day: "2-digit",
    hour: "2-digit",
    minute: "2-digit",
    hourCycle: "h23",
  }).formatToParts(new Date(seconds * 1000));
  const p = Object.fromEntries(parts.map((v) => [v.type, v.value]));
  return `${p.year}-${p.month}-${p.day}T${p.hour}:${p.minute}`;
}

export function repeatedTimeOffset(seconds, zone, localTime) {
  const instant = Math.floor(seconds / 60) * 60;
  const localAsUTC = Date.parse(localTime + "Z") / 1000;
  const offset = localAsUTC - instant;
  // Compare the neighboring offsets to also handle transitions shorter than an hour.
  for (const delta of [-86400, 86400]) {
    const neighbor = instant + delta;
    const otherOffset =
      Date.parse(localInput(neighbor, zone) + "Z") / 1000 - neighbor;
    if (
      otherOffset === offset ||
      localInput(localAsUTC - otherOffset, zone) !== localTime
    )
      continue;
    const minutes = Math.abs(offset) / 60;
    const hours = String(Math.floor(minutes / 60)).padStart(2, "0");
    const remainder = String(minutes % 60).padStart(2, "0");
    return `UTC${offset < 0 ? "−" : "+"}${hours}:${remainder}`;
  }
  return "";
}
export function priceRange(prices) {
  let min = Infinity,
    max = -Infinity;
  for (const row of prices) {
    if (Number.isFinite(row[2])) {
      min = Math.min(min, row[2]);
      max = Math.max(max, row[2]);
    }
  }
  return min === Infinity ? null : { min, max, flat: min === max };
}
export function priceFraction(value, range) {
  return !range || range.flat
    ? 0.5
    : Math.max(0, Math.min(1, (value - range.min) / (range.max - range.min)));
}
export function powerSegments(profile, start) {
  if (
    !Number.isFinite(profile.duration_seconds) ||
    profile.duration_seconds <= 0
  )
    return [];
  return (profile.energy_wh || [])
    .map((wh, i) => {
      const a = i * 60,
        b = Math.min((i + 1) * 60, profile.duration_seconds);
      return { start: start + a, end: start + b, watts: (wh * 3600) / (b - a) };
    })
    .filter((p) => p.end > p.start && Number.isFinite(p.watts) && p.watts >= 0);
}
export function relativeTime(seconds, now, zone) {
  const local = localInput(seconds, zone);
  const today = localInput(now, zone).slice(0, 10);
  const tomorrow = new Date(Date.parse(today + "T12:00:00Z") + 86400000)
    .toISOString()
    .slice(0, 10);
  const date = local.slice(0, 10);
  const label =
    date === today
      ? "I dag"
      : date === tomorrow
        ? "I morgon"
        : new Date(seconds * 1000).toLocaleDateString("sv-SE", {
            timeZone: zone,
            day: "numeric",
            month: "short",
          });
  return `${label} ${local.slice(11).replace(":", ".")}`;
}

export function coverageMessage(profile, view) {
  if (!profile.sample_count) return "Behöver en komplett märkt körning.";
  if (!view || view.price_status !== "ok" || profile.selected_cost !== null)
    return "";
  const last = Math.max(-Infinity, ...view.prices.map((row) => row[1]));
  if (profile.selected_end > last)
    return "Programmet slutar efter sista kända elpriset.";
  return "Elpriser saknas under hela eller delar av körningen.";
}

export function chartDomain(view, mode = "all", hidden = new Set()) {
  if (mode === "run") {
    let duration = 0;
    for (const p of view.profiles)
      if (!hidden.has(p.id) && Number.isFinite(p.duration_seconds))
        duration = Math.max(duration, p.duration_seconds);
    return {
      start: view.selected_start,
      end: view.selected_start + (duration || 3600),
    };
  }
  const start = Math.floor(Math.min(view.now, view.selected_start) / 60) * 60;
  let end = start + 3600;
  for (const p of view.prices) end = Math.max(end, p[1]);
  for (const p of view.profiles) end = Math.max(end, p.selected_end || start);
  return { start, end };
}
export class LatestPlanRequests {
  constructor(load, receive, fail) {
    this.load = load;
    this.receive = receive;
    this.fail = fail;
    this.epoch = 0;
    this.pending = null;
    this.active = false;
    this.closed = false;
    this.key = null;
  }
  request(key, input) {
    if (this.closed || key === this.key) return;
    this.key = key;
    this.pending = { epoch: ++this.epoch, input };
    this.pump();
  }
  invalidate() {
    this.epoch++;
    this.pending = null;
    this.key = null;
  }
  dispose() {
    this.closed = true;
    this.invalidate();
  }
  async pump() {
    if (this.active || this.closed) return;
    this.active = true;
    try {
      while (this.pending && !this.closed) {
        const item = this.pending;
        this.pending = null;
        try {
          const data = await this.load(item.input);
          if (!this.closed && item.epoch === this.epoch) this.receive(data);
        } catch (error) {
          if (!this.closed && item.epoch === this.epoch) this.fail(error);
        }
      }
    } finally {
      this.active = false;
    }
  }
}
