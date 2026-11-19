const fs = require('fs');
const path = require('path');
const crypto = require('crypto');
const { spawn } = require('child_process');

const CHROME_PATH = 'C:\\Program Files\\Google\\Chrome\\Application\\chrome.exe';
const SCREENSHOTS_DIR = path.resolve(
  'C:/Users/ADMIN/.gemini/antigravity/brain/3c3792fe-a25b-4b45-89fc-9fe2f02a0e53/screenshots'
);

fs.mkdirSync(SCREENSHOTS_DIR, { recursive: true });

function getSha256(filePath) {
  const fileBuffer = fs.readFileSync(filePath);
  const hashSum = crypto.createHash('sha256');
  hashSum.update(fileBuffer);
  return hashSum.digest('hex');
}

async function main() {
  console.log('Starting Chrome CDP on 9222...');

  const chrome = spawn(CHROME_PATH, [
    '--headless=new',
    '--remote-debugging-port=9222',
    '--disable-gpu',
    '--no-sandbox',
    'about:blank',
  ]);

  let wsUrl = '';
  for (let i = 0; i < 40; i++) {
    await new Promise((r) => setTimeout(r, 250));
    try {
      const res = await fetch('http://127.0.0.1:9222/json/list');
      const data = await res.json();
      const pageTarget = data.find((t) => t.type === 'page');
      if (pageTarget && pageTarget.webSocketDebuggerUrl) {
        wsUrl = pageTarget.webSocketDebuggerUrl;
        break;
      }
    } catch {}
  }

  if (!wsUrl) {
    console.error('Failed to connect to Chrome debugging port');
    chrome.kill();
    process.exit(1);
  }

  const ws = new WebSocket(wsUrl);
  await new Promise((resolve) => {
    ws.onopen = resolve;
  });

  let msgId = 1;
  const pending = new Map();

  ws.onmessage = (event) => {
    const data = JSON.parse(event.data);
    if (data.id && pending.has(data.id)) {
      const cb = pending.get(data.id);
      pending.delete(data.id);
      cb(data);
    }
  };

  function send(method, params = {}) {
    return new Promise((resolve) => {
      const id = msgId++;
      pending.set(id, (res) => resolve(res.result));
      ws.send(JSON.stringify({ id, method, params }));
    });
  }

  async function evalJS(expression) {
    const res = await send('Runtime.evaluate', {
      expression,
      returnByValue: true,
      awaitPromise: true,
    });
    return res?.result?.value;
  }

  await send('Page.enable');
  await send('DOM.enable');

  let currentWidth = 1440;

  async function setViewport(width, height) {
    currentWidth = width;
    await send('Emulation.setDeviceMetricsOverride', {
      width,
      height,
      deviceScaleFactor: 1,
      mobile: width <= 768,
    });
    await new Promise((r) => setTimeout(r, 250));
  }

  async function waitForSelector(selector, timeoutMs = 20000) {
    const start = Date.now();
    while (Date.now() - start < timeoutMs) {
      const found = await evalJS(`
        (function() {
          const loading = document.querySelector('.search-spinner-inline');
          const el = document.querySelector(${JSON.stringify(selector)});
          return Boolean(el) && !loading;
        })()
      `);
      if (found) return true;
      await new Promise((r) => setTimeout(r, 250));
    }
    return false;
  }

  async function resetHome() {
    await send('Page.navigate', { url: 'http://localhost:5173/#/app' });
    await send('Page.reload', { ignoreCache: false });
    await new Promise((r) => setTimeout(r, 800));
    await waitForSelector('.home-cards-grid', 15000);
    await new Promise((r) => setTimeout(r, 300));
  }

  async function runQuery(queryText, expectedSelector) {
    await resetHome();
    await evalJS(`
      (function() {
        const input = document.getElementById('question-input');
        if (!input) return false;
        const setter = Object.getOwnPropertyDescriptor(window.HTMLInputElement.prototype, 'value').set;
        setter.call(input, ${JSON.stringify(queryText)});
        input.dispatchEvent(new Event('input', { bubbles: true }));
        input.dispatchEvent(new Event('change', { bubbles: true }));
        return true;
      })()
    `);
    await new Promise((r) => setTimeout(r, 300));
    await evalJS(`
      (function() {
        const btn = document.querySelector('.search-submit-btn');
        if (btn) { btn.click(); return true; }
        return false;
      })()
    `);
    await new Promise((r) => setTimeout(r, 600));
    const ok = await waitForSelector(expectedSelector, 25000);
    if (!ok) {
      console.warn(`Warning: selector "${expectedSelector}" not found in time for query "${queryText}"`);
    }

    // Scroll to bottom to load all layout and settle
    await evalJS(`
      (function() {
        window.scrollTo(0, document.documentElement.scrollHeight);
      })()
    `);
    await new Promise((r) => setTimeout(r, 500));
    // Scroll back to top
    await evalJS(`window.scrollTo(0, 0);`);
    await new Promise((r) => setTimeout(r, 500));
  }

  async function captureFullPage(filename, stateLabel) {
    const metrics = await evalJS(`
      (function() {
        const h = Math.max(
          document.body.scrollHeight,
          document.documentElement.scrollHeight,
          900
        );
        const mainEl = document.querySelector('main') || document.body;
        const headings = Array.from(mainEl.querySelectorAll('h1, h2, h3, h4'))
          .map(el => el.textContent.trim().replace(/\\s+/g, ' '))
          .filter(Boolean);
        return {
          fullPageHeight: h,
          headingCount: headings.length,
          firstHeading: headings.length > 0 ? headings[0] : '(none)',
          lastHeading: headings.length > 0 ? headings[headings.length - 1] : '(none)',
          allHeadings: headings.slice(0, 10),
        };
      })()
    `);

    const captureHeight = Math.min(metrics.fullPageHeight, 12000);
    const { data } = await send('Page.captureScreenshot', {
      format: 'png',
      captureBeyondViewport: true,
      clip: {
        x: 0,
        y: 0,
        width: currentWidth,
        height: captureHeight,
        scale: 1,
      },
    });
    const buffer = Buffer.from(data, 'base64');
    const outPath = path.join(SCREENSHOTS_DIR, filename);
    fs.writeFileSync(outPath, buffer);
    const sha = getSha256(outPath);

    console.log(
      `Saved ${filename} | ${currentWidth}x${metrics.fullPageHeight}px | ${buffer.length} bytes | sha=${sha.substring(0, 12)}...`
    );

    return {
      filename,
      state: stateLabel,
      viewportWidth: currentWidth,
      fullPageHeight: metrics.fullPageHeight,
      size: buffer.length,
      sha,
      firstHeading: metrics.firstHeading,
      lastHeading: metrics.lastHeading,
      headingCount: metrics.headingCount,
    };
  }

  const queries = [
    {
      query: 'Dolo 650',
      selector: '.brand-lookup-view',
      name1440: 'app_dolo_650_1440.png',
      name400: 'app_dolo_650_400.png',
      label: 'Dolo 650 (found in ClinPGx as paracetamol, openable)',
    },
    {
      query: 'Flexon',
      selector: '.brand-lookup-view',
      name1440: 'app_flexon_1440.png',
      name400: 'app_flexon_400.png',
      label: 'Flexon (combination, 2+ ingredients)',
    },
    {
      query: 'Minidolo',
      selector: '.product-orphan-fallback',
      name1440: 'app_minidolo_1440.png',
      name400: 'app_minidolo_400.png',
      label: 'Minidolo (orphan generic)',
    },
    {
      query: 'paracetamol',
      selector: '.card-unrecognized',
      name1440: 'app_paracetamol_1440.png',
      name400: 'app_paracetamol_400.png',
      label: 'paracetamol (ClinPGx search, not brand lookup)',
    },
    {
      query: 'acetaminophen',
      selector: '.overview-table',
      name1440: 'app_acetaminophen_1440.png',
      name400: 'app_acetaminophen_400.png',
      label: 'acetaminophen (ClinPGx search, not brand lookup)',
    },
  ];

  const manifest = [];

  // --- DESKTOP 1440px ---
  console.log('\n--- Capturing 1440px Desktop Screenshots ---');
  await setViewport(1440, 900);

  for (const q of queries) {
    console.log(`Running query: "${q.query}" at 1440px...`);
    await runQuery(q.query, q.selector);
    manifest.push(await captureFullPage(q.name1440, `${q.label} [1440px]`));
  }

  // --- MOBILE 400px ---
  console.log('\n--- Capturing 400px Mobile Screenshots ---');
  await setViewport(400, 844);

  for (const q of queries) {
    console.log(`Running query: "${q.query}" at 400px...`);
    await runQuery(q.query, q.selector);
    manifest.push(await captureFullPage(q.name400, `${q.label} [400px]`));
  }

  const manifestPath = path.join(SCREENSHOTS_DIR, 'd9_screenshots_manifest.json');
  fs.writeFileSync(manifestPath, JSON.stringify(manifest, null, 2), 'utf-8');
  console.log(`\nManifest written to ${manifestPath}`);

  ws.close();
  chrome.kill();
  console.log('Done!');
}

main().catch((err) => {
  console.error('Fatal error in capture script:', err);
  process.exit(1);
});
