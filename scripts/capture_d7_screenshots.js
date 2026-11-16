const http = require('http');
const fs = require('fs');
const path = require('path');
const crypto = require('crypto');
const { spawn } = require('child_process');

const CHROME_PATH = 'C:\\Program Files\\Google\\Chrome\\Application\\chrome.exe';
const SCREENSHOTS_DIR = path.resolve('C:/Users/ADMIN/.gemini/antigravity/brain/3c3792fe-a25b-4b45-89fc-9fe2f02a0e53/screenshots');

fs.mkdirSync(SCREENSHOTS_DIR, { recursive: true });

function getSha256(filePath) {
  const fileBuffer = fs.readFileSync(filePath);
  const hashSum = crypto.createHash('sha256');
  hashSum.update(fileBuffer);
  return hashSum.digest('hex');
}

async function main() {
  console.log('Connecting to Chrome CDP on 9222...');
  
  // Start Chrome with remote debugging
  const chrome = spawn(CHROME_PATH, [
    '--headless=new',
    '--remote-debugging-port=9222',
    '--disable-gpu',
    '--no-sandbox',
    'about:blank',
  ]);

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

  async function setViewport(width, height) {
    await send('Emulation.setDeviceMetricsOverride', {
      width,
      height,
      deviceScaleFactor: 1,
      mobile: width <= 768,
    });
    await new Promise((r) => setTimeout(r, 200));
  }

  async function captureScreenshot(filename) {
    // Wait an extra beat for layout stability
    await new Promise((r) => setTimeout(r, 400));
    const { data } = await send('Page.captureScreenshot', { format: 'png' });
    const buffer = Buffer.from(data, 'base64');
    const outPath = path.join(SCREENSHOTS_DIR, filename);
    fs.writeFileSync(outPath, buffer);
    const sha = getSha256(outPath);
    console.log(`Saved ${filename} (${buffer.length} bytes, SHA-256: ${sha})`);
    return { filename, size: buffer.length, sha };
  }

  async function runQuery(queryText) {
    // 1. Select all text in input and delete it
    await send('Runtime.evaluate', {
      expression: `
        (function() {
          const input = document.getElementById('question-input');
          if (input) {
            input.focus();
            input.select();
          }
        })()
      `,
    });
    await new Promise((r) => setTimeout(r, 100));

    // 2. Type queryText using native CDP Input
    await send('Input.insertText', { text: queryText });
    await new Promise((r) => setTimeout(r, 200));

    // 3. Dispatch Enter key
    await send('Input.dispatchKeyEvent', {
      type: 'rawKeyDown',
      windowsVirtualKeyCode: 13,
      unmangledKey: 'Enter',
      key: 'Enter',
      code: 'Enter',
    });
    await send('Input.dispatchKeyEvent', {
      type: 'keyUp',
      windowsVirtualKeyCode: 13,
      unmangledKey: 'Enter',
      key: 'Enter',
      code: 'Enter',
    });

    // 4. Wait for network fetch and React re-render
    await new Promise((r) => setTimeout(r, 3000));
  }

  async function resetHome() {
    await send('Runtime.evaluate', {
      expression: `
        (function() {
          const clearBtn = document.querySelector('.search-clear-btn');
          if (clearBtn) clearBtn.click();
          const backBtn = document.querySelector('.btn-back-overview');
          // Clear query manually if needed
          const input = document.getElementById('question-input');
          if (input) {
            input.focus();
            input.select();
          }
        })()
      `,
    });
    await send('Input.dispatchKeyEvent', {
      type: 'rawKeyDown',
      windowsVirtualKeyCode: 8,
      key: 'Backspace',
      code: 'Backspace',
    });
    await send('Input.dispatchKeyEvent', {
      type: 'keyUp',
      windowsVirtualKeyCode: 8,
      key: 'Backspace',
      code: 'Backspace',
    });
    // Re-navigate to cleanly reset state
    await send('Page.navigate', { url: 'http://127.0.0.1:5173/#/app' });
    await new Promise((r) => setTimeout(r, 1000));
  }

  const results = [];

  // Navigate to app page
  console.log('\nNavigating to http://127.0.0.1:5173/#/app...');
  await send('Page.navigate', { url: 'http://127.0.0.1:5173/#/app' });
  await new Promise((r) => setTimeout(r, 2500));

  // --- DESKTOP 1440px ---
  console.log('\n--- Capturing Desktop 1440px Screenshots ---');
  await setViewport(1440, 900);

  // 1. Home state
  console.log('\nCapturing 1: Home state');
  await resetHome();
  results.push(await captureScreenshot('app_home_1440.png'));

  // 2. Medicine overview: clopidogrel
  console.log('\nCapturing 2: Query: clopidogrel');
  await runQuery('clopidogrel');
  results.push(await captureScreenshot('app_medicine_overview_1440.png'));

  // 3. Gene overview: CYP2C19
  console.log('\nCapturing 3: Query: CYP2C19');
  await runQuery('CYP2C19');
  results.push(await captureScreenshot('app_gene_overview_1440.png'));

  // 4. Pair detail: CYP2C19 clopidogrel
  console.log('\nCapturing 4: Query: CYP2C19 clopidogrel');
  await runQuery('CYP2C19 clopidogrel');
  results.push(await captureScreenshot('app_pair_detail_1440.png'));

  // 5. Variant detail: rs4244285 clopidogrel
  console.log('\nCapturing 5: Query: rs4244285 clopidogrel');
  await runQuery('rs4244285 clopidogrel');
  results.push(await captureScreenshot('app_variant_detail_1440.png'));

  // 6. Ambiguity picker: CYP2C19*2
  console.log('\nCapturing 6: Query: CYP2C19*2');
  await runQuery('CYP2C19*2');
  results.push(await captureScreenshot('app_ambiguity_1440.png'));

  // 7. Unrecognized query: dolo 650
  console.log('\nCapturing 7: Query: dolo 650');
  await runQuery('dolo 650');
  results.push(await captureScreenshot('app_unrecognized_1440.png'));

  // 8. Refusal state: how much clopidogrel should I take
  console.log('\nCapturing 8: Query: how much clopidogrel should I take');
  await runQuery('how much clopidogrel should I take');
  results.push(await captureScreenshot('app_refusal_1440.png'));

  // --- MOBILE 400px ---
  console.log('\n--- Capturing Mobile 400px Screenshots ---');
  await setViewport(400, 850);

  // 9. Mobile Home state
  console.log('\nCapturing 9: Mobile Home state');
  await resetHome();
  results.push(await captureScreenshot('app_home_400.png'));

  // 10. Mobile Medicine overview
  console.log('\nCapturing 10: Mobile Query: clopidogrel');
  await runQuery('clopidogrel');
  results.push(await captureScreenshot('app_medicine_overview_400.png'));

  // 11. Mobile Pair detail
  console.log('\nCapturing 11: Mobile Query: CYP2C19 clopidogrel');
  await runQuery('CYP2C19 clopidogrel');
  results.push(await captureScreenshot('app_pair_detail_400.png'));

  // 12. Mobile Refusal state
  console.log('\nCapturing 12: Mobile Query: how much clopidogrel should I take');
  await runQuery('how much clopidogrel should I take');
  results.push(await captureScreenshot('app_refusal_400.png'));

  ws.close();
  chrome.kill();

  console.log('\n--- All Screenshots Successfully Captured ---');
  fs.writeFileSync(
    path.join(SCREENSHOTS_DIR, 'd7_screenshots_manifest.json'),
    JSON.stringify(results, null, 2)
  );
}

main().catch((err) => {
  console.error(err);
  process.exit(1);
});
