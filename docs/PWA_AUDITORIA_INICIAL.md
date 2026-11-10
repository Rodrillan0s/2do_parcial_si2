# AuroraStore — Auditoría Inicial para Refactorización Progresiva a Angular PWA Offline-First (Iteración 2)

**Fecha:** 28 de Octubre de 2026  
**Autor:** Antigravity  
**Alcance:** Inspección técnica del repositorio real (`frontend/` Angular y `backend/` FastAPI + PostgreSQL) previa a la implementación de las Fases A–E de la Iteración 2.

---

## 1. Estado Actual del Frontend Angular y Configuración de Compilación

| Aspecto | Estado Real Verificado en el Repositorio | Archivos de Referencia |
| :--- | :--- | :--- |
| **Versión de Angular y Builder** | `@angular/core: ^21.2.0`, `@angular/router: ^21.2.0`, `@angular/build: ^21.2.14` con builder `@angular/build:application`. TypeScript `~5.9.2`, RxJS `~7.8.0`, Tailwind CSS `^3.4.19`. | [`frontend/package.json`](../frontend/package.json), [`frontend/angular.json`](../frontend/angular.json) |
| **Modo de Renderizado** | **SPA pura en cliente** (`browser: "src/main.ts"`). Aunque existen archivos residuales `main.server.ts` y `server.ts`, `angular.json` no configura `server` ni `prerender` en `architect.build.options`, y [`app.config.ts`](../frontend/src/app/app.config.ts) provee únicamente `provideBrowserGlobalErrorListeners()`, `provideRouter(routes)` y `provideHttpClient(withInterceptors([authInterceptor, errorInterceptor]))`. | [`frontend/src/app/app.config.ts`](../frontend/src/app/app.config.ts), [`frontend/angular.json`](../frontend/angular.json) |
| **Enrutamiento y Lazy Loading** | **100% de las rutas de nivel superior e hijas administrativas** utilizan `loadComponent` (carga diferida) tras la optimización de la Iteración 1. | [`frontend/src/app/app.routes.ts`](../frontend/src/app/app.routes.ts) |
| **Soporte PWA Actual** | **Inexistente (0%).** No existe `manifest.webmanifest`, no está instalado `@angular/service-worker`, no existe `ngsw-config.json` ni `sw.js`, y [`frontend/public/`](../frontend/public/) solo contiene `favicon.ico`, `car.png`, `ficct.jpg` y `sos.png`. [`src/index.html`](../frontend/src/index.html) tampoco incluye `<link rel="manifest">` ni `<meta name="theme-color">`. | [`frontend/src/index.html`](../frontend/src/index.html), [`frontend/public/`](../frontend/public/) |
| **Persistencia Local Actual** | **Solo `localStorage`** para sesión y preferencias visuales (`token`, `usuario`, `aurora_selected_company`, `aurora_selected_branch`, `preferencia_tema_oscuro`). **No existe IndexedDB**, ni adaptador de almacenamiento local, ni cola de operaciones pendientes (`pending_operations`), ni coordinación entre pestañas (`BroadcastChannel` / `navigator.locks`). | [`frontend/src/app/services/auth.ts`](../frontend/src/app/services/auth.ts), [`frontend/src/app/services/theme.ts`](../frontend/src/app/services/theme.ts) |
| **Dependencias Externas de Almacenamiento** | No están instaladas `dexie` ni `idb`. Siguiendo la Regla No Negociable #10 (*"No instalar bibliotecas sin necesidad"*), se utilizará la **API nativa `indexedDB` del estándar Web** encapsulada en un adaptador tipado propio con migraciones por versión, `0 KB` de dependencias externas y soporte completo para pruebas unitarias. | [`frontend/package.json`](../frontend/package.json) |

---

## 2. Mapa de Servicios HTTP, Interceptores, Guards y Cachés Existentes

