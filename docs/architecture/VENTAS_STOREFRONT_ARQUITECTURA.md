# Arquitectura de Ventas y Pedidos StoreFront — AuroraStore

**Módulo:** Ventas E-commerce, Pedidos Online y Carrito Inteligente (`CU08W`, `CU09W`, `CU27W`)  
**Tecnologías:** Angular 21 · FastAPI · PostgreSQL  
**Ubicación:** `backend/app/modules/pedidos/`, `backend/app/modules/ecommerce/` & `frontend/src/app/pages/pedidos/`  
**Última Actualización:** 2026-11-07  
**Estado:** Estable / Reserva Atómica, Expiración Idempotente y Desacoplamiento de Citas Operativos  

---

## 1. Visión y Separación Conceptual de Flujos

AuroraStore atiende a dos tipos de intenciones de compra por parte del cliente común desde la web:

1. **Venta Online Directa (E-commerce / Pedidos):** El cliente desea comprar una prenda y asegura su adquisición pagando online o solicitando retiro en sucursal / envío a domicilio. Representa una **intención vinculante de compra**.
2. **Cita de Probador en Boutique (Reservas):** El cliente tiene dudas sobre el talle, la caída de la tela o la combinación estética y solicita una cita presencial para probarse prendas en el probador de una boutique física. **No es una compra ni genera asiento contable**, sino una experiencia previa a la venta.

```
┌────────────────────────────────────────────────────────────────────────────────────────┐
│                        MAPA DE CONVERGENCIA DE FLUJOS AURORASTORE                      │
│                                                                                        │
│   [ CATÁLOGO STOREFRONT ]                                                              │
│             │                                                                          │
│             ├─────────────────────────────────────┐                                    │
│             ▼                                     ▼                                    │
│   [ FLUJO 1: COMPRA ONLINE ]            [ FLUJO 2: CITA DE PROBADOR ]                  │
│   • Añadir a la Bolsa                   • Agendar Cita en Boutique                     │
│   • Dirección / Retiro                  • Hasta 5 prendas / 7 días anticipación        │
│   • Genera PEDIDO (PENDIENTE_PAGO)      • Genera RESERVA (PENDIENTE)                   │
│   • Reserva Stock en t_inventario       • Reserva Stock en t_inventario                │
│             │                                     │                                    │
│             ▼                                     ▼                                    │
│   [ Pago Online / Pasarela ]            [ Visita Presencial a la Tienda ]              │
│   • Consume stock_reservado             • Prueba en Probador Boutique                  │
│   • Genera Venta y Factura                        │                                    │
│             │                                     ├──────────────────────┐             │
│             ▼                                     ▼                      ▼             │
│   [ Despacho o Retiro ]                 [ Prendas Aceptadas ]   [ Prendas Rechazadas ] │
│   • Entrega al cliente                  • Cobro en POS          • Liberación a Stock   │
│                                         • Caja Única Sucursal     Disponible           │
└────────────────────────────────────────────────────────────────────────────────────────┘
```

---

## 2. Ciclo de Vida del Pedido y Máquina de Estados Ortogonales

Para evitar combinaciones ambiguas en el ciclo de vida de la orden, AuroraStore desacopla el **estado logístico del pedido** de su **estado financiero de pago**:

### A. Estados de Pedido (`t_pedido.estado`)
- **`PENDIENTE_PAGO`:** Pedido creado desde el carrito. El inventario se encuentra **reservado atómicamente** para el cliente.
- **`CONFIRMADO`:** Pago validado exitosamente por la pasarela o autorizado para preparación.
- **`EN_PREPARACION`:** El personal de la sucursal o almacén central está empaquetando los productos.
- **`LISTO_ENTREGA`:** Listo para retiro en mostrador o entregado al servicio de mensajería (`EN_CAMINO`).
- **`ENTREGADO`:** Pedido completado y recibido por el cliente final.
- **`CANCELADO`:** Pedido anulado voluntariamente por el cliente o expirado automáticamente por inactividad (+48h). El inventario reservado se libera inmediatamente a `stock_disponible`.

