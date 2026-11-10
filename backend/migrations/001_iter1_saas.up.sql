-- Explicit migration. __SCHEMA__ is validated/quoted by migrate.py.
-- No automatic subscription/backfill or destructive repair of P1 data.
CREATE TABLE __SCHEMA__.t_plan (
    codigo VARCHAR(20) PRIMARY KEY CHECK (codigo IN ('BASICO', 'PROFESIONAL')),
    nombre VARCHAR(80) NOT NULL,
    max_sucursales INTEGER NOT NULL,
    reportes_generativos BOOLEAN NOT NULL,
    activo BOOLEAN NOT NULL DEFAULT TRUE,
    CHECK ((codigo = 'BASICO' AND max_sucursales = 2 AND NOT reportes_generativos)
        OR (codigo = 'PROFESIONAL' AND max_sucursales = 10 AND reportes_generativos))
);
INSERT INTO __SCHEMA__.t_plan VALUES
    ('BASICO', 'Básico', 2, FALSE, TRUE),
    ('PROFESIONAL', 'Profesional', 10, TRUE, TRUE);

CREATE TABLE __SCHEMA__.t_suscripcion (
    id_suscripcion BIGSERIAL PRIMARY KEY,
    id_empresa INTEGER NOT NULL REFERENCES __SCHEMA__.empresa(id_empresa),
    codigo_plan VARCHAR(20) NOT NULL REFERENCES __SCHEMA__.t_plan(codigo),
    inicio TIMESTAMPTZ NOT NULL,
    fin TIMESTAMPTZ NOT NULL CHECK (fin > inicio),
    estado VARCHAR(20) NOT NULL DEFAULT 'ACTIVA' CHECK (estado IN ('ACTIVA', 'CANCELADA')),
    motivo TEXT NOT NULL CHECK (length(trim(motivo)) BETWEEN 3 AND 500),
    creado_por INTEGER NOT NULL REFERENCES __SCHEMA__.t_usuario(id_usuario),
    creado_en TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP
);
CREATE INDEX idx_suscripcion_empresa_periodo ON __SCHEMA__.t_suscripcion(id_empresa, inicio, fin) WHERE estado = 'ACTIVA';

-- Fail on dirty legacy references; never repair/delete rows automatically.
ALTER TABLE __SCHEMA__.t_usuario ADD CONSTRAINT iter1_usuario_empresa_fk
    FOREIGN KEY (id_empresa) REFERENCES __SCHEMA__.empresa(id_empresa) NOT VALID;
ALTER TABLE __SCHEMA__.t_usuario VALIDATE CONSTRAINT iter1_usuario_empresa_fk;
ALTER TABLE __SCHEMA__.t_sucursal ADD CONSTRAINT iter1_sucursal_empresa_fk
    FOREIGN KEY (id_empresa) REFERENCES __SCHEMA__.empresa(id_empresa) NOT VALID;
ALTER TABLE __SCHEMA__.t_sucursal VALIDATE CONSTRAINT iter1_sucursal_empresa_fk;
CREATE INDEX iter1_usuario_empresa_idx ON __SCHEMA__.t_usuario(id_empresa);

