/**
 * AuroraStore — Service Worker Oficial (Iteración 2 PWA Offline-First)
 *
 * REGLAS DE SEGURIDAD Y ARQUITECTURA:
 * 1. Separa estrictamente el caché del App Shell / recursos estáticos (CacheStorage)
 *    de los datos de negocio multitenant (almacenados exclusivamente en IndexedDB).
 * 2. NUNCA intercepta ni almacena en CacheStorage peticiones a `/api/*`, peticiones con
 *    cabecera `Authorization`, ni métodos distintos de `GET`.
 * 3. Gestiona actualizaciones de versión sin recargas sorpresivas: notifica a los clientes
 *    activos y solo ejecuta `skipWaiting()` cuando el usuario o el gestor seguro lo confirma.
 */

const SW_VERSION = '2.0.0';
const SHELL_CACHE = `aurora-shell-v${SW_VERSION}`;
const STATIC_CACHE = `aurora-static-v${SW_VERSION}`;
const IMAGE_CACHE = `aurora-images-v${SW_VERSION}`;
const ACTIVE_CACHES = [SHELL_CACHE, STATIC_CACHE, IMAGE_CACHE];
const MAX_CACHED_IMAGES = 120;

const CORE_SHELL_ASSETS = [
  '/',
  '/index.html',
  '/manifest.webmanifest',
  '/favicon.ico',
  '/icons/icon-192x192.png',
  '/icons/icon-512x512.png'
];

self.addEventListener('install', (event) => {
  event.waitUntil(
    (async () => {
      const cache = await caches.open(SHELL_CACHE);
      for (const assetUrl of CORE_SHELL_ASSETS) {
        try {
          const response = await fetch(assetUrl, { cache: 'reload' });
          if (response && response.ok) {
            await cache.put(assetUrl, response.clone());
          }
        } catch (_) {
          // Si algún recurso secundario falla en instalación inicial, continuar
        }
      }

      // Si no hay clientes controlados previos, activar de inmediato en 1ª instalación.
      // Si ya hay clientes abiertos, esperar confirmación explícita (SKIP_WAITING) para
      // no perder formularios ni operaciones en curso.
      const clientsList = await self.clients.matchAll({ type: 'window', includeUncontrolled: false });
      if (!clientsList || clientsList.length === 0) {
        await self.skipWaiting();
      } else {
        for (const client of clientsList) {
          client.postMessage({
            type: 'SW_UPDATE_AVAILABLE',
            version: SW_VERSION
          });
        }
      }
    })()
  );
});

self.addEventListener('activate', (event) => {
  event.waitUntil(
    (async () => {
      const keys = await caches.keys();
      await Promise.all(
        keys.map((key) => {
          if (key.startsWith('aurora-') && !ACTIVE_CACHES.includes(key)) {
            return caches.delete(key);
          }
          return Promise.resolve();
        })
      );
      await self.clients.claim();
      const clientsList = await self.clients.matchAll({ type: 'window' });
      for (const client of clientsList) {
        client.postMessage({
          type: 'SW_ACTIVATED',
          version: SW_VERSION
        });
      }
    })()
  );
});

self.addEventListener('message', (event) => {
  const data = event.data || {};
  if (data.type === 'SKIP_WAITING') {
    self.skipWaiting();
  } else if (data.type === 'GET_VERSION') {
    if (event.source) {
      event.source.postMessage({
        type: 'SW_VERSION_INFO',
        version: SW_VERSION
      });
    }
  } else if (data.type === 'CLEAR_IMAGE_CACHE') {
    event.waitUntil(caches.delete(IMAGE_CACHE));
  }
});

async function trimCache(cacheName, maxItems) {
  try {
    const cache = await caches.open(cacheName);
    const keys = await cache.keys();
    if (keys.length > maxItems) {
      const deleteCount = keys.length - maxItems;
      for (let i = 0; i < deleteCount; i++) {
        await cache.delete(keys[i]);
      }
    }
  } catch (_) {}
}

function isApiOrAuthenticatedRequest(request, url) {
  if (request.method !== 'GET') return true;
  if (url.protocol !== 'http:' && url.protocol !== 'https:') return true;
  if (url.pathname.startsWith('/api/') || url.pathname === '/api') return true;
  if (url.pathname.startsWith('/ws/') || url.pathname.includes('/api/ws')) return true;
  if (request.headers.get('Authorization')) return true;
  return false;
}

function isHashedStaticAsset(url) {
  if (url.origin !== self.location.origin) return false;
  return /\.(js|css|woff2?|ttf|eot|svg|ico|webmanifest)$/i.test(url.pathname);
}

