# AuroraStore: propuesta de normalización gradual

Fecha: 2026-11-01. Codex. Estado: **análisis y propuesta para validación; no es una migración aplicada ni una certificación funcional de devoluciones**.

Se contrastó la auditoría adjunta «FashionStore — esquema comercio» con el código actual, las migraciones y PostgreSQL real mediante conexiones con `transaction_read_only=on`. No se importó/arrancó la aplicación, no se hicieron escrituras reales, no se corrigieron datos y no se modificaron Angular, `mobile/` ni CU41W. La autorización anterior de 003/004 no se extiende a 005 o a esta propuesta.

## 1. Recomendación

Establecer una fuente de verdad para cada dato, corregir primero las inconsistencias verificadas y añadir restricciones compatibles con P1. Conservar instantáneas históricas y redundancias técnicas justificadas. Una reducción de columnas por sí sola no asegura normalización ni integridad.

El orden recomendado es: **conciliación de inventario y catálogos → integridad de devoluciones/reembolsos → restricciones multitenant y unicidad → simplificación de estados/roles/notificaciones**. Las fases se pueden preparar conjuntamente en un entorno aislado, pero las reparaciones de datos reales requieren correspondencias aprobadas, no decisiones automáticas por defecto.

## 2. Qué está comprobado

La consulta actual confirma **62 tablas físicas, 514 columnas, 352 columnas nullable y 112 FK**. Se conservaron restricciones, índices, triggers, columnas, conteos y SQL de los diagnósticos agregados en [la evidencia](evidencias/NORMALIZACION_DIAGNOSTICO_2026-11-01.json). No se exportaron nombres de clientes, credenciales, comprobantes ni filas comerciales individuales. Las lecturas no constituyen un snapshot único de toda la actividad: una aplicación activa puede modificar cantidades entre consultas.

| Comprobación | Resultado al consultar | Implicación |
| --- | --- | --- |
| Inventario | 6.019 filas | El volumen permite una conciliación dirigida, sin una reconstrucción del sistema |
| Disponible distinto de `actual - reservado` | **5.691 filas**: 5.426 superiores y 265 inferiores | Confirmar definición de stock y sus escritores antes de recalcular o convertir a columna generada |
| Identidad/stock nulos, negativos o reservado mayor que actual | 0 casos en las comprobaciones realizadas | Hay margen para endurecer estas reglas tras validar todos los escritores |
| Duplicados inventario por sucursal/variante | 0 grupos; ninguna temporada asignada | Esa pareja es una candidata razonable a clave de stock, pendiente de confirmar el negocio |
| Variantes con talla/color de otra empresa conocida | **513 variantes**; ambas relaciones están afectadas | Preparar mapa de equivalencias por tenant, preservando `id_variante` y referencias históricas |
| Variante con producto/talla/color incompleto | 1 fila | Definir si talla/color son obligatorios o existe una variante sin esos atributos |
| SKU repetido dentro de una misma empresa | 1 grupo | Resolver significado comercial antes de añadir unicidad |
| Clientes repetidos por usuario | **3 usuarios**, 16 perfiles adicionales respecto a uno por cuenta | El `LIMIT 1` actual puede escoger un perfil diferente del referenciado por una compra |
| Usuario con varios roles | 1 usuario | El puente multirrol ya tiene uso real; no eliminarlo |
| Rol principal no contenido en el puente | 0 casos entre los principales no nulos; 1 usuario sin principal | Formalizar el principal como preferencia de presentación/compatibilidad |
| Pedido marcado `PAGADO` sin `id_venta` | **1 pedido** | Conciliar el respaldo del pago; no inventar venta, cobro ni cambio de estado |
| Reservas con pago declarado | 0 | No se justifica ampliar ahora el modelo para cobros de reservas sin definir ese flujo |
| Pago sin venta/método/importe o con importe no positivo | 0 en los 106 pagos | Endurecer el flujo actual sin suponer que esos nulos ya existen |
| Caja/sesión incoherente, dos sesiones abiertas por caja | 0 casos/grupos | Mantener los datos y añadir protección de concurrencia y coherencia |
| Asignación usuario/sucursal cruzada entre empresas conocidas | 0 | Ya existe un trigger de asignaciones; conservarlo y probarlo |
| Productos/ventas/sucursales sin empresa; venta/sucursal o detalle/producto cruzados | 0 en las comprobaciones indicadas | Refuerzos declarativos son posibles tras revisar canales y cuentas globales |
| `estado`/`activo` contradictorios en producto, talla, color y categoría | 0 | La unificación tiene menor urgencia que inventario y finanzas |
| `notificacion` y `t_notificacion` | 0 filas en ambas; sin vistas dependientes detectadas de la primera | Consolidación de bajo volumen, pero revisar también consumidores externos y permisos |
| Proveedor usado por lotes de varias empresas | 1 proveedor | Cambiar proveedor a propiedad exclusiva de un tenant rompería una relación existente |
| SaaS | 2 planes, 2 suscripciones; sin solapamientos detectados | Ya hay CHECK y trigger que serializa por empresa para impedir solapamientos |
| RLS | Sin tablas habilitadas ni políticas | RLS sería una defensa adicional; su ausencia no demuestra por sí sola un bypass de las autorizaciones del backend |
| Devoluciones en base real | 0 cabeceras y 0 detalles; estructura P1 | **005 no está aplicada**. El ledger contiene 003/004; estas no se deben reescribir |

