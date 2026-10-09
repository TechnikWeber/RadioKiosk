"use strict";

const STRINGS = {
  en: {
    webradio: "Web radio", dab: "DAB+", fm: "FM", settings: "Settings",
    favorites: "Favorites", popular: "Popular", search: "Search", go: "Go",
    noFavorites: "No favorites yet. Tap the star next to a station.",
    noResults: "No stations found.", loading: "Loading…",
    scan: "Scan for stations", scanning: "Scanning block", found: "found",
    noServices: "No stations stored yet. Start a scan.",
    noSdr: "No RTL-SDR stick found", notInstalled: "not installed", noMpv: "mpv is not installed",
    running: "Running", quit: "Quit", expert: "Expert receiver",
    output: "Audio output", save: "Save", remove: "Remove",
    tuner: "Receiver", tunerSub: "Shortwave, 2 m, 70 cm …", squelch: "Squelch", off: "off",
    signal: "Signal", gainLabel: "Gain", stereo: "Stereo", muted: "squelched", zoom: "Zoom",
    fmScanning: "Scanning the band…", fmFound: "Found", fmSaved: "Saved",
    enterFrequency: "Up to 1750: MHz · from 2000: kHz", cancel: "Cancel",
    relevel: "Reset remembered gain",
    relevelHint: "The tuner gain adjusts itself and is remembered per band. Reset it after changing the antenna or location.",
    kinds: { analog: "Headphone jack / built-in", usb: "USB", bluetooth: "Bluetooth", hdmi: "HDMI" },
  },
  de: {
    webradio: "Webradio", dab: "DAB+", fm: "UKW", settings: "Einstellungen",
    favorites: "Favoriten", popular: "Beliebt", search: "Suche", go: "Los",
    noFavorites: "Noch keine Favoriten. Tippe auf den Stern neben einem Sender.",
    noResults: "Keine Sender gefunden.", loading: "Lädt…",
    scan: "Sendersuchlauf", scanning: "Suche in Block", found: "gefunden",
    noServices: "Noch keine Sender gespeichert. Starte einen Suchlauf.",
    noSdr: "Kein RTL-SDR-Stick gefunden", notInstalled: "nicht installiert", noMpv: "mpv ist nicht installiert",
    running: "Läuft", quit: "Beenden", expert: "Experten-Empfänger",
    output: "Tonausgabe", save: "Speichern", remove: "Entfernen",
    tuner: "Empfänger", tunerSub: "Kurzwelle, 2 m, 70 cm …", squelch: "Rauschsperre", off: "aus",
    signal: "Signal", gainLabel: "Verstärkung", stereo: "Stereo", muted: "Rauschsperre zu", zoom: "Zoom",
    fmScanning: "Suche Sender im Band…", fmFound: "Gefunden", fmSaved: "Gespeichert",
    enterFrequency: "Bis 1750: MHz · ab 2000: kHz", cancel: "Abbrechen",
    relevel: "Gemerkte Verstärkung zurücksetzen",
    relevelHint: "Die Verstärkung regelt sich selbst und wird je Band gemerkt. Nach Antennen- oder Standortwechsel zurücksetzen.",
    kinds: { analog: "Klinke / eingebaut", usb: "USB", bluetooth: "Bluetooth", hdmi: "HDMI" },
  },
};
const lang = STRINGS[navigator.language.slice(0, 2)] ? navigator.language.slice(0, 2) : "en";
const t = STRINGS[lang];
document.documentElement.lang = lang;
// band plan entries carry their names as plain text or as { de, en }
const tr = name => typeof name === "string" ? name : name[lang] || name.en;

const ICONS = {
  webradio: '<circle cx="12" cy="12" r="9"/><path d="M3 12h18M12 3c3 3 3 15 0 18M12 3c-3 3-3 15 0 18"/>',
  dab: '<rect x="3" y="8" width="18" height="12" rx="2"/><path d="M7 8l9-5M7 14h4M16 14h.01M7 17h4"/>',
  fm: '<path d="M12 12v9M8 16a5.5 5.5 0 010-8M16 8a5.5 5.5 0 010 8M5 19a10 10 0 010-14M19 5a10 10 0 010 14"/>',
  app: '<path d="M3 17l4-9 3 6 3-10 3 8 2-3 3 8"/>',
  tuner: '<circle cx="12" cy="12" r="9"/><circle cx="12" cy="12" r="2"/><path d="M12 3v3M12 10V7M5.6 5.6l2 2M3 12h3M18.4 5.6l-2 2M21 12h-3"/>',
  settings: '<path d="M4 7h10M18 7h2M4 17h2M10 17h10"/><circle cx="16" cy="7" r="2"/><circle cx="8" cy="17" r="2"/>',
  star: '<path d="M12 4l2.5 5.2 5.5.8-4 4 1 5.6-5-2.7-5 2.7 1-5.6-4-4 5.5-.8z"/>',
};
const icon = name => `<svg viewBox="0 0 24 24">${ICONS[name]}</svg>`;

