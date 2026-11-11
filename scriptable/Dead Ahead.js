// Variables used by Scriptable.
// These must be at the very top of the file. Do not edit.
// icon-color: red; icon-glyph: location-arrow;

/*
 * Dead Ahead for Scriptable: lock-screen widget + daily wallpaper.
 *
 *  • Run it once in Scriptable  → set up (site URL + passcode, saved in your iPhone Keychain).
 *  • Add as a lock-screen widget → what's still due today (or "Nothing due today").
 *  • Run from Shortcuts          → returns a wallpaper image of your whole week (tests included).
 *
 * Setup guide: see SETUP-IPHONE.md in the repo.
 */

const VERSION = 1;
const KC_URL = "deadahead.site";
const KC_PASS = "deadahead.passcode";
const URGENT_DAYS = 7;          // widget looks this far ahead
const BG_FILE = "dead-ahead-background.jpg"; // optional photo in Scriptable's folder

const COLORS = {
  bgTop: "#141C38", bgBot: "#080B18", ink: "#EEF1F8", muted: "#8C94AB",
  coral: "#FF5A4E", test: "#A78BFA", warn: "#FF922B", line: "#232B42",
};
const URGENT_KINDS = new Set(["assignment", "quiz", "discussion", "peer review", "todo", "deadline"]);
const DAY = 864e5;

/* ------------------------------------------------------------ data picking (pure) */

const startOfDay = (d) => new Date(d.getFullYear(), d.getMonth(), d.getDate());
const dayDiff = (a, b) => Math.round((startOfDay(a) - startOfDay(b)) / DAY);

function openItems(feed, now = new Date()) {
  // Past items only stay (as late) if Quercus marks them missing; Gradescope/MarkUs work drops off once due.
  return feed.items.map((i) => ({ ...i, _d: new Date(i.due) })).filter((i) => !i.done && (i._d >= now || i.missing));
}

/** Widget: unfinished work (not events) that's overdue or due within URGENT_DAYS. */
function pickUrgent(feed, now = new Date()) {
  const until = new Date(startOfDay(now).getTime() + URGENT_DAYS * DAY);
  return openItems(feed, now)
    .filter((i) => (URGENT_KINDS.has(i.kind) || i.test) && i._d < until)
    .sort((a, b) => a._d - b._d);
}

/** Lock-screen widget: only what's still ahead today (nothing overdue). */
function pickToday(feed, now = new Date()) {
  const end = new Date(startOfDay(now).getTime() + DAY);
  return feed.items.map((i) => ({ ...i, _d: new Date(i.due) }))
    .filter((i) => !i.done && i._d >= now && i._d < end)
    .sort((a, b) => a._d - b._d);
}

/** Wallpaper: everything (tests, events, syllabus dates) from now until the end of the school week. Never overdue.
 *  Sun–Fri: through Friday night. From Saturday on, the next week loads in (rest of the weekend + Mon–Fri). */
function weekEnd(now = new Date()) {
  const toSat = (6 - now.getDay() + 7) % 7 || 7; // days until the next Saturday 00:00 (a Saturday counts as next week)
  return new Date(startOfDay(now).getTime() + toSat * DAY);
}
function pickWeek(feed, now = new Date()) {
  const end = weekEnd(now);
  const upcoming = feed.items.map((i) => ({ ...i, _d: new Date(i.due) }))
    .filter((i) => !i.done && i._d >= now && i._d < end);
  const days = [];
  for (let day = startOfDay(now); day < end; day = new Date(day.getTime() + DAY)) {
    const list = upcoming.filter((i) => dayDiff(i._d, day) === 0).sort((a, b) => a._d - b._d);
    if (list.length) days.push({ day, items: list });
  }
  const nextWeek = now.getDay() === 6 || now.getDay() === 0;
  return { overdue: [], days, total: upcoming.length, tests: upcoming.filter((i) => i.test).length, nextWeek };
}

function fmtTime(d, allDay) {
  if (allDay) return "all day";
  let h = d.getHours(); const m = d.getMinutes();
  const ap = h >= 12 ? "p" : "a"; h = h % 12 || 12;
  return m ? `${h}:${String(m).padStart(2, "0")}${ap}` : `${h}${ap}`;
}
const DOW = ["Sun", "Mon", "Tue", "Wed", "Thu", "Fri", "Sat"];
function dayName(d, now) {
  const k = dayDiff(d, now);
  return k === 0 ? "Today" : k === 1 ? "Tmrw" : DOW[d.getDay()];
}
function countdown(d, now) {
  const ms = d - now;
  if (ms < 0) return "overdue";
  const h = ms / 36e5;
  if (h < 1) return `${Math.max(1, Math.round(ms / 6e4))}m`;
  if (h < 24) return `${Math.round(h)}h`;
  return `${dayDiff(d, now)}d`;
}
const code = (feed, i) => (feed.courses[i.course] || {}).code || "";
const color = (feed, i) => (feed.courses[i.course] || {}).color || COLORS.muted;
const clip = (s, n) => (s.length > n ? s.slice(0, Math.max(1, n - 1)).trimEnd() + "…" : s);

