# Contexto persistente de Iteración 1

## Alcance acordado

Backend SaaS para la web, conservando Angular P1 para integración por Antigravity. No tocar móvil ni respaldos/restauraciones. Trabajar en la rama actual (Eddy), sin crear ramas. No hacer push.

## Auditoría previa

Base compartida, esquema `comercio`, entidades P1 existentes. Hay `t_empleado` (sucursal principal) y `t_usuario_sucursal` (alcance múltiple). No crear sustitutos. Se observaron 6 sucursales, ninguna sin empresa y ninguna asignación cruzada; una empresa supera 2 sucursales activas. No asignar Básico automáticamente ni desactivar sucursales.

## Decisiones de implementación

- Roles compartidos P1: su definición y permisos solo los administra plataforma; administradores de empresa delegan a sus empleados únicamente roles/permisos autorizados.
- `t_usuario_sucursal` es autoridad de acceso. `t_empleado.id_sucursal` conserva el dato laboral heredado; no cambiarlo implícitamente. No trasladar usuarios o sucursales entre empresas mediante un PUT genérico.
- Planes fijos BASICO (2, sin reportes generativos) y PROFESIONAL (10, motor existente). No nueva IA. Historial de periodos; renovación administrativa explícita.
- No crear suscripciones de empresas existentes automáticamente. Antes del despliegue se debe aprobar plan y vigencia por empresa.
- Conservación de lectura/historial y terminación/cancelación de obligaciones existentes al vencer; bloquear nuevas compras, reservas, ventas y activaciones. La activación SaaS requiere aplicar la migración explícita.
- Restitución de versión: no borrar historial de suscripciones; la reversión debe bloquearse si hay datos nuevos.

## Integración futura móvil

No se modificó `mobile/`. La API compartida sí tendrá autorizaciones más estrictas: conservar la forma de los contratos P1 y documentar sus nuevos errores. Revisar los contratos y permisos actuales en `docs/ITER1_API.md` antes de migrar móvil; nunca asumir que el selector local autoriza acceso.

## Estado de entrega (2026-10-24)

Backend implementado en la rama actual, sin commit/push. Nuevas APIs: planes, historial/asignación/renovación/cancelación de suscripciones, consulta de vigencia/capacidades/uso; asignaciones P1 aseguradas. Motor existente requiere Profesional y reportes.ver. Clientes usan alcance CLIENTE; coordinar ampliación del enum con Antigravity.

Se corrigieron contextos de caja, KPIs, reportes, compras y bitácora relacionados con aislamiento. Usuario/roles/permisos/sucursales se guardan en una transacción. El administrador de plataforma conserva control de definiciones de roles compartidos; no se crearon roles por empresa. `DELETE empresa` desactiva. El arranque no modifica esquema ni vuelve a sembrar permisos.

29 pruebas pasan con PostgreSQL local desechable; la base real no fue modificada. No hay pruebas visuales ni regresión completa de funciones almacenadas/pagos P1. No se editaron archivos Angular; la implementación de sus nuevas pantallas corresponde a Antigravity mediante los contratos entregados. CU41W excluido por el usuario, no pendiente de implementar en este alcance.

Pendientes de liberación: revisar/coordinar contratos con Antigravity, construir y validar web, ensayar migración en clon completo P1, aprobar plan y vigencia de cada empresa existente y autorizar aplicación al destino real. La iteración completa todavía no debe darse por cerrada.

## Diagnóstico posterior de suscripciones web

Antigravity integró Angular (ver registro de cambios). El usuario reportó redirección de `/admin/suscripciones` a `/admin/kpis`. Se verificó en PostgreSQL, exclusivamente en lectura, que siguen ausentes `t_plan`, `t_suscripcion` y `schema_migrations`; no aplicar migración sin autorización. El guard exigía `suscripciones.ver` desde datos antiguos de login y ahora refresca permisos mediante `/api/rbac/mis-permisos`, sin inventar permisos ni omitir controles. Se corrigieron estados del historial (ACTIVA/CANCELADA), renovación con precisión temporal, errores ocultos del historial y respuestas tardías de otra empresa. 7 pruebas frontend pasan y build de producción exitoso. La funcionalidad real aún requiere aplicar la migración autorizada y verificar el recorrido conectado; no asignar suscripciones automáticamente.

## Aplicación real autorizada (2026-10-24; sustituye el estado pendiente anterior)

El usuario respondió «Ok, hazlo» a la solicitud explícita de aplicar `001_iter1_saas` en la base configurada, conservando datos y sin asignar planes automáticamente. Se ejecutó `python -B backend/migrate.py up --apply`, completado en una transacción. Verificación posterior de solo lectura: versión/checksum registrados, BASICO (2/sin reportes) y PROFESIONAL (10/con reportes) activos, los 4 permisos SaaS activos con asignaciones a roles, y 0 suscripciones. Conteos P1 antes/después sin cambios: empresas 2, usuarios 15, sucursales 6, pedidos 108, ventas 141. No se ejecutaron respaldos ni restauraciones ni se tocó móvil. Pendiente: recargar la web para refrescar permisos, recorrido conectado y asignación administrativa de planes/fechas aprobados. No inferir autorización para nuevas asignaciones a partir de esta aprobación de migración.
