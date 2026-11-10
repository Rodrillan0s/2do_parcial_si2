# Idempotencia transaccional — auditoría y endurecimiento

Fecha: 2026-10-31. Agente: Codex. Rama actual; sin publicación ni cambios en `mobile/` o CU41W. Tras la auditoría inicial, el usuario autorizó el ajuste mínimo de la cola Angular; sus resultados se documentan por separado.

## Estado del despliegue real

**Actualización tras autorización del usuario:** 003 y 004 se aplicaron y verificaron el 2026-10-31; la reaplicación devuelve «Sin cambios». El backend local se restableció tras la transición. Ver [acta de aplicación y limpieza](SYNC_MIGRACION_APLICADA_2026-10-31.md) y [evidencia posterior](evidencias/SYNC_POST_MIGRATION_2026-10-31.json). El párrafo siguiente describe el estado inicial, previo a esta aplicación.

Se consultó PostgreSQL configurado exclusivamente mediante `backend/check_sync_persistence.py`, con `transaction_read_only=on`, sin importar ni arrancar FastAPI. `to_regclass` devolvió NULL para `comercio.t_sync_operacion` y `comercio.schema_migrations`; tampoco existen columnas, restricciones ni índices de la primera tabla. **La migración 003 no está instalada en este destino. La garantía persistente todavía no está activa allí.** No se ejecutó DDL ni escritura comercial real.

La presencia del archivo SQL en Git y los anteriores resultados de pruebas no demuestran que esté aplicado en producción. Las afirmaciones históricas de «respaldo en memoria» no equivalen a idempotencia persistente y quedan sustituidas por este informe y el contrato actualizado. La [evidencia de solo lectura](evidencias/SYNC_AUDIT_2026-10-31.json) confirma PostgreSQL 17.11 con `fsync`, `full_page_writes` y `synchronous_commit` habilitados.

Las funciones reales se leyeron y conservaron como fixtures de pruebas, sustituyendo únicamente el calificador de esquema. SHA-256 del texto original devuelto por `pg_get_functiondef`:

| Función | SHA-256 |
| --- | --- |
| `fn_registrar_venta_pos` | `bcc907172bfce97f9d6827941f91f7fd0071112a995d588ed758a027792c7fa5` |
| `fn_reservar_stock` | `cc21fefffcd58ac9cd04355d1dbceb144ff74f14a203f034e90e670b9240371f` |

Ambas bloquean inventario con `FOR UPDATE` y escriben `t_movimiento_inventario`. El código anterior confirmaba venta, pago y recibo sync en momentos distintos; además, comprobar y luego insertar una clave no serializaba ejecutores concurrentes. La compensación posterior del pago podía fallar y no sustituía una transacción.

## Garantía implementada

Alcance: `POST /api/sync/lote` y su alias `/api/sync/operations`, para las operaciones existentes de carrito, reservas y ventas de contado. Los endpoints P1 directos conservan su contrato; no adquieren automáticamente claves de idempotencia.

1. Se valida el contexto de empresa en servidor y se comprueban vigencia, permisos POS y alcance de sucursal antes de devolver incluso un recibo previo. La clave conserva el alcance contractual `(id_usuario, id_empresa, operation_id)`; no se debe reasignar una operación pendiente a otro usuario o empresa.
2. Una conexión y transacción comparten todas las llamadas de repositorio. Los commits internos se difieren hasta el límite exterior. Un error interno marca la transacción y no libera anticipadamente los bloqueos.
3. `pg_advisory_xact_lock(hashtextextended(scope, 0))` serializa la clave aun cuando todavía no haya fila. Funciona entre procesos/servidores que comparten PostgreSQL; una colisión de hash solo añade espera, no mezcla recibos, porque se consulta la clave completa. Esperas mayores de cinco segundos fallan sin confirmación y conservan la operación para reintento.
4. Se exige la tabla de recibos, `request_hash` y el control de transición de la migración 004. Su ausencia o una avería devuelve `failed_retryable`, `http_status: 503`, `PERSISTENT_IDEMPOTENCY_UNAVAILABLE`, `confirmation_verified: false`. Se eliminó el registro en memoria y las excepciones de persistencia silenciadas.
5. Se bloquean la sesión de caja y las filas de inventario del tenant en orden estable. Se rechazan variantes repetidas: el cliente debe combinar sus cantidades. Distintas claves compiten por el stock real sin sobreventa.
6. Venta, detalle, inventario, movimientos, pago, denominaciones y recibo `synced` se confirman en **un único COMMIT**, con `synchronous_commit=on`. La reserva comparte ese límite con sus detalles, stock reservado, movimientos y auditoría. No hay compensación posterior para sustituir un rollback.
7. Un savepoint permite revertir todos los efectos de una operación rechazada y persistir su incidencia sin soltar el bloqueo de su clave. Un fallo al escribir el recibo revierte también los efectos comerciales.
8. La respuesta `synced` solo sale después del commit. Si se pierde la respuesta o el proceso muere tras confirmar, reenviar la misma clave y contenido recupera el mismo resultado persistido. Si el commit es incierto, no se emite confirmación: se consulta mediante reenvío, sin crear una clave nueva.
9. La huella SHA-256 cubre JSON canónico de `kind`, `branch_id`, `entity_id` y `payload`; excluye timestamps y metadatos de transporte. Reutilizar una clave confirmada con otro contenido o cambiar su tipo devuelve `IDEMPOTENCY_KEY_REUSED`. Los conflictos sin efectos confirmados admiten resolución con la misma clave y tipo.

