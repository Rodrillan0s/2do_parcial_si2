# AuroraStore — Iteración 2: Arquitectura PWA Offline-First

**Fecha:** 2026-10-28  
** Alcance:** Frontend Web Angular 21 (`frontend/`) + Contrato de Sincronización en Backend FastAPI (`backend/app/modules/ecommerce/routes/sync_routes.py`) + PostgreSQL (`003_iter2_sync_idempotency`).  
**Compatibilidad:** Conserva íntegramente los contratos P1 e Iteración 1 y establece el contrato común de sincronización reutilizable por la app móvil Flutter (`mobile/` no modificado en esta tarea).

---

## 1. Visión Arquitectónica y Separación de Responsabilidades

La arquitectura PWA Offline-First de AuroraStore separa estrictamente **cuatro capas** para cumplir las reglas de seguridad multitenant SaaS y preservar las optimizaciones de rendimiento de la Iteración 1:

```
┌────────────────────────────────────────────────────────────────────────────┐
│                         NAVEGADOR / CLIENTE PWA                            │
│                                                                            │
│  ┌──────────────────────────────┐     ┌─────────────────────────────────┐  │
│  │ 1. Service Worker (/sw.js)   │     │ 2. IndexedDB (aurora_store_pwa) │  │
│  │ • App Shell (HTML/JS/CSS)    │     │ • Particionado por scope_key:   │  │
│  │ • Iconos y fuentes estáticas │     │   - Público: public|e:{tid}     │  │
│  │ • Imágenes de catálogo (LRU) │     │   - Privado: u:{uid}|e:{tid}    │  │
│  │ • PROHIBIDO cachear /api/*   │     │ • Cola Offline (CU37W/38W/39W)  │  │
│  └──────────────────────────────┘     └─────────────────────────────────┘  │
│                 ▲                                      ▲                   │
│                 │                                      │                   │
│  ┌──────────────┴──────────────────────────────────────┴────────────────┐  │
│  │ 3. Servicios Angular Reactivos (Signals + RxJS)                      │  │
│  │ • NetworkStatusService (ONLINE | OFFLINE | CHECKING | SYNCING)       │  │
│  │ • SyncQueueService (FIFO, UUID idempotente, Lock multi-pestaña)      │  │
│  │ • PwaUpdateService (actualización controlada con confirmación)       │  │
│  └──────────────────────────────────┬───────────────────────────────────┘  │
└─────────────────────────────────────┼──────────────────────────────────────┘
                                      │ HTTPS / JSON (POST /api/sync/operations)
                                      ▼
┌────────────────────────────────────────────────────────────────────────────┐
│                    4. SERVIDOR FASTAPI + POSTGRESQL                        │
│  • Validación estricta de JWT, RBAC, vigencia SaaS y resolver_empresa      │
│  • Registro idempotente por (id_usuario, id_empresa, operation_id)         │
│  • Detección autoritativa de conflictos (stock, precio, estado inactivo)   │
└────────────────────────────────────────────────────────────────────────────┘
```

---

## 2. Política de Cachés del Service Worker (`frontend/public/sw.js`)

Se implementó un Service Worker nativo controlado (`frontend/public/sw.js`) sin introducir dependencias externas adicionales (`0 KB` de sobrecarga en librerías npm):

| Caché en `CacheStorage` | Contenido permitido | Estrategia | Límite / Limpieza |
| :--- | :--- | :--- | :--- |
| `aurora-shell-v2.0.0` | `/`, `/index.html`, `/manifest.webmanifest`, `/icons/*` | *Network-First* para navegaciones HTML con fallback offline a `/index.html` | Se purgan versiones previas en `activate` |
| `aurora-static-v2.0.0` | Bundles de Angular con hash (`chunk-*.js`, `main-*.js`, `styles-*.css`), fuentes | *Cache-First* (inmutables por hash de compilación) | Se purgan versiones previas en `activate` |
| `aurora-images-v2.0.0` | Imágenes públicas de catálogo (`.png`, `.jpg`, `.webp`, Cloudinary) | *Stale-While-Revalidate* | Máximo **120 imágenes** (recorte FIFO automático `trimCache`) |
| **Exclusión Estricta (`/api/*`)** | Cualquier ruta `/api/*`, métodos `POST/PUT/DELETE/PATCH` o cabeceras `Authorization` | **Network-Only (Jamás entra en `CacheStorage`)** | Evita fugas de datos privados entre usuarios o tenants en dispositivos compartidos |

---

## 3. Esquema y Particionamiento en IndexedDB (`IndexedDbService`)

Base de datos local: `aurora_store_pwa_db` (versión `1`), implementada en `frontend/src/app/core/storage/indexed-db.service.ts` con degradación automática a memoria temporal (`FALLBACK_MEMORY`) si el navegador bloquea IndexedDB o agota cuota (`QuotaExceededError`):