const $ = id => document.getElementById(id);
const view = $("view");
let state = { caps: { apps: [] }, detail: {} };
let current = null;   // the visible view: { title, render(), onState?() }

function h(tag, props = {}, ...children) {
  const el = Object.assign(document.createElement(tag), props);
  el.append(...children.filter(c => c != null));
  return el;
}

async function api(path, body) {
  const response = await fetch(path, body === undefined ? {} : {
    method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(body),
  });
  const data = await response.json();
  if (!response.ok) throw new Error(data.error || response.statusText);
  return data;
}

function show(v) {
  current = v;
  $("heading").textContent = v.title;
  $("back").hidden = v === home;
  view.scrollTop = 0;
  v.render();
}

const hint = text => h("p", { className: "hint", textContent: text });

function stationRow({ title, info, active, onPlay, starred, onStar }) {
  const row = h("div", { className: "row" + (active ? " current" : "") },
    h("button", { onclick: onPlay }, h("b", { textContent: title }), h("small", { textContent: info || "" })));
  if (onStar) {
    row.append(h("button", { className: "icon star" + (starred ? " on" : ""), innerHTML: icon("star"), onclick: onStar }));
  }
  return row;
}

/* ---------- spectrum and waterfall ---------- */

const PALETTE = (() => {
  // dark blue -> cyan -> yellow -> white
  const stops = [[0, 8, 12, 40], [0.35, 20, 90, 170], [0.6, 40, 200, 200], [0.8, 250, 220, 80], [1, 255, 255, 255]];
  const colors = new Uint8ClampedArray(256 * 4);
  for (let i = 0; i < 256; i++) {
    const x = i / 255;
    const k = stops.findIndex(stop => stop[0] >= x) || 1;
    const [a, b] = [stops[k - 1], stops[k]];
    const f = (x - a[0]) / (b[0] - a[0]);
    for (let c = 0; c < 3; c++) colors[i * 4 + c] = a[c + 1] + (b[c + 1] - a[c + 1]) * f;
    colors[i * 4 + 3] = 255;
  }
  return colors;
})();

// One spectrum line from the receiver engine: header, then one byte per point (0..255 = -120..0 dBFS).
function parseSpectrum(buffer) {
  const head = new DataView(buffer);
  const flags = head.getUint8(36);
  return {
    start: head.getFloat64(0, true), span: head.getFloat64(8, true), tuned: head.getFloat64(16, true),
    snr: head.getFloat32(28, true), gain: head.getFloat32(32, true),
    stereo: !!(flags & 1), squelched: !!(flags & 2), line: new Uint8Array(buffer, 37),
  };
}

const meterText = s => [
  `${t.signal} ${Math.max(0, s.snr).toFixed(0)} dB`, `${t.gainLabel} ${s.gain.toFixed(0)} dB`,
  s.stereo ? t.stereo : null, s.squelched ? t.muted : null,
].filter(Boolean).join(" · ");

