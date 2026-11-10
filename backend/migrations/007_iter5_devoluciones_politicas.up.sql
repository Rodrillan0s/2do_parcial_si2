-- ============================================================================
-- AuroraStore Iteración 5 — Migración 007 (UP): Políticas de Devolución,
-- Resolución Triple (Cambio, Saldo a Favor, Reembolso) y Conciliación Financiera
-- Propósito:
--   1. Añadir política de devoluciones configurable por tenant a comercio.empresa (Ley 453 Bolivia).
--   2. Extender t_devolucion y t_detalle_devolucion para soportar los 3 resultados:
--      CAMBIO_PRENDA, SALDO_A_FAVOR, REEMBOLSO_DINERO y egreso de caja física.
--   3. Crear t_credito_cliente y t_movimiento_credito para gestión de saldo a favor en tienda.
-- Reversibilidad: 007_iter5_devoluciones_politicas.down.sql
-- ============================================================================

-- 1. Política de devolución en comercio.empresa
ALTER TABLE __SCHEMA__.empresa 
ADD COLUMN IF NOT EXISTS politica_devolucion JSONB NOT NULL DEFAULT '{
    "dias_limite_cambio": 15,
    "dias_limite_defecto": 90,
    "permite_cambio": true,
    "permite_saldo_favor": true,
    "permite_reembolso": true,
    "requiere_etiqueta_cambio": true,
    "requiere_empaque_original": false,
    "descripcion_politica": "Cambios de talla y modelo permitidos dentro de los 15 días posteriores a la compra con etiquetas intactas. Defectos de fabricación amparados legalmente hasta 90 días conforme a la Ley 453 de Defensa del Consumidor sin requerir etiquetas originales."
}'::jsonb;

-- 2. Extensión de t_devolucion para triple resolución y políticas
ALTER TABLE __SCHEMA__.t_devolucion 
ADD COLUMN IF NOT EXISTS tipo_resolucion VARCHAR(30) DEFAULT 'REEMBOLSO_DINERO';

ALTER TABLE __SCHEMA__.t_devolucion 
ADD COLUMN IF NOT EXISTS id_sesion_caja INTEGER REFERENCES __SCHEMA__.t_caja_sesion(id_sesion_caja);

ALTER TABLE __SCHEMA__.t_devolucion 
ADD COLUMN IF NOT EXISTS diferencia_cambio NUMERIC(10,2) DEFAULT 0.00;

ALTER TABLE __SCHEMA__.t_devolucion 
ADD COLUMN IF NOT EXISTS dias_desde_compra INTEGER;

ALTER TABLE __SCHEMA__.t_devolucion 
ADD COLUMN IF NOT EXISTS cumple_politica BOOLEAN DEFAULT TRUE;

ALTER TABLE __SCHEMA__.t_devolucion 
ADD COLUMN IF NOT EXISTS excepcion_ley_453 BOOLEAN DEFAULT FALSE;

-- 3. Extensión de t_detalle_devolucion para prendas de cambio y destino de inventario
ALTER TABLE __SCHEMA__.t_detalle_devolucion 
ADD COLUMN IF NOT EXISTS id_variante_cambio INTEGER REFERENCES __SCHEMA__.t_producto_talla_color(id_variante);

ALTER TABLE __SCHEMA__.t_detalle_devolucion 
ADD COLUMN IF NOT EXISTS cantidad_cambio INTEGER DEFAULT 0;

ALTER TABLE __SCHEMA__.t_detalle_devolucion 
ADD COLUMN IF NOT EXISTS precio_unitario_cambio NUMERIC(10,2) DEFAULT 0.00;

ALTER TABLE __SCHEMA__.t_detalle_devolucion 
ADD COLUMN IF NOT EXISTS destino_inventario VARCHAR(30) DEFAULT 'STOCK_DISPONIBLE';

-- 4. Tablas para Saldo a Favor / Crédito en Tienda Multitenant
CREATE TABLE IF NOT EXISTS __SCHEMA__.t_credito_cliente (
    id_credito SERIAL PRIMARY KEY,
    id_cliente INTEGER NOT NULL REFERENCES __SCHEMA__.t_cliente(id_cliente),
    id_empresa INTEGER NOT NULL REFERENCES __SCHEMA__.empresa(id_empresa),
    id_devolucion INTEGER REFERENCES __SCHEMA__.t_devolucion(id_devolucion),
    codigo_credito VARCHAR(50) NOT NULL UNIQUE,
    monto_inicial NUMERIC(10,2) NOT NULL CHECK (monto_inicial > 0),
    saldo_disponible NUMERIC(10,2) NOT NULL CHECK (saldo_disponible >= 0),
    fecha_emision TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    fecha_expiracion TIMESTAMP,
    estado VARCHAR(20) NOT NULL DEFAULT 'ACTIVO',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_credito_cliente_tenant
    ON __SCHEMA__.t_credito_cliente (id_cliente, id_empresa, estado);

CREATE TABLE IF NOT EXISTS __SCHEMA__.t_movimiento_credito (
    id_movimiento_credito SERIAL PRIMARY KEY,
    id_credito INTEGER NOT NULL REFERENCES __SCHEMA__.t_credito_cliente(id_credito),
    tipo_movimiento VARCHAR(30) NOT NULL,
    monto NUMERIC(10,2) NOT NULL,
    saldo_anterior NUMERIC(10,2) NOT NULL,
    saldo_nuevo NUMERIC(10,2) NOT NULL,
    id_venta INTEGER REFERENCES __SCHEMA__.t_venta(id_venta),
    id_usuario INTEGER REFERENCES __SCHEMA__.t_usuario(id_usuario),
    fecha TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    motivo TEXT
);

CREATE INDEX IF NOT EXISTS idx_movimiento_credito_id
    ON __SCHEMA__.t_movimiento_credito (id_credito, fecha DESC);

-- 5. Sembrar permiso de configuración de políticas de devolución
INSERT INTO __SCHEMA__.t_permiso (codigo, nombre, descripcion, modulo, activo)
VALUES 
    ('devoluciones.politicas', 'Gestionar políticas de devolución', 'Permite configurar plazos y reglas de devolución por empresa', 'ventas', true)
ON CONFLICT (codigo) DO UPDATE 
SET nombre = EXCLUDED.nombre, descripcion = EXCLUDED.descripcion, modulo = EXCLUDED.modulo, activo = true;

INSERT INTO __SCHEMA__.t_rol_permiso (id_rol, id_permiso)
SELECT r.id_rol, p.id_permiso
FROM __SCHEMA__.t_rol r, __SCHEMA__.t_permiso p
WHERE r.nombre IN ('ADMINISTRADOR', 'ADMINISTRADOR_TIENDA') AND p.codigo = 'devoluciones.politicas'
ON CONFLICT (id_rol, id_permiso) DO NOTHING;
