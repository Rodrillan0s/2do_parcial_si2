# Analisis y propuesta de rediseño RBAC y control de accesos

## Estado de este documento

El documento se elaboro inicialmente como analisis y propuesta. La implementacion posterior esta identificada explicitamente en la seccion final.

La implementacion debe comenzar solamente despues de aprobar la arquitectura, el orden de fases y los permisos definitivos.

> Estado actualizado: la propuesta fue aprobada y se implementaron las primeras fases descritas. Las secciones siguientes conservan el analisis original; al final se detalla lo aplicado.

## Resumen ejecutivo

Aurora Store ya cuenta con una base funcional de autenticacion, multiempresa y RBAC:

- JWT firmado con usuario, rol, empresa, alcance, permisos y sucursales.
- Roles y permisos persistidos en PostgreSQL.
- Permisos heredados del rol y permisos directos por usuario.
- Relacion usuario-sucursal.
- Dependencias `require_permission`, tenant guard y guards de Angular.
- Sidebar y pantallas administrativas parcialmente filtradas por permisos.

El problema principal no es la ausencia de RBAC, sino la coexistencia de varias fuentes de autorizacion:

1. Permisos efectivos.
2. Nombre del rol.
3. ID numerico del rol.
4. Alcance derivado en distintos lugares.
5. Filtros de empresa o sucursal enviados por el cliente.

Esto provoca reglas duplicadas, inconsistencias y posibles bypasses. La propuesta es evolucionar el sistema actual hacia una politica central:

```text
Autenticacion
    -> permiso requerido
    -> alcance del usuario
    -> empresa efectiva
    -> sucursal autorizada
    -> acceso al recurso
```

## A. Estructura actual

### A.1 Backend

Autenticacion y JWT:

- `backend/app/routes/auth_routes.py`
- `backend/app/services/auth_services.py`
- `backend/app/repos/auth_repos.py`
- `backend/app/utils/security.py`
- `frontend/src/app/services/auth.ts`
- `frontend/src/app/interceptors/auth-interceptor.ts`

El backend valida firma y expiracion del JWT. El frontend guarda token y usuario en `localStorage` y usa el token para construir el estado visual.

El JWT actual contiene, entre otros:

```text
id_usuario / nro_usuario
id_rol
nombre_rol
roles
id_empresa
alcance
permisos
sucursales
```

RBAC y relaciones:

- `backend/app/utils/rbac_migration.py`
- `backend/app/utils/migrate_usuario_permisos.py`
- `backend/app/repos/rbac_repos.py`
- `backend/app/services/rbac_services.py`
- `backend/app/routes/rbac_routes.py`
- `backend/app/routes/roles_routes.py`
- `backend/app/routes/users_routes.py`
- `backend/app/services/users_services.py`
- `backend/app/repos/users_repos.py`

Tenancy y sucursales:

- `backend/app/utils/tenant_guard.py`
- `backend/app/routes/tenant_routes.py`
- `backend/app/services/tenant_services.py`
- `backend/app/routes/sucursales_routes.py`
- `backend/app/services/sucursales_services.py`
- `backend/app/repos/sucursales_repos.py`

### A.2 Tablas actuales relevantes

La migracion RBAC ya contempla estas tablas y relaciones:

```text
empresa
t_usuario
t_rol
t_permiso
t_usuario_rol
t_rol_permiso
t_usuario_permiso
t_sucursal
t_usuario_sucursal
t_bitacora
```

Relaciones existentes:

```text
Usuario 1:N Empresa mediante t_usuario.id_empresa
Usuario M:N Rol mediante t_usuario_rol
Rol M:N Permiso mediante t_rol_permiso
Usuario M:N Permiso directo mediante t_usuario_permiso
Usuario M:N Sucursal mediante t_usuario_sucursal
Sucursal N:1 Empresa mediante t_sucursal.id_empresa
```

