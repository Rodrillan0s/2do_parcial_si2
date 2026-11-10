# Correcciones críticas sin normalización general

Fecha: 2026-11-01. Correcciones preventivas implementadas en backend; **ninguna migración, reparación comercial o despliegue real ejecutado en esta tarea**. Se conservaron la rama y los cambios previos del workspace. Diagnóstico inicial 00:25 y ampliado 00:44:42 −04 mediante `backend/audit_critical_integrity.py`, con conexión READ ONLY / REPEATABLE READ, sin importar la aplicación. Las cifras revalidadas no cambiaron.

## Matriz de verificación previa a cambios

| Hallazgo | Anterior → actual | Evidencia / causa | Función o camino | Arreglo mínimo previsto | Compatibilidad |
| --- | --- | --- | --- | --- | --- |
| Variantes con catálogos ajenos | 513 → 513 | FK independientes; generación del repositorio no comprueba pertenencia y depende del llamador | `sincronizar_variantes_producto`, validaciones producto/inventario | Validar en servidor y dentro de la transacción; bloquear asociación incompatible | Conservar IDs, entidades y flujos plataforma; mapa histórico requiere aprobación |
| Disponible incoherente | 5.691 → 5.691 | Fórmula documentada `actual-reservado`; escritores que suman/restan sobre disponible previo y funciones SQL que lo usan como límite | POS/reservas/compras/importación/inventario/atención/devolución | Bloqueo y validación de posición, orden estable, exclusión de creación concurrente; no reparar saldos históricos automáticamente | Posiciones inconsistentes requieren conciliación explícita, no crear stock por defecto |
| Inventario duplicado por sucursal/variante | 0 → 0 | Sin UNIQUE efectivo; SELECT seguido de INSERT deja ventana de carrera | Compras y recepción | Serializar la posición ausente y proponer UNIQUE mínimo por separado | Sin aplicar restricciones reales |
| Variante incompleta | 1 → 1 | NULL permitido; significado no confirmado | Escrituras de catálogo | Prevenir nuevas referencias inválidas en caminos corregidos | No inventar talla/color histórico |
| Perfiles cliente duplicados | 3 cuentas / 16 adicionales → igual | `LIMIT 1` por usuario determina arbitrariamente identidad | Carrito, historial, reservas y devoluciones | Autorizar por cuenta/compra real; bloquear creación ambigua y serializar creación de perfil | Conservar perfiles y referencias; mapa sin fusiones |
| Pedido PAGADO sin venta | 1 → 1 | Origen/evidencia por rastrear; función SQL y confirmación de pago deben ser atómicas | Pedido / `fn_confirmar_pago_pedido` | Prevenir confirmación parcial o falso éxito, conservar caso histórico | No inventar transacción ni cambiar estado |
| SKU repetido por tenant | 1 grupo → 1 | Generación truncada puede colisionar; falta unicidad de negocio | Generador de variantes | Comprobar colisiones nuevas bajo bloqueo | No renombrar SKU histórico |
| Devoluciones y 005 | 0/0, no aplicada → igual | Cantidades repetidas, parcial no persistido, dinero float y reembolso solo de cabecera | Repositorio/servicios de devoluciones | Validar propiedad/sucursal, acumular cantidades, Decimal, transacción con auditoría; bloquear parcial/reembolso sin soporte | No ejecutar ni reescribir 005; propuesta mínima separada |
| Multirrol | 1 → 1 | Modelo en uso | RBAC | Mantener intacto | Sin rediseño de roles |

La evidencia actual está en `docs/evidencias/correcciones_criticas_2026-11-01/`: SQL de comprobación, restricciones/índices/triggers, funciones de stock leídas, CSV por posición, candidatos de talla/color **no aprobados**, referencias de perfiles cliente y pedido/SKU pendientes. Los candidatos por nombre/HEX son pistas de revisión, nunca autorización para reasignar IDs.

## Límites de esta intervención

No aplicar 005 ni otra migración real. No modificar 001/003/004 ni sincronización/offline, Angular, mobile, notificaciones, roles, proveedores, SaaS o CU41W. No reparar ni borrar registros históricos. Las ampliaciones mínimas que resulten necesarias se presentan como propuestas para aprobación; las acciones sin evidencia suficiente deben fallar sin éxito simulado.

## 1. Hallazgos revalidados y origen

