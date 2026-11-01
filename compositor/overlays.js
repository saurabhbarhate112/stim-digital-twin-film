// Motion-graphics layer. Each shot's function draws one frame purely from its frame
// number, so any frame can be rendered alone. Chart values follow the source article's
// figures and are labelled illustrative on screen.
const W = 1280, H = 720;
const cv = document.getElementById('c');
const c = cv.getContext('2d');
const C = { ink: '#0E2219', forest: '#0D2920', green: '#087844', mint: '#2CCB7F', twin: '#3DF2A0', amber: '#F5A524',
  red: '#E5484D', white: '#FFFFFF', paper: '#F3F6F2', muted: '#5B6B63', steel: '#9FB0A8' };
const SANS = "'DM Sans', sans-serif", MONO = "'Plex', monospace";
const clamp = (v, a = 0, b = 1) => Math.min(b, Math.max(a, v));
const outC = t => 1 - Math.pow(1 - clamp(t), 3);
const inOut = t => { t = clamp(t); return t * t * (3 - 2 * t); };
const back = t => { t = clamp(t); const k = 1.7; return 1 + (k + 1) * Math.pow(t - 1, 3) + k * Math.pow(t - 1, 2); };
const mix = (a, b, t) => a + (b - a) * t;

let g = null;              // Per-frame state: shot, f, N, cue(), anchor().
const ASSETS = { img: {} };

function load(src) {
  if (ASSETS.img[src]) return ASSETS.img[src];
  return ASSETS.img[src] = new Promise((res, rej) => {
    const i = new Image(); i.onload = () => res(i); i.onerror = () => rej(new Error('missing ' + src)); i.src = src;
  });
}

const prog = (start, dur = 10) => clamp((g.f - start) / dur);
const pin = (start, dur = 12) => outC(prog(start, dur));

function text(str, x, y, o = {}) {
  const { size = 28, weight = 600, color = C.white, align = 'left', font = SANS, alpha = 1, track = 0 } = o;
  c.save();
  c.globalAlpha *= alpha;
  c.font = `${weight} ${size}px ${font}`;
  c.textAlign = align;
  c.textBaseline = 'alphabetic';
  c.fillStyle = color;
  if ('letterSpacing' in c) c.letterSpacing = track + 'px';
  if (o.shadow) { c.shadowColor = 'rgba(0,0,0,.55)'; c.shadowBlur = o.shadow; c.shadowOffsetY = 2; }
  c.fillText(str, x, y);
  c.restore();
}
const measure = (str, size, weight = 600, font = SANS) => { c.font = `${weight} ${size}px ${font}`; return c.measureText(str).width; };

function rrect(x, y, w, h, r) { c.beginPath(); c.roundRect(x, y, w, h, r); }

function card(x, y, w, h, o = {}) {
  const { r = 14, fill = 'rgba(255,255,255,.95)', alpha = 1, shadow = true, stroke } = o;
  c.save();
  c.globalAlpha *= alpha;
  if (shadow) { c.shadowColor = 'rgba(6,24,16,.34)'; c.shadowBlur = 26; c.shadowOffsetY = 10; }
  c.fillStyle = fill;
  rrect(x, y, w, h, r);
  c.fill();
  c.shadowColor = 'transparent';
  if (stroke) { c.strokeStyle = stroke; c.lineWidth = 1.5; c.stroke(); }
  c.restore();
}
const DARK = 'rgba(9,31,23,.86)';

// Headline that wipes up out of its own baseline.
function reveal(str, x, y, start, o = {}) {
  const p = pin(start, o.dur || 14);
  if (p <= 0) return;
  const size = o.size || 44;
  c.save();
  c.beginPath();
  const w = measure(str, size, o.weight || 700);
  const left = o.align === 'center' ? x - w / 2 : o.align === 'right' ? x - w : x;
  c.rect(left - 10, y - size * 1.1, w + 20, size * 1.45);
  c.clip();
  text(str, x, y + (1 - p) * size * 1.3, { weight: 700, shadow: 14, ...o, size });
  c.restore();
}

function kicker(str, x, y, o = {}) {
  const p = pin(o.at ?? 4, 12);
  if (p <= 0) return;
  c.save();
  c.globalAlpha = p;
  const w = measure(str, 15, 500, MONO) + 44;
  card(x, y, w, 34, { fill: o.fill || DARK, r: 17 });
  c.fillStyle = o.dot || C.twin;
  c.beginPath(); c.arc(x + 18, y + 17, 5, 0, 7); c.fill();
  text(str, x + 32, y + 22, { size: 15, weight: 500, font: MONO, color: o.color || '#E9F5EE' });
  c.restore();
}

function illustrative(x = 34, y = 664) {
  text('ILLUSTRATIVE VALUES', x, y, { size: 12, font: MONO, weight: 500, color: 'rgba(255,255,255,.75)', track: 1, shadow: 6 });
}

// Stage tracker for the four-step tour.
const STEPS = ['Paste', 'Place', 'Reflow', 'Inspect'];
function stepper(n) {
  const p = pin(2, 14);
  c.save();
  c.globalAlpha = p;
  const x0 = 34, y0 = 32, sw = 94;
  card(x0 - 12, y0 - 12, sw * 4 + 18, 48, { fill: DARK, r: 24 });
  STEPS.forEach((s, i) => {
    const on = i === n, done = i < n;
    c.fillStyle = on ? C.twin : done ? '#5FA88A' : 'rgba(255,255,255,.28)';
    c.beginPath(); c.arc(x0 + 10 + i * sw, y0 + 12, 5.5, 0, 7); c.fill();
    text(s, x0 + 24 + i * sw, y0 + 18, { size: 16, weight: on ? 700 : 500, color: on ? '#fff' : 'rgba(255,255,255,.62)' });
  });
  c.restore();
}