La persistencia supone un almacenamiento PostgreSQL correcto, WAL y `fsync` habilitados. No se promete recuperación ante pérdida física de discos ni se introduce trabajo de CU41W.

## Operaciones anteriores y conservación local

No se puede reconstruir una confirmación que solo estuvo en RAM. Ejecutar de nuevo una venta antigua desconocida podría duplicar una venta ya cobrada.

La migración 004 crea `t_sync_control.inicio_garantia` una sola vez. Una venta o reserva nueva sin recibo requiere `created_at` ISO con zona horaria, igual o posterior a esa frontera; las operaciones anteriores, sin fecha o con fecha inválida reciben `LEGACY_OPERATION_REQUIRES_REVIEW`, sin efectos nuevos. La fecha original debe conservarse; cambiarla para evitar la revisión incumple el contrato. Un reloj local atrasado puede requerir revisión manual. Este control conserva los casos ambiguos, no certifica retroactivamente ventas antiguas.

Un recibo existente sin huella permanece intacto y devuelve `LEGACY_RECEIPT_REQUIRES_REVIEW`. No se inventan huellas ni se reejecutan esos registros. La revisión debe contrastar venta, reserva, pagos, movimientos y evidencia de caja antes de decidir; no borrar operaciones ni fabricar confirmaciones.

No se eliminaron operaciones locales. El backend solo emite `synced` con confirmación durable. Para Antigravity y la futura implementación Flutter: antes de retirar una operación local, comprobar `status=synced`, `confirmation_verified=true`, la identidad de operación/usuario/empresa de `confirmation` y el resultado comercial; conservar el recibo en el historial local en una transacción. HTTP 200 del lote o un ping no confirman ninguna operación. Si falta el resultado individual, hay timeout, 5xx, conflicto o recibo antiguo, conservar el sobre original. Un parche de conflicto no debe transformarse en una venta nueva si se desconoce el resultado previo. No iniciar Flutter offline hasta cerrar la transición real y la conciliación pendiente.

La revisión inicial detectó purga/descarte sin recibo, historial truncable y éxito aparente en RAM. El usuario autorizó expresamente corregir solo la cola Angular. Ahora los pendientes, intentos y recibos se conservan entre sesiones; la retirada exige recibo válido y comparte transacción con su historial; las notas no retiran operaciones. Hay 40 pruebas nuevas aprobadas con IndexedDB emulado y compilación de producción correcta. Ver [resultados completos y límites](PWA_COLA_RETENCION_RESULTADOS.md). La suite general tiene un fallo previo de mock en un test de permisos. Las migraciones reales ya están aplicadas y verificadas; quedan la conciliación del legado y la verificación en navegadores reales, sin afirmar pruebas comerciales reales de extremo a extremo.

## Migraciones, permisos y puesta en servicio

003 conserva su contenido y checksum. 004 es una migración adicional explícita: añade huella nullable para distinguir legado, control de transición y FKs `ON DELETE RESTRICT` para impedir que borrar usuarios/empresas elimine recibos en cascada. No reasigna planes ni altera datos P1. La eliminación administrativa de identidades con recibos queda bloqueada hasta acordar conservación/archivo explícitos.