El SQL exacto de cada comprobación está en [diagnostico_consultas.sql](evidencias/correcciones_criticas_2026-11-01/diagnostico_consultas.sql); parámetros y lecturas adicionales del pedido están en el JSON de evidencia. Las consultas de cada ejecución comparten snapshot REPEATABLE READ. No demuestran el origen de cada fila histórica.

- **513 variantes, 474 de empresa 1 y 39 de empresa 2:** la importación de lotes buscaba talla/color por nombre sin empresa; puede reproducir la mezcla. El repositorio de variantes confiaba en la validación del llamador. Eso acredita defectos preventivos; no identifica quién creó cada referencia histórica. Se exportaron IDs y candidatos, sin reasignarlos.
- **5.691/6.019 saldos discrepantes:** 5.426 disponibles superiores a actual−reservado, 265 inferiores. Los escritores inspeccionados utilizan esa fórmula, sin otra retención persistente encontrada. Sumaban/restaban sobre disponible previo, propagando discrepancias, y algunas creaciones de posición no bloqueaban la ausencia. Los 224 movimientos históricos no reconstruyen por sí solos todos los saldos iniciales.
- **3 cuentas, 16 perfiles adicionales:** `LIMIT 1` escogía una identidad arbitraria. Los mapas corresponden a cuentas 9991, 9992 y 9993 y conservan todas las FK comerciales encontradas. No se eligió canónico.
- **Pedido 8882**, cliente 9, empresa 1, total Bs 1.180, `PAGADO` sin venta: detalle 10 / variante 16 / una unidad / subtotal Bs 1.200. No se encontró recibo sync ni auditoría con enlace explícito al pedido, ni venta de ese cliente/tenant/total. El origen exacto y la acreditación del pago siguen sin probarse. El flujo SQL actual escribe venta, pago y enlace dentro de una transacción; no se atribuye el caso antiguo a esa función sin evidencia.
- **Un grupo SKU repetido:** empresa 1, variantes 154/157. Los generadores truncaban talla/color y no comprobaban una colisión en el tenant. La regla de unicidad comercial y el significado de las etiquetas históricas necesitan validación.
- **Una variante incompleta, un usuario multirrol y devoluciones 0/0:** no se rellenó la variante ni se eliminó el puente de roles. 005 no figura aplicada en el destino configurado; el ledger conserva 003/004. Se desconoce el historial de otros destinos, por lo que se preservó también 005.

Desglose reproducible de posiciones discrepantes, según empresa/sucursal y existencia de movimientos; **tener movimientos no prueba que estos expliquen el saldo completo**:

| Empresa / sucursal | Con movimientos | Sin movimientos | Total |
| --- | ---: | ---: | ---: |
| 1 / 1 | 54 | 1.264 | 1.318 |
| 1 / 2 | 10 | 1.263 | 1.273 |
| 2 / 3 | 0 | 773 | 773 |
| 1 / 4 | 4 | 765 | 769 |
| 2 / 5 | 30 | 770 | 800 |
| 1 / 7 | 0 | 758 | 758 |
| **Total** | **98** | **5.593** | **5.691** |

Procedimiento de conciliación pendiente: validar definición comercial; contrastar por posición ingresos documentados, ventas y reservas activas, saldos iniciales y conteo físico si falta historia; aprobar los tres saldos y su evidencia por ID; preparar ejecución condicional con valores anteriores y mapa de reversión; volver a comprobar stock y documentos. No basta asignar disponible=actual−reservado: podría habilitar ventas de existencias no demostradas.

## 2. Corregido en código