// Spectrum trace on top, waterfall below. The element keeps its picture while views redraw around it.
function makeWaterfall(onTune) {
  const TRACE = 48, ROWS = 72;
  const canvas = h("canvas", { className: "waterfall", width: 1024, height: TRACE + ROWS });
  const ctx = canvas.getContext("2d", { willReadFrequently: true });
  const row = ctx.createImageData(1024, 1);
  let last = null, floor = 60;
  canvas.onclick = e => {
    if (!last) return;
    const box = canvas.getBoundingClientRect();
    onTune(last.start + (e.clientX - box.left) / box.width * last.span);
  };
  return {
    el: canvas,
    push(s) {
      if (!last || last.start !== s.start || last.span !== s.span) ctx.clearRect(0, 0, 1024, TRACE + ROWS);
      last = s;
      // follow the noise floor so the colours fit weak and strong bands alike
      const sorted = Uint8Array.from(s.line).sort();
      floor += (sorted[300] - floor) * 0.1;
      const scale = v => Math.min(1, Math.max(0, (v - floor + 6) / 110));   // about 50 dB of range
      ctx.drawImage(canvas, 0, TRACE, 1024, ROWS - 1, 0, TRACE + 1, 1024, ROWS - 1);
      for (let x = 0; x < 1024; x++) {
        row.data.set(PALETTE.subarray(Math.round(scale(s.line[x]) * 255) * 4, Math.round(scale(s.line[x]) * 255) * 4 + 4), x * 4);
      }
      ctx.putImageData(row, 0, TRACE);
      ctx.clearRect(0, 0, 1024, TRACE);
      ctx.beginPath();
      for (let x = 0; x < 1024; x++) ctx.lineTo(x, TRACE - 2 - scale(s.line[x]) * (TRACE - 4));
      ctx.strokeStyle = "#93a1b3";
      ctx.lineWidth = 1.5;
      ctx.stroke();
      const marker = (s.tuned - s.start) / s.span * 1024;
      ctx.fillStyle = "#ffb347";
      ctx.fillRect(marker - 1, 0, 2, TRACE);
    },
  };
}

/* ---------- home ---------- */

const home = {
  title: "RadioKiosk",
  render() {
    const c = state.caps;
    const sdrProblem = !c.sdr ? t.noSdr : null;
    const tile = (id, label, problem, onclick, sub) => h("button", {
      className: "tile" + (state.source === id ? " running" : ""), disabled: !!problem, onclick,
      innerHTML: icon(id) + `<span>${label}</span>` + (problem || sub ? `<small>${problem || sub}</small>` : ""),
    });
    view.replaceChildren(h("div", { className: "tiles" },
      tile("webradio", t.webradio, c.mpv ? null : t.noMpv, () => show(webradio)),
      tile("dab", t.dab, c.dab ? sdrProblem : `welle-cli ${t.notInstalled}`, () => show(dab)),
      tile("fm", t.fm, c.fm ? sdrProblem : `librtlsdr ${t.notInstalled}`, () => show(fm)),
      tile("tuner", t.tuner, c.fm ? sdrProblem : `librtlsdr ${t.notInstalled}`, () => show(tuner), t.tunerSub),
      ...c.apps.map(a => {
        const running = state.source === "app" && state.detail.app === a.id;
        const el = tile("app", a.name, a.available ? (a.needs_sdr ? sdrProblem : null) : t.notInstalled,
          () => running ? api("/api/stop", {}) : api(`/api/apps/${a.id}/start`, {}),
          running ? `${t.running} – ${t.quit}` : t.expert);
        el.classList.toggle("running", running);
        return el;
      }),
      tile("settings", t.settings, null, () => show(settings)),
    ));
  },
  onState() { this.render(); },
};

/* ---------- web radio ---------- */

const webradio = {
  title: t.webradio,
  tab: "favorites",
  favorites: [],
  results: [],
  query: "",
  async render() {
    this.favorites = await api("/api/webradio/favorites");
    if (!this.favorites.length && this.tab === "favorites") this.tab = "popular";
    this.draw();
    if (this.tab === "popular") this.load("");
  },
  async load(query) {
    this.results = null;
    this.draw();
    try {
      this.results = await api("/api/webradio/stations?q=" + encodeURIComponent(query));
    } catch (e) {
      this.results = [];
      this.error = e.message;
    }
    if (current === this) this.draw();
  },
  draw() {
    const tabButton = id => h("button", {
      className: this.tab === id ? "on" : "", textContent: t[id],
      onclick: () => { this.tab = id; this.results = []; this.error = null; this.draw(); if (id === "popular") this.load(""); },
    });
    const parts = [h("div", { className: "tabs" }, tabButton("favorites"), tabButton("popular"), tabButton("search"))];
    if (this.tab === "search") {
      const input = h("input", { type: "search", value: this.query, placeholder: t.search, enterKeyHint: "search" });
      const run = () => { this.query = input.value.trim(); if (this.query) this.load(this.query); };
      input.onkeydown = e => { if (e.key === "Enter") run(); };
      parts.push(h("div", { className: "toolbar" }, input, h("button", { className: "primary", textContent: t.go, onclick: run })));
    }
    const list = this.tab === "favorites" ? this.favorites : this.results;
    if (list === null) parts.push(hint(t.loading));
    else if (this.error) parts.push(hint(this.error));
    else if (!list.length && this.tab === "favorites") parts.push(hint(t.noFavorites));
    else if (!list.length && this.tab === "search" && this.query) parts.push(hint(t.noResults));
    else for (const s of list) {
      parts.push(stationRow({
        title: s.name, info: s.info,
        active: state.source === "webradio" && state.detail.id === s.id,
        onPlay: () => api("/api/webradio/play", s),
        starred: this.favorites.some(f => f.id === s.id),
        onStar: async () => { this.favorites = await api("/api/webradio/favorites", s); this.draw(); },
      }));
    }
    const top = view.scrollTop;
    view.replaceChildren(...parts);
    view.scrollTop = top;
  },
  onState() { this.draw(); },
};

