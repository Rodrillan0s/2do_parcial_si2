# AuroraStore — Diagnóstico de Rendimiento y Auditoría de Latencia (Fase 1)

**Fecha:** 28 de Octubre de 2026  
**Entorno de Medición:** Windows 11, Node v20+, Python 3.14, FastAPI Backend (`uvicorn` puerto 5000), PostgreSQL Remoto (`147.15.29.190:5433`, esquema `comercio`) y Clúster PostgreSQL Local Aislado (`LocalPostgres` para pruebas deterministas), Angular 19 PWA (puerto 4200).  
**Identidad de Prueba:** Superadmin / Administrador (`id_usuario: 4`) y Administrador de Tienda (`id_empresa: 1`).

---

## 1. Resumen Ejecutivo de Diagnóstico

La auditoría integral de punta a punta (Angular PWA → Red HTTP → FastAPI/Security/TenantGuard → Pool `psycopg2` → PostgreSQL) determinó que la lentitud perceptible al entrar en pantallas administrativas (>6 segundos en **Productos y Prendas** y >5 segundos en **Inventario**) **no proviene de una única consulta aislada**, sino del efecto multiplicador de **seis factores combinados**:

1. **Latencia de Red Base (RTT) hacia PostgreSQL Remoto + Doble RTT por `rollback()` en `close_connection()`:**
   - La base de datos configurada opera en un host remoto (`147.15.29.190:5433`) con un *handshake* TCP mínimo medido de **117.11 ms**.
   - En [`backend/app/core/postgres.py`](../../backend/app/core/postgres.py), `psycopg2` abre conexiones con `autocommit = False` por defecto. Toda consulta de lectura (`get_data`) inicia implícitamente un bloque `BEGIN` en PostgreSQL (~150 ms) y, al cerrar la conexión en `close_connection()`, ejecuta incondicionalmente `self.conn.rollback()`, enviando un segundo comando de red `ROLLBACK` (~150 ms) antes de devolver la conexión al pool (`putconn`). Esto duplica la latencia de cada lectura individual a **~303–320 ms**.
   - Adicionalmente, `PostgreSQL.create_connection()` contenía código duplicado de reconexión (líneas 89–115) y el pool arrancaba con `minconn=1`, obligando a abrir nuevas conexiones TCP bajo ráfagas concurrentes de 6–8 peticiones al entrar a una vista.

2. **Sobrecarga Transversal de Autorización en Cada Request (`_contexto_vigente` + `tenant_guard.py`):**
   - En **cada petición HTTP autenticada**, [`security.py:_contexto_vigente`](../../backend/app/core/security.py) consultaba en base de datos el contexto completo del usuario (`session_repos.obtener_contexto_actual(uid)` y `rbac_repos.obtener_permisos_efectivos_usuario(uid)`, consumiendo **~706.71 ms** antes de unificar la consulta, y **~305 ms** tras unificarla pero aún sin caché en memoria).
   - Acto seguido, en el mismo request, [`tenant_guard.py`](../../backend/app/core/tenant_guard.py) (`resolver_tenant_operacion` y `obtener_sucursales_autorizadas`) abría una **segunda conexión** a PostgreSQL para volver a consultar `SELECT estado FROM empresa` o `SELECT id_sucursal FROM t_sucursal / t_usuario_sucursal`, aun cuando `_contexto_vigente` ya había recuperado `estado_empresa` y `sucursales` del usuario.