### 2.1 Interceptores y Guards
- [`authInterceptor`](../frontend/src/app/interceptors/auth-interceptor.ts): Adjunta `Authorization: Bearer <token>` a todas las solicitudes HTTP excepto `/api/auth/login`, `/api/auth/register`, `/api/auth/forgot-password` y `/api/auth/reset-password`.
- [`errorInterceptor`](../frontend/src/app/interceptors/error-interceptor.ts): Captura respuestas `401 Unauthorized` en rutas protegidas y ejecuta `authService.cerrarSesion()`, redirigiendo a `/`. **Observación crítica para PWA:** Los errores de red (`status === 0` o `ProgressEvent`) **no** disparan cierre de sesión, lo cual es correcto y permite mantener la sesión activa cuando el usuario pierde conectividad temporalmente.
- [`authGuard`](../frontend/src/app/guards/auth-guard.ts), [`permissionGuard`](../frontend/src/app/guards/permission-guard.ts) y [`scopeGuard`](../frontend/src/app/guards/scope-guard.ts):
  - `permissionGuard` invoca `authService.refrescarPermisos()` (`GET /api/rbac/mis-permisos` con caché de 15 s) y ya cuenta con un bloque `catchError` que recurre a los permisos de la sesión local si falla la red, permitiendo navegar entre vistas administrativas ya cargadas durante microcortes.

### 2.2 Cachés en Memoria de Aplicación (Iteración 1)
Los siguientes servicios administrativos ya cuentan con caché en memoria aislado por clave compuesta `u:${uid}|e:${id_empresa}`, deduplicación en vuelo (`shareReplay(1)`) e invalidación inmediata en mutaciones CRUD:
- [`CategoriasService`](../frontend/src/app/services/categorias.ts) (TTL 60 s)
- [`TallasColoresService`](../frontend/src/app/services/tallas-colores.ts) (TTL 60 s)
- [`EmpresaService`](../frontend/src/app/services/empresa.ts) (TTL 60 s)
- [`SucursalService`](../frontend/src/app/services/sucursales.ts) (TTL 45 s)
- [`CiudadService`](../frontend/src/app/services/ciudades.ts) (TTL 120 s)
- [`RbacService`](../frontend/src/app/services/rbac.ts) (TTL 60 s)
- [`SaasService`](../frontend/src/app/services/saas.ts) (TTL 20–120 s)
- [`KpisService`](../frontend/src/app/services/kpis.ts) (TTL 30 s)

### 2.3 Servicios del Flujo E-Commerce Público y de Cliente (Sin Caché Offline ni Optimización Previa)
1. [`CatalogoPublicoService`](../frontend/src/app/services/catalogo-publico.ts):
   - Consume `GET /api/catalogo/tenants`, `GET /api/catalogo/filtros`, `GET /api/catalogo/productos`, `GET /api/catalogo/productos/{id}` y `GET /api/catalogo/variantes/{id}/disponibilidad`.
   - **Estado actual:** Sin caché en memoria ni persistencia en IndexedDB. Cada visita o cambio de filtro realiza peticiones directas sin fallback offline ni metadatos de antigüedad (`fetched_at`).
2. [`CarritoService`](../frontend/src/app/services/carrito.ts):
   - Consume `GET /api/carrito`, `POST /api/carrito/items`, `PUT /api/carrito/items/{id_detalle}`, `DELETE /api/carrito/items/{id_detalle}` y `DELETE /api/carrito/vaciar`.
   - **Hallazgo de petición duplicada al iniciar:** Tanto [`NavbarComponent.ngOnInit`](../frontend/src/app/components/navbar/navbar.ts) como [`CarritoDrawerComponent.ngOnInit`](../frontend/src/app/components/carrito-drawer/carrito-drawer.ts) se montan simultáneamente en [`App`](../frontend/src/app/app.html) y ambos llaman a `this.carritoService.cargarCarrito().subscribe()`, disparando **2 peticiones `GET /api/carrito` idénticas en paralelo**.
   - **Estado actual offline:** Si el usuario intenta agregar/modificar/eliminar un ítem del carrito sin conexión, la petición HTTP falla inmediatamente y se pierde la acción.
3. [`ReservaService`](../frontend/src/app/services/reserva.ts):
   - Consume `POST /api/reservas`, `GET /api/reservas/mis-reservas`, `GET /api/reservas/{id}` y `POST /api/reservas/{id}/cancelar`.
   - **Estado actual offline:** No permite guardar solicitudes de reserva pendientes en cola local ni advierte que la confirmación de stock requiere validación en línea.
