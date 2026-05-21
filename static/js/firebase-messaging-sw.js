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