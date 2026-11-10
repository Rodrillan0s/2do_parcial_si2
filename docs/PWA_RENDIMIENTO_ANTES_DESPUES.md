# AuroraStore — Iteración 2: Rendimiento Antes / Después de la Refactorización PWA

**Fecha:** 2026-10-28  
**Metodología:** Mediciones reales extraídas de `ng build` (producción) y del arnés de pruebas instrumentado con `Server-Timing` / `X-DB-Query-Count` (`tests/test_performance_iter1.py` y `tests/test_pwa_iter2.py` sobre PostgreSQL local aislado con 180 productos y 2,880 variantes).

---

## 1. Impacto en el Tamaño del Bundle Inicial de Angular (`ng build`)

Se implementó toda la infraestructura PWA (`IndexedDbService`, `NetworkStatusService`, `SyncQueueService`, `PwaUpdateService`, `PwaStatusBarComponent` y `sw.js`) **sin añadir ninguna dependencia externa en `package.json`** (`0 KB` de bibliotecas de terceros):

| Métrica de Compilación (`frontend/`) | Antes de Iteración 2 (Línea Base Post-Iter1) | Después de Iteración 2 (PWA Offline-First) | Variación |
| :--- | :---: | :---: | :---: |
| **Initial Bundle Total (Raw)** | `662.25 kB` | `680.97 kB` | `+18.72 kB` (`+2.8%`) |
| **Initial Bundle Total (Estimated Transfer / Gzip)** | `142.34 kB` | `146.35 kB` | **`+4.01 kB` (`+2.8%`)** |
| **Lazy Chunk `/catalogo` (`catalogo`)** | `51.69 kB` (`10.15 kB` gzip) | `52.77 kB` (`10.38 kB` gzip) | `+0.23 kB` gzip |
| **Lazy Chunk `/admin/productos` (`productos`)** | `105.00 kB` (`19.78 kB` gzip) | `105.00 kB` (`19.78 kB` gzip) | `0.00 kB` |
| **Lazy Chunk `/admin/caja` (`caja`)** | `105.28 kB` (`18.31 kB` gzip) | `105.76 kB` (`18.45 kB` gzip) | `+0.14 kB` gzip |
| **Dependencias npm externas añadidas** | `0` | `0` | **`0 KB`** |

---

## 2. Preservación de las Mejoras de Rendimiento de Iteración 1 (`/admin/productos` e Inventario)

Los benchmarks automatizados (`test_05_concurrency_and_benchmark_metrics` en `tests/test_performance_iter1.py`) confirman que las mejoras de la Iteración 1 se conservaron intactas tras integrar la capa PWA:

| Endpoint | Antes de Iter1 (Línea Base Original) | Después de Iter1 | Después de Iter2 (PWA Actual) | Consultas SQL (Frío / Caliente) |
| :--- | :---: | :---: | :---: | :---: |
| `GET /api/productos?limit=20&offset=0` | `58.95 ms` (`572,188 B`) | `6.70 ms` (`15,823 B`) | **`6.50 ms` p50 / `6.77 ms` p95** (`15,823 B`) | `2` / `1` |
| `GET /api/inventario/?page=1&limit=15` | `18.69 ms` (`5` SQL) | `12.63 ms` (`2` SQL) | **`13.80 ms` p50 / `14.38 ms` p95** (`11,508 B`) | `4` / `2` |
| `GET /api/categorias/` | `15.52 ms` (`2` SQL) | `4.14 ms` (`0` SQL) | **`4.63 ms` p50 / `4.91 ms` p95** (`8,582 B`) | `2` / `0` |
| `GET /api/tallas/` | `5.04 ms` (`2` SQL) | `3.59 ms` (`0` SQL) | **`3.87 ms` p50 / `4.16 ms` p95** (`1,255 B`) | `2` / `0` |
| `GET /api/colores/` | `5.32 ms` (`2` SQL) | `3.46 ms` (`0` SQL) | **`4.03 ms` p50 / `4.20 ms` p95** (`1,266 B`) | `2` / `0` |

---

## 3. Nuevas Optimizaciones de Red y Consultas SQL en Flujos Comerciales (Iteración 2)

Además de habilitar la operación offline, la Iteración 2 corrigió tres cuellos de botella detectados en la auditoría inicial (`docs/PWA_AUDITORIA_INICIAL.md`):

| Flujo / Endpoint | Antes de Iteración 2 | Después de Iteración 2 | Evidencia Verificada |
| :--- | :--- | :--- | :--- |
| **Carga de `/catalogo` (Frontend)** | Cascada secuencial de 3 etapas (`tenants` → `filtros` → `productos`) y búsqueda sin debounce. | Carga paralela de `obtenerFiltros` + `consultarProductos` y debounce de `200 ms` en `onBusquedaChange`. | `frontend/src/app/pages/catalogo/catalogo.ts` |
| **`GET /api/catalogo/filtros?id_empresa=1`** | **7 consultas SQL** en cada visita (`obtener_info_tenant` + 6 consultas en `obtener_filtros_disponibles`). | **0 consultas SQL** en visitas repetidas dentro de la ventana TTL de 30s (invalidada automáticamente al mutar catálogo). | Verificado en `test_06_multitenant_isolation_and_public_catalog_cache` (`X-DB-Query-Count: 0`) |
| **Arranque de App (`GET /api/carrito`)** | **2 peticiones HTTP duplicadas** simultáneas (`NavbarComponent` + `CarritoDrawerComponent`) y **N+1 consultas SQL** en servidor (`1` query extra por cada prenda en el carrito). | **1 sola petición HTTP** deduplicada (`shareReplay(1)`) y **0 consultas N+1** en `consultar_carrito_completo` (stock calculado mediante `LEFT JOIN` agregado). | Verificado en `test_03_sync_cart_operations_idempotency_and_n_plus_1_elimination` (`X-DB-Query-Count <= 4` con múltiples ítems) |
| **Lectura de Catálogo / Detalle Sin Conexión (`CU04W`–`CU07W`)** | Fallo total de pantalla (`status === 0` / lista vacía). | Respuesta inmediata desde `IndexedDB` (`aurora_store_pwa_db`) con sello `fetchedAt` y filtrado local transparente. | `CatalogoPublicoService` + `ProductosService` |