3. **Ráfagas de Peticiones Concurrentes y Peticiones Innecesarias al Entrar a Vistas en Angular:**
   - Al entrar a `/admin/productos`, Angular dispara hasta **8 solicitudes HTTP**:
     - Desde `permissionGuard`: `GET /api/rbac/mis-permisos` (en caché fría).
     - Desde `AdminLayoutComponent`: `GET /api/sucursales/`, `GET /api/mi-empresa/plan`, `GET /api/kpis/tenants` y `/api/ws/notificaciones`.
     - Desde `ProductosComponent.cargarDatosIniciales()`: `GET /api/empresas/`, `GET /api/productos`, `GET /api/categorias/?solo_activas=true`, `GET /api/tallas/?solo_activas=true` y `GET /api/colores/?solo_activos=true`.
   - Los catálogos `tallas` y `colores` se descargan siempre al abrir la pantalla de Productos aunque **solo se utilizan dentro del modal de Crear/Editar Producto**.
   - En `/admin/inventario` (`ListaInventarioComponent.ngOnInit`), la suscripción simultánea a dos `BehaviorSubject` (`companyChanged$` y `branchChanged$`) provocaba doble emisión inicial de `recargarInventario$.next()` y recargas redundantes cuando `AdminLayoutComponent` resolvía la sucursal activa.
   - En `/admin/tallas-colores`, se disparaban simultáneamente `GET /api/tallas/` y `GET /api/colores/` aunque inicialmente solo es visible la pestaña `TALLAS`.
   - En `/admin/usuarios`, `ngOnInit` ejecutaba un bucle de espera activa (`setTimeout(50)` hasta 10 intentos) y consultaba `/api/empresas/` directamente con `HttpClient` ignorando `EmpresaService`.

4. **Consultas SQL Subóptimas, Subconsultas Correlacionadas y Falta de Paginación Real en Servidor:**
   - **Productos (`productos_repos.listar_productos`)**:
     - Originalmente ejecutaba **5 subconsultas correlacionadas por fila** sobre las 132 prendas (~660 subconsultas).
     - Aun al usar `LEFT JOIN (...) img_agg` y `var_agg`, las subconsultas agrupaban la tabla completa `t_producto_imagen` y `t_producto_talla_color` de todos los tenants antes de aplicar el filtro/límite de productos, y el servicio devolvía `"total": len(productos)` en lugar del conteo total real (`COUNT(*) OVER()`), impidiendo la paginación en servidor.
     - En creación/edición de productos (`productos_services.py` y `productos_repos.py`), existen bucles N+1 en `_validar_tallas_activas`, `_validar_colores_activos`, `validar_relaciones_tenant` y `sincronizar_variantes_producto` (un `SELECT`/`INSERT`/`UPDATE` + `commit=True` por cada variante).
   - **Inventario (`inventario_repos.listar_inventario`)**:
     - Ejecuta **3 consultas SQL separadas con el mismo bloque de 4–6 JOINs** (`query_count`, `query_items`, `query_totales`) por cada cambio de página o filtro. `query_count` y `query_totales` escanean exactamente el mismo conjunto filtrado en dos idas y vueltas distintas a PostgreSQL, e incluyen `LEFT JOIN t_talla` y `LEFT JOIN t_color` incluso cuando no se filtra por talla ni color.
   - **Categorías (`categorias_repos.obtener_categorias`) y Tallas/Colores (`tallas_colores_repos.py`)**:
     - Ejecutan subconsultas correlacionadas `COUNT(*)` por cada fila (`total_productos`, `total_subcategorias`, `total_variantes`) sin agregación previa ni índices compuestos.

5. **Sobrecarga de Renderizado DOM, Imágenes Originales y Bundles en Angular PWA:**
   - `app.routes.ts` importaba de forma ansiosa (`eager`) componentes pesados de nivel superior (`ExplorarComponent`, `CatalogoComponent`, `AdminLayoutComponent`, `PerfilComponent`, `CheckoutComponent`, `PagoComponent`, etc.) y `ListaSucursalesComponent` importaba estáticamente `MapaSucursalComponent` (con Leaflet).
   - `src/styles.css` contenía un `@import url('https://fonts.googleapis.com/...')` duplicado respecto al `<link>` de `src/index.html`, y `index.html` cargaba `<script src="https://unpkg.com/@phosphor-icons/web"></script>` en `<head>` sin `defer`, bloqueando el parseo inicial.
   - En `ProductosComponent`, `ListaCategoriasComponent`, `TallasColoresComponent`, `ListaSucursalesComponent`, `ListaUsuariosComponent` y `SuscripcionesComponent`, los filtros y métricas de cabecera se recalculaban mediante *getters* en cada ciclo de detección de cambios (CD), varias tablas carecían de `trackBy`, y las imágenes en tabla descargaban la resolución completa de Cloudinary sin transformación de miniatura ni `loading="lazy"`.

