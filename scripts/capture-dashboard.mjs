// Dev helper: capture docs/dashboard.png from the running operator dashboard.
//
// This is a throwaway tooling script, not part of the app or CI. It uses
// Playwright/Chromium, which is NOT a project dependency — install it ad hoc.
//
// Full reproduction (three terminals or background processes):
//
//   # 1. API with an isolated demo DB
//   cd api && DATABASE_URL="sqlite:///./data/demo.db" \
//     ./.venv/bin/python -m uvicorn src.main:app --port 8011
//
//   # 2. Seed a few violation events through the REAL /events API
//   API=http://127.0.0.1:8011
//   curl -s -XPOST $API/events -H 'content-type: application/json' \
//     -d '{"site_id":"site-001","kind":"no_helmet","confidence":0.93,
//          "bbox_xyxy_norm":[0.12,0.20,0.34,0.78],
//          "description":"Person detected without a hard hat in zone A"}'
//   # ... repeat for the other events ...
//
//   # 3. Dashboard pointed at that API
//   cd dashboard && npm install && \
//     NEXT_PUBLIC_API_URL=http://127.0.0.1:8011 \
//     NEXT_PUBLIC_WS_URL=ws://127.0.0.1:8011 npx next dev -p 3030
//
//   # 4. Capture
//   npm install playwright && npx playwright install chromium
//   SHOT_URL=http://127.0.0.1:3030/ SHOT_OUT=docs/dashboard.png \
//     node scripts/capture-dashboard.mjs
//
import { chromium } from "playwright";

const url = process.env.SHOT_URL || "http://127.0.0.1:3030/";
const out = process.env.SHOT_OUT || "docs/dashboard.png";

const browser = await chromium.launch({ args: ["--no-sandbox"] });
const page = await browser.newPage({
  viewport: { width: 1000, height: 760 },
  deviceScaleFactor: 1.5,
  colorScheme: "dark",
});
await page.goto(url, { waitUntil: "networkidle", timeout: 30000 });
await page.waitForSelector("text=no_helmet", { timeout: 15000 });
await page.waitForTimeout(1000);
await page.screenshot({ path: out, fullPage: true });
await browser.close();
console.log("captured", out);
