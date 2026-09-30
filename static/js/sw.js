// Cache only public static assets. Grading, identity and APK responses stay online.
// v2 retires cached HTML containing the removed browser-camera interface.
const STATIC_CACHE = 'gradeflow-static-v2';
const OFFLINE_URL = '/offline/';
self.addEventListener('install', event => {
  event.waitUntil(caches.open(STATIC_CACHE).then(cache => cache.add(OFFLINE_URL)));
  self.skipWaiting();
});
self.addEventListener('activate', event => {
  event.waitUntil(caches.keys().then(keys => Promise.all(keys
    .filter(key => key.startsWith('gradeflow-') && key !== STATIC_CACHE)
    .map(key => caches.delete(key)))));
  self.clients.claim();
});
self.addEventListener('fetch', event => {
  const request = event.request;
  const url = new URL(request.url);
  if (request.method !== 'GET' || url.origin !== self.location.origin) return;
  if (url.pathname.startsWith('/downloads/') || url.pathname.startsWith('/media/') ||
      url.pathname.startsWith('/api/') || url.pathname.includes('/api/')) return;
  if (url.pathname.startsWith('/static/')) {
    event.respondWith(caches.match(request).then(cached => cached || fetch(request).then(response => {
      if (response.ok) {
        const copy = response.clone();
        event.waitUntil(caches.open(STATIC_CACHE).then(cache => cache.put(request, copy)));
      }
      return response;
    })));
  } else if (request.mode === 'navigate') {
    event.respondWith(fetch(request).catch(async () =>
      (await caches.match(OFFLINE_URL)) || new Response('GradeFlow: cần kết nối mạng.', {
        status: 503, headers: { 'Content-Type': 'text/plain; charset=utf-8' }
      })));
  }
});