6. **Ausencia de Compresión HTTP e Instrumentación de Tiempos en Backend:**
   - `app/main.py` no tenía `GZipMiddleware` activo para comprimir payloads JSON grandes, ni cabeceras `Server-Timing` / `X-Request-ID` con medición desglosada de tiempo total vs. tiempo y conteo de consultas SQL.

---

## 2. Trazabilidad Arquitectónica por Pantalla (Fase 1.1)

| Pantalla / Ruta Angular | Componente Principal | Guards en Ruta | Servicios Angular Invocados | Endpoints HTTP Disparados al Entrar | Métodos Backend (Service → Repo) |
| :--- | :--- | :--- | :--- | :--- | :--- |
| **Layout Administrativo** (`/admin/*`) | `AdminLayoutComponent` | `authGuard` | `AuthService`, `SucursalService`, `SaasService`, `KpisService`, `NotificacionesService` | 1. `GET /api/sucursales/`<br>2. `GET /api/mi-empresa/plan`<br>3. `GET /api/kpis/tenants`<br>4. `GET /api/ws/notificaciones`<br>5. `WS /api/ws/notificaciones` | `sucursales_services.listar_sucursales` → `sucursales_repos.obtener_sucursales`<br>`saas_services.obtener_plan_actual_empresa`<br>`kpis_services.obtener_tenants` → `kpis_repos.obtener_resumen_tenants` |
| **1. Productos y Prendas** (`/admin/productos`) | `ProductosComponent` | `authGuard`, `permissionGuard('productos.ver')` | `ProductosService`, `CategoriasService`, `TallasColoresService`, `EmpresaService`, `AuthService` | 1. `GET /api/rbac/mis-permisos` (guard)<br>2. `GET /api/empresas/` (SuperAdmin)<br>3. `GET /api/productos?limit=200`<br>4. `GET /api/categorias/?solo_activas=true`<br>5. `GET /api/tallas/?solo_activas=true`<br>6. `GET /api/colores/?solo_activos=true` | `productos_services.listar_productos` → `productos_repos.listar_productos`<br>`categorias_services.listar_categorias` → `categorias_repos.obtener_categorias`<br>`tallas_colores_services.listar_tallas / listar_colores` |
| **2. Inventario** (`/admin/inventario`) | `ListaInventarioComponent` | `authGuard`, `permissionGuard('inventario.ver')` | `InventarioService`, `SucursalService`, `TallasColoresService`, `EmpresaService`, `AuthService` | 1. `GET /api/empresas/` (SuperAdmin)<br>2. `GET /api/sucursales/`<br>3. `GET /api/tallas/`<br>4. `GET /api/colores/`<br>5. `GET /api/inventario/?pagina=1&limite=20` (x2 por doble suscripción inicial) | `inventario_routes.listar_inventario` → `inventario_repos.listar_inventario` (ejecuta 3 queries SQL: `count`, `items`, `totales`) |
| **3. Categorías** (`/admin/categorias`) | `ListaCategoriasComponent` | `authGuard`, `permissionGuard(['categorias.ver', 'productos.ver'])` | `CategoriasService`, `EmpresaService`, `AuthService` | 1. `GET /api/empresas/` (SuperAdmin)<br>2. `GET /api/categorias/` | `categorias_services.listar_categorias` → `categorias_repos.obtener_categorias` |
| **4. Tallas y Colores** (`/admin/tallas-colores`) | `TallasColoresComponent` | `authGuard`, `permissionGuard(['tallas.ver', 'productos.ver'])` | `TallasColoresService`, `EmpresaService`, `AuthService` | 1. `GET /api/empresas/` (SuperAdmin)<br>2. `GET /api/tallas/`<br>3. `GET /api/colores/` | `tallas_colores_services.listar_tallas` → `tallas_colores_repos.obtener_tallas`<br>`tallas_colores_services.listar_colores` → `tallas_colores_repos.obtener_colores` |
| **5. Sucursales y Ciudades** (`/admin/sucursales`) | `ListaSucursalesComponent` | `authGuard`, `permissionGuard('sucursales.ver')` | `SucursalService`, `CiudadService`, `EmpresaService`, `AuthService` | 1. `GET /api/empresas/`<br>2. `GET /api/ciudades/?solo_activas=false`<br>3. `GET /api/sucursales/` | `sucursales_services.listar_sucursales` → `sucursales_repos.obtener_sucursales`<br>`ciudades_services.listar_ciudades` → `ciudades_repos.obtener_ciudades` |
| **6. Usuarios y Roles** (`/admin/usuarios`) | `ListaUsuariosComponent` | `authGuard`, `permissionGuard('usuarios.ver')` | `UsuariosService`, `RbacService`, `SucursalService`, `HttpClient`, `AuthService` | 1. `GET /api/rbac/roles`<br>2. `GET /api/empresas/` (sin usar `EmpresaService`)<br>3. `GET /api/usuarios/` | `users_services.obtener_usuarios_completos` → `users_repos.obtener_usuarios_completos_por_empresa` |
| **7. Suscripciones** (`/admin/suscripciones`) | `SuscripcionesComponent` | `authGuard`, `permissionGuard('suscripciones.ver')` | `SaasService`, `EmpresaService`, `AuthService` | 1. `GET /api/planes`<br>2. `GET /api/empresas/` (SuperAdmin)<br>3. `GET /api/mi-empresa/plan`<br>4. `GET /api/empresas/{id}/suscripciones` | `saas_services.listar_planes`<br>`saas_services.obtener_plan_actual_empresa`<br>`saas_services.listar_suscripciones_empresa` |