### B. Estados de Pago (`t_pedido.estado_pago`)
- **`PENDIENTE`:** En espera de confirmación de pasarela o transacción.
- **`PAGADO`:** Conciliado y procesado por el backend financiero.
- **`REEMBOLSADO`:** Fondos devueltos al cliente (total o parcialmente).
- **`FALLIDO`:** Rechazado por la pasarela o cancelado antes de pago.

---

## 3. Integridad Transaccional y Balance de Inventario

### A. Ecuación Inmutable de Balance de Stock
En todo momento, para cada variante de producto en cada sucursal física, debe cumplirse la siguiente igualdad:

$$\text{stock\_actual} = \text{stock\_disponible} + \text{stock\_reservado} + \text{stock\_contingencia}$$

Donde:
- `stock_actual`: Total de existencias físicas reales en el almacén de la sucursal.
- `stock_disponible`: Unidades que pueden ser adquiridas inmediatamente en el StoreFront.
- `stock_reservado`: Unidades comprometidas por pedidos online pendientes o reservas de probador en curso.
- `stock_contingencia`: Cuota de contingencia asignada a terminales POS para operaciones offline sin conexión.

### B. Reserva Atómica al Crear Pedido
Al invocarse `validar_y_crear_pedido`:
1. Se adquiere bloqueo pesimista `SELECT ... FOR UPDATE` sobre la fila correspondiente en `t_inventario`.
2. Se valida que $\text{stock\_disponible} \ge \text{cantidad\_solicitada}$.
3. Se incrementa `stock_reservado += cantidad` y se decrementa `stock_disponible -= cantidad`.
4. `stock_actual` permanece inalterado.
5. Se inserta un registro en `t_movimiento_inventario` con `tipo_movimiento = 'RESERVA'` y auditoría en `t_bitacora`.

### C. Consumo de Stock en Pago (`fn_confirmar_pago_pedido`)
Cuando el cliente concluye el pago de su orden pre-reservada:
1. El backend deduce prioritariamente las unidades desde `stock_reservado` en lugar de `stock_disponible`:
   $$\Delta \text{stock\_reservado} = -\text{cantidad}$$
   $$\Delta \text{stock\_actual} = -\text{cantidad}$$
   $$\Delta \text{stock\_disponible} = 0$$
2. Se previene la anomalía de "doble descuento" y se genera el movimiento contable `'VENTA'`.

### D. Cancelación y Expiración Transaccional
- **Cancelación Voluntaria (`cancelar_pedido_cliente`):**
  El cliente puede cancelar pedidos en estado `PENDIENTE_PAGO` desde su panel de control en `mis-pedidos`. La transacción valida pertenencia al tenant, restituye `stock_reservado` a `stock_disponible` y registra `tipo_movimiento = 'LIBERACION_RESERVA'`.
- **Expiración Automática por Inactividad (`expirar_pedidos_vencidos`):**
  Un pedido no pagado retiene existencias por un máximo de **48 horas**. Cumplido dicho plazo, el proceso de expiración (ejecutable periódicamente o de forma oportuna / JIT en consultas) cancela el pedido y restituye las existencias automáticamente.

---

## 4. Experiencia de Usuario en Frontend (Angular 21)

1. **Detalle de Producto (`ProductDetailModalComponent`):**
   - Presenta dos llamadas a la acción explícitas y visualmente jerarquizadas:
     - Botón principal de compra: «Añadir a la bolsa».
     - Botón secundario refinado: «Probar en tienda · Agendar cita».
   - Soporte para `@Input() modoInicial: 'PRODUCTO' | 'AGENDAR_CITA'`, permitiendo invocar directamente el selector de fecha, hora y boutique.
2. **Carrito Inteligente (`carrito-drawer`):**
   - Cada artículo en la bolsa incluye un disparador contextual: «¿Dudas con la talla? Probar en tienda →».
   - Al pulsar, navega fluidamente a `/catalogo?producto={id}&modo=cita` sin vaciar ni mutar el contenido del carrito.
3. **Gestión de Pedidos (`mis-pedidos`):**
   - Tarjetas de pedido con diferenciación por estado y modalidad de entrega.
   - Banners informativos que advierten la ventana de retención de 48 horas.
   - Botón reactivo de cancelación para pedidos no pagados, con modal modal de confirmación y feedback inmediato.
