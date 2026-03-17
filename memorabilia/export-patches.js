const puppeteer = require('puppeteer');
const path = require('path');
const fs = require('fs');

const ASSETS_DIR = path.join(__dirname, 'assets');

// Physical sizes in cm → pixels at given DPI
// Front patch: ~12 × 16 cm
// Back patch:  ~14 × 18 cm
function cmToPixels(cm, dpi) {
  return Math.round(cm * dpi / 2.54);
}

const PATCHES = [
  {
    name: 'front-patch',
    widthCm: 12,
    heightCm: 16,
    html: () => getFrontPatchHTML(),
  },
  {
    name: 'back-patch',
    widthCm: 14,
    heightCm: 18,
    html: () => getBackPatchHTML(),
  },
];

const DPIS = [1200];

function getFrontPatchHTML() {
  return `<!DOCTYPE html>
<html><head>
<link href="https://fonts.googleapis.com/css2?family=Inter:wght@300;400;500;600;700&display=swap" rel="stylesheet">
<style>
  * { margin: 0; padding: 0; box-sizing: border-box; }
  body {
    background: transparent;
    display: flex;
    align-items: center;
    justify-content: center;
    width: 100vw;
    height: 100vh;
    overflow: hidden;
  }
  .front-patch {
    width: 100vw;
    height: 100vh;
    display: flex;
    flex-direction: column;
    align-items: center;
    justify-content: center;
  }
  .glassbox-icon { margin-bottom: 5%; }
  .f-brand { text-align: center; margin-bottom: 3%; }
  .f-brand-text {
    font-family: 'Inter', sans-serif;
    font-size: 7vw;
    font-weight: 600;
    letter-spacing: 0.2em;
    text-transform: uppercase;
  }
  .f-brand-text .green { color: #4ade80; }
  .f-brand-text .white { color: #ffffff; }
  .f-not {
    font-family: 'Inter', sans-serif;
    font-size: 2.8vw;
    color: #ffffff;
    letter-spacing: 0.4em;
    text-transform: lowercase;
    margin-bottom: 2%;
    text-align: center;
  }
  .f-black {
    font-family: 'Inter', sans-serif;
    font-size: 5vw;
    font-weight: 400;
    color: #f87171;
    letter-spacing: 0.12em;
    text-decoration: line-through;
    text-decoration-thickness: 2px;
    opacity: 0.8;
    text-align: center;
  }
</style>
</head>
<body>
<div class="front-patch">
  <div class="glassbox-icon">
    <svg width="45vw" height="45vw" viewBox="0 0 150 150" fill="none">
      <!-- Original elegant geometry, print-safe strokes, solid colors -->
      <!-- Body -->
      <line x1="75" y1="28" x2="75" y2="122" stroke="#4ade80" stroke-width="4"/>
      <!-- Antennae -->
      <path d="M75 32 Q58 16 52 10" fill="none" stroke="#4ade80" stroke-width="2.5"/>
      <circle cx="52" cy="10" r="5" fill="#4ade80"/>
      <path d="M75 32 Q92 16 98 10" fill="none" stroke="#4ade80" stroke-width="2.5"/>
      <circle cx="98" cy="10" r="5" fill="#4ade80"/>
      <!-- Left upper wing -->
      <path d="M75 38 Q28 32 18 62 Q15 80 48 86 Q68 88 75 74 Z" fill="#0f2018" stroke="#4ade80" stroke-width="2.5"/>
      <!-- Right upper wing -->
      <path d="M75 38 Q122 32 132 62 Q135 80 102 86 Q82 88 75 74 Z" fill="#0f2018" stroke="#4ade80" stroke-width="2.5"/>
      <!-- Left lower wing -->
      <path d="M75 78 Q38 84 26 105 Q30 118 54 112 Q70 109 75 95 Z" fill="#0d1a14" stroke="#4ade80" stroke-width="2.5"/>
      <!-- Right lower wing -->
      <path d="M75 78 Q112 84 124 105 Q120 118 96 112 Q80 109 75 95 Z" fill="#0d1a14" stroke="#4ade80" stroke-width="2.5"/>
      <!-- Wing veins -->
      <path d="M75 38 Q50 50 30 68" fill="none" stroke="#2a7a4e" stroke-width="1.5"/>
      <path d="M75 38 Q45 55 22 72" fill="none" stroke="#2a7a4e" stroke-width="1.5"/>
      <path d="M75 38 Q100 50 120 68" fill="none" stroke="#2a7a4e" stroke-width="1.5"/>
      <path d="M75 38 Q105 55 128 72" fill="none" stroke="#2a7a4e" stroke-width="1.5"/>
      <!-- Agent nodes -->
      <circle cx="48" cy="58" r="12" fill="#1a5c38"/>
      <circle cx="48" cy="58" r="9" fill="#4ade80"/>
      <circle cx="102" cy="58" r="12" fill="#1a5c38"/>
      <circle cx="102" cy="58" r="9" fill="#4ade80"/>
      <circle cx="75" cy="100" r="12" fill="#1a5c38"/>
      <circle cx="75" cy="100" r="9" fill="#4ade80"/>
      <!-- Agent connections -->
      <path d="M48 58 Q75 48 102 58" fill="none" stroke="#2a7a4e" stroke-width="1.5"/>
      <path d="M48 58 Q58 80 75 100" fill="none" stroke="#2a7a4e" stroke-width="1.5"/>
      <path d="M102 58 Q92 80 75 100" fill="none" stroke="#2a7a4e" stroke-width="1.5"/>
    </svg>
  </div>
  <div class="f-brand">
    <span class="f-brand-text"><span class="green">Glass</span><span class="white">Box AI</span></span>
  </div>
  <div class="f-not">-- not --</div>
  <div class="f-black">BlackBox AI</div>
</div>
</body></html>`;
}

