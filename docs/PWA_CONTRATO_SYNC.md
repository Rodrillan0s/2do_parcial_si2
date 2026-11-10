# AuroraStore — Contrato Común de Sincronización Offline-First (Angular PWA + Flutter SQLite)

**Fecha:** 2026-10-31
**Endpoints implementados:**  
- `GET /api/sync/ping`  
- `POST /api/sync/lote` *(endpoint canónico de procesamiento por lotes)*  
- `POST /api/sync/operations` *(alias compatible 1:1 con `/api/sync/lote`)*  

**Implementación en Backend:** `backend/app/modules/ecommerce/routes/sync_routes.py`  
**Persistencia de Idempotencia y Auditoría:** PostgreSQL obligatorio, migraciones 003 y 004. No existe fallback en memoria. Sin persistencia verificable se rechaza la operación sin confirmarla. Ambas migraciones fueron autorizadas, aplicadas y verificadas en el destino real el 2026-10-31; su reaplicación no produce cambios. Ver [acta de aplicación](SYNC_MIGRACION_APLICADA_2026-10-31.md) e [informe transaccional](SYNC_IDEMPOTENCIA_TRANSACCIONAL.md).

---

## 1. Propósito y Compatibilidad Multiplataforma

Este contrato fue diseñado e implementado en FastAPI para servir simultáneamente a:
1. **Angular PWA (Iteración 2 — Implementado):** Cola local en IndexedDB (`pending_operations`, `sync_attempts`, `sync_receipts` y `stock_snapshots`). La versión local 4 añade recibos conservando operaciones anteriores. Su retirada y el guardado del recibo/historial comparten una transacción; pendientes e historias críticas no usan fallback RAM ni se purgan en logout/401. Ver [resultados de retención](PWA_COLA_RETENCION_RESULTADOS.md).
2. **Flutter Mobile (Futura Iteración):** Deberá conservar el sobre original y validar la confirmación durable descrita aquí. Su implementación offline no comienza hasta verificar las migraciones reales y conciliar el legado sin recibos.

---

## 2. Sondeo Rápido de Conectividad Real (`GET /api/sync/ping`)

Permite a Angular (`NetworkStatusService`) y a Flutter verificar si existe conexión real con FastAPI sin tocar PostgreSQL (`0` consultas SQL).

### Respuesta (`200 OK`)
```json
{
  "success": true,
  "status": "ONLINE",
  "server_time": "2026-10-28T22:30:00.000000+00:00"
}
```

---

## 3. Identificadores Únicos, Estados Persistentes e Idempotencia (`CU38W`)

### 3.1. Identificador Único (`operation_id`)
- Cada operación generada offline lleva un **UUID v4 inmutable** (`operation_id`, p. ej. `f47ac10b-58cc-4372-a567-0e02b2c3d479`) generado en el cliente en el momento exacto de la acción.
- El `operation_id` nunca cambia en reintentos ni al resolver un conflicto de cantidad o precio sobre la misma operación.
- Para ventas de contado en efectivo (`VENTA_CONTADO`), el recibo provisional local se conserva; la referencia externa persistida usa `OFFLINE-{id_empresa}-{id_usuario}-{operation_id}` completo para evitar colisiones del prefijo de ocho caracteres.
- `created_at` conserva la fecha original ISO con zona horaria. Ventas/reservas sin recibo deben ser posteriores a `t_sync_control.inicio_garantia`; las previas, sin fecha o inválidas quedan en `LEGACY_OPERATION_REQUIRES_REVIEW`, sin ejecución automática. No cambiar fecha/UUID para eludir esa revisión.

### 3.2. Estados Persistentes de Operación (`status`)