// Leader-line label pinned to a tracked 3D point.
function callout(ax, ay, lx, ly, title, sub, start, o = {}) {
  const p = pin(start, 16);
  if (p <= 0) return;
  const w = Math.max(measure(title, 19, 700), sub ? measure(sub, 13, 500, MONO) : 0) + 34;
  const h = sub ? 60 : 42;
  const ex = lx < ax ? lx + w : lx;
  const ey = ly + h / 2;
  c.save();
  c.globalAlpha = clamp(p * 1.5);
  c.strokeStyle = 'rgba(255,255,255,.95)';
  c.lineWidth = 1.8;
  c.shadowColor = 'rgba(0,0,0,.5)'; c.shadowBlur = 4;
  c.beginPath();
  c.moveTo(ax, ay);
  c.lineTo(mix(ax, ex, p), mix(ay, ey, p));
  c.stroke();
  c.fillStyle = o.color || C.mint;
  c.beginPath(); c.arc(ax, ay, 5.5 + 2 * Math.sin(g.f / 7), 0, 7); c.fill();
  c.strokeStyle = '#fff'; c.lineWidth = 2; c.stroke();
  c.restore();
  c.save();
  c.globalAlpha = clamp((p - 0.4) * 2);
  card(lx, ly, w, h, { r: 10 });
  c.fillStyle = o.color || C.green; rrect(lx + 8, ly + 9, 3, h - 18, 2); c.fill();
  text(title, lx + 19, ly + (sub ? 26 : 28), { size: 19, weight: 700, color: C.ink });
  if (sub) text(sub, lx + 19, ly + 47, { size: 13, weight: 500, font: MONO, color: C.muted });
  c.restore();
}

function plate(o = {}) {
  const img = g.plate;
  const z = mix(o.z0 ?? 1.0, o.z1 ?? 1.07, g.f / Math.max(1, g.N - 1));
  const px = mix(o.x0 ?? 0, o.x1 ?? 0, g.f / Math.max(1, g.N - 1));
  c.save();
  if (o.blur) c.filter = `blur(${o.blur}px)`;
  const dw = W * z, dh = H * z;
  c.drawImage(img, (W - dw) / 2 + px, (H - dh) / 2, dw, dh);
  c.restore();
  if (o.shade) { c.fillStyle = `rgba(6,26,19,${o.shade})`; c.fillRect(0, 0, W, H); }
}

// The article's FIG. 3: paste volume through a shift, with and without a stencil wipe.
function driftChart(mode, stage) {
  const x0 = 110, x1 = 1170, y0 = 180, y1 = 590;
  const X = h => x0 + (x1 - x0) * h / 8, Y = v => y1 - (y1 - y0) * (v - 55) / 60;
  card(x0 - 74, y0 - 62, x1 - x0 + 120, y1 - y0 + 122, { fill: 'rgba(9,31,23,.88)', r: 18 });
  text('PASTE VOLUME, % OF TARGET', x0 - 40, y0 - 28, { size: 14, font: MONO, weight: 500, color: '#BCD3C8', track: .6 });
  c.lineWidth = 1;
  for (const v of [60, 70, 80, 90, 100, 110]) {
    c.strokeStyle = 'rgba(255,255,255,.1)'; c.beginPath(); c.moveTo(x0, Y(v)); c.lineTo(x1, Y(v)); c.stroke();
    text(v + '%', x0 - 12, Y(v) + 5, { size: 14, font: MONO, weight: 500, align: 'right', color: '#9FB5AA' });
  }
  for (let h = 0; h <= 8; h++) text(h + 'h', X(h), y1 + 26, { size: 14, font: MONO, weight: 500, align: 'center', color: '#9FB5AA' });
  c.fillStyle = 'rgba(229,72,77,.14)'; c.fillRect(x0, Y(75), x1 - x0, y1 - Y(75));
  c.strokeStyle = C.red; c.setLineDash([8, 7]); c.lineWidth = 2;
  c.beginPath(); c.moveTo(x0, Y(75)); c.lineTo(x1, Y(75)); c.stroke(); c.setLineDash([]);
  text('SPEC MINIMUM 75%', x1 - 8, Y(75) - 9, { size: 14, font: MONO, weight: 600, align: 'right', color: '#FF9A9D' });

  const drift = h => 100 - 3.6 * h - 0.06 * h * h;
  const wiped = h => h < 3 ? drift(h) : h < 3.35 ? mix(drift(3), 100, (h - 3) / .35) : 100 - 2.0 * (h - 3.35);
  const line = (fn, upto, color, width, dash) => {
    c.strokeStyle = color; c.lineWidth = width; c.lineJoin = 'round'; c.setLineDash(dash || []);
    c.beginPath();
    for (let h = 0; h <= upto; h += 0.05) { const px = X(h), py = Y(fn(h)); h === 0 ? c.moveTo(px, py) : c.lineTo(px, py); }
    c.stroke(); c.setLineDash([]);
  };
  const dot = (h, v, color) => { c.fillStyle = color; c.beginPath(); c.arc(X(h), Y(v), 7, 0, 7); c.fill(); c.strokeStyle = '#fff'; c.lineWidth = 2; c.stroke(); };
  if (mode === 'drift') {
    const a = 8 * clamp(stage);
    line(drift, a, C.amber, 4);
    dot(a, drift(a), C.amber);
    if (a > 6.72) {
      const p = clamp((a - 6.72) / .8);
      c.save(); c.globalAlpha = p;
      card(X(6.0), Y(62), 230, 46, { fill: C.red, r: 10 });
      text('Weak joints under the QFN', X(6.0) + 14, Y(62) + 29, { size: 15, weight: 700 });
      c.restore();
    }
  } else {
    line(drift, 8, 'rgba(245,165,36,.42)', 3, [6, 6]);
    const a = 8 * clamp(stage);
    line(wiped, a, C.twin, 4.5);
    dot(a, wiped(a), C.twin);
  }
  return { X, Y, drift };
}

function bars(x, y, w, h, vals, color, p) {
  const bw = w / vals.length;
  vals.forEach((v, i) => {
    const t = clamp(p * vals.length - i);
    c.fillStyle = typeof color === 'function' ? color(i) : color;
    rrect(x + i * bw + 3, y + h - h * v * t, bw - 6, h * v * t, 3);
    c.fill();
  });
}

