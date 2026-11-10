-- Requires 003. Keep its checksum intact. No automatic assignment of legacy hashes.
ALTER TABLE __SCHEMA__.t_sync_operacion
    ADD COLUMN request_hash VARCHAR(64);

ALTER TABLE __SCHEMA__.t_sync_operacion
    ADD CONSTRAINT ck_sync_request_hash
    CHECK (request_hash IS NULL OR request_hash ~ '^[0-9a-f]{64}$');

-- Unknown operations from the old memory-only deployment cannot be proven safe
-- to execute again. Retain a durable cutover boundary for reconciliation.
CREATE TABLE __SCHEMA__.t_sync_control (
    id SMALLINT PRIMARY KEY CHECK (id = 1),
    inicio_garantia TIMESTAMPTZ NOT NULL DEFAULT clock_timestamp()
);
INSERT INTO __SCHEMA__.t_sync_control (id) VALUES (1);

-- Durable receipts must survive deletion of a user or tenant. Explicit archival
-- and reconciliation are required before deleting referenced identities.
ALTER TABLE __SCHEMA__.t_sync_operacion
    DROP CONSTRAINT t_sync_operacion_id_usuario_fkey,
    DROP CONSTRAINT t_sync_operacion_id_empresa_fkey,
    ADD CONSTRAINT t_sync_operacion_id_usuario_fkey FOREIGN KEY (id_usuario)
        REFERENCES __SCHEMA__.t_usuario(id_usuario) ON DELETE RESTRICT,
    ADD CONSTRAINT t_sync_operacion_id_empresa_fkey FOREIGN KEY (id_empresa)
        REFERENCES __SCHEMA__.empresa(id_empresa) ON DELETE RESTRICT;