/* ------------------------------------------------------------ wallpaper (DrawContext only) */

function drawWallpaper(feed, W, H, bgImage, now = new Date()) {
  const ctx = new DrawContext();
  ctx.size = new Size(W, H);
  ctx.opaque = true;
  ctx.respectScreenScale = false;
  const u = W / 390; // design in iPhone points, scale to pixels

  // Background: photo (dimmed) or navy gradient
  if (bgImage) {
    const s = Math.max(W / bgImage.size.width, H / bgImage.size.height);
    const bw = bgImage.size.width * s, bh = bgImage.size.height * s;
    ctx.drawImageInRect(bgImage, new Rect((W - bw) / 2, (H - bh) / 2, bw, bh));
  } else {
    const steps = 48;
    const a = hex(COLORS.bgTop), b = hex(COLORS.bgBot);
    for (let k = 0; k < steps; k++) {
      const t = k / (steps - 1);
      ctx.setFillColor(new Color(rgbHex(a.map((v, j) => v + (b[j] - v) * t))));
      ctx.fillRect(new Rect(0, (H * k) / steps, W, H / steps + 1));
    }
  }

  const week = pickWeek(feed, now);
  const x0 = 24 * u, x1 = W - 24 * u;
  const top = H * 0.385;          // below clock + lock-screen widget row
  const bottom = H - 120 * u;      // above flashlight / camera buttons

  // Panel behind the list for legibility on photos
  const panel = new Path();
  panel.addRoundedRect(new Rect(x0 - 12 * u, top - 14 * u, x1 - x0 + 24 * u, bottom - top + 14 * u), 22 * u, 22 * u);
  ctx.addPath(panel);
  ctx.setFillColor(new Color("#05070F", bgImage ? 0.62 : 0.35));
  ctx.fillPath();

  let y = top;
  const text = (s, x, yy, w, size, col, bold, align = "left") => {
    ctx.setFont(bold ? Font.boldSystemFont(size * u) : Font.systemFont(size * u));
    ctx.setTextColor(new Color(col));
    if (align === "right") ctx.setTextAlignedRight(); else ctx.setTextAlignedLeft();
    ctx.drawTextInRect(s, new Rect(x, yy, w, size * u * 1.35));
  };

  // Header
  const head = week.total ? `${week.total} due ${week.nextWeek ? "next week" : "this week"}${week.tests ? ` · ${week.tests} test${week.tests > 1 ? "s" : ""}` : ""}` : `Nothing due ${week.nextWeek ? "next week" : "this week"} 🌊`;
  text("▲ DEAD AHEAD", x0, y, 200 * u, 11, COLORS.coral, true);
  text(head, x0, y + 16 * u, x1 - x0, 17, COLORS.ink, true);
  y += 48 * u;

  const ROW = 30 * u, DAYH = 22 * u;
  const rows = [];
  if (week.overdue.length) rows.push({ type: "day", label: "Overdue", warn: true }, ...week.overdue.map((i) => ({ type: "item", i, over: true })));
  for (const d of week.days) rows.push({ type: "day", label: `${dayName(d.day, now)} ${d.day.getDate()}` }, ...d.items.map((i) => ({ type: "item", i })));

  const room = Math.floor((bottom - y - 20 * u) / ROW);
  let shown = 0, used = 0;
  for (const r of rows) {
    const h = r.type === "day" ? DAYH + 6 * u : ROW;
    if (y + h > bottom - 24 * u) break;
    if (r.type === "day") {
      y += 6 * u;
      text(r.label.toUpperCase(), x0, y, 200 * u, 11, r.warn ? COLORS.coral : COLORS.muted, true);
      y += DAYH;
      continue;
    }
    const i = r.i;
    // course colour dot
    ctx.setFillColor(new Color(color(feed, i)));
    ctx.fillEllipse(new Rect(x0, y + 6 * u, 9 * u, 9 * u));
    const c = code(feed, i);
    text(c, x0 + 16 * u, y + 1 * u, 62 * u, 13, color(feed, i), true);
    // TEST pill
    let tx = x0 + 80 * u;
    if (i.test) {
      const pill = new Path();
      pill.addRoundedRect(new Rect(tx, y + 2 * u, 34 * u, 16 * u), 5 * u, 5 * u);
      ctx.addPath(pill); ctx.setFillColor(new Color(COLORS.test)); ctx.fillPath();
      ctx.setTextAlignedCenter();
      ctx.setFont(Font.heavySystemFont(9 * u)); ctx.setTextColor(Color.white());
      ctx.drawTextInRect("TEST", new Rect(tx, y + 4.5 * u, 34 * u, 14 * u));
      tx += 40 * u;
    }
    const timeW = 58 * u;
    const titleW = x1 - timeW - tx - 6 * u;
    const title = clip(i.title + (i.source === "syllabus" ? " 📄" : ""), Math.floor(titleW / (15 * u * 0.53)));
    text(title, tx, y, titleW, 15, r.over ? COLORS.coral : COLORS.ink, i.test || r.over);
    text(r.over ? "late" : fmtTime(i._d, i.all_day), x1 - timeW, y + 1 * u, timeW, 13, r.over ? COLORS.coral : COLORS.muted, false, "right");
    y += ROW;
    shown++;
  }
  const totalItems = rows.filter((r) => r.type === "item").length;
  if (shown < totalItems) text(`+${totalItems - shown} more in the app`, x0, y + 4 * u, 300 * u, 12, COLORS.muted, false);

  const stamp = `updated ${new Date(feed.generated_at).toLocaleTimeString([], { hour: "numeric", minute: "2-digit" })}`;
  text(stamp, x0, bottom - 18 * u, x1 - x0, 10, COLORS.muted, false, "right");
  return ctx.getImage();
}

