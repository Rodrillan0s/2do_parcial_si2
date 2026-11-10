-- ============================================================================
-- AuroraStore Iteración 3 — Migración 005 (DOWN): Reversión de Gestión de Devoluciones
-- ============================================================================

-- 1. Eliminar Permisos y Relaciones RBAC
DELETE FROM __SCHEMA__.t_rol_permiso
WHERE id_permiso IN (
    SELECT id_permiso FROM __SCHEMA__.t_permiso WHERE codigo LIKE 'devoluciones.%'
);

DELETE FROM __SCHEMA__.t_permiso
WHERE codigo LIKE 'devoluciones.%';

-- 2. Eliminar Índices Creados
DROP INDEX IF EXISTS __SCHEMA__.idx_devolucion_empresa_estado;
DROP INDEX IF EXISTS __SCHEMA__.idx_devolucion_venta;
DROP INDEX IF EXISTS __SCHEMA__.idx_devolucion_usuario;
DROP INDEX IF EXISTS __SCHEMA__.idx_detalle_devolucion_devolucion;
DROP INDEX IF EXISTS __SCHEMA__.idx_detalle_devolucion_detalle_venta;

-- 3. Revertir Columnas en t_detalle_devolucion
ALTER TABLE __SCHEMA__.t_detalle_devolucion DROP COLUMN IF EXISTS estado_item;
ALTER TABLE __SCHEMA__.t_detalle_devolucion DROP COLUMN IF EXISTS monto_reembolso;
ALTER TABLE __SCHEMA__.t_detalle_devolucion DROP COLUMN IF EXISTS descuento_unitario;
ALTER TABLE __SCHEMA__.t_detalle_devolucion DROP COLUMN IF EXISTS precio_unitario;
ALTER TABLE __SCHEMA__.t_detalle_devolucion DROP COLUMN IF EXISTS condicion;

-- 4. Revertir Columnas en t_devolucion
ALTER TABLE __SCHEMA__.t_devolucion DROP COLUMN IF EXISTS updated_at;
ALTER TABLE __SCHEMA__.t_devolucion DROP COLUMN IF EXISTS fecha_reembolso;
ALTER TABLE __SCHEMA__.t_devolucion DROP COLUMN IF EXISTS referencia_reembolso;
ALTER TABLE __SCHEMA__.t_devolucion DROP COLUMN IF EXISTS metodo_reembolso;
ALTER TABLE __SCHEMA__.t_devolucion DROP COLUMN IF EXISTS observaciones_resolucion;
ALTER TABLE __SCHEMA__.t_devolucion DROP COLUMN IF EXISTS fecha_resolucion;
ALTER TABLE __SCHEMA__.t_devolucion DROP COLUMN IF EXISTS id_usuario_revisor;
ALTER TABLE __SCHEMA__.t_devolucion DROP COLUMN IF EXISTS evidencia_url;
ALTER TABLE __SCHEMA__.t_devolucion DROP COLUMN IF EXISTS descripcion_cliente;
ALTER TABLE __SCHEMA__.t_devolucion DROP COLUMN IF EXISTS tipo_devolucion;
ALTER TABLE __SCHEMA__.t_devolucion DROP COLUMN IF EXISTS id_sucursal;
ALTER TABLE __SCHEMA__.t_devolucion DROP COLUMN IF EXISTS id_empresa;
ALTER TABLE __SCHEMA__.t_devolucion DROP COLUMN IF EXISTS codigo_devolucion;

