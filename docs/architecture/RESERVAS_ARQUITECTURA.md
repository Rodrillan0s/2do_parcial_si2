# Arquitectura del Módulo de Reservas y Citas — AuroraStore

**Módulo:** Reservas de Prendas y Citas de Probador en Boutique (`CU10W`)  
**Tecnologías:** Angular 21 · FastAPI · PostgreSQL  
**Ubicación:** `backend/app/modules/reservas/` & `frontend/src/app/components/product-detail-modal/`  
**Última Actualización:** 2026-11-07  
**Estado:** Estable / Expiración Automática y Políticas de Integridad Operativas  

---

## 1. Visión y Propósito del Módulo

El módulo de reservas permite a los clientes programar citas presenciales en una sucursal física de la empresa para probarse prendas exclusivas de moda. A diferencia de una venta definitiva, la reserva aparta temporalmente unidades del inventario vendible sin generar un asiento contable de ingreso hasta que el cliente asiste a la boutique y decide adquirir la prenda.

```
┌──────────────────────────────────────────────────────────────────────────────────┐
│                             CICLO DE VIDA DE LA RESERVA                          │
│                                                                                  │
│   Cliente Storefront              Mostrador / Cajero POS          Expiración     │
│   ┌──────────────────┐            ┌──────────────────────┐        ┌────────────┐ │
│   │ 1. Programar Cita│            │ 2. Recepción Cliente │        │ Si excede  │ │
│   │ • Sucursal       │            │ • Revisión prendas   │        │ tolerancia │ │
│   │ • Fecha y Hora   │            │ • Cita en probador   │        │ (+12h):    │ │
│   │ • Hasta 5 prendas│            └──────────┬───────────┘        └──────┬─────┘ │
│   └─────────┬────────┘                       │                           │       │
│             │                                ▼                           ▼       │
│             ▼                         Compra en POS              Liberación      │
│      [ PENDIENTE ] ──────────────► [ ATENDIDA ]            [ VENCIDA ]           │
│      Stock: Reservado                 Stock: Vendido              Stock: Libre   │
└──────────────────────────────────────────────────────────────────────────────────┘
```

---

## 2. Decisiones Arquitectónicas Fundamentales

### A. Caja Registradora Única y Compartida por Sucursal
- Se ratificó mantener una **única caja registradora activa por sucursal**, compartida armónicamente entre el sistema POS y el mostrador de reservas.
- Las reservas administran la agenda, la bienvenida y la experiencia de probador.
- Las ventas finales resultantes de las reservas se liquidan exclusivamente mediante el módulo POS, garantizando que el arqueo de caja, el control de turnos y la emisión de comprobantes fiscales residan en un único punto contable auditable.

### B. Seguridad Financiera: Exclusividad de Cobro Presencial en POS
- Se inhabilitó el parámetro `con_pago=True` en la creación de reservas online.
- Motivo: declarar pagos anticipados sin una conciliación instantánea con pasarela financiera abría vulnerabilidades operativas y riesgos de cobros no respaldados. Todas las citas son gratuitas y cualquier pago se realiza frente al cajero al término de la prueba.

### C. Políticas Comerciales de Reserva
1. **Anticipación máxima:** Se permite agendar citas con un máximo de **7 días calendario** de antelación.
2. **Límite de prendas por cita:** Máximo **5 prendas** por reserva para evitar acaparamiento de stock escaso.
3. **Límite de citas simultáneas:** Un cliente solo puede tener hasta **3 reservas activas** en estado `PENDIENTE`.
4. **Validación de Horarios Comerciales:** El sistema contrasta la fecha y hora de la cita con las columnas `horario_apertura` y `horario_cierre` de la sucursal elegida (horario estándar: 09:00 a 21:00).

---

## 3. Máquina de Estados y Gestión Atómica de Inventario

La tabla `t_reserva` coordina con las tablas `t_detalle_reserva` e `t_inventario` a través de los siguientes estados:

| Estado Reserva | Estado Detalle | Efecto en `t_inventario` | Movimiento Registrado |
| :--- | :--- | :--- | :--- |
| **`PENDIENTE`** | `RESERVADA` | `stock_reservado += cant`, `stock_disponible -= cant` | `RESERVA` en `t_movimiento_inventario` |
| **`ATENDIDA`** | `VENDIDA` / `LIBERADA` | Se transfiere a venta POS: `stock_reservado -= cant`, `stock_actual -= cant` | `VENTA_POS` en `t_movimiento_inventario` |
| **`CANCELADA`** | `CANCELADA` | `stock_reservado -= cant`, `stock_disponible += cant` | `LIBERACION_RESERVA` |
| **`VENCIDA`** | `VENCIDA` | `stock_reservado -= cant`, `stock_disponible += cant` | `LIBERACION_RESERVA` (Motivo: `EXPIRACION_AUTOMATICA`) |

---

## 4. Algoritmo de Expiración Automática (`expirar_reservas_vencidas`)

Para resolver el problema histórico de prendas atrapadas indefinidamente, se implementó el procedimiento de saneamiento periódico:

```python
def expirar_reservas_vencidas(id_empresa: int, tolerancia_horas: int = 12):
    # 1. Bloqueo transaccional FOR UPDATE sobre reservas PENDIENTE vencidas
    # 2. Por cada detalle de reserva:
    #      stock_reservado = GREATEST(stock_reservado - cant, 0)
    #      stock_disponible = stock_disponible + cant
    #      INSERT INTO t_movimiento_inventario (tipo='LIBERACION_RESERVA', ...)
    # 3. UPDATE t_reserva SET estado = 'VENCIDA'
    # 4. INSERT INTO t_bitacora (modulo='RESERVAS', accion='EXPIRACION_RESERVA_VENCIDA', ...)
```

### Mecanismos de Activación:
1. **Llamadas Oportunistas (Just-In-Time):** Al invocar `obtener_mis_reservas` (Storefront) o `listar_reservas_para_atender` (Mostrador), el sistema ejecuta oportunamente la expiración para el tenant actual sin sobrecargar el servidor.
2. **Endpoint Programable:** `POST /api/reservas/expirar-vencidas` para ejecución mediante cron de mantenimiento diario.
