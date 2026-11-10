# AuroraStore — Iteración 2 (Fase Avanzada): Informe de Pruebas PWA Offline-First y Sincronización Transaccional

> Estado final 2026-10-31: 003/004 autorizadas, aplicadas en PostgreSQL real y verificadas por lectura de catálogo/checksums y reaplicación sin cambios. Se restableció el backend local y se limpiaron artefactos generados; no se ejecutaron ventas de prueba reales. [Acta y evidencia](SYNC_MIGRACION_APLICADA_2026-10-31.md).

> Cola Angular, excepción autorizada el 2026-10-31: 40 pruebas nuevas de almacenamiento/retención aprobadas. La ejecución general tuvo 46/47 aprobadas y un fallo ajeno de mock en `permission-guard.spec.ts`; compilación de producción correcta. Se usó IndexedDB emulado, no un navegador físico. [Resultados y pendientes](PWA_COLA_RETENCION_RESULTADOS.md).

> Endurecimiento 2026-10-31: la auditoría inicial detectó la ausencia de la tabla sync, subsanada mediante la aplicación autorizada posterior. El [informe transaccional](SYNC_IDEMPOTENCIA_TRANSACCIONAL.md) documenta 15 pruebas nuevas de integración aislada y una regresión individual adicional aprobadas, además de las ocho PWA y las 29 Iteración 1. Incluyen concurrencia, muerte de procesos, respuesta HTTP perdida, movimientos reales y reinicio de PostgreSQL con WAL/fsync. La suite histórica de rendimiento tiene cuatro errores preexistentes de configuración; no se declara aprobada. Flutter permanece sin modificar.

**Fecha:** 2026-10-28  
**Comandos ejecutados:**
- `python -B -m unittest discover -s tests -p "test_*.py" -v`
- `python -B -m unittest tests/test_pwa_iter2.py -v`
- `Set-Location frontend; npm run build`

**Resultado global:** **42 pruebas automatizadas aprobadas (`OK`)** en clúster PostgreSQL aislado (`LocalPostgres`) + compilación de producción Angular PWA limpia (`0` errores TypeScript/plantillas, bundle inicial de `151.02 kB` transfer).

---

## 1. Matriz de Pruebas Automatizadas Ejecutadas (`tests/test_pwa_iter2.py`)

Todas las pruebas de integración se ejecutaron sobre un clúster PostgreSQL efímero aislado (`LocalPostgres`) sin conectar ni modificar la base de datos remota de producción (`147.15.29.190:5433`):

