# Migración SaaS 001 y despliegue

**Actualización 2026-10-24:** el usuario autorizó expresamente y se aplicó `001_iter1_saas` en la base configurada, esquema `comercio`. Se verificaron versión/checksum, planes y permisos. Se conservaron los conteos P1: 2 empresas, 15 usuarios, 6 sucursales, 108 pedidos y 141 ventas. Hay 0 suscripciones: no se asignaron planes ni vigencias automáticamente. Las instrucciones siguientes se conservan para otros entornos y futuras operaciones autorizadas.

## Estructura

`backend/migrations/001_iter1_saas.up.sql` añade `t_plan` y `t_suscripcion`, índices, permisos y triggers. Reutiliza tablas P1. Incluye claves foráneas de empresa en usuarios/sucursales y valida referencias existentes. Si existen huérfanos o un objeto incompatible, falla y revierte la transacción; no repara ni borra datos.

Las altas/reactivaciones de sucursales activas exigen empresa activa y periodo vigente. La empresa se bloquea durante el conteo para serializar solicitudes. La edición general no permite trasladar una sucursal entre empresas. Las asignaciones tienen control adicional en PostgreSQL. Las suscripciones tienen periodos inmutables y no solapados por empresa; renovación = nuevo periodo, cancelación = estado histórico.

No se activó RLS ni se convirtió el modelo compartido a schemas por empresa. La autorización de la API es por contexto vigente y permisos; los triggers refuerzan las reglas indicadas.

## Preparación sin tocar la base

```powershell
python -B backend/migrate.py up
python -B backend/migrate.py down
```

Por defecto solo imprime el SQL. No importa `app`, no conecta a PostgreSQL y no escribe. El esquema configurable se valida antes de interpolarlo.

## Antes de un despliegue autorizado

1. Aprobar plan y fechas por empresa actual. Una empresa auditada supera Básico: no asignarle Básico ni desactivar sucursales automáticamente. Considerar Profesional si corresponde y obtener aprobación administrativa.
2. Ensayar con una copia de P1 en un entorno aislado, incluyendo vistas, funciones almacenadas y datos representativos. La fixture de pruebas es mínima y no sustituye ese ensayo.
3. Coordinar los contratos de `docs/ITER1_API.md` con Antigravity, especialmente alcance CLIENTE, errores y permisos sobre roles compartidos. Completar pruebas visuales web antes de liberar.
4. Detener escrituras durante la migración/alta inicial de suscripciones y revisar datos huérfanos o incompatibles. Cualquier operación sobre datos reales requiere autorización específica. CU41W no forma parte del trabajo.
5. Ejecutar el siguiente comando solo contra el destino aprobado, con DB_HOST/DB_PORT/DB_NAME/DB_USER/DB_PASSWORD/DB_SCHEMA del entorno adecuado:

```powershell
python -B backend/migrate.py up --apply
```

El ejecutor usa bloqueo de migraciones, checksum y registro `schema_migrations`. Una segunda ejecución de la misma versión es inocua; un checksum alterado se rechaza. Toda la migración se confirma en una sola transacción. No hay migración ni reinserción de permisos durante el arranque de FastAPI.

6. Asignar las suscripciones aprobadas mediante la API de plataforma y comprobar límites antes de habilitar nuevas operaciones comerciales. No hay periodos gratis, Básico automático ni nuevas vigencias implícitas.

## Reversión

```powershell
python -B backend/migrate.py down --apply
```

Solo en destino autorizado. No usa CASCADE sobre tablas P1. Elimina objetos nuevos y únicamente semillas RBAC que la migración registró como propias. Conserva entidades/registros P1. Se bloquea si existe cualquier historial de suscripción o nuevas delegaciones de los permisos creados: preservar esos datos y acordar una reversión específica antes de continuar. No cambiar los SQL después de aplicarlos; añadir una nueva versión.

Revertir requiere desplegar también una versión compatible del backend. El código SaaS devuelve 503 si sus tablas no existen; nunca omite controles por falta de migración.

## Arranque P1

FastAPI ya no ejecuta automáticamente `asegurar_vistas_sql`, `migrar_tablas_compras_lotes` ni `ejecutar_migracion_rbac`. Las utilidades históricas se conservan, pero no se ejecutan desde la migración SaaS ni las pruebas. Una instalación P1 vacía requiere su proceso de preparación explícito; la migración 001 presupone el esquema P1 existente y no lo reconstruye.

## Verificación automatizada

```powershell
python -B -m unittest discover -s tests -v
```

Las pruebas crean un cluster PostgreSQL temporal local con conexión limitada a loopback, usan datos ficticios y lo eliminan al finalizar. No usan las credenciales del proyecto para conectarse. Se necesita PostgreSQL local (`initdb` y `postgres`), o definir `ITER1_PG_BIN`. Si no está disponible, unittest lo informa como omitido; no equivale a éxito de integración.

Verificaciones: aislamiento por empresa/sucursal, permisos revocados, límites 2/10 y reactivación, concurrencia, vigencia, reportes Profesional, renovación/solapamiento, cancelación, rollback de usuario/asignaciones/auditoría, migración/reversión/idempotencia/checksum y arranque sin conexiones ni DDL con registro de rutas P1.

Pendiente: clon completo P1 con funciones almacenadas, pagos/entregas/caja de extremo a extremo y pruebas de navegación Angular. La migración real autorizada se aplicó y verificó el 2026-10-24; no se ejecutaron pruebas comerciales de escritura ni pruebas visuales de navegador sobre esa base.


## Endurecimiento sync (2026-10-31)

La auditoría inicial detectó que faltaban la tabla sync y su registro de migraciones. Tras autorización explícita, **003 y 004 se aplicaron y verificaron en la base real el 2026-10-31**, sin cambios al contenido de 003. La reaplicación devuelve «Sin cambios». Revisar el [acta de aplicación](SYNC_MIGRACION_APLICADA_2026-10-31.md), [informe transaccional](SYNC_IDEMPOTENCIA_TRANSACCIONAL.md) y [contrato actualizado](PWA_CONTRATO_SYNC.md) para permisos, reversibilidad y conciliación de operaciones anteriores. No ejecutar 003 DOWN cuando existan recibos reales. Flutter offline permanece pendiente de conciliación y validación en dispositivos reales.
