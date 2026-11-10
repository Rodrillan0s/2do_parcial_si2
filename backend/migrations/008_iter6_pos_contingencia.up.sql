-- ============================================================================
-- AuroraStore Iteración 6 — Migración 008 (UP): Estrategia de Contingencia Offline POS
-- Propósito:
--   1. Añadir stock_contingencia y cuota_manual_contingencia a t_inventario.
--   2. Añadir politica_contingencia_pos JSONB a empresa.
--   3. Crear t_caja_cuota_contingencia para preasignación transaccional por sesión de caja.
--   4. Crear t_incidencia_sobreventa para auditoría y resolución centralizada.
--   5. Extender t_venta con es_contingencia_offline y comprobante_tipo_provisional.
--   6. Sembrar permiso RBAC pos.contingencia.
-- Reversibilidad: 008_iter6_pos_contingencia.down.sql
-- ============================================================================

-- 1. Política de contingencia en empresa
ALTER TABLE __SCHEMA__.empresa
ADD COLUMN IF NOT EXISTS politica_contingencia_pos JSONB NOT NULL DEFAULT '{
    "habilitado": true,
    "modo": "PORCENTAJE",
    "porcentaje_defecto": 15.0,
    "cantidad_fija_defecto": 2,
    "minimo_unidades": 1,
    "maximo_unidades": 10,
    "permitir_sobreventa_con_incidencia": true,
    "solo_efectivo_offline": true
}'::jsonb;

-- 2. Extensión de t_inventario para aislamiento de contingencia
ALTER TABLE __SCHEMA__.t_inventario
ADD COLUMN IF NOT EXISTS stock_contingencia INTEGER NOT NULL DEFAULT 0 CHECK (stock_contingencia >= 0);

ALTER TABLE __SCHEMA__.t_inventario
ADD COLUMN IF NOT EXISTS cuota_manual_contingencia INTEGER DEFAULT NULL CHECK (cuota_manual_contingencia IS NULL OR cuota_manual_contingencia >= 0);

CREATE INDEX IF NOT EXISTS idx_inventario_contingencia
    ON __SCHEMA__.t_inventario (id_sucursal, stock_contingencia)
    WHERE stock_contingencia > 0;

-- 3. Tabla de cuotas preasignadas por sesión de caja
CREATE TABLE IF NOT EXISTS __SCHEMA__.t_caja_cuota_contingencia (
    id_cuota BIGSERIAL PRIMARY KEY,
    id_empresa INTEGER NOT NULL REFERENCES __SCHEMA__.empresa(id_empresa),
    id_sucursal INTEGER NOT NULL REFERENCES __SCHEMA__.t_sucursal(id_sucursal),
    id_caja INTEGER NOT NULL REFERENCES __SCHEMA__.t_caja(id_caja),
    id_sesion_caja INTEGER NOT NULL REFERENCES __SCHEMA__.t_caja_sesion(id_sesion_caja),
    id_variante INTEGER NOT NULL REFERENCES __SCHEMA__.t_producto_talla_color(id_variante),
    cuota_asignada INTEGER NOT NULL CHECK (cuota_asignada >= 0),
    cuota_consumida INTEGER NOT NULL DEFAULT 0 CHECK (cuota_consumida <= cuota_asignada),
    estado VARCHAR(30) NOT NULL DEFAULT 'ACTIVA' CHECK (estado IN ('ACTIVA', 'CONCILIADA', 'LIBERADA')),
    fecha_asignacion TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    fecha_conciliacion TIMESTAMPTZ,
    CONSTRAINT uq_sesion_caja_variante UNIQUE (id_sesion_caja, id_variante)
);

CREATE INDEX IF NOT EXISTS idx_cuota_contingencia_sesion
    ON __SCHEMA__.t_caja_cuota_contingencia (id_sesion_caja, estado);

CREATE INDEX IF NOT EXISTS idx_cuota_contingencia_variante_sucursal
    ON __SCHEMA__.t_caja_cuota_contingencia (id_sucursal, id_variante, estado);

-- 4. Tabla de incidencias de sobreventa y conciliación centralizada
CREATE TABLE IF NOT EXISTS __SCHEMA__.t_incidencia_sobreventa (
    id_incidencia BIGSERIAL PRIMARY KEY,
    id_empresa INTEGER NOT NULL REFERENCES __SCHEMA__.empresa(id_empresa),
    id_sucursal INTEGER NOT NULL REFERENCES __SCHEMA__.t_sucursal(id_sucursal),
    id_venta_pos INTEGER REFERENCES __SCHEMA__.t_venta(id_venta),
    id_variante INTEGER NOT NULL REFERENCES __SCHEMA__.t_producto_talla_color(id_variante),
    cantidad_solicitada INTEGER NOT NULL CHECK (cantidad_solicitada > 0),
    stock_fisico_disponible INTEGER NOT NULL DEFAULT 0,
    estado VARCHAR(40) NOT NULL DEFAULT 'PENDIENTE_CONCILIACION'
        CHECK (estado IN ('PENDIENTE_CONCILIACION', 'REASIGNADA_SUCURSAL', 'REEMBOLSADA_ONLINE', 'AJUSTADA_INVENTARIO', 'RESUELTA')),
    resolucion_tipo VARCHAR(40),
    observaciones TEXT,
    creado_por INTEGER REFERENCES __SCHEMA__.t_usuario(id_usuario),
    creado_en TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    resuelto_por INTEGER REFERENCES __SCHEMA__.t_usuario(id_usuario),
    resuelto_en TIMESTAMPTZ
);

CREATE INDEX IF NOT EXISTS idx_incidencia_sobreventa_empresa_estado
    ON __SCHEMA__.t_incidencia_sobreventa (id_empresa, estado, creado_en DESC);

-- 5. Extensión de t_venta para comprobantes provisionales de contingencia
ALTER TABLE __SCHEMA__.t_venta
ADD COLUMN IF NOT EXISTS es_contingencia_offline BOOLEAN NOT NULL DEFAULT FALSE;

ALTER TABLE __SCHEMA__.t_venta
ADD COLUMN IF NOT EXISTS comprobante_tipo_provisional VARCHAR(50) DEFAULT NULL;

ALTER TABLE __SCHEMA__.t_venta
ADD COLUMN IF NOT EXISTS id_cuota_contingencia BIGINT REFERENCES __SCHEMA__.t_caja_cuota_contingencia(id_cuota);

-- 6. Sembrado de permiso RBAC pos.contingencia
INSERT INTO __SCHEMA__.t_permiso (codigo, nombre, descripcion, modulo, activo)
VALUES
    ('pos.contingencia', 'Gestionar contingencia offline POS', 'Permite configurar cuotas de contingencia de inventario y resolver incidencias de sobreventa', 'ventas', true)
ON CONFLICT (codigo) DO UPDATE
SET nombre = EXCLUDED.nombre,
    descripcion = EXCLUDED.descripcion,
    modulo = EXCLUDED.modulo,
    activo = true;

-- Asignar a administradores y encargados de empresa
INSERT INTO __SCHEMA__.t_rol_permiso (id_rol, id_permiso)
SELECT r.id_rol, p.id_permiso
FROM __SCHEMA__.t_rol r
CROSS JOIN __SCHEMA__.t_permiso p
WHERE p.codigo = 'pos.contingencia'
  AND UPPER(r.nombre) IN ('ADMINISTRADOR', 'ADMIN_EMPRESA', 'ADMINISTRADOR_EMPRESA', 'ENCARGADO')
ON CONFLICT DO NOTHING;
