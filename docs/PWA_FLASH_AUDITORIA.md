# AuroraStore — Auditoría y Línea Base PWA (Fase F1)
**Fecha:** 28 de Octubre de 2026  
**Agente:** Antigravity (Gemini Flash 3.8)  
**Alcance:** Frontend Angular PWA (Iteración 2 — Fase F1 a F5)  
**Objetivo:** Diagnóstico del estado actual de la PWA, mecanismos de caché, aislamiento multitenant, rendimiento y plan de trabajo delimitado sin tocar operaciones transaccionales reservadas para Argon.

---

## 1. Inspección de la Estructura Real de Angular y PWA

### 1.1. Manifiesto y Metadatos de Instalabilidad
- **Archivo:** `frontend/public/manifest.webmanifest`
- **Configuración verificada:**
  - `start_url: "/"` y `scope: "/"` configurados correctamente para cubrir toda la SPA.
  - `display: "standalone"`, `orientation: "portrait-primary"`.
  - Tematización: `theme_color: "#d97706"`, `background_color: "#09090b"`.
  - Iconos: 9 resoluciones PNG presentes en `frontend/public/icons/` (desde 72x72 hasta 512x512, incluyendo variante `maskable` de 512x512).
  - Accesos directos (shortcuts): Rutas `/catalogo` y `/mis-reservas`.
- **Integración HTML:** `frontend/src/index.html` declara `<link rel="manifest" href="manifest.webmanifest">`, `<meta name="theme-color">` y etiquetas para Apple iOS (`apple-mobile-web-app-capable`).

### 1.2. Service Worker (`frontend/public/sw.js`)
- **Versión:** `SW_VERSION = '2.0.0'`.
- **Estrategias implementadas:**
  1. **App Shell (`aurora-shell-v2.0.0`):** Pre-caché de `/`, `/index.html`, `/manifest.webmanifest`, `favicon.ico` y los íconos primarios (192 y 512).
  2. **Navegación SPA:** Modo `navigate` con fallback a `/index.html` en caso de pérdida de red, y página 503 informativa de emergencia si el shell no estuviera descargado.
  3. **Recursos estáticos versionados (`aurora-static-v2.0.0`):** `Cache-First` para `.js`, `.css`, fuentes y `.webmanifest`.
  4. **Imágenes de catálogo (`aurora-images-v2.0.0`):** `Stale-While-Revalidate` con cuota máxima acotada (`MAX_CACHED_IMAGES = 120`).