function isCatalogImageAsset(request, url) {
  if (request.destination === 'image') return true;
  if (/\.(png|jpe?g|webp|avif|gif)$/i.test(url.pathname)) return true;
  if (url.hostname.includes('res.cloudinary.com') || url.hostname.includes('images.unsplash.com')) {
    return true;
  }
  return false;
}

self.addEventListener('fetch', (event) => {
  const request = event.request;
  let url;
  try {
    url = new URL(request.url);
  } catch (_) {
    return;
  }

  // REGLA NO NEGOCIABLE #5 y #7: Jamás cachear APIs ni peticiones autenticadas en Service Worker
  if (isApiOrAuthenticatedRequest(request, url)) {
    return;
  }

  // 1. Navegaciones de documentos SPA (Rutas como /, /catalogo, /admin/productos, /mis-reservas)
  if (request.mode === 'navigate') {
    event.respondWith(
      (async () => {
        try {
          const networkResponse = await fetch(request);
          if (networkResponse && networkResponse.ok && url.origin === self.location.origin) {
            const shellCache = await caches.open(SHELL_CACHE);
            shellCache.put('/index.html', networkResponse.clone());
          }
          return networkResponse;
        } catch (_) {
          const shellCache = await caches.open(SHELL_CACHE);
          const cachedIndex = (await shellCache.match('/index.html')) || (await shellCache.match('/'));
          if (cachedIndex) {
            return cachedIndex;
          }
          return new Response(
            '<!doctype html><html lang="es"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>AuroraStore — Sin Conexión</title><style>body{background:#09090b;color:#f4f4f5;font-family:system-ui,sans-serif;display:flex;align-items:center;justify-content:center;min-height:100vh;margin:0;padding:24px;text-align:center}.card{max-width:440px;padding:32px;border-radius:24px;background:#18181b;border:1px solid #27272a}h1{color:#f59e0b;font-size:1.25rem;margin-bottom:12px}p{color:#a1a1aa;font-size:0.875rem;line-height:1.5}</style></head><body><div class="card"><h1>AuroraStore — Sin conexión a Internet</h1><p>Esta es tu primera visita sin conexión y el App Shell aún no se encontraba descargado en este dispositivo. Conéctate brevemente para habilitar el modo offline.</p></div></body></html>',
            {
              status: 503,
              headers: { 'Content-Type': 'text/html; charset=utf-8' }
            }
          );
        }
      })()
    );
    return;
  }

  // 2. Bundles estáticos de la aplicación (Cache-First + actualización en caché)
  if (isHashedStaticAsset(url)) {
    // En desarrollo local (localhost), omitir intercepción de chunks dinámicos de Vite HMR
    if (url.hostname === 'localhost' || url.hostname === '127.0.0.1' || url.port === '4200') {
      return;
    }
    event.respondWith(
      (async () => {
        const cached = await caches.match(request);
        if (cached) {
          return cached;
        }
        try {
          const networkResponse = await fetch(request);
          if (networkResponse && networkResponse.ok) {
            const staticCache = await caches.open(STATIC_CACHE);
            staticCache.put(request, networkResponse.clone());
          } else if (networkResponse && networkResponse.status === 404 && /\.js$/i.test(url.pathname)) {
            // Un chunk con hash no se encontró en el servidor: nueva versión desplegada
            try {
              await caches.delete(STATIC_CACHE);
              await caches.delete(SHELL_CACHE);
            } catch (_) {}
            const clientsList = await self.clients.matchAll({ type: 'window' });
            for (const client of clientsList) {
              client.postMessage({
                type: 'STALE_CHUNK_DETECTED',
                pathname: url.pathname
              });
            }
          }
          return networkResponse;
        } catch (err) {
          throw err;
        }
      })()
    );
    return;
  }

  // 3. Imágenes públicas de catálogo e íconos (Stale-While-Revalidate con cuota acotada)
  if (isCatalogImageAsset(request, url)) {
    event.respondWith(
      (async () => {
        const imageCache = await caches.open(IMAGE_CACHE);
        const cached = await imageCache.match(request);
        const fetchPromise = fetch(request)
          .then((networkResponse) => {
            if (networkResponse && (networkResponse.ok || networkResponse.type === 'opaque')) {
              imageCache.put(request, networkResponse.clone());
              trimCache(IMAGE_CACHE, MAX_CACHED_IMAGES);
            }
            return networkResponse;
          })
          .catch(() => cached);

        return cached || fetchPromise;
      })()
    );
  }
});

