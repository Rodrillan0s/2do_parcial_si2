# Iteración 1 — contrato para Antigravity

Estado actualizado al 2026-10-24: backend e integración Angular implementados localmente. Migración real `001_iter1_saas` aplicada con autorización del usuario y verificada en el esquema configurado `comercio`. Los planes y permisos están creados; no se asignaron suscripciones automáticamente. Publicación del código y recorrido visual conectado aún no verificados. No modificar `mobile/` ni respaldos.

## Autorización y compatibilidad P1

Autenticación `Authorization: Bearer <token>`. Cada petición reconstruye empresa, roles activos, permisos y sucursales desde la base. Un JWT válido de un usuario desactivado devuelve 401; las revocaciones surten efecto en la siguiente petición. Los campos del JWT y los selectores del cliente no sustituyen la autorización del servidor.

Alcances internos y de sesión: `PLATAFORMA`, `EMPRESA`, `SUCURSAL`, **`CLIENTE`**. Este último corrige el alcance de clientes sin empresa; antes podían recibir la etiqueta PLATAFORMA. Angular ya incorpora este alcance y las pantallas SaaS; mantener a clientes fuera de `/admin` y completar la validación visual conectada antes de liberar. El guard actualiza permisos mediante `/api/rbac/mis-permisos`, sin depender únicamente de los guardados al iniciar sesión.

Se conservan rutas, métodos y cuerpos P1 salvo estas validaciones documentadas:

- Un selector de empresa ajena para personal de empresa/sucursal devuelve 403. Los clientes pueden seleccionar tiendas públicas activas y operar únicamente sus propios carritos/pedidos/reservas.
- Definir/modificar/desactivar roles compartidos o sus permisos requiere plataforma, además del permiso correspondiente. Abarca `/api/roles/*` y definiciones de `/api/rbac/roles*` y `/api/rbac/permisos`. Las empresas delegan roles/permisos existentes dentro de su autoridad; no modifican roles compartidos por otras empresas.
- `DELETE /api/empresas/{id}` conserva el contrato de acción exitosa, pero **desactiva** la empresa; no elimina registros. El mensaje indica desactivación.
- Los PUT genéricos no trasladan usuarios/sucursales entre empresas. Se rechazan con 409 cuando se solicita un traslado; no se remapean relaciones P1.
- Asignaciones exigen listas explícitas de enteros positivos. Omitir la lista es 422; `[]` revoca. No se aceptan booleanos como IDs. Los empleados y sucursales deben tener la misma empresa, las sucursales deben estar activas, y un actor con alcance SUCURSAL no puede gestionar personal ajeno a su alcance.
- Los controles de KPIs, reportes, supervisión de caja y operaciones de compras dejan de usar empresas/sucursales predeterminadas como autorización. Una sucursal ajena o sin asignación devuelve 403. En operaciones de compras por ID, la empresa se obtiene de la orden y luego se autoriza, sin elegir empresa 1.
- El motor `/api/motor-reportes/*` requiere `reportes.ver`. Parsear/ejecutar/exportar requiere además Profesional vigente. El catálogo requiere el permiso de lectura. Los reportes P1 convencionales conservan su disponibilidad por permisos; no son una nueva función de IA.

## Permisos SaaS

| Código | Uso | Asignación inicial de la migración |
|---|---|---|
| `planes.ver` | Catálogo | Administrador, Superadmin y personal de empresa definido en la semilla |
| `planes.gestionar` | Nombre/disponibilidad de planes | Administrador/Superadmin; ruta exige alcance PLATAFORMA |
| `suscripciones.ver` | Vigencia, uso, historial propio | Administrador, Superadmin y personal de empresa definido en la semilla |
| `suscripciones.gestionar` | Asignación, renovación, cancelación | Administrador/Superadmin; ruta exige alcance PLATAFORMA |

La semilla de lectura incluye `ADMINISTRADOR_TIENDA`, `ENCARGADO_SUCURSAL`, `CAJERO`, `EMPLEADO`. No cambia delegaciones P1 ni reactiva permisos previamente desactivados. Roles personalizados requieren delegación explícita.

## Rutas nuevas

Todas las respuestas JSON exitosas usan `{ "success": true, "data": ... }`. Fechas ISO 8601 con zona horaria. Los cuerpos nuevos rechazan campos desconocidos.

### Planes

- `GET /api/planes` — `planes.ver`. `data` es una lista con `codigo`, `nombre`, `max_sucursales`, `reportes_generativos`, `activo`.
- `PUT /api/planes/{codigo}` — plataforma + `planes.gestionar`.

```json
{ "nombre": "Profesional", "activo": true }
```

Códigos fijos `BASICO` (2 activas, reportes generativos false) y `PROFESIONAL` (10, true). No hay CRUD de límites arbitrarios ni precios/cobros recurrentes. Desactivar un plan impide nuevas suscripciones, pero no revoca periodos ya concedidos.

### Asignar y renovar suscripción

- `GET /api/empresas/{id}/suscripciones` — `suscripciones.ver`, empresa propia o plataforma. Lista histórica, incluidas canceladas/vencidas.
- `POST /api/empresas/{id}/suscripciones` — plataforma + `suscripciones.gestionar`, respuesta 201. La misma ruta registra una renovación creando otro periodo; no altera el anterior.

```json
{
  "codigo_plan": "PROFESIONAL",
  "inicio": "2026-11-01T00:00:00-04:00",
  "fin": "2026-12-01T00:00:00-04:00",
  "motivo": "Renovación administrativa aprobada"
}
```