| Estado (`status`) | Descripción | ¿Se reintenta automáticamente? | ¿Se elimina de `IndexedDB`? |
| :--- | :--- | :--- | :--- |
| `pending` | Operación registrada localmente en espera de conectividad. | Sí (FIFO por `created_at_ms`). | No. |
| `syncing` | En tránsito hacia `POST /api/sync/lote`. | Bloqueada contra envíos concurrentes; si la app se cierra a mitad de vuelo, al reiniciar vuelve a `pending`. | No. |
| `synced` | Efectos y recibo confirmados por el mismo COMMIT de PostgreSQL. | No; un reenvío recupera el resultado persistido con `idempotent_replay: true`. | Solo tras validar `confirmation_verified=true`, identidad de operación/usuario/empresa y resultado comercial, y conservar el recibo en historial local. HTTP 200 del lote no basta. |
| `conflict` | Rechazada por regla de negocio o conservada para revisión local. | No; un parche requiere rechazo de negocio conocido. Si el resultado es incierto, reenviar el sobre original. | No. La revisión o el descarte local no sustituyen una confirmación. |
| `reconciliation_required` | **Exclusivo de `VENTA_CONTADO` (CU24W)** cuando el servidor rechaza la venta en efectivo al reconectar (stock agotado, precio modificado, caja cerrada o producto inactivo). | No automático; permite reintentar (p. ej. tras abrir caja o aceptar precio/stock) o registrar nota de conciliación física de caja. | **Prohibido eliminar silenciosamente.** Se conserva como incidencia auditable tanto en `t_sync_operacion` (servidor) como en `IndexedDB` (cliente). |
| `failed_retryable` | Error transitorio de red (`status 0`) o servidor (`5xx`, timeout). | Sí, con backoff exponencial (`next_retry_at_ms`). | No. |
| `failed_permanent` | Rechazo definitivo de seguridad o contrato (`403 TENANT_FORBIDDEN`, `403 ROLE_FORBIDDEN`, `409 PAYMENT_REQUIRES_ONLINE`). | No. | Permanece visible para el usuario hasta su revisión. |

### 3.3. Garantía de Idempotencia en Servidor (`comercio.t_sync_operacion`)
- PK compuesta `(id_usuario, id_empresa, operation_id)` y bloqueo transaccional de esa clave en PostgreSQL, incluso antes de existir la fila. No reasignar una operación a otro usuario o tenant.
- Autorización en servidor también antes de un replay; una transacción comparte repositorios, efectos comerciales y recibo. No hay commits intermedios ni compensación posterior del cobro. Se exige `synchronous_commit=on`.
- Si existe recibo confirmado y la huella del contenido coincide, se devuelve su resultado con `idempotent_replay=true` sin repetir inventario, movimientos, reservas, ventas o pagos. Cambiar contenido confirmado o tipo produce `409 IDEMPOTENCY_KEY_REUSED`, sin modificar el recibo original.
- Un conflicto puede resolverse con la misma clave y tipo porque sus efectos comerciales se revierten al savepoint antes de guardar la incidencia. Si falla el guardado del recibo, se revierte todo.
- Respuesta confirmada: `confirmation_verified=true` y `confirmation: {operation_id, id_usuario, id_empresa, request_hash}`. La respuesta se entrega únicamente después del commit; el reenvío es el mecanismo de verificación si se pierde la respuesta HTTP. El campo confirma persistencia del servidor; no es una firma criptográfica.
- Sin tabla, columna, control de transición, conexión o commit verificable: `failed_retryable`, `http_status=503`, `PERSISTENT_IDEMPOTENCY_UNAVAILABLE`, `confirmation_verified=false`. El HTTP exterior continúa siendo 200 por compatibilidad del lote; revisar cada resultado individual y conservar la cola local.
- Un recibo legado sin huella devuelve `LEGACY_RECEIPT_REQUIRES_REVIEW`. Una operación anterior sin recibo devuelve `LEGACY_OPERATION_REQUIRES_REVIEW`. Ambos requieren revisión sin reejecución, purga o confirmación inventada. Un recibo confirmado no se modifica al recibir estos reenvíos.
- Los recibos no tienen TTL. Las FKs de 004 impiden eliminarlos en cascada al borrar usuarios/empresas. Cualquier archivo o eliminación requiere un procedimiento explícito que preserve la evidencia.