La existencia de objetos SaaS de 001 sin su registro actual en `schema_migrations` debe reconciliarse con su historial/checksum por separado. No ejecutar 001 de nuevo basándose solo en el ledger. Tampoco se infiere la ausencia de toda optimización de índices a partir de su registro.

## 3. Modelo propuesto por dominio

### A. Inventario y variantes: prioridad crítica

- Confirmar que `t_inventario` representa existencias vendibles y que `stock_disponible = stock_actual - stock_reservado`. Si hay otra retención válida, identificar su origen y persistencia antes de cambiar la fórmula.
- Hacer obligatorios sucursal, variante y cantidades; impedir cantidades negativas y reservas superiores a las existencias según la regla aprobada. Añadir unicidad por `(id_sucursal, id_variante)` si se confirma que no hay stock separado por lote/temporada/condición. No introducir un desglose por lote implícitamente.
- Elegir un único responsable del cálculo de disponible. Como transición compatible con funciones P1 que hoy escriben los tres campos, propongo recalcularlo en un trigger único y validar el CHECK tras conciliar las discrepancias. Una columna generada es una alternativa posterior: primero habría que retirar sus escrituras de POS, reservas, compras, importación y devoluciones.
- No hacer `UPDATE disponible=actual-reservado` indiscriminado: podría aumentar o reducir disponibilidad y no demuestra cuál de los saldos es correcto. Los 224 movimientos existentes tampoco bastan por sí solos para certificar todos los saldos iniciales y las 6.019 posiciones.
- Reparar las 513 referencias con correspondencias aprobadas de talla/color de la empresa del producto, creando equivalentes locales cuando corresponda. Preservar IDs de variante y enlaces de ventas/reservas. No trasladar el catálogo ajeno de empresa ni fusionar variantes automáticamente.
- Definir unicidad de combinación de variante y de SKU por su alcance real. Un SKU visible puede tener alias históricos; cambiarlo exige revisar etiquetas/referencias. La variante incompleta requiere una decisión de negocio, no un relleno con IDs arbitrarios.
- Dar al movimiento un origen verificable de venta, reserva, recepción de compra o devolución, además del motivo descriptivo. Conservar las instantáneas de cantidad/saldo anterior/nuevo.

### B. Pertenencia a tenant y caja: prioridad crítica/alta