El usuario de API necesita SELECT/INSERT/UPDATE en `t_sync_operacion`, SELECT en `t_sync_control` y los permisos P1 existentes. No se añaden permisos RBAC ni se confía en `tenant_id` como autorización. El ejecutor de migraciones requiere los permisos DDL correspondientes. No debe concederse DELETE indiscriminado sobre recibos ni añadirse un TTL que permita volver a ejecutar claves pendientes.

Secuencia autorizada y completada el 2026-10-31; se conserva como referencia operativa. No volver a aplicar versiones distintas ni ejecutar DOWN sin autorización específica:

1. Suspender escrituras de sincronización en todos los workers antiguos y conservar las colas originales. Evitar convivencia con el backend que usa memoria durante la transición.
2. Revisar las migraciones renderizadas; la auditoría observó que 003 falta. No ejecutar ni modificar 001/002 como parte de este trabajo.
3. Aplicar 003 y después 004 con el ejecutor explícito:

```powershell
python -B backend/migrate.py up --version 003_iter2_sync_idempotency
python -B backend/migrate.py up --version 004_iter2_sync_transactional
# Aplicación autorizada y completada el 2026-10-31:
python -B backend/migrate.py up --version 003_iter2_sync_idempotency --apply
python -B backend/migrate.py up --version 004_iter2_sync_transactional --apply
python -B backend/check_sync_persistence.py
```

4. Verificar tabla, PK compuesta, huella, FKs, control de transición, configuración WAL y checksums. Desplegar todos los workers corregidos antes de reabrir sincronización. No arrancar la aplicación ni ejecutar ventas de prueba contra la base real para esta verificación.
5. Mantener en revisión las operaciones anteriores sin evidencia verificable y documentar su conciliación. No cambiar su UUID, usuario, tenant ni fecha para forzar su aceptación.

Reversión: detener escritores y ejecutar 004 DOWN únicamente en un destino autorizado. Conserva recibos y tablas comerciales, pero elimina huellas/control y vuelve a las FKs anteriores; deja la sincronización suspendida. No volver a habilitar el fallback en memoria. **No ejecutar 003 DOWN en una base con recibos reales**, porque elimina la tabla completa. Una nueva aplicación de 004 tras revertir conserva los recibos como legado para revisión.

## Validación reproducible

Las pruebas nuevas usan PostgreSQL local descartable, `fsync=on`, funciones reales capturadas y tablas de contrato con datos ficticios. No es un clon completo del esquema real: no certifica todos sus triggers, RLS o extensiones. Son pruebas de integración aislada, no unitarias ni escrituras comerciales en producción.

```powershell
python -B -m unittest discover -s tests -p test_sync_transactional.py -v
python -B -m unittest discover -s tests -p test_pwa_iter2.py -v
python -B -m unittest discover -s tests -p test_iter1.py -v
```

Resultado: 15 pruebas de la suite transaccional aprobadas en 47.947 s y una regresión adicional de identidad de operación del carrito aprobada individualmente en 7.036 s. Cubren ausencia de tabla/columna, ocho solicitudes simultáneas por clave para venta y reserva, procesos separados con la misma clave, competencia por el último stock, fallo después del pago, fallo SQL al persistir recibo, muerte abrupta del proceso antes del commit y después del commit sin respuesta HTTP, reenvío desde un proceso nuevo, claves reutilizadas, aislamiento, variantes repetidas, legado, reversión con recibos, CLI con checksum/reaplicación y recuperación WAL tras parada inmediata/reinicio del PostgreSQL aislado. La regresión adicional comprueba que actualizar un ítem creado localmente no cambia el tipo/huella de su recibo al reutilizar la lógica de agregar.

Las ocho pruebas PWA existentes verifican también ping con cero SQL, carrito con como máximo cuatro consultas sin N+1 y caché de catálogo sin fuga entre tenants. Las 29 pruebas Iteración 1 pasaron, incluido rollback de auditoría y vigencia/RBAC.

La suite histórica `test_performance_iter1.py` se ejecutó: una prueba de índices pasó y cuatro fallaron antes de autenticar por `Config.SECRET_KEY=None`. Se reprodujeron esos mismos cuatro errores cargando en memoria `backend/app/core/postgres.py` de HEAD. Una exploración con secreto ficticio detectó además fixtures antiguos sin `codigo_producto`/`estado`; se revirtió esa modificación temporal. No se declara aprobado ese benchmark ni se inventan latencias; su mantenimiento queda pendiente fuera de esta corrección. No se cambió catálogo, índices, caché, pooling ni métricas para ocultar esos fallos.