Ademas, `t_usuario.id_rol` continua existiendo y algunos procesos lo usan como rol principal. Esto duplica la fuente de verdad frente a `t_usuario_rol`.

### A.3 Frontend

Autorizacion de interfaz:

- `frontend/src/app/services/auth.ts`
- `frontend/src/app/services/rbac.ts`
- `frontend/src/app/directives/has-permission.directive.ts`
- `frontend/src/app/guards/permission-guard.ts`
- `frontend/src/app/guards/scope-guard.ts`
- `frontend/src/app/guards/auth-guard.ts`
- `frontend/src/app/layouts/admin-layout/admin-layout.ts`
- `frontend/src/app/app.routes.ts`

El sidebar ya tiene un catalogo declarativo y filtra opciones por permiso y alcance. Varias pantallas tambien ocultan botones con `hasPermission`.

## B. Lo que ya funciona correctamente

Estas piezas deben conservarse y reutilizarse:

1. La separacion entre autenticacion y autorizacion mediante dependencias FastAPI.
2. `require_permission`, que puede consultar permisos en la base de datos cuando el JWT esta desactualizado.
3. La union de permisos heredados y directos en `obtener_permisos_efectivos_usuario`.
4. La relacion `t_usuario_sucursal` para representar sucursales autorizadas.
5. La validacion de pertenencia a empresa en `tenant_guard.py`.
6. La gestion actual de usuarios con validacion de jerarquia y permisos delegables.
7. La directiva `hasPermission` y los guards de Angular.
8. El sidebar filtrado por permisos y alcance.
9. La bitacora para auditar acciones RBAC.
10. Los tests de aislamiento administrador global versus administrador de tienda y los tests de POS/inventario existentes.

No se justifica una reescritura completa ni una separacion artificial de usuarios y empleados en esta etapa.

## C. Problemas y limitaciones comprobadas

### C.1 Fuentes de verdad duplicadas

La jerarquia de roles se repite en:

- `backend/app/services/rbac_services.py`
- `backend/app/repos/rbac_repos.py`
- `backend/app/utils/security.py`
- `backend/app/utils/tenant_guard.py`
- `frontend/src/app/services/auth.ts`

Tambien se usan simultaneamente `t_usuario.id_rol` y `t_usuario_rol`. Esto puede provocar que el login, la delegacion y los permisos efectivos no representen exactamente el mismo estado.

### C.2 Autorizacion por rol junto con autorizacion por permiso

Varias rutas operativas permiten acceso por IDs o nombres de rol, aunque ya existe RBAC. Ejemplos claros:

- `caja_routes.py`
- `pos_routes.py`
- `caja_pago_routes.py`
- `tenant_guard.py`
- `auth.ts`

Esto contradice parcialmente el objetivo de que el rol sea solo un agrupador de permisos.

### C.3 Cobertura backend desigual

Se encontraron rutas que usan solamente `verificar_token` y no una politica explicita de permiso para operaciones sensibles, entre ellas:

- Creacion y modificacion de productos.
- Modificacion de ciudades.
- Importacion y operaciones de compras/lotes.
- Algunas operaciones de reportes, KPIs y multimedia.

Algunas de estas rutas tienen controles manuales de tenant o servicio, pero no existe una regla uniforme `permiso + alcance + recurso`.

### C.4 Restriccion por sucursal no centralizada

Inventario, POS, caja y reportes aplican restricciones de sucursal de formas distintas. Algunas rutas aceptan un `id_sucursal` y lo validan, mientras otras dependen de filtros del servicio o de la lista del JWT.

Debe existir una sola funcion backend para resolver la sucursal efectiva y rechazar IDs fuera de `t_usuario_sucursal`.

### C.5 Rutas frontend con proteccion incompleta

En `frontend/src/app/app.routes.ts`, las rutas administrativas de:

- `triaje-chat`
- `catalogo`
- `proveedores`

dependen del guard de autenticacion padre, pero no tienen permiso especifico asociado.

