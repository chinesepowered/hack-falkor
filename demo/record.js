// Records the CapyBrain demo: drives the real app (real FalkorDB, real LLM) scene by scene and captures
// Chrome's screencast at 1920x1080, 30 fps, as JPEG frames plus a marks.json with scene and wait times.
//
//   node demo/record.js [outDir]        (expects the app on http://localhost:8000 and demo/out/audio/durations.json)
//
// demo/build_video.py turns the frames into the final video: it keeps every scene at real speed,
// fast-forwards the parts where the app waits for the LLM (marked on screen), and lays the narration on top.
const path = require('path');
const fs = require('fs');

let playwright;
try { playwright = require('playwright'); } catch { playwright = require('/opt/node22/lib/node_modules/playwright'); }
const { chromium } = playwright;

const BASE = process.env.BASE || 'http://localhost:8000';
const OUT = path.resolve(process.argv[2] || path.join(__dirname, 'out', 'raw'));
const FPS = 30;
const MAX_WAIT_SHOWN = 2.5; // seconds a wait lasts after fast-forwarding (must match build_video.py)

const durations = JSON.parse(fs.readFileSync(path.join(__dirname, 'out', 'audio', 'durations.json'), 'utf8'));

// A visible cursor (headless screencasts have none) with a click pulse.
const CURSOR_SCRIPT = `
(() => {
  const install = () => {
    if (document.getElementById('demo-cursor')) return;
    const c = document.createElement('div');
    c.id = 'demo-cursor';
    c.innerHTML = '<svg width="28" height="28" viewBox="0 0 28 28"><path d="M4 2 L4 22 L9.5 17 L13 25 L16.5 23.5 L13 15.8 L20.5 15.8 Z" fill="#fff" stroke="#2e2520" stroke-width="1.6" stroke-linejoin="round"/></svg>';
    Object.assign(c.style, { position: 'fixed', left: '-100px', top: '-100px', zIndex: 2147483647, pointerEvents: 'none', transition: 'transform 0.08s', filter: 'drop-shadow(0 2px 3px rgba(0,0,0,0.35))' });
    const ring = document.createElement('div');
    Object.assign(ring.style, { position: 'fixed', width: '44px', height: '44px', marginLeft: '-22px', marginTop: '-22px', borderRadius: '50%', border: '3px solid #F2B33D', opacity: '0', pointerEvents: 'none', zIndex: 2147483646 });
    document.body.appendChild(ring);
    document.body.appendChild(c);
    window.addEventListener('mousemove', (e) => { c.style.left = e.clientX - 3 + 'px'; c.style.top = e.clientY - 2 + 'px'; }, true);
    window.addEventListener('mousedown', (e) => {
      ring.style.left = e.clientX + 'px'; ring.style.top = e.clientY + 'px';
      ring.animate([{ opacity: 0.9, transform: 'scale(0.4)' }, { opacity: 0, transform: 'scale(1.4)' }], { duration: 500, easing: 'ease-out' });
      c.style.transform = 'scale(0.86)'; setTimeout(() => (c.style.transform = ''), 140);
    }, true);
  };
  if (document.readyState === 'loading') document.addEventListener('DOMContentLoaded', install); else install();
})();`;

