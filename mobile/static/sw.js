// Service worker simples: guarda a "casca" do app para abrir rápido.
// As chamadas /api/ sempre vão para a rede (dados sempre atualizados).
const CACHE = "quinza-v1";
const ARQUIVOS = ["/", "/static/styles.css", "/static/app.js", "/manifest.webmanifest",
                  "/static/icons/icon-192.png", "/static/icons/icon-180.png"];

self.addEventListener("install", (e) => {
  e.waitUntil(caches.open(CACHE).then((c) => c.addAll(ARQUIVOS)));
  self.skipWaiting();
});

self.addEventListener("activate", (e) => {
  e.waitUntil(caches.keys().then((ks) => Promise.all(ks.filter((k) => k !== CACHE).map((k) => caches.delete(k)))));
  self.clients.claim();
});

self.addEventListener("fetch", (e) => {
  const url = new URL(e.request.url);
  if (e.request.method !== "GET" || url.pathname.startsWith("/api/")) return;
  // Rede primeiro; se estiver offline, usa o cache.
  e.respondWith(
    fetch(e.request)
      .then((r) => {
        const copia = r.clone();
        caches.open(CACHE).then((c) => c.put(e.request, copia));
        return r;
      })
      .catch(() => caches.match(e.request))
  );
});
