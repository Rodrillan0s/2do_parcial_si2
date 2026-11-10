-- ============================================================================
-- AuroraStore Iteración 6 — Migración 008 (DOWN): Reversión de Contingencia Offline POS
-- ============================================================================

DELETE FROM __SCHEMA__.t_rol_permiso 
WHERE id_permiso IN (SELECT id_permiso FROM __SCHEMA__.t_permiso WHERE codigo = 'pos.contingencia');

DELETE FROM __SCHEMA__.t_permiso WHERE codigo = 'pos.contingencia';

ALTER TABLE __SCHEMA__.t_venta DROP COLUMN IF EXISTS id_cuota_contingencia;
ALTER TABLE __SCHEMA__.t_venta DROP COLUMN IF EXISTS comprobante_tipo_provisional;
ALTER TABLE __SCHEMA__.t_venta DROP COLUMN IF EXISTS es_contingencia_offline;

DROP TABLE IF EXISTS __SCHEMA__.t_incidencia_sobreventa CASCADE;
DROP TABLE IF EXISTS __SCHEMA__.t_caja_cuota_contingencia CASCADE;

ALTER TABLE __SCHEMA__.t_inventario DROP COLUMN IF EXISTS cuota_manual_contingencia;
ALTER TABLE __SCHEMA__.t_inventario DROP COLUMN IF EXISTS stock_contingencia;

ALTER TABLE __SCHEMA__.empresa DROP COLUMN IF EXISTS politica_contingencia_pos;