---

## 4. Aislamiento Multitenant y Autorización en Servidor

1. **Particionado Local (`IndexedDB`):** Todas las claves de `pending_operations`, `stock_snapshots`, `products`, `branches`, `reservations` y `cart_draft` incluyen el prefijo `u:{user_id}|e:{tenant_id}|b:{branch_id}`.
2. **Validación de Tenant en Servidor:**
   - Para operaciones de cliente (`CART_*`, `RESERVA_SOLICITUD`), `resolver_empresa_compra(token_data, op.tenant_id)` verifica que la empresa exista, esté activa, tenga suscripción SaaS vigente (`exigir_vigencia`) y que ningún usuario con rol de empresa opere fuera de su `id_empresa`.
   - Para operaciones administrativas de Punto de Venta (`VENTA_CONTADO`), el servidor exige:
     - Que el usuario autenticado tenga rol de personal (`ADMIN_EMPRESA`, `EMPLEADO` o `SUPER_ADMIN` con contexto), rechazando cualquier rol `CLIENTE` con `403 ROLE_FORBIDDEN`.
     - Que posea al menos uno de los permisos RBAC de caja/POS (`pos.vender`, `pos.cobrar` o `caja.ver`) verificados en base de datos, y `pos.descuento` si `descuento > 0`.
     - Que `op.tenant_id` coincida con la empresa autorizada del empleado y que la sucursal (`op.branch_id` / `payload.id_sucursal`) pertenezca a dicha empresa y el empleado tenga acceso a ella (`_obtener_sucursal_contexto`).

---

## 5. Procesamiento por Lotes (`POST /api/sync/lote` y `POST /api/sync/operations`)

### Formato de Solicitud (`SyncBatchRequestDTO`)
```json
{
  "operations": [
    {
      "operation_id": "f47ac10b-58cc-4372-a567-0e02b2c3d479",
      "kind": "VENTA_CONTADO",
      "tenant_id": 1,
      "branch_id": 1,
      "entity_id": "OFFLINE-E1-S1-F47AC10B",
      "client_version": "2026-10-28T22:15:00.000Z",
      "created_at": "2026-10-28T22:15:00.000Z",
      "payload": {
        "id_sucursal": 1,
        "id_sesion_caja": 12,
        "metodo_tipo": "EFECTIVO",
        "id_metodo_pago": 1,
        "descuento": 0,
        "monto_recibido": 200.00,
        "expected_total": 150.00,
        "accept_price_change": false,
        "datos_facturacion": {
          "nit_ci": "1234567",
          "razon_social": "CLIENTE MOSTRADOR"
        },
        "desglose_recibido": [],
        "desglose_cambio": [],
        "items": [
          {
            "id_variante": 100,
            "cantidad": 1,
            "expected_unit_price": 150.00
          }
        ]
      }
    }
  ]
}
```

### Tipos de Operación Soportados (`kind`)

