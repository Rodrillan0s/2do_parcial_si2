-- Stop sync writers first. Receipts and P1 business data are preserved.
DROP TABLE __SCHEMA__.t_sync_control;
ALTER TABLE __SCHEMA__.t_sync_operacion
    DROP CONSTRAINT ck_sync_request_hash,
    DROP COLUMN request_hash,
    DROP CONSTRAINT t_sync_operacion_id_usuario_fkey,
    DROP CONSTRAINT t_sync_operacion_id_empresa_fkey,
    ADD CONSTRAINT t_sync_operacion_id_usuario_fkey FOREIGN KEY (id_usuario)
        REFERENCES __SCHEMA__.t_usuario(id_usuario) ON DELETE CASCADE,
    ADD CONSTRAINT t_sync_operacion_id_empresa_fkey FOREIGN KEY (id_empresa)
        REFERENCES __SCHEMA__.empresa(id_empresa) ON DELETE CASCADE;
