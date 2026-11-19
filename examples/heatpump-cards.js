// Heat pump dashboard cards (Vaillant aroTHERM via ebusd)
// heatpump-curve-card   : weather-compensation curve with live operating point
// heatpump-daily-card   : daily COP bars (mode: bars) or N-day totals (mode: summary)
//                         computed from HA long-term hourly statistics.

const HP_num = (hass, id) => {
  if (!id || !hass.states[id]) return null;
  const v = parseFloat(hass.states[id].state);
  return isNaN(v) ? null : v;
};
const HP_fmt = (v, d = 1) => (v == null || isNaN(v) ? "—" : Number(v).toFixed(d));

const HP_STYLE = `
  .wrap{padding:0 16px 16px}
  .sub{color:var(--secondary-text-color);font-size:13px;line-height:1.4;margin:0 0 8px}
  svg{width:100%;height:auto;display:block;overflow:visible}
  .ax{stroke:var(--divider-color);stroke-width:1}
  .lbl{fill:var(--secondary-text-color);font-size:10px;font-family:var(--ha-font-family-body,Roboto,sans-serif)}
  .val{fill:var(--primary-text-color);font-size:11px;font-weight:600;font-family:var(--ha-font-family-body,Roboto,sans-serif)}
  .leg{display:flex;gap:14px;flex-wrap:wrap;font-size:12px;color:var(--secondary-text-color);margin-top:6px}
  .leg span::before{content:"";display:inline-block;width:14px;height:3px;margin-right:5px;vertical-align:middle;background:var(--c)}
  .rows{display:grid;gap:10px;padding:4px 0}
  .row{display:flex;align-items:center;gap:14px;font-size:14px}
  .row ha-icon{color:var(--state-icon-color,#44739e);--mdc-icon-size:22px}
  .row .n{flex:1;color:var(--primary-text-color)}
  .row .v{color:var(--primary-text-color);font-variant-numeric:tabular-nums}
  details{margin-top:8px;font-size:12px;color:var(--secondary-text-color)}
  table{border-collapse:collapse;width:100%;margin-top:6px;font-variant-numeric:tabular-nums}
  td,th{padding:2px 4px;text-align:right}
  td:first-child,th:first-child{text-align:left}
`;

/* ---------------- Weather compensation curve ---------------- */
class HeatpumpCurveCard extends HTMLElement {
  setConfig(c) {
    this._c = Object.assign(
      {
        title: "Weather compensation",
        // Fitted from VRC 720 data: flow = room + k*HC*(room-out)^p
        k: 3.33,
        p: 0.73,
        x_min: -15,
        x_max: 20,
      },
      c
    );
  }
  getCardSize() { return 6; }
  getGridOptions() { return { columns: 12, rows: "auto", min_rows: 5 }; }

  _flow(room, hc, out, lo, hi) {
    const d = room - out;
    let f = d <= 0 ? room : room + this._c.k * hc * Math.pow(d, this._c.p);
    if (lo != null) f = Math.max(f, lo);
    if (hi != null) f = Math.min(f, hi);
    return f;
  }

