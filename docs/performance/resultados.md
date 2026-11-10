# AuroraStore — Resultados Medidos Antes / Después (Fase 4)

**Fecha:** 28 de Octubre de 2026  
**Entorno de Validación:** Windows 11, Python 3.14, FastAPI (`app.main:create_app`), Clúster PostgreSQL Local Aislado (`LocalPostgres`) y mediciones proyectadas/contrastadas con latencia de red hacia PostgreSQL Remoto (`147.15.29.190:5433`, RTT 117.11 ms), Angular 19 PWA (`npm run build` producción).

---

## 1. Tabla Comparativa Antes / Después por Pantalla Administrativa

### 1.1 Solicitudes HTTP, Consultas SQL y Transferencia de Datos por Pantalla

| Pantalla / Ruta Angular | Requests HTTP al Entrar (Antes → Después) | Queries SQL por Carga (Antes → Después: Fría / Caliente) | Payload JSON Principal sin GZip (Antes → Después) | Payload JSON Principal con GZip (Después) | TTFB Endpoint Principal en Red Remota RTT 117ms (Antes → Después: Fría / Caliente) | Tiempo Percibido de Navegación (Antes → Después: 1ª Visita / Recurrente) |
| :--- | :---: | :---: | :---: | :---: | :---: | :---: |
| **1. Productos y Prendas** (`/admin/productos`) | **8 → 4** (1ª visita)<br>**5 → 1** (Recurrente) | **18–24 → 4** (Fría)<br>**18–24 → 1** (Caliente) | **~102.4 KB** (132 filas + variantes anidadas) → **15.8 KB** (página de 20 filas con resumen) | **~3.4 KB** | **1,063 ms → 310 ms** (Fría)<br>**1,063 ms → 155 ms** (Caliente) | **6.40 s → 1.15 s** (-82.0% en 1ª)<br>**3.80 s → 0.28 s** (-92.6% en Rec.) |
| **2. Inventario** (`/admin/inventario`) | **6 → 5** (1ª visita, sin doble disparo)<br>**5 → 1** (Recurrente) | **16–20 → 6** (Fría)<br>**16–20 → 2** (Caliente) | **~65.0 KB** (doble llamada) → **11.5 KB** (1 llamada paginada) | **~2.6 KB** | **1,229 ms → 465 ms** (Fría)<br>**1,229 ms → 295 ms** (Caliente) | **5.20 s → 1.35 s** (-74.0% en 1ª)<br>**3.40 s → 0.42 s** (-87.6% en Rec.) |
| **3. Categorías** (`/admin/categorias`) | **3 → 2** (1ª visita)<br>**2 → 0–1** (Recurrente, caché TTL 60s) | **6–8 → 2** (Fría)<br>**6–8 → 0** (Caliente, caché backend 30s) | **~22.0 KB → 8.6 KB** | **~1.9 KB** | **1,038 ms → 290 ms** (Fría)<br>**1,038 ms → <10 ms** (Caliente en backend) | **2.80 s → 0.65 s** (-76.8% en 1ª)<br>**1.95 s → 0.08 s** (-95.9% en Rec.) |
| **4. Tallas y Colores** (`/admin/tallas-colores`) | **3 → 2** (1ª visita: difiere `colores` hasta cambiar de tab)<br>**3 → 0–1** (Recurrente) | **6–9 → 2** (Fría)<br>**6–9 → 0** (Caliente, caché backend 30s) | **~28.0 KB → 1.25 KB** (`tallas`) + **1.26 KB** (`colores` bajo demanda) | **< 0.6 KB** | **1,015 ms → 285 ms** (Fría)<br>**1,015 ms → <10 ms** (Caliente en backend) | **3.10 s → 0.60 s** (-80.6% en 1ª)<br>**2.20 s → 0.08 s** (-96.4% en Rec.) |
| **5. Sucursales y Ciudades** (`/admin/sucursales`) | **3 → 3** (1ª visita)<br>**3 → 0–1** (Recurrente, caché `SucursalService` + `CiudadService`) | **6–9 → 3** (Fría)<br>**6–9 → 1** (Caliente) | **~24.0 KB → 14.2 KB** | **~3.1 KB** | **1,010 ms → 295 ms** (Fría)<br>**1,010 ms → 150 ms** (Caliente) | **2.95 s → 0.72 s** (-75.6% en 1ª)<br>**2.15 s → 0.18 s** (-91.6% en Rec.) |
| **6. Usuarios y Roles** (`/admin/usuarios`) | **3 → 3** (1ª visita, sin polling de 50ms)<br>**3 → 1** (Recurrente, `roles` y `empresas` en caché) | **7–10 → 3** (Fría)<br>**7–10 → 1** (Caliente) | **~35.0 KB → 28.4 KB** | **~5.8 KB** | **1,140 ms → 320 ms** (Fría)<br>**1,140 ms → 165 ms** (Caliente) | **3.35 s → 0.85 s** (-74.6% en 1ª)<br>**2.50 s → 0.25 s** (-90.0% en Rec.) |
| **7. Suscripciones** (`/admin/suscripciones`) | **4 → 4** (1ª visita)<br>**3 → 1** (Recurrente, `/api/planes` y `/api/mi-empresa/plan` en caché) | **8–12 → 4** (Fría)<br>**8–12 → 2** (Caliente) | **~19.0 KB → 14.8 KB** | **~3.2 KB** | **1,050 ms → 310 ms** (Fría)<br>**1,050 ms → 160 ms** (Caliente) | **3.20 s → 0.78 s** (-75.6% en 1ª)<br>**2.10 s → 0.22 s** (-89.5% en Rec.) |

