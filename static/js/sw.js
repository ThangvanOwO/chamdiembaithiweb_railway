// GradeFlow Service Worker — PWA
// Network-first strategy: ưu tiên mạng, fallback cache khi offline

const CACHE_NAME = 'gradeflow-v1';
const STATIC_CACHE = 'gradeflow-static-v1';

// Static assets to cache on install
const STATIC_ASSETS = [
  '/static/css/design-system.css',
  '/static/css/components.css',
  '/static/css/layout.css',
  '/static/css/animations.css',
  '/static/css/polish.css',
  '/static/js/htmx.min.js',
  '/static/js/alpine.min.js',
  '/static/js/app.js',
  '/static/manifest.json',
];

// Install: cache static assets
self.addEventListener('install', (event) => {
  event.waitUntil(
    caches.open(STATIC_CACHE).then((cache) => {
      return cache.addAll(STATIC_ASSETS);
    })
  );
  self.skipWaiting();
});

// Activate: clean old caches
self.addEventListener('activate', (event) => {
  event.waitUntil(
    caches.keys().then((keys) => {
      return Promise.all(
        keys
          .filter((key) => key !== CACHE_NAME && key !== STATIC_CACHE)
          .map((key) => caches.delete(key))
      );
    })
  );
  self.clients.claim();
});

// Fetch: network-first for pages, cache-first for static assets
self.addEventListener('fetch', (event) => {
  const { request } = event;
  const url = new URL(request.url);

  // Skip non-GET requests
  if (request.method !== 'GET') return;

  // Skip Django admin and auth endpoints
  if (url.pathname.startsWith('/admin') || url.pathname.startsWith('/accounts')) return;

  // Skip media uploads (large files)
  if (url.pathname.startsWith('/media')) return;

  // Static assets: cache-first (fast load)
  if (url.pathname.startsWith('/static/')) {
    event.respondWith(
      caches.match(request).then((cached) => {
        if (cached) return cached;
        return fetch(request).then((response) => {
          if (response.ok) {
            const clone = response.clone();
            caches.open(STATIC_CACHE).then((cache) => cache.put(request, clone));
          }
          return response;
        });
      })
    );
    return;
  }

  // HTML pages: network-first (always fresh data from server)
  if (request.headers.get('Accept')?.includes('text/html')) {
    event.respondWith(
      fetch(request)
        .then((response) => {
          if (response.ok) {
            const clone = response.clone();
            caches.open(CACHE_NAME).then((cache) => cache.put(request, clone));
          }
          return response;
        })
        .catch(() => {
          return caches.match(request).then((cached) => {
            if (cached) return cached;
            // Fallback to offline page for navigation requests
            return caches.match('/offline/');
          });
        })
    );
    return;
  }

  // API / other requests: network-first
  event.respondWith(
    fetch(request)
      .then((response) => {
        if (response.ok) {
          const clone = response.clone();
          caches.open(CACHE_NAME).then((cache) => cache.put(request, clone));
        }
        return response;
      })
      .catch(() => caches.match(request))
  );
});
