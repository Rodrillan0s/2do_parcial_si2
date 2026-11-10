# Changelog — Módulo de Reservas y Citas en Boutique (AuroraStore)

**Módulo:** Reservas de Prendas y Citas en Boutique (`CU10W`)  
**Ubicación:** `backend/app/modules/reservas/` & `frontend/src/app/components/product-detail-modal/`  
**Base de Datos:** PostgreSQL (`t_reserva`, `t_detalle_reserva`, `t_inventario`, `t_movimiento_inventario`, `t_bitacora`)  
**Estado:** Estable / Stock Liberado / Expiración Automática en Producción  

---

## [2026-11-06] — Saneamiento de Ciclo de Vida, Expiración Automática y Seguridad Financiera

### 1. Diagnóstico y Problemas Identificados
- **Prendas atrapadas indefinidamente:** Existían 26 reservas antiguas en estado `PENDIENTE` que no habían sido atendidas y mantenían 46 prendas bloqueadas en `stock_reservado`, reduciendo el `stock_disponible` para ventas en tienda física y online.
- **Riesgo en pagos anticipados no conciliados:** El modal de detalle de producto permitía marcar `con_pago=True` sin una pasarela financiera real conectada para reservas, lo cual abría la posibilidad de declarar cobros sin constancia contable.
- **Citas fuera de horario comercial:** No se validaba si la hora de la cita programada coincidía con los horarios de apertura y cierre de la sucursal elegida.
- **Sin límites de anticipación ni prendas:** No existían topes a la cantidad de prendas reservadas por cita ni a la antelación de la reserva.

### 2. Cambios Implementados

#### A. Expiración Automática con Liberación Atómica de Inventario (`reserva_repos.py`)
- Se implementó la función `expirar_reservas_vencidas(id_empresa: int, tolerancia_horas: int = 12)`:
  - Selecciona reservas en `PENDIENTE` cuya `fecha_hora_visita` haya superado la tolerancia (12 horas después de la cita programada).
  - Emplea bloqueo pesimista `FOR UPDATE` para garantizar consistencia transaccional sin condiciones de carrera.
  - Itera sobre cada detalle de reserva (`t_detalle_reserva`) y restituye el inventario atómicamente:
    - `UPDATE t_inventario SET stock_reservado = GREATEST(stock_reservado - cant, 0), stock_disponible = stock_disponible + cant`
    - Inserta un movimiento auditable en `t_movimiento_inventario` con tipo `LIBERACION_RESERVA` y motivo `EXPIRACION_AUTOMATICA`.
  - Actualiza `t_reserva.estado = 'VENCIDA'` y cada detalle a `estado_prenda = 'VENCIDA'`.
  - Registra el evento en `t_bitacora` (`modulo='RESERVAS'`, `accion='EXPIRACION_RESERVA_VENCIDA'`).
- **Llamados Oportunistas:** Se incorporó la ejecución automática de expiración al listar las reservas del cliente (`obtener_mis_reservas`) y al cargar el tablero de mostrador (`listar_reservas_para_atender`).
- **Endpoint Administrativo:** Se habilitó `POST /api/reservas/expirar-vencidas` para su invocación vía cron o tarea de mantenimiento periódico.

#### B. Saneamiento de la Base de Datos Real
- Se ejecutó el procedimiento contra la base de datos de producción:
  - **26 reservas vencidas** migradas a estado `VENCIDA`.
  - **46 prendas recuperadas** y reintegradas a `stock_disponible`.
  - **0 reservas vencidas pendientes** remanentes en el sistema.

#### C. Seguridad Financiera: Deshabilitación de `con_pago`
- Se deshabilitó la opción de pago anticipado no conciliado en el backend (`reserva_routes.py` y `reserva_repos.py`), forzando `con_pago = False` y `monto_pagado = 0.00`.
- En el frontend (`product-detail-modal.ts` y `product-detail-modal.html`), se eliminó el selector de pago anticipado y se dejó explícito que la reserva es una **Cita Gratuita de Prueba en Boutique**.

#### D. Políticas Comerciales y Límites de Reserva
- **Anticipación máxima:** Se restringió la programación de citas a un máximo de **7 días hábiles**.
- **Límite de prendas por cita:** Máximo **5 prendas** por cita para evitar acaparamientos y probadores saturados.
- **Límite de citas activas por cliente:** Máximo **3 reservas simultáneas** en estado `PENDIENTE`.
- **Validación de Horarios Comerciales:** Se verifica que la cita se encuentre dentro de `horario_apertura` y `horario_cierre` de la sucursal seleccionada (rango por defecto: 09:00 a 21:00).

#### E. Decisión Arquitectónica de Caja
- Se ratificó el uso de una **única caja registradora compartida por sucursal** entre el POS y las reservas. El módulo de reservas administra la cita y la prueba física de la prenda; al concluir la prueba satisfactoriamente, el cajero liquida la compra en el módulo POS registrando el comprobante de venta fiscal y el cobro en efectivo, QR o tarjeta.

---

## [2026-10-28] — Creación del Módulo de Reservas (Iteración 1)
- Creación de tablas `t_reserva` y `t_detalle_reserva` con aislamiento multitenant.
- Endpoint de reserva y función PL/pgSQL `fn_reservar_stock`.
- Soporte para visualización de reservas en mostrador y confirmación de asistencia.
