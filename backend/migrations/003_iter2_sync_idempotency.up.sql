-- ============================================================================
-- AuroraStore Iteración 2 — Migración 003 (UP): Registro Idempotente de Operaciones PWA/Móvil
-- Propósito: Almacenar claves de idempotencia (operation_id UUID) por usuario y tenant
--            para evitar que reintentos de red dupliquen efectos en carrito o reservas.
-- Reversibilidad: 003_iter2_sync_idempotency.down.sql
-- ============================================================================

CREATE TABLE IF NOT EXISTS __SCHEMA__.t_sync_operacion (
    operation_id VARCHAR(64) NOT NULL,
    id_usuario INTEGER NOT NULL REFERENCES __SCHEMA__.t_usuario(id_usuario) ON DELETE CASCADE,
    id_empresa INTEGER NOT NULL REFERENCES __SCHEMA__.empresa(id_empresa) ON DELETE CASCADE,
    kind VARCHAR(40) NOT NULL,
    status VARCHAR(24) NOT NULL,
    http_status INTEGER NOT NULL DEFAULT 200,
    conflict_code VARCHAR(40),
    response_json JSONB NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    PRIMARY KEY (id_usuario, id_empresa, operation_id)
);

CREATE INDEX IF NOT EXISTS idx_iter2_sync_op_empresa_fecha
    ON __SCHEMA__.t_sync_operacion (id_empresa, created_at DESC);

