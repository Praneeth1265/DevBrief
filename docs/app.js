/* DevBrief — installable reader app. Vanilla JS, no build step. */
"use strict";

const SECTIONS = [
  ["headlines", "Headlines"], ["deep_read", "Deep reads"], ["career", "Careers & hiring"], ["security", "Security watch"], ["release_radar", "Release radar"],
];
const $ = (id) => document.getElementById(id);
const $view = $("view");
const icon = (name) => `<svg class="i" aria-hidden="true"><use href="#i-${name}"/></svg>`;

/* ── helpers ──────────────────────────────────────────────────── */
const esc = (s) => String(s ?? "").replace(/[&<>"']/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]));
const safeUrl = (u) => (/^https?:\/\//i.test(u || "") ? u : "#");
const isoOf = (dt) => `${dt.getFullYear()}-${String(dt.getMonth() + 1).padStart(2, "0")}-${String(dt.getDate()).padStart(2, "0")}`;
const todayISO = () => isoOf(new Date());
const fmtDay = (iso) => new Date(iso + "T00:00:00").toLocaleDateString("en-IN", { weekday: "long", day: "numeric", month: "long" });
const shortDay = (iso) => new Date(iso + "T00:00:00").toLocaleDateString("en-IN", { weekday: "short", day: "numeric", month: "short" });
const isIOS = () => /iphone|ipad|ipod/i.test(navigator.userAgent);
const isInstalled = () => matchMedia("(display-mode: standalone)").matches || navigator.standalone;

function toast(msg) {
  const t = $("toast"); t.textContent = msg; t.classList.add("show");
  clearTimeout(toast.t); toast.t = setTimeout(() => t.classList.remove("show"), 1800);
}

/* ── local storage (this phone only) ──────────────────────────── */
const store = {
  get(k, d) { try { return JSON.parse(localStorage.getItem("db:" + k)) ?? d; } catch { return d; } },
  set(k, v) { try { localStorage.setItem("db:" + k, JSON.stringify(v)); } catch { /* private mode */ } },
};
const prefs = () => store.get("prefs", { theme: "dark", size: 1 });
const isRead = (key) => key in store.get("read", {});
function markRead(key) { const r = store.get("read", {}); if (!(key in r)) { r[key] = Date.now(); store.set("read", r); } }
const isSaved = (key) => key in store.get("saved", {});
function toggleSave(item, name) {
  const s = store.get("saved", {});
  if (s[item.key]) { delete s[item.key]; toast("Removed from saved"); }
  else { s[item.key] = { ...item, _from: name, _at: Date.now() }; toast("Saved for later"); }
  store.set("saved", s);
  return !!s[item.key];
}
const getNote = (key) => store.get("notes", {})[key] || "";
function setNote(key, text, item, name) {
  const n = store.get("notes", {}); if (text.trim()) n[key] = text; else delete n[key]; store.set("notes", n);
  if (text.trim() && item && !isSaved(key)) { const s = store.get("saved", {}); s[key] = { ...item, _from: name, _at: Date.now() }; store.set("saved", s); }
}
function bumpStreak() {
  const s = store.get("streak", { last: "", count: 0 }); const t = todayISO();
  if (s.last !== t) { s.count = s.last === isoOf(new Date(Date.now() - 864e5)) ? s.count + 1 : 1; s.last = t; store.set("streak", s); }
  if (s.count >= 2) { const el = $("streak"); el.hidden = false; el.innerHTML = `${icon("flame")}${s.count}`; el.title = `${s.count}-day reading streak`; }
}
function applyPrefs() {
  const p = prefs();
  const theme = p.theme === "system" ? (matchMedia("(prefers-color-scheme: light)").matches ? "light" : "dark") : p.theme;
  document.documentElement.dataset.theme = theme;
  document.documentElement.style.setProperty("--fs", p.size);
  document.querySelector('meta[name="theme-color"]').content = theme === "light" ? "#F5F6FA" : "#0E1220";
  // The glow follows the clock: violet pre-dawn → apricot morning → rose evening → indigo night.
  const h = new Date().getHours();
  const [a, b] = h < 6 ? ["110,96,230", "190,120,200"] : h < 11 ? ["140,123,255", "255,179,138"]
    : h < 17 ? ["120,150,255", "255,206,150"] : h < 20 ? ["200,110,190", "255,150,120"] : ["90,90,210", "150,110,230"];
  document.documentElement.style.setProperty("--glow-a", a);
  document.documentElement.style.setProperty("--glow-b", b);
}

/* ── data ─────────────────────────────────────────────────────── */
const cache = {};
async function getJSON(path, fresh = false) {
  if (!fresh && cache[path]) return cache[path];
  const r = await fetch(path, { cache: fresh ? "no-cache" : "default" });
  if (!r.ok) throw new Error(`${path} returned ${r.status}`);
  return (cache[path] = await r.json());
}
const getIndex = (fresh) => getJSON("api/index.json", fresh);
const getDigest = (name) => getJSON(`api/digests/${encodeURIComponent(name)}.json`);

/* ── building blocks ──────────────────────────────────────────── */
function metaLine(it, extra = "") {
  const bits = [];
  if (it.read_minutes) bits.push(`${it.read_minutes} min read`);
  if (it.points) bits.push(`${it.points} points`);
  (it.tags || []).slice(0, 2).forEach((t) => bits.push(esc(t)));
  return `<div class="meta">${bits.map((b) => `<span>${b}</span>`).join("")}${extra}</div>`;
}

function storyRow(it, name) {
  const read = isRead(it.key) ? " read" : "";
  return `<a class="story${read}" href="#/a/${encodeURIComponent(name)}/${it.key}">
    <div class="src"><i class="dot"></i>${esc(it.source)}</div>
    <h3>${esc(it.title)}</h3>
    <p>${esc(it.one_liner)}</p>
    ${metaLine(it, isSaved(it.key) ? `<span class="bm">Saved</span>` : "")}
  </a>`;
}

function leadStory(it, name) {
  return `<a class="lead-story${isRead(it.key) ? " read" : ""}" href="#/a/${encodeURIComponent(name)}/${it.key}">
    <div class="tag">Must-know today</div>
    <h3>${esc(it.title)}</h3>
    <p>${esc(it.one_liner)}</p>
    ${it.why_read ? `<div class="worth">${esc(it.why_read)}</div>` : ""}
    ${metaLine({ ...it, tags: [] }, `<span>${esc(it.source)}</span>`)}
  </a>`;
}

function angleCard(c, withLink = true) {
  if (!c || !c.name) return "";
  return `<section class="angle">
    <div class="k">Interview angle</div>
    <h3>${esc(c.name)}</h3>
    <p>${esc(c.explanation)}</p>
    ${c.interview_question ? `<div class="q">“${esc(c.interview_question)}”</div>` : ""}
    ${c.related_url ? `<a class="from" href="${safeUrl(c.related_url)}" target="_blank" rel="noopener">Seen in: ${esc(c.related_title)}</a>` : ""}
    ${withLink ? `<br><a class="from" href="#/learn">Practise with flashcards</a>` : ""}
  </section>`;
}

function installBanner() {
  if (isInstalled() || store.get("hideInstall", false)) return "";
  const msg = isIOS() ? "Add to your Home Screen: tap <b>Share</b>, then <b>Add to Home Screen</b>." : "<b>Install DevBrief</b> to get it on your home screen.";
  const btn = !isIOS() && deferredInstall ? `<button class="btn" id="installNow">Install</button>` : "";
  return `<div class="banner"><div class="grow">${msg}</div>${btn}<button class="ibtn" id="hideInstall" aria-label="Dismiss">✕</button></div>`;
}

/* ── views ────────────────────────────────────────────────────── */
function renderDigest(d, mode) {
  const items = d.items || [];
  const done = items.filter((i) => isRead(i.key)).length;
  const h = new Date().getHours();
  const greet = mode === "today" ? (h < 12 ? "Good morning" : h < 17 ? "Good afternoon" : "Good evening")
    : mode === "latest" ? `Latest brief, ${shortDay(d.date)}` : d.weekly ? "Week in review" : "From the archive";
  const top = items.find((i) => i.section === "top_story");

  let html = (mode !== "archive" ? installBanner() : "") + `
    <div class="greet">${greet}</div>
    <h1 class="title">${esc(d.weekly ? fmtDay(d.date).split(",")[0] + "’s recap" : fmtDay(d.date))}</h1>
    ${d.tldr ? `<p class="tldr">${esc(d.tldr)}</p>` : ""}
    ${items.length && "speechSynthesis" in window ? `<button class="listen" id="listenBtn" aria-pressed="false">${icon("play")}<span>Listen to this brief</span><small>${Math.max(1, Math.round(items.length * 0.4))} min</small></button>` : ""}
    ${items.length ? `<div class="progress"><div class="track"><i style="width:${(done / items.length) * 100}%"></i></div>${done} of ${items.length} read</div>` : ""}
    ${top ? leadStory(top, d.name) : ""}`;

  for (const [key, label] of SECTIONS) {
    const sec = items.filter((i) => i.section === key);
    if (!sec.length) continue;
    html += `<h2 class="sec${key === "security" ? " alert" : ""}">${label}<span class="n">${sec.length}</span></h2>` + sec.map((i) => storyRow(i, d.name)).join("");
  }
  if (!items.length) html += `<div class="empty"><h2>A quiet one</h2><p>Nothing cleared your bar today. Enjoy the extra ten minutes.</p></div>`;
  if ((d.quiz || []).length) {
    const best = store.get("quiz", {})[d.name];
    html += `<a class="quiz-card" href="#/quiz/${encodeURIComponent(d.name)}"><div class="grow"><div class="k">Today’s quiz</div>
      <b>${best ? `You scored ${best.score} of ${best.total}. Try again?` : `${d.quiz.length} quick questions on today’s stories`}</b></div>${icon("chev")}</a>`;
  }
  html += angleCard(d.concept);
  if ((d.glossary || []).length) {
    html += `<h2 class="sec">Jargon in today’s brief</h2><div class="terms">${d.glossary.map((g) => `<div><b>${esc(g.term)}</b>${esc(g.meaning)}</div>`).join("")}</div>`;
  }
  if (items.length && done === items.length) html += `<p class="caught">You’re all caught up. See you tomorrow.</p>`;
  return html;
}

async function viewToday() {
  const idx = await getIndex();
  if (!idx.length) return `<div class="empty"><h2>Your first brief is on its way</h2><p>It lands here tomorrow morning at about 6:30.</p></div>`;
  const latest = idx.find((e) => !e.weekly) || idx[0];
  const weekly = idx.find((e) => e.weekly && e.date === todayISO());
  const d = await getDigest(latest.name); currentToday = d;
  const wk = weekly ? `<a class="banner" href="#/d/${encodeURIComponent(weekly.name)}"><div class="grow"><b>Your week in review is ready.</b> The big themes, plus what to study this weekend.</div></a>` : "";
  return wk + renderDigest(d, latest.date === todayISO() ? "today" : "latest");
}

async function viewDigest(name) { return renderDigest(await getDigest(name), "archive"); }

async function viewArticle(name, key) {
  let d = null, it = null;
  try { d = await getDigest(name); it = d.items.find((i) => i.key === key); } catch { /* offline */ }
  if (!it) it = store.get("saved", {})[key];
  if (!it) return `<div class="empty"><h2>Not available offline</h2><p>Connect to the internet and open this story again.</p></div>`;
  markRead(key);
  const items = d ? d.items : [];
  const next = items[items.findIndex((i) => i.key === key) + 1];
  const when = it.published ? new Date(it.published).toLocaleString("en-IN", { day: "numeric", month: "short", hour: "numeric", minute: "2-digit" }) : "";
  const angle = d && d.concept && d.concept.related_url === it.url ? angleCard(d.concept) : "";
  return `<article class="reader">
    <div class="src">${esc(it.source)}</div>
    <h1>${esc(it.title)}</h1>
    ${metaLine({ ...it, tags: [] }, when ? `<span>${esc(when)}</span>` : "")}
    <div class="body">${esc(it.one_liner)}</div>
    ${it.why_read ? `<div class="worth-block"><div class="k">Why it’s worth your time</div><div>${esc(it.why_read)}</div></div>` : ""}
    ${(it.takeaways || []).length ? `<div class="points"><div class="k">Key points</div><ul>${it.takeaways.map((t) => `<li>${esc(t)}</li>`).join("")}</ul></div>` : ""}
    ${it.context ? `<div class="context"><div class="k">Background</div><p>${esc(it.context)}</p></div>` : ""}
    ${(it.tags || []).length ? `<div class="chips">${it.tags.map((t) => `<a class="chip" href="#/t/${encodeURIComponent(t)}">${esc(t)}</a>`).join("")}</div>` : ""}
    <div class="cta-row">
      <a class="btn primary" href="${safeUrl(it.url)}" target="_blank" rel="noopener">Read the article ${icon("open")}</a>
      <button class="btn round ${isSaved(key) ? "on" : ""}" id="saveBtn" aria-label="${isSaved(key) ? "Remove from saved" : "Save for later"}">${icon("saved")}</button>
      <button class="btn round" id="shareBtn" aria-label="Share">${icon("share")}</button>
    </div>
    ${it.comments_url && it.comments_url !== it.url ? `<a class="btn wide" href="${safeUrl(it.comments_url)}" target="_blank" rel="noopener">${icon("chat")} Read the discussion</a>` : ""}
    <div class="note"><label for="noteBox">Your note</label><textarea id="noteBox" rows="2" placeholder="Jot down what you want to remember or try">${esc(getNote(key))}</textarea></div>
    ${angle}
    ${next ? `<div class="upnext"><h2 class="sec">Up next</h2>${storyRow(next, name)}</div>` : ""}
  </article>`;
}

function bindArticle(name, key) {
  const it = () => (cache[`api/digests/${encodeURIComponent(name)}.json`]?.items || []).find((i) => i.key === key) || store.get("saved", {})[key];
  $("saveBtn")?.addEventListener("click", (e) => {
    const on = toggleSave(it(), name);
    e.currentTarget.classList.toggle("on", on);
    e.currentTarget.setAttribute("aria-label", on ? "Remove from saved" : "Save for later");
  });
  let t; $("noteBox")?.addEventListener("input", (e) => { clearTimeout(t); t = setTimeout(() => { setNote(key, e.target.value, it(), name); toast("Note saved"); }, 700); });
  $("shareBtn")?.addEventListener("click", async () => {
    const i = it();
    if (navigator.share) { try { await navigator.share({ title: i.title, text: i.one_liner, url: i.url }); } catch { } }
    else { try { await navigator.clipboard.writeText(i.url); toast("Link copied"); } catch { } }
  });
}

const archiveRows = (idx) => idx.map((e) => `<a class="row" href="#/d/${encodeURIComponent(e.name)}">
  <div class="when"><span class="${e.weekly ? "wk" : ""}">${e.weekly ? "Week in review" : esc(shortDay(e.date))}</span><span>${e.count} stories</span></div>
  <b>${esc(e.tldr || e.top || "Quiet day")}</b></a>`).join("") || `<div class="empty"><h2>No matches</h2><p>Try a different word.</p></div>`;

let exploreTab = "topics";
async function viewArchive() {
  const seg = `<div class="seg">${[["topics", "Topics"], ["briefs", "Past briefs"]].map(([t, l]) => `<button data-ex="${t}" class="${t === exploreTab ? "on" : ""}">${l}</button>`).join("")}</div>`;
  if (exploreTab === "briefs") {
    const idx = await getIndex();
    return `<h1 class="title sm">Explore</h1>${seg}<input class="search" id="q" type="search" placeholder="Search past briefs" autocomplete="off" aria-label="Search past briefs"><div id="list">${archiveRows(idx)}</div>`;
  }
  let T = { trending: [], topics: [] };
  try { T = await getJSON("api/topics.json"); } catch { }
  const trend = T.trending.length ? `<h2 class="sec">Trending this week</h2><div class="trend">${T.trending.map((t) => {
      const delta = t.this_week - t.last_week;
      return `<a href="#/t/${encodeURIComponent(t.tag)}"><b>${esc(t.tag)}</b><span>${t.this_week} ${t.this_week === 1 ? "story" : "stories"}</span><em>${delta > 0 ? `+${delta}` : "steady"}</em></a>`;
    }).join("")}</div>` : "";
  const all = T.topics.length ? `<h2 class="sec">All topics</h2><div class="chips big">${T.topics.map((t) => `<a class="chip" href="#/t/${encodeURIComponent(t.tag)}">${esc(t.tag)} <span>${t.count}</span></a>`).join("")}</div>`
    : `<div class="empty"><h2>Topics build up over time</h2><p>Each story is tagged, so after a few days you can follow a topic across briefs.</p></div>`;
  return `<h1 class="title sm">Explore</h1>${seg}${trend}${all}`;
}

async function viewTopic(tag) {
  let T = { topics: [] };
  try { T = await getJSON("api/topics.json"); } catch { }
  const t = T.topics.find((x) => x.tag === tag);
  if (!t) return `<div class="empty"><h2>No stories on “${esc(tag)}” yet</h2><p>They’ll show up here as briefs arrive.</p></div>`;
  return `<div class="greet" style="margin-top:20px">Topic</div><h1 class="title sm" style="margin-top:2px">${esc(tag)}</h1>
    <p class="tldr" style="font-size:16px">${t.count} ${t.count === 1 ? "story" : "stories"} across your briefs, newest first.</p>` +
    t.stories.map((x) => storyRow({ ...x, tags: [] }, x.name).replace('<div class="meta">', `<div class="meta"><span>${esc(shortDay(x.date))}</span>`)).join("");
}

/* ── quiz ── */
async function viewQuiz(name) {
  const d = await getDigest(name);
  if (!(d.quiz || []).length) return `<div class="empty"><h2>No quiz for this brief</h2></div>`;
  return `<div class="greet" style="margin-top:20px">${esc(fmtDay(d.date))}</div><h1 class="title sm" style="margin-top:2px">Today’s quiz</h1><div id="quizBox"></div>`;
}
function bindQuiz(name) {
  const d = cache[`api/digests/${encodeURIComponent(name)}.json`]; const qs = d.quiz;
  let i = 0, score = 0;
  const box = $("quizBox");
  const show = () => {
    if (i >= qs.length) {
      const all = store.get("quiz", {}); const prev = all[name];
      if (!prev || score >= prev.score) { all[name] = { score, total: qs.length, at: Date.now() }; store.set("quiz", all); }
      box.innerHTML = `<div class="qdone"><div class="big">${score}<span>/${qs.length}</span></div><p>${score === qs.length ? "Perfect. You really read the brief." : score ? "Nice work. Review the ones you missed in the stories." : "Tough one. The stories have the answers."}</p>
        <div class="cta-row"><button class="btn" id="again">Try again</button><a class="btn primary" href="#/">Back to today</a></div></div>`;
      $("again").onclick = () => { i = 0; score = 0; show(); };
      return;
    }
    const q = qs[i];
    box.innerHTML = `<div class="qstep">Question ${i + 1} of ${qs.length}</div><div class="track" style="margin:10px 0 22px"><i style="width:${(i / qs.length) * 100}%"></i></div>
      <h2 class="qq">${esc(q.question)}</h2><div class="opts-list">${q.options.map((o, n) => `<button class="opt" data-n="${n}">${esc(o)}</button>`).join("")}</div><div id="qfb"></div>`;
    box.querySelectorAll(".opt").forEach((b) => b.addEventListener("click", () => {
      const n = Number(b.dataset.n), right = n === q.answer;
      if (right) score++;
      box.querySelectorAll(".opt").forEach((x) => { x.disabled = true; const k = Number(x.dataset.n);
        if (k === q.answer) x.classList.add("right"); else if (k === n) x.classList.add("wrong"); });
      $("qfb").innerHTML = `<div class="qexp"><b>${right ? "Correct." : "Not quite."}</b> ${esc(q.explanation)}
        ${q.item_key ? `<a href="#/a/${encodeURIComponent(name)}/${q.item_key}">Read the story</a>` : ""}</div>
        <button class="btn primary wide" id="qnext" style="margin-top:16px">${i + 1 < qs.length ? "Next question" : "See your score"}</button>`;
      $("qnext").onclick = () => { i++; show(); };
    }));
  };
  show();
}

/* ── listen mode (on-device text-to-speech) ── */
function bindListen(d) {
  const btn = $("listenBtn"); if (!btn) return;
  const label = btn.querySelector("span");
  btn.addEventListener("click", () => {
    if (speechSynthesis.speaking) { speechSynthesis.cancel(); return; }
    const parts = [`Your DevBrief for ${fmtDay(d.date)}.`, d.tldr];
    for (const [key, sec] of [["top_story", "Must know"], ...SECTIONS]) {
      const its = d.items.filter((x) => x.section === key); if (!its.length) continue;
      parts.push(sec + ".");
      its.forEach((x) => parts.push(`${x.title}. ${x.one_liner} ${x.why_read ? "Why it matters: " + x.why_read : ""}`));
    }
    if (d.concept && d.concept.name) parts.push(`Today's interview angle: ${d.concept.name}. ${d.concept.explanation}`);
    const voices = speechSynthesis.getVoices();
    const voice = voices.find((v) => /en-IN/i.test(v.lang)) || voices.find((v) => /^en/i.test(v.lang));
    const utters = parts.filter(Boolean).map((t) => { const u = new SpeechSynthesisUtterance(t); u.rate = 1.02; if (voice) u.voice = voice; return u; });
    utters[utters.length - 1].onend = () => { btn.setAttribute("aria-pressed", "false"); label.textContent = "Listen to this brief"; btn.classList.remove("on"); };
    utters.forEach((u) => speechSynthesis.speak(u));
    btn.setAttribute("aria-pressed", "true"); label.textContent = "Playing. Tap to stop"; btn.classList.add("on");
  });
}

function viewSaved() {
  const s = Object.values(store.get("saved", {})).sort((a, b) => b._at - a._at);
  if (!s.length) return `<h1 class="title sm">Saved</h1><div class="empty"><h2>Nothing saved yet</h2><p>Tap the bookmark on any story to keep it here, even offline.</p></div>`;
  return `<h1 class="title sm">Saved</h1>` + s.map((i) => storyRow(i, i._from) + (getNote(i.key) ? `<div class="saved-note">${esc(getNote(i.key))}</div>` : "")).join("");
}

let learnTab = "flashcards";
async function viewLearn() {
  let L = { concepts: [], glossary: [] };
  try { L = await getJSON("api/learn.json"); } catch { }
  const tabs = [["flashcards", "Flashcards"], ["concepts", "Concepts"], ["glossary", "Glossary"]];
  const seg = `<div class="seg" role="tablist">${tabs.map(([t, l]) => `<button role="tab" aria-selected="${t === learnTab}" data-seg="${t}" class="${t === learnTab ? "on" : ""}">${l}</button>`).join("")}</div>`;
  let body = "";
  if (learnTab === "concepts") body = L.concepts.map((c) => angleCard(c, false)).join("") || `<div class="empty"><h2>No concepts yet</h2><p>One new interview concept arrives with every brief.</p></div>`;
  if (learnTab === "glossary") body = L.glossary.length ? `<div class="terms">${L.glossary.map((g) => `<div><b>${esc(g.term)}</b>${esc(g.meaning)}</div>`).join("")}</div>` : `<div class="empty"><h2>No terms yet</h2><p>New jargon from each brief collects here.</p></div>`;
  if (learnTab === "flashcards") body = `<div class="flash" id="flash" tabindex="0" role="button" aria-label="Flashcard"></div><div class="deckcount" id="deckcount"></div>`;
  return `<h1 class="title sm">Learn</h1>${seg}${body}`;
}
function bindLearn() {
  document.querySelectorAll("[data-seg]").forEach((b) => b.addEventListener("click", () => { learnTab = b.dataset.seg; route(); }));
  const box = $("flash"); if (!box) return;
  const L = cache["api/learn.json"] || { concepts: [], glossary: [] };
  const deck = [...L.glossary.map((g) => ({ q: g.term, a: g.meaning })),
    ...L.concepts.flatMap((c) => [{ q: c.name, a: c.explanation }, c.interview_question && { q: c.interview_question, a: `${c.name}. ${c.explanation}` }].filter(Boolean))];
  if (!deck.length) { box.innerHTML = `<div class="front">Your deck is empty</div><div class="back">Cards build up from each day’s concept and jargon.</div>`; return; }
  $("deckcount").textContent = `${deck.length} cards in your deck`;
  let card, shown, last = -1;
  const draw = () => {
    let n; do { n = Math.floor(Math.random() * deck.length); } while (deck.length > 1 && n === last);
    last = n; card = deck[n]; shown = false;
    box.innerHTML = `<div class="front">${esc(card.q)}</div><div class="hint">Tap to reveal</div>`;
  };
  const flip = () => { if (shown) return draw(); shown = true;
    box.innerHTML = `<div class="front">${esc(card.q)}</div><div class="back">${esc(card.a)}</div><div class="hint">Tap for the next card</div>`; };
  box.addEventListener("click", flip);
  box.addEventListener("keydown", (e) => { if (e.key === "Enter" || e.key === " ") { e.preventDefault(); flip(); } });
  draw();
}

/* ── settings + notifications ─────────────────────────────────── */
async function viewSettings() {
  const p = prefs();
  const perm = "Notification" in window ? Notification.permission : "unsupported";
  const status = { granted: ["On", "status-ok"], denied: ["Blocked in your browser settings", "status-bad"], unsupported: ["Not supported here", "status-bad"], default: ["Off", ""] }[perm];
  const seg = (k, opts) => `<div class="seg">${opts.map(([v, l]) => `<button data-pref="${k}" data-val="${v}" class="${p[k] == v ? "on" : ""}">${l}</button>`).join("")}</div>`;
  const read = Object.values(store.get("read", {}));
  const weekAgo = Date.now() - 7 * 864e5;
  const quizzes = Object.values(store.get("quiz", {}));
  const acc = quizzes.length ? Math.round((quizzes.reduce((a, q) => a + q.score, 0) / quizzes.reduce((a, q) => a + q.total, 0)) * 100) : 0;
  const stat = (n, l) => `<div><b>${n}</b><span>${l}</span></div>`;
  return `<h1 class="title sm">Settings</h1>
    <div class="group"><h2>Your progress</h2><div class="stats">
      ${stat(read.filter((t) => t > weekAgo).length, "read this week")}${stat(store.get("streak", { count: 0 }).count, "day streak")}
      ${stat(quizzes.length ? acc + "%" : "–", "quiz accuracy")}${stat(Object.keys(store.get("saved", {})).length, "saved")}</div></div>
    <div class="group"><h2>Morning notification</h2><div class="panel">
      <div class="line">Status<span class="${status[1]}">${status[0]}</span></div>
      ${isIOS() && !isInstalled() ? `<p>On iPhone, add DevBrief to your Home Screen first (Share, then Add to Home Screen). Open it from there and come back to this page.</p>` : ""}
      <button class="btn primary wide" id="enablePush" ${perm === "unsupported" ? "disabled" : ""}>${perm === "granted" ? "Show this phone’s code" : "Turn on notifications"}</button>
      <div id="pushOut"></div>
    </div></div>
    <div class="group"><h2>Theme</h2><div class="panel" style="padding:12px">${seg("theme", [["dark", "Dark"], ["light", "Light"], ["system", "System"]])}</div></div>
    <div class="group"><h2>Text size</h2><div class="panel" style="padding:12px">${seg("size", [[0.92, "Small"], [1, "Default"], [1.1, "Large"], [1.22, "Larger"]])}</div></div>
    <div class="group"><h2>On this phone</h2><div class="panel">
      <div class="line">Read markers<button class="btn" id="clearRead" style="height:38px;margin:0;font-size:14px">Reset</button></div>
    </div></div>
    <p class="foot">Topics and sources are set in config.yaml in your GitHub repo.</p>`;
}

const b64ToBytes = (b64) => { const p = "=".repeat((4 - (b64.length % 4)) % 4); const raw = atob((b64 + p).replace(/-/g, "+").replace(/_/g, "/")); return Uint8Array.from(raw, (c) => c.charCodeAt(0)); };

async function enablePush() {
  const out = $("pushOut");
  try {
    const cfg = await getJSON("api/config.json", true).catch(() => ({}));
    if (!cfg.vapidPublicKey) { out.innerHTML = `<p>Notifications aren’t set up on the server yet. Add the VAPID_PUBLIC_KEY and VAPID_PRIVATE_KEY secrets, run the workflow once, then try again.</p>`; return; }
    if ((await Notification.requestPermission()) !== "granted") { out.innerHTML = `<p>Notifications are off. Allow them for this site in your browser settings, then try again.</p>`; return; }
    const reg = await navigator.serviceWorker.ready;
    const sub = (await reg.pushManager.getSubscription()) || await reg.pushManager.subscribe({ userVisibleOnly: true, applicationServerKey: b64ToBytes(cfg.vapidPublicKey) });
    const code = JSON.stringify(sub);
    out.innerHTML = `<p>One last step links this phone to your daily brief:</p>
      <ol><li>Copy the code below.</li><li>In your GitHub repo, add it as a secret named WEBPUSH_SUBSCRIPTION.</li><li>Run the workflow with <i>test-delivery</i>. A test notification arrives here.</li></ol>
      <textarea readonly id="subCode" aria-label="This phone's notification code">${esc(code)}</textarea>
      <button class="btn wide" id="copySub">Copy code</button>`;
    $("copySub").onclick = async () => { try { await navigator.clipboard.writeText(code); toast("Code copied"); } catch { $("subCode").select(); } };
  } catch (e) { out.innerHTML = `<p>Couldn’t turn on notifications: ${esc(e.message)}</p>`; }
}

function bindSettings() {
  $("enablePush")?.addEventListener("click", enablePush);
  document.querySelectorAll("[data-pref]").forEach((b) => b.addEventListener("click", () => {
    const p = prefs(); p[b.dataset.pref] = b.dataset.pref === "size" ? Number(b.dataset.val) : b.dataset.val;
    store.set("prefs", p); applyPrefs(); route();
  }));
  $("clearRead")?.addEventListener("click", () => { store.set("read", {}); toast("Read markers reset"); });
}

/* ── router ───────────────────────────────────────────────────── */
let deferredInstall = null;
let currentToday = null;
const TITLES = { a: "", d: "Brief", t: "Topic", quiz: "Quiz", archive: "Explore", saved: "Saved", learn: "Learn", settings: "Settings" };

async function route() {
  const [r = "", a, b] = location.hash.replace(/^#\/?/, "").split("/").map(decodeURIComponent);
  if (r !== "") try { speechSynthesis.cancel(); } catch { }
  const tab = { "": "today", d: "today", a: "today", quiz: "today", t: "archive", archive: "archive", saved: "saved", learn: "learn" }[r] || "";
  document.querySelectorAll("#tabbar a").forEach((el) => {
    const on = el.dataset.tab === tab; el.classList.toggle("on", on);
    on ? el.setAttribute("aria-current", "page") : el.removeAttribute("aria-current");
  });
  const sub = ["a", "d", "t", "quiz", "settings"].includes(r);
  $("backBtn").hidden = !sub;
  $("wordmark").hidden = sub;
  $("barTitle").hidden = !sub; $("barTitle").textContent = TITLES[r] || "";
  $("dawn").hidden = r !== "";
  if (!$view.dataset.loaded) $view.innerHTML = `<div class="sk" style="width:35%;margin-top:30px"></div><div class="sk" style="height:40px;width:80%"></div><div class="sk"></div><div class="sk" style="width:70%"></div>`;
  try {
    $view.innerHTML = r === "a" ? await viewArticle(a, b) : r === "d" ? await viewDigest(a) : r === "t" ? await viewTopic(a) : r === "quiz" ? await viewQuiz(a) : r === "archive" ? await viewArchive()
      : r === "saved" ? viewSaved() : r === "learn" ? await viewLearn() : r === "settings" ? await viewSettings() : await viewToday();
    $view.dataset.loaded = "1";
  } catch (e) {
    $view.innerHTML = `<div class="empty"><h2>You’re offline</h2><p>Briefs you’ve opened before are still available. Reconnect and tap refresh to get today’s.</p></div>`;
  }
  if (r === "a") bindArticle(a, b);
  if (r === "learn") bindLearn();
  if (r === "quiz") bindQuiz(a);
  if (r === "" || r === "d") { const cur = r === "d" ? cache[`api/digests/${encodeURIComponent(a)}.json`] : currentToday; if (cur) bindListen(cur); }
  document.querySelectorAll("[data-ex]").forEach((b) => b.addEventListener("click", () => { exploreTab = b.dataset.ex; route(); }));
  if (r === "settings") bindSettings();
  if (r === "archive") {
    const idx = await getIndex().catch(() => []);
    $("q")?.addEventListener("input", (e) => {
      const q = e.target.value.toLowerCase();
      $("list").innerHTML = archiveRows(idx.filter((x) => `${x.tldr} ${x.top} ${x.date}`.toLowerCase().includes(q)));
    });
  }
  $("hideInstall")?.addEventListener("click", () => { store.set("hideInstall", true); route(); });
  $("installNow")?.addEventListener("click", async () => { deferredInstall.prompt(); await deferredInstall.userChoice; deferredInstall = null; route(); });
  window.scrollTo(0, 0); onScroll();
}

async function refresh() {
  const btn = $("refreshBtn"); btn.classList.add("spin");
  for (const k of Object.keys(cache)) delete cache[k];
  try { await getIndex(true); await route(); toast("Up to date"); } catch { toast("Offline. Showing your saved copy."); }
  btn.classList.remove("spin");
}

function onScroll() { $("topbar").classList.toggle("scrolled", window.scrollY > 24); }

window.addEventListener("hashchange", route);
window.addEventListener("scroll", onScroll, { passive: true });
window.addEventListener("beforeinstallprompt", (e) => { e.preventDefault(); deferredInstall = e; if ((location.hash || "#/") === "#/") route(); });
$("refreshBtn").addEventListener("click", refresh);
$("backBtn").addEventListener("click", () => (history.length > 1 ? history.back() : (location.hash = "#/")));
document.addEventListener("visibilitychange", () => { if (document.visibilityState === "visible") { applyPrefs(); if ((location.hash || "#/") === "#/") refresh(); } });

applyPrefs(); bumpStreak(); route();
if ("serviceWorker" in navigator) navigator.serviceWorker.register("sw.js");