---

## 3. Configuración de Ejecución e Infraestructura (Fase 1.4)

- **Proceso de Servidor (`backend/run.py`):** Uvicorn ejecutándose en proceso único (`workers=1`, `port=5000`, `reload=True` en desarrollo). Los endpoints declarados como funciones síncronas (`def`) se ejecutan en el threadpool de AnyIO/Starlette.
- **Pool de Conexiones (`backend/app/core/postgres.py`):** `psycopg2.pool.ThreadedConnectionPool(minconn=1, maxconn=20)`.
  - Al iniciar con `minconn=1`, una ráfaga de 6–8 solicitudes concurrentes al abrir una vista administrativa obliga al pool a establecer conexiones TCP+SSL nuevas en caliente contra el servidor remoto.
  - Cada instancia de repositorio abre y cierra su propia conexión (`PostgreSQL().create_connection()` / `close_connection()`), por lo que un solo endpoint llega a realizar **entre 2 y 4 checkouts del pool** (`_contexto_vigente` → `tenant_guard` → `service/repo`).
- **Latencia de Red Base ( Backend ↔ PostgreSQL `147.15.29.190:5433` ):**
  - Handshake TCP de 3 vías: **117.11 ms**.
  - Consulta simple con `autocommit=False` + `rollback()` al devolver al pool: **303–320 ms** (2 RTTs de red).
  - Consulta simple en modo `autocommit=True` (sin `ROLLBACK` redundante en lecturas): **~140–155 ms** (1 RTT de red).

---

## 4. Análisis de Consultas PostgreSQL y Planes de Ejecución (Fase 1.5)

Volumen actual verificado en el esquema `comercio`:
- `empresa`: 2 registros | `t_sucursal`: 6 registros | `t_categoria`: 33 registros
- `t_producto`: 132 prendas | `t_producto_imagen`: 145 imágenes | `t_producto_talla_color`: 2,356 variantes
- `t_inventario`: 6,019 registros de existencias