CREATE FUNCTION __SCHEMA__.iter1_suscripcion_validar() RETURNS trigger LANGUAGE plpgsql AS $$
DECLARE limite INTEGER; usadas INTEGER;
BEGIN
    PERFORM 1 FROM __SCHEMA__.empresa WHERE id_empresa = NEW.id_empresa FOR UPDATE;
    IF TG_OP = 'UPDATE' AND (NEW.id_empresa, NEW.codigo_plan, NEW.inicio, NEW.fin, NEW.motivo, NEW.creado_por)
        IS DISTINCT FROM (OLD.id_empresa, OLD.codigo_plan, OLD.inicio, OLD.fin, OLD.motivo, OLD.creado_por) THEN
        RAISE EXCEPTION 'SUSCRIPCION_INMUTABLE' USING ERRCODE='23514';
    END IF;
    IF NEW.estado = 'ACTIVA' THEN
        IF EXISTS (SELECT 1 FROM __SCHEMA__.t_suscripcion s
            WHERE s.id_empresa = NEW.id_empresa AND s.estado = 'ACTIVA'
            AND s.id_suscripcion <> NEW.id_suscripcion
            AND s.inicio < NEW.fin AND NEW.inicio < s.fin) THEN
            RAISE EXCEPTION 'PERIODO_SOLAPADO' USING ERRCODE='23514';
        END IF;
        SELECT max_sucursales INTO limite FROM __SCHEMA__.t_plan WHERE codigo = NEW.codigo_plan AND activo;
        IF limite IS NULL THEN RAISE EXCEPTION 'PLAN_INACTIVO' USING ERRCODE='23514'; END IF;
        SELECT COUNT(*) INTO usadas FROM __SCHEMA__.t_sucursal WHERE id_empresa=NEW.id_empresa AND COALESCE(activo,estado,FALSE);
        IF usadas > limite THEN RAISE EXCEPTION 'LIMITE_SUCURSALES' USING ERRCODE='23514'; END IF;
    END IF;
    RETURN NEW;
END $$;
CREATE TRIGGER iter1_suscripcion_validar BEFORE INSERT OR UPDATE ON __SCHEMA__.t_suscripcion
    FOR EACH ROW EXECUTE FUNCTION __SCHEMA__.iter1_suscripcion_validar();

CREATE FUNCTION __SCHEMA__.iter1_sucursal_validar() RETURNS trigger LANGUAGE plpgsql AS $$
DECLARE limite INTEGER; usadas INTEGER;
BEGIN
    IF TG_OP = 'UPDATE' AND NEW.id_empresa IS DISTINCT FROM OLD.id_empresa THEN
        RAISE EXCEPTION 'TRASLADO_EMPRESA_NO_PERMITIDO' USING ERRCODE='23514';
    END IF;
    IF COALESCE(NEW.activo,NEW.estado,FALSE) AND
       (TG_OP = 'INSERT' OR NOT COALESCE(OLD.activo,OLD.estado,FALSE)) THEN
        PERFORM 1 FROM __SCHEMA__.empresa WHERE id_empresa=NEW.id_empresa AND estado='ACTIVO' FOR UPDATE;
        IF NOT FOUND THEN RAISE EXCEPTION 'EMPRESA_INACTIVA' USING ERRCODE='23514'; END IF;
        SELECT p.max_sucursales INTO limite FROM __SCHEMA__.t_suscripcion s
            JOIN __SCHEMA__.t_plan p ON p.codigo=s.codigo_plan
            WHERE s.id_empresa=NEW.id_empresa AND s.estado='ACTIVA'
            AND s.inicio<=CURRENT_TIMESTAMP AND s.fin>CURRENT_TIMESTAMP;
        IF limite IS NULL THEN RAISE EXCEPTION 'SUSCRIPCION_NO_VIGENTE' USING ERRCODE='23514'; END IF;
        SELECT COUNT(*) INTO usadas FROM __SCHEMA__.t_sucursal
            WHERE id_empresa=NEW.id_empresa AND COALESCE(activo,estado,FALSE);
        IF usadas >= limite THEN RAISE EXCEPTION 'LIMITE_SUCURSALES' USING ERRCODE='23514'; END IF;
        -- Protect scheduled downgrades as well as the current plan.
        IF EXISTS (SELECT 1 FROM __SCHEMA__.t_suscripcion s JOIN __SCHEMA__.t_plan p ON p.codigo=s.codigo_plan
            WHERE s.id_empresa=NEW.id_empresa AND s.estado='ACTIVA' AND s.fin>CURRENT_TIMESTAMP
            AND p.max_sucursales < usadas+1) THEN
            RAISE EXCEPTION 'LIMITE_PLAN_PROGRAMADO' USING ERRCODE='23514';
        END IF;
    END IF;
    RETURN NEW;