La empresa canónica de una sucursal es `t_sucursal.id_empresa`. Cuando una cabecera ya conserva sucursal y empresa, propongo mantener esos campos durante la compatibilidad y forzar la pareja mediante FK compuesta. En `t_caja_sesion`, comprobar conjuntamente caja/sucursal/empresa contra `t_caja`; el cajero debe seguir sujeto a autorización de servidor.

Crear un índice único parcial para una sesión `ABIERTA` por caja. Si también se exige un único turno abierto por cajero/sucursal, aprobar esa regla por separado: es distinta de la exclusividad de caja.

Para variantes e inventario, una FK independiente a sucursal y otra a producto no prueban coincidencia de empresa. Hay dos diseños válidos: validar la relación mediante trigger transaccional sin duplicar tenant, o materializar `id_empresa` derivado por servidor y proteger todas sus relaciones con FK compuestas. Propongo el segundo solo donde aporte una necesidad comprobada de consulta/RLS; no añadir empresa a todas las tablas por costumbre.

RLS queda como fase posterior, con rol de API adecuado, evaluación de propietarios/BYPASSRLS y contexto fijado con `SET LOCAL` dentro de cada transacción del pool. Debe contemplar clientes que compran en tiendas públicas y la administración de plataforma; no habilitar una política genérica que bloquee P1. Las FK y los permisos de la API siguen siendo necesarios. [Documentación PostgreSQL: restricciones](https://www.postgresql.org/docs/17/ddl-constraints.html), [RLS](https://www.postgresql.org/docs/17/ddl-rowsecurity.html).

### C. Devolución, recepción e inventario físico: prioridad crítica

Reutilizar `t_devolucion` y `t_detalle_devolucion`. Propongo separar solicitud de recepción física:

- `t_devolucion`: venta de origen, solicitante, motivo y estado general. La empresa se deriva de la venta verificada; la sucursal de recepción es un dato separado cuando puede diferir de la venta.
- `t_detalle_devolucion`: renglón vendido y cantidad solicitada/aprobada, con una línea canónica por detalle de venta en la solicitud. El detalle debe pertenecer a la misma venta de la cabecera; dos FK independientes no lo garantizan.
- `t_recepcion_devolucion` y su detalle: cada recepción física, responsable, sucursal, fecha, cantidad y condición. Permiten recibir una misma solicitud en varias ocasiones y separar unidades revendibles de defectuosas en un mismo renglón.
- Inventario comercial aumenta solo por lo revendible efectivamente recibido. Las unidades defectuosas permanecen trazadas como recibidas no vendibles/merma, con su destino y cantidad; omitir el incremento de stock no basta como registro de custodia física.

La suma solicitada activa no debe exceder la vendida; la recibida no debe exceder la aprobada y el reembolso debe corresponder al derecho aprobado/recibido. Las excepciones de reembolso sin recepción requieren regla y autorización explícitas. Para límites acumulados entre filas se necesitan bloqueos y lógica transaccional, no un CHECK con una suma de otra tabla.

### D. Reembolsos y pagos: prioridad crítica

Crear `t_reembolso` como hecho económico vinculado a la devolución y al pago/venta de origen. Campos conceptuales: importe, moneda, método referenciado a catálogo, estado, referencia/comprobante, responsable, fecha y clave idempotente. Admitir varios reintegros parciales si el flujo lo requiere; la cabecera de devolución muestra su resumen, no mantiene un total liquidado editable e independiente.

Para efectivo, registrar una salida de caja vinculada al reembolso y a una sesión autorizada. Si no existe un movimiento financiero equivalente, introducir un registro específico de movimiento de caja y reflejarlo en arqueos, denominaciones y reportes. La recepción de prendas y la salida de dinero son eventos diferentes.

Para transferencia/tarjeta, registrar evidencia y confirmación manual autorizada o una respuesta auténtica de un proveedor configurado. Una cadena de referencia ingresada no prueba que un banco ejecutó el reintegro. No simular pasarelas ni convertir simplemente un UPDATE de cabecera en un movimiento financiero.

Usar `Decimal`/`NUMERIC` y distribuir descuentos globales y residuos de centavos de forma determinista. Ejemplo de validación: venta de Bs 300 con descuento de cabecera de Bs 30 tiene Bs 270 netos, no Bs 300 devolvibles; devolver tres unidades de un subtotal de Bs 100 exige conservar el centavo residual de `33,33 × 3`. El tope acumulado nunca debe exceder el importe neto reembolsable según la política aprobada. [Tipos numéricos exactos en PostgreSQL](https://www.postgresql.org/docs/17/datatype-numeric.html).

Mantener `t_pago` para cobros y no mezclar reintegros como cobros negativos sin adaptar sus consumidores. Los 106 pagos existentes están vinculados a ventas; el pedido `PAGADO` sin venta necesita revisión de evidencia. Si se decide cobrar pedidos/reservas antes de emitir venta, diseñar una relación explícita de aplicación del pago, no una pareja genérica `tipo/id` sin FK ni una copia del monto en varias cabeceras.

Las operaciones de devolución seguirían exclusivamente online. Reutilizar el patrón de idempotencia transaccional para solicitudes, recepciones y reembolsos HTTP, con claves persistentes por acción; no incorporarlas a la cola offline ni cambiar la PK/retención de `t_sync_operacion`.

### E. Cliente y RBAC: prioridad alta

Propongo **cliente global por cuenta**, como el flujo actual de compras públicas, y movimientos comerciales siempre acotados por su venta/pedido/empresa. No añadir empresa al perfil de cliente para duplicarlo por tienda.

Antes de `UNIQUE(t_cliente.id_usuario)`, conciliar los tres usuarios con múltiples perfiles: escoger perfil canónico con validación, remapear todas las FK y conservar un mapa de IDs antiguos. No borrar compras ni elegir el menor ID como regla automática. En autorización de compras, comprobar la pertenencia mediante la cuenta de la venta en lugar de comparar contra un perfil obtenido con `LIMIT 1`.

Mantener `t_usuario_rol` como fuente canónica de membresía: ya hay un usuario multirrol. El rol principal es una preferencia distinta de tener varios roles; podría trasladarse a una marca de principal en el puente, con unicidad parcial, mientras `t_usuario.id_rol` queda como compatibilidad temporal. Los permisos efectivos continúan derivándose de RBAC del servidor, incluidos permisos directos activos. `t_empleado` puede describir relación laboral/sucursal principal sin sustituir el alcance de `t_usuario_sucursal`.

### F. Catálogos, notificaciones y lotes: segunda fase

- Conservar un solo booleano de activación en catálogos tras inventariar lectores/escritores de `estado` y `activo`; usar alias o transición compatible. Conservar los estados de ciclo de vida de ventas, caja, pedido y devolución, que tienen otra semántica.
- Las cuatro tablas de catálogo ya tienen índices únicos de nombre normalizado por tenant. No duplicarlos. Revisar el significado del nombre único de producto: distintos productos pueden tener nombre igual si el negocio identifica por código/SKU.
- Establecer `t_notificacion` como tabla canónica, porque es la utilizada por los repositorios actuales. Ambas tablas están vacías y no se encontraron vistas dependientes de `notificacion`, pero revisar código externo/permisos antes de sustituir el nombre legado por una vista de compatibilidad o retirarlo mediante migración específica.
- Proveedores: conservar la identidad compartida; ya hay uno usado por varias empresas. Si cada tienda tiene condiciones y visibilidad propias, usar una asociación empresa-proveedor y dejar condiciones/costos privados en su alcance. No asignar el proveedor compartido arbitrariamente a una tienda.
- Promociones: definir alcance global o privado explícito antes de añadir tenant; validar que las promociones privadas solo incluyan productos de su empresa. Las tres promociones existentes requieren clasificación, no un tenant por defecto.
- Temporada/colección: elegir relaciones canónicas y conservar etiquetas históricas cuando corresponda. Ambas tablas de catálogo y sus asociaciones están vacías actualmente; se puede preparar el cambio a partir de los textos existentes con un mapa aprobado, sin descartar esos textos aún.
- Lotes: conservar `t_lote`, órdenes y detalles de compra. Si se necesita trazabilidad por variante/lote, añadir un detalle de recepción/lote relacionado con lo existente y sus movimientos. No reconstruir los 11 lotes históricos a partir de totales ambiguos.
- Imágenes: mantener una galería y, cuando sea la regla, índice parcial de una principal por producto. No se encontraron grupos con varias principales. `t_producto.imagen_url` puede mantenerse como caché compatible, con un escritor definido.

### G. Mantener el alcance SaaS y los históricos

Los límites de planes 2/10, las restricciones de `t_plan` y el historial de `t_suscripcion` ya existen. El trigger actual bloquea por empresa para prevenir solapamientos y la consulta no encontró períodos cruzados. No crearía ahora otra tabla genérica de capacidades ni asignaría planes/vigencias nuevas.

Conservar instantáneas fiscales/de precio/costo/descuento de las operaciones y de denominaciones en pagos. Evitan que un cambio del catálogo reescriba el significado de una venta pasada. Los recibos JSON inmutables de idempotencia y las tablas técnicas de migraciones/control también tienen una función válida; no deben eliminarse como supuestos duplicados.

La revisión de códigos hasheados/expiración y de retención/redacción de bitácoras/dispositivos corresponde a una tarea de seguridad separada. No ampliar IA, RA, fidelización, mobile ni CU41W para normalizar el dominio actual.

## 4. Ajustes de código y documentación antes de aprobar 005

| Hallazgo estático confirmado | Ajuste propuesto |
| --- | --- |
| El documento anuncia código VARCHAR(30), UNIQUE/NOT NULL y timestamps con zona; 005 crea VARCHAR(50) nullable sin unicidad y TIMESTAMP sin zona | Unificar especificación, SQL y DTO; aplicar la integridad elegida tras validar datos. La zona de datos históricos debe conocerse antes de convertirlos |
| El documento usa ONLINE/PRESENCIAL, `estado`, `devoluciones.aprobar` y movimiento ENTRADA_DEVOLUCION; código usa SOLICITUD_CLIENTE/PRESENCIAL_MOSTRADOR, `estado_item`, `devoluciones.aprobar_rechazar` y ENTRADA | Publicar un único contrato, preservando compatibilidad cuando existan consumidores. El permiso reembolsar de CAJERO declarado en el documento no se siembra en 005 |
| El servicio usa alcance TENANT donde `tenant_guard` retorna EMPRESA | Corregir el contrato de alcance y probar administrador de tienda, cliente, plataforma y cajero |
| La solicitud del cliente pasa `id_empresa` recibido en lugar de derivarlo de la compra verificada | Resolver propiedad de la venta por usuario, derivar tenant y rechazar contexto incompatible |
| La elegibilidad busca `response_json->>'id_venta'`; el recibo sync actual guarda `data.id_venta` y se silencian errores de consulta | Corregir enlace/consulta y fallar sin omitir la verificación cuando sea necesaria. A medio plazo, relación tipada de origen/recibo; la ausencia de un recibo sync no invalida por sí sola una venta P1 directa |
| Un mismo detalle de venta puede repetirse en el body y cada aparición se compara contra el mismo saldo, sin acumular lo ya procesado | Rechazar o agregar duplicados antes de validar; añadir unicidad de línea y comprobar límites acumulados bajo bloqueo de la venta |
| Se recibe una cantidad menor a la solicitada, pero no se persiste la cantidad recibida y la cabecera pasa a pendiente de reembolso por su monto original | Persistir recepción por renglón/condición; impedir liquidar el monto total solicitado por una recepción parcial |
| Los cálculos usan float y subtotal de detalle; el descuento de cabecera no se prorratea en esos bucles | Usar cálculo exacto y tope neto; contrastar semántica con POS y ecommerce. Hay cuatro ventas pagadas/completadas con descuento de cabecera que requieren esta cobertura |
| `registrar_reembolso_financiero` y el inmediato solo actualizan/inserten cabecera y referencias | Persistir reembolso y salida financiera reales con la operación idempotente; no afirmar pago externo automático |
| Auditoría se registra en servicios después del COMMIT del repositorio | Usar la transacción compartida del proyecto para mutación, movimientos, reembolso y auditoría; una respuesta perdida/fallo posterior no debe facilitar un duplicado |
| Recepción/reembolso validan tenant, pero el alcance de sucursal de la devolución no se aplica de forma uniforme en cada acción | Verificar venta/devolución, sucursal origen/destino y permisos de servidor en todos los caminos, incluidas cuentas de alcance empresa/plataforma |
| 005 DOWN elimina columnas y todos los permisos `devoluciones.%`, incluso preexistentes | No calificarlo como reversión sin pérdida. Registrar propiedad de semillas/cambios, bloquear DOWN con datos de devoluciones y no eliminar campos o permisos ajenos |

No se editó 005 ni se cambió su checksum en este análisis. Antes de reescribirla se debe confirmar que no se aplicó en otros entornos. Si ya está aplicada en alguno, la corrección debe ser una nueva migración compatible.

El test actual de DOWN/UP comprueba ausencia y recreación de permisos; no demuestra conservación de todas las columnas, importes o evidencia. Las ocho pruebas declaradas en el documento no se ejecutaron de nuevo en esta tarea y no cubren por sí solas los escenarios señalados.

## 5. Despliegue propuesto y pruebas que faltan

1. Validar las reglas indicadas: fórmula de stock, catálogos privados por empresa, cliente global, política de devolución/recepción parcial y comprobación del reintegro. Congelar una correspondencia de reparación de datos con trazabilidad de IDs.
2. Preparar migraciones aditivas por dominio y adaptar escritores/lectores en un entorno aislado. Mantener APIs P1 y estados de compatibilidad; cualquier cambio público debe documentarse para Antigravity.
3. Añadir CHECK/FK inicialmente con `NOT VALID` cuando proceda, de modo que las escrituras nuevas se controlen, y validarlas tras la conciliación. Esa opción no sustituye la limpieza ni permite instalar UNIQUE sobre duplicados. Una FK nullable tampoco obliga a que el vínculo esté informado; añadir obligatoriedad donde el flujo la exija. [ALTER TABLE en PostgreSQL 17](https://www.postgresql.org/docs/17/sql-altertable.html).
4. Probar claves y casos concurrentes: último stock, combinación sucursal/variante ausente, compra/reserva/venta/recepción simultáneas, dos devoluciones del mismo saldo, dos sesiones de la misma caja, body duplicado, recepción parcial/mixta, repetición de reembolso y pérdida de HTTP después del commit.
5. Probar dinero exacto y descuentos globales/residuales; rollback de stock/reembolso/auditoría; pertenencia a empresa/sucursal; cliente con perfiles antiguos; rol principal y varios roles; recibos sync; historial conservado al revertir.
6. Ensayar avance y reversión con registros, no solo con tablas vacías. La reversión debe preservar el mapa de reparación y bloquear operaciones destructivas cuando haya nueva historia.
7. Presentar SQL y resultados para autorización específica del destino real. Programar transición de escritores; si se usa creación concurrente de índices, el ejecutor transaccional actual necesita un procedimiento separado para esa operación. No aplicar esta propuesta automáticamente ni ejecutar 001/005 por el mero estado del ledger.

No se han corrido pruebas unitarias/integración nuevas ni compilaciones en este análisis: las comprobaciones ejecutadas fueron lectura de código, metadatos y diagnósticos SELECT agregados. La evidencia permite priorizar; no certifica que todos los datos sean correctos ni sustituye la conciliación.
