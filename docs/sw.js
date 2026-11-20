/* DevBrief service worker: offline reading + push notifications. */
const SHELL = "devbrief-shell-v3";
const DATA = "devbrief-data";
const SHELL_FILES = ["./", "index.html", "app.css", "app.js", "manifest.webmanifest", "icons/icon-192.png", "icons/badge-96.png",
  "fonts/newsreader-latin-opsz-normal.woff2", "fonts/newsreader-latin-opsz-italic.woff2", "fonts/figtree-latin-wght-normal.woff2"];

self.addEventListener("install", (e) => {
  e.waitUntil(caches.open(SHELL).then((c) => c.addAll(SHELL_FILES)).then(() => self.skipWaiting()));
});

self.addEventListener("activate", (e) => {
  e.waitUntil(caches.keys()
    .then((keys) => Promise.all(keys.filter((k) => k !== SHELL && k !== DATA).map((k) => caches.delete(k))))
    .then(() => self.clients.claim()));
});

self.addEventListener("fetch", (e) => {
  const url = new URL(e.request.url);
  if (e.request.method !== "GET" || url.origin !== location.origin) return;
  if (url.pathname.includes("/api/")) {
    // News: network first (fresh), fall back to the last copy so it works offline.
    e.respondWith(fetch(e.request).then((res) => {
      const copy = res.clone(); caches.open(DATA).then((c) => c.put(e.request, copy)); return res;
    }).catch(() => caches.match(e.request)));
  } else {
    // App shell: cache first, refresh in background.
    e.respondWith(caches.match(e.request).then((hit) => {
      const net = fetch(e.request).then((res) => {
        if (res.ok) { const copy = res.clone(); caches.open(SHELL).then((c) => c.put(e.request, copy)); }
        return res;
      }).catch(() => hit);
      return hit || net;
    }));
  }
});

self.addEventListener("push", (e) => {
  let d = {};
  try { d = e.data.json(); } catch { d = { title: "DevBrief", body: e.data && e.data.text() }; }
  e.waitUntil((async () => {
    // Pre-load today's brief so it opens instantly (even on a flaky morning connection).
    try {
      const cache = await caches.open(DATA);
      const idx = await fetch("api/index.json", { cache: "no-cache" });
      await cache.put("api/index.json", idx.clone());
      const list = await idx.json();
      for (const name of [list[0]?.name, list.find((x) => !x.weekly)?.name].filter(Boolean)) {
        const r = await fetch(`api/digests/${name}.json`); await cache.put(`api/digests/${name}.json`, r);
      }
      const learn = await fetch("api/learn.json"); await cache.put("api/learn.json", learn);
    } catch { /* offline — notification still shows */ }
    await self.registration.showNotification(d.title || "☕ DevBrief", {
      body: d.body || "Your morning brief is ready.",
      icon: "icons/icon-192.png", badge: "icons/badge-96.png", tag: d.tag || "devbrief",
      renotify: true, requireInteraction: !!d.urgent, data: { url: d.url || self.registration.scope },
    });
  })());
});

self.addEventListener("notificationclick", (e) => {
  e.notification.close();
  const target = e.notification.data && e.notification.data.url || self.registration.scope;
  e.waitUntil(clients.matchAll({ type: "window", includeUncontrolled: true }).then((wins) => {
    for (const w of wins) if (w.url.startsWith(self.registration.scope)) { w.navigate(target); return w.focus(); }
    return clients.openWindow(target);
  }));
});
