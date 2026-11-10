-- ============================================================================
-- AuroraStore Iteración 4 — Migración 006 (DOWN): Revertir Storefront Multitenant & Contratación SaaS
-- ============================================================================

DELETE FROM __SCHEMA__.t_rol_permiso
WHERE id_permiso IN (
    SELECT id_permiso FROM __SCHEMA__.t_permiso
    WHERE codigo IN ('storefront.configurar', 'contrataciones.gestionar')
);

DELETE FROM __SCHEMA__.t_permiso
WHERE codigo IN ('storefront.configurar', 'contrataciones.gestionar');

DROP INDEX IF EXISTS __SCHEMA__.idx_solicitud_contratacion_token;
DROP INDEX IF EXISTS __SCHEMA__.idx_solicitud_contratacion_estado;
DROP INDEX IF EXISTS __SCHEMA__.idx_solicitud_contratacion_empresa;
DROP TABLE IF EXISTS __SCHEMA__.t_solicitud_contratacion;

ALTER TABLE __SCHEMA__.t_plan DROP COLUMN IF EXISTS beneficios;
ALTER TABLE __SCHEMA__.t_plan DROP COLUMN IF EXISTS descripcion;
ALTER TABLE __SCHEMA__.t_plan DROP COLUMN IF EXISTS moneda;
ALTER TABLE __SCHEMA__.t_plan DROP COLUMN IF EXISTS precio_anual;
ALTER TABLE __SCHEMA__.t_plan DROP COLUMN IF EXISTS precio_mensual;

DROP INDEX IF EXISTS __SCHEMA__.idx_empresa_slug_unique;
ALTER TABLE __SCHEMA__.empresa DROP COLUMN IF EXISTS configuracion_storefront;
ALTER TABLE __SCHEMA__.empresa DROP COLUMN IF EXISTS slug;