| Dominio / archivos y funciones | Antes → después |
| --- | --- |
| `catalogo/repos/productos_repos.py`: crear, actualizar y sincronizar variantes; `catalogo/services/productos_services.py` | Producto y variantes podían confirmar por separado; generación dependía de ON CONFLICT sobre una restricción ausente en la base real. Ahora comparten transacción, validan categoría/talla/color contra empresa del producto y serializan catálogo/SKU antes de insertar. Colisión nueva: 409, sin renombrar historia. |
| `inventario/services/compras_lotes_services.py`: importar lote, recibir orden | Talla/color por nombre global y lectura seguida de INSERT sin exclusión. Ahora la búsqueda limita tenant/compartidos, se serializa catálogo y posición ausente, se bloquea la orden para no recibirla dos veces y se comprueba stock antes/después. Proveedores compartidos se conservan. |
| `core/inventory_integrity.py`; POS, reservas, atención, movimiento manual, compras, devolución | Guardia local compartida por escritores existentes: tenant de sucursal/producto/categoría/talla/color, cantidades positivas acumuladas, bloqueo de posición en orden estable, exclusión transaccional incluso cuando no existe y rechazo de saldos nulos/negativos/duplicados/incoherentes. No elige ni recalcula un saldo histórico. |
| `pos/repos/pos_repos.py`: registrar/anular pendiente | Venta valida sesión real y stock acumulado antes de la función SQL; venta, movimientos y pago conservan la transacción compartida existente. Anulación serializa inventario y valida el resultado. |
| `pos/repos/caja_pago_repos.py`, `caja_repos.py` | Bloqueo de venta evita dos pagos simultáneos. Sesión de pago debe ser la activa del cajero y coincidir con empresa/sucursal. Apertura bloquea usuario y caja; comprueba caja/sucursal/empresa y serializa dos aperturas. Se conservan las tres columnas. |
| `reservas/repos/reserva_repos.py`, `atender_reserva_repos.py` | Se suman cantidades repetidas antes de apartar, se bloquean posiciones y se impide liberar más reservado del existente. Cancelación y atención validan saldos en la misma transacción. Atención comprueba tenant/cajero de sesión. Una reserva declarada pagada sin venta acreditada, o un rechazo que exigiría reintegro de una entrega pagada, requiere conciliación. |
| `ecommerce/repos/pago_repos.py`, `routes/pago_routes.py` | Pedido y prendas se bloquean antes de confirmar; importe exacto positivo contra total real, propiedad por cuenta, tenant/stock y comprobación final de venta/pago/enlace. Segundo intento: 409 sin segundo cobro local. Se propaga HTTP 409 en vez de convertirlo en 500. |
| `ecommerce/repos/carrito_repos.py`; `pedidos/repos/pedido_repos.py`; lecturas/cancelación de reservas | Perfil existente se consulta con detección de duplicados; se serializa solo la creación ausente. Con varios perfiles: 409 para nuevas operaciones ambiguas. Historial, detalle, cancelación y devolución autorizan por cuenta del perfil realmente referenciado. Checkout comparte transacción, bloquea carrito y rechaza referencias de catálogos ajenos. |
| `pedidos/repos/devoluciones_repos.py`, `devolucion_importes.py`, `services/devoluciones_services.py` | Tenant derivado de venta del usuario, permisos y sucursales en servidor, body sin detalles repetidos, límites acumulados bajo bloqueo de venta; Decimal y reparto determinista de descuentos/centavos/topes. Verificación sync consulta `data.id_venta`, contrasta huella/confirmación persistida y falla si falta infraestructura. Mutación, stock, movimiento y auditoría crítica comparten transacción. |

La guardia protege los caminos de esta versión de backend. No sustituye restricciones de base frente a SQL externo ni protege instancias antiguas que no la ejecuten. Un saldo inconsistente produce **409 `INVENTORY_RECONCILIATION_REQUIRED`** y conserva sus valores: afecta a operaciones sobre posiciones pendientes de conciliación. No es una reparación de las 5.691 filas. Se mantienen las consultas agrupadas del catálogo/carrito; las escrituras de stock incorporan consultas de bloqueo adicionales, sin afirmar una medición global de carga.

### Contrato efectivo de devoluciones para Antigravity

Se mantienen rutas, DTO y estados existentes; no se modifica Angular ni la cola. Las devoluciones siguen exclusivamente online.

