# Revision de Caja (POS) y errores de API

## Problemas encontrados

### 1. Prefijos duplicados en tres routers

`create_app()` agregaba prefijos a routers que ya los declaraban internamente:

| Funcionalidad | Ruta solicitada por frontend | Ruta que quedaba publicada | Resultado |
| --- | --- | --- | --- |
| Plantilla de importacion | `/api/inventario/importacion/plantilla` | `/api/compras-lotes/api/inventario/importacion/plantilla` | `404` |
| Asistente | `/api/asistente/chat` | `/api/asistente/api/asistente/chat` | `404` |
| Motor de reportes | `/api/motor-reportes/parse-command` | `/api/reportes/api/motor-reportes/parse-command` | `404` |

El frontend estaba consumiendo las rutas correctas. El error estaba en el registro de routers del backend, no en CORS ni en la comunicacion entre procesos.

### 2. Error en el contexto de empresa de Caja y POS

En `caja_routes.py` y `pos_routes.py` se calculaba la empresa efectiva en `id_emp`, pero se enviaba la variable inexistente `id_empresa` al repositorio. Cuando una apertura de caja o una venta llegara a esa linea, produciria un `NameError` y una respuesta `500`.

### 3. Prefijos duplicados en Caja y pagos POS

El mismo error estaba aplicado a los routers de caja, POS y pagos de caja. Por ejemplo, el endpoint esperado `/api/caja/estado` quedaba publicado bajo `/api/caja/api/caja/estado`. Por eso se corrigio tambien su registro en `create_app()`.

## Cambios realizados

- Se registraron sin prefijo adicional los routers de compras/lotes, asistente y motor de reportes.
- Se registraron sin prefijo adicional los routers de caja, POS y pagos de caja.
- Se reemplazo `id_empresa=id_empresa` por `id_empresa=id_emp` en apertura de caja y registro de venta POS.
- Se mantuvieron las URLs del frontend, por lo que no se requiere cambiar Angular.

## Estado esperado de las rutas

- `GET /api/inventario/importacion/plantilla`
- `POST /api/inventario/importacion/preview`
- `POST /api/inventario/importacion/confirmar`
- `POST /api/asistente/chat`
- `GET /api/motor-reportes/catalogo`
- `POST /api/motor-reportes/parse-command`
- `POST /api/motor-reportes/ejecutar`
- `POST /api/motor-reportes/exportar/pdf`
- `GET /api/caja/estado`
- `POST /api/caja/abrir`
- `POST /api/caja/cerrar`
- `GET /api/pos/productos`
- `POST /api/pos/ventas`

## Caja/POS y base de datos

El flujo de caja esta implementado y depende de estas operaciones persistentes:

1. Consultar denominaciones y caja disponible de la sucursal.
2. Abrir una sesion asociada a usuario, empresa, sucursal y caja.
3. Impedir ventas si el cajero no tiene una sesion abierta.
4. Registrar la venta con bloqueo de inventario.
5. Procesar el pago y actualizar el estado de la venta.
6. Calcular el resumen y cerrar la caja con arqueo de denominaciones.

Los `404` ocurridos no eran causados por tablas o datos faltantes: la peticion no alcanzaba ningun handler. La validacion de saldos, sesiones, inventario y pagos si requiere ejecutar contra PostgreSQL con las variables de entorno configuradas y un usuario con permisos de cajero.

## Validacion

- `python -m compileall -q app` fue ejecutado sobre el backend sin errores de sintaxis.
- Se deben reiniciar el backend y Angular para descartar rutas antiguas en procesos ya iniciados.
- Luego deben repetirse las llamadas de los logs. Un problema de datos o permisos, si existe, ya debera aparecer como `400`, `401`, `403` o `500` con detalle, no como `404`.