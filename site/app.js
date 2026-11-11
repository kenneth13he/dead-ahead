"use strict";
/* Dead Ahead: decrypts feed.enc.json with your passcode and draws the timeline. */

const FEED_URL = "feed.enc.json";
const KEY_PASS = "deadahead.passcode";
const KEY_DONE = "deadahead.done";
const KEY_FILTER = "deadahead.filter";
const KEY_CACHE = "deadahead.cache";
const DAY = 864e5;

const $ = (s) => document.querySelector(s);
const store = {
  get(k) { try { return localStorage.getItem(k); } catch { return null; } },
  set(k, v) { try { localStorage.setItem(k, v); } catch {} },
  del(k) { try { localStorage.removeItem(k); } catch {} },
};

/* ---------- crypto (must match deadahead/crypto.py) ---------- */
const b64 = (s) => Uint8Array.from(atob(s), (c) => c.charCodeAt(0));
async function decrypt(blob, pass) {
  if (blob.v !== 1) throw new Error("Unknown data format. Update the app.");
  const enc = new TextEncoder();
  const base = await crypto.subtle.importKey("raw", enc.encode(pass), "PBKDF2", false, ["deriveKey"]);
  const key = await crypto.subtle.deriveKey(
    { name: "PBKDF2", hash: "SHA-256", salt: b64(blob.salt), iterations: blob.iter },
    base, { name: "AES-GCM", length: 256 }, false, ["decrypt"]);
  const pt = await crypto.subtle.decrypt(
    { name: "AES-GCM", iv: b64(blob.iv), additionalData: enc.encode("dead-ahead:v1") }, key, b64(blob.ct));
  return JSON.parse(new TextDecoder().decode(pt));
}

async function loadFeed(pass) {
  let blob;
  try {
    const r = await fetch(`${FEED_URL}?t=${Date.now()}`, { cache: "no-store" });
    if (!r.ok) throw new Error(r.status);
    blob = await r.json();
    store.set(KEY_CACHE, JSON.stringify(blob));
  } catch {
    const cached = store.get(KEY_CACHE);
    if (!cached) throw new Error("Couldn't load your deadlines. Check your connection.");
    blob = JSON.parse(cached); // offline: last good copy
  }
  try {
    return await decrypt(blob, pass);
  } catch (e) {
    if (e.name === "OperationError") throw new Error("Wrong passcode.");
    throw e;
  }
}

/* ---------- dates ---------- */
const startOfDay = (d) => new Date(d.getFullYear(), d.getMonth(), d.getDate());
const dayDiff = (a, b) => Math.round((startOfDay(a) - startOfDay(b)) / DAY);
const fmtTime = (d) => d.toLocaleTimeString([], { hour: "numeric", minute: "2-digit" });
const fmtDow = (d) => d.toLocaleDateString([], { weekday: "short" });
const fmtShort = (d) => d.toLocaleDateString([], { month: "short", day: "numeric" });

function countdown(due, now) {
  const ms = due - now;
  if (ms < 0) {
    const h = Math.round(-ms / 36e5);
    return h < 24 ? `${h}h overdue` : `${Math.round(h / 24)}d overdue`;
  }
  const h = ms / 36e5;
  if (h < 1) return `${Math.max(1, Math.round(ms / 6e4))} min`;
  if (h < 24) return `${Math.round(h)} hr${Math.round(h) === 1 ? "" : "s"}`;
  const d = dayDiff(due, now);
  return d === 1 ? "tomorrow" : `${d} days`;
}

function ago(iso) {
  const m = Math.round((Date.now() - new Date(iso)) / 6e4);
  if (m < 2) return "just now";
  if (m < 60) return `${m} min ago`;
  const h = Math.round(m / 60);
  return h < 24 ? `${h}h ago` : `${Math.round(h / 24)}d ago`;
}

function weekLabel(d, now) {
  const monday = (x) => { const s = startOfDay(x); s.setDate(s.getDate() - ((s.getDay() + 6) % 7)); return s; };
  const w = Math.round((monday(d) - monday(now)) / (7 * DAY));
  if (w <= 0) return "This week";
  if (w === 1) return "Next week";
  return `Week of ${fmtShort(monday(d))}`;
}

