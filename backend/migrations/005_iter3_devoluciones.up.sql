-- ============================================================================
-- AuroraStore Iteración 3 — Migración 005 (UP): Gestión de Devoluciones (CU24W / CU25W)
-- Propósito: Extensión no destructiva de t_devolucion y t_detalle_devolucion,
--            adición de campos de auditoría, resolución, recepción de prendas
--            (revendible vs defectuoso) y liquidación de reembolsos.
-- Reversibilidad: 005_iter3_devoluciones.down.sql
-- ============================================================================

-- 1. Extensión de t_devolucion
ALTER TABLE __SCHEMA__.t_devolucion ADD COLUMN IF NOT EXISTS codigo_devolucion VARCHAR(50);
ALTER TABLE __SCHEMA__.t_devolucion ADD COLUMN IF NOT EXISTS id_empresa INTEGER REFERENCES __SCHEMA__.empresa(id_empresa);
ALTER TABLE __SCHEMA__.t_devolucion ADD COLUMN IF NOT EXISTS id_sucursal INTEGER REFERENCES __SCHEMA__.t_sucursal(id_sucursal);
ALTER TABLE __SCHEMA__.t_devolucion ADD COLUMN IF NOT EXISTS tipo_devolucion VARCHAR(30) DEFAULT 'SOLICITUD_CLIENTE';
ALTER TABLE __SCHEMA__.t_devolucion ADD COLUMN IF NOT EXISTS descripcion_cliente TEXT;
ALTER TABLE __SCHEMA__.t_devolucion ADD COLUMN IF NOT EXISTS evidencia_url TEXT;
ALTER TABLE __SCHEMA__.t_devolucion ADD COLUMN IF NOT EXISTS id_usuario_revisor INTEGER REFERENCES __SCHEMA__.t_usuario(id_usuario);
ALTER TABLE __SCHEMA__.t_devolucion ADD COLUMN IF NOT EXISTS fecha_resolucion TIMESTAMP;
ALTER TABLE __SCHEMA__.t_devolucion ADD COLUMN IF NOT EXISTS observaciones_resolucion TEXT;
ALTER TABLE __SCHEMA__.t_devolucion ADD COLUMN IF NOT EXISTS metodo_reembolso VARCHAR(50);
ALTER TABLE __SCHEMA__.t_devolucion ADD COLUMN IF NOT EXISTS referencia_reembolso VARCHAR(150);
ALTER TABLE __SCHEMA__.t_devolucion ADD COLUMN IF NOT EXISTS fecha_reembolso TIMESTAMP;
ALTER TABLE __SCHEMA__.t_devolucion ADD COLUMN IF NOT EXISTS updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP;

-- 2. Extensión de t_detalle_devolucion
ALTER TABLE __SCHEMA__.t_detalle_devolucion ADD COLUMN IF NOT EXISTS condicion VARCHAR(30) DEFAULT 'REVENDIBLE';
ALTER TABLE __SCHEMA__.t_detalle_devolucion ADD COLUMN IF NOT EXISTS precio_unitario NUMERIC(10,2);
ALTER TABLE __SCHEMA__.t_detalle_devolucion ADD COLUMN IF NOT EXISTS descuento_unitario NUMERIC(10,2) DEFAULT 0;
ALTER TABLE __SCHEMA__.t_detalle_devolucion ADD COLUMN IF NOT EXISTS monto_reembolso NUMERIC(10,2);
ALTER TABLE __SCHEMA__.t_detalle_devolucion ADD COLUMN IF NOT EXISTS estado_item VARCHAR(30) DEFAULT 'SOLICITADO';

-- 3. Índices de Rendimiento para Búsquedas y Aislamiento por Tenant
CREATE INDEX IF NOT EXISTS idx_devolucion_empresa_estado
    ON __SCHEMA__.t_devolucion (id_empresa, estado, fecha_devolucion DESC);

CREATE INDEX IF NOT EXISTS idx_devolucion_venta
    ON __SCHEMA__.t_devolucion (id_venta);

CREATE INDEX IF NOT EXISTS idx_devolucion_usuario
    ON __SCHEMA__.t_devolucion (id_usuario, fecha_devolucion DESC);

CREATE INDEX IF NOT EXISTS idx_detalle_devolucion_devolucion
    ON __SCHEMA__.t_detalle_devolucion (id_devolucion);

