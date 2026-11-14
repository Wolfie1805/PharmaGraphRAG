const http = require('http');
const fs = require('fs');
const path = require('path');
const { spawn } = require('child_process');

const CHROME_PATH = 'C:\\Program Files\\Google\\Chrome\\Application\\chrome.exe';
const DIST_DIR = path.resolve(__dirname, '../frontend/dist');
const SCREENSHOTS_DIR = path.resolve('C:/Users/ADMIN/.gemini/antigravity/brain/3c3792fe-a25b-4b45-89fc-9fe2f02a0e53/screenshots');

fs.mkdirSync(SCREENSHOTS_DIR, { recursive: true });

// 1. Static file server
const mimeTypes = {
  '.html': 'text/html',
  '.js': 'text/javascript',
  '.css': 'text/css',
  '.json': 'application/json',
  '.png': 'image/png',
  '.woff': 'font/woff',
  '.woff2': 'font/woff2',
};

const server = http.createServer((req, res) => {
  let reqPath = req.url.split('?')[0].split('#')[0];
  if (reqPath === '/') reqPath = '/index.html';
  const filePath = path.join(DIST_DIR, reqPath);

  if (!fs.existsSync(filePath)) {
    // fallback for SPA
    const indexPath = path.join(DIST_DIR, 'index.html');
    res.writeHead(200, { 'Content-Type': 'text/html' });
    return res.end(fs.readFileSync(indexPath));
  }

  const ext = path.extname(filePath);
  const contentType = mimeTypes[ext] || 'application/octet-stream';
  res.writeHead(200, { 'Content-Type': contentType });
  fs.createReadStream(filePath).pipe(res);
});

async function main() {
  server.listen(4173, '127.0.0.1');
  console.log('Serving frontend/dist on http://127.0.0.1:4173...');

  // Start Chrome with remote debugging
  const chrome = spawn(CHROME_PATH, [
    '--headless=new',
    '--remote-debugging-port=9222',
    '--disable-gpu',
    '--no-sandbox',
    'about:blank',
  ]);

  // Wait for Chrome to be ready and get a page target
  let wsUrl = '';
  for (let i = 0; i < 30; i++) {
    await new Promise((r) => setTimeout(r, 200));
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
    server.close();
    process.exit(1);
  }

  console.log('Connected to Chrome CDP at', wsUrl);

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

  await send('Page.enable');
  await send('DOM.enable');

  const sections = [
    { name: '01_hero', id: 'hero' },
    { name: '02_what_it_is', id: 'what-it-is' },
    { name: '03_how_it_works', id: 'how-it-works' },
    { name: '04_does_not_do', id: 'boundaries' },
    { name: '05_benefits', id: 'benefits' },
    { name: '06_use_cases', id: 'use-cases' },
    { name: '07_questions', id: 'example-questions' },
    { name: '08_the_data', id: 'the-data' },
    { name: '09_reliability', id: 'reliability' },
    { name: '10_search_honesty', id: 'search-architecture' },
    { name: '11_quality', id: 'quality' },
    { name: '12_limits_roadmap', id: 'limits-roadmap' },
    { name: '13_faq_footer', id: 'faq' },
  ];

  // Helper to capture
  async function capture(filename, width, height, evaluateScript = null) {
    await send('Emulation.setDeviceMetricsOverride', {
      width,
      height,
      deviceScaleFactor: 1,
      mobile: width <= 768,
    });
    await new Promise((r) => setTimeout(r, 100));

    if (evaluateScript) {
      await send('Runtime.evaluate', { expression: evaluateScript });
      await new Promise((r) => setTimeout(r, 400));
    }

    const { data } = await send('Page.captureScreenshot', { format: 'png' });
    const buffer = Buffer.from(data, 'base64');
    const outPath = path.join(SCREENSHOTS_DIR, filename);
    fs.writeFileSync(outPath, buffer);
    console.log(`Saved ${filename} (${buffer.length} bytes)`);
  }

  // Navigate to landing page
  await send('Page.navigate', { url: 'http://127.0.0.1:4173/#/' });
  await new Promise((r) => setTimeout(r, 1000));

  console.log('\n--- Capturing 1440px Desktop Screenshots ---');
  for (const s of sections) {
    await capture(`section_${s.name}_1440.png`, 1440, 900, `
      (function() {
        const el = document.getElementById("${s.id}");
        if (el) el.scrollIntoView({ behavior: 'instant', block: 'start' });
      })()
    `);
  }

  console.log('\n--- Capturing 400px Mobile Screenshots ---');
  for (const s of sections) {
    await capture(`section_${s.name}_400.png`, 400, 850, `
      (function() {
        const el = document.getElementById("${s.id}");
        if (el) el.scrollIntoView({ behavior: 'instant', block: 'start' });
      })()
    `);
  }

  console.log('\n--- Capturing How It Works Steps 1-6 at 1440px ---');
  for (let step = 1; step <= 6; step++) {
    await capture(`step_panel_step_${step}_1440.png`, 1440, 900, `
      (function() {
        const tab = document.getElementById("step-tab-${step}");
        if (tab) tab.click();
        const section = document.getElementById("how-it-works");
        if (section) section.scrollIntoView({ behavior: 'instant', block: 'start' });
      })()
    `);
  }

  console.log('\n--- Capturing Hero with Scrim at 1440px ---');
  await capture('hero_with_scrim_1440.png', 1440, 900, `
    (function() {
      window.scrollTo(0, 0);
    })()
  `);

  console.log('\n--- Capturing Reduced Effects Hero at 1440px ---');
  await capture('section_hero_reduced_effects_1440.png', 1440, 900, `
    (function() {
      const toggle = document.querySelector(".btn-toggle-effects");
      if (toggle && !toggle.classList.contains("active")) toggle.click();
      window.scrollTo(0, 0);
    })()
  `);

  ws.close();
  chrome.kill();
  server.close();
  console.log('\nAll screenshots captured successfully via CDP!');
}

main().catch((err) => {
  console.error(err);
  server.close();
  process.exit(1);
});