El frontend no es la barrera de seguridad final, pero una ruta visible sin guard contradice la navegacion declarativa por permisos.

### C.6 Hardcodes de sucursal y valores fallback

`AuthService` mantiene una lista fija de sucursales y un fallback de sucursal `[1]`. Tambien existen fallbacks backend como `id_empresa or 1` e `id_usuario or 1`.

Estos valores pueden dirigir una operacion a una empresa o sucursal incorrecta si faltan claims o si la sesion esta incompleta.

### C.7 Riesgos de seguridad prioritarios

Se observaron los siguientes riesgos que deben atenderse antes o junto con el rediseño:

1. El registro publico acepta `id_rol` e `id_empresa` enviados por el cliente; debe crear siempre un cliente y no permitir autoasignacion de privilegios.
2. Los endpoints `/init-db`, `/run-tests` y `/check-tables` estan expuestos sin autenticacion y pueden tocar o revelar la base de datos.
3. El secreto JWT tiene fallback hardcodeado si faltan variables de entorno.
4. `DEBUG` queda activo por defecto si no se configura.
5. La verificacion de nuevo dispositivo debe comparar codigo y expiracion antes de registrar el dispositivo.
6. La recuperacion de contrasena puede revelar si una cuenta existe y el correo asociado.
7. No se observa invalidacion de tokens emitidos cuando cambia el rol, permiso, estado o sucursal del usuario.
8. El frontend conserva la sesion en `localStorage`, lo cual aumenta el impacto de un XSS.
9. La migracion RBAC no se ejecuta claramente durante `create_app()` y se apoya en endpoints de inicializacion.

Estos puntos no deben resolverse mezclados indiscriminadamente con el rediseño. Se propone tratarlos por prioridad y con pruebas especificas.

## D. Arquitectura propuesta

### D.1 Modelo conceptual

```text
Usuario
  |-- roles --------------------> Permisos efectivos
  |                               (rol + permisos directos)
  |
  |-- empresa ------------------> Empresa efectiva
  |
  |-- sucursales autorizadas ---> Sucursal efectiva
  |
  `-- estado / version ---------> Validez de la sesion
```

La decision de acceso debe ser:

```text
usuario autenticado
    y permiso requerido
    y usuario activo
    y empresa valida
    y sucursal autorizada cuando aplique
    y recurso perteneciente al contexto
