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
// PWA Service Worker Lifecycle & Offline Fetch Support
// ══════════════════════════════════════════════════════
const PWA_CACHE_NAME = 'stallcart-pwa-v1';
const PWA_CORE_ASSETS = [
    '/',
    '/static/manifest.json',
    '/static/favicon.ico',
    '/static/images/icons/android-chrome-192x192.png',
    '/static/images/icons/android-chrome-512x512.png',
    '/static/images/icons/apple-touch-icon.png',
    '/static/css/style.css'
];

self.addEventListener('install', (event) => {
    self.skipWaiting();
    event.waitUntil(
        caches.open(PWA_CACHE_NAME).then((cache) => {
            return cache.addAll(PWA_CORE_ASSETS).catch((err) => {
                // Graceful fallback if any asset fails to pre-cache
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

// Network-first fetch strategy required for PWA installability
self.addEventListener('fetch', (event) => {
    if (event.request.method !== 'GET') return;
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