- Tipos vigentes: `SOLICITUD_CLIENTE` / `PRESENCIAL_MOSTRADOR`; detalle `estado_item`; aprobación asigna `PENDIENTE_RECEPCION`; recepción completa asigna `PENDIENTE_REEMBOLSO`. Rechazo resuelve `RECHAZAR` → `RECHAZADA` correctamente. Movimiento de retorno conserva `ENTRADA` con motivo/ID de devolución.
- Permiso de dictamen vigente: `devoluciones.aprobar_rechazar`. `EMPRESA` se reconoce como alcance; un cliente con empresa heredada sigue validándose por su compra. El permiso `devoluciones.ver` de cliente no lo convierte en personal. Los roles personalizados continúan dependiendo de sus permisos/contexto del servidor. 005 asigna a CAJERO ver/crear presencial/recibir, **no reembolsar**; no se cambió esa siembra.
- Falta de estructura 005: **503 `RETURNS_SCHEMA_NOT_READY`**, sin autoaplicarla. Falta de infraestructura de recibos: 503; no se omite la comprobación. Un recibo conflictivo, o uno legado marcado synced sin huella/confirmación verificable, bloquea solicitud/presencial.
- Solicitud idéntica (misma venta, cuenta, tipo, motivo, descripción/evidencia e ítems/condiciones) reutiliza la devolución persistente, incluso tras perder respuesta y reiniciar el proceso. No genera otra cabecera ni otra auditoría. Reutilizar exactamente ese contenido para una segunda intención indistinguible devuelve la primera; **esta es una limitación conservadora**, pendiente de clave explícita HTTP persistente. No se presenta como protocolo general de idempotencia por clave.
- Recepción completa: todos los detalles una vez, cantidades exactas y condición válida. La cantidad, condición, receptor, sucursal y fecha quedan en detalle/estado y auditoría persistente de la misma transacción; defectuosas no elevan stock vendible. Reenvío idéntico con evidencia persistida devuelve confirmación sin otro movimiento. Sin evidencia suficiente del reenvío se devuelve 409 y no se recibe de nuevo.
- **Parcial, omisión de renglones o mezcla repetida de un detalle:** bloqueo 409 `PARTIAL_RECEIPT_REQUIRES_MIGRATION` o 400 por detalle repetido, antes de mutar. No se declara el total recibido ni se liquida por el total solicitado. Custodia mixta/parcial completa necesita estructura mínima.
- **Reembolso e inmediato:** autorización primero (403 si falta permiso/sucursal/tenant), luego 409 `REFUND_EVIDENCE_REQUIRED`. No se actualiza a COMPLETADA, no se inventa transferencia, no se mueve caja ni stock por un presencial con reintegro inmediato bloqueado. Una referencia sola no acredita el egreso.
- Cálculo: descuento global se distribuye una vez sobre los subtotales; si los detalles ya contienen ese descuento, no se descuenta dos veces. Cabecera/detalles ambiguos: 409 de conciliación. Bs 100 / 3 produce 33,33 + 33,33 + 33,34 por derecho acumulado. El envío no eleva el tope de prendas. Se comprueba también lo comprometido por devoluciones anteriores.

005 permanece con sus tipos/restricciones actuales (código VARCHAR(50) nullable; timestamps sin zona, sin unicidad de código). No se afirma VARCHAR(30)/NOT NULL/UNIQUE/timestamptz. Corregir eso y su DOWN destructivo requiere conocer otros entornos y una migración compatible; no se modificó su checksum.

## 3. Pruebas ejecutadas

Todas las integraciones usan **LocalPostgres descartable**, configurado antes de crear/importar la aplicación para ejecutarla. Ninguna prueba funcional se dirigió a la base real.

| Comando `python -m unittest discover -s tests -p … -v` | Resultado | Cobertura relevante |
| --- | --- | --- |
| `test_critical_integrity.py` | 43/43 | 5 unitarias de dinero y 38 integraciones dirigidas: tenant, cliente duplicado, rollback de auditoría, recepción/reembolso bloqueados, reenvío en proceso nuevo, concurrencia de stock/caja/pagos/recepciones/importación/variantes. |
| `test_iter1.py` | 29/29 | P1/SaaS/RBAC/alcances y contrato de checkout. |
| `test_pwa_iter2.py` | 8/8 | Recibos/aislamiento y optimizaciones: ping sin SQL y carrito caliente con máximo previo de 4 consultas. |
| `test_sync_transactional.py` | 16/16 | Reenvío, última existencia, fallos dentro de transacción, respuesta HTTP perdida, procesos concurrentes y crash/reinicio PostgreSQL con recibo durable. No se cambió el mecanismo sync. |
| `test_devoluciones_iter3.py` | 8/8 | Solicitud, pertenencia, saldo, recepción completa/defectuosa; reembolso ahora verifica bloqueo y conservación del estado/stock. DOWN/UP solo aislado. |

**Total: 104 casos (5 unitarios y 99 de integración aislada).** Transcripciones en la carpeta de evidencia. La prueba DOWN/UP de 005 no certifica conservación de historia: su riesgo destructivo sigue pendiente. La prueba de respuesta perdida de devolución descarta la salida después de confirmar, termina ese proceso y reenvía desde otro; no es una prueba de caída física de red ni de banco. Reinicio de PostgreSQL se prueba en la suite transaccional existente.