/* ---------- state ---------- */
let feed = null;
let filter = store.get(KEY_FILTER) || "todo";
const localDone = new Set(JSON.parse(store.get(KEY_DONE) || "[]"));
const isDone = (i) => i.done || localDone.has(i.id);

function toggleDone(id) {
  localDone.has(id) ? localDone.delete(id) : localDone.add(id);
  store.set(KEY_DONE, JSON.stringify([...localDone]));
  render();
}

/* ---------- render ---------- */
const esc = (s) => String(s ?? "").replace(/[&<>"']/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]));

function itemHTML(i, now) {
  const c = feed.courses[i.course] || { code: "", color: "#8892A6" };
  const due = new Date(i.due);
  const done = isDone(i);
  const overdue = !done && due < now;
  const soon = !done && !overdue && due - now < 2 * DAY;
  const badges = [
    i.test && `<span class="badge test">Test</span>`,
    overdue && `<span class="badge over">${i.missing ? "Missing" : "Overdue"}</span>`,
    soon && `<span class="badge soon">${countdown(due, now)}</span>`,
    i.source === "syllabus" && `<span class="badge syl">📄 Syllabus</span>`,
  ].filter(Boolean).join("");
  const time = i.all_day ? "All day" : fmtTime(due);
  const tag = i.url ? "a" : "div";
  const href = i.url ? ` href="${esc(i.url)}" target="_blank" rel="noopener"` : "";
  return `<${tag} class="item${done ? " done" : ""}" style="--c:${esc(c.color)}"${href}>
    <span class="bar"></span>
    <span>
      <span class="meta"><span class="code">${esc(c.code)}</span><span>${esc(time)}</span>${badges}</span>
      <div class="t">${esc(i.title)}</div>
      ${i.note || i.weight ? `<div class="note">${esc([i.weight, i.note].filter(Boolean).join(" · "))}</div>` : ""}
    </span>
    <button class="check" data-id="${esc(i.id)}" aria-label="${done ? "Mark not done" : "Mark done"}">✓</button>
  </${tag}>`;
}

function render() {
  const now = new Date();
  const items = feed.items.map((i) => ({ ...i, _d: new Date(i.due) }));
  const open = items.filter((i) => !isDone(i));
  const weekEnd = new Date(startOfDay(now).getTime() + 7 * DAY);

  // Next up: earliest not-done, not-overdue item
  const next = open.find((i) => i._d >= now);
  const nextEl = $("#next");
  if (next) {
    const c = feed.courses[next.course] || {};
    nextEl.style.setProperty("--c", c.color || "");
    nextEl.innerHTML = `<div class="label">Next up · ${esc(c.code || "")}</div>
      <div class="title">${esc(next.title)}</div>
      <div class="muted small">${fmtDow(next._d)} ${fmtShort(next._d)} · ${next.all_day ? "All day" : fmtTime(next._d)}</div>
      <div class="count">${countdown(next._d, now)}</div>`;
  } else {
    nextEl.innerHTML = `<div class="label">Next up</div><div class="title">Nothing due. Enjoy it. 🌊</div>`;
  }

  const thisWeek = open.filter((i) => i._d >= now && i._d < weekEnd);
  const overdue = open.filter((i) => i._d < now);
  $("#stats").innerHTML = [
    [thisWeek.length, "due in 7 days"],
    [thisWeek.filter((i) => i.test).length, "tests in 7 days"],
    [overdue.length, "overdue"],
  ].map(([n, l]) => `<div class="stat"><b>${n}</b><span>${l}</span></div>`).join("");

  document.querySelectorAll(".chip").forEach((b) => b.classList.toggle("active", b.dataset.filter === filter));

  let shown = items;
  if (filter === "todo") shown = items.filter((i) => !isDone(i));
  if (filter === "tests") shown = items.filter((i) => i.test);
  // Hide old finished stuff; keep overdue-but-not-done visible
  shown = shown.filter((i) => i._d >= startOfDay(now) || !isDone(i));

  const groups = new Map();
  for (const i of shown) {
    const key = i._d < startOfDay(now) ? "overdue" : startOfDay(i._d).toISOString();
    if (!groups.has(key)) groups.set(key, []);
    groups.get(key).push(i);
  }
  const todayKey = startOfDay(now).toISOString();
  if (!groups.has(todayKey)) groups.set(todayKey, []);

  const keys = [...groups.keys()].sort((a, b) => (a === "overdue" ? -1 : b === "overdue" ? 1 : a.localeCompare(b)));
  let html = "";
  let lastWeek = "";
  for (const k of keys) {
    const list = groups.get(k);
    if (k === "overdue") {
      html += `<div class="week" style="color:var(--accent)">Overdue</div>`;
      html += `<div class="day"><div class="day-label"><div class="dow">⚠︎</div></div><div class="day-items">${list.map((i) => itemHTML(i, now)).join("")}</div></div>`;
      continue;
    }
    const d = new Date(k);
    const wl = weekLabel(d, now);
    if (wl !== lastWeek) { html += `<div class="week">${wl}</div>`; lastWeek = wl; }
    const diff = dayDiff(d, now);
    const dow = diff === 0 ? "Today" : diff === 1 ? "Tmrw" : fmtDow(d);
    html += `<div class="day${diff === 0 ? " today" : ""}">
      <div class="day-label"><div class="dow">${dow}</div><div class="dom">${d.getDate()}</div></div>
      <div class="day-items">${list.length ? list.map((i) => itemHTML(i, now)).join("") : `<div class="empty-day">Nothing due today ✨</div>`}</div>
    </div>`;
  }
  $("#timeline").innerHTML = html;

  const stale = Date.now() - new Date(feed.generated_at) > 12 * 36e5;
  $("#updated").innerHTML = `Updated ${ago(feed.generated_at)}` + (stale ? " · ⚠︎ not refreshing" : "");
  $("#school").textContent = (feed.school || "").replace(/^https?:\/\//, "");
}

/* ---------- flow ---------- */
async function unlock(pass, remember) {
  feed = await loadFeed(pass);
  if (remember) store.set(KEY_PASS, pass);
  $("#lock").hidden = true;
  $("#app").hidden = false;
  render();
}

function showLock(msg = "") {
  $("#app").hidden = true;
  $("#lock").hidden = false;
  $("#lock-error").textContent = msg;
  $("#passcode").value = "";
  setTimeout(() => $("#passcode").focus(), 50);
}

$("#lock-form").addEventListener("submit", async (e) => {
  e.preventDefault();
  const btn = $("#unlock-btn");
  btn.disabled = true; btn.textContent = "Unlocking…";
  try { await unlock($("#passcode").value, $("#remember").checked); }
  catch (err) { $("#lock-error").textContent = err.message; }
  finally { btn.disabled = false; btn.textContent = "Unlock"; }
});

$("#refresh").addEventListener("click", async () => {
  const pass = store.get(KEY_PASS);
  if (!pass) return location.reload();
  $("#refresh").classList.add("spin");
  try { feed = await loadFeed(pass); render(); } catch {}
  $("#refresh").classList.remove("spin");
});

$("#lock-now").addEventListener("click", () => { store.del(KEY_PASS); feed = null; showLock(); });

document.querySelector(".chips").addEventListener("click", (e) => {
  const b = e.target.closest(".chip");
  if (!b) return;
  filter = b.dataset.filter; store.set(KEY_FILTER, filter); render();
});

$("#timeline").addEventListener("click", (e) => {
  const b = e.target.closest(".check");
  if (!b) return;
  e.preventDefault(); e.stopPropagation();
  toggleDone(b.dataset.id);
});

// Refresh when you come back to the app; re-render every minute so countdowns tick.
document.addEventListener("visibilitychange", () => { if (!document.hidden && feed) $("#refresh").click(); });
setInterval(() => feed && render(), 60_000);

if ("serviceWorker" in navigator) navigator.serviceWorker.register("sw.js").catch(() => {});

(async () => {
  const saved = store.get(KEY_PASS);
  if (!saved) return showLock();
  try { await unlock(saved, true); } catch (e) { store.del(KEY_PASS); showLock(e.message); }
})();
