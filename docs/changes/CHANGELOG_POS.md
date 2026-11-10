# Registro de Cambios POS — Contingencia Offline (Iteración 6)

## [2026-11-07] — Iteración 6: Contingencia Offline POS (Migración 008)

### Contexto y Necesidad
En situaciones de pérdida de conexión a Internet en sucursales físicas, el punto de venta (POS) debe permitir continuar registrando ventas en efectivo sin detener la atención al cliente, pero protegiendo al StoreFront online contra sobreventas. Se implementó una arquitectura basada en **cuotas de inventario de contingencia preasignadas transaccionalmente a las sesiones de caja**, sincronización prioritaria P0 y conciliación con resolución de incidencias.

---

### Componentes Modificados y Creados

#### 1. Base de Datos y Migraciones
- `backend/migrations/008_iter6_pos_contingencia.up.sql`:
  - Agrega `politica_contingencia_pos` (JSONB) en `empresa` con valores por defecto seguros.
  - Agrega `stock_contingencia` (INTEGER CHECK >= 0) y `cuota_manual_contingencia` en `t_inventario`.
  - Crea tabla `t_caja_cuota_contingencia` con restricción única `(id_sesion_caja, id_variante)` y control de cuotas asignadas/consumidas/liberadas.
  - Crea tabla `t_incidencia_sobreventa` para registrar ventas físicas autorizadas que requieran resolución administrativa en caso de conflicto concurrente.
  - Extiende `t_venta` con `es_contingencia_offline`, `comprobante_tipo_provisional` e `id_cuota_contingencia`.
  - Registra y siembra permiso `pos.contingencia` a roles autorizados.
- `backend/migrations/008_iter6_pos_contingencia.down.sql`:
  - Rollback reversible y limpio de todas las tablas, columnas, índices y permisos creados.

#### 2. Backend — Repositorios y Servicios
- `backend/app/core/inventory_integrity.py`:
  - Actualiza la validación de integridad física de inventario para incorporar dinámicamente `stock_contingencia`:
    $$\text{stock\_disponible} = \text{stock\_actual} - \text{stock\_reservado} - \text{stock\_contingencia}$$
  - Mantiene 100% de retrocompatibilidad con esquemas donde aún no se aplique la migración 008.
- `backend/app/modules/pos/repos/contingencia_repos.py`:
  - `obtener_politica_contingencia` & `actualizar_politica_contingencia`: gestión de parámetros híbridos (porcentaje, cantidad fija, límites).
  - `calcular_y_asignar_cuotas_sesion`: cálculo híbrido con bloqueo `FOR UPDATE` en `t_inventario` y descuento de cuotas activas en otras cajas abiertas de la sucursal.
  - `obtener_cuotas_activas_sesion`: listado para descarga y almacenamiento local en IndexedDB.
  - `consumir_cuota_contingencia_transaccional`: decremento atómico de la cuota consumida y restitución a `stock_disponible` de las unidades vendidas por contingencia para no afectar el catálogo online.
  - `liberar_cuotas_sesion_caja`: restitución masiva del inventario de contingencia remanente al cerrar la sesión de caja.
  - `registrar_incidencia_sobreventa` & `listar_incidencias_sobreventa`.
- `backend/app/modules/pos/repos/caja_repos.py`:
  - En `abrir_caja_sesion`: invoca automáticamente `calcular_y_asignar_cuotas_sesion` y retorna las cuotas generadas en la respuesta.
  - En `cerrar_caja_sesion`: invoca automáticamente `liberar_cuotas_sesion_caja` para devolver el stock al inventario online disponible.
- `backend/app/modules/pos/routes/pos_routes.py`:
  - `GET /api/pos/contingencia/cuotas`: descarga de cuotas de la sesión.
  - `GET /api/pos/contingencia/politica` & `PUT /api/pos/contingencia/politica`: administración de políticas por tenant.
  - `GET /api/pos/contingencia/incidencias`: monitoreo de incidencias de sobreventa.
- `backend/app/modules/ecommerce/routes/sync_routes.py`:
  - Ordena las operaciones del lote entrante priorizando con **P0** las ventas de contado (`VENTA_CONTADO`) antes de carritos o reservas.
  - Consume transaccionalmente las cuotas de contingencia y marca las ventas sincronizadas como `es_contingencia_offline = TRUE` y `comprobante_tipo_provisional = 'PROVISIONAL_CONTINGENCIA'`.

#### 3. Frontend — Angular PWA & POS
- `frontend/src/app/core/storage/indexed-db.service.ts`:
  - Agrega almacén `'pos_contingency_quotas'` con índice de búsqueda por clave (`caja:id|var:id`).
- `frontend/src/app/core/sync/sync-queue.service.ts`:
  - Despacho ordenado en el cliente priorizando operaciones `VENTA_CONTADO` (Prioridad P0).
- `frontend/src/app/modules/pos/services/caja.ts`:
  - `abrirCaja`: almacena automáticamente las cuotas de contingencia descargadas en IndexedDB.
  - `obtenerCuotasContingencia`, `guardarCuotasContingenciaOffline`, `obtenerCuotaContingenciaLocal`.
  - `registrarVentaContadoOffline`: adjunta metadatos `contingencia: true`, `es_contingencia_offline: true`, `comprobante_tipo_provisional: 'PROVISIONAL_CONTINGENCIA'`.
- `frontend/src/app/pages/caja/caja.ts` & `caja.html`:
  - Desbloquea la venta presencial en efectivo durante desconexión.
  - Muestra banner amber: *"Modo Contingencia POS Activo (Solo Efectivo) • Prioridad P0"*.
  - Modal de venta exitosa offline con llamado a *"Comprobante Provisional de Contingencia (No Válido como Factura Fiscal)"* y botón de impresión de ticket provisional.

---

### Pruebas Automatizadas Ejecutadas
- `tests/test_pos_contingencia.py`: **5/5 pruebas PASSED (100% verde)**
  1. `test_01_reversible_contingencia_migration_008`: Reversibilidad 100% limpia de UP y DOWN.
  2. `test_02_hybrid_quota_calculation_and_assignment_on_cash_open`: Cálculo de 15% por defecto y preasignación a caja.
  3. `test_03_transactional_quota_distribution_multi_terminal`: Distribución multi-caja en concurrencia sin sobrepasar stock físico.
  4. `test_04_sync_p0_priority_and_contingency_sale_consumption`: Sincronización prioritaria P0 y consumo atómico de cuota.
  5. `test_05_release_unused_contingency_stock_on_cash_close`: Restitución limpia al cerrar caja.
- `tests/test_pwa_iter2.py`: **8/8 pruebas PASSED (100% verde)**
  - Idempotencia, ping con 0 SQL, carritos, reservas online, guardas RBAC, incidencias de caja cerrada y conciliación CU39W.