4. [`PedidoService`](../frontend/src/app/services/pedido.ts) y [`PagoService`](../frontend/src/app/services/pago.ts):
   - Gestionan `POST /api/pedidos` y pagos (`POST /api/pagos/...`). Conforme a la Regla No Negociable #6, la confirmación de compra y pagos electrónicos requieren validación estrictamente online.
5. [`CajaService`](../frontend/src/app/services/caja.ts) y [`CajaComponent`](../frontend/src/app/pages/caja/caja.ts) (CU24W POS):
   - Registra apertura/arqueo/cierre de caja y ventas presenciales (`POST /api/pos/ventas`) con descuento inmediato de inventario y generación de comprobante fiscal.

---

## 3. Estructura Modular del Backend y Auditoría de Endpoints de Catálogo y Carrito

### 3.1 Endpoints Existentes Relevantes para la Iteración 2
| Módulo Backend | Archivo de Rutas | Endpoints | Estado y Observaciones de Rendimiento / Sincronización |
| :--- | :--- | :--- | :--- |
| **Catálogo Público** (`catalogo`) | [`catalogo_routes.py`](../backend/app/modules/catalogo/routes/catalogo_routes.py) → [`catalogo_repos.py`](../backend/app/modules/catalogo/repos/catalogo_repos.py) | `GET /api/catalogo/tenants`<br>`GET /api/catalogo/filtros`<br>`GET /api/catalogo/productos`<br>`GET /api/catalogo/productos/{id}`<br>`GET /api/catalogo/variantes/{id}/disponibilidad` | - `/api/catalogo/filtros` ejecuta **7 consultas SQL secuenciales** (`obtener_info_tenant` + 6 consultas en `obtener_filtros_disponibles`).<br>- `/api/catalogo/productos` ejecuta **4 consultas SQL** y usa 5 subconsultas correlacionadas por fila.<br>- `/api/catalogo/productos/{id}` ejecuta **7 consultas SQL secuenciales** (`q_prod`, `q_promocion`, `q_imgs`, `q_vars`, `q_ra`, `q_sucs`, `q_inv`). |
| **Catálogo Admin** (`catalogo`) | [`productos_routes.py`](../backend/app/modules/catalogo/routes/productos_routes.py) | `GET /api/productos`<br>`GET /api/productos/{id}` | Ya optimizado en Iteración 1 con CTE paginada (`COUNT(*) OVER()`) + `LEFT JOIN LATERAL` (**1 query SQL** en caché caliente, `15.8 KB` por página de 20). |
| **Carrito** (`ecommerce`) | [`carrito_routes.py`](../backend/app/modules/ecommerce/routes/carrito_routes.py) → [`carrito_repos.py`](../backend/app/modules/ecommerce/repos/carrito_repos.py) | `GET /api/carrito`<br>`POST /api/carrito/items`<br>`PUT /api/carrito/items/{id}`<br>`DELETE /api/carrito/items/{id}`<br>`DELETE /api/carrito/vaciar` | **Patrón N+1 detectado en `consultar_carrito_completo`:** Abre conexiones adicionales dentro del bucle `for r in filas` llamando a `obtener_stock_total_variante(id_var, id_empresa)` por cada prenda del carrito. |
| **Reservas** (`reservas`) | [`reserva_routes.py`](../backend/app/modules/reservas/routes/reserva_routes.py) → [`reserva_repos.py`](../backend/app/modules/reservas/repos/reserva_repos.py) | `POST /api/reservas`<br>`GET /api/reservas/mis-reservas`<br>`POST /api/reservas/{id}/cancelar` | Valida vigencia SaaS (`exigir_vigencia`), bloquea filas de inventario y descuenta `stock_disponible` / incrementa `stock_reservado` en transacción atómica. |
| **Sincronización Idempotente** | *(Por incorporar de forma compatible)* | `GET /api/sync/health` (o `/api/health`)<br>`POST /api/sync/batch` / cabeceras `X-Operation-Id` | Actualmente no existe tabla ni registro de idempotencia de operaciones (`operation_id` UUID) para evitar que el reintento de una operación en cola duplique efectos en servidor. |

---

## 4. Clasificación de Datos y Particionamiento de Seguridad SaaS

Para cumplir estrictamente las Reglas No Negociables #4, #5 y #7:

| Categoría de Dato | Ejemplos | Ámbito de Particionamiento en IndexedDB | Política de Retención y Limpieza |
| :--- | :--- | :--- | :--- |
| **1. Recursos Estáticos del Shell** | `index.html`, bundles JS/CSS con hash (`main-*.js`, `chunk-*.js`), fuentes, íconos del manifest. | `CacheStorage` del Service Worker (`aurora-shell-v1`, `aurora-assets-v1`). | Actualización controlada por versión del Service Worker; nunca almacena respuestas de `/api/*`. |
| **2. Catálogo Público Multitenant** | Tiendas activas (`/api/catalogo/tenants`), filtros (`/api/catalogo/filtros`), páginas visitadas (`/api/catalogo/productos`), detalles de prenda (`/api/catalogo/productos/{id}`). | Particionado por `tenant_id` (`id_empresa`) y clave de consulta/página (`scope_key = public|e:${id_empresa}`). | Máximo acotado (p. ej. últimas 15 páginas de catálogo y últimos 60 detalles de producto visitados por tenant, TTL suave de 30 min para revalidación y expiración dura de 24 h). |
| **3. Snapshots de Disponibilidad por Sucursal** | `sucursales_stock` y `/api/catalogo/variantes/{id}/disponibilidad`. | Particionado por `tenant_id` (`id_empresa`) + `id_producto` / `id_variante`. | Incluye siempre `fetched_at` obligatorio. En modo offline se muestra con **advertencia explícita de dato referencial potencialmente desactualizado**; nunca garantiza existencias. |
| **4. Datos Privados de Usuario + Tenant** | Páginas visitadas de `/admin/productos`, borradores de carrito (`cart_drafts`), mis reservas (`mis_reservas`), cola de operaciones pendientes (`pending_operations`) e historial de intentos (`sync_attempts`). | Particionado estrictamente por **`user_id` (`id_usuario`) + `tenant_id` (`id_empresa`) + `branch_id` (`id_sucursal` cuando aplique)**: `u:${uid}|e:${id_empresa}`. | **Limpieza inmediata** al ejecutar `cerrarSesion()` (logout), ante respuesta `401`, o al cambiar de usuario/tenant, garantizando **cero fugas entre cuentas o empresas**. |
| **5. Datos Prohibidos en Caché / Cola Offline** | Tokens JWT en `CacheStorage`, contraseñas, tarjetas/datos bancarios, confirmaciones de pago (`CU09W`/`CU27W`) o ventas POS confirmadas (`CU24W`). | **Prohibido en IndexedDB y CacheStorage.** | Nunca se almacenan en IndexedDB ni en Service Worker. |

---

## 5. Limitaciones de Hosting y Despliegue para PWA

- **HTTPS y Alcance del Service Worker:** Service Workers e instalación PWA requieren contexto seguro (`https://` en producción como Render `https://aurora-store-d20q.onrender.com`, o `http://localhost` / `http://127.0.0.1` en pruebas locales). El archivo `sw.js` debe servirse desde la raíz (`/sw.js`) con `Scope: /` y sin caché inmutable del navegador (`Cache-Control: no-cache`).
- **Rutas SPA (Fallback):** Al recargar una ruta profunda como `/catalogo` o `/admin/productos` sin conexión, el Service Worker debe responder con el `index.html` cacheado del App Shell para que el router de Angular resuelva la ruta localmente.

---

## 6. Línea Base de Rendimiento (Antes de Iteración 2)

Mediciones reales verificadas sobre el build de producción (`npm run build`) y clúster PostgreSQL aislado + proyección con RTT remoto (`117.11 ms`):