/* ---------- DAB+ ---------- */

const dab = {
  title: t.dab,
  services: [],
  async render() {
    this.services = (await api("/api/dab/services")).services;
    this.draw();
  },
  draw() {
    const scan = state.source === "dab" && state.detail.scan;
    const parts = [h("div", { className: "toolbar" },
      h("button", { textContent: t.scan, disabled: !!scan, onclick: () => api("/api/dab/scan", {}) }))];
    if (scan) parts.push(hint(`${t.scanning} ${scan.channel} · ${scan.found} ${t.found}`));
    else if (!this.services.length) parts.push(hint(t.noServices));
    else for (const s of this.services) {
      parts.push(stationRow({
        title: s.name, info: `${s.ensemble} · ${s.channel}`,
        active: state.source === "dab" && state.detail.sid === s.sid,
        onPlay: () => api("/api/dab/play", { sid: s.sid }),
      }));
    }
    const top = view.scrollTop;
    view.replaceChildren(...parts);
    view.scrollTop = top;
  },
  wasScanning: false,
  onState() {
    const scanning = !!(state.source === "dab" && state.detail.scan);
    if (this.wasScanning && !scanning) this.render(); else this.draw();
    this.wasScanning = scanning;
  },
};

/* ---------- FM ---------- */

const fm = {
  title: t.fm,
  mhz: 98.5,
  presets: [],
  stations: [],
  meter: h("p", { className: "label meter" }),
  fall: null,
  onSpectrum(s) {
    this.fall.push(s);
    this.meter.textContent = meterText(s);
  },
  async render() {
    this.fall = this.fall || makeWaterfall(hz => this.tune(Math.round(hz / 1e5) / 10));
    [this.presets, this.stations] = await Promise.all([api("/api/fm/presets"), api("/api/fm/stations")]);
    if (state.source === "fm" && state.detail.mhz) this.mhz = state.detail.mhz;
    this.draw();
  },
  tune(mhz) {
    this.mhz = Math.round(Math.min(108, Math.max(87.5, mhz)) * 100) / 100;
    this.draw();
    // several quick taps should retune the stick once, not once per tap
    clearTimeout(this.timer);
    this.timer = setTimeout(() => api("/api/fm/tune", { mhz: this.mhz }), 400);
  },
  draw() {
    const scanning = state.source === "fm" && state.detail.scan;
    const step = (label, delta) => h("button", { textContent: label, onclick: () => this.tune(this.mhz + delta) });
    const chips = (label, list) => list.length ? [
      h("p", { className: "label", textContent: label }),
      h("div", { className: "chips" }, ...list.map(mhz => h("button", {
        className: mhz === this.mhz ? "on" : "", textContent: mhz.toFixed(1), onclick: () => this.tune(mhz),
      }))),
    ] : [];
    const saved = this.presets.includes(this.mhz);
    view.replaceChildren(
      h("div", { className: "dial", innerHTML: `${this.mhz.toFixed(2)} <small>MHz</small>` }),
      this.meter,
      this.fall.el,
      h("div", { className: "steps" }, step("− 1", -1), step("− 0.1", -0.1), step("+ 0.1", 0.1), step("+ 1", 1)),
      h("div", { className: "toolbar" },
        h("button", { className: "primary", textContent: "▶", onclick: () => this.tune(this.mhz) }),
        h("button", {
          textContent: saved ? t.remove : t.save,
          onclick: async () => { this.presets = await api("/api/fm/presets", { mhz: this.mhz }); this.draw(); },
        }),
        h("button", { textContent: t.scan, disabled: !!scanning, onclick: () => api("/api/fm/scan", {}) }),
      ),
      ...(scanning ? [hint(t.fmScanning)] : []),
      ...chips(t.fmSaved, this.presets),
      ...chips(t.fmFound, this.stations.map(s => s.mhz)),
    );
  },
  wasScanning: false,
  onState() {
    const scanning = !!(state.source === "fm" && state.detail.scan);
    if (this.wasScanning && !scanning) this.render(); else if (scanning !== this.wasScanning) this.draw();
    this.wasScanning = scanning;
  },
};