function getBackPatchHTML() {
  return `<!DOCTYPE html>
<html><head>
<link href="https://fonts.googleapis.com/css2?family=JetBrains+Mono:wght@300;400;500;600;700&family=Inter:wght@300;400;500;600;700&display=swap" rel="stylesheet">
<style>
  * { margin: 0; padding: 0; box-sizing: border-box; }
  body {
    background: transparent;
    display: flex;
    align-items: center;
    justify-content: center;
    width: 100vw;
    height: 100vh;
    overflow: hidden;
    font-family: 'JetBrains Mono', monospace;
  }
  .back-patch {
    width: 88vw;
    display: flex;
    flex-direction: column;
    align-items: center;
    justify-content: center;
  }
  .diff-header {
    width: 100%;
    padding: 2.2vh 3vw;
    background: #161b22;
    border: 3px solid #4a5568;
    border-bottom: none;
    border-radius: 1.8vw 1.8vw 0 0;
    font-size: 2.8vw;
    color: #8b949e;
    display: flex;
    align-items: center;
    gap: 1.5vw;
  }
  .diff-icon { width: 3vw; height: 3vw; }
  .diff-repo { color: #58a6ff; }
  .diff-body {
    width: 100%;
    background: #0d1117;
    border: 3px solid #4a5568;
    border-radius: 0 0 1.8vw 1.8vw;
    padding: 3vh 0;
    font-size: 3.2vw;
    line-height: 2.6;
  }
  .diff-line { padding: 0 3vw; white-space: nowrap; }
  .diff-line.del { background: rgba(248,113,113,0.1); color: #ffa198; }
  .diff-line.add { background: rgba(74,222,128,0.1); color: #7ee787; }
  .diff-line.blank { color: transparent; user-select: none; line-height: 0.8; font-size: 1vw; }
  .var { color: #ffa657; }
  .op  { color: #79c0ff; }
  .fn  { color: #d2a8ff; }
  .str { color: #a5d6ff; }
  .back-tagline {
    margin-top: 5vh;
    text-align: center;
  }
  .tagline-main {
    font-family: 'JetBrains Mono', monospace;
    font-size: 3vw;
    font-weight: 400;
    color: #7ee787;
    letter-spacing: 0.1em;
  }
</style>
</head>
<body>
<div class="back-patch">
  <div class="diff-header">
    <svg class="diff-icon" viewBox="0 0 16 16" fill="#8b949e">
      <path fill-rule="evenodd" d="M8 0C3.58 0 0 3.58 0 8c0 3.54 2.29 6.53 5.47 7.59.4.07.55-.17.55-.38 0-.19-.01-.82-.01-1.49-2.01.37-2.53-.49-2.69-.94-.09-.23-.48-.94-.82-1.13-.28-.15-.68-.52-.01-.53.63-.01 1.08.58 1.23.82.72 1.21 1.87.87 2.33.66.07-.52.28-.87.51-1.07-1.78-.2-3.64-.89-3.64-3.95 0-.87.31-1.59.82-2.15-.08-.2-.36-1.02.08-2.12 0 0 .67-.21 2.2.82.64-.18 1.32-.27 2-.27.68 0 1.36.09 2 .27 1.53-1.04 2.2-.82 2.2-.82.44 1.1.16 1.92.08 2.12.51.56.82 1.27.82 2.15 0 3.07-1.87 3.75-3.65 3.95.29.25.54.73.54 1.48 0 1.07-.01 1.93-.01 2.2 0 .21.15.46.55.38A8.013 8.013 0 0016 8c0-4.42-3.58-8-8-8z"/>
    </svg>
    <span class="diff-repo">agentic-trust-labs/glassbox-ai</span>
  </div>
  <div class="diff-body">
    <div class="diff-line del">- <span class="var">decisions</span> <span class="op">=</span> <span class="fn">blackbox</span>(<span class="var">model</span>)</div>
    <div class="diff-line del">- <span class="var">trust</span>     <span class="op">=</span> <span class="str">"assumed"</span></div>
    <div class="diff-line del">- <span class="var">oversight</span>  <span class="op">=</span> <span class="str">None</span></div>
    <div class="diff-line blank">.</div>
    <div class="diff-line" style="padding: 1vh 3vw;"><span style="display:block; border-top: 3px solid #4a5568;"></span></div>
    <div class="diff-line blank">.</div>
    <div class="diff-line add">+ <span class="var">agents</span>    <span class="op">=</span> <span class="fn">debate</span>(<span class="var">decisions</span>)</div>
    <div class="diff-line add">+ <span class="var">trust</span>     <span class="op">=</span> <span class="fn">earned</span>(<span class="var">verified</span>)</div>
    <div class="diff-line add">+ <span class="var">oversight</span>  <span class="op">=</span> <span class="fn">transparent</span>(<span class="var">always</span>)</div>
  </div>
  <div class="back-tagline">
    <div class="tagline-main">trustable agents for scalable solutions</div>
  </div>
</div>
</body></html>`;
}

