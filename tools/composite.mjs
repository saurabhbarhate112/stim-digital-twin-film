// Draw the motion-graphics layer over each shot's background and encode one segment per shot.
// node tools/composite.mjs --shots a,b [--preview fraction]
// Background clips: build/bg/<src>.mp4  Plates: build/plates/<src>.jpg  Anchors: build/anchors/<src>.json
import { spawn } from 'node:child_process';
import { createReadStream, existsSync, mkdirSync, readFileSync, writeFileSync } from 'node:fs';
import http from 'node:http';
import path from 'node:path';
import { chromium } from 'playwright';

const ROOT = path.resolve(import.meta.dirname, '..');
const args = Object.fromEntries(process.argv.slice(2).join(' ').split('--').filter(Boolean).map(a => a.trim().split(/\s+/)));
const tl = JSON.parse(readFileSync(path.join(ROOT, 'build/timeline.json'), 'utf8'));
const pick = args.shots ? new Set(args.shots.split(',')) : null;
const shots = tl.shots.filter(s => !pick || pick.has(s.id));
const OUT = path.join(ROOT, 'build/seg');
mkdirSync(OUT, { recursive: true });

const TYPES = { '.html': 'text/html', '.js': 'text/javascript', '.svg': 'image/svg+xml', '.jpg': 'image/jpeg', '.png': 'image/png', '.woff2': 'font/woff2' };
const server = http.createServer((req, res) => {
  const file = path.join(ROOT, decodeURIComponent(req.url.split('?')[0]));
  if (!file.startsWith(ROOT) || !existsSync(file)) { res.writeHead(404); return res.end(); }
  res.writeHead(200, { 'content-type': TYPES[path.extname(file)] || 'application/octet-stream' });
  createReadStream(file).pipe(res);
}).listen(0, '127.0.0.1');
await new Promise(r => server.once('listening', r));
const base = `http://127.0.0.1:${server.address().port}`;

const browser = await chromium.launch();
const page = await browser.newPage({ viewport: { width: 1280, height: 720 } });
page.on('pageerror', e => { console.error('PAGE ERROR', e.message); process.exitCode = 1; });
page.on('console', m => { if (m.type() === 'warning') console.warn(m.text()); });
await page.goto(base + '/compositor/index.html');

const anchors = s => {
  const f = path.join(ROOT, 'build/anchors', s.src + '.json');
  return existsSync(f) ? JSON.parse(readFileSync(f, 'utf8')) : {};
};

async function encodeShot(s) {
  const plate = s.kind === 'plate' ? `/build/plates/${s.src}.jpg` : null;
  await page.evaluate(([shot, p, a]) => window.setShot(shot, p, a), [s, plate, anchors(s)]);
  const dest = path.join(OUT, s.id + '.mp4');
  const enc = ['-c:v', 'libx264', '-preset', 'medium', '-crf', '15', '-pix_fmt', 'yuv420p', '-r', '24'];
  const png = ['-f', 'image2pipe', '-framerate', '24', '-c:v', 'png', '-i', '-'];
  const ff = s.kind === 'plate'
    ? ['-y', '-v', 'error', ...png, ...enc, '-frames:v', s.frames, dest]
    : ['-y', '-v', 'error', '-i', path.join(ROOT, 'build/bg', s.src + '.mp4'), ...png,
      '-filter_complex', '[0:v]fps=24,tpad=stop_mode=clone:stop_duration=2,trim=end_frame=' + s.frames + ',setpts=PTS-STARTPTS[b];[b][1:v]overlay=eof_action=pass:format=auto[o]',
      '-map', '[o]', ...enc, '-frames:v', s.frames, dest];
  const p = spawn('ffmpeg', ff.map(String), { stdio: ['pipe', 'inherit', 'inherit'] });
  for (let f = 0; f < s.frames; f++) {
    await page.evaluate(n => window.drawFrame(n), f);
    const b64 = await page.evaluate(() => window.grab());
    if (!p.stdin.write(Buffer.from(b64, 'base64'))) await new Promise(r => p.stdin.once('drain', r));
  }
  p.stdin.end();
  await new Promise((res, rej) => p.on('close', code => code ? rej(new Error('ffmpeg ' + code)) : res()));
  console.log('segment', s.id, s.frames);
}

async function preview(s, frac) {
  const qaDir = path.join(ROOT, 'build/qa', s.src);
  const plate = s.kind === 'plate' ? `/build/plates/${s.src}.jpg` : null;
  await page.evaluate(([shot, p, a]) => window.setShot(shot, p, a), [s, plate, anchors(s)]);
  const f = Math.floor((s.frames - 1) * frac);
  await page.evaluate(n => window.drawFrame(n), f);
  if (s.kind !== 'plate') {
    const q = existsSync(qaDir) ? (await import('node:fs')).readdirSync(qaDir).find(n => n.endsWith('.jpg')) : null;
    if (q) await page.evaluate(u => window.preview(u), `/build/qa/${s.src}/${q}`);
  }
  const b64 = await page.evaluate(() => window.grab());
  mkdirSync(path.join(ROOT, 'build/qa/over'), { recursive: true });
  writeFileSync(path.join(ROOT, `build/qa/over/${s.id}.png`), Buffer.from(b64, 'base64'));
}

for (const s of shots) {
  if (args.preview) await preview(s, parseFloat(args.preview));
  else await encodeShot(s);
}
await browser.close();
server.close();
