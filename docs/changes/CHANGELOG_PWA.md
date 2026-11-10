# Changelog — Módulo PWA Offline-First (AuroraStore)

**Módulo:** Progressive Web App (PWA) & Sincronización Transaccional Offline-First  
**Ubicación:** `frontend/` (Angular 21) & `backend/app/modules/ecommerce/routes/sync_routes.py`  
**Base de Datos:** PostgreSQL (`003_iter2_sync_idempotency`, `004_iter2_sync_transactional`) + IndexedDB (`aurora_store_pwa_db` v4)  
**Estado:** Estable / Pruebas 100% Superadas (8/8 `test_pwa_iter2.py`)  

---

## [2026-11-07] — Estabilización de Pruebas de Integración y Compatibilidad Multitenant

### 1. Contexto y Diagnóstico
Durante la auditoría del módulo PWA y ejecución de la suite de pruebas automatizadas `tests/test_pwa_iter2.py`, se identificó que la suite creaba esquemas temporales dinámicos (`pwa_*`) aplicando únicamente las migraciones 001 a 004. Tras la introducción de la arquitectura multitenant SaaS (migración 006) y la validación de horarios de atención en sucursales, surgieron dos discrepancias en el entorno de pruebas:
- La consulta pública de tiendas (`obtener_tenants_publicos`) requería las columnas `slug` y `configuracion_storefront` añadidas en la migración 006.
- La validación de visitas presenciales de reservas requería las columnas `horario_apertura` y `horario_cierre` en `t_sucursal`.

### 2. Cambios Implementados
- **`tests/test_pwa_iter2.py`:**
  - Se incorporó la ejecución formal de la migración `backend/migrations/006_iter4_saas_storefront.up.sql` en el `setUpClass` de la suite aislada, garantizando que los contratos de subdominio/slug y tabla `t_solicitud_contratacion` estén presentes en los esquemas de prueba.
  - Se añadieron formalmente las columnas `horario_apertura` (DEFAULT `'09:00:00'`) y `horario_cierre` (DEFAULT `'21:00:00'`) en `PWA_SYNC_SCHEMA_SQL` para `t_sucursal`.
- **`backend/app/modules/saas/services/saas_services.py`:**
  - Verificada la resiliencia en `consultar_plan()` para que la consulta a `t_solicitud_contratacion` no aborte transacciones activas en esquemas heredados.

### 3. Verificación y Resultados de Pruebas
- **Comando:** `python -m pytest tests/test_pwa_iter2.py -v`
- **Resultado:** **8 pasadas de 8 pruebas ejecutadas (100% GREEN)** en 8.83 segundos:
  - `test_01_reversible_sync_migration_003` -> PASSED
  - `test_02_sync_ping_zero_sql_queries` -> PASSED (0 SQL queries en ping)
  - `test_03_sync_cart_operations_idempotency_and_n_plus_1_elimination` -> PASSED
  - `test_04_sync_conflict_detection_and_resolution_cu39w` -> PASSED
  - `test_05_sync_reserva_solicitud_and_payment_guard_cu10w` -> PASSED (Rechazo de pagos online en cola offline `PAYMENT_REQUIRES_ONLINE` + aceptación de reserva gratuita)
  - `test_06_multitenant_isolation_and_public_catalog_cache` -> PASSED (Aislamiento entre tenants `TENANT_FORBIDDEN` y caché de catálogo en memoria)
  - `test_07_sync_lote_venta_contado_efectivo_idempotency_and_guards_cu24w` -> PASSED (Guardas RBAC para `VENTA_CONTADO`, ventas en efectivo confirmadas con idempotencia)
  - `test_08_sync_lote_venta_contado_conflicts_and_reconciliation_cu39w` -> PASSED (Detección de conflictos de precio y conciliación de caja en reconexión)

---

## [2026-10-31] — Idempotencia Transaccional y Cola de Retención Durable

### 1. Resumen de la Implementación
- Implementación de la migración `004_iter2_sync_transactional.up.sql` para vincular cada efecto comercial (venta, reserva, movimiento de stock) y su recibo persistente (`t_sync_recibo`) en un único `COMMIT` atómico en PostgreSQL.
- Eliminación de commits intermedios y eliminación de compensaciones en diferido.
- Bloqueo por aviso transaccional en PostgreSQL (`pg_advisory_xact_lock`) sobre `(schema, id_usuario, id_empresa, operation_id)` para prevenir condiciones de carrera entre múltiples pestañas o procesos worker concurrentes.
- Huella criptográfica de contenido (`request_hash` SHA-256): si una operación idéntica se reenvía, el servidor detecta el replay idempotente y devuelve el resultado original (`idempotent_replay: true`) sin duplicar movimientos de stock ni asientos contables.

---

## [2026-10-28] — Arquitectura Base PWA Offline-First

### 1. Resumen de la Implementación
- **Service Worker Nativo (`frontend/public/sw.js` v2.0.0):**
  - App Shell: `aurora-shell-v2.0.0` (Network-First con fallback a `/index.html`).
  - Bundles JS/CSS con hash: `aurora-static-v2.0.0` (Cache-First).
  - Imágenes: `aurora-images-v2.0.0` (Stale-While-Revalidate con límite LRU de 120 imágenes).
  - Aislamiento estricto: `/api/*` y solicitudes autenticadas jamás se almacenan en `CacheStorage`.
  - Detección de chunks 404 tras despliegues (`STALE_CHUNK_DETECTED`) para recarga suave.
- **Web App Manifest (`frontend/public/manifest.webmanifest`):**
  - Standalone, iconos adaptativos de 72px a 512px + maskable icon, accesos directos a Catálogo y Reservas.
- **IndexedDB (`aurora_store_pwa_db` v4):**
  - Tiendas durables: `pending_operations`, `sync_attempts`, `sync_receipts`.
  - Tiendas de caché: `products`, `product_details`, `catalog_filters`, `branches`, `stock_snapshots`, `cart_drafts`, `metadata`.
  - Particionado estricto de scope: `public|e:{tenant_id}` vs `u:{user_id}|e:{tenant_id}|b:{branch_id}`.
- **Detección de Conectividad (`NetworkStatusService`):**
  - Señales híbridas: eventos del navegador + telemetría pasiva de peticiones HTTP + sondeo activo `/api/sync/ping` (0 SQL).
- **Gestión de Cola (`SyncQueueService`):**
  - FIFO, backoff exponencial, locks entre pestañas con `BroadcastChannel` y `localStorage`.