- **Seguridad y exclusiones estrictas (Reglas #5 y #7):**
  - La función `isApiOrAuthenticatedRequest()` ignora y **nunca almacena** peticiones `/api/*`, WebSockets `/ws/*`, peticiones no-GET ni ninguna petición con cabecera `Authorization`.
  - Evita mezclar datos de negocio multitenant en `CacheStorage`.

### 1.3. Almacenamiento Local Seguro (`IndexedDbService`)
- **Base de datos:** `aurora_store_pwa_db` (Versión 1).
- **Stores disponibles:**
  - Lectura de catálogo: `products`, `product_details`, `catalog_filters`, `branches`, `stock_snapshots`.
  - Operaciones locales / offline: `cart_drafts`, `pending_operations`, `sync_attempts`, `metadata`.
- **Aislamiento Multitenant y Seguridad:**
  - Ámbitos públicos particionados por tenant: `public|e:<id_empresa>`.
  - Ámbitos privados particionados por usuario, empresa y sucursal: `u:<id_usuario>|e:<id_empresa>|b:<id_sucursal>`.
  - Métodos `purgeUserData(userId)` y `purgeAllPrivateData()` integrados en `AuthService.cerrarSesion()` para prevenir fuga de datos entre sesiones o tenants.
  - Fallback en memoria transparente (`memoryFallback`) si IndexedDB está bloqueado (modo incógnito restrictivo o cuota excedida).

### 1.4. Enrutamiento, Guards e Interceptores
- **Guards:**
  - `authGuard`: Comprueba `usuario` y `tokenExpirado()` mediante el reclamo local `exp` del JWT. Valida roles de administración sin requerir llamadas al servidor si la sesión está activa localmente.
  - `permissionGuard`: Refresca permisos con TTL de 15 segundos (`permisosCache$`). Posee fallback a sesión local cuando el backend no responde.
- **Interceptores:**
  - `authInterceptor`: Inyecta Bearer token en rutas de API.
  - `errorInterceptor`: Gestiona errores HTTP. No cierra sesión en errores de red (`status === 0`); únicamente procesa 401 en endpoints protegidos cuando hay token. Notifica eventos a `NetworkStatusService`.

---

## 2. Verificación de Optimizaciones Previas

| Optimización | Ubicación | Estado Verificado |
| :--- | :--- | :--- |
| **Paginación lado servidor** | `CatalogoPublicoService` (`limit`, `offset`) | Implementado y preservado. |
| **Lazy loading de rutas** | `frontend/src/app/app.routes.ts` | 100% de rutas admin y catálogo con `loadComponent`. |
| **Prevención de duplicación de peticiones** | `AuthService.refrescarPermisos` (TTL 15s) | Operativo con `shareReplay` / observables cacheados. |
| **Carga diferida de imágenes** | `ProductoCardComponent` | Atributo `loading="lazy"` en tarjetas de catálogo. |
| **Filtros en backend** | FastAPI `/api/catalogo/filtros` y `/productos` | Respeta parámetros de PostgreSQL. |

---

## 3. Mecanismo Actual de Caché y Políticas de Expiración

- **Estrategia A (Cache-on-Navigation):**
  - Al navegar por el catálogo, cada página (`page_e:1_limit=12&offset=0...`) se guarda en el store `products` con un TTL de 24 horas (`CATALOG_TTL_MS = 86400000`).
  - Si el usuario pierde conexión, `resolverCatalogoOffline()` busca la consulta exacta o consolida los productos únicos ya descargados de ese tenant (`CU05W`), aplicando filtros en memoria.
- **Aislamiento Multitenant:**
  - Las consultas offline filtran estrictamente por `scope_key` (`public|e:1`). No se mezclan productos de distintas empresas.
- **Datos Sensibles:**
  - Ni contraseñas ni tokens JWT se guardan en IndexedDB ni en CacheStorage.
  - El token JWT se conserva únicamente en `localStorage` / memoria para la sesión activa del navegador.

---

## 4. Línea Base y Mediciones (Build de Producción)

- **Comando ejecutado:** `npm run build` en `frontend/`
- **Resultados de compilación:**
  - **Tiempo de build:** ~3.2 segundos.
  - **Tamaño total transferido inicial (App Shell):** `146.35 kB` (raw: `501.99 kB`).
  - **Chunk principal (`main-*.js`):** `107.82 kB` (raw: `373.18 kB`).
  - **Estilos globales (`styles-*.css`):** `24.44 kB` (raw: `100.99 kB`).
  - **Chuncks perezosos de módulos:** promedio entre `2 kB` y `18 kB` por pantalla.
- **Suite de pruebas automatizadas:**
  - `python -B -m unittest discover -s tests -p "test_*.py" -v`:
  - 40 pruebas ejecutadas en 31.414 segundos: **40/40 PASADAS (100% OK)**.

---

## 5. Hallazgos Críticos y Oportunidades de Mejora (Flash Scope)

1. **Registro del Service Worker inactivo:**
   - `PwaUpdateService` define `initServiceWorker()`, pero ningún componente raíz (`App`) lo estaba invocando en el arranque del navegador. Se debe conectar en `App.ngOnInit()`.
2. **Error 404 en chunks obsoletos (`chunk-*.js`):**
   - Cuando se compila una nueva versión, los hashes de los chunks cambian. Sesiones abiertas con HTML viejo piden chunks que devuelven 404. El SW debe capturar este estado y `PwaUpdateService` debe ofrecer una actualización limpia sin bucles ni congelar la pantalla.
3. **Indicador de red desconectado en el panel administrativo:**
   - El header de `AdminLayoutComponent` tenía un badge estático ("Sistema Operativo") que no reflejaba `NetworkStatusService`. Si se pierde internet, el panel no alertaba adecuadamente y seguía intentando llamadas repetitivas.
4. **Verificación redundante de permisos offline:**
   - `permissionGuard` llamaba a `refrescarPermisos()` en cada clic de navegación incluso sin red, generando errores `status === 0` en consola innecesariamente.
5. **Precarga selectiva ausente:**
   - Si un usuario ingresaba a la PWA por primera vez y perdía conexión antes de entrar al catálogo, no había datos precargados en IndexedDB. Se debe implementar una precarga no bloqueante en tiempo ocioso (`requestIdleCallback`) para la página 1 y filtros del tenant activo.
6. **Estado vacío honesto en catálogo:**
   - Cuando no hay productos offline, el catálogo mostraba un mensaje genérico ("No se encontraron prendas") en lugar de informar con claridad que ese contenido no fue descargado previamente.

---

## 6. Plan de Archivos Afectados (Fases F2 a F5)

1. `frontend/src/app/core/network/network-status.service.ts`: Exponer señales de diagnóstico y estado offline detallado.
2. `frontend/src/app/interceptors/error-interceptor.ts`: Garantizar que errores de red (`status === 0`), timeouts y 5xx jamás cierren sesión ni confundan con 401/403.
3. `frontend/src/app/guards/permission-guard.ts`: Evitar peticiones HTTP de permisos cuando `!networkStatus.isOnline()`, validando con la sesión local.
4. `frontend/src/app/layouts/admin-layout/admin-layout.ts` y `.html`: Vincular estado real de conectividad, pausar sondeos en offline y mostrar banner claro de sesión activa pero módulo limitado.
5. `frontend/public/sw.js`: Manejo de chunks 404 con notificación de actualización sin romper navegación.
6. `frontend/src/app/core/pwa/pwa-update.service.ts`: Manejo de actualización segura y captura de chunks obsoletos.
7. `frontend/src/app/app.ts`: Inicializar Service Worker y precarga selectiva en tiempo ocioso.
8. `frontend/src/app/services/catalogo-publico.ts`: Incorporar `precargarCatalogoInicial()` con `requestIdleCallback` y aviso de advertencia de stock/precios.
9. `frontend/src/app/pages/catalogo/catalogo.html`: Estado vacío honesto para catálogo offline y advertencia explícita de precios/stock.