function hex(h) { const n = parseInt(h.slice(1), 16); return [(n >> 16) & 255, (n >> 8) & 255, n & 255]; }
function rgbHex(a) { return "#" + a.map((v) => Math.round(v).toString(16).padStart(2, "0")).join(""); }

/* ------------------------------------------------------------ widget (lock + home screen) */

function buildWidget(feed, family, siteUrl, now = new Date()) {
  const w = new ListWidget();
  w.url = siteUrl;
  w.refreshAfterDate = new Date(Date.now() + 30 * 60e3);
  const urgent = feed ? pickUrgent(feed, now) : [];

  if (!feed) {
    const t = w.addText("Dead Ahead: open Scriptable to set up");
    t.font = Font.systemFont(12);
    return w;
  }

  // Lock screen: just today, from now on. Never overdue.
  const today = pickToday(feed, now);
  const none = "Nothing due today";

  if (family === "accessoryInline") {
    const n = today[0];
    w.addText(n ? `▲ ${code(feed, n)} ${clip(n.title, 16)} ${fmtTime(n._d, n.all_day)}${today.length > 1 ? ` +${today.length - 1}` : ""}` : none);
    return w;
  }

  if (family === "accessoryCircular") {
    w.addAccessoryWidgetBackground = true;
    const st = w.addStack(); st.layoutVertically(); st.centerAlignContent();
    const n = st.addText(String(today.length)); n.font = Font.boldRoundedSystemFont(22); n.centerAlignText();
    const l = st.addText("today"); l.font = Font.systemFont(9); l.centerAlignText();
    return w;
  }

  if (family === "accessoryRectangular") {
    if (!today.length) {
      const t = w.addText(none); t.font = Font.boldSystemFont(14); t.minimumScaleFactor = 0.7; t.lineLimit = 1;
      return w;
    }
    const head = w.addText(`▲ ${today.length} due today`);
    head.font = Font.boldSystemFont(13); head.lineLimit = 1; head.minimumScaleFactor = 0.7;
    const shown = today.slice(0, 2);
    shown.forEach((i, k) => {
      const more = k === shown.length - 1 && today.length > 2 ? ` +${today.length - 2}` : "";
      const t = w.addText(`${fmtTime(i._d, i.all_day)} ${code(feed, i)} ${i.title}${more}`);
      t.font = Font.systemFont(12); t.lineLimit = 1; t.minimumScaleFactor = 0.75;
    });
    return w;
  }

  // Home-screen sizes
  w.backgroundColor = new Color(COLORS.bgBot);
  const max = family === "large" ? 9 : family === "medium" ? 4 : 3;
  const h = w.addText(`▲ ${urgent.length} due soon`);
  h.font = Font.boldSystemFont(13); h.textColor = new Color(COLORS.coral);
  w.addSpacer(6);
  if (!urgent.length) { const t = w.addText("All clear 🌊"); t.textColor = new Color(COLORS.ink); }
  for (const i of urgent.slice(0, max)) {
    const row = w.addStack(); row.centerAlignContent(); row.spacing = 6;
    const c = row.addText(code(feed, i)); c.font = Font.boldSystemFont(11); c.textColor = new Color(color(feed, i));
    const t = row.addText(i.title); t.font = Font.systemFont(12); t.textColor = new Color(COLORS.ink); t.lineLimit = 1;
    row.addSpacer();
    const d = row.addText(countdown(i._d, now)); d.font = Font.mediumSystemFont(11);
    d.textColor = new Color(i._d < now ? COLORS.coral : i._d - now < 2 * DAY ? COLORS.warn : COLORS.muted);
    w.addSpacer(4);
  }
  w.addSpacer();
  const u = w.addText(`updated ${new Date(feed.generated_at).toLocaleTimeString([], { hour: "numeric", minute: "2-digit" })}`);
  u.font = Font.systemFont(9); u.textColor = new Color(COLORS.muted);
  return w;
}