/* ---------- receiver (free tuning) ---------- */

const MODE_NAMES = { nfm: "FM", wfm: "WFM", am: "AM", usb: "USB", lsb: "LSB" };
const SQUELCH_LEVELS = [0, 3, 6, 10, 15];   // dB above the noise floor
const ZOOMS = [1, 4, 16, 64];
const formatHz = hz => hz < 30e6
  ? `${(hz / 1e3).toFixed(1)} <small>kHz</small>` : `${(hz / 1e6).toFixed(4)} <small>MHz</small>`;

const tuner = {
  title: t.tuner,
  bands: [],
  favorites: [],
  band: null,      // null shows the band list
  entry: null,     // digits typed on the number pad, null when it is closed
  hz: 145500000, mode: "nfm", squelch: 0, zoom: 1, label: "",
  meter: h("p", { className: "label meter" }),
  fall: null,
  onSpectrum(s) {
    this.fall.push(s);
    this.meter.textContent = meterText(s);
  },
  async render() {
    this.fall = this.fall || makeWaterfall(hz => {
      const step = this.band ? this.band.step : 1000;
      this.tune(Math.round(hz / step) * step);
    });
    [this.bands, this.favorites] = await Promise.all([api("/api/tuner/bands"), api("/api/tuner/favorites")]);
    this.draw();
  },
  back() {
    if (this.entry !== null) this.entry = null;
    else if (this.band) this.band = null;
    else return false;
    this.draw();
    return true;
  },
  open(band, preset) {
    this.band = band;
    this.squelch = band.squelch || 0;
    this.select(preset || band.presets[0]);
  },
  select(preset) {
    this.tune(preset.hz, preset.mode || this.band.mode, preset.name ? tr(preset.name) : "");
  },
  tune(hz, mode = this.mode, label = "") {
    Object.assign(this, { hz: Math.round(Math.min(1.75e9, Math.max(1e5, hz))), mode, label });
    this.draw();
    clearTimeout(this.timer);
    this.timer = setTimeout(() => api("/api/tuner/tune",
      { hz: this.hz, mode: this.mode, squelch: this.mode === "nfm" ? this.squelch : 0, zoom: this.zoom, label: this.label }), 400);
  },
  draw() {
    $("heading").textContent = this.band ? tr(this.band.name) : this.title;
    if (this.entry !== null) return this.drawPad();
    if (!this.band) return this.drawBands();
    const isFavorite = this.favorites.some(f => f.hz === this.hz && f.mode === this.mode);
    const step = (label, factor) => h("button", { textContent: label, onclick: () => this.tune(this.hz + factor * this.band.step) });
    const top = view.scrollTop;
    view.replaceChildren(
      h("div", { className: "dial", innerHTML: formatHz(this.hz), onclick: () => { this.entry = ""; this.draw(); } }),
      this.meter,
      this.fall.el,
      h("div", { className: "steps five" }, ...Object.keys(MODE_NAMES).map(m => h("button", {
        className: m === this.mode ? "on" : "", textContent: MODE_NAMES[m], onclick: () => this.tune(this.hz, m, this.label),
      }))),
      h("div", { className: "steps" }, step("◀◀", -10), step("◀", -1), step("▶", 1), step("▶▶", 10)),
      h("div", { className: "toolbar" },
        h("button", {
          className: "star" + (isFavorite ? " on" : ""), innerHTML: icon("star"),
          onclick: async () => {
            this.favorites = await api("/api/tuner/favorites", { hz: this.hz, mode: this.mode, name: this.label });
            this.draw();
          },
        }),
        this.mode === "nfm" ? h("button", {
          textContent: `${t.squelch}: ${this.squelch ? this.squelch + " dB" : t.off}`,
          onclick: () => {
            this.squelch = SQUELCH_LEVELS[(SQUELCH_LEVELS.indexOf(this.squelch) + 1) % SQUELCH_LEVELS.length];
            this.tune(this.hz, this.mode, this.label);
          },
        }) : null,
        h("button", {
          textContent: `${t.zoom} ×${this.zoom}`,
          onclick: () => {
            this.zoom = ZOOMS[(ZOOMS.indexOf(this.zoom) + 1) % ZOOMS.length];
            this.tune(this.hz, this.mode, this.label);
          },
        }),
      ),
      ...this.band.presets.map(p => stationRow({
        title: tr(p.name), info: `${formatHz(p.hz).replace(/<\/?small>/g, "")} · ${MODE_NAMES[p.mode || this.band.mode]}`,
        active: p.hz === this.hz, onPlay: () => this.select(p),
      })),
    );
    view.scrollTop = top;
  },
  drawBands() {
    const custom = { id: "custom", name: t.favorites, mode: "nfm", step: 12500, presets: this.favorites };
    view.replaceChildren(
      ...(this.favorites.length ? [stationRow({
        title: t.favorites, info: this.favorites.map(f => f.name || formatHz(f.hz).replace(/<\/?small>/g, "")).join(" · "),
        onPlay: () => this.open(custom),
      })] : []),
      ...this.bands.map(b => stationRow({
        title: tr(b.name), info: b.presets.slice(0, 4).map(p => tr(p.name)).join(" · "), onPlay: () => this.open(b),
      })),
    );
  },
  drawPad() {
    const key = (label, action) => h("button", { textContent: label, onclick: () => { action(); this.draw(); } });
    const digit = d => key(d, () => { if (this.entry.length < 9) this.entry += d; });
    const value = parseFloat(this.entry);
    view.replaceChildren(
      h("div", { className: "dial", textContent: this.entry || "–" }),
      h("p", { className: "label", textContent: t.enterFrequency }),
      h("div", { className: "pad" },
        ..."123456789".split("").map(digit),
        key(".", () => { if (!this.entry.includes(".")) this.entry += "."; }),
        digit("0"),
        key("⌫", () => { this.entry = this.entry.slice(0, -1); }),
        key(t.cancel, () => { this.entry = null; }),
        h("button", {
          className: "primary wide", textContent: "OK", disabled: !(value > 0),
          onclick: () => { this.entry = null; this.tune((value >= 2000 ? 1e3 : 1e6) * value); },
        }),
      ),
    );
  },
};