```

### D.2 Politica de alcance

| Alcance | Empresa | Sucursales | Uso propuesto |
| --- | --- | --- | --- |
| `PLATAFORMA` | Todas, solo si la politica lo permite | Todas, solo si la politica lo permite | Administrador global |
| `EMPRESA` | Una empresa obligatoria | Cualquier sucursal activa de esa empresa, segun permiso | Administrador de tienda |
| `SUCURSAL` | Una empresa obligatoria | Solo las filas de `t_usuario_sucursal` | Encargado y cajero |

El alcance no debe derivarse unicamente del nombre del rol. El rol inicial puede sugerir un alcance por compatibilidad, pero el backend debe validar el alcance persistido y sus relaciones.

### D.3 Roles

Se conservaran los roles funcionales existentes:

```text
ADMINISTRADOR
ADMINISTRADOR_TIENDA
ENCARGADO_SUCURSAL
CAJERO
PROVEEDOR
CLIENTE
```

Se recomienda normalizar variantes legacy (`ENCARGADO`, `EMPLEADO`, `SUPERADMIN`, `GERENTE`, etc.) mediante una migracion controlada y dejar de aceptarlas progresivamente en reglas nuevas.

Para el alcance actual se recomienda la opcion A: roles del sistema con permisos predefinidos, mas permisos directos excepcionales ya soportados. No se recomienda habilitar roles totalmente dinamicos hasta estabilizar la politica central.

## E. Catalogo de permisos propuesto

El catalogo debe partir de los modulos existentes y reutilizar codigos actuales. Se deben eliminar duplicados y agregar solo los permisos necesarios para rutas reales.

### Seguridad y administracion

```text
admin.acceder
usuarios.ver
usuarios.crear
usuarios.editar
usuarios.desactivar
roles.ver
roles.crear
roles.editar
roles.asignar
permisos.ver
bitacora.ver
```

### Empresas, sucursales y catalogo

```text
empresas.ver
empresas.crear
empresas.editar
sucursales.ver
sucursales.crear
sucursales.editar
sucursales.desactivar
productos.ver
productos.crear
productos.editar
productos.eliminar
productos.cambiar_precio
categorias.ver
categorias.gestionar
tallas.ver
tallas.gestionar
```

### Operacion

```text
inventario.ver
inventario.gestionar
compras.ver
compras.crear
ventas.ver
ventas.crear
ventas.editar
ventas.anular
reservas.ver
reservas.atender
promociones.ver
promociones.crear
promociones.editar
```

### Caja, reportes e indicadores

```text
caja.ver
caja.abrir
caja.cerrar
pagos.procesar
comprobantes.ver
reportes.ver
reportes.generar
reportes.exportar
indicadores.ver
```

Antes de sembrar codigos nuevos se debe comparar este listado con `t_permiso` para evitar duplicar `ventas.crear` frente a `pos.vender`, o `inventario.gestionar` frente a otros codigos legacy.

## F. Cambios de base de datos propuestos

### F.1 Tablas a reutilizar

No se requieren nuevas tablas para el nucleo del modelo. Se reutilizaran:

- `empresa`
- `t_usuario`
- `t_rol`
- `t_permiso`
- `t_usuario_rol`
- `t_rol_permiso`
- `t_usuario_permiso`
- `t_sucursal`
- `t_usuario_sucursal`
- `t_bitacora`

### F.2 Ajustes recomendados

1. Definir `t_usuario_rol` como fuente principal de roles y mantener `t_usuario.id_rol` solo durante una etapa de compatibilidad.
2. Auditar y normalizar todos los roles legacy antes de retirar compatibilidad.
3. Garantizar que cada sucursal asignada al usuario pertenezca a su empresa.
4. Agregar restricciones o validaciones equivalentes para impedir asignaciones entre empresas.
5. Agregar una version de autorizacion del usuario, por ejemplo `authz_version` o `permisos_version`, para invalidar o refrescar sesiones cuando cambien roles, permisos, empresa, sucursal o estado.
6. Agregar indices para consultas por usuario, empresa y sucursal si el plan de PostgreSQL confirma que hacen falta.
7. Versionar las migraciones y evitar que endpoints HTTP ejecuten migraciones.

### F.3 Tabla opcional, solo si se requiere una politica explicita

No la implementaria en la primera fase, pero puede evaluarse una tabla de asignacion de alcance si se necesita distinguir formalmente empresa y sucursal de una simple relacion:

```text
t_usuario_alcance
    id_usuario
    alcance
    id_empresa
    activo