END $$;
CREATE TRIGGER iter1_sucursal_validar BEFORE INSERT OR UPDATE ON __SCHEMA__.t_sucursal
    FOR EACH ROW EXECUTE FUNCTION __SCHEMA__.iter1_sucursal_validar();

CREATE FUNCTION __SCHEMA__.iter1_asignacion_validar() RETURNS trigger LANGUAGE plpgsql AS $$
DECLARE empresa_usuario INTEGER; empresa_sucursal INTEGER; sucursal_activa BOOLEAN;
BEGIN
    SELECT id_empresa INTO empresa_usuario FROM __SCHEMA__.t_usuario WHERE id_usuario=NEW.id_usuario FOR SHARE;
    SELECT id_empresa, COALESCE(activo,estado,FALSE) INTO empresa_sucursal,sucursal_activa
        FROM __SCHEMA__.t_sucursal WHERE id_sucursal=NEW.id_sucursal FOR SHARE;
    IF empresa_usuario IS NULL OR empresa_usuario IS DISTINCT FROM empresa_sucursal OR NOT sucursal_activa THEN
        RAISE EXCEPTION 'ASIGNACION_SUCURSAL_NO_AUTORIZADA' USING ERRCODE='23514';
    END IF;
    RETURN NEW;
END $$;
CREATE TRIGGER iter1_asignacion_validar BEFORE INSERT OR UPDATE ON __SCHEMA__.t_usuario_sucursal
    FOR EACH ROW EXECUTE FUNCTION __SCHEMA__.iter1_asignacion_validar();

-- Keep ownership of new seeds for a reversible migration without touching P1 seeds.
CREATE TABLE __SCHEMA__.iter1_permisos_creados (id_permiso INTEGER PRIMARY KEY REFERENCES __SCHEMA__.t_permiso(id_permiso));
WITH nuevos AS (
    INSERT INTO __SCHEMA__.t_permiso(codigo,nombre,descripcion,modulo,activo)
    VALUES ('planes.ver','Consultar planes','Catálogo SaaS','SAAS',TRUE),
           ('planes.gestionar','Gestionar planes','Administración de plataforma','SAAS',TRUE),
           ('suscripciones.ver','Consultar suscripciones','Plan, vigencia y límites','SAAS',TRUE),
           ('suscripciones.gestionar','Gestionar suscripciones','Asignación y renovación administrativa','SAAS',TRUE)
    ON CONFLICT (codigo) DO NOTHING RETURNING id_permiso
) INSERT INTO __SCHEMA__.iter1_permisos_creados SELECT id_permiso FROM nuevos;
CREATE TABLE __SCHEMA__.iter1_roles_permisos_creados(id_rol INTEGER NOT NULL,id_permiso INTEGER NOT NULL,PRIMARY KEY(id_rol,id_permiso));
WITH nuevos AS (
    INSERT INTO __SCHEMA__.t_rol_permiso(id_rol,id_permiso)
    SELECT r.id_rol,p.id_permiso FROM __SCHEMA__.t_rol r CROSS JOIN __SCHEMA__.t_permiso p
    WHERE p.codigo IN ('planes.ver','suscripciones.ver','planes.gestionar','suscripciones.gestionar')
      AND (r.nombre IN ('ADMINISTRADOR','SUPERADMIN') OR
          (r.nombre IN ('ADMINISTRADOR_TIENDA','ENCARGADO_SUCURSAL','CAJERO','EMPLEADO') AND p.codigo IN ('planes.ver','suscripciones.ver')))
    ON CONFLICT (id_rol,id_permiso) DO NOTHING RETURNING id_rol,id_permiso
) INSERT INTO __SCHEMA__.iter1_roles_permisos_creados SELECT * FROM nuevos;