Respuesta `data`: `id_suscripcion`, `id_empresa`, `codigo_plan`, `inicio`, `fin`, `estado`, `motivo`, `creado_por`, `creado_en`.

Los intervalos son `[inicio, fin)`: una renovación puede empezar exactamente en el fin anterior. Fin debe ser futuro y posterior al inicio. No se permiten periodos activos solapados. No se asigna un plan cuya capacidad sea inferior al uso actual; el administrador debe resolverlo expresamente. Las activaciones también respetan planes futuros programados.

- `POST /api/empresas/{id}/suscripciones/{id_suscripcion}/cancelar` — plataforma + `suscripciones.gestionar`.

```json
{ "motivo": "Cancelación administrativa solicitada", "confirmar": true }
```

Respuesta `data`: `{ "id_suscripcion": 123, "estado": "CANCELADA" }`. No se borra el registro. Una cancelación repetida devuelve 404. Mostrar confirmación al administrador antes de enviarla.

### Consultar plan y límites (CU36W)

- `GET /api/mi-empresa/plan` — `suscripciones.ver`. Empresa desde la sesión.
- Plataforma: `GET /api/mi-empresa/plan?id_empresa=123`. Selector obligatorio para plataforma, no autoriza empresas ajenas para otros usuarios. Permite consultar una empresa suspendida.

```json
{
  "success": true,
  "data": {
    "id_empresa": 123,
    "estado": "VIGENTE",
    "vigente": true,
    "id_suscripcion": 456,
    "codigo_plan": "BASICO",
    "inicio": "2026-11-01T04:00:00Z",
    "fin": "2026-12-01T04:00:00Z",
    "limites": { "sucursales_activas": 2 },
    "uso": { "sucursales_activas": 1 },
    "disponibles": 1,
    "capacidades": { "reportes_generativos": false }
  }
}
```

Estados: `VIGENTE`, `SIN_SUSCRIPCION`, `PROGRAMADA`, `VENCIDA`, `CANCELADA`, `EMPRESA_INACTIVA`. Sin periodo actual, ID/plan/fechas/límite son null y disponibles es 0. El catálogo se consulta por separado. No deducir autoridad de `disponibles`: el servidor vuelve a validar cada escritura.

## Asignaciones reutilizadas (CU43W)

- `GET /api/rbac/usuarios/{id}/sucursales` — `sucursales.ver`; respuesta P1 `{success,id_usuario,sucursales:[1,2]}`.
- `POST /api/rbac/usuarios/{id}/sucursales` — `sucursales.asignar`.

```json
{ "ids_sucursales": [1, 2] }
```

Respuesta `{success:true,message,id_usuario,sucursales:[1,2]}`. Reemplazo completo y atómico; `[]` revoca. El servidor valida IDs, empresa, sucursales activas, alcance del actor y jerarquía del empleado; registra el antes/después. `t_empleado.id_sucursal` conserva el dato laboral P1, no se reescribe implícitamente. La autorización se obtiene de `t_usuario_sucursal`.

El registro/edición P1 de usuarios sigue aceptando `ids_sucursales`, `ids_permisos`, `id_rol`/`nro_rol`; usuario, rol y asignaciones se guardan o revierten juntos. Las contraseñas se guardan en la columna P1 `password_hash`.

## Vigencia y errores

Sin vigencia se bloquea crear pedidos, reservas y ventas POS nuevas, y crear/reactivar sucursales activas. Se conserva historial y no se añaden restricciones de plan a cobros/entregas/cancelaciones de obligaciones P1 existentes. No se desactivan sucursales automáticamente. El conteo incluye únicamente sucursales activas y se protege frente a concurrencia en PostgreSQL.

Errores nuevos SaaS: `{ "detail": { "code": "LIMITE_SUCURSALES", "message": "..." } }`. Los endpoints P1 también pueden conservar `detail` como texto; Angular debe manejar ambos formatos y 422 de validación.

| HTTP | Códigos/casos |
|---|---|
| 400 | Falta selección de empresa para una operación de plataforma |
| 401 | Token inválido/expirado o usuario desactivado |
| 403 | Empresa/sucursal/permiso ajeno, `SUSCRIPCION_NO_VIGENTE`, `PLAN_NO_HABILITA_REPORTES`, `EMPRESA_INACTIVA` |
| 404 | `PLAN_NO_ENCONTRADO`, `EMPRESA_NO_ENCONTRADA`, `SUSCRIPCION_NO_ENCONTRADA` |
| 409 | `LIMITE_SUCURSALES`, `LIMITE_PLAN_PROGRAMADO`, `PERIODO_SOLAPADO`, traslado entre empresas |
| 422 | Cuerpo, fechas, lista de IDs o confirmación inválidos |
| 503 | `MIGRACION_PENDIENTE` o sesión no verificable por indisponibilidad de BD |

## Entrega a Antigravity

Integrar catálogo, suscripción/historial, consulta de límites y asignaciones con estas rutas reales. Reutilizar pantallas/patrones P1. Añadir guards/menús por permiso, estado y capacidades sin sustituir las validaciones del servidor. Ampliar alcance `CLIENTE`, adaptar errores y el mensaje de desactivación de empresas. Probar carga, vacío, error, confirmación y recorrido por roles con dos empresas. No tocar esquema ni reglas del backend. No tocar respaldos ni móvil.