En la primera ejecución se detectaron: dos expectativas antiguas que afirmaban reembolso ficticio, fixture sin recibos persistentes, secuencias del fixture sin avanzar y una regresión de consultas por bloquear la lectura de perfil. Se corrigieron fixtures/expectativas y la ruta de lectura; no se debilitó el límite de rendimiento ni los controles. No se ejecutaron Angular/Flutter, pasarelas reales, pruebas de carga ni migración nueva de propuestas. Los casos habilitados de parcial/reembolso quedan pendientes y **no se reportan como aprobados**.

## 4. Pendiente por autorización

SQL, precondiciones, verificación y límites de reversión: [CORRECCIONES_CRITICAS_SQL_PROPUESTO.md](CORRECCIONES_CRITICAS_SQL_PROPUESTO.md). Incluye restricciones mínimas de posición/caja, mapas sin destinos inferidos y estructura acotada para clave explícita, recepción parcial/mixta y evidencia de un reembolso completo. **Nada de ello se aplicó ni habilita ahora la acción bloqueada.**

Se necesita aprobar reglas/saldos y correspondencias históricas, obtener historial de 005 de otros entornos, completar evidencia del pedido 8882 y autorizar por separado cualquier destino real. Antes de desplegar escritores, coordinar la retirada de instancias antiguas/consumidores externos. No se ejecutaron reparaciones, respaldos/restauraciones ni deploy. No se verificó ni se garantiza atomicidad distribuida con bancos: capturas externas de PayPal/tarjeta y su conciliación requieren evidencia del proveedor y trabajo específico; esta tarea protege los efectos locales en PostgreSQL.

## 5. Lo que NO se tocó

No normalización general, renombrados ni eliminación de entidades/columnas. Sin cambios en Angular, `mobile/`, UX, cola offline, `t_sync_operacion` o su mecanismo; sin cambios de RBAC general, SaaS, proveedores compartidos, estados/activo de catálogos, notificaciones, imágenes, colección/temporada, IA/RA o CU41W. Migraciones 001/003/004/005 y `sync_routes.py` se conservaron byte por byte respecto del registro de esta intervención: [hashes verificados](evidencias/correcciones_criticas_2026-11-01/archivos_protegidos_verificados.json). El diff global contiene trabajo anterior; no se atribuye todo a esta tarea ni se revierten cambios ajenos.

## 6. Estado por hallazgo

| Hallazgo | Estado de esta entrega |
| --- | --- |
| Nuevas mezclas por importación/generación y operaciones corregidas | **RESUELTO en código y pruebas aisladas**; protección declarativa/despliegue pendientes. |
| 513 referencias de catálogo históricas | **PARCIAL**: identificadas y mapeadas como candidatas; no reparadas. |
| Último stock, doble posición/recepción/cobro/apertura en caminos corregidos | **RESUELTO en código y pruebas aisladas**; SQL externo/instancias antiguas requieren transición. |
| 5.691 saldos históricos y definición comercial final | **PARCIAL**: origen técnico rastreado y prevención; conciliación/aprobación pendiente. |
| Cliente por LIMIT 1 | **RESUELTO en autorización de caminos corregidos**; historial se consulta por cuenta real. |
| 3 cuentas / 16 perfiles adicionales | **PARCIAL**: mapa completo; nuevas operaciones ambiguas bloqueadas; sin consolidación. |
| Pedido 8882 pagado sin venta | **BLOQUEADO para reparación** por falta de evidencia; prevención de nueva confirmación parcial implementada. |
| SKU histórico duplicado / variante incompleta | **PARCIAL**: prevención y mapa; semántica/destinos pendientes. |
| Duplicación/sobredevolución, dinero exacto y auditoría | **RESUELTO en caminos habilitados y pruebas aisladas**, con límite conservador de intención idéntica documentado. |
| Recepción parcial/mixta y liquidación de reembolso | **BLOQUEADO de forma segura** hasta estructura/evidencia y aprobación; no funcionalidad completada. |
| Migración 005 real | **BLOQUEADA para aplicación**; ausencia comprobada solo en destino configurado, otros entornos sin verificar. |
| Multirrol | **CONSERVADO**: no requiere corrección ni sustitución. |