| Caso de Prueba | Caso de Uso / Regla | Qué valida | Resultado |
| :--- | :--- | :--- | :--- |
| `test_01_reversible_sync_migration_003` | Regla #3 (Migración reversible) | Ejecuta `003_iter2_sync_idempotency.down.sql`, comprueba que `t_sync_operacion` se elimina limpiamente, vuelve a aplicar `.up.sql` y verifica la tabla e índices. | **OK** |
| `test_02_sync_ping_zero_sql_queries` | Regla #8 (`GET /api/sync/ping`) | Verifica que `GET /api/sync/ping` responda `200 OK` con `X-DB-Query-Count: 0`. | **OK** |
| `test_03_sync_cart_operations_idempotency_and_n_plus_1_elimination` | `CU08W`, `CU38W`, Regla #2 | Sincroniza un lote con `CART_ADD_ITEM` para múltiples variantes, reenvía el mismo `operation_id` verificando `idempotent_replay: True` sin duplicar cantidades en `t_detalle_carrito`, y comprueba que `GET /api/carrito` ejecuta `<= 4` consultas SQL (eliminación del bucle N+1). | **OK** |
| `test_04_sync_conflict_detection_and_resolution_cu39w` | `CU39W` (Conflictos en carrito) | Provoca conflicto `STOCK_INSUFFICIENT` (solicita 50 con 15 disponibles) y lo resuelve ajustando a cantidad disponible; provoca conflicto `PRICE_CHANGED` (Bs. 120 vs Bs. 200 vigentes) y lo resuelve con `accept_price_change: True`. | **OK** |
| `test_05_sync_reserva_solicitud_and_payment_guard_cu10w` | `CU10W`, `CU27W`, Regla #6 | Comprueba que una reserva con `con_pago: True` en la cola offline es rechazada con `409 PAYMENT_REQUIRES_ONLINE`, mientras que una solicitud gratuita (`con_pago: False`) valida sucursal/stock y se confirma atómicamente (`RES-...`) con idempotencia estricta ante reintentos. | **OK** |
| `test_06_multitenant_isolation_and_public_catalog_cache` | Regla #4 (Seguridad SaaS) y `CU04W` | Verifica que un usuario de `Empresa 1` recibe `403 TENANT_FORBIDDEN` al intentar sincronizar operaciones hacia `Empresa 2`, y comprueba que `/api/catalogo/filtros?id_empresa=1` sirve metadatos cacheados en `0` consultas SQL en visitas repetidas. | **OK** |
| `test_07_sync_lote_venta_contado_efectivo_idempotency_and_guards_cu24w` | `CU24W`, `CU38W`, Reglas Críticas POS | 1) Rechaza `CLIENTE` intentando `VENTA_CONTADO` en `POST /api/sync/lote` (`403 ROLE_FORBIDDEN`). 2) Rechaza pago electrónico (`QR`) en `VENTA_CONTADO` (`409 PAYMENT_REQUIRES_ONLINE`, `reconciliation_required`). 3) Rechaza venta en efectivo con caja cerrada (`409 CAJA_CERRADA`, `status: "reconciliation_required"`) y verifica que la incidencia quede persistida en `t_sync_operacion` sin perderse. 4) Abre turno de caja para el cajero y sincroniza `VENTA_CONTADO` en `EFECTIVO` verificando `estado_venta: "PAGADO"`, cálculo de cambio y descuento exacto en `t_inventario`. 5) Reenvía el mismo `operation_id` a `POST /api/sync/lote` y comprueba `idempotent_replay: True`, `1` sola fila en `t_venta`/`t_pago` y que el stock NO se descuenta dos veces. | **OK** |
| `test_08_sync_lote_venta_contado_conflicts_and_reconciliation_cu39w` | `CU24W`, `CU39W` (Conciliación de caja) | 1) Provoca conflicto `PRICE_CHANGED` en `VENTA_CONTADO` y comprueba retorno `status: "reconciliation_required"`, `reconciliation_required: True`. 2) Provoca conflicto `STOCK_INSUFFICIENT` en `VENTA_CONTADO` (solicita 50 con 12 en sucursal) y verifica persistencia de ambas incidencias en `t_sync_operacion`. 3) Resuelve el conflicto ajustando cantidad al stock disponible con el mismo `operation_id` y verifica transición a `status: "synced"` (`PAGADO`). | **OK** |

---

## 2. Regresión Completa de Iteración 1 SaaS, Rendimiento e Iteración 2 PWA

| Suite | Pruebas | Estado |
| :--- | :--- | :--- |
| `tests/test_iter1.py` (SaaS Multitenant, RBAC, Suscripciones, Vigencia, Límites de Sucursales) | 29 pruebas | **29 OK** |
| `tests/test_performance_iter1.py` (Paginación de Productos, Aislamiento de Caché, Índices `002`, Benchmark Concurrente) | 5 pruebas | **5 OK** |
| `tests/test_pwa_iter2.py` (Migración `003`, `/api/sync/ping`, `/api/sync/lote`, `CU08W`, `CU10W`, `CU24W`, `CU38W`, `CU39W`, Aislamiento) | 8 pruebas | **8 OK (`7.224s`)** |
| **Total** | **42 pruebas** | **42 OK (100%)** |

---

## 3. Verificación deEscenarios Offline, Reinicio de PWA y Reconexión