async function main() {
  fs.rmSync(OUT, { recursive: true, force: true });
  fs.mkdirSync(path.join(OUT, 'frames'), { recursive: true });
  await fetch(`${BASE}/api/reset`, { method: 'POST' });

  const browser = await chromium.launch({ args: ['--hide-scrollbars', '--disable-dev-shm-usage', '--disable-gpu'] });
  browser.on('disconnected', () => console.log('browser disconnected'));
  const page = await browser.newPage({ viewport: { width: 1920, height: 1080 } });
  await page.addInitScript(CURSOR_SCRIPT);
  page.on('pageerror', (e) => console.log('pageerror:', e.message));
  page.on('crash', () => console.log('PAGE CRASHED'));
  page.on('console', (m) => { if (m.type() === 'error') console.log('console error:', m.text()); });

  // ---- capture: newest screencast frame, sampled at a fixed 30 fps against the wall clock
  const cdp = await page.context().newCDPSession(page);
  let latest = null, latestId = 0, writtenId = -1, lastFile = null, frames = 0, t0 = 0, recording = false;
  cdp.on('Page.screencastFrame', ({ data, sessionId }) => {
    latest = Buffer.from(data, 'base64');
    latestId++;
    cdp.send('Page.screencastFrameAck', { sessionId }).catch(() => {});
  });
  await cdp.send('Page.startScreencast', { format: 'jpeg', quality: 90, maxWidth: 1920, maxHeight: 1080 });
  const sampler = setInterval(() => {
    if (!recording || !latest) return;
    const due = Math.floor(((Date.now() - t0) * FPS) / 1000);
    while (frames < due) {
      const file = path.join(OUT, 'frames', String(frames).padStart(6, '0') + '.jpg');
      if (latestId !== writtenId || !lastFile) {
        fs.writeFileSync(file, latest);
        writtenId = latestId;
        lastFile = file;
      } else {
        fs.linkSync(lastFile, file);
      }
      frames++;
    }
  }, 5);
  const now = () => frames / FPS;

  // ---- scene bookkeeping
  const marks = { fps: FPS, scenes: [] };
  let scene = null;
  const begin = (id) => {
    scene = { id, start: now(), waits: [], events: {} };
    marks.scenes.push(scene);
    console.log(`[${now().toFixed(1)}] ${id}`);
  };
  const shownSoFar = () => {
    const raw = now() - scene.start;
    const saved = scene.waits.reduce((s, w) => s + Math.max(0, (w.end ?? now()) - w.start - MAX_WAIT_SHOWN), 0);
    return raw - saved;
  };
  const holdToNarration = async (extra = 0.6) => {
    const target = (durations[scene.id] || 4) + extra;
    const left = target - shownSoFar();
    if (left > 0) await page.waitForTimeout(left * 1000);
  };
  const end = () => { scene.end = now(); };
  const waitFor = async (fn) => {
    const w = { start: now() };
    scene.waits.push(w);
    await fn();
    w.end = now();
  };
  const event = (name) => { scene.events[name] = now(); };

  // ---- input helpers (smooth, visible mouse)
  let mouse = { x: 960, y: 540 };
  const moveTo = async (x, y, steps = 24) => {
    await page.mouse.move(x, y, { steps });
    mouse = { x, y };
  };
  const click = async (locator, pause = 220) => {
    await locator.waitFor({ state: 'visible', timeout: 60000 });
    await locator.scrollIntoViewIfNeeded();
    const b = await locator.boundingBox();
    await moveTo(b.x + b.width / 2, b.y + b.height / 2);
    await page.waitForTimeout(pause);
    await page.mouse.down();
    await page.mouse.up();
  };
  const settle = (ms) => page.waitForTimeout(ms);

  // =========================================================== scenes
  // intro card (load before recording starts so there is no blank frame)
  await page.goto(`${BASE}/?card=intro`, { waitUntil: 'networkidle' });
  recording = true;
  t0 = Date.now();
  await settle(100);
  begin('intro');
  await holdToNarration(0.9);
  end();

  // the company graph
  await page.goto(`${BASE}/`, { waitUntil: 'networkidle' });
  await settle(3200);
  begin('graph');
  await moveTo(1150, 520, 40);
  await settle(1500);
  await moveTo(1300, 640, 40);
  await settle(1200);
  await moveTo(900, 700, 40);
  await holdToNarration();
  end();

  // why: decision trace with citations
  begin('why');
  await click(page.getByRole('button', { name: 'Why did we move webhooks to a queue?' }));
  await waitFor(() => page.locator('.turn').nth(0).locator('.meta').waitFor({ timeout: 120000 }));
  await settle(2500);
  await click(page.locator('.sources .source').filter({ has: page.locator('.type-badge', { hasText: 'Message' }) }).first());
  await settle(1500);
  await holdToNarration();
  end();

  // who: expertise, someone left
  begin('who');
  await click(page.locator('.detail .close'));
  await click(page.getByRole('button', { name: 'Who can help me with the ledger service?' }));
  await waitFor(() => page.locator('.turn').nth(1).locator('.meta').waitFor({ timeout: 120000 }));
  await settle(2500);
  const wei = page.locator('.sources .source').filter({ hasText: 'Wei in' }).first();
  if (await wei.count()) await click(wei);
  await holdToNarration();
  end();

  // compare: graph vs plain vector RAG
  begin('compare');
  if (await page.locator('.detail .close').count()) await click(page.locator('.detail .close'));
  await click(page.locator('.toggle input'));
  await settle(400);
  await click(page.getByRole('button', { name: /Which customers would break/ }));
  await waitFor(async () => {
    await page.locator('.turn').nth(2).locator('.meta').waitFor({ timeout: 120000 });
    await page.locator('.baseline .snips').waitFor({ timeout: 120000 });
  });
  await settle(1500);
  await moveTo(1700, 300, 30);
  await holdToNarration();
  end();

  // ripple: a change lands
  begin('ripple');
  await click(page.locator('.toggle input')); // comparison off again
  await settle(300);
  await click(page.getByRole('button', { name: /A change lands/ }));
  await settle(1200);
  await click(page.getByRole('button', { name: /Drop it in the hot spring/ }));
  event('drop');
  await page.locator('.tl-step.done').nth(2).waitFor({ timeout: 120000 });
  await settle(3000); // let the rings play at real speed
  await waitFor(() => page.locator('.tl-step.done').nth(4).waitFor({ timeout: 120000 }));
  await settle(1500);
  await click(page.locator('.stale-doc').first());
  await settle(2500);
  await holdToNarration();
  end();

  // work: proposals, approve, what's left
  begin('work');
  if (await page.locator('.detail .close').count()) await click(page.locator('.detail .close'));
  await page.locator('.proposals').waitFor({ timeout: 120000 });
  await settle(1200);
  const edits = page.locator('.prop').filter({ hasText: 'API Quickstart' }).locator('.cy-toggle');
  if (await edits.count()) { await click(edits.first()); await settle(2500); }
  await page.locator('.right-scroll').evaluate((el) => el.scrollTo({ top: el.scrollHeight, behavior: 'smooth' }));
  await settle(1500);
  await click(page.getByRole('button', { name: /Approve \d+ task/ }));
  await settle(3000);
  await click(page.getByRole('button', { name: /what's left/ }));
  await waitFor(() => page.locator('.turn').last().locator('.meta').waitFor({ timeout: 120000 }));
  await settle(2500);
  await holdToNarration();
  end();

  // org x-ray
  begin('xray');
  await click(page.getByRole('button', { name: /Org X-ray/ }));
  await settle(3500);
  await click(page.getByRole('button', { name: 'size graph' }));
  await settle(2500);
  await moveTo(1000, 520, 40);
  await holdToNarration();
  end();

  // outro card
  await page.goto(`${BASE}/?card=outro`, { waitUntil: 'networkidle' });
  await settle(200);
  begin('outro');
  await holdToNarration(1.6);
  end();

  recording = false;
  clearInterval(sampler);
  marks.frames = frames;
  fs.writeFileSync(path.join(OUT, 'marks.json'), JSON.stringify(marks, null, 2));
  console.log(`done: ${frames} frames (${(frames / FPS).toFixed(1)} s) -> ${OUT}`);
  await browser.close();
}

main().catch((e) => { console.error(e); process.exit(1); });