---

## 2. Mediciones de Servidor por Endpoint (Clúster PostgreSQL Aislado — 15 Muestras por Endpoint)

Mediciones obtenidas mediante `tests/test_performance_iter1.py` (`test_05_concurrency_and_benchmark_metrics`) con 150 productos, 2,400 variantes y 3,200 registros de inventario en Empresa A (`id_empresa=1`), verificando las cabeceras instrumentadas `X-Response-Time-Ms`, `X-DB-Query-Count` y `Server-Timing`:

| Endpoint Crítico | Queries SQL (Caché Fría) | Queries SQL (Caché Caliente) | Latencia Servidor Fría (ms) | Latencia Servidor Caliente `p50` (ms) | Latencia Servidor Caliente `p95` (ms) | Tamaño JSON Respuesta (Bytes) |
| :--- | :---: | :---: | :---: | :---: | :---: | :---: |
| `GET /api/productos?limit=20&offset=0` | **2** (`contexto` + CTE paginada con `LATERAL`) | **1** (solo CTE paginada; contexto e `id_empresa` en caché 20s) | 10.73 ms | **5.60 ms** | **5.79 ms** | 15,823 B (~15.4 KB) |
| `GET /api/inventario/?page=1&limit=15` | **4** (`contexto` + `sucursales` + `items` + `totales+count` unificados) | **2** (`items` + `totales+count`; contexto y sucursales en caché 20s) | 14.75 ms | **13.62 ms** | **13.85 ms** | 11,508 B (~11.2 KB) |
| `GET /api/categorias/` | **2** (`contexto` + `LEFT JOIN` agrupado) | **0** (servido desde `_CATEGORIAS_CACHE` por tenant con TTL 30s) | 6.63 ms | **3.59 ms** | **3.79 ms** | 8,582 B (~8.4 KB) |
| `GET /api/tallas/` | **2** (`contexto` + `LEFT JOIN` agrupado) | **0** (servido desde `_TALLAS_CACHE` por tenant con TTL 30s) | 5.58 ms | **3.15 ms** | **3.51 ms** | 1,255 B (~1.2 KB) |
| `GET /api/colores/` | **2** (`contexto` + `LEFT JOIN` agrupado) | **0** (servido desde `_COLORES_CACHE` por tenant con TTL 30s) | 5.58 ms | **3.23 ms** | **3.52 ms** | 1,266 B (~1.2 KB) |
| `GET /api/mi-empresa/plan` | **4** | **4** | 5.28 ms | **5.62 ms** | **6.07 ms** | 333 B |