1. **Desconexión y Persistencia Sobreviviendo Reinicio de PWA (`IndexedDB`):**
   - Las operaciones `CART_ADD_ITEM` (`CU08W`), `RESERVA_SOLICITUD` (`CU10W`) y `VENTA_CONTADO` (`CU24W`) se persisten en el object store `pending_operations` de `aurora_store_pwa_db` con `operation_id` UUID v4.
   - Si el navegador se cierra o recarga en medio de un intento de sincronización, `SyncQueueService.recoverInterruptedOperations()` restaura automáticamente cualquier operación en estado `'syncing'` a `'pending'` en el arranque y rehidrata el mapa de stock provisional (`recalculateProvisionalStockFromQueue()`).
   - En `/mis-reservas` (`ReservaService.obtenerMisReservas`), las solicitudes de reserva locales (`RESERVA_SOLICITUD`) se fusionan con las reservas del servidor mostrando código provisional `PROV-XXXXXXXX` y estado `PENDIENTE_SYNC` o `CONFLICTO_SYNC`.
   - En `/admin/caja` (`CajaService` + `CajaComponent`), las ventas de contado en efectivo registradas sin red descuentan stock provisional local (`Prov: -X (Srv: Y)`), emiten comprobante provisional con referencia `OFFLINE-XXXXXXXX` y aparecen en la pestaña **Ventas del Turno** incluso tras recargar la PWA sin red.
2. **Reconexión y Sincronización por Lotes (`CU38W`):**
   - `NetworkStatusService` sondea `GET /api/sync/ping?_t=...` (`0` consultas SQL) y al confirmar retorno de red dispara `SyncQueueService.processQueue('network_restored')` enviando el lote FIFO a `POST /api/sync/lote` con lock multi-pestaña (`aurora_pwa_sync_lock_v1`).
3. **Detección de Conflictos y Conciliación de Caja (`CU39W` y `CU37W`):**
   - En `PwaStatusBarComponent`, las operaciones rechazadas por `STOCK_INSUFFICIENT` o `PRICE_CHANGED` ofrecen resolución en 1 clic (**Aceptar nuevo precio y reintentar** / **Ajustar a stock disponible**), actualizando también los ítems de reservas y ventas multi-ítem.
   - Las ventas `VENTA_CONTADO` rechazadas pasan a estado `'reconciliation_required'`, bloquean el descarte silencioso y despliegan un formulario de **Conciliación Física de Caja** que registra la nota de arqueo en `sync_attempts` y en el historial auditable `cash_sale_incidences` de `IndexedDB`.

---

## 4. Problemas Detectados en Auditoría y Corregidos

1. **Prefijo `/api` en `SyncQueueService` y `ReservaService`:** `environment.apiUrl` es `'http://127.0.0.1:5000'`, mientras que `SyncQueueService` y `ReservaService` invocaban `${environment.apiUrl}/sync/operations` y `${environment.apiUrl}/reservas` sin `/api`. Corregido a `${environment.apiUrl}/api/sync/lote` y `${environment.apiUrl}/api/reservas`.
2. **Verificación de `db.create_connection()` en `sync_routes.py`:** `PostgreSQL.create_connection()` asigna `self.conn` y retorna `None`; las guardas `if not db.create_connection():` en `sync_routes.py` impedían escribir en `t_sync_operacion` y validar sucursales. Corregido a `db.create_connection(); if not db.conn:`.
3. **Polimorfismo de `t_sucursal.estado` (`BOOLEAN` vs `TEXT`):** En fixtures P1 `t_sucursal.estado` es `BOOLEAN` (`TRUE`) y en despliegues extendidos puede ser `'ACTIVO'`. Ajustado `_verificar_sucursal_activa_empresa` y `_obtener_stock_sucursal_variante` para aceptar ambos formatos sin falsos positivos de `BRANCH_INACTIVE`.

---

## 5. Funcionalidades Pendientes (Fuera de Alcance de este Encargo)

- **Integración móvil Flutter (`mobile/` con SQLite):** Expressamente excluida por `AGENTS.md` y las restricciones del encargo; el contrato `POST /api/sync/lote` y `GET /api/sync/ping` documentado en `docs/PWA_CONTRATO_SYNC.md` queda listo y compatible 1:1 para su futura adopción en Flutter.
- **Ejecución de la migración `003_iter2_sync_idempotency.up.sql` en la base remota real (`147.15.29.190:5433`):** Sujeta a autorización explícita del usuario conforme a `AGENTS.md`.