### Hallazgos en Consultas Críticas (`EXPLAIN (ANALYZE, BUFFERS)`):
1. **`productos_repos.listar_productos`**:
   - **Problema 1 (Antes):** 5 subconsultas correlacionadas ejecutadas por cada una de las 132 filas (`Seq Scan` repetitivo sobre `t_producto_imagen` y `t_producto_talla_color`).
   - **Problema 2 (Intermedio):** El reemplazo por `LEFT JOIN (SELECT ... FROM t_producto_imagen GROUP BY id_producto)` fuerza un `Seq Scan` + `HashAggregate` sobre **toda** la tabla `t_producto_imagen` y **toda** la tabla `t_producto_talla_color` (2,356 filas) de todos los tenants antes de paginar.
   - **Problema 3:** No calcula `COUNT(*) OVER() AS total_registros`, por lo que al pasar `limit=24, offset=0`, el backend reporta `total = 24` en vez de `132`.
   - **Solución SQL:** CTE `productos_filtrados` con filtro indexado por tenant/categoría/estado/temporada + `COUNT(*) OVER() AS total_registros` + `ORDER BY ... LIMIT %s OFFSET %s`, seguido de `LEFT JOIN LATERAL` únicamente para las `N` filas de la página actual respaldado por índices compuestos `idx_producto_imagen_prod_principal` e `idx_variante_producto_activo`.
2. **`inventario_repos.listar_inventario`**:
   - **Problema:** Ejecuta 3 consultas separadas (`query_count`, `query_items`, `query_totales`). `query_count` y `query_totales` hacen exactamente el mismo `INNER JOIN` cuádruple sobre las 6,019 filas de `t_inventario`, duplicando el tiempo de base de datos y el RTT de red. Además, `query_count` y `query_totales` incluyen `LEFT JOIN t_talla` y `LEFT JOIN t_color` aunque no se filtre por talla o color.
   - **Solución SQL:** Unificar `query_count` dentro de `query_totales` (`COUNT(*)::int AS total_registros` junto con los `SUM(...)`), eliminando 1 de las 3 consultas completas (reducción inmediata del 33% en queries de inventario) e incluir los `LEFT JOIN t_talla / t_color` en el agregado solo cuando exista filtro de búsqueda/talla/color.
3. **`categorias_repos.obtener_categorias` y `tallas_colores_repos.obtener_tallas / obtener_colores`**:
   - **Problema:** Subconsultas correlacionadas por fila para contar productos, subcategorías y variantes.
   - **Solución SQL:** Reemplazar por `LEFT JOIN` a subconsultas agrupadas filtradas o indexadas por `id_categoria`, `id_padre`, `id_talla`, `id_color`.
4. **Operaciones N+1 en Escritura/Validación de Productos (`productos_services.py` / `productos_repos.py`)**:
   - `_validar_tallas_activas`, `_validar_colores_activos`, `validar_relaciones_tenant` y `sincronizar_variantes_producto` ejecutan consultas individuales dentro de bucles `for`. Con 15 variantes, una edición dispara >30 viajes de red a PostgreSQL (>4.5 segundos).
   - **Solución SQL:** Validación por lotes con `ANY(%s)` en una sola consulta y sincronización de variantes dentro de una única transacción atómica.
5. **Índices Faltantes Identificados (Migración Reversible `002_iter1_perf_indexes`):**
   - `t_producto (id_empresa, activo, id_categoria, fecha_registro DESC)`
   - `t_producto_imagen (id_producto, es_principal DESC, orden ASC, id_imagen ASC)`
   - `t_producto_talla_color (id_producto, activo)` y `(id_talla)`, `(id_color)`
   - `t_inventario (id_sucursal, id_variante)` y `(id_variante)`
   - `t_categoria (id_empresa, activo, id_padre)`
   - `t_sucursal (id_empresa, activo)`

