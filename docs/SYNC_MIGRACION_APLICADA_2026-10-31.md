# Migraciones de idempotencia aplicadas

Fecha: 2026-10-31. Codex. Autorización explícita del usuario: «termina las migrcaciones y borra los elementos inncesarios luego»; en el contexto de las migraciones pendientes 003 y 004. No se aplicaron 001/002, no se asignaron planes ni se modificó `mobile/` o CU41W.

## Resultado real de PostgreSQL

Se aplicaron mediante `backend/migrate.py`, sin importar la aplicación, en el esquema configurado `comercio`:

- `003_iter2_sync_idempotency`: tabla de recibos, PK compuesta e índice por empresa/fecha.
- `004_iter2_sync_transactional`: huella, control de transición y FKs que conservan recibos mediante `ON DELETE RESTRICT`.

Cada migración se confirmó en su propia transacción, con bloqueo de migraciones y registro de checksum. La segunda aplicación de ambas devolvió «Sin cambios». No se ejecutaron ventas, reservas, cobros ni cambios de inventario de prueba en la base real.

La auditoría posterior, ejecutada con `transaction_read_only=on`, verificó:

| Comprobación | Resultado |
| --- | --- |
| `t_sync_operacion`, `t_sync_control`, `schema_migrations` | Presentes |
| PK `(id_usuario, id_empresa, operation_id)` | Presente |
| `request_hash` y restricción de formato | Presentes |
| FKs de usuario/empresa | `ON DELETE RESTRICT` |
| Índice por empresa/fecha | Presente |
| Registro de 003/004 y checksums de archivos | Coinciden |
| `fsync`, `full_page_writes`, `synchronous_commit` | `on` |
| Frontera de garantía | **2026-10-31 01:25:59.021451 UTC−04:00**, America/La_Paz |

Las definiciones de las funciones comerciales conservan los hashes de la auditoría inicial. La [evidencia posterior](evidencias/SYNC_POST_MIGRATION_2026-10-31.json) se conserva junto a la [auditoría previa](evidencias/SYNC_AUDIT_2026-10-31.json).

Se comprobó que el backend activo del puerto 5000 correspondía al directorio de este proyecto y se detuvo durante la transición. Las conexiones locales restantes a PostgreSQL pertenecían a pgAdmin; no se cerraron sus sesiones. Tras las migraciones y la limpieza, se restableció el servicio previamente activo con el código actual y sin generar bytecode. Se verificó el listener del puerto 5000; no se arrancó la aplicación para ejecutar pruebas comerciales contra la base real.

## Limpieza completada

Se eliminaron **55 directorios generados**, con **5.77 MiB** de archivos: `__pycache__` de código/pruebas del proyecto y `frontend/dist` generado por la validación de compilación. Todos los destinos se resolvieron dentro del workspace y se comprobó que no contenían archivos versionados antes de borrarlos.

Se conservó `.angular`, porque el servidor de desarrollo Angular continúa activo. Se conservaron fuentes, migraciones UP/DOWN, pruebas, fixtures SQL y evidencias, necesarios para mantener y verificar esta garantía. No se eliminaron operaciones locales ni recibos de PostgreSQL. Las eliminaciones de diagramas que ya existían en el workspace quedaron intactas.

## Alcance de la validación y pendientes

Esta actuación verifica la instalación y la reaplicación segura de las migraciones reales, no sustituye las pruebas de negocio aisladas ya documentadas. No hubo nuevos cambios de lógica que exigieran repetirlas.

Los resultados anteriores siguen diferenciados: integración transaccional con PostgreSQL descartable, pruebas Angular con IndexedDB emulado y compilación de producción. Las incidencias preexistentes de suites de rendimiento/permisos no se ocultan ni se corrigieron como parte de esta migración.

Las operaciones anteriores a la frontera sin evidencia verificable siguen requiriendo conciliación. No cambiar UUID, cuenta, empresa o fecha para forzar su aceptación. Queda pendiente la verificación en navegadores/dispositivos físicos. Flutter offline continúa sin iniciar y no se publicaron cambios ni se crearon ramas.