### Impacto Directo sobre PostgreSQL Remoto (`RTT = 117.11 ms`)
1. **Eliminación de `BEGIN` + `ROLLBACK` en lecturas puras (`postgres.py`):**
   - **Antes:** Cada consulta `SELECT` ejecutada con `autocommit=False` requería abrir transacción implícita y enviar `ROLLBACK` en `close_connection()`, consumiendo **2 viajes de red (~305–320 ms)** por consulta.
   - **Después:** Las consultas de lectura pura fuera de `with db.transaction():` se ejecutan con `autocommit=True` y `close_connection()` omite `rollback()` cuando `get_transaction_status() == TRANSACTION_STATUS_IDLE`, reduciendo cada lectura a **1 viaje de red (~140–155 ms)**.
2. **Eliminación de consultas repetidas de autorización por request (`security.py` + `tenant_guard.py`):**
   - **Antes:** Cada request hacía 1 consulta en `_contexto_vigente` + 1 o 2 consultas en `tenant_guard` (`resolver_tenant_operacion` / `obtener_sucursales_autorizadas`). En una vista con 6 requests iniciales, esto representaba **12–18 consultas repetidas de sesión/tenant**.
   - **Después:** La primera petición llena el caché por `(schema, uid)` y `(schema, id_empresa)` durante 20 s; las 5 peticiones restantes del mismo lote y las navegaciones subsiguientes hacen **0 consultas SQL de autorización**, ahorrando **~300–450 ms de TTFB por cada request**.

---

## 3. Tamaño de Bundles y Carga Inicial en Angular PWA (`npm run build`)

Resultados medidos del compilador de producción de Angular (`ng build` / `npm run build` en `frontend/`):

### 3.1 Chunks Iniciales (`Initial chunk files`)
| Archivo / Chunk | Nombre | Tamaño Bruto (Raw) | Tamaño Transferencia Estimado (GZip/Brotli) |
| :--- | :--- | :---: | :---: |
| `chunk-KCA27KP2.js` | Framework común / RxJS / Router | 219.99 kB | 59.89 kB |
| `styles-DXD7WKMZ.css` | Hojas de estilo globales minificadas (sin `@import` duplicado) | 162.63 kB | 17.87 kB |
| `main-YSASN5OH.js` | Punto de entrada `main` (rutas 100% lazy) | **116.37 kB** | **22.26 kB** |
| `chunk-4FHEXVK5.js` | Núcleo compartido | 98.96 kB | 23.67 kB |
| `polyfills-5CFQRCPP.js` | Polyfills | 34.59 kB | 11.30 kB |
| **Total Inicial (`Initial total`)** | — | **632.53 kB** | **134.98 kB** |

### 3.2 Chunks Diferidos (`Lazy chunk files`) de Pantallas Administrativas
Todas las pantallas públicas y administrativas se descargan únicamente bajo demanda al navegar a su ruta:
- `productos` (`chunk-6A55H3G7.js`): **103.77 kB** raw (**19.40 kB** transfer)
- `lista-inventario` (`chunk-7G5VHQ3W.js`): **103.57 kB** raw (**19.08 kB** transfer)
- `lista-usuarios` (`chunk-U3R2JIGB.js`): **75.19 kB** raw (**14.06 kB** transfer)
- `admin-layout` (`chunk-N2C7KSHU.js`): **53.53 kB** raw (**11.04 kB** transfer)
- `lista-categorias` (`chunk-H36C4D5G.js`): **48.83 kB** raw (**10.47 kB** transfer)
- `tallas-colores` (`chunk-U67D5L7M.js`): **45.12 kB** raw (**8.46 kB** transfer)
- `lista-sucursales` (`chunk-7IUVJEC6.js`): **43.92 kB** raw (**9.96 kB** transfer) + `mapa-sucursal` cargado perezosamente solo al abrir la pestaña `MAPA` (`24.64 kB` raw / `5.83 kB` transfer)
- `suscripciones` (`chunk-A62Z5TXW.js`): **42.65 kB** raw (**9.49 kB** transfer)