---

## 5. Tabla de Mediciones "Antes" (Línea Base — Fase 1.2, 1.3 y 1.6)

Condiciones de línea base:
- **Red y BD:** PostgreSQL remoto (`147.15.29.190:5433`, RTT 117.11 ms) para tiempos reales percibidos, y verificación de planes/conteos de queries por endpoint en clúster aislado.
- **Estado de Caché:** Caché fría en primera visita tras login; navegación recurrente sin caché de contexto en backend ni caché de catálogos por tenant.

| Pantalla / Ruta | Endpoints Llamados al Entrar | Requests (1ª visita / Recurrente) | Queries SQL por Carga | Bytes Transferidos (JSON sin GZip) | TTFB Endpoint Principal (ms) | Tiempo SQL + Pool (ms) | Latencia Auth `_contexto_vigente` (ms) | Tiempo Total Percibido (s) | Cuello de Botella Principal y Evidencia |
| :--- | :--- | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :--- |
| **Productos y Prendas** (`/admin/productos`) | `/api/rbac/mis-permisos`<br>`/api/empresas/`<br>`/api/productos`<br>`/api/categorias/`<br>`/api/tallas/`<br>`/api/colores/`<br>+ 3 de `AdminLayout` | 8 / 5 | 18–24 queries | ~190 KB (`productos`: ~102 KB + imágenes originales >15 MB) | 1,063 ms | 356 ms | 706 ms | **6.40 s** (1ª)<br>**3.80 s** (Rec.) | 8 requests concurrentes × 706 ms auth basal + `rollback()` doble RTT + carga innecesaria de `tallas`/`colores` al abrir listado + render de 132 filas con fotos originales sin paginar. |
| **Inventario** (`/admin/inventario`) | `/api/empresas/`<br>`/api/sucursales/`<br>`/api/tallas/`<br>`/api/colores/`<br>`/api/inventario/` (x2) | 6 / 5 | 16–20 queries (3 SQL pesadas por cada llamada a `/api/inventario/`) | ~65 KB | 1,229 ms | 480 ms | 706 ms | **5.20 s** (1ª)<br>**3.40 s** (Rec.) | Doble disparo inicial de `/api/inventario/` por suscripción simultánea a `companyChanged$` y `branchChanged$` + 3 queries full-join (`count`, `items`, `totales`) + reconsulta de sucursales en `tenant_guard`. |
| **Categorías** (`/admin/categorias`) | `/api/empresas/`<br>`/api/categorias/`<br>+ Layout | 3 / 2 | 6–8 queries | ~22 KB | 1,038 ms | 180 ms | 706 ms | **2.80 s** (1ª)<br>**1.95 s** (Rec.) | Subconsultas correlacionadas `COUNT(*)` por fila en `t_categoria`, ausencia de caché por tenant y re-evaluación de getters en cada ciclo de detección de cambios. |
| **Tallas y Colores** (`/admin/tallas-colores`) | `/api/empresas/`<br>`/api/tallas/`<br>`/api/colores/` | 3 / 3 | 6–9 queries | ~28 KB | 1,015 ms | 195 ms | 706 ms | **3.10 s** (1ª)<br>**2.20 s** (Rec.) | Descarga simultánea de `tallas` y `colores` aunque solo la pestaña `TALLAS` está activa + subconsultas correlacionadas hacia `t_producto_talla_color` (2,356 filas). |
| **Sucursales y Ciudades** (`/admin/sucursales`) | `/api/empresas/`<br>`/api/ciudades/`<br>`/api/sucursales/` | 3 / 3 | 6–9 queries | ~24 KB | 1,010 ms | 175 ms | 706 ms | **2.95 s** (1ª)<br>**2.15 s** (Rec.) | Importación ansiosa de `MapaSucursalComponent` (Leaflet) aunque la pestaña `MAPA` esté oculta + carga simultánea de `ciudades` sin caché de servicio + getters no memoizados. |
| **Usuarios y Roles** (`/admin/usuarios`) | `/api/rbac/roles`<br>`/api/empresas/`<br>`/api/usuarios/` | 3 / 3 | 7–10 queries | ~35 KB | 1,140 ms | 310 ms | 706 ms | **3.35 s** (1ª)<br>**2.50 s** (Rec.) | Espera activa (`while + setTimeout(50)`) en `ngOnInit`, petición directa a `/api/empresas/` sin caché de `EmpresaService`, y JOIN de 6 tablas con `STRING_AGG(DISTINCT)`. |
| **Suscripciones** (`/admin/suscripciones`) | `/api/planes`<br>`/api/empresas/`<br>`/api/mi-empresa/plan`<br>`/api/empresas/{id}/suscripciones` | 4 / 3 | 8–12 queries | ~19 KB | 1,050 ms | 240 ms | 706 ms | **3.20 s** (1ª)<br>**2.10 s** (Rec.) | Sin caché para catálogo `/api/planes` en `SaasService`, múltiples checkouts de conexión por request en `saas_services.py` y falta de `trackBy` en tabla de historial. |