| `kind` | Caso de Uso | Campos de `payload` | Comportamiento en Servidor |
| :--- | :--- | :--- | :--- |
| `CART_ADD_ITEM` | `CU08W` | `id_variante`, `cantidad`, `mode` (`"ADD"` \| `"SET"`), `expected_unit_price`, `accept_price_change` | Verifica que la prenda/variante esté activa, que el precio coincida y que exista stock disponible antes de insertar/fijar en `t_detalle_carrito`. |
| `CART_UPDATE_QTY` | `CU08W` | `id_detalle_carrito`, `id_variante`, `cantidad` | Si `id_detalle_carrito < 0` (creado offline), resuelve por `id_variante`. Valida stock disponible y actualiza cantidad. |
| `CART_REMOVE_ITEM` | `CU08W` | `id_detalle_carrito`, `id_variante` | Elimina la prenda del carrito activo del usuario para ese tenant. |
| `CART_CLEAR` | `CU08W` | `id_empresa` | Vacía el carrito activo del usuario en esa tienda. |
| `RESERVA_SOLICITUD` | `CU10W` | `id_sucursal`, `fecha_hora_visita`, `observaciones`, `items` (`[{id_variante, cantidad, expected_unit_price}]`), `con_pago` (`false`), `accept_price_change` | Valida vigencia SaaS, sucursal activa del tenant, precio vigente vs `expected_unit_price`, stock por variante en esa sucursal y ejecuta `crear_reserva` con bloqueo `FOR UPDATE`. Si `con_pago == true`, rechaza con `409 PAYMENT_REQUIRES_ONLINE`. |
| `VENTA_CONTADO` | `CU24W` | `id_sucursal`, `id_sesion_caja`, `metodo_tipo` (`"EFECTIVO"`), `id_metodo_pago`, `items` (`[{id_variante, cantidad, expected_unit_price}]`), `descuento`, `monto_recibido`, `datos_facturacion`, `desglose_recibido`, `desglose_cambio`, `accept_price_change` | Exige rol empleado/admin + permisos RBAC POS y `metodo_tipo == "EFECTIVO"`. Verifica sesión de caja abierta, vigencia de precios y stock físico en sucursal; registra atómicamente la venta (`fn_registrar_venta_pos`) y el cobro en efectivo (`ejecutar_pago_caja`). Si hay conflicto, devuelve `reconciliation_required: true` y persiste la incidencia en `t_sync_operacion`. |

---

## 6. Formato de Respuesta y Catálogo de Conflictos (`CU39W`)

```json
{
  "success": true,
  "total": 2,
  "synced_count": 1,
  "conflict_count": 1,
  "failed_count": 0,
  "server_time": "2026-10-28T22:31:00.000000+00:00",
  "results": [
    {
      "operation_id": "op-venta-1",
      "kind": "VENTA_CONTADO",
      "status": "synced",
      "http_status": 200,
      "conflict_code": null,
      "reconciliation_required": false,
      "message": "Venta de contado en efectivo sincronizada y cobrada (#V-2026-0045).",
      "data": {
        "id_venta": 45,
        "numero_venta": "V-2026-0045",
        "id_pago": 39,
        "codigo_transaccion": "TXN-20261028-EF91",
        "total": 150.0,
        "monto_recibido": 200.0,
        "cambio": 50.0,
        "estado_venta": "PAGADO"
      },
      "synced_at": "2026-10-28T22:31:00.000000+00:00",
      "idempotent_replay": false
    },
    {
      "operation_id": "op-venta-2",
      "kind": "VENTA_CONTADO",
      "status": "reconciliation_required",
      "http_status": 409,
      "conflict_code": "STOCK_INSUFFICIENT",
      "reconciliation_required": true,
      "message": "Incidencia de conciliación en venta en efectivo: Stock insuficiente para 'Abrigo Cachemira Imperial' (Talla M / Negro). Solicitaste 3 y hay 1 disponible(s).",
      "conflict_detail": {
        "id_variante": 100,
        "producto_nombre": "Abrigo Cachemira Imperial",
        "requested_quantity": 3,
        "available_stock": 1,
        "reconciliation_required": true
      }
    }
  ]
}
```

### Códigos de Conflicto Estándar (`conflict_code`)

