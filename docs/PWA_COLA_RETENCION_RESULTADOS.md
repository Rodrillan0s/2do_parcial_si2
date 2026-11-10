# Cola Angular: conservación y confirmación verificable

Fecha: 2026-10-31. Codex. Excepción al reparto de AGENTS.md autorizada expresamente por el usuario: «Autorizar la corrección mínima de la cola». Posteriormente, el usuario autorizó terminar las migraciones 003/004; su aplicación se documenta en el [acta correspondiente](SYNC_MIGRACION_APLICADA_2026-10-31.md). El ajuste de la cola no modificó `mobile/`, guards ni permisos, ni publicó cambios.

## Resultado

- `IndexedDbService` exige IndexedDB para `pending_operations`, `sync_attempts` y el nuevo `sync_receipts`. Una escritura crítica solo resuelve al completarse la transacción con durabilidad estricta. Cuota, bloqueo, aborto o error se propagan; el fallback RAM sigue disponible para cachés descartables.
- La migración local a versión 4 crea el almacén de recibos sin borrar datos. También abre versiones físicas superiores que instalaciones anteriores pudieron generar al reparar almacenes; se probó desde versiones 3 y 7. No se usa `deleteDatabase` ni se limpian operaciones al actualizar.
- `acknowledgeOperation` valida estado `synced`, HTTP individual 2xx, `confirmation_verified=true`, UUID, tipo, usuario/empresa, formato de huella y resultado comercial: venta PAGADO con IDs de venta y pago, o reserva con ID y código. La huella es evidencia recibida de la API autenticada; el cliente no la presenta como firma criptográfica ni recalcula el hash Python.
- El guardado del recibo completo y su intento, la comparación del sobre enviado contra el pendiente actual y la retirada del pendiente ocurren en una sola transacción IndexedDB. Un fallo en cualquier escritura revierte las demás. Otra pestaña no puede recrear un pendiente después de quedar registrado su recibo.
- Una respuesta parcial, duplicada, sin identidad/confirmación o un HTTP perdido conserva UUID, contenido, cuenta, tenant y fecha original. Los contadores muestran únicamente confirmaciones verificadas. Un error posterior del lote no recrea operaciones ya confirmadas.
- Logout, 401, cambio de usuario o empresa ocultan la cola anterior y conservan sus registros. Las lecturas, acciones por UUID y envíos de la cola se limitan al usuario autenticado y empresa actuales. Un cambio de sesión durante el chequeo de conectividad cancela el envío; durante HTTP hace que se ignore esa respuesta hasta verificarla nuevamente con el propietario.
- Se adquiere el bloqueo local antes del primer `await`. Se distinguen operaciones actualmente en vuelo de estados `syncing` heredados de un cierre anterior; estos últimos pueden reenviarse con su clave original.
- Una nota de conciliación no elimina una venta ni certifica su resultado. Se añade como evento durable, sin truncarlo a 50 elementos; se mantiene la lectura del historial legado. Se requiere nota no vacía. Descartar una reserva o carrito conserva el pendiente en revisión. Incluso cancelar un agregado de carrito antes de enviarlo conserva su evidencia local.
- No se compacta una operación que ya tuvo intentos ni se cambia un payload con resultado incierto. Los parches se permiten tras un rechazo de negocio conocido del protocolo nuevo; un reenvío sin parche conserva el sobre original.
- El panel conserva su diseño. Se ajustaron los textos a «Guardar nota de conciliación», «Notas de conciliación de caja» y «Conservar para revisión» para reflejar lo que realizan las acciones.

El aislamiento de IndexedDB es separación de contexto en la aplicación; no cifra datos frente al dueño del navegador/DevTools. La autorización multitenant del servidor permanece como autoridad.

## Pruebas ejecutadas

Se añadió `fake-indexeddb` como dependencia **solo de desarrollo**, sin incorporarla al producto. Las pruebas usan Angular TestBed/Vitest, jsdom, un emulador transaccional de IndexedDB y una API simulada; no son pruebas de navegador físico ni ventas reales.

| Comprobación | Resultado |
| --- | --- |
| 21 pruebas de almacenamiento y recibos | Aprobadas |
| 19 pruebas de cola, contextos y reenvíos | Aprobadas |
| Suite general Angular, 47 pruebas | 46 aprobadas; 1 fallo ajeno en `permission-guard.spec.ts` |
| Compilación producción `npm run build` | Aprobada, 712.75 kB iniciales / 154.09 kB de transferencia estimada |

El fallo general es `TypeError: authService.hasAnyPermission is not a function` en el escenario de red del test de permisos: su mock no implementa el método que usa el guard. Ni ese test ni el guard fueron modificados. No se declara verde toda la suite. La compilación conserva la advertencia previa de CommonJS de Leaflet.

Casos comprobados: confirmación válida; recibo de otra identidad/tipo/operación; falta de huella, pago, venta, estado PAGADO o HTTP individual; fallo de recibo y fallo de eliminación con rollback; cuota y falta de IndexedDB sin éxito en RAM; purga y reapertura con pendientes/recibos; versiones previas; escritura atrasada de otra instancia; payload editado durante envío; respuesta parcial/perdida; error posterior a un primer recibo; reconexiones simultáneas; cambio de sesión antes y después del envío; reautenticación del propietario; notas e historial mayor a 50; descarte sin recibo; UUID de otra cuenta; bloqueo de parches inciertos/sobrescritura/compactación; cancelación local con evidencia; recuperación de estados heredados.

Reproducción desde `frontend/`:

```powershell
npm test -- --watch=false --include=src/app/core/storage/indexed-db.service.spec.ts --include=src/app/core/sync/sync-queue.service.spec.ts
npm test -- --watch=false
npm run build
```

## Pendientes reales

003/004 ya fueron autorizadas y aplicadas con el backend local detenido; tablas, restricciones, checksums y reaplicación se verificaron en la base real. Se restableció el servicio local tras completar la transición. Revisar [acta de aplicación](SYNC_MIGRACION_APLICADA_2026-10-31.md), [informe transaccional](SYNC_IDEMPOTENCIA_TRANSACCIONAL.md) y [contrato](PWA_CONTRATO_SYNC.md).

Queda la verificación en navegadores/dispositivos reales (cuotas, cierres y persistencia del perfil), la corrección independiente del test de permisos y la conciliación de operaciones anteriores sin evidencia. La aplicación no puede impedir que el usuario borre físicamente el perfil/almacenamiento del navegador. Flutter offline permanece sin iniciar.