---

## 6. Lista Priorizada de Cambios por Lotes Incrementales

### Lote A — Núcleo Transversal Backend (Pool, Auth Context, TenantGuard, Compresión e Instrumentación) + Productos (Backend + Frontend)
1. **`backend/app/core/postgres.py`**:
   - Eliminar el bloque duplicado de reconexión en `create_connection()`.
   - Evitar el doble RTT de red (`ROLLBACK` innecesario en `close_connection()`) ejecutando lecturas fuera de transacciones explícitas con `autocommit=True` y reservando `autocommit=False` + `commit/rollback` para bloques transaccionales (`with db.transaction():`) o escrituras explícitas, además de registrar métricas por request (`db_queries`, `db_ms`) mediante `contextvars`.
2. **`backend/app/core/security.py` y `backend/app/core/tenant_guard.py`**:
   - Implementar caché en memoria seguro con TTL corto (45 s) e invalidación inmediata (`invalidar_cache_contexto`) para `_contexto_vigente` indexado por `id_usuario`, retornando copias profundas aisladas para evitar mutación entre requests.
   - Invocar `invalidar_cache_contexto` en todos los puntos de mutación de usuarios, roles, permisos, sucursales asignadas, empresas y suscripciones.
   - Optimizar `tenant_guard.py` (`resolver_tenant_operacion` y `obtener_sucursales_autorizadas`) para reutilizar `estado_empresa` y `sucursales` ya presentes en el contexto verificado del usuario y cachear por corto plazo (30 s) el estado de empresa y sucursales activas por `id_empresa`, con invalidación al crear/editar/cambiar estado de sucursales o empresas.
3. **`backend/app/main.py`**:
   - Activar `GZipMiddleware(minimum_size=1000, compresslevel=5)` para respuestas HTTP/JSON.
   - Incorporar middleware de instrumentación segura por request (`X-Request-ID`, `Server-Timing: total;dur=..., db;dur=..., app;dur=...`, `X-DB-Query-Count`) y logging estructurado sin exponer tokens ni datos sensibles.
4. **Productos (`productos_routes.py`, `productos_services.py`, `productos_repos.py` y `frontend/.../productos.*`)**:
   - Reescribir `productos_repos.listar_productos` con CTE paginada (`COUNT(*) OVER() AS total_registros`) + `LEFT JOIN LATERAL` sobre las filas de la página actual, evitando agrupar las 2,356 variantes de toda la base. Soportar filtro por estado (`activo`), categoría, temporada y búsqueda en SQL manteniendo 100% de compatibilidad con Angular y Flutter.
   - Reemplazar bucles N+1 en `_validar_tallas_activas`, `_validar_colores_activos`, `validar_relaciones_tenant` y `sincronizar_variantes_producto` por consultas por lotes (`ANY(%s)`).
   - En `ProductosComponent` (Angular): diferir la carga de `tallas` y `colores` hasta abrir el modal de Crear/Editar; añadir paginación coordinada, skeleton de carga, memoización de métricas/filtros y pre-cálculo de temporada actual.