/* ------------------------------------------------------------ Scriptable plumbing */

const fm = () => FileManager.local();
const cachePath = () => fm().joinPath(fm().documentsDirectory(), "dead-ahead-cache.json");

async function decryptInWebView(blob, pass, pageUrl) {
  // Uses the iPhone's built-in WebCrypto (same code as the web app). WebCrypto only exists on a real https page,
  // so we open the feed URL itself in a hidden WebView and decrypt there.
  const wv = new WebView();
  await wv.loadURL(pageUrl);
  const js = `(async () => {
    try {
      if (!window.crypto || !crypto.subtle) throw new Error("WebCrypto not available (isSecureContext=" + window.isSecureContext + ")");
      const blob = ${JSON.stringify(blob)}, pass = ${JSON.stringify(pass)};
      const b64 = (s) => Uint8Array.from(atob(s), (c) => c.charCodeAt(0));
      const enc = new TextEncoder();
      const base = await crypto.subtle.importKey("raw", enc.encode(pass), "PBKDF2", false, ["deriveKey"]);
      const key = await crypto.subtle.deriveKey({ name: "PBKDF2", hash: "SHA-256", salt: b64(blob.salt), iterations: blob.iter },
        base, { name: "AES-GCM", length: 256 }, false, ["decrypt"]);
      const pt = await crypto.subtle.decrypt({ name: "AES-GCM", iv: b64(blob.iv), additionalData: enc.encode("dead-ahead:v1") }, key, b64(blob.ct));
      window.__deadAhead = new TextDecoder().decode(pt);
    } catch (e) { window.__deadAhead = "ERR:" + e.name + ":" + e.message; }
  })(); "started";`;
  // Start the async work, then poll for the answer (evaluateJavaScript can't return a Promise).
  await wv.evaluateJavaScript(js, false);
  let out = "";
  for (let i = 0; i < 150 && !out; i++) {
    await new Promise((r) => Timer.schedule(200, false, r));
    out = await wv.evaluateJavaScript(`window.__deadAhead || ""`, false);
  }
  if (!out) throw new Error("Unlocking took too long. Try again.");
  if (typeof out !== "string" || out.startsWith("ERR:")) {
    throw new Error(String(out).includes("OperationError") ? "Wrong passcode" : `Decrypt failed: ${out}`);
  }
  return JSON.parse(out);
}

async function getFeed(strict = false) {
  if (!Keychain.contains(KC_URL) || !Keychain.contains(KC_PASS)) return null;
  const site = Keychain.get(KC_URL);
  try {
    const url = `${site.replace(/\/+$/, "")}/feed.enc.json`;
    const req = new Request(`${url}?t=${Date.now()}`);
    req.timeoutInterval = 20;
    let blob;
    try { blob = await req.loadJSON(); } catch (e) { throw new Error(`Couldn't download ${url} (${e.message})`); }
    if (!blob || !blob.ct) throw new Error(`No feed at ${url}. Check the site link.`);
    const feed = await decryptInWebView(blob, Keychain.get(KC_PASS), url);
    fm().writeString(cachePath(), JSON.stringify(feed));
    return feed;
  } catch (e) {
    if (strict) throw e;
    console.warn(`Using cached copy: ${e.message}`);
    if (fm().fileExists(cachePath())) return JSON.parse(fm().readString(cachePath()));
    if (String(e.message).includes("Wrong passcode")) throw e;
    return null;
  }
}

