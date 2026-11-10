# SQL propuesto: correcciones críticas, sin aplicación real

2026-11-01. **Propuesta para revisión, no migración registrada, aplicada ni ensayada como conjunto.** No ejecutar 005 ni estos bloques por el estado del ledger. Los nombres nuevos deben reservarse tras conocer el historial de otros entornos. Se conserva 001/003/004/005 sin reescribir archivos.

## Inventario y caja

Diagnósticos reproducidos: [consultas SELECT](evidencias/correcciones_criticas_2026-11-01/diagnostico_consultas.sql). La pareja sucursal/variante tiene cero duplicados y cero identidades nulas. Las cantidades no presentan nulos/negativos ni reservas superiores a actual; hay 5.691 disponibles inconsistentes. La ruta de movimiento y las cuatro funciones SQL usan disponible = actual − reservado; no se encontró otra retención persistente en esos escritores. La definición comercial y la conciliación histórica requieren validación del responsable.

Solo después de aprobación del destino, revisión de escritores externos/instancias antiguas y de volver a ejecutar esos diagnósticos:

```sql
BEGIN;
SET LOCAL lock_timeout = '5s';
-- Precondición: resolver nulos/duplicados si aparecen entre diagnóstico y despliegue.
ALTER TABLE comercio.t_inventario
  ADD CONSTRAINT uq_crit_inventario_posicion UNIQUE(id_sucursal,id_variante);

-- NOT VALID controla nuevas escrituras sin afirmar que el histórico está conciliado.
-- Instalar este CHECK puede rechazar actualizaciones de las posiciones históricas
-- discrepantes. Su activación debe coordinarse con los escritores.
ALTER TABLE comercio.t_inventario ADD CONSTRAINT ck_crit_inventario_saldos CHECK (
  id_sucursal IS NOT NULL AND id_variante IS NOT NULL
  AND stock_actual IS NOT NULL AND stock_reservado IS NOT NULL AND stock_disponible IS NOT NULL
  AND stock_actual >= 0 AND stock_reservado >= 0 AND stock_disponible >= 0
  AND stock_reservado <= stock_actual
  AND stock_disponible = stock_actual-stock_reservado
) NOT VALID;

CREATE UNIQUE INDEX uq_crit_caja_abierta ON comercio.t_caja_sesion(id_caja)
  WHERE estado='ABIERTA';
COMMIT;
```

No se propone UNIQUE SKU ni cliente en este bloque: existe ambigüedad histórica que lo impediría o cambiaría la regla comercial. No se añade tenant a todas las tablas. La protección declarativa de referencias cruzadas debe decidirse después de aprobar los mapas; no se instala un trigger que invalide las 513 referencias sin conciliarlas.

Verificación posterior: repetir SELECT de duplicados/nulos/saldos/caja, comprobar los nombres y definiciones en `pg_constraint`/`pg_indexes`, probar última unidad y caja concurrentes en el destino aislado equivalente. **No ejecutar `VALIDATE CONSTRAINT ck_crit_inventario_saldos` hasta cerrar la conciliación**. El índice propuesto es transaccional ordinario: no se usa CONCURRENTLY con el ejecutor actual. Para una base grande se necesita otro procedimiento de despliegue, no cambiar silenciosamente el ejecutor.

Reversión limitada a estos objetos nuevos, una vez comprobada su propiedad y dependencias; no elimina datos ni objetos P1:

```sql
BEGIN;
DROP INDEX comercio.uq_crit_caja_abierta;
ALTER TABLE comercio.t_inventario DROP CONSTRAINT ck_crit_inventario_saldos;
ALTER TABLE comercio.t_inventario DROP CONSTRAINT uq_crit_inventario_posicion;
COMMIT;
```

## Mapas históricos: ninguna correspondencia aprobada