| Métrica / Flujo | Estado Base (Fin de Iteración 1 / Inicio Iteración 2) | Observaciones / Oportunidades Detectadas |
| :--- | :--- | :--- |
| **Bundle Inicial (`Initial total`)** | **632.53 kB** raw (**134.98 kB** transfer) | `main`: `116.37 kB` raw (`22.26 kB` transfer). Debe mantenerse sin regresión significativa (sin librerías pesadas). |
| **Admin `/admin/productos` (Online)** | `4` requests en 1ª visita / `1` request en recurrente; `1` query SQL caliente (`8.11 ms` local / `~155 ms` remoto); payload `15.8 KB` (`3.4 KB` GZip). | Si se pierde la conexión (`Offline`), actualmente muestra error vacío y pierde la tabla. Con IndexedDB mostrará la última página consultada con aviso de antigüedad. |
| **Público `/catalogo` (Online)** | **4–5 requests** al entrar (`tenants`, `filtros`, `productos`, y **2 llamadas duplicadas** a `GET /api/carrito` si hay sesión). | - `GET /api/catalogo/filtros` ejecuta **7 queries SQL**.<br>- `GET /api/catalogo/productos` ejecuta **4 queries SQL**.<br>- `GET /api/carrito` se dispara **2 veces** al iniciar (`Navbar` + `CarritoDrawer`) y tiene N+1 en stock por ítem. |
| **Detalle de Prenda `/api/catalogo/productos/{id}`** | `1` request HTTP que ejecuta **7 queries SQL** secuenciales en backend. | En modo offline falla y redirige. Con IndexedDB cargará instantáneamente si ya fue visitado, advirtiendo la fecha del último stock conocido. |
| **Navegación Offline (1ª visita vs. Recurrente)** | **Falla total (`ERR_INTERNET_DISCONNECTED`)** tanto en primera visita como en visita recurrente. | Con Service Worker + IndexedDB: en visita recurrente offline cargará el App Shell (`< 50 ms`) y los datos de catálogo/carrito almacenados localmente. |

---

## 7. Plan de Ejecución Incremental (Fases A → E)

1. **Fase A — PWA Base Instalable:** Crear `manifest.webmanifest`, íconos vectoriales/PNG propios de AuroraStore en `public/icons/`, `public/sw.js` con estrategia *App Shell + Static Assets* (excluyendo estrictamente `/api/*`), servicio `PwaUpdateService` para actualización controlada sin pérdida de estado, e integración en `index.html` y `main.ts`.
2. **Fase B — Persistencia IndexedDB Particionada (`core/storage/`):** Implementar `IndexedDbService` (nativo, versionado `v1`, almacenes `products`, `product_details`, `catalog_filters`, `branches`, `stock_snapshots`, `cart_drafts`, `pending_operations`, `sync_attempts`, `metadata`), integrar caché offline/stale-while-revalidate en `CatalogoPublicoService` y `ProductosService` con indicadores de antigüedad, corregir la llamada duplicada de `CarritoService` y optimizar las consultas SQL de `catalogo_repos.py` y `carrito_repos.py`.
3. **Fase C — Conectividad Real y Cola de Operaciones (`core/network/` y `core/sync/`):** Implementar `NetworkStatusService` (combinando eventos del navegador + *heartbeat* real `/api/sync/ping` + interceptación pasiva de fallos de red), `SyncQueueService` con bloqueo entre pestañas (`BroadcastChannel` + `navigator.locks` / lease en storage) y componente visual accesible de estado de conexión y bandeja de operaciones pendientes (**CU37W**).
4. **Fase D — Sincronización Idempotente y Resolución de Conflictos (**CU38W / CU39W**):** Implementar endpoint transaccional e idempotente en FastAPI (`/api/sync/operations` y soporte de `operation_id` UUID) con validación completa de JWT/RBAC/tenant/stock, detección de conflictos (`STOCK_INSUFFICIENT`, `PRICE_CHANGED`, `PRODUCT_INACTIVE`, `VERSION_CONFLICT`) y UI de resolución en Angular, más documentación en `docs/PWA_CONTRATO_SYNC.md`.
5. **Fase E — Integración Comercial Segura (`CU04W–CU10W`, `CU09W/CU27W`, `CU24W`), Pruebas Automatizadas y Documentación Final:** Asegurar que carrito (`CU08W`) y solicitudes de reserva en borrador (`CU10W`) funcionen con trazabilidad clara, que compras/pagos (`CU09W`/`CU27W`) y ventas POS (`CU24W`) exijan validación online, ejecutar todas las pruebas automatizadas y generar `docs/PWA_ARQUITECTURA.md`, `docs/PWA_PRUEBAS.md` y `docs/PWA_RENDIMIENTO_ANTES_DESPUES.md`.