async function setup() {
  const a = new Alert();
  a.title = "Dead Ahead setup";
  a.message = "Paste your Dead Ahead site link and passcode. They're stored in your iPhone Keychain.";
  a.addTextField("https://you.github.io/dead-ahead", Keychain.contains(KC_URL) ? Keychain.get(KC_URL) : "");
  a.addSecureTextField("Passcode", "");
  a.addAction("Save");
  a.addCancelAction("Cancel");
  if ((await a.present()) === -1) return false;
  const site = a.textFieldValue(0).trim(), pass = a.textFieldValue(1);
  if (!/^https:\/\//.test(site) || pass.length < 8) {
    const e = new Alert(); e.title = "Check that again"; e.message = "The link must start with https:// and the passcode needs 8+ characters."; e.addAction("OK"); await e.present();
    return false;
  }
  Keychain.set(KC_URL, site); Keychain.set(KC_PASS, pass);
  try {
    const feed = await getFeed(true);
    const ok = new Alert(); ok.title = "✓ Connected"; ok.message = `${feed.items.length} deadlines loaded.`; ok.addAction("Nice"); await ok.present();
    return true;
  } catch (e) {
    if (String(e.message).includes("Wrong passcode")) Keychain.remove(KC_PASS);
    const bad = new Alert(); bad.title = "Couldn't unlock"; bad.message = e.message; bad.addAction("OK"); await bad.present();
    return false;
  }
}

function backgroundImage() {
  const f = fm(), p = f.joinPath(f.documentsDirectory(), BG_FILE);
  if (f.fileExists(p)) return Image.fromFile(p);
  try { // iCloud is optional: FileManager.iCloud() throws when Scriptable isn't using iCloud Drive
    const ic = FileManager.iCloud(), q = ic.joinPath(ic.documentsDirectory(), BG_FILE);
    if (ic.fileExists(q)) return Image.fromFile(q);
  } catch (e) { /* no iCloud: no custom background */ }
  return null;
}

function wallpaperSize() {
  const r = Device.screenResolution();
  return { W: Math.round(Math.min(r.width, r.height)), H: Math.round(Math.max(r.width, r.height)) };
}

async function main() {
  const param = String(args.shortcutParameter || args.widgetParameter || args.queryParameters?.mode || "").toLowerCase();

  if (config.runsInWidget) {
    const feed = await getFeed().catch(() => null);
    Script.setWidget(buildWidget(feed, config.widgetFamily, Keychain.contains(KC_URL) ? Keychain.get(KC_URL) : null));
    return Script.complete();
  }

  // Run from Shortcuts (or with "wallpaper" parameter) → hand back the wallpaper image
  if (param.includes("wallpaper") || !config.runsInApp) {
    const feed = await getFeed();
    if (!feed) throw new Error("Dead Ahead isn't set up yet. Open the script in Scriptable first.");
    const { W, H } = wallpaperSize();
    const img = drawWallpaper(feed, W, H, backgroundImage());
    // Shortcuts can't receive an Image from Scriptable, so hand back base64 text.
    // The shortcut turns it back into a picture with "Decode Base64" before "Set Wallpaper Photo".
    Script.setShortcutOutput(Data.fromPNG(img).toBase64String());
    return Script.complete();
  }

  // Opened in the Scriptable app: menu
  const m = new Alert();
  m.title = "Dead Ahead ▲";
  m.addAction(Keychain.contains(KC_PASS) ? "Change site / passcode" : "Set up");
  m.addAction("Preview lock-screen widget");
  m.addAction("Preview home-screen widget");
  m.addAction("Preview wallpaper");
  m.addCancelAction("Close");
  const pick = await m.present();
  if (pick === 0) await setup();
  if (pick === 1 || pick === 2 || pick === 3) {
    const feed = await getFeed();
    if (!feed) { await setup(); return Script.complete(); }
    if (pick === 1) await buildWidget(feed, "accessoryRectangular", Keychain.get(KC_URL)).presentAccessoryRectangular();
    if (pick === 2) await buildWidget(feed, "medium", Keychain.get(KC_URL)).presentMedium();
    if (pick === 3) { const { W, H } = wallpaperSize(); QuickLook.present(drawWallpaper(feed, W, H, backgroundImage()), true); }
  }
  Script.complete();
}

if (typeof __DEAD_AHEAD_PREVIEW__ === "undefined") await main();