- [513 variantes: IDs y candidatos por tenant](evidencias/correcciones_criticas_2026-11-01/variantes_mapeo_NO_APROBADO.csv): 474 de empresa 1 y 39 de empresa 2. Los destinos aprobados están vacíos. Coincidir en nombre/HEX no basta para aprobar una equivalencia.
- [3 cuentas y todas sus referencias FK detectadas](evidencias/correcciones_criticas_2026-11-01/clientes_referencias_NO_FUSIONAR.json): no se eligió perfil canónico. Mantener los perfiles antiguos y sus IDs hasta resolver la política de consolidación.
- SKU empresa 1, variantes 154/157: `aur-den-011-40.0-azul`. Revisar talla/etiquetas/consumidores; no renombrar ninguno ni atribuir el grupo a una ejecución concreta sin evidencia.
- [Inventario por ID](evidencias/correcciones_criticas_2026-11-01/inventario_discrepancias.csv): no hay saldo objetivo aprobado. Conciliar por documento de ingreso, reserva activa, venta y movimiento, más conteo físico cuando falte historia. Separar siempre actual/reservado/disponible y registrar quién validó cada valor.

Plantilla de corrección de variantes, **sin INSERT de mapeos aprobado y no ejecutada**. Conserva id_variante y las FK históricas de ventas/reservas. La tabla temporal es solo entrada de revisión de una futura ejecución autorizada:

```sql
BEGIN;
SET LOCAL lock_timeout='5s';
CREATE TEMP TABLE mapa_variante_aprobado (
  id_variante integer PRIMARY KEY,
  talla_anterior integer, color_anterior integer,
  talla_nueva integer NOT NULL, color_nuevo integer NOT NULL,
  aprobado_por text NOT NULL CHECK(btrim(aprobado_por)<>'')
) ON COMMIT DROP;
-- Cargar exclusivamente correspondencias firmadas y revisar el SELECT siguiente.
SELECT m.*,p.id_empresa,t.id_empresa AS empresa_talla,c.id_empresa AS empresa_color
FROM mapa_variante_aprobado m
JOIN comercio.t_producto_talla_color v USING(id_variante)
JOIN comercio.t_producto p ON p.id_producto=v.id_producto
JOIN comercio.t_talla t ON t.id_talla=m.talla_nueva
JOIN comercio.t_color c ON c.id_color=m.color_nuevo;
-- La futura ejecución debe abortar si falta un ID, hay un destino de otra empresa,
-- si cambió el origen o si el resultado de combinaciones/SKU no está aprobado.
-- El SELECT no constituye por sí mismo esa validación.
ROLLBACK;
```

No se incluye un UPDATE listo para producción con IDs inferidos. Tras aprobar el archivo completo se debe preparar un ejecutor con precondiciones de todas las filas, bloqueo de variantes, actualización por ID exacto, conteos antes/después y registro del mapa anterior/nuevo. Su reversión utiliza ese mapa y se bloquea si cambió una correspondencia después del cambio. El mapa de clientes necesita además inventariar índices únicos y referencias de cada consumidor; no eliminar perfiles para satisfacer una restricción.

## Ampliación mínima pendiente para devoluciones

005 solo se verificó ausente en el destino configurado. No se dispone del historial de otros entornos; por ello no se parchea 005 ni se asigna un número definitivo a su corrección. Los siguientes bloques son diseño aditivo propuesto; requieren contrato, pruebas de ida/reversión con datos y autorización independiente antes de aplicarse.

Para reemplazar la repetición conservadora por una clave explícita de solicitud sin cambiar endpoints/DTO existentes:

```sql
ALTER TABLE comercio.t_devolucion
  ADD COLUMN clave_solicitud varchar(120),
  ADD COLUMN hash_solicitud char(64);
CREATE UNIQUE INDEX uq_crit_devolucion_clave
  ON comercio.t_devolucion(id_empresa,id_usuario,tipo_devolucion,clave_solicitud)
  WHERE clave_solicitud IS NOT NULL;
```

El servidor tomaría una clave HTTP por acción, compararía la huella del contenido completo y devolvería la misma devolución; una clave con otro contenido sería 409. No rellenar claves históricas ni reutilizar/modificar `t_sync_operacion`.

Para parciales/condiciones mixtas se necesita conservar cada entrega, no sobrescribir `cantidad` solicitada ni una única `condicion`. Dos tablas acotadas al flujo existente:

```sql
CREATE TABLE comercio.t_devolucion_recepcion_evento (
  id_recepcion uuid PRIMARY KEY,
  id_devolucion integer NOT NULL REFERENCES comercio.t_devolucion(id_devolucion),
  id_empresa integer NOT NULL REFERENCES comercio.empresa(id_empresa),
  id_sucursal integer NOT NULL REFERENCES comercio.t_sucursal(id_sucursal),
  id_usuario integer NOT NULL REFERENCES comercio.t_usuario(id_usuario),
  clave_operacion varchar(120) NOT NULL,
  hash_solicitud char(64) NOT NULL,
  respuesta_json jsonb NOT NULL,
  fecha_recepcion timestamptz NOT NULL DEFAULT now(),
  UNIQUE(id_empresa,id_usuario,clave_operacion)
);
CREATE TABLE comercio.t_devolucion_recepcion_item (
  id_recepcion uuid NOT NULL REFERENCES comercio.t_devolucion_recepcion_evento(id_recepcion),
  id_detalle_devolucion integer NOT NULL REFERENCES comercio.t_detalle_devolucion(id_detalle_devolucion),
  condicion varchar(30) NOT NULL CHECK(condicion IN ('REVENDIBLE','DEFECTUOSO','NO_REVENDIBLE')),
  cantidad integer NOT NULL CHECK(cantidad>0),
  PRIMARY KEY(id_recepcion,id_detalle_devolucion,condicion)
);
```

FK independientes no garantizan coincidencia de devolución/tenant. El ejecutor futuro debe bloquear venta y devolución, comprobar esa pertenencia, acumular aprobado/recibido bajo bloqueo, limitar cantidades, registrar la custodia defectuosa y confirmar stock/movimientos/auditoría/recibo en una sola transacción. El backend actual **no usa ni exige estas tablas para recibir una solicitud completa**; los parciales quedan bloqueados.

Para el único reembolso completo que permite el contrato actual, sin crear un subsistema de reintegros parciales:

```sql
CREATE TABLE comercio.t_devolucion_reembolso (
  id_reembolso uuid PRIMARY KEY,
  id_devolucion integer NOT NULL UNIQUE REFERENCES comercio.t_devolucion(id_devolucion),
  id_empresa integer NOT NULL REFERENCES comercio.empresa(id_empresa),
  id_metodo_pago integer NOT NULL REFERENCES comercio.t_metodo_pago(id_metodo_pago),
  id_sesion_caja integer REFERENCES comercio.t_caja_sesion(id_sesion_caja),
  importe numeric(12,2) NOT NULL CHECK(importe>0),
  moneda char(3) NOT NULL CHECK(moneda='BOB'),
  referencia varchar(150) NOT NULL CHECK(btrim(referencia)<>''),
  evidencia text NOT NULL CHECK(btrim(evidencia)<>''),
  id_usuario_confirmador integer NOT NULL REFERENCES comercio.t_usuario(id_usuario),
  fecha_confirmacion timestamptz NOT NULL DEFAULT now(),
  clave_operacion varchar(120) NOT NULL,
  hash_solicitud char(64) NOT NULL,
  respuesta_json jsonb NOT NULL,
  UNIQUE(id_empresa,id_usuario_confirmador,clave_operacion)
);
```

Este hecho sería a la vez la salida financiera de efectivo vinculada a sesión y devolución. **No basta crear la tabla**: adaptar efectivo esperado/arqueo/reportes para restar una sola vez ese importe; verificar sesión/caja/cajero/tenant, derecho neto recibido, método y evidencia de entrega; confirmar auditoría en la misma transacción. Transferencia/tarjeta necesitan confirmación manual autorizada verificable o respuesta auténtica del proveedor, nunca una referencia fabricada. No convertir `t_pago` en cobros negativos ni asignar reembolsos ficticios a los 106 cobros existentes.

Verificación/reversión: probar clave repetida/diferente, pérdida HTTP, reinicio, rollback financiero y auditoría, parcial/mixto y centavos. Con historia nueva, el DOWN debe **bloquear eliminación de tablas/columnas**, conservar eventos/evidencia y revertir mediante compatibilidad de aplicación. No se ha escrito un DOWN destructivo ni se ha ejecutado el DOWN de 005 en la base real. Nada de este diseño habilita ahora liquidaciones o parciales.
