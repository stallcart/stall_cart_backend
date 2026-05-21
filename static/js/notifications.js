// static/js/notifications.js
'use strict';

(function () {
    const el = document.getElementById('sc-fcm');
    if (!el) {
        console.log('[SCNotif] #sc-fcm element not found - skipping init');
        return;
    }

    // ✅ SAFE: Read config from dedicated JSON script tag (NOT dataset)
    let firebaseConfig = {};
    try {
        const configScript = document.getElementById('firebase-config-data');
        if (configScript?.textContent?.trim()) {
            firebaseConfig = JSON.parse(configScript.textContent);
            console.log('[SCNotif] ✅ Config loaded from #firebase-config-data', {
                projectId: firebaseConfig.projectId,
                appId: firebaseConfig.appId ? firebaseConfig.appId.substring(0, 10) + '...' : null
            });
        } else {
            console.error('[SCNotif] ❌ #firebase-config-data is empty or missing');
            return;
        }
    } catch (e) {
        console.error('[SCNotif] ❌ Failed to parse firebase config:', e);
        const configScript = document.getElementById('firebase-config-data');
        console.warn('[SCNotif] Raw content preview:', configScript?.textContent?.substring(0, 300));
        return;
    }

    const vapidKey    = el.dataset.vapid  || '';
    const registerUrl = el.dataset.url    || '';
    const csrfToken   = el.dataset.csrf   || '';

    console.log('[SCNotif] Initializing...', {
        hasProjectId: !!firebaseConfig.projectId,
        hasVapid: !!vapidKey,
        hasUrl: !!registerUrl,
        permission: Notification.permission
    });

    if (!firebaseConfig.projectId || !registerUrl) {
        console.error('[SCNotif] ❌ Missing required config', {
            projectId: firebaseConfig.projectId,
            registerUrl: registerUrl
        });
        return;
    }

    // ✅ Skip if permission denied - dispatch event for UI to show help
    if (Notification.permission === 'denied') {
        console.warn('[SCNotif] ⚠️ Permission denied - dispatching event');
        document.dispatchEvent(new CustomEvent('notificationPermissionDenied'));
        return;
    }

    // Lazy-load Firebase SDK (with duplicate check)
    function loadScript(src) {
        return new Promise((res, rej) => {
            if (document.querySelector(`script[src="${src}"]`)) {
                console.log('[SCNotif] Script already loaded:', src);
                res();
                return;
            }
            const s = document.createElement('script');
            s.src = src;
            s.onload = () => { console.log('[SCNotif] Loaded:', src); res(); };
            s.onerror = (e) => { console.error('[SCNotif] Failed to load:', src, e); rej(e); };
            document.head.appendChild(s);
        });
    }

    async function init() {
        console.log('[SCNotif] 🚀 Starting init flow...');
        
        if (Notification.permission === 'denied') {
            console.warn('[SCNotif] Permission denied - aborting');
            return;
        }

        try {
            // Load Firebase SDKs
            await loadScript('https://www.gstatic.com/firebasejs/10.7.1/firebase-app-compat.js');
            await loadScript('https://www.gstatic.com/firebasejs/10.7.1/firebase-messaging-compat.js');
            console.log('[SCNotif] ✅ Firebase SDKs loaded');

            // Initialize Firebase app
            if (!firebase.apps.length) {
                firebase.initializeApp(firebaseConfig);
                console.log('[SCNotif] ✅ Firebase app initialized');
            } else {
                console.log('[SCNotif] ℹ️ Firebase app already initialized');
            }
            
            const messaging = firebase.messaging();

            // Register Service Worker
            const sw = await navigator.serviceWorker.register(
                '/firebase-messaging-sw.js', { scope: '/' }
            );
            console.log('[SCNotif] ✅ Service Worker registered', sw.scope);

            // Request notification permission
            const permission = await Notification.requestPermission();
            console.log('[SCNotif] 📢 Notification permission:', permission);
            if (permission !== 'granted') {
                console.warn('[SCNotif] Permission not granted - stopping');
                return;
            }

            // Get FCM token
            const token = await messaging.getToken({ 
                vapidKey: vapidKey, 
                serviceWorkerRegistration: sw 
            });
            console.log('[SCNotif] 🔑 FCM Token:', token ? token.substring(0, 20) + '...' : 'NULL');
            if (!token) {
                console.warn('[SCNotif] No token received - stopping');
                return;
            }

            // POST token to Django backend
            console.log('[SCNotif] 📤 Sending token to:', registerUrl);
            const resp = await fetch(registerUrl, {
                method:  'POST',
                headers: {
                    'Content-Type': 'application/json',
                    'X-CSRFToken':  csrfToken,
                },
                body: JSON.stringify({
                    token: token,
                    device_id:   getDeviceId(),
                    device_name: getDeviceName(),
                }),
            });

            const data = await resp.json();
            console.log('[SCNotif] 📥 Server response:', data);
            
            if (!data.ok) {
                console.warn('[SCNotif] ❌ Registration failed', data);
                return;
            }

            console.log('[SCNotif] 🎉 Registration successful!');

            // Handle foreground messages (tab is focused)
            messaging.onMessage((payload) => {
                console.log('[SCNotif] 💬 Foreground message received', {
                    title: payload.notification?.title,
                    body: payload.notification?.body
                });
                const n = payload.notification || {};
                if (window.showToast) {
                    window.showToast(`🔔 ${n.title}: ${n.body}`, 'info');
                }
                // Also show native notification for consistency
                if (Notification.permission === 'granted') {
                    new Notification(n.title || 'StallCart', {
                        body: n.body || '',
                        icon: n.icon || '/static/images/logo-fallback.png',
                        data: { url: payload.data?.click_action || '/' }
                    });
                }
            });

            // ✅ Expose function for manual re-trigger (e.g., after login)
            window.triggerFCMRegistration = async function() {
                console.log('[SCNotif] 🔄 Manual re-trigger requested');
                if (Notification.permission === 'granted') {
                    try {
                        const token = await messaging.getToken({ 
                            vapidKey: vapidKey, 
                            serviceWorkerRegistration: sw 
                        });
                        if (token) {
                            await fetch(registerUrl, {
                                method: 'POST',
                                headers: { 
                                    'Content-Type': 'application/json', 
                                    'X-CSRFToken': csrfToken 
                                },
                                body: JSON.stringify({ 
                                    token, 
                                    device_id: getDeviceId(), 
                                    device_name: getDeviceName() 
                                }),
                            });
                            console.log('[SCNotif] ✅ Token re-registered');
                        }
                    } catch (e) {
                        console.warn('[SCNotif] Re-trigger failed:', e);
                    }
                }
            };

        } catch (error) {
            console.error('[SCNotif] ❌ Init failed:', error);
        }
    }

    // Helper: Generate stable device ID
    function getDeviceId() {
        let id = localStorage.getItem('sc_did');
        if (!id) { 
            id = 'w-' + (crypto?.randomUUID ? crypto.randomUUID() : Math.random().toString(36).substr(2)); 
            localStorage.setItem('sc_did', id); 
        }
        return id;
    }

    // Helper: Get readable device name
    function getDeviceName() {
        const ua = navigator.userAgent;
        if (/iPhone|iPad|iPod/.test(ua))  return 'Safari iOS';
        if (/Android/.test(ua))      return 'Android Browser';
        if (/Chrome/.test(ua) && !/Edg/.test(ua)) return 'Chrome';
        if (/Firefox/.test(ua))      return 'Firefox';
        if (/Safari/.test(ua))       return 'Safari';
        return 'Web Browser';
    }

    // Auto-init on load (if not handled by login flow)
    if ('serviceWorker' in navigator && 'Notification' in window) {
        if (!window.loginFlowHandledFCM) {
            console.log('[SCNotif] 📅 Scheduling auto-init on load');
            window.addEventListener('load', () => {
                console.log('[SCNotif] 🏁 Window loaded - running init');
                init().catch(e => console.warn('[SCNotif] Auto-init error:', e));
            });
        } else {
            console.log('[SCNotif] ⏭️ Skipping auto-init (login flow will handle)');
        }
    } else {
        console.warn('[SCNotif] ❌ ServiceWorker or Notifications not supported');
    }
    
    // ✅ Export init for manual calls (e.g., from login success)
    window.manualFCMInit = init;
    
})();