  set hass(hass) {
    const c = this._c;
    const v = (k) => HP_num(hass, c[k]);
    const s = {
      out: v("outdoor"), flow: v("flow"), des: v("desired"),
      room: v("room_set"), night: v("night_set"), hc: v("curve"),
      lo: v("min_flow"), hi: v("max_flow"),
    };
    const key = JSON.stringify(s);
    if (key === this._key) return;
    this._key = key;
    if (!this._card) {
      this._card = document.createElement("ha-card");
      this._card.header = c.title;
      this.attachShadow({ mode: "open" }).appendChild(this._card);
      const st = document.createElement("style");
      st.textContent = HP_STYLE;
      this.shadowRoot.appendChild(st);
      this._body = document.createElement("div");
      this._body.className = "wrap";
      this._card.appendChild(this._body);
    }
    if (s.room == null || s.hc == null) {
      this._body.innerHTML = `<p class="sub">Waiting for room set-point / heat curve…</p>`;
      return;
    }

    const W = 420, H = 230, L = 34, R = 10, T = 10, B = 28;
    const yMax = Math.max(50, Math.ceil(((s.hi ?? 45) + 5) / 10) * 10);
    const yMin = 10;
    const X = (x) => L + ((x - c.x_min) / (c.x_max - c.x_min)) * (W - L - R);
    const Y = (y) => T + (1 - (y - yMin) / (yMax - yMin)) * (H - T - B);

    const path = (room) => {
      let d = "";
      for (let x = c.x_min; x <= c.x_max + 0.001; x += 0.5) {
        const y = this._flow(room, s.hc, x, s.lo, s.hi);
        d += (d ? "L" : "M") + X(x).toFixed(1) + "," + Y(y).toFixed(1);
      }
      return d;
    };

    let grid = "";
    for (let x = c.x_min; x <= c.x_max; x += 5) {
      grid += `<line class="ax" x1="${X(x)}" x2="${X(x)}" y1="${T}" y2="${H - B}" stroke-opacity=".35"/>
               <text class="lbl" x="${X(x)}" y="${H - B + 14}" text-anchor="middle">${x}</text>`;
    }
    for (let y = yMin; y <= yMax; y += 10) {
      grid += `<line class="ax" x1="${L}" x2="${W - R}" y1="${Y(y)}" y2="${Y(y)}" stroke-opacity=".35"/>
               <text class="lbl" x="${L - 6}" y="${Y(y) + 3}" text-anchor="end">${y}</text>`;
    }

    const comfortC = "#ff9800", nightC = "#03a9f4", flowC = "var(--primary-text-color)";
    let marks = "";
    if (s.out != null) {
      const ox = X(Math.min(Math.max(s.out, c.x_min), c.x_max));
      marks += `<line x1="${ox}" x2="${ox}" y1="${T}" y2="${H - B}" stroke="var(--secondary-text-color)" stroke-dasharray="3 3"/>`;
      if (s.des != null && s.des > 0)
        marks += `<circle cx="${ox}" cy="${Y(s.des)}" r="5" fill="none" stroke="${comfortC}" stroke-width="2"/>`;
      if (s.flow != null)
        marks += `<circle cx="${ox}" cy="${Y(s.flow)}" r="4.5" fill="${flowC}"/>`;
    }
    const night = s.night != null && s.night !== s.room
      ? `<path d="${path(s.night)}" fill="none" stroke="${nightC}" stroke-width="2" stroke-dasharray="5 4"/>` : "";

    const theo = s.out != null ? this._flow(s.room, s.hc, s.out, s.lo, s.hi) : null;
    this._body.innerHTML = `
      <p class="sub">Curve ${HP_fmt(s.hc, 2)} · room set ${HP_fmt(s.room, 1)}°C · outdoor ${HP_fmt(s.out, 1)}°C<br>
      Controller target ${HP_fmt(s.des, 1)}°C (curve ${HP_fmt(theo, 1)}°C) · actual flow ${HP_fmt(s.flow, 1)}°C</p>
      <svg viewBox="0 0 ${W} ${H}">
        ${grid}
        <text class="lbl" x="${(L + W - R) / 2}" y="${H - 2}" text-anchor="middle">Outdoor temperature (°C)</text>
        <text class="lbl" x="4" y="${T + 2}" transform="rotate(-90 4 ${T + 2})" text-anchor="end">Flow (°C)</text>
        ${night}
        <path d="${path(s.room)}" fill="none" stroke="${comfortC}" stroke-width="2.5"/>
        ${marks}
      </svg>
      <div class="leg">
        <span style="--c:${comfortC}">Comfort ${HP_fmt(s.room, 0)}°C</span>
        ${night ? `<span style="--c:${nightC}">Setback ${HP_fmt(s.night, 0)}°C</span>` : ""}
        <span style="--c:${comfortC};opacity:.8">○ controller target</span>
        <span style="--c:var(--primary-text-color)">● actual flow</span>
      </div>
      <p class="sub" style="margin-top:8px">Curve shape fitted to your VRC 720's own target flow history (min ${HP_fmt(s.lo, 0)}°C, max ${HP_fmt(s.hi, 0)}°C clamps applied).</p>`;
  }
}
customElements.define("heatpump-curve-card", HeatpumpCurveCard);

/* ---------------- Daily COP / period totals from statistics ---------------- */
class HeatpumpDailyCard extends HTMLElement {
  setConfig(c) {
    this._c = Object.assign(
      { mode: "bars", days: 7, heat: "sensor.arotherm_plus_heat_output", electric: "sensor.arotherm_plus_electrical_input", heat_scale: 1, electric_scale: 1, refresh_minutes: 15 },
      c
    );
    if (!this._c.title) this._c.title = this._c.mode === "summary" ? `Last ${this._c.days} days` : "Daily estimated COP";
  }
  getCardSize() { return this._c.mode === "summary" ? 3 : 5; }
  getGridOptions() { return { columns: 12, rows: "auto", min_rows: 3 }; }

  set hass(hass) {
    this._hass = hass;
    if (!this._card) {
      this._card = document.createElement("ha-card");
      this._card.header = this._c.title;
      this.attachShadow({ mode: "open" }).appendChild(this._card);
      const st = document.createElement("style");
      st.textContent = HP_STYLE;
      this.shadowRoot.appendChild(st);
      this._body = document.createElement("div");
      this._body.className = "wrap";
      this._body.innerHTML = `<p class="sub">Loading statistics…</p>`;
      this._card.appendChild(this._body);
    }
    const now = Date.now();
    if (!this._busy && (!this._t || now - this._t > this._c.refresh_minutes * 60000)) {
      this._t = now;
      this._fetch().catch((e) => { this._body.innerHTML = `<p class="sub">Statistics error: ${e && e.message ? e.message : e}</p>`; })
        .finally(() => { this._busy = false; });
      this._busy = true;
    }
  }

  async _fetch() {
    const c = this._c, hass = this._hass;
    const tz = hass.config.time_zone;
    const dayKey = new Intl.DateTimeFormat("en-CA", { timeZone: tz, year: "numeric", month: "2-digit", day: "2-digit" });
    const hourFmt = new Intl.DateTimeFormat("en-GB", { timeZone: tz, hour: "2-digit", hourCycle: "h23" });
    const toMs = (s) => (typeof s === "number" ? s : Date.parse(s));
    const start = new Date(Date.now() - (c.days + 1) * 86400000);
    start.setMinutes(0, 0, 0);
    const r = await hass.callWS({
      type: "recorder/statistics_during_period",
      start_time: start.toISOString(),
      statistic_ids: [c.heat, c.electric],
      period: "hour",
      types: ["mean"],
    });
    const hm = new Map();
    for (const x of r[c.heat] || []) if (x.mean != null) hm.set(toMs(x.start), x.mean);
    const days = {};
    for (const x of r[c.electric] || []) {
      const t = toMs(x.start);
      if (x.mean == null || !hm.has(t)) continue;
      const k = dayKey.format(new Date(t));
      const d = days[k] || (days[k] = { h: 0, e: 0, n: 0 });
      d.h += Math.max(0, hm.get(t) * c.heat_scale) / 1000; // scale converts the sensor to W (1000 for a kW sensor)
      d.e += Math.max(0, (c.electric_invert ? -1 : 1) * x.mean * c.electric_scale) / 1000;
      d.n++;
    }
    const today = dayKey.format(new Date());
    const elapsed = Math.max(1, parseInt(hourFmt.format(new Date()), 10));
    const list = [];
    for (let i = c.days - 1; i >= 0; i--) {
      const k = dayKey.format(new Date(Date.now() - i * 86400000));
      const d = days[k];
      const isToday = k === today;
      const cov = d ? Math.min(1, d.n / (isToday ? elapsed : 24)) : 0;
      list.push({ k, isToday, h: d ? d.h : null, e: d ? d.e : null, cop: d && d.e > 0.05 ? d.h / d.e : null, cov, n: d ? d.n : 0 });
    }
    this._render(list);
  }