| Object Store | `keyPath` | Índices | `scope_key` (Particionamiento) | Propósito y Límite |
| :--- | :--- | :--- | :--- | :--- |
| `products` | `key` | `by_scope`, `by_tenant`, `by_fetched_at` | `public\|e:{tid}` (catálogo) o `u:{uid}\|e:{tid}` (admin) | Páginas visitadas de productos (máx. **20 páginas** por scope, LRU, TTL 24h) |
| `product_details` | `key` | `by_scope`, `by_tenant`, `by_fetched_at` | `public\|e:{tid}` o `u:{uid}\|e:{tid}` | Detalle de prendas visitadas (máx. **60 fichas** por scope, LRU, TTL 24h) |
| `catalog_filters` | `key` | `by_scope`, `by_tenant`, `by_fetched_at` | `public\|e:{tid}` | Tenants públicos y filtros dinámicos (categorías, tallas, colores, temporadas) |
| `stock_snapshots` | `key` | `by_scope`, `by_tenant`, `by_fetched_at` | `public\|e:{tid}` | Última disponibilidad conocida por variante y sucursal con `fetched_at` |
| `cart_drafts` | `key` | `by_scope`, `by_tenant`, `by_fetched_at` | `u:{uid}\|e:{tid}` | Copia local y borrador optimista del carrito del usuario por tienda |
| `pending_operations` | `operation_id` | `by_scope`, `by_tenant`, `by_status` | `u:{uid}\|e:{tid}` | Cola persistente de operaciones pendientes (`CU37W`, `CU38W`, `CU39W`) |
| `sync_attempts` | `attempt_id` | `by_scope`, `by_tenant`, `by_fetched_at` | `u:{uid}\|e:{tid}` | Bitácora local de intentos de sincronización y códigos HTTP recibidos |
| `metadata` | `key` | `by_scope`, `by_tenant`, `by_fetched_at` | `u:{uid}\|e:{tid}` | Mis reservas descargadas y metadatos auxiliares |

### Seguridad SaaS y Purga en Logout / Cambio de Cuenta
- En `AuthService.cerrarSesion()` y en `AuthService.guardarSesion()` (cuando cambia `id_usuario`), se invoca `this.indexedDb.purgePrivateData()`, eliminando todos los registros con prefijo `u:` así como el contenido completo de `cart_drafts`, `pending_operations` y `sync_attempts`.
- Ningún token JWT, contraseña ni credencial de pago se almacena en `IndexedDB` ni en `CacheStorage`.

---

## 4. Detección Real de Conectividad y Coordinación Multi-Pestaña

1. **Detección Híbrida (`NetworkStatusService`)**:
   - No asume que `navigator.onLine === true` equivale a conexión real con FastAPI.
   - Combina eventos del navegador (`online` / `offline`), señales pasivas del `errorInterceptor` (`recordApiSuccess` ante respuestas HTTP reales y `recordApiNetworkFailure` ante `status === 0`), y sondeo activo con `AbortController` (`3.5s` timeout) contra `/api/sync/ping` o `/?_ping=...` (`0` consultas SQL).
2. **Coordinación entre Pestañas (`SyncQueueService`)**:
   - Utiliza `BroadcastChannel('aurora_sync_channel')` para mantener sincronizado el contador de la cola en todas las pestañas abiertas.
   - Implementa un **lease lock** en `localStorage` (`aurora_sync_lock_lease` con `tabId` y TTL de `15s`) para garantizar que solo una pestaña ejecute el envío por lotes `POST /api/sync/operations` al reconectar.

---

## 5. Decisiones de Negocio por Caso de Uso (Regla #6)

- **Permitidos Offline (Lectura con sello de antigüedad)**: `CU04W` (Catálogo), `CU05W` (Búsqueda/filtrado sobre subconjunto local con aviso explícito), `CU06W` (Detalle de producto visitado o vista honesta de resumen), `CU07W` (Disponibilidad por sucursal mostrando `fetched_at` y advertencia de no garantía offline).
- **Permitidos Offline (Encolado Seguro)**: `CU08W` (Agregar/actualizar/quitar/vaciar bolsa de compras con coalescencia inteligente) y `CU10W` (Preparar solicitud de reserva gratuita `SIN_PAGO` en la cola local, etiquetada explícitamente como *Solicitud pendiente de validación online*, nunca como reserva confirmada).
- **Estrictamente Online (Bloqueados sin conexión con aviso claro)**: `CU09W` (Confirmar pedido de compra), `CU27W` (Procesar pago electrónico / reserva con pago anticipado) y `CU24W` (Registrar venta presencial en Caja POS para evitar doble venta física y descuadres de arqueo).