```

Por ahora `t_usuario.id_empresa` y `t_usuario_sucursal` cubren el modelo solicitado, con menos riesgo de migracion.

## G. Cambios backend propuestos

### G.1 Capa central de autorizacion

Crear una unica politica reutilizable, por ejemplo `authorize(permission, resource_context)`, que:

1. Valide JWT y usuario activo.
2. Obtenga permisos efectivos desde BD o cache controlada.
3. Resuelva alcance.
4. Resuelva empresa efectiva.
5. Valide sucursal efectiva si la operacion aplica.
6. Valide que el recurso pertenece a empresa/sucursal permitida.
7. Devuelva el contexto autorizado o `403`.

Las rutas dejarian de implementar copias de `if id_rol == ...` y usarian esta dependencia.

### G.2 Aplicacion por modulo

Prioridad de proteccion:

1. Registro publico y endpoints de inicializacion.
2. Usuarios, roles, permisos y sucursales.
3. Productos, inventario, compras y lotes.
4. Caja, POS, pagos y comprobantes.
5. Reservas, pedidos y promociones.
6. Reportes, KPIs, bitacora y multimedia.

Cada mutacion debe declarar el permiso requerido. Cada consulta debe usar el contexto backend, no confiar en `id_empresa` o `id_sucursal` enviados por el frontend.

### G.3 Regla de empresa y sucursal

Para usuarios no globales:

- El `id_empresa` del request nunca puede reemplazar la empresa del contexto autenticado.
- La empresa del recurso debe coincidir con la empresa autorizada.
- Una sucursal solicitada debe existir, estar activa, pertenecer a la empresa y estar asignada al usuario cuando el alcance sea `SUCURSAL`.
- Para operaciones de sucursal sin `id_sucursal`, el backend debe resolver la sucursal autorizada; no usar `1` como fallback.

### G.4 JWT y sesiones

Propuesta conservadora:

- Mantener en JWT solo identidad, empresa, alcance, roles resumidos, expiracion y version de autorizacion.
- No depender exclusivamente de `permisos` ni `sucursales` del JWT para decisiones sensibles.
- Consultar permisos/contexto en BD o cache invalidable en operaciones protegidas.
- Invalidar sesiones cuando cambien estado, roles, permisos, empresa o sucursales.
- Eliminar el secreto JWT hardcodeado y fallar al iniciar si falta una clave segura.
- Separar endpoints de desarrollo y pruebas del API publico.

## H. Cambios frontend propuestos

### H.1 Navegacion y rutas

- Mantener `permissionGuard`, `scopeGuard` y `hasPermission`.
- Asociar permiso a todas las rutas administrativas, incluyendo triaje-chat, catalogo y proveedores.
- Usar un catalogo comun de permisos para menu, rutas y botones.
- No usar nombre de rol como criterio principal de visibilidad.

### H.2 Gestion de usuarios y empleados

Se recomienda mantener un solo modulo administrativo en esta etapa, porque ya contiene:

- Datos personales.
- Estado de cuenta.
- Rol.
- Empresa.
- Sucursales.
- Permisos directos.
- Permisos efectivos.

La pantalla puede organizarse en secciones o tabs de `Cuenta` y `Asignacion operativa`, sin crear dos CRUD separados.

Debe permitir:

- Cambiar rol segun autoridad del actor.
- Cambiar empresa solo cuando el actor tenga alcance permitido.
- Asignar una o varias sucursales segun la politica del rol.
- Mostrar permisos heredados, directos y efectivos.
- Impedir que un usuario modifique su propia empresa, alcance o sucursal desde perfil.

### H.3 Selector de sucursal

- Eliminar lista fija de sucursales del frontend.
- Cargar solo sucursales autorizadas desde backend.
- Para alcance `SUCURSAL`, bloquear cambio a otra sucursal.
- Para alcance `EMPRESA`, mostrar solamente sucursales de su empresa.
- Para `PLATAFORMA`, permitir seleccion solo donde el permiso y la operacion lo admitan.

### H.4 Almacenamiento de sesion

No se cambiara sin pruebas el mecanismo actual, pero se recomienda migrar progresivamente desde `localStorage` hacia cookies seguras `HttpOnly`, `Secure` y `SameSite`, o documentar formalmente el riesgo aceptado.

## I. Flujo final de autorizacion

```text
1. Usuario autenticado
        |
2. Backend valida firma, expiracion y estado de sesion
        |
3. Obtiene permisos efectivos: rol + permisos directos
        |
4. Resuelve alcance: PLATAFORMA / EMPRESA / SUCURSAL
        |
5. Resuelve empresa autorizada
        |
6. Resuelve sucursal autorizada si aplica
        |
7. Comprueba permiso de la operacion
        |
8. Comprueba pertenencia empresa/sucursal del recurso
        |
9. Registra auditoria si es una mutacion sensible
        |
