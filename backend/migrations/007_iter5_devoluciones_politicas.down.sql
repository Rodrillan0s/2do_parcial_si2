-- ============================================================================
-- AuroraStore Iteración 5 — Migración 007 (DOWN): Reversión de Políticas y Créditos
-- ============================================================================

DROP TABLE IF EXISTS __SCHEMA__.t_movimiento_credito CASCADE;
DROP TABLE IF EXISTS __SCHEMA__.t_credito_cliente CASCADE;

ALTER TABLE __SCHEMA__.t_detalle_devolucion DROP COLUMN IF EXISTS destino_inventario;
ALTER TABLE __SCHEMA__.t_detalle_devolucion DROP COLUMN IF EXISTS precio_unitario_cambio;
ALTER TABLE __SCHEMA__.t_detalle_devolucion DROP COLUMN IF EXISTS cantidad_cambio;
ALTER TABLE __SCHEMA__.t_detalle_devolucion DROP COLUMN IF EXISTS id_variante_cambio;

ALTER TABLE __SCHEMA__.t_devolucion DROP COLUMN IF EXISTS excepcion_ley_453;
ALTER TABLE __SCHEMA__.t_devolucion DROP COLUMN IF EXISTS cumple_politica;
ALTER TABLE __SCHEMA__.t_devolucion DROP COLUMN IF EXISTS dias_desde_compra;
ALTER TABLE __SCHEMA__.t_devolucion DROP COLUMN IF EXISTS diferencia_cambio;
ALTER TABLE __SCHEMA__.t_devolucion DROP COLUMN IF EXISTS id_sesion_caja;
ALTER TABLE __SCHEMA__.t_devolucion DROP COLUMN IF EXISTS tipo_resolucion;

ALTER TABLE __SCHEMA__.empresa DROP COLUMN IF EXISTS politica_devolucion;

DELETE FROM __SCHEMA__.t_rol_permiso WHERE id_permiso IN (SELECT id_permiso FROM __SCHEMA__.t_permiso WHERE codigo = 'devoluciones.politicas');
DELETE FROM __SCHEMA__.t_permiso WHERE codigo = 'devoluciones.politicas';