  _render(list) {
    const c = this._c;
    const src = `${c.heat} ÷ ${c.electric}`;
    if (c.mode === "summary") {
      let h = 0, e = 0, n = 0;
      for (const d of list) if (d.h != null) { h += d.h; e += d.e; n += d.n; }
      const cop = e > 0.05 ? h / e : null;
      const cov = n / (list.length * 24);
      const row = (icon, name, val) => `<div class="row"><ha-icon icon="${icon}"></ha-icon><span class="n">${name}</span><span class="v">${val}</span></div>`;
      this._body.innerHTML = `<div class="rows">
        ${row("mdi:radiator", "Estimated heat produced", `${HP_fmt(h, 1)} kWh`)}
        ${row("mdi:flash", "Electricity consumed", `${HP_fmt(e, 1)} kWh`)}
        ${row("mdi:gauge", `Estimated ${list.length}-day COP`, HP_fmt(cop, 2))}
        ${row("mdi:database-clock", "Data coverage", `${Math.round(cov * 100)}%`)}
      </div>`;
      return;
    }

    const W = 420, H = 200, L = 26, R = 6, T = 22, B = 34;
    const maxCop = Math.max(6, ...list.map((d) => (d.cop == null ? 0 : Math.ceil(d.cop))));
    const Y = (v) => T + (1 - v / maxCop) * (H - T - B);
    const slot = (W - L - R) / list.length;
    const bw = Math.min(46, slot * 0.72);
    let g = "";
    for (let v = 0; v <= maxCop; v += maxCop > 8 ? 2 : 1) {
      if (v % (maxCop > 8 ? 4 : 2) && v !== maxCop) continue;
      g += `<line class="ax" x1="${L}" x2="${W - R}" y1="${Y(v)}" y2="${Y(v)}" stroke-opacity=".35"/>
            <text class="lbl" x="${L - 5}" y="${Y(v) + 3}" text-anchor="end">${v}</text>`;
    }
    let bars = "";
    list.forEach((d, i) => {
      const cx = L + slot * (i + 0.5);
      const lab = d.k.slice(5);
      const sub = d.isToday ? "today" : d.n === 0 ? "no data" : d.cov < 0.95 ? `${Math.round(d.cov * 100)}%` : "";
      if (d.cop != null) {
        const partial = d.isToday || d.cov < 0.95;
        bars += `<rect x="${cx - bw / 2}" y="${Y(d.cop)}" width="${bw}" height="${Y(0) - Y(d.cop)}" rx="2"
                  fill="${partial ? "url(#hpstripe)" : "var(--accent-color,#03a9f4)"}" stroke="var(--accent-color,#03a9f4)" stroke-width="${partial ? 1 : 0}"/>
                 <text class="val" x="${cx}" y="${Y(d.cop) - 5}" text-anchor="middle">${HP_fmt(d.cop, 2)}</text>`;
      }
      bars += `<text class="lbl" x="${cx}" y="${H - B + 14}" text-anchor="middle">${lab}</text>
               <text class="lbl" x="${cx}" y="${H - B + 26}" text-anchor="middle">${sub}</text>`;
    });
    const rows = list.map((d) => `<tr><td>${d.k}</td><td>${HP_fmt(d.h, 2)}</td><td>${HP_fmt(d.e, 2)}</td><td>${HP_fmt(d.cop, 2)}</td><td>${d.n}h</td></tr>`).join("");
    this._body.innerHTML = `
      <p class="sub">Each bar = heat kWh ÷ electrical kWh for that local day. Striped bars are partial (today, or hours missing); missing days are not counted as zero.</p>
      <svg viewBox="0 0 ${W} ${H}">
        <defs><pattern id="hpstripe" width="6" height="6" patternUnits="userSpaceOnUse" patternTransform="rotate(45)">
          <rect width="6" height="6" fill="var(--accent-color,#03a9f4)" fill-opacity=".25"/>
          <line x1="0" y1="0" x2="0" y2="6" stroke="var(--accent-color,#03a9f4)" stroke-width="2.5"/></pattern></defs>
        ${g}${bars}
      </svg>
      <details><summary>Daily energy and coverage</summary>
        <table><tr><th>Day</th><th>Heat kWh</th><th>Elec kWh</th><th>COP</th><th>Hours</th></tr>${rows}</table>
        <p>Source: hourly statistics of ${src}. Timezone: ${this._hass.config.time_zone}.</p>
      </details>`;
  }
}
customElements.define("heatpump-daily-card", HeatpumpDailyCard);

window.customCards = window.customCards || [];
window.customCards.push(
  { type: "heatpump-curve-card", name: "Heat pump weather-compensation curve", description: "Heating curve with live operating point" },
  { type: "heatpump-daily-card", name: "Heat pump daily COP", description: "Daily COP bars or period totals from statistics" }
);