10. PERMITIR o devolver 403
```

## J. Plan de implementacion propuesto

### Fase 0: aprobacion y linea base

- Aprobar nombres de permisos y politica de alcance.
- Obtener inventario real de `t_rol`, `t_permiso`, asignaciones y usuarios.
- Ejecutar tests actuales sobre una base de datos de prueba.
- No modificar datos de produccion.

### Fase 1: cerrar riesgos criticos

- Forzar rol CLIENTE en registro publico.
- Proteger o retirar `/init-db`, `/run-tests` y `/check-tables`.
- Eliminar secretos fallback y `DEBUG=True` por defecto.
- Corregir verificacion de dispositivo y recuperacion de contrasena.
- Definir estrategia de invalidacion de sesion.

### Fase 2: normalizar modelo RBAC

- Consolidar jerarquia y alcance en un modulo backend.
- Normalizar roles legacy.
- Comparar y limpiar permisos duplicados.
- Definir fuente principal de roles.
- Preparar version de autorizacion.

### Fase 3: autorizacion backend central

- Implementar dependencia de permiso + alcance + tenant + sucursal.
- Migrar primero usuarios, roles, sucursales, productos e inventario.
- Migrar despues compras, POS, pagos, reservas, reportes y multimedia.
- Retirar atajos por nombre/ID de rol solo despues de cubrir cada ruta.

### Fase 4: frontend

- Alinear rutas, sidebar, botones, tabs y formularios con permisos.
- Eliminar sucursales hardcodeadas.
- Mostrar permisos efectivos.
- Mantener gestion de usuarios y empleados en el modulo actual.

### Fase 5: pruebas de seguridad y regresion

- Permisos individuales por endpoint.
- Aislamiento entre empresas.
- Aislamiento entre sucursales.
- Cambio de sucursal de un empleado.
- Cambio de rol y permisos con sesion anterior.
- Registro publico sin escalada.
- Compatibilidad de login, perfil, recuperacion y usuarios existentes.

## K. Matriz inicial de permisos por rol

Esta es una propuesta inicial para aprobar y ajustar con los casos de uso. No representa aun cambios ejecutados en la base.

| Rol | Permisos base propuestos | Alcance |
| --- | --- | --- |
| ADMINISTRADOR | Todos los permisos activos segun politica de plataforma | `PLATAFORMA` |
| ADMINISTRADOR_TIENDA | Usuarios/equipo, productos, inventario, sucursales, ventas, reservas, promociones, reportes de su empresa | `EMPRESA` |
| ENCARGADO_SUCURSAL | Inventario, disponibilidad, reservas, ventas y reportes permitidos | `SUCURSAL` |
| CAJERO | Ventas, caja, pagos, comprobantes y consulta de productos | `SUCURSAL` |
| PROVEEDOR | Operaciones de proveedor que el proyecto mantenga habilitadas | Segun empresa/relacion |
| CLIENTE | Tienda, productos publicos, ventas propias, pedidos y reservas propias | Propio |

La asignacion final debe basarse en los casos de uso reales, especialmente W14, W17, W22, W23, W24, W25, W30, W31, W32 y W33.

## L. Criterios de aprobacion antes de codificar

Se requiere confirmar:

1. Si `t_usuario_rol` sera la fuente principal y `t_usuario.id_rol` quedara solo como compatibilidad temporal.
2. Si `ENCARGADO_SUCURSAL` puede tener varias sucursales o inicialmente solo una.
3. Si se permiten permisos directos a usuarios o solo permisos por rol.
4. Si los roles seran predefinidos en esta entrega.
5. Los nombres canonicos de permisos que reemplazaran `pos.vender`, `caja.ver` y otros legacy.
6. Si se acepta una migracion de sesion para invalidar JWT al cambiar autorizacion.
7. El orden de las fases y el alcance de la primera implementacion.

## Conclusion

La recomendacion es evolucionar la implementacion existente, no reemplazarla:

```text
Reutilizar tablas y servicios actuales
    -> centralizar politica de autorizacion
    -> cerrar bypasses por rol y fallback
    -> reforzar empresa/sucursal en backend
    -> alinear frontend
    -> probar aislamiento y regresion