| `conflict_code` | `http_status` | Causa | Acción de Resolución en UI (`CU39W`) |
| :--- | :--- | :--- | :--- |
| `STOCK_INSUFFICIENT` | `409` | La cantidad solicitada supera el stock disponible actual en servidor. | Botón **"Ajustar a X disponible(s) y sincronizar"**, **"Descartar"** (carrito/reserva) o **"Registrar Conciliación de Caja"** (`VENTA_CONTADO`). |
| `PRICE_CHANGED` | `409` | El precio vigente en servidor cambió respecto a `expected_unit_price`. | Botón **"Aceptar precio actual (Bs. Y) y sincronizar"** o **"Registrar Conciliación"** / **"Descartar"**. |
| `PRODUCT_INACTIVE` | `409` | El producto o variante fue desactivado mientras el cliente estaba offline. | Informar al usuario; permitir **"Descartar"** (carrito/reserva) o **"Registrar Conciliación de Caja"** (`VENTA_CONTADO`). |
| `BRANCH_INACTIVE` | `409` | La sucursal seleccionada no está activa o no pertenece a la empresa. | Informar al usuario y permitir resolución controlada. |
| `CAJA_CERRADA` | `409` | La sesión de caja donde se registró la venta offline fue cerrada y el cajero no tiene otra sesión abierta en la sucursal. | Permite al cajero **abrir turno de caja y pulsar "Reintentar Sincronización"** o registrar nota de conciliación. |
| `MONTO_INSUFICIENTE` | `409` | Tras un cambio de precio aceptado, el efectivo recibido (`monto_recibido`) es menor al nuevo total. | Permite ajustar el monto recibido o registrar conciliación de caja. |
| `PAYMENT_REQUIRES_ONLINE` | `409` | Intento de sincronizar una reserva pagada o una venta POS con método electrónico (`TARJETA`, `QR`, `PAYPAL`). | Bloqueado; pagos electrónicos requieren conexión en tiempo real. |
| `TENANT_FORBIDDEN` / `ROLE_FORBIDDEN` | `403` | El usuario no tiene permisos RBAC, no pertenece a la empresa/sucursal o la suscripción SaaS venció. | Informar el motivo de autorización. |

---

## 7. Stock Provisional Local vs Stock Confirmado del Servidor

- **Stock Confirmado (`stock` / `stock_actual`):** Valor proveniente de PostgreSQL (`comercio.t_inventario`) en la última lectura online o tras una sincronización exitosa.
- **Stock Provisional (`stock_snapshots` en `IndexedDB`):** Cada vez que se encola offline una `RESERVA_SOLICITUD` o `VENTA_CONTADO`, el cliente registra un descuento provisional por variante (`provisional_delta`) bajo la clave `u:{uid}|e:{tid}|b:{bid}_var_{id_variante}`.
- **Visualización Diferenciada:** La interfaz muestra el stock disponible efectivo (`max(0, stock_confirmado - delta_provisional)`) e identifica explícitamente cuándo una prenda tiene unidades comprometidas en la cola local pendiente de confirmación.
- **Reconciliación de Stock:** La confirmación verificable retira el pendiente y libera su stock provisional. Una venta/reserva incierta se conserva como compromiso provisional; una nota o petición de descarte no la confirma ni la elimina.

---

## 8. Esquema SQLite Equivalente para Futura App Móvil Flutter

```sql
CREATE TABLE pending_operations (
    operation_id TEXT PRIMARY KEY,
    scope_key TEXT NOT NULL,
    user_id INTEGER NOT NULL,
    tenant_id INTEGER NOT NULL,
    branch_id INTEGER,
    kind TEXT NOT NULL,
    entity_id TEXT,
    summary_label TEXT NOT NULL,
    payload_json TEXT NOT NULL,
    created_at TEXT NOT NULL,
    created_at_ms INTEGER NOT NULL,
    attempt_count INTEGER NOT NULL DEFAULT 0,
    next_retry_at_ms INTEGER,
    status TEXT NOT NULL DEFAULT 'pending',
    reconciliation_required INTEGER NOT NULL DEFAULT 0,
    reconciliation_note TEXT,
    last_error TEXT,
    conflict_code TEXT,
    conflict_detail_json TEXT,
    client_version TEXT
);
CREATE INDEX idx_pending_ops_scope ON pending_operations(scope_key, status, created_at_ms);
```
