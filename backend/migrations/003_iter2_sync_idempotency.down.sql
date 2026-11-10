-- ============================================================================
-- AuroraStore Iteración 2 — Migración 003 (DOWN): Reversión de tabla de idempotencia
-- ============================================================================

DROP INDEX IF EXISTS __SCHEMA__.idx_iter2_sync_op_empresa_fecha;
DROP TABLE IF EXISTS __SCHEMA__.t_sync_operacion;