```

La primera entrega de codigo deberia concentrarse en Fase 1 y Fase 2. No conviene modificar simultaneamente todos los modulos hasta aprobar el catalogo de permisos, la fuente de verdad del rol y la politica de sucursales.

## M. Implementacion realizada tras la aprobacion

### Seguridad y autenticacion

- El registro publico fuerza `CLIENTE` y `id_empresa = NULL`; ya no acepta privilegios enviados por el cliente.
- La verificacion de dispositivo compara codigo y expiracion, y consume el codigo despues de usarlo.
- `/init-db`, `/run-tests` y `/check-tables` requieren administrador global con alcance `PLATAFORMA`.
- Se elimino el secreto JWT hardcodeado como fallback.
- `DEBUG` queda desactivado por defecto.
- La migracion RBAC se ejecuta durante el arranque, con manejo de advertencia si la base no esta disponible.

### Backend RBAC y aislamiento

- Se centralizo `tiene_permiso()` para consultar primero el JWT y luego permisos efectivos en BD.
- Caja, POS y pagos ya no autorizan por nombre o ID de rol; requieren permisos.
- Inventario resuelve sucursales autorizadas desde PostgreSQL mediante `t_usuario_sucursal`.
- Compras/importacion y ciudades ahora requieren permisos explicitos.
- Productos, imagenes y promociones ahora requieren permisos por operacion.
- Se eliminaron fallbacks silenciosos a empresa, usuario y sucursal `1` en los flujos modificados.
- Se agregaron a la semilla permisos de roles y sucursales usados por las rutas protegidas.

### Frontend

- `AuthService` ya no concede todos los permisos automaticamente por nombre `ADMINISTRADOR`.
- Las rutas administrativas de triaje, catalogo y proveedores tienen guard de permisos.
- La compilacion Angular fue exitosa; permanecen solo warnings preexistentes de presupuesto y `leaflet` CommonJS.

### Pruebas

- Se agrego `backend/test_rbac_policy_unit.py` con cinco pruebas unitarias de permisos, alcance global y sucursal.
- Las cinco pruebas pasan con `python -m unittest -v test_rbac_policy_unit.py`.
- La aplicacion FastAPI compila y genera OpenAPI correctamente.

### Pendientes para la siguiente fase

- Migrar el resto de rutas sensibles a la misma dependencia central.
- Auditar y normalizar todos los roles legacy y la duplicacion `t_usuario.id_rol` / `t_usuario_rol`.
- Implementar invalidacion de sesiones al cambiar autorizaciones.
- Ejecutar pruebas de aislamiento entre dos empresas y dos sucursales con PostgreSQL de prueba.
- Evaluar migracion de `localStorage` a cookies `HttpOnly`.

## N. Analisis de logs posterior

- Las rutas que inicialmente devolvian `404` ahora responden `401` sin token, confirmando que estan publicadas.
- El login del proceso principal devolvia `500` porque `backend/.env` existe, pero no contiene `TOKEN_KEY` ni `SECRET_KEY`. Tras el endurecimiento JWT, el error ahora se informa como `503` de configuracion en lugar de ocultarse como `500`.
- Con una clave efimera de prueba, el login funciona y devuelve permisos RBAC correctamente.
- Caja y POS devuelven `403` para un administrador global sin `id_empresa`/sucursal seleccionada. Es un rechazo esperado del contexto, no una ruta ausente.
- Compras convertia el `400` de tenant global faltante en `500`; se corrigio para preservar el codigo correcto y aceptar `id_empresa` explicito en ordenes y lotes.
- No se modifico el `backend/.env` real ni se dejo un archivo `.env.example`.