function logRow(x, y, w, key, val, tone, alpha = 1) {
  c.save(); c.globalAlpha *= alpha;
  text(key, x, y, { size: 14, font: MONO, weight: 500, color: '#BCD3C8' });
  text(val, x + w, y, { size: 14, font: MONO, weight: 600, align: 'right', color: tone || '#fff' });
  c.restore();
}

const flash = (start, dur, color = '#fff', peak = .9) => {
  const t = (g.f - start) / dur;
  if (t < 0 || t > 1) return;
  c.fillStyle = color; c.globalAlpha = peak * (1 - t); c.fillRect(0, 0, W, H); c.globalAlpha = 1;
};

const O = {
  line_wide() { kicker('LINE 2 · 03:14 · ALL STATIONS PASSING', 34, 34, { at: 8 }); text('Example scenario', 36, 92, { size: 13, weight: 500, alpha: .85, shadow: 6 }); },
  paste_macro() {
    kicker('PASTE DEPOSIT · IN SPEC', 34, 34, { at: 3 });
  },
  aoi_pass() {
    const pts = [['u2', 74], ['u3', 62], ['u5', 66], ['u1', 54]];
    pts.forEach(([a, s], i) => {
      const p = back(prog(10 + i * 11, 10));
      if (p <= 0) return;
      const [x, y] = g.anchor(a);
      c.strokeStyle = C.mint; c.lineWidth = 3;
      c.strokeRect(x - s * p / 2, y - s * .62 * p / 2, s * p, s * .62 * p);
      text('PASS', x, y - s * .36 - 8, { size: 15, font: MONO, weight: 600, align: 'center', alpha: clamp(p), shadow: 6 });
    });
    const n = 4809 + Math.min(3, Math.floor(g.f / 16));
    card(1000, 34, 246, 78, { fill: DARK });
    text('BOARD', 1020, 62, { size: 13, font: MONO, weight: 500, color: '#BCD3C8' });
    text('#' + n.toLocaleString('en-CA').replace(/\s/, ','), 1020, 96, { size: 32, weight: 700 });
    text('PASS', 1226, 96, { size: 22, font: MONO, weight: 600, align: 'right', color: C.twin });
  },
  fail_clock() {
    plate({ z0: 1.0, z1: 1.14, blur: 1 });
    const hrs = 1 + Math.min(4, Math.floor(g.f / (g.N / 4.2)));
    c.fillStyle = `rgba(229,72,77,${.1 + .12 * clamp(g.f / g.N)})`; c.fillRect(0, 0, W, H);
    text('+' + hrs + 'h', W / 2, 360, { size: 110, weight: 800, align: 'center', shadow: 22 });
    text('FAST-FORWARD', W / 2, 400, { size: 16, font: MONO, weight: 500, align: 'center', shadow: 8 });
  },
  question() {
    plate({ blur: 5, z0: 1.14, z1: 1.2, shade: .52 });
    reveal('How do you catch a failure', W / 2, 330, 4, { size: 54, align: 'center' });
    reveal("that hasn't happened yet?", W / 2, 400, 14, { size: 54, align: 'center', color: C.twin });
  },
  twin_reveal() {
    reveal('A second factory.', 70, 112, g.cue('second'), { size: 50 });
    reveal('One that doesn’t physically exist.', 70, 166, g.cue('one'), { size: 30, color: C.twin, weight: 600 });
  },
  cockpit() {},
  cockpit2() {},
  twin_orbit() {
    reveal('DIGITAL TWIN', W / 2, 340, 8, { size: 86, align: 'center', weight: 800 });
    reveal('A flight simulator for a factory', W / 2, 392, 22, { size: 28, align: 'center', color: C.twin, weight: 500 });
  },
  board_twin() {
    text('REAL BOARD', 90, 640, { size: 18, font: MONO, weight: 600, alpha: pin(6), shadow: 8 });
    text('NOT JUST A MODEL', 1190, 640, { size: 18, font: MONO, weight: 600, align: 'right', alpha: pin(14), color: C.twin, shadow: 8 });
  },
  map_phone() {
    const road = g.cue('roads'), app = g.cue('traffic');
    if (g.f >= road - 10) callout(330, 430, 90, 110, 'Paper map', 'A picture: shows roads', road - 10);
    if (g.f >= app) callout(1035, 330, 720, 96, 'Traffic app', 'A mirror: live right now', app + 8);
  },
  board_feed() {
    const [rx, ry] = g.anchor('real'), [tx, ty] = g.anchor('twin');
    const items = ['Paste height', 'Mis-picks', 'Zone temps', 'Joint images'];
    for (let i = 0; i < 26; i++) {
      const o = i * 37 % 300, x = rx + ((i * 73) % 640 - 320);
      const t = ((g.f + i * 13) % 56) / 56;
      c.fillStyle = C.twin; c.globalAlpha = Math.sin(t * Math.PI) * pin(g.cue('fed') - 8);
      c.beginPath(); c.arc(mix(x, x * .9 + tx * .1, t), mix(ry - 20, ty + 42, t), 3.4, 0, 7); c.fill();
    }
    c.globalAlpha = 1;
    items.forEach((s, i) => { const a = g.cue('fed') + i * 8; if (g.f >= a) card(40, 260 + i * 44, 170, 36, { fill: DARK, r: 9, alpha: pin(a) }); if (g.f >= a) text(s, 56, 284 + i * 44, { size: 16, weight: 600, alpha: pin(a) }); });
    kicker('SOFTWARE COPY · LIVE', 34, 34, { at: 8 });
  },
  line_change() {
    plate({ z0: 1.0, z1: 1.09, shade: .28 });
    const ch = 30, val = g.f < ch ? 245 : 245 + 3 * pin(ch, 18);
    [['REAL LINE · ZONE 7', 110, C.white], ['DIGITAL TWIN · ZONE 7', 680, C.twin]].forEach(([t, x, col], i) => {
      card(x, 230, 490, 190, { fill: DARK, alpha: pin(4 + i * 8) });
      text(t, x + 30, 276, { size: 17, font: MONO, weight: 500, color: col, alpha: pin(4 + i * 8) });
      const v = i ? (g.f < ch + 9 ? 245 : val) : val;
      text(v.toFixed(0) + ' °C', x + 30, 370, { size: 76, weight: 800, alpha: pin(4 + i * 8), color: g.f > ch + (i ? 9 : 0) && g.f < ch + 40 + (i ? 9 : 0) ? C.amber : '#fff' });
    });
    if (g.f > g.cue('and')) reveal('Two-way link', W / 2, 520, g.cue('and'), { size: 36, align: 'center', color: C.twin });
  },
  line_track() { stepper(-1); },
  paste_spheres() {
    stepper(0);
    const s = g.anchor('sphere');
    callout(s[0], s[1], 90, 520, 'Solder spheres', '20–38 µm, Type 4 paste', 16);
    callout(640, 268, 900, 520, 'Sticky flux', 'cleans and holds', 40, { color: C.amber });
  },
  squeegee() {
    stepper(0);
    const a = g.cue('stencil');
    const p = pin(a, 20);
    card(860, 430, 360, 188, { fill: DARK, alpha: p });
    text('STEEL STENCIL VS CREDIT CARD', 884, 466, { size: 13, font: MONO, weight: 500, color: '#BCD3C8', alpha: p, track: .5 });
    text('Stencil', 884, 516, { size: 19, weight: 600, alpha: p }); text('≈ 0.1 mm', 1196, 516, { size: 19, weight: 700, align: 'right', alpha: p });
    c.fillStyle = C.twin; c.globalAlpha = p; c.fillRect(884, 528, 312 * .13 * p, 8);
    c.globalAlpha = 1;
    text('Card', 884, 578, { size: 19, weight: 600, alpha: p }); text('0.76 mm', 1196, 578, { size: 19, weight: 700, align: 'right', alpha: p });
    c.fillStyle = '#9FB5AA'; c.globalAlpha = p; c.fillRect(884, 590, 312 * p, 8); c.globalAlpha = 1;
  },
  spi_scan() {
    stepper(0);
    card(40, 500, 300, 150, { fill: DARK, alpha: pin(3) });
    logRow(62, 540, 256, 'HEIGHT', '118 µm', C.twin, pin(5));
    logRow(62, 574, 256, 'VOLUME', '97 %', C.twin, pin(9));
    logRow(62, 608, 256, 'DEPOSIT', (2140 + g.f * 7).toLocaleString('en-CA').replace(/\s/, ','), '#fff', pin(13));
  },
  pnp_wide() {
    stepper(1);
    reveal('Vacuum nozzles', 950, 600, g.cue('vacuum'), { size: 34 });
    reveal('parts from reels to wet paste', 950, 636, g.cue('vacuum') + 8, { size: 20, weight: 500 });
  },
  pnp_macro() {
    stepper(1);
    card(40, 540, 300, 112, { fill: DARK, alpha: pin(g.cue('every') - 5) });
    logRow(62, 582, 256, 'PARTS PLACED', (1200 + g.f * 3).toLocaleString('en-CA').replace(/\s/, ','), '#fff', pin(g.cue('every')));
    logRow(62, 622, 256, 'MIS-PICKS LOGGED', '3', C.amber, pin(g.cue('every') + 6));
  },
  oven_cut() {
    stepper(2);
    const list = [1, 2, 3, 4, 5, 6, 7, 8];
    list.forEach(i => {
      const [x, y] = g.anchor('z' + i);
      if (x < 30 || x > W - 30) return;
      card(x - 28, y - 16, 56, 30, { fill: DARK, r: 8 });
      text('Z' + i, x, y + 5, { size: 16, font: MONO, weight: 600, align: 'center' });
    });
  },
  melt() {
    stepper(2);
    const f = g.f / g.N;
    const T = f < .4 ? mix(170, 217, f / .4) : f < .7 ? mix(217, 245, (f - .4) / .3) : mix(245, 150, (f - .7) / .3);
    card(980, 34, 266, 104, { fill: DARK });
    text('BOARD TEMP', 1002, 66, { size: 13, font: MONO, weight: 500, color: '#BCD3C8' });
    text(T.toFixed(0) + ' °C', 1002, 118, { size: 46, weight: 800, color: T >= 217 ? C.amber : '#fff' });
    if (f > .36) text('LIQUID', 1226, 118, { size: 16, font: MONO, weight: 600, align: 'right', color: C.amber, alpha: f < .72 ? 1 : 0 });
    if (f > .4 && f < .74) callout(470, 470, 90, 560, 'Surface tension', 'pulls the part into line', g.N * .42);
  },
  joint_macro() {
    stepper(2);
    callout(644, 372, 880, 540, 'Solid joint', 'frozen solder fillet', 10);
  },
  profile() {
    plate({ blur: 6, shade: .4 });
    stepper(2);
    const x0 = 150, x1 = 1130, y0 = 170, y1 = 590;
    card(x0 - 60, y0 - 50, x1 - x0 + 110, y1 - y0 + 100, { fill: DARK, r: 18 });
    const prof = [[0, 25], [.22, 150], [.5, 195], [.58, 217], [.68, 245], [.78, 217], [1, 90]];
    const X = t => x0 + (x1 - x0) * t, Y = v => y1 - (y1 - y0) * v / 270;
    c.setLineDash([7, 7]); c.strokeStyle = C.amber; c.lineWidth = 2; c.beginPath(); c.moveTo(x0, Y(217)); c.lineTo(x1, Y(217)); c.stroke(); c.setLineDash([]);
    text('217 °C, SOLDER MELTS', x0, Y(217) - 9, { size: 13, font: MONO, weight: 600, color: C.amber });
    const a = pin(0, g.N * .85);
    c.strokeStyle = C.twin; c.lineWidth = 4; c.lineJoin = 'round'; c.beginPath();
    for (let i = 0; i <= 200; i++) {
      const t = i / 200 * a;
      let k = 0; while (k < prof.length - 2 && t > prof[k + 1][0]) k++;
      const [ta, va] = prof[k], [tb, vb] = prof[k + 1];
      const v = mix(va, vb, inOut((t - ta) / (tb - ta)));
      i ? c.lineTo(X(t), Y(v)) : c.moveTo(X(t), Y(v));
    }
    c.stroke();
    ['PREHEAT', 'SOAK', 'REFLOW', 'COOL'].forEach((s, i) => text(s, X([.1, .38, .66, .9][i]), y1 + 26, { size: 14, font: MONO, weight: 500, align: 'center', color: '#BCD3C8' }));
    illustrative(100, 650);
  },
  aoi_cam() { stepper(3); kicker('AOI · RED, GREEN, BLUE LIGHT', 34, 90, { at: 4 }); },
  xray() { stepper(3); callout(640, 360, 860, 520, 'Hidden joints', 'no camera can reach them', 6, { color: C.green }); },
  test_probe() {
    stepper(3);
    const p = pin(g.N * .55);
    card(920, 560, 320, 92, { fill: DARK, alpha: p });
    text('ELECTRICAL TEST', 944, 592, { size: 13, font: MONO, weight: 500, color: '#BCD3C8', alpha: p });
    text('PASS', 944, 634, { size: 34, weight: 800, color: C.twin, alpha: p });
  },
  diaries() {
    plate({ z0: 1.0, z1: 1.08, blur: 2, shade: .34 });
    const logs = [['PRINTER', 'paste height'], ['PLACER', 'mis-picks'], ['OVEN', 'zone temps'], ['AOI', 'joint images']];
    logs.forEach(([t, s], i) => {
      const a = 8 + i * 10, x = 60 + i * 296, y = 200 + (i % 2) * 40 + Math.sin(g.f / 30 + i) * 4;
      c.save(); c.globalAlpha = pin(a);
      c.translate(x + 130, y + 140); c.rotate((i - 1.5) * .025); c.translate(-(x + 130), -(y + 140));
      card(x, y, 262, 262, { fill: 'rgba(255,255,255,.96)' });
      text(t, x + 22, y + 42, { size: 21, weight: 800, color: C.ink });
      text(s, x + 22, y + 66, { size: 14, font: MONO, weight: 500, color: C.muted });
      for (let r = 0; r < 7; r++) {
        const v = ((g.f + r * 11 + i * 7) * 37) % 997;
        text(String(v).padStart(4, '0'), x + 22, y + 104 + r * 22, { size: 14, font: MONO, weight: 500, color: '#2C4238' });
        c.fillStyle = 'rgba(8,120,68,.28)'; c.fillRect(x + 80, y + 95 + r * 22, 40 + (v % 130), 8);
      }
      c.restore();
    });
    reveal('Nobody reads them side by side.', W / 2, 90, g.cue('nobody'), { size: 38, align: 'center' });
  },
  diary_trace() {
    plate({ z0: 1.08, z1: 1.0, shade: .44 });
    const st = ['Print', 'Place', 'Reflow', 'AOI', 'Test'];
    const rowY = 300, x0 = 110, gap = 265;
    reveal('BOARD #4,812', W / 2, 150, 4, { size: 50, align: 'center', weight: 800 });
    const walk = g.cue('walk');
    const back_ = g.f < walk ? -1 : Math.floor((g.f - walk) / ((g.N - walk) / 5.2));
    st.forEach((s, i) => {
      const x = x0 + i * gap, a = 10 + i * 7, p = pin(a);
      const isFail = i === 4, isRoot = i === 0 && back_ >= 4, lit = back_ >= 4 - i && back_ >= 0;
      card(x - 90, rowY, 180, 112, { fill: isRoot ? C.amber : isFail ? C.red : lit ? 'rgba(61,242,160,.95)' : DARK, alpha: p });
      text(s, x, rowY + 46, { size: 24, weight: 800, align: 'center', color: lit && !isFail ? C.ink : '#fff', alpha: p });
      text(isFail ? 'FAILED' : isRoot ? 'VOLUME LOW' : 'logged', x, rowY + 80, { size: 14, font: MONO, weight: 600, align: 'center', color: lit && !isFail ? C.ink : '#D5E5DC', alpha: p });
      if (i) { c.strokeStyle = 'rgba(255,255,255,.7)'; c.lineWidth = 2.5; c.globalAlpha = p; c.beginPath(); c.moveTo(x - gap + 92, rowY + 56); c.lineTo(x - 92, rowY + 56); c.stroke(); c.globalAlpha = 1; }
    });
    if (back_ >= 4) reveal('Root cause: one stencil aperture', W / 2, 520, walk + (g.N - walk) * .78, { size: 32, align: 'center', color: C.amber });
  },
  dashboard() {
    plate({ z0: 1.02, z1: 1.1, blur: 3, shade: .46 });
    card(180, 150, 920, 400, { fill: DARK });
    text('LINE 2 DASHBOARD', 214, 194, { size: 16, font: MONO, weight: 500, color: '#BCD3C8' });
    [['First pass yield', '99.7 %'], ['Boards today', '4,812'], ['Oven peak', '245 °C']].forEach(([a, b], i) => {
      text(a, 214 + i * 286, 250, { size: 17, weight: 500, color: '#CFE2D8' });
      text(b, 214 + i * 286, 304, { size: 44, weight: 800 });
    });
    bars(214, 345, 840, 170, Array.from({ length: 34 }, (_, i) => .35 + .45 * Math.abs(Math.sin(i * 1.7 + g.f / 40))), C.mint, pin(4, 24));
    reveal('What’s happening. Not what’s coming.', W / 2, 628, g.cue('shows'), { size: 34, align: 'center' });
  },
  ml_pattern() {
    plate({ z0: 1.08, z1: 1.0, blur: 4, shade: .55 });
    text('MONTHS OF PRODUCTION HISTORY', 90, 112, { size: 15, font: MONO, weight: 500, color: '#BCD3C8', alpha: pin(4) });
    const cols = 46, rows = 8, cw = 24.2, x0 = 90, y0 = 130;
    const a = g.cue('small'), b = g.cue('expensive');
    const rand = (i, j) => (Math.sin(i * 12.9898 + j * 78.233) * 43758.5453) % 1;
    for (let j = 0; j < rows; j++) for (let i = 0; i < cols; i++) {
      const v = Math.abs(rand(i, j));
      const reveal_ = clamp((g.f - i * .7) / 12);
      c.fillStyle = `rgba(44,203,127,${(.08 + v * .42) * reveal_})`;
      rrect(x0 + i * cw, y0 + j * cw, cw - 3, cw - 3, 3); c.fill();
    }
    [[6, 2], [20, 5], [33, 1]].forEach(([i, j], k) => {
      const pa = pin(a + k * 6), pb = pin(b + k * 6);
      const ax = x0 + i * cw + 10, ay = y0 + j * cw + 10, bx = ax + cw * 3, by = y0 + (j + 2) * cw + 10;
      c.fillStyle = C.amber; c.globalAlpha = pa; c.beginPath(); c.arc(ax, ay, 9, 0, 7); c.fill();
      text('A', ax, ay + 6, { size: 15, weight: 800, align: 'center', color: C.ink });
      c.globalAlpha = 1;
      if (pb > 0) {
        c.strokeStyle = '#fff'; c.lineWidth = 2; c.globalAlpha = pb; c.beginPath(); c.moveTo(ax, ay); c.lineTo(mix(ax, bx, pb), mix(ay, by, pb)); c.stroke();
        c.fillStyle = C.red; c.beginPath(); c.arc(bx, by, 9, 0, 7); c.fill();
        text('B', bx, by + 6, { size: 15, weight: 800, align: 'center' });
        c.globalAlpha = 1;
      }
    });
    reveal('A small change today', 90, 390 + 170, a + 4, { size: 36, color: C.amber });
    reveal('an expensive problem in a day or two', 90, 390 + 214, b, { size: 36 });
  },
  aperture_dry() {
    const w = g.anchor('wall');
    callout(w[0], w[1], 840, 96, 'Paste dries on the wall', 'it clings when the stencil lifts', 12, { color: C.amber });
    if (g.f > g.N * .7) reveal('Slightly less paste released', 70, 640, g.N * .72, { size: 32 });
  },
  drift_chart() {
    plate({ blur: 7, shade: .3 });
    const { X, Y } = driftChart('drift', clamp(g.f / (g.N * .94)));
    if (g.f < g.N * .55) { card(X(.5), Y(70), 240, 44, { fill: C.mint, r: 10, alpha: pin(6) }); text('Still in spec. Still passing.', X(.5) + 14, Y(70) + 28, { size: 15, weight: 700, color: C.ink, alpha: pin(6) }); }
    illustrative(70, 664);
  },
  xray_weak() {
    plate({ z0: 1.0, z1: 1.08 });
    const [x, y] = g.anchor('weak');
    c.strokeStyle = C.red; c.lineWidth = 3; c.setLineDash([8, 6]); rrect(x - 42, y - 170, 84, 340, 12); c.stroke(); c.setLineDash([]);
    callout(x + 42, y, 900, 180, 'Starved joints', 'hidden under the package', 8, { color: C.red });
  },
  flag_chart() {
    plate({ blur: 7, shade: .3 });
    const { X, Y, drift } = driftChart('wipe', clamp((g.f - g.cue('hour') + 10) / (g.N * .6)));
    const a = g.cue('flags');
    if (g.f >= a - 2) {
      const p = back(prog(a - 2, 12));
      card(X(3) + 18, Y(66), 300, 88, { fill: '#fff', alpha: clamp(p) });
      text('TWIN ALERT · HOUR 3', X(3) + 36, Y(66) + 32, { size: 14, font: MONO, weight: 600, color: C.green, alpha: clamp(p) });
      text('Wipe stencil 2. Trend matches', X(3) + 36, Y(66) + 58, { size: 16, weight: 600, color: C.ink, alpha: clamp(p) });
      text('a known failure.', X(3) + 36, Y(66) + 78, { size: 16, weight: 600, color: C.ink, alpha: clamp(p) });
    }
    illustrative(70, 664);
  },
  wipe() { kicker('STENCIL WIPED', 34, 34, { at: 2 }); },
  clean_deposit() {
    reveal('Bad batch', W / 2, 340, 2, { size: 72, align: 'center', weight: 800 });
    const p = pin(g.cue('never') , 12);
    c.strokeStyle = C.red; c.lineWidth = 8; c.beginPath(); c.moveTo(W / 2 - 190, 316); c.lineTo(W / 2 - 190 + 380 * p, 316); c.stroke();
    if (p > 0) reveal('never exists', W / 2, 424, g.cue('never') + 2, { size: 58, align: 'center', color: C.twin });
  },
  aoi_grid() {
    plate({ blur: 8, shade: .45, z0: 1.2, z1: 1.2 });
    const a = g.cue('models');
    text(g.f < a ? 'RULE-BASED AOI' : 'AI-TRAINED INSPECTION', 70, 96, { size: 20, font: MONO, weight: 600, color: g.f < a ? C.amber : C.twin });
    const img = g.plate, cols = 7, rows = 3, cw = 160, gap = 8, x0 = 70, y0 = 122;
    const flagged = [1, 4, 6, 9, 11, 13, 16, 18, 20];
    for (let i = 0; i < cols * rows; i++) {
      const x = x0 + (i % cols) * (cw + gap), y = y0 + Math.floor(i / cols) * (cw + gap), p = pin(i * 1.6);
      c.save(); c.globalAlpha = p; rrect(x, y, cw, cw, 8); c.clip();
      const sx = 330 + (i * 83) % 520, sy = 300 + (i * 47) % 170;
      c.drawImage(img, sx, sy, 150, 150, x, y, cw, cw);
      c.restore();
      const fl = flagged.indexOf(i);
      if (fl < 0) continue;
      const appear = 12 + fl * 5, drop = a + 8 + fl * 5;
      const keep = i === 9;
      const on = g.f >= appear && (keep || g.f < drop);
      if (on) { c.strokeStyle = keep ? C.red : C.amber; c.lineWidth = 4; rrect(x + 2, y + 2, cw - 4, cw - 4, 8); c.stroke(); text(keep ? 'REAL DEFECT' : 'FALSE ALARM', x + 10, y + cw - 12, { size: 12, font: MONO, weight: 600, shadow: 6 }); }
      else if (g.f >= drop) { c.fillStyle = 'rgba(44,203,127,.2)'; rrect(x, y, cw, cw, 8); c.fill(); }
    }
    illustrative(70, 664);
  },
  inspector() { kicker('JUDGED AGAINST IPC-A-610 WORKMANSHIP CRITERIA', 34, 34, { at: 6 }); },
  q_twin() {
    plate({ z0: 1.0, z1: 1.1 });
    const qs = [['Oven peak +5 °C?', 110, 'raise'], ['New paste supplier?', 760, 'change']];
    reveal('What if?', W / 2, 190, 2, { size: 74, align: 'center', weight: 800 });
    qs.forEach(([t, x, w]) => {
      const a = g.cue(w) - 8, p = back(prog(a, 14));
      if (p <= 0) return;
      card(x, 360 + (1 - p) * 40, 410, 76, { fill: 'rgba(255,255,255,.96)', alpha: clamp(p) });
      text(t, x + 205, 410 + (1 - p) * 40, { size: 28, weight: 700, align: 'center', color: C.ink, alpha: clamp(p) });
    });
  },
  cost_compare() {
    plate({ blur: 4, shade: .36, z0: 1.0, z1: 1.06 });
    const b = g.cue('twin');
    card(100, 200, 500, 300, { fill: 'rgba(255,255,255,.96)', alpha: pin(3) });
    text('ON THE LIVE LINE', 136, 252, { size: 16, font: MONO, weight: 600, color: C.red, alpha: pin(3) });
    ['Boards', 'Parts', 'Machine hours'].forEach((s, i) => text(s, 136, 316 + i * 50, { size: 34, weight: 700, color: C.ink, alpha: pin(8 + i * 6) }));
    card(680, 200, 500, 300, { fill: DARK, alpha: pin(b - 4) });
    text('ON THE TWIN', 716, 252, { size: 16, font: MONO, weight: 600, color: C.twin, alpha: pin(b - 4) });
    text('Minutes', 716, 386, { size: 86, weight: 800, alpha: pin(b + 2) });
  },
  heatmap() {
    const p = g.anchor('copper');
    callout(p[0], p[1], 880, 110, 'Heavy copper lags', 'it soaks up heat', 14, { color: C.red });
    text('MODELLED HEAT FLOW', 34, 54, { size: 15, font: MONO, weight: 600, shadow: 8 });
    illustrative(34, 684);
  },
  shortlist() {
    plate({ z0: 1.08, z1: 1.0, blur: 2, shade: .46 });
    const rows = [['Oven peak +5 °C', 'joints OK', 1], ['New paste', 'more voids', 0], ['Slower conveyor', 'OK', 1], ['Thinner stencil', 'bridging', 0]];
    rows.forEach(([a, b, ok], i) => {
      const t = 6 + i * 9, y = 150 + i * 82, p = pin(t);
      card(100, y, 560, 66, { fill: DARK, r: 11, alpha: p });
      text(a, 126, y + 42, { size: 24, weight: 700, alpha: p });
      text(b, 636, y + 42, { size: 18, font: MONO, weight: 600, align: 'right', color: ok ? C.twin : '#FF9A9D', alpha: p });
    });
    const a = g.cue('short');
    const p = pin(a, 14);
    card(760, 190, 420, 250, { fill: 'rgba(255,255,255,.96)', alpha: p });
    text('REAL BUILD', 970, 256, { size: 18, font: MONO, weight: 600, align: 'center', color: C.green, alpha: p });
    text('Short list', 970, 330, { size: 54, weight: 800, align: 'center', color: C.ink, alpha: p });
    text('not a hunch', 970, 386, { size: 26, weight: 600, align: 'center', color: C.muted, alpha: p });
    illustrative(100, 664);
  },
  nozzle_drop() {
    const t = g.anchor('tip');
    callout(t[0], t[1], 860, 120, 'Worn nozzle', 'losing vacuum grip', 20, { color: C.amber });
  },
  reject_chart() {
    plate({ blur: 7, shade: .46 });
    const vals = [.1, .12, .1, .14, .13, .17, .2, .24, .3, .37, .46, .56];
    text('REJECTS PER SHIFT, NOZZLE 3', 170, 130, { size: 16, font: MONO, weight: 500, color: '#BCD3C8' });
    bars(170, 150, 940, 380, vals, i => i > 6 ? C.amber : C.mint, pin(0, g.N * .75));
    c.strokeStyle = 'rgba(255,255,255,.5)'; c.lineWidth = 2; c.beginPath(); c.moveTo(170, 532); c.lineTo(1110, 532); c.stroke();
    reveal('Too small for anyone to notice', W / 2, 610, 10, { size: 34, align: 'center' });
    illustrative(170, 664);
  },
  schedule() {
    plate({ blur: 6, shade: .42, z0: 1.05, z1: 1.0 });
    const x0 = 200, x1 = 1140, hours = 24, X = h => x0 + (x1 - x0) * h / hours;
    const lane = (y, name, stops) => {
      text(name, x0 - 22, y + 36, { size: 16, weight: 700, align: 'right' });
      c.fillStyle = 'rgba(44,203,127,.85)'; rrect(x0, y, (x1 - x0) * pin(4, 22), 56, 8); c.fill();
      stops.forEach(([h, d, col, label]) => {
        if (g.f < 26) return;
        const p = pin(26);
        c.fillStyle = col; c.globalAlpha = p; rrect(X(h), y - 4, Math.max(6, (X(h + d) - X(h))), 64, 6); c.fill(); c.globalAlpha = 1;
        text(label, X(h) + (X(h + d) - X(h)) / 2, y - 16, { size: 16, weight: 700, align: 'center', color: col === C.red ? '#FF9A9D' : '#fff', alpha: p, shadow: 6 });
      });
    };
    lane(240, 'Run to failure', [[20, 3, C.red, '02:00 BREAKDOWN · ~3 h']]);
    lane(420, 'With a twin', [[12, .5, C.amber, '18:00 PLANNED SWAP · 20 min']]);
    ['06:00', '12:00', '18:00', '00:00', '06:00'].forEach((s, i) => text(s, X(i * 6), 540, { size: 14, font: MONO, weight: 500, align: 'center', color: '#BCD3C8' }));
    illustrative(200, 664);
  },
  silo() {
    plate({ blur: 3, shade: .42, z0: 1.0, z1: 1.06 });
    reveal('Only as good as its data', W / 2, 150, 8, { size: 50, align: 'center' });
    const blocks = 12, x0 = 150, bw = 76;
    const holes = [2, 5, 6, 9], a = g.cue('share');
    for (let i = 0; i < blocks; i++) {
      const hole = holes.includes(i), lost = hole && g.f > a - 10;
      const x = x0 + i * bw, p = pin(14 + i);
      c.globalAlpha = p;
      if (lost) { c.strokeStyle = C.red; c.setLineDash([6, 6]); c.lineWidth = 2.5; rrect(x, 330, bw - 12, 60, 8); c.stroke(); c.setLineDash([]); }
      else { c.fillStyle = C.mint; rrect(x, 330, bw - 12, 60, 8); c.fill(); }
      c.globalAlpha = 1;
    }
    if (g.f > a) reveal('Gaps in the record, wobble in the forecast', W / 2, 470, a, { size: 28, align: 'center', color: '#FF9A9D', weight: 600 });
  },
  engineer() {
    card(70, 500, 520, 140, { fill: DARK, alpha: pin(4) });
    text('Model', 100, 554, { size: 19, font: MONO, weight: 500, color: '#BCD3C8', alpha: pin(4) });
    text('knows that it cracked', 230, 554, { size: 24, weight: 600, alpha: pin(4) });
    text('Engineer', 100, 608, { size: 19, font: MONO, weight: 500, color: C.twin, alpha: pin(12) });
    text('knows why', 230, 608, { size: 30, weight: 800, color: C.twin, alpha: pin(12) });
  },
  nist() {
    plate({ z0: 1.0, z1: 1.12, shade: .42 });
    kicker('NIST · DIGITAL TWINS RESEARCH PROGRAM', 34, 34, { at: 4 });
    const a = g.cue('potential');
    reveal('Standards are still young', W / 2, 230, 8, { size: 40, align: 'center', weight: 600 });
    reveal('Low tens of billions', W / 2, 350, a, { size: 78, align: 'center', weight: 800, color: C.twin });
    reveal('of dollars: potential impact of digital twins in manufacturing', W / 2, 402, a + 14, { size: 22, align: 'center', weight: 500 });
    text('Source: D. Thomas, Economics of Digital Twins, NIST, 2024', W / 2, 618, { size: 14, weight: 500, align: 'center', alpha: pin(a + 20), shadow: 6 });
  },
  ordinary() {},
  no_items() {
    plate({ z0: 1.0, z1: 1.1 });
    const ws = [['No scrap.', 'scrap'], ['No alarm.', 'alarm'], ['No investigation.', 'investigation']];
    ws.forEach(([t, w], i) => reveal(t, 90, 230 + i * 90, g.cue(w) - 8, { size: 58, weight: 800, shadow: 18 }));
    reveal('Just an ordinary shift.', 90, 560, g.cue('ordinary') - 5, { size: 38, weight: 500, color: C.twin });
  },
  final_pull() {
    const end = g.N - 3.2 * 24 - 8;
    const a = g.cue('failure');
    if (g.f < end) {
      reveal('The failure', W / 2, 330, a - 4, { size: 74, align: 'center', weight: 800 });
      reveal('you never see.', W / 2, 410, a + 4, { size: 74, align: 'center', weight: 800, color: C.twin });
    }
    const p = inOut((g.f - end) / 26);
    if (p > 0) {
      c.fillStyle = `rgba(243,246,242,${p})`; c.fillRect(0, 0, W, H);
      c.globalAlpha = clamp((g.f - end - 16) / 16);
      const logo = g.logoDark, lw = 300, lh = lw * logo.naturalHeight / logo.naturalWidth;
      c.drawImage(logo, (W - lw) / 2, (H - lh) / 2 - 14, lw, lh);
      text('Toronto, Canada', W / 2, (H + lh) / 2 + 34, { size: 19, weight: 500, align: 'center', color: C.muted });
      c.globalAlpha = 1;
    }
  },
};

