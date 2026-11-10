-- ============================================================================
-- AuroraStore Iteración 4 — Migración 006 (UP): Storefront Multitenant & Contratación SaaS Autónoma
-- Propósito:
--   1. Añadir slug único y configuracion_storefront JSONB controlado a comercio.empresa.
--   2. Añadir precio_mensual, precio_anual, moneda, descripcion y beneficios a comercio.t_plan.
--   3. Crear comercio.t_solicitud_contratacion para gestionar el registro autónomo,
--      verificación criptográfica de correo (hash + expiración + un solo uso),
--      pago por pasarela PayPal o QR/Transferencia con comprobante, y auditoría de activación.
--   4. Sembrar permiso RBAC storefront.configurar para ADMINISTRADOR_TIENDA y ADMINISTRADOR.
-- Reversibilidad: 006_iter4_saas_storefront.down.sql
-- ============================================================================

-- 1. Extensión de comercio.empresa para resolución multitenant y tema configurable
ALTER TABLE __SCHEMA__.empresa ADD COLUMN IF NOT EXISTS slug VARCHAR(80);
ALTER TABLE __SCHEMA__.empresa ADD COLUMN IF NOT EXISTS configuracion_storefront JSONB NOT NULL DEFAULT '{}'::jsonb;

-- Sembrar slugs limpios para empresas existentes sin alterar su estado ni datos
UPDATE __SCHEMA__.empresa
SET slug = LOWER(REGEXP_REPLACE(TRIM(nombre_empresa), '[^a-zA-Z0-9]+', '-', 'g'))
WHERE slug IS NULL AND nombre_empresa IS NOT NULL;

CREATE UNIQUE INDEX IF NOT EXISTS idx_empresa_slug_unique
    ON __SCHEMA__.empresa (LOWER(slug))
    WHERE slug IS NOT NULL;

-- 2. Extensión de comercio.t_plan con precios, moneda, periodicidad y beneficios reales
ALTER TABLE __SCHEMA__.t_plan ADD COLUMN IF NOT EXISTS precio_mensual NUMERIC(10,2) NOT NULL DEFAULT 199.00;
ALTER TABLE __SCHEMA__.t_plan ADD COLUMN IF NOT EXISTS precio_anual NUMERIC(10,2) NOT NULL DEFAULT 1990.00;
ALTER TABLE __SCHEMA__.t_plan ADD COLUMN IF NOT EXISTS moneda VARCHAR(10) NOT NULL DEFAULT 'BOB';
ALTER TABLE __SCHEMA__.t_plan ADD COLUMN IF NOT EXISTS descripcion TEXT;
ALTER TABLE __SCHEMA__.t_plan ADD COLUMN IF NOT EXISTS beneficios JSONB NOT NULL DEFAULT '[]'::jsonb;

UPDATE __SCHEMA__.t_plan
SET precio_mensual = 199.00,
    precio_anual = 1990.00,
    moneda = 'BOB',
    descripcion = 'Ideal para tiendas y boutiques en crecimiento que operan hasta 2 sucursales activas con tienda online personalizable.',
    beneficios = '["Storefront multitenant personalizable (logo, colores, tipografía, banners)", "Catálogo multi-público (Mujer, Hombre, Unisex, Infantil, Bebés)", "Hasta 2 sucursales físicas activas con stock en tiempo real", "Carrito, checkout, reservas en tienda y gestión de devoluciones", "Panel administrativo con POS y control de acceso por roles (RBAC)"]'::jsonb
WHERE codigo = 'BASICO';

UPDATE __SCHEMA__.t_plan
SET precio_mensual = 399.00,
    precio_anual = 3990.00,
    moneda = 'BOB',
    descripcion = 'Para marcas y cadenas multitienda que requieren hasta 10 sucursales activas, motor generativo de reportes e inteligencia comercial.',
    beneficios = '["Todo lo incluido en el Plan Básico", "Hasta 10 sucursales físicas activas simultáneas", "Motor Dinámico y Generativo de Reportes con exportación PDF/Excel", "Asistente IA y motor de recomendaciones basado en preferencias", "Soporte prioritario y analítica multi-sucursal avanzada"]'::jsonb
WHERE codigo = 'PROFESIONAL';