CREATE INDEX IF NOT EXISTS idx_detalle_devolucion_detalle_venta
    ON __SCHEMA__.t_detalle_devolucion (id_detalle_venta);

-- 4. Sembrado de Permisos Granulares RBAC para Devoluciones
INSERT INTO __SCHEMA__.t_permiso (codigo, nombre, descripcion, modulo, activo)
VALUES 
    ('devoluciones.ver', 'Ver devoluciones', 'Permite consultar solicitudes e historial de devoluciones', 'ventas', true),
    ('devoluciones.solicitar', 'Solicitar devolución', 'Permite a clientes solicitar devoluciones de compras', 'ventas', true),
    ('devoluciones.crear_presencial', 'Registrar devolución presencial', 'Permite registrar devoluciones en mostrador POS', 'ventas', true),
    ('devoluciones.revisar', 'Revisar devoluciones', 'Permite inspeccionar y dictaminar solicitudes', 'ventas', true),
    ('devoluciones.aprobar_rechazar', 'Aprobar o rechazar devoluciones', 'Permite resolver y aprobar solicitudes', 'ventas', true),
    ('devoluciones.recibir', 'Recibir prendas de devolución', 'Permite registrar recepción física y ajustar inventario', 'ventas', true),
    ('devoluciones.reembolsar', 'Registrar reembolso', 'Permite liquidar y asentar el reembolso económico', 'ventas', true)
ON CONFLICT (codigo) DO UPDATE 
SET nombre = EXCLUDED.nombre, descripcion = EXCLUDED.descripcion, modulo = EXCLUDED.modulo, activo = true;

-- 5. Asignación de Permisos a Roles por Nombre
-- A. ADMINISTRADOR -> TODOS los permisos de devoluciones
INSERT INTO __SCHEMA__.t_rol_permiso (id_rol, id_permiso)
SELECT r.id_rol, p.id_permiso
FROM __SCHEMA__.t_rol r, __SCHEMA__.t_permiso p
WHERE r.nombre = 'ADMINISTRADOR' AND p.codigo LIKE 'devoluciones.%'
ON CONFLICT (id_rol, id_permiso) DO NOTHING;

-- B. ADMINISTRADOR_TIENDA
INSERT INTO __SCHEMA__.t_rol_permiso (id_rol, id_permiso)
SELECT r.id_rol, p.id_permiso
FROM __SCHEMA__.t_rol r, __SCHEMA__.t_permiso p
WHERE r.nombre = 'ADMINISTRADOR_TIENDA' AND p.codigo IN (
    'devoluciones.ver',
    'devoluciones.crear_presencial',
    'devoluciones.revisar',
    'devoluciones.aprobar_rechazar',
    'devoluciones.recibir',
    'devoluciones.reembolsar'
)
ON CONFLICT (id_rol, id_permiso) DO NOTHING;

-- C. ENCARGADO_SUCURSAL
INSERT INTO __SCHEMA__.t_rol_permiso (id_rol, id_permiso)
SELECT r.id_rol, p.id_permiso
FROM __SCHEMA__.t_rol r, __SCHEMA__.t_permiso p
WHERE r.nombre = 'ENCARGADO_SUCURSAL' AND p.codigo IN (
    'devoluciones.ver',
    'devoluciones.crear_presencial',
    'devoluciones.revisar',
    'devoluciones.aprobar_rechazar',
    'devoluciones.recibir',
    'devoluciones.reembolsar'
)
ON CONFLICT (id_rol, id_permiso) DO NOTHING;

-- D. CAJERO
INSERT INTO __SCHEMA__.t_rol_permiso (id_rol, id_permiso)
SELECT r.id_rol, p.id_permiso
FROM __SCHEMA__.t_rol r, __SCHEMA__.t_permiso p
WHERE r.nombre = 'CAJERO' AND p.codigo IN (
    'devoluciones.ver',
    'devoluciones.crear_presencial',
    'devoluciones.recibir'
)
ON CONFLICT (id_rol, id_permiso) DO NOTHING;

-- E. CLIENTE
INSERT INTO __SCHEMA__.t_rol_permiso (id_rol, id_permiso)
SELECT r.id_rol, p.id_permiso
FROM __SCHEMA__.t_rol r, __SCHEMA__.t_permiso p
WHERE r.nombre = 'CLIENTE' AND p.codigo IN (
    'devoluciones.solicitar',
    'devoluciones.ver'
)
ON CONFLICT (id_rol, id_permiso) DO NOTHING;