function bug() {
  const logo = g.logoLight;
  const lw = 74, lh = lw * logo.naturalHeight / logo.naturalWidth;
  c.save();
  c.globalAlpha = .92;
  c.shadowColor = 'rgba(0,0,0,.6)'; c.shadowBlur = 8;
  c.drawImage(logo, W - lw - 30, 30, lw, lh);
  c.restore();
}

window.setShot = async (shot, plateUrl, anchors) => {
  const logoLight = await load('/assets/img/stim-logo-light.svg');
  const logoDark = await load('/assets/img/stim-logo.svg');
  const pl = plateUrl ? await load(plateUrl) : null;
  await document.fonts.load("700 20px 'DM Sans'");
  await document.fonts.load("500 20px 'Plex'");
  g = { shot, N: shot.frames, f: 0, plate: pl, logoLight, logoDark, anchors: anchors || {} };
  g.cue = (word, n = 1) => {
    const k = word.toLowerCase();
    let seen = 0;
    for (const w of shot.words) if (w.w.toLowerCase().replace(/[^a-z0-9']/g, '').startsWith(k) && ++seen === n) return w.f;
    console.warn('cue missing', shot.id, word);
    return Math.round(shot.frames * .4);
  };
  g.anchor = name => {
    const a = g.anchors[name];
    return a ? a[Math.min(g.f, a.length - 1)] : [W / 2, H / 2];
  };
};

window.drawFrame = (f, bgUrlImage) => {
  g.f = f;
  c.clearRect(0, 0, W, H);
  c.globalAlpha = 1;
  (O[g.shot.id] || (() => {}))();
  if (g.shot.id !== 'final_pull' || f < g.N - 3.2 * 24 - 8) bug();
  return true;
};

window.grab = () => cv.toDataURL('image/png').split(',')[1];
window.preview = async (bg) => {
  const i = await load(bg);
  c.globalCompositeOperation = 'destination-over';
  c.drawImage(i, 0, 0, W, H);
  c.globalCompositeOperation = 'source-over';
};
window.shotList = () => Object.keys(O);