-- 3. Tabla de Solicitudes de Contratación SaaS Autónoma
CREATE TABLE IF NOT EXISTS __SCHEMA__.t_solicitud_contratacion (
    id_solicitud BIGSERIAL PRIMARY KEY,
    codigo_seguimiento VARCHAR(40) UNIQUE NOT NULL,
    id_empresa INTEGER NOT NULL REFERENCES __SCHEMA__.empresa(id_empresa),
    id_usuario_propietario INTEGER NOT NULL REFERENCES __SCHEMA__.t_usuario(id_usuario),
    codigo_plan VARCHAR(20) NOT NULL REFERENCES __SCHEMA__.t_plan(codigo),
    periodicidad VARCHAR(20) NOT NULL DEFAULT 'MENSUAL' CHECK (periodicidad IN ('MENSUAL', 'ANUAL')),
    monto NUMERIC(10,2) NOT NULL CHECK (monto > 0),
    moneda VARCHAR(10) NOT NULL DEFAULT 'BOB',
    estado_contratacion VARCHAR(40) NOT NULL DEFAULT 'PENDIENTE_VERIFICACION_CORREO'
        CHECK (estado_contratacion IN (
            'PENDIENTE_VERIFICACION_CORREO',
            'PENDIENTE_PAGO',
            'PENDIENTE_VERIFICACION_PAGO',
            'ACTIVA',
            'RECHAZADO',
            'CANCELADA'
        )),
    token_verificacion_hash VARCHAR(128),
    token_expira_en TIMESTAMPTZ,
    token_usado_en TIMESTAMPTZ,
    correo_verificado BOOLEAN NOT NULL DEFAULT FALSE,
    metodo_pago VARCHAR(30) CHECK (metodo_pago IS NULL OR metodo_pago IN ('PAYPAL', 'QR_TRANSFERENCIA')),
    referencia_pago VARCHAR(150),
    paypal_order_id VARCHAR(120),
    comprobante_url TEXT,
    id_suscripcion_generada BIGINT REFERENCES __SCHEMA__.t_suscripcion(id_suscripcion),
    revisado_por INTEGER REFERENCES __SCHEMA__.t_usuario(id_usuario),
    revisado_en TIMESTAMPTZ,
    observaciones_revision TEXT,
    creado_en TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    actualizado_en TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_solicitud_contratacion_empresa
    ON __SCHEMA__.t_solicitud_contratacion (id_empresa, creado_en DESC);

CREATE INDEX IF NOT EXISTS idx_solicitud_contratacion_estado
    ON __SCHEMA__.t_solicitud_contratacion (estado_contratacion, creado_en DESC);

CREATE INDEX IF NOT EXISTS idx_solicitud_contratacion_token
    ON __SCHEMA__.t_solicitud_contratacion (token_verificacion_hash)
    WHERE token_verificacion_hash IS NOT NULL;

-- 4. Sembrado de Permisos para Configuración de Storefront y Contratación
INSERT INTO __SCHEMA__.t_permiso (codigo, nombre, descripcion, modulo, activo)
VALUES
    ('storefront.configurar', 'Configurar storefront de la tienda', 'Permite personalizar identidad visual, públicos, colecciones y secciones del storefront de la empresa', 'SAAS', true),
    ('contrataciones.gestionar', 'Gestionar contrataciones SaaS', 'Permite verificar comprobantes de pago y aprobar o rechazar contrataciones pendientes en la plataforma', 'SAAS', true)
ON CONFLICT (codigo) DO UPDATE
SET nombre = EXCLUDED.nombre,
    descripcion = EXCLUDED.descripcion,
    modulo = EXCLUDED.modulo,
    activo = true;

-- Asignar ambos permisos a ADMINISTRADOR (SuperAdmin de plataforma)
INSERT INTO __SCHEMA__.t_rol_permiso (id_rol, id_permiso)
SELECT r.id_rol, p.id_permiso
FROM __SCHEMA__.t_rol r, __SCHEMA__.t_permiso p
WHERE r.nombre IN ('ADMINISTRADOR', 'SUPERADMIN')
  AND p.codigo IN ('storefront.configurar', 'contrataciones.gestionar')
ON CONFLICT (id_rol, id_permiso) DO NOTHING;

-- Asignar storefront.configurar, planes.ver y suscripciones.ver a ADMINISTRADOR_TIENDA
INSERT INTO __SCHEMA__.t_rol_permiso (id_rol, id_permiso)
SELECT r.id_rol, p.id_permiso
FROM __SCHEMA__.t_rol r, __SCHEMA__.t_permiso p
WHERE r.nombre = 'ADMINISTRADOR_TIENDA'
  AND p.codigo IN ('storefront.configurar', 'planes.ver', 'suscripciones.ver')
ON CONFLICT (id_rol, id_permiso) DO NOTHING;
