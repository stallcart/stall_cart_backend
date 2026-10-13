// static/js/firebase-messaging-sw.js
// Config is injected by Django's firebase_sw view before this runs
importScripts('https://www.gstatic.com/firebasejs/10.7.1/firebase-app-compat.js');
importScripts('https://www.gstatic.com/firebasejs/10.7.1/firebase-messaging-compat.js');

firebase.initializeApp(self.FIREBASE_CONFIG || {});
const messaging = firebase.messaging();

// Background notifications (tab not focused)
messaging.onBackgroundMessage((payload) => {
    const n    = payload.notification || {};
    const data = payload.data || {};
    self.registration.showNotification(n.title || 'StallCart', {
        body:               n.body || '',
        icon:               n.icon || '/static/images/logo-fallback.png',
        image:              n.image,
        badge:              '/static/images/badge-icon.png',
        tag:                data.tag || 'stallcart',
        data:               { url: data.click_action || '/' },
        requireInteraction: false,
        actions: [
            { action: 'open',  title: '🛍️ View' },
            { action: 'close', title: 'Dismiss' },
        ],
    });
});

// Click → navigate
self.addEventListener('notificationclick', (e) => {
    e.notification.close();
    if (e.action === 'close') return;
    const url = e.notification.data?.url || '/';
    e.waitUntil(
        clients.matchAll({ type: 'window', includeUncontrolled: true }).then((list) => {
            for (const c of list) {
                if (c.url.startsWith(self.location.origin) && 'focus' in c) {
                    return c.focus().then(w => w.navigate(url));
                }
            }
            return clients.openWindow(url);
        })
    );
});

// ══════════════════════════════════════════════════════
// PWA Service Worker Lifecycle & High-Performance Fetch
// ══════════════════════════════════════════════════════
const PWA_CACHE_NAME = 'stallcart-pwa-v2';
const PWA_CORE_ASSETS = [
    '/',
    '/static/manifest.json'
];

self.addEventListener('install', (event) => {
    self.skipWaiting();
    event.waitUntil(
        caches.open(PWA_CACHE_NAME).then((cache) => {
            return cache.addAll(PWA_CORE_ASSETS).catch((err) => {
                console.warn('PWA Pre-cache notice:', err);
            });
        })
    );
});

self.addEventListener('activate', (event) => {
    event.waitUntil(
        caches.keys().then((keys) => {
            return Promise.all(
                keys.filter((key) => key !== PWA_CACHE_NAME).map((key) => caches.delete(key))
            );
        }).then(() => clients.claim())
    );
});

// High-Performance Fetch Strategy:
// Intercept ONLY top-level HTML navigation requests for offline support & PWA compliance.
// Subresources (images, stylesheets, fonts, scripts, API calls) bypass Service Worker thread completely,
// streaming directly through native browser HTTP cache and network pipelines at maximum speed.
self.addEventListener('fetch', (event) => {
    if (event.request.method !== 'GET') return;
    if (event.request.mode !== 'navigate') return;
    if (!event.request.url.startsWith(self.location.origin)) return;

    event.respondWith(
        fetch(event.request)
            .then((networkResponse) => {
                return networkResponse;
            })
            .catch(() => {
                return caches.match(event.request).then((cached) => {
                    return cached || caches.match('/');
                });
            })
    );
});