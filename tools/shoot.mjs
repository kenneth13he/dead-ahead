// Dev helper: screenshot a page as an iPhone (390x844 @3x) via Chrome DevTools Protocol.
// usage: node tools/shoot.mjs <url> <out.png> [waitForSelector] [dark|light] [fullPage]
import { spawn } from "node:child_process";
import fs from "node:fs";
import os from "node:os";
import path from "node:path";

const [url, out, waitSel = "body", scheme = "dark", full = ""] = process.argv.slice(2);
const CHROME = "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome";
const port = 9300 + Math.floor(Math.random() * 500);
const prof = fs.mkdtempSync(path.join(os.tmpdir(), "da-shoot-"));
const chrome = spawn(CHROME, ["--headless=new", `--remote-debugging-port=${port}`, `--user-data-dir=${prof}`, "--no-first-run", "about:blank"], { stdio: "ignore" });
const sleep = (ms) => new Promise((r) => setTimeout(r, ms));

let ws;
for (let i = 0; i < 50 && !ws; i++) {
  try {
    const targets = await (await fetch(`http://127.0.0.1:${port}/json`)).json();
    const page = targets.find((t) => t.type === "page");
    ws = new WebSocket(page.webSocketDebuggerUrl);
  } catch { await sleep(200); }
}
await new Promise((r) => ws.addEventListener("open", r));
let id = 0; const pending = new Map();
ws.addEventListener("message", (m) => { const d = JSON.parse(m.data); pending.get(d.id)?.(d); });
const send = (method, params = {}) => new Promise((r) => { const i = ++id; pending.set(i, r); ws.send(JSON.stringify({ id: i, method, params })); });

await send("Emulation.setDeviceMetricsOverride", { width: 390, height: 844, deviceScaleFactor: 3, mobile: true });
await send("Emulation.setEmulatedMedia", { features: [{ name: "prefers-color-scheme", value: scheme }] });
await send("Page.enable");
await send("Page.navigate", { url });
let ok = false;
for (let i = 0; i < 100; i++) {
  const r = await send("Runtime.evaluate", { expression: `(()=>{const e=document.querySelector(${JSON.stringify(waitSel)});return !!e && !e.closest('[hidden]')})()`, returnByValue: true });
  if (r.result?.result?.value) { ok = true; break; }
  await sleep(150);
}
await sleep(400);
const h = full ? (await send("Runtime.evaluate", { expression: "document.documentElement.scrollHeight", returnByValue: true })).result.result.value : 844;
if (full) await send("Emulation.setDeviceMetricsOverride", { width: 390, height: h, deviceScaleFactor: 2, mobile: true });
await sleep(200);
const shot = await send("Page.captureScreenshot", { format: "png" });
fs.writeFileSync(out, Buffer.from(shot.result.data, "base64"));
console.log(`${ok ? "✓" : "⚠ selector not found:"} ${waitSel} -> ${out} (${h}px)`);
ws.close(); chrome.kill(); await sleep(500); try { fs.rmSync(prof, { recursive: true, force: true, maxRetries: 5 }); } catch {}