async function exportPatches() {
  console.log('Launching browser...');
  const browser = await puppeteer.launch({
    headless: 'new',
    args: ['--no-sandbox', '--disable-setuid-sandbox'],
  });

  for (const patch of PATCHES) {
    for (const dpi of DPIS) {
      const widthPx = cmToPixels(patch.widthCm, dpi);
      const heightPx = cmToPixels(patch.heightCm, dpi);

      // Use a base viewport and scale factor
      // Base at 96 DPI equivalent, scale up
      const scaleFactor = dpi / 96;
      const baseW = Math.round(widthPx / scaleFactor);
      const baseH = Math.round(heightPx / scaleFactor);

      const page = await browser.newPage();
      await page.setViewport({
        width: baseW,
        height: baseH,
        deviceScaleFactor: scaleFactor,
      });

      const html = patch.html();
      await page.setContent(html, { waitUntil: 'networkidle0' });

      // Wait for fonts to load
      await page.evaluate(() => document.fonts.ready);
      await new Promise(r => setTimeout(r, 1500));

      const filename = `${patch.name}-${dpi}dpi.png`;
      const filepath = path.join(ASSETS_DIR, filename);

      await page.screenshot({
        path: filepath,
        omitBackground: true,  // TRANSPARENT for DTG on black fabric
        type: 'png',
      });

      const stats = fs.statSync(filepath);
      console.log(`✓ ${filename} — ${widthPx}×${heightPx}px (${(stats.size / 1024).toFixed(0)} KB)`);

      await page.close();
    }
  }

  await browser.close();
  console.log(`\nAll PNGs saved to: ${ASSETS_DIR}`);
}

exportPatches().catch(console.error);
