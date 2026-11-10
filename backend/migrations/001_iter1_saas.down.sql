DO $$ BEGIN
    IF EXISTS (SELECT 1 FROM __SCHEMA__.t_suscripcion) THEN
        RAISE EXCEPTION 'REVERSIÓN BLOQUEADA: preservar/exportar historial SaaS antes de revertir';
    END IF;
    IF EXISTS (SELECT 1 FROM __SCHEMA__.t_usuario_permiso WHERE id_permiso IN (SELECT id_permiso FROM __SCHEMA__.iter1_permisos_creados))
    OR EXISTS (SELECT 1 FROM __SCHEMA__.t_rol_permiso rp JOIN __SCHEMA__.iter1_permisos_creados p USING(id_permiso)
        WHERE NOT EXISTS (SELECT 1 FROM __SCHEMA__.iter1_roles_permisos_creados c WHERE c.id_rol=rp.id_rol AND c.id_permiso=rp.id_permiso)) THEN
        RAISE EXCEPTION 'REVERSIÓN BLOQUEADA: existen nuevas delegaciones SaaS';
    END IF;
END $$;
DELETE FROM __SCHEMA__.t_rol_permiso rp USING __SCHEMA__.iter1_roles_permisos_creados c
    WHERE rp.id_rol=c.id_rol AND rp.id_permiso=c.id_permiso;
ALTER TABLE __SCHEMA__.iter1_permisos_creados DROP CONSTRAINT iter1_permisos_creados_id_permiso_fkey;
DELETE FROM __SCHEMA__.t_permiso WHERE id_permiso IN (SELECT id_permiso FROM __SCHEMA__.iter1_permisos_creados);
DROP TABLE __SCHEMA__.iter1_roles_permisos_creados, __SCHEMA__.iter1_permisos_creados;
DROP TRIGGER iter1_asignacion_validar ON __SCHEMA__.t_usuario_sucursal;
DROP FUNCTION __SCHEMA__.iter1_asignacion_validar();
DROP TRIGGER iter1_sucursal_validar ON __SCHEMA__.t_sucursal;
DROP FUNCTION __SCHEMA__.iter1_sucursal_validar();
DROP TABLE __SCHEMA__.t_suscripcion;
DROP FUNCTION __SCHEMA__.iter1_suscripcion_validar();
DROP TABLE __SCHEMA__.t_plan;
ALTER TABLE __SCHEMA__.t_usuario DROP CONSTRAINT iter1_usuario_empresa_fk;
ALTER TABLE __SCHEMA__.t_sucursal DROP CONSTRAINT iter1_sucursal_empresa_fk;
DROP INDEX __SCHEMA__.iter1_usuario_empresa_idx;