### Lote B — Categorías, Tallas/Colores, Inventario y Migración Reversible de Índices
1. **`categorias_repos.py` y `tallas_colores_repos.py`**:
   - Reemplazar subconsultas correlacionadas `COUNT(*)` fila por fila por `LEFT JOIN` agrupados y añadir caché seguro en memoria por tenant con invalidación automática en altas/ediciones/bajas.
2. **`inventario_repos.py` y `ListaInventarioComponent`**:
   - Consolidar `query_count` dentro de `query_totales` en `listar_inventario` (reduciendo de 3 a 2 consultas SQL por request) y omitir `LEFT JOIN t_talla / t_color` en el conteo/totales cuando no se filtre por ellos.
   - En `ListaInventarioComponent`, eliminar la doble emisión inicial entre `companyChanged$` y `branchChanged$` y reutilizar los catálogos cacheados por tenant.
3. **Pantallas `ListaCategoriasComponent` y `TallasColoresComponent`**:
   - En `TallasColoresComponent`, cargar inicialmente solo la pestaña activa (`TALLAS`) y cargar `COLORES` bajo demanda al cambiar de pestaña; agregar `trackBy`, búsqueda con *debounce* y memoización de contadores en ambas pantallas.
4. **Migración Reversible de Índices (`backend/migrations/002_iter1_perf_indexes.up.sql` y `.down.sql`)**:
   - Crear índices compuestos alineados con los planes reales de lectura y verificar con `EXPLAIN (ANALYZE, BUFFERS)` en el clúster PostgreSQL aislado de pruebas.

### Lote C — Pantallas de Sucursales, Usuarios y Suscripciones + Optimización Transversal Angular PWA
1. **Aislamiento Multitenant en Cachés de Servicios Angular (`CategoriasService`, `TallasColoresService`, `EmpresaService`, `SucursalService`, `CiudadService`, `SaasService`, `KpisService`)**:
   - Incluir `id_usuario` e `id_empresa` activo en todas las claves de caché, deduplicar peticiones en vuelo con `shareReplay(1)` y limpiar cachés automáticamente al cerrar sesión o cambiar de tenant.
2. **Lazy Loading Completo (`app.routes.ts`) y Carga Diferida de recursos (`index.html`, `styles.css`, `angular.json`)**:
   - Migrar todas las rutas principales de `app.routes.ts` a `loadComponent`.
   - Eliminar el `@import` duplicado de Google Fonts en `src/styles.css` y añadir `defer` al script de iconos en `src/index.html`.
3. **Sucursales (`ListaSucursalesComponent`), Usuarios (`ListaUsuariosComponent`) y Suscripciones (`SuscripcionesComponent`)**:
   - Eliminar el bucle de polling de token en `ListaUsuariosComponent`, usar `EmpresaService.listarEmpresas()` cacheado, añadir `trackBy`, *debounce* en búsquedas y memoización de listas filtradas y métricas.
   - Cachear `/api/planes` en `SaasService` y `/api/ciudades` en `CiudadService`.

### Lote D — Validación Integral, Pruebas Automatizadas (Funcionales, Seguridad Multitenant, Concurrencia y Rendimiento) y Entregables Finales
1. Ejecutar pruebas automatizadas de extremo a extremo en PostgreSQL aislado validando contratos API, paginación, aislamiento entre Empresa A y Empresa B, invalidación de caché y concurrencia sin errores 5xx ni agotamiento del pool.
2. Medir tiempos antes/después (p50/p95, TTFB, queries SQL, bytes JSON con/sin GZip y tamaños de bundle Angular) y documentar en `docs/performance/cambios.md`, `docs/performance/resultados.md` y `docs/AGENT_CHANGES.md`.
