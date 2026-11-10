# Historial de Cambios: Pagos y Conciliación de Inventario

**Dominio:** Pasarela de Pagos (PayPal / Tarjeta), Integridad de Inventario y Conciliación Transaccional (`CU27W`, `CU29W`, `CU39W`)  
**Fecha:** 2026-11-07  
**Agente Responsable:** Antigravity / Codex  
**Estado:** Aplicado y Verificado (Migración 009 activa, 18/18 tests superados)  

---

## 1. Resumen de la Incidencia

Durante el flujo de pago con PayPal de un pedido de tienda (Pedido `PED-20261107-6596F7`, total Bs. 110.00), el servidor respondió con error **409 Conflict**:
```
INFO:     127.0.0.1:57219 - "OPTIONS /api/pagos/paypal/capturar HTTP/1.1" 200 OK
INFO:     127.0.0.1:57219 - "POST /api/pagos/paypal/capturar HTTP/1.1" 409 Conflict

Detail: "INVENTORY_RECONCILIATION_REQUIRED: saldo histórico inconsistente; requiere conciliación."
```

---

## 2. Diagnóstico y Causa Raíz

1. **Drift Histórico en `t_inventario`:**
   - La base de datos heredaba 5,690 registros (el 94.5% del catálogo) donde `stock_disponible` no cumplía la relación matemática canónica:
     $$\text{stock\_disponible} = \text{stock\_actual} - \text{stock\_reservado} - \text{stock\_contingencia}$$
   - En la prenda del pedido actual (variante 1797 en sucursal 5, `id_inventario = 4876`), `stock_actual` era 10, `stock_reservado` era 1 (apartado durante la creación del pedido), pero `stock_disponible` quedó en 12 en vez de 9 debido a saldos iniciales arbitrarios de siembras antiguas.
2. **Activación de Guardia Estricta `lock_position`:**
   - Al invocar `POST /api/pagos/paypal/capturar`, el repositorio de confirmación de pagos (`pago_repos.py`) ejecutaba `lock_items(...)`, invocando la función de guarda de `backend/app/core/inventory_integrity.py`.
   - Al detectar que `available != (actual - reserved - contingency)`, la guardia abortó la transacción lanzando `HTTPException(409)` para evitar propagar saldos inconsistentes.
3. **Falta de Pre-vuelo antes de la Captura en Pasarelas Externas:**
   - En `pago_routes.py`, la captura con PayPal (`paypal_service.capturar_orden_paypal`) se ejecutaba antes de adquirir los bloqueos pesimistas de inventario. Si la confirmación de base de datos fallaba, el cobro quedaba retenido en la pasarela externa pero la venta no se registraba en la base de datos local.

---

## 3. Solución Implementada

### A. Migración Reversible 009: Conciliación de Inventario
- **Archivos:**
  - `backend/migrations/009_iter7_reconciliacion_inventario.up.sql`
  - `backend/migrations/009_iter7_reconciliacion_inventario.down.sql`
- **Mecanismo de Seguridad:**
  1. Se crea la tabla de respaldo `comercio.t_inventario_conciliacion_backup_009` con el snapshot exacto de `stock_actual`, `stock_reservado` y `stock_disponible` previo a cualquier mutación.
  2. Se respaldaron **5,690 registros** discrepantes.
  3. Se sincronizó `stock_disponible = GREATEST(0, stock_actual - stock_reservado - COALESCE(stock_contingencia, 0))`.
  4. La consulta de verificación posterior confirmó **0 inconsistencias restantes** en las 6,019 filas de `t_inventario`.
  5. En caso de requerirse, `down.sql` permite restaurar los valores históricos inmediatamente.

### B. Pre-vuelo de Integridad en Backend antes de Cobro
- **Archivo:** `backend/app/modules/ecommerce/repos/pago_repos.py`
  - Añadida la función `validar_integridad_inventario_pedido`: adquiere bloqueos y valida la integridad matemática de las posiciones del pedido antes de efectuar cobros externos.
- **Archivo:** `backend/app/modules/ecommerce/routes/pago_routes.py`
  - En `capturar_paypal_endpoint`, se incorporó el paso 0 de pre-vuelo antes de llamar a `paypal_service.capturar_orden_paypal`. De este modo, si alguna posición presenta incidencias, la petición se detiene antes de capturar dinero del cliente en PayPal.
  - Se mantiene la compatibilidad idempotente: si la orden ya fue capturada por PayPal (como en el caso del reintento del usuario), `paypal_service` recupera el capture ID existente y permite completar la confirmación atómica en la base de datos.

---

## 4. Validación y Pruebas

- **Migración 009:** Aplicada con `python backend/migrate.py up --apply --version 009_iter7_reconciliacion_inventario`.
- **Suite de Pruebas de Regresión:**
  - `tests/test_pos_contingencia.py`: 5 passed
  - `tests/test_pwa_iter2.py`: 8 passed
  - `tests/test_ventas_reservas_flujo.py`: 5 passed
  - **Total:** 18 passed (100% éxito)
- **Frontend Build:** Compilación Angular completada limpiamente (0 errores).
