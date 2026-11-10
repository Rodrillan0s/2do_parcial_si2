# AuroraStore — Implementación de Devoluciones Online (Iteración 3: CU24W & CU25W)

> Estado verificado por Codex, 2026-11-01: 005 **no está aplicada en el destino real configurado** y su historial en otros entornos sigue sin verificar. Se corrigió backend en entorno aislado; no se cambió esquema ni datos reales. El contrato vigente, cambios, pruebas y pendientes están en [Correcciones críticas, sección 2](CORRECCIONES_CRITICAS_2026-11-01.md#2-corregido-en-código). Las recepciones parciales/mixtas y los reembolsos, incluido el inmediato, están **bloqueados de forma segura**; una referencia no acredita un egreso. Una recepción completa válida conserva cantidad/condición/receptor/fecha en la transacción y su auditoría. Sin estructura 005, la operación devuelve 503.
>
> Las secciones siguientes conservan el informe del avance original para trazabilidad. Sus afirmaciones sobre liquidación, permisos, tipos SQL y pruebas antiguas **no certifican el comportamiento actual ni autorizan aplicar 005**. En el contrato actual se usan `SOLICITUD_CLIENTE` / `PRESENCIAL_MOSTRADOR`, `estado_item`, `devoluciones.aprobar_rechazar`, y movimiento `ENTRADA`; CAJERO no recibe permiso de reembolso en 005. Las 8 pruebas de devolución actuales comprueban el bloqueo del reembolso y la conservación de datos, no su liquidación exitosa. No se inició una normalización general.

## 1. Resumen Ejecutivo y Alcance
- **Casos de Uso Implementados:**
  - **CU25W — Solicitar devolución:** Orientado al actor `CLIENTE`. Permite seleccionar compras previas entregadas o pagadas, elegir prendas y cantidades elegibles (descontando devoluciones previas o en curso), seleccionar motivo tipificado, ingresar descripción y evidencia opcional, y consultar la trazabilidad y estado de sus solicitudes en "Mis Devoluciones".
  - **CU24W — Gestionar devoluciones:** Orientado al personal autorizado (`CAJERO`, `ENCARGADO_SUCURSAL`, `ADMINISTRADOR_TIENDA`). Bandeja de filtrado multicriterio, consulta de detalle con trazabilidad y prendas, dictamen técnico formal (Aprobar / Rechazar), registro de devolución presencial directa en mostrador con reingreso automático al stock y opción de reembolso inmediato en efectivo, recepción física e inspección con discriminación estricta de condición (`REVENDIBLE` reingresa al inventario vendible vs `DEFECTUOSO` que se retiene en merma sin inflar stock comercializable), y registro/liquidación de reembolso financiero con método y referencia bancaria comprobable.
- **Límites de Seguridad y Principios Clave:**
  - **Exclusivamente Online:** FastAPI y PostgreSQL son la única fuente de verdad. No se utiliza `sync_queue`, IndexedDB ni colas offline para devoluciones.
  - **Bloqueo de Ventas en Conciliación o No Confirmadas:** Una venta POS con sincronización pendiente o en conflicto (`reconciliation_required`) no admite devoluciones hasta ser conciliada en la base de datos central.
  - **Aislamiento Multitenant Estricto:** La pertenencia de la empresa (`id_empresa`) y sucursal (`id_sucursal`) se valida en servidor en cada endpoint. Para clientes, el `id_empresa` se deriva de la compra original verificada en base de datos.
  - **No Ficticio:** El sistema registra y liquida los reembolsos con trazabilidad de método y comprobante/referencia sin simular transacciones externas automáticas con pasarelas de pago no configuradas.

---

## 2. Esquema de Base de Datos y Migración 005
La migración no destructiva e idempotente extiende las tablas existentes `t_devolucion` y `t_detalle_devolucion` en el esquema PostgreSQL (`comercio`):
- Archivos creados:
  - `backend/migrations/005_iter3_devoluciones.up.sql`
  - `backend/migrations/005_iter3_devoluciones.down.sql`

### Columnas Incorporadas:
1. `comercio.t_devolucion`:
   - `codigo_devolucion VARCHAR(30) UNIQUE NOT NULL` (Secuencia legible `DEV-YYYYMMDD-XXXXXX`).
   - `id_empresa INTEGER REFERENCES comercio.empresa(id_empresa)` (Tenant).
   - `id_sucursal INTEGER REFERENCES comercio.t_sucursal(id_sucursal)` (Sucursal de recepción).
   - `tipo_devolucion VARCHAR(20) DEFAULT 'ONLINE'` (`ONLINE` vs `PRESENCIAL`).
   - `id_usuario_revisor INTEGER REFERENCES comercio.t_usuario(id_usuario)` (Auditor o encargado).
   - `fecha_resolucion TIMESTAMP WITH TIME ZONE`.
   - `observaciones_resolucion TEXT` (Justificación técnica del dictamen).
   - `metodo_reembolso VARCHAR(50)` (`EFECTIVO`, `TRANSFERENCIA`, `VALE_TIENDA`, `TARJETA_PASARELA`).
   - `referencia_reembolso VARCHAR(150)` (Código de transacción o comprobante).
   - `fecha_reembolso TIMESTAMP WITH TIME ZONE`.
   - `descripcion_cliente TEXT` y `evidencia_url TEXT`.
2. `comercio.t_detalle_devolucion`:
   - `id_detalle_venta INTEGER REFERENCES comercio.t_detalle_venta(id_detalle_venta)` (Ítem original).
   - `condicion VARCHAR(30) DEFAULT 'REVENDIBLE'` (`REVENDIBLE` vs `DEFECTUOSO`).
   - `descuento_unitario NUMERIC(12,2) DEFAULT 0.00`.
   - `monto_reembolso NUMERIC(12,2) NOT NULL`.
   - `estado VARCHAR(30) DEFAULT 'SOLICITADO'`.

### Permisos RBAC Sembrados:
- `devoluciones.ver`: Permite listar y consultar detalles de devoluciones. Asignado a `ADMINISTRADOR`, `ENCARGADO_SUCURSAL`, `CAJERO`.
- `devoluciones.crear_presencial`: Permite registrar devoluciones en mostrador POS. Asignado a `ADMINISTRADOR`, `ENCARGADO_SUCURSAL`, `CAJERO`.
- `devoluciones.revisar`: Permite poner en revisión o evaluar solicitudes. Asignado a `ADMINISTRADOR`, `ENCARGADO_SUCURSAL`.
- `devoluciones.aprobar`: Permite dictaminar (Aprobar / Rechazar). Asignado a `ADMINISTRADOR`, `ENCARGADO_SUCURSAL`.
- `devoluciones.recibir`: Permite inspeccionar físicamente y modificar inventario. Asignado a `ADMINISTRADOR`, `ENCARGADO_SUCURSAL`, `CAJERO`.
- `devoluciones.reembolsar`: Permite liquidar el reembolso financiero. Asignado a `ADMINISTRADOR`, `ENCARGADO_SUCURSAL`, `CAJERO`.

---

## 3. Endpoints de la API Backend (`/api/devoluciones`)

| Método | Ruta | Actor / Permiso | Propósito |
| :--- | :--- | :--- | :--- |
| `GET` | `/api/devoluciones/ventas/{id_venta}/elegibilidad` | Token activo | Comprueba elegibilidad, bloqueos por conciliación y saldo devolvible por ítem con precios netos. |
| `POST` | `/api/devoluciones/solicitudes` | `CLIENTE` | Crea solicitud online en estado `SOLICITADA` validando que las prendas pertenezcan al usuario. |
| `GET` | `/api/devoluciones/mis-solicitudes` | `CLIENTE` | Lista solicitudes propias del cliente autenticado con paginación. |
| `GET` | `/api/devoluciones/mis-solicitudes/{id}` | `CLIENTE` | Detalle completo de la solicitud propia, resolución técnica y datos de reembolso. |
| `GET` | `/api/devoluciones` | `devoluciones.ver` | Bandeja de gestión con filtros por estado, sucursal, fechas, búsqueda libre y paginación. |
| `GET` | `/api/devoluciones/{id}` | `devoluciones.ver` | Detalle administrativo completo con auditoría e ítems. |
| `POST` | `/api/devoluciones/presencial` | `devoluciones.crear_presencial` | Registro directo en mostrador; actualiza stock según condición (`REVENDIBLE`/`DEFECTUOSO`) y opcionalmente liquida reembolso en efectivo. |
| `POST` | `/api/devoluciones/{id}/revisar` | `devoluciones.revisar`/`aprobar` | Dictamen técnico formal: `APROBAR` (pasa a `PENDIENTE_RECEPCION`) o `RECHAZAR` con justificación obligatoria. |
| `POST` | `/api/devoluciones/{id}/recepcion` | `devoluciones.recibir` | Recepción física en sucursal: incrementa stock vendible solo para unidades `REVENDIBLE` con movimiento `ENTRADA_DEVOLUCION`; retiene defectuosas en merma. Estado pasa a `RECIBIDA` / `PENDIENTE_REEMBOLSO`. |
| `POST` | `/api/devoluciones/{id}/reembolso` | `devoluciones.reembolsar` | Liquidación contable del reembolso con método y comprobante. Estado avanza a `COMPLETADA`. |

---

## 4. Frontend Angular 19 (CU24W & CU25W)

### 4.1 CU25W — Cliente en `Mis Pedidos`:
- **Ruta:** `/mis-pedidos` (Componente `MisPedidosComponent`).
- **Selector de Pestañas:**
  - Tab 1: **Mis Pedidos** (historial con filtros y detalle de pedidos).
  - Tab 2: **Mis Devoluciones** (listado de devoluciones solicitadas con insignias de estado, fecha, prendas, monto a reembolsar y detalle con modal de resolución y liquidación).
- **Acción en Detalle de Pedido:**
  - Para pedidos pagados/entregados vinculados a una venta (`id_venta`), se muestra el botón **"Solicitar Devolución de Prendas"**.
  - Abre el modal de solicitud:
    - Consulta reactiva de elegibilidad y saldo de prendas.
    - Checkbox y control numérico de cantidad por prenda ($\le$ saldo elegible).
    - Selector de motivo (`DEFECTO_FABRICA`, `TALLA_INCORRECTA`, `PRODUCTO_EQUIVOCADO`, `DANO_TRANSPORTE`, `OTRO`).
    - Campo de descripción detallada y enlace de fotografía/evidencia.
    - Cálculo dinámico en tiempo real del monto estimado a reembolsar (proporcional con descuentos).
    - Aviso de procesamiento exclusivamente online.

### 4.2 CU24W — Personal Autorizado en `Devoluciones & Garantías`:
- **Ruta:** `/admin/devoluciones` (Componente `DevolucionesComponent`).
- **Menú Lateral:** Enlace visible bajo "VENTAS & POS" -> "Devoluciones & Garantías" para roles con permiso `devoluciones.ver`.
- **Bandeja de Devoluciones:**
  - Filtros avanzados: búsqueda por código/venta/cliente, selector de estado, selector de sucursal, paginación server-side.
  - Identificación visual de tipo de devolución (`ONLINE` vs `PRESENCIAL`).
  - Botón de **"Nueva Devolución Presencial"** para cajeros y encargados.
  - Modales especializados según permisos del actor:
    - **Modal Detalle Completo:** visualización de historial, motivos, evidencias, revisor, dictamen y datos bancarios.
    - **Modal Devolución Presencial:** búsqueda de venta por ID, selección de prendas, asignación de condición (`REVENDIBLE`/`DEFECTUOSO`), y cobro/reembolso inmediato en efectivo.
    - **Modal Dictamen:** resolución formal con justificación técnica (`APROBAR`/`RECHAZAR`).
    - **Modal Recepción Física:** confirmación de prendas recibidas, asignación de sucursal y discriminación de condición física.
    - **Modal Liquidación Reembolso:** registro de método de pago y número de comprobante/autorización.

---

## 5. Pruebas y Verificación

### 5.1 Suite Automatizada de Devoluciones (`tests/test_devoluciones_iter3.py`)
Ejecutada en `LocalPostgres` aislado (disponible y descartable):
- `test_01_cliente_solicita_devolucion_valida`: Solicitud exitosa, validación de pertenencia e importes netos proporcionales. **PASSED**
- `test_02_cliente_no_puede_ver_ni_devolver_venta_ajena`: Prevención estricta de acceso cruzado entre usuarios y tenants (HTTP 403/404). **PASSED**
- `test_03_rechazo_cantidades_mayores_a_elegibles`: Bloqueo de devoluciones con cantidades superiores al saldo vendido/remanente. **PASSED**
- `test_04_bloqueo_venta_no_confirmada`: Bloqueo de devoluciones en ventas pendientes de pago o en conciliación de sincronización. **PASSED**
- `test_05_flujo_completo_personal_aprobacion_recepcion_reembolso`: Ciclo de vida completo: `SOLICITADA` $\rightarrow$ `APROBADA` $\rightarrow$ `RECIBIDA` (con reincorporación a stock) $\rightarrow$ `COMPLETADA` (reembolso liquidado). **PASSED**
- `test_06_recepcion_defectuosa_no_incrementa_stock_disponible`: Unidades `DEFECTUOSO` no inflan el inventario comercializable. **PASSED**
- `test_07_devolucion_presencial_mostrador_con_reembolso_efectivo`: Registro directo presencial con actualización inmediata de stock y comprobante de efectivo. **PASSED**
- `test_08_reversibilidad_migracion_005_down_up`: Ejecución exitosa de rollback (`down.sql`) y reaplicación (`up.sql`) sin pérdida de consistencia. **PASSED**

### 5.2 Regresión y Build
- **Regresión Backend:** 37 de 37 pruebas pasaron en `test_iter1.py` y `test_pwa_iter2.py` (Total 45/45 pruebas backend aprobadas).
- **Frontend Build (`ng build`):** Compilación de producción completada con **cero errores** de TypeScript y plantillas (chunks `mis-pedidos` y `devoluciones` generados limpiamente).