/* ---------- settings ---------- */

const settings = {
  title: t.settings,
  async render() {
    const sinks = await api("/api/audio");
    view.replaceChildren(
      h("p", { className: "hint", textContent: t.output }),
      ...sinks.map(s => stationRow({
        title: s.label, info: t.kinds[s.kind], active: s.active,
        onPlay: async () => { await api("/api/audio", { name: s.name }); this.render(); },
      })),
      h("p", { className: "hint", textContent: t.relevelHint }),
      h("div", { className: "toolbar" },
        h("button", { textContent: t.relevel, onclick: e => { e.target.disabled = true; api("/api/gain/reset", {}); } })),
    );
  },
};

/* ---------- shared chrome ---------- */

function applyState(next) {
  state = next;
  const failed = state.status === "error";
  $("now").classList.toggle("error", failed);
  $("now-title").textContent = state.title || "";
  $("now-text").textContent = failed ? state.error : state.status === "loading" ? t.loading : state.text || "";
  $("vol").textContent = state.volume ?? "";
  $("stop").disabled = !state.source;
  if (current && current.onState) current.onState();
}

// deep links such as #fm or #tuner/2m open a view directly
async function openLink() {
  const [name, band] = location.hash.slice(1).split("/");
  const target = { webradio, dab, fm, tuner, settings }[name] || home;
  show(target);
  if (target === tuner && band) {
    const bands = await api("/api/tuner/bands");
    const match = bands.find(b => b.id === band);
    if (match) tuner.open(match);
  }
}

function connect() {
  const ws = new WebSocket(`ws://${location.host}/ws`);
  ws.binaryType = "arraybuffer";
  ws.onmessage = e => {
    if (typeof e.data !== "string") {
      if (current && current.onSpectrum) current.onSpectrum(parseSpectrum(e.data));
      return;
    }
    const first = current === null;
    applyState(JSON.parse(e.data));
    if (first) openLink();
  };
  ws.onclose = () => setTimeout(connect, 1500);
}

$("back").onclick = () => { if (!(current.back && current.back())) show(home); };
$("stop").onclick = () => api("/api/stop", {});
$("vol-down").onclick = () => api("/api/volume", { value: (state.volume ?? 50) - 5 });
$("vol-up").onclick = () => api("/api/volume", { value: (state.volume ?? 50) + 5 });

const tick = () => { $("clock").textContent = new Date().toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" }); };
tick();
setInterval(tick, 10000);
connect();