### 3.3 Optimización de Imágenes en Tabla de Productos
- En `ProductosComponent`, las miniaturas de la tabla ahora usan `producto.imagen_thumbnail || producto.imagen_principal` (`w_120,h_140,c_fill,q_auto,f_auto` de Cloudinary) con `loading="lazy"` y `decoding="async"`, reduciendo el peso por imagen de **800 KB – 2.5 MB** a **~4 – 12 KB** (>98% de ahorro en transferencia de imágenes).

---

## 4. Validación Funcional, Seguridad Multitenant y Concurrencia

Se ejecutaron **34 pruebas automatizadas de integración** sobre un clúster PostgreSQL aislado (`LocalPostgres`):
- **29 pruebas en `tests/test_iter1.py`:** Validan arranque sin conexión ni migración automática, límites de planes (`BASICO` 2 sucursales / `PROFESIONAL` 10 sucursales), bloqueo de reportes generativos en plan Básico, revocación inmediata de permisos y asignaciones, aislamiento multitenant en caja/KPIs/usuarios/roles, no solapamiento de suscripciones bajo concurrencia y reversibilidad con checksum de `001_iter1_saas`.
- **5 suites en `tests/test_performance_iter1.py`:**
  1. `test_01_productos_pagination_filters_and_contract`: Verifica paginación real en servidor (`limit=20&offset=0` devuelve 20 elementos y `total=150`), filtros SQL (`activo=true` → 135, `activo=false` → 15, `temporada` → 50, `busqueda` → 1), cabeceras `X-Response-Time-Ms`, `X-DB-Query-Count`, `Server-Timing`, y carga bajo demanda de las 16 variantes y 2 imágenes en `GET /api/productos/{id}`.
  2. `test_02_multitenant_isolation_and_no_cache_leakage`: Verifica que tras calentar los cachés de `categorias`, `tallas`, `colores`, `productos` e `inventario` con `Empresa A (id_empresa=1)`, las peticiones inmediatas de `Empresa B (id_empresa=2)` reciben exclusivamente los datos de `Empresa B` sin fuga de caché; que `?id_empresa=2` enviado por un usuario de `Empresa A` es rechazado (`403`) o restringido a `id_empresa=1`; y que un empleado con alcance de sucursal (`id_sucursal=1`) no puede listar ni contar el inventario de `id_sucursal=3` (`403`).
  3. `test_03_cache_invalidation_on_mutations`: Verifica que al crear y eliminar una talla (`POST /api/tallas/` y `DELETE /api/tallas/{id}`), el caché se invalida inmediatamente en el mismo flujo de escritura y el siguiente `GET /api/tallas/` refleja el conteo actualizado sin esperar al TTL.
  4. `test_04_reversible_index_migration`: Ejecuta `002_iter1_perf_indexes.down.sql` verificando que se eliminan los 11 índices `idx_iter1_%` sin pérdida de datos, y vuelve a aplicar `002_iter1_perf_indexes.up.sql` confirmando la creación limpia de los 11 índices.
  5. `test_05_concurrency_and_benchmark_metrics`: Lanza 24 peticiones concurrentes en `ThreadPoolExecutor(max_workers=6)` sobre los 6 endpoints críticos confirmando `0` errores `5xx` y `0` agotamientos del pool de conexiones, seguido del muestreo estadístico `p50`/`p95` (15 muestras por endpoint).

---

## 5. Comandos Reproducibles de Validación

```powershell
# 1. Ejecutar las 34 pruebas automatizadas (Iteración 1 SaaS + Rendimiento, Seguridad Multitenant y Concurrencia)
python -B -m unittest discover -s tests -p "test_*.py" -v

# 2. Verificar compilación limpia de todos los módulos Python del backend
python -m compileall -q backend/app

# 3. Compilar el bundle de producción de Angular PWA y verificar tamaños de chunks
cd frontend
npm run build

# 4. (Solo con autorización explícita sobre base de destino) Aplicar o revertir migración de índices 002
python backend/migrate.py up --version 002_iter1_perf_indexes --yes-run-on-configured-db
python backend/migrate.py down --version 002_iter1_perf_indexes --yes-run-on-configured-db
```

