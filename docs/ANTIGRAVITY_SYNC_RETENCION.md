# Retención local antes de habilitar operaciones críticas

2026-10-31, revisión de Codex. El usuario autorizó la excepción «Autorizar la corrección mínima de la cola». Los cambios descritos fueron implementados y validados con 40 pruebas nuevas aprobadas; ver [resultados de retención](PWA_COLA_RETENCION_RESULTADOS.md). Posteriormente se autorizaron y aplicaron 003/004 en PostgreSQL; ver [acta de aplicación](SYNC_MIGRACION_APLICADA_2026-10-31.md). No se probaron ventas reales.

## Hallazgos iniciales corregidos

- `frontend/src/app/core/storage/indexed-db.service.ts`, `purgePrivateData` (línea 356): incluye `pending_operations` y `sync_attempts` en la purga al cerrar sesión/cambiar de cuenta/401. Conservar aislamiento no debe implicar perder operaciones sin recibo.
- `frontend/src/app/core/sync/sync-queue.service.ts`, procesamiento de resultados (líneas 536–550): retira operaciones por `status=synced` sin comprobar explícitamente `confirmation_verified`, identidad del recibo y resultado comercial. Guardar intento y borrar cola son escrituras separadas.
- Mismo archivo, `reconcileCashSaleIncidence` (líneas 760–807): una nota local mueve la operación a historial limitado a 50 elementos y la elimina de pendientes. Esa nota no prueba que la venta exista o no exista en servidor.
- Mismo archivo, `discardOperation` (líneas 816–833): puede borrar operaciones no confirmadas, incluidas reservas. Un timeout no demuestra que no se ejecutó.
- `IndexedDbService.put` (líneas 220–257): puede resolver sin persistencia durable ante error/cuota y quedarse solo con el fallback RAM. No aceptar una nueva venta/reserva crítica como guardada localmente en ese caso.

Las referencias de línea corresponden a la auditoría inicial. Los fallos se cubren ahora con pruebas unitarias/transaccionales emuladas. No se ejecutaron pruebas de navegador físico ni se afirma pérdida efectiva de datos del usuario.

## Cambio implementado, conservando diseño y contratos P1

1. Separar cachés descartables de operaciones/recibos críticos. Logout, 401 y cambio de tenant deben ocultar y bloquear el contexto anterior, manteniendo sus operaciones particionadas y accesibles solo tras reautenticación del mismo usuario/empresa. No enviarlas con otra cuenta.
2. Retirar pendientes únicamente tras un recibo individual `synced`, `confirmation_verified=true`, `confirmation.operation_id/id_usuario/id_empresa` concordantes y el ID comercial esperado. Persistir recibo e historial y retirar el pendiente en una transacción IndexedDB que confirme éxito; si falla, conservar para reenvío.
3. Una nota o descarte manual no equivale a confirmación remota. Mantener las ventas/reservas no verificadas como incidencias durables; no truncar su evidencia a 50 elementos ni purgarlas por cambio de sesión.
4. Hacer que la persistencia crítica falle explícitamente si IndexedDB no confirma la escritura. El fallback RAM puede servir para cachés, no para asegurar al usuario que se registró una venta o reserva pendiente.
5. Mantener UUID, usuario, empresa, payload y fecha original durante la incertidumbre de red. `LEGACY_OPERATION_REQUIRES_REVIEW`, `LEGACY_RECEIPT_REQUIRES_REVIEW` e `IDEMPOTENCY_KEY_REUSED` conservan la operación y su evidencia para revisión; no arreglarlos creando otro UUID/fecha.

## Verificaciones requeridas

Probar pérdida de respuesta tras commit y reenvío; respuesta parcial o sin confirmación; error de escritura/cuota IndexedDB; recarga durante confirmación local; logout/401/cambio de cuenta con ventas y reservas pendientes; restauración tras reautenticar la misma cuenta; nota de conciliación y descarte sin recibo. Comprobar que otra cuenta no puede leer, mostrar ni enviar operaciones retenidas. No probar contra ventas reales.

El backend, permisos y esquema pertenecen a Codex. Antigravity debe consumir el [contrato actualizado](PWA_CONTRATO_SYNC.md), los [resultados de la corrección](PWA_COLA_RETENCION_RESULTADOS.md) y el [informe transaccional](SYNC_IDEMPOTENCIA_TRANSACCIONAL.md) sin modificar esos controles. 003/004 ya se aplicaron; Flutter offline permanece pendiente de la conciliación del legado y de la validación en dispositivos reales.
