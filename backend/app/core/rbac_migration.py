import logging
from app.core.postgres import PostgreSQL
from app.core.config import Config

logger = logging.getLogger(__name__)

def ejecutar_migracion_rbac():
    db = PostgreSQL()
    db.create_connection()
    if not db.conn:
        print("❌ No se pudo conectar a la base de datos para ejecutar la migración RBAC.")
        return False

    schema = Config.SCHEMA or 'comercio'

    try:
        # 1. Crear tablas si no existen y asegurar columnas necesarias en esquemas preexistentes
        sql_crear_tablas = f"""
        -- Tabla de Empresa / Tenant
        CREATE TABLE IF NOT EXISTS {schema}.empresa (
            id_empresa SERIAL PRIMARY KEY,
            nombre_empresa VARCHAR(150) NOT NULL,
            nit VARCHAR(50),
            estado VARCHAR(20) DEFAULT 'ACTIVO',
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );
        ALTER TABLE {schema}.empresa ADD COLUMN IF NOT EXISTS nit VARCHAR(50);
        ALTER TABLE {schema}.empresa ADD COLUMN IF NOT EXISTS estado VARCHAR(20) DEFAULT 'ACTIVO';
        ALTER TABLE {schema}.empresa ADD COLUMN IF NOT EXISTS created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP;

        -- Asegurar columna id_empresa en t_usuario
        ALTER TABLE {schema}.t_usuario ADD COLUMN IF NOT EXISTS id_empresa INT;

        -- Tabla de Roles
        CREATE TABLE IF NOT EXISTS {schema}.t_rol (
            id_rol SERIAL PRIMARY KEY,
            nombre VARCHAR(100) UNIQUE NOT NULL,
            descripcion TEXT,
            activo BOOLEAN DEFAULT TRUE,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );
        ALTER TABLE {schema}.t_rol ADD COLUMN IF NOT EXISTS descripcion TEXT;
        ALTER TABLE {schema}.t_rol ADD COLUMN IF NOT EXISTS activo BOOLEAN DEFAULT TRUE;
        ALTER TABLE {schema}.t_rol ADD COLUMN IF NOT EXISTS created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP;

        -- Tabla de Permisos
        CREATE TABLE IF NOT EXISTS {schema}.t_permiso (
            id_permiso SERIAL PRIMARY KEY,
            codigo VARCHAR(100) UNIQUE NOT NULL,
            nombre VARCHAR(150) NOT NULL,
            descripcion TEXT,
            modulo VARCHAR(100) NOT NULL,
            activo BOOLEAN DEFAULT TRUE,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );
        ALTER TABLE {schema}.t_permiso ADD COLUMN IF NOT EXISTS descripcion TEXT;
        ALTER TABLE {schema}.t_permiso ADD COLUMN IF NOT EXISTS modulo VARCHAR(100) DEFAULT 'general';
        ALTER TABLE {schema}.t_permiso ADD COLUMN IF NOT EXISTS activo BOOLEAN DEFAULT TRUE;
        ALTER TABLE {schema}.t_permiso ADD COLUMN IF NOT EXISTS created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP;

        -- Tabla de Relación Usuario-Rol (M:N)
        CREATE TABLE IF NOT EXISTS {schema}.t_usuario_rol (
            id_usuario INT NOT NULL REFERENCES {schema}.t_usuario(id_usuario) ON DELETE CASCADE,
            id_rol INT NOT NULL REFERENCES {schema}.t_rol(id_rol) ON DELETE CASCADE,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            PRIMARY KEY (id_usuario, id_rol)
        );
        ALTER TABLE {schema}.t_usuario_rol ADD COLUMN IF NOT EXISTS created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP;

        -- Tabla de Relación Rol-Permiso (M:N)
        CREATE TABLE IF NOT EXISTS {schema}.t_rol_permiso (
            id_rol INT NOT NULL REFERENCES {schema}.t_rol(id_rol) ON DELETE CASCADE,
            id_permiso INT NOT NULL REFERENCES {schema}.t_permiso(id_permiso) ON DELETE CASCADE,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            PRIMARY KEY (id_rol, id_permiso)
        );
        ALTER TABLE {schema}.t_rol_permiso ADD COLUMN IF NOT EXISTS created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP;

        -- Tabla de Sucursales
        CREATE TABLE IF NOT EXISTS {schema}.t_sucursal (
            id_sucursal SERIAL PRIMARY KEY,
            nombre VARCHAR(150) NOT NULL,
            direccion TEXT,
            id_empresa INT REFERENCES {schema}.empresa(id_empresa) ON DELETE CASCADE,
            activo BOOLEAN DEFAULT TRUE,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );
        ALTER TABLE {schema}.t_sucursal ADD COLUMN IF NOT EXISTS direccion TEXT;
        ALTER TABLE {schema}.t_sucursal ADD COLUMN IF NOT EXISTS id_empresa INT;
        ALTER TABLE {schema}.t_sucursal ADD COLUMN IF NOT EXISTS activo BOOLEAN DEFAULT TRUE;
        ALTER TABLE {schema}.t_sucursal ADD COLUMN IF NOT EXISTS created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP;

        -- Tabla de Alcance Usuario-Sucursal (M:N)
        CREATE TABLE IF NOT EXISTS {schema}.t_usuario_sucursal (
            id_usuario INT NOT NULL REFERENCES {schema}.t_usuario(id_usuario) ON DELETE CASCADE,
            id_sucursal INT NOT NULL REFERENCES {schema}.t_sucursal(id_sucursal) ON DELETE CASCADE,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            PRIMARY KEY (id_usuario, id_sucursal)
        );
        ALTER TABLE {schema}.t_usuario_sucursal ADD COLUMN IF NOT EXISTS created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP;
        -- Tabla de Bitácora del Sistema
        CREATE TABLE IF NOT EXISTS {schema}.t_bitacora (
            id_bitacora BIGSERIAL PRIMARY KEY,
            fecha_hora TIMESTAMPTZ NOT NULL DEFAULT NOW(),
            id_usuario INT REFERENCES {schema}.t_usuario(id_usuario) ON DELETE SET NULL,
            usuario_nombre VARCHAR(150),
            usuario_email VARCHAR(150),
            id_empresa INT REFERENCES {schema}.empresa(id_empresa) ON DELETE SET NULL,
            id_sucursal INT REFERENCES {schema}.t_sucursal(id_sucursal) ON DELETE SET NULL,
            modulo VARCHAR(100) NOT NULL,
            accion VARCHAR(150) NOT NULL,
            entidad VARCHAR(150),
            id_entidad VARCHAR(100),
            descripcion TEXT,
            resultado VARCHAR(20) NOT NULL CHECK (resultado IN ('EXITO', 'ERROR')),
            nivel VARCHAR(20) NOT NULL CHECK (nivel IN ('INFO', 'WARNING', 'CRITICAL')),
            ip VARCHAR(50),
            user_agent TEXT,
            datos_anteriores JSONB,
            datos_nuevos JSONB,
            metadatos JSONB,
            request_id VARCHAR(100)
        );
        
        ALTER TABLE {schema}.t_bitacora ADD COLUMN IF NOT EXISTS fecha_hora TIMESTAMPTZ DEFAULT NOW();
        ALTER TABLE {schema}.t_bitacora ADD COLUMN IF NOT EXISTS id_usuario INT;
        ALTER TABLE {schema}.t_bitacora ADD COLUMN IF NOT EXISTS usuario_nombre VARCHAR(150);
        ALTER TABLE {schema}.t_bitacora ADD COLUMN IF NOT EXISTS usuario_email VARCHAR(150);
        ALTER TABLE {schema}.t_bitacora ADD COLUMN IF NOT EXISTS id_empresa INT;
        ALTER TABLE {schema}.t_bitacora ADD COLUMN IF NOT EXISTS id_sucursal INT;
        ALTER TABLE {schema}.t_bitacora ADD COLUMN IF NOT EXISTS modulo VARCHAR(100) DEFAULT 'GENERAL';
        ALTER TABLE {schema}.t_bitacora ADD COLUMN IF NOT EXISTS accion VARCHAR(150) DEFAULT 'ACCION';
        ALTER TABLE {schema}.t_bitacora ADD COLUMN IF NOT EXISTS entidad VARCHAR(150);
        ALTER TABLE {schema}.t_bitacora ADD COLUMN IF NOT EXISTS id_entidad VARCHAR(100);
        ALTER TABLE {schema}.t_bitacora ADD COLUMN IF NOT EXISTS descripcion TEXT;
        ALTER TABLE {schema}.t_bitacora ADD COLUMN IF NOT EXISTS resultado VARCHAR(20) DEFAULT 'EXITO';
        ALTER TABLE {schema}.t_bitacora ADD COLUMN IF NOT EXISTS nivel VARCHAR(20) DEFAULT 'INFO';
        ALTER TABLE {schema}.t_bitacora ADD COLUMN IF NOT EXISTS user_agent TEXT;
        ALTER TABLE {schema}.t_bitacora ADD COLUMN IF NOT EXISTS ip VARCHAR(50);
        ALTER TABLE {schema}.t_bitacora ADD COLUMN IF NOT EXISTS datos_anteriores JSONB;
        ALTER TABLE {schema}.t_bitacora ADD COLUMN IF NOT EXISTS datos_nuevos JSONB;
        ALTER TABLE {schema}.t_bitacora ADD COLUMN IF NOT EXISTS metadatos JSONB;
        ALTER TABLE {schema}.t_bitacora ADD COLUMN IF NOT EXISTS request_id VARCHAR(100);

        CREATE INDEX IF NOT EXISTS idx_bitacora_fecha ON {schema}.t_bitacora(fecha_hora DESC);
        CREATE INDEX IF NOT EXISTS idx_bitacora_usuario ON {schema}.t_bitacora(id_usuario);
        CREATE INDEX IF NOT EXISTS idx_bitacora_empresa ON {schema}.t_bitacora(id_empresa);
        CREATE INDEX IF NOT EXISTS idx_bitacora_sucursal ON {schema}.t_bitacora(id_sucursal);
        CREATE INDEX IF NOT EXISTS idx_bitacora_modulo ON {schema}.t_bitacora(modulo);
        CREATE INDEX IF NOT EXISTS idx_bitacora_accion ON {schema}.t_bitacora(accion);
        CREATE INDEX IF NOT EXISTS idx_bitacora_resultado ON {schema}.t_bitacora(resultado);

        """
        db.execute_query(sql_crear_tablas, commit=True)

        # Limpieza de roles heredados antiguos
        db.execute_query(f"UPDATE {schema}.t_rol SET nombre = 'ADMINISTRADOR_TIENDA', descripcion = 'Administrador general de la tienda y catálogo de productos.' WHERE LOWER(nombre) IN ('gerente taller', 'gerente_taller', 'gerente');", commit=True)
        db.execute_query(f"UPDATE {schema}.t_rol SET nombre = 'ENCARGADO_SUCURSAL', descripcion = 'Supervisión y gestión operativa de sucursal.' WHERE LOWER(nombre) IN ('mecanico', 'mecánico', 'tecnico');", commit=True)

        # 2. Seed de Roles Iniciales (Utiliza SELECT para verificar existencia sin requerir UNIQUE constraint)
        roles_seed = [
            ('ADMINISTRADOR', 'Administrador global del sistema con todos los privilegios.'),
            ('CLIENTE', 'Cliente comprador de la plataforma e-commerce.'),
            ('ADMINISTRADOR_TIENDA', 'Administrador general de la tienda y catálogo de productos.'),
            ('ENCARGADO_SUCURSAL', 'Supervisión y gestión operativa de sucursal.'),
            ('CAJERO', 'Atención de caja y creación de ventas en punto de venta.'),
            ('PROVEEDOR', 'Proveedor externo de bienes y servicios.')
        ]

        for nombre_rol, desc in roles_seed:
            res_rol = db.execute_query(f"SELECT id_rol FROM {schema}.t_rol WHERE LOWER(nombre) = LOWER(%s);", (nombre_rol,), fetchone=True)
            if not res_rol:
                db.execute_query(f"INSERT INTO {schema}.t_rol (nombre, descripcion) VALUES (%s, %s);", (nombre_rol, desc), commit=True)
            else:
                db.execute_query(f"UPDATE {schema}.t_rol SET nombre = %s, descripcion = %s WHERE id_rol = %s;", (nombre_rol, desc, res_rol[0]), commit=True)

        # 3. Seed de Permisos Iniciales (<recurso>.<accion>)
        permisos_seed = [
            # Productos
            ('productos.ver', 'Ver catálogo de productos', 'Permite consultar el catálogo y detalle de productos', 'productos'),
            ('productos.crear', 'Crear producto', 'Permite registrar nuevos productos en el catálogo', 'productos'),
            ('productos.editar', 'Editar producto', 'Permite modificar detalles de productos existentes', 'productos'),
            ('productos.eliminar', 'Eliminar producto', 'Permite eliminar o desactivar productos', 'productos'),
            ('productos.cambiar_precio', 'Cambiar precio de productos', 'Permite modificar precios de lista y descuentos', 'productos'),

            # Ventas
            ('ventas.ver', 'Ver ventas', 'Permite consultar el historial de ventas y pedidos', 'ventas'),
            ('ventas.crear', 'Crear venta', 'Permite procesar compras y generar ventas', 'ventas'),
            ('ventas.editar', 'Editar venta', 'Permite modificar pedidos o ventas en proceso', 'ventas'),
            ('ventas.anular', 'Anular venta', 'Permite cancelar o anular ventas procesadas', 'ventas'),

            # Compras
            ('compras.ver', 'Ver compras', 'Permite consultar órdenes de compra a proveedores', 'compras'),
            ('compras.crear', 'Crear compra', 'Permite registrar órdenes de compra e inventario', 'compras'),

            # Reportes
            ('reportes.ver', 'Ver reportes', 'Permite visualizar dashboards y estadísticas', 'reportes'),
            ('reportes.exportar', 'Exportar reportes', 'Permite descargar reportes en CSV/Excel/PDF', 'reportes'),

            # Usuarios
            ('usuarios.ver', 'Ver usuarios', 'Permite listar los usuarios registrados', 'usuarios'),
            ('usuarios.crear', 'Crear usuario', 'Permite registrar nuevos usuarios en el sistema', 'usuarios'),
            ('usuarios.editar', 'Editar usuario', 'Permite actualizar datos de usuarios', 'usuarios'),
            ('usuarios.desactivar', 'Desactivar usuario', 'Permite bloquear o desactivar usuarios', 'usuarios'),

            # Roles y Permisos
            ('roles.ver', 'Ver roles', 'Permite consultar el catálogo de roles', 'roles'),
            ('roles.crear', 'Crear rol', 'Permite definir nuevos roles en el sistema', 'roles'),
            ('roles.editar', 'Editar rol', 'Permite modificar roles existentes', 'roles'),
            ('roles.eliminar', 'Eliminar rol', 'Permite desactivar roles existentes', 'roles'),
            ('sucursales.ver', 'Ver sucursales', 'Permite consultar sucursales autorizadas', 'sucursales'),
            ('sucursales.crear', 'Crear sucursal', 'Permite registrar nuevas sucursales', 'sucursales'),
            ('sucursales.editar', 'Editar sucursal', 'Permite modificar sucursales existentes', 'sucursales'),
            ('sucursales.desactivar', 'Desactivar sucursal', 'Permite desactivar sucursales existentes', 'sucursales'),
            # Acceso General
            ('tienda.acceder', 'Acceso a tienda e-commerce', 'Permite navegar y comprar en la tienda', 'acceso'),
            ('admin.acceder', 'Acceso al panel administrativo', 'Permite ingresar al dashboard administrativo', 'acceso'),
            ('bitacora.ver', 'Ver bitácora del sistema', 'Permite consultar la bitácora de auditoría', 'bitacora'),

            # Inventario (W22 - CU22)
            ('inventario.ver', 'Ver inventario', 'Permite consultar niveles de stock, variantes y movimientos de inventario', 'inventario'),
            ('inventario.gestionar', 'Gestionar inventario', 'Permite registrar entradas, salidas y ajustes de inventario', 'inventario'),
        ]

        for codigo, nombre, desc, modulo in permisos_seed:
            res_p = db.execute_query(f"SELECT id_permiso FROM {schema}.t_permiso WHERE LOWER(codigo) = LOWER(%s);", (codigo,), fetchone=True)
            if not res_p:
                db.execute_query(f"INSERT INTO {schema}.t_permiso (codigo, nombre, descripcion, modulo) VALUES (%s, %s, %s, %s);", (codigo, nombre, desc, modulo), commit=True)
            else:
                db.execute_query(f"UPDATE {schema}.t_permiso SET nombre = %s, descripcion = %s, modulo = %s WHERE id_permiso = %s;", (nombre, desc, modulo, res_p[0]), commit=True)

        # 4. Asignación inicial de Permisos a Roles en t_rol_permiso sin ON CONFLICT
        # A. ADMINISTRADOR -> TODOS los permisos
        db.execute_query(f"""
            INSERT INTO {schema}.t_rol_permiso (id_rol, id_permiso)
            SELECT r.id_rol, p.id_permiso
            FROM {schema}.t_rol r, {schema}.t_permiso p
            WHERE UPPER(r.nombre) = 'ADMINISTRADOR'
            AND NOT EXISTS (
                SELECT 1 FROM {schema}.t_rol_permiso rp 
                WHERE rp.id_rol = r.id_rol AND rp.id_permiso = p.id_permiso
            );
        """, commit=True)

        # B. CLIENTE -> tienda.acceder, productos.ver, ventas.crear
        codigos_cliente = ['tienda.acceder', 'productos.ver', 'ventas.crear']
        db.execute_query(f"""
            INSERT INTO {schema}.t_rol_permiso (id_rol, id_permiso)
            SELECT r.id_rol, p.id_permiso
            FROM {schema}.t_rol r
            JOIN {schema}.t_permiso p ON p.codigo = ANY(%s)
            WHERE UPPER(r.nombre) = 'CLIENTE'
            AND NOT EXISTS (
                SELECT 1 FROM {schema}.t_rol_permiso rp 
                WHERE rp.id_rol = r.id_rol AND rp.id_permiso = p.id_permiso
            );
        """, (codigos_cliente,), commit=True)

        # C. CAJERO -> admin.acceder, tienda.acceder, productos.ver, ventas.ver, ventas.crear
        codigos_cajero = ['admin.acceder', 'tienda.acceder', 'productos.ver', 'ventas.ver', 'ventas.crear']
        db.execute_query(f"""
            INSERT INTO {schema}.t_rol_permiso (id_rol, id_permiso)
            SELECT r.id_rol, p.id_permiso
            FROM {schema}.t_rol r
            JOIN {schema}.t_permiso p ON p.codigo = ANY(%s)
            WHERE UPPER(r.nombre) = 'CAJERO'
            AND NOT EXISTS (
                SELECT 1 FROM {schema}.t_rol_permiso rp 
                WHERE rp.id_rol = r.id_rol AND rp.id_permiso = p.id_permiso
            );
        """, (codigos_cajero,), commit=True)

        # D. ENCARGADO_SUCURSAL
        codigos_encargado = ['admin.acceder', 'tienda.acceder', 'productos.ver', 'ventas.ver', 'ventas.crear', 'ventas.editar', 'ventas.anular', 'reportes.ver', 'sucursales.ver', 'usuarios.ver', 'bitacora.ver', 'inventario.ver', 'inventario.gestionar']
        db.execute_query(f"""
            INSERT INTO {schema}.t_rol_permiso (id_rol, id_permiso)
            SELECT r.id_rol, p.id_permiso
            FROM {schema}.t_rol r
            JOIN {schema}.t_permiso p ON p.codigo = ANY(%s)
            WHERE UPPER(r.nombre) = 'ENCARGADO_SUCURSAL'
            AND NOT EXISTS (
                SELECT 1 FROM {schema}.t_rol_permiso rp 
                WHERE rp.id_rol = r.id_rol AND rp.id_permiso = p.id_permiso
            );
        """, (codigos_encargado,), commit=True)

        # E. ADMINISTRADOR_TIENDA
        codigos_admin_tienda = ['admin.acceder', 'tienda.acceder', 'productos.ver', 'productos.crear', 'productos.editar', 'productos.eliminar', 'productos.cambiar_precio', 'ventas.ver', 'reportes.ver', 'reportes.exportar', 'usuarios.ver', 'usuarios.crear', 'usuarios.editar', 'usuarios.desactivar', 'roles.ver', 'sucursales.ver', 'sucursales.crear', 'sucursales.editar', 'sucursales.activar', 'sucursales.desactivar', 'sucursales.asignar', 'bitacora.ver', 'inventario.ver', 'inventario.gestionar']
        db.execute_query(f"""
            INSERT INTO {schema}.t_rol_permiso (id_rol, id_permiso)
            SELECT r.id_rol, p.id_permiso
            FROM {schema}.t_rol r
            JOIN {schema}.t_permiso p ON p.codigo = ANY(%s)
            WHERE UPPER(r.nombre) = 'ADMINISTRADOR_TIENDA'
            AND NOT EXISTS (
                SELECT 1 FROM {schema}.t_rol_permiso rp 
                WHERE rp.id_rol = r.id_rol AND rp.id_permiso = p.id_permiso
            );
        """, (codigos_admin_tienda,), commit=True)

        # F. PROVEEDOR
        codigos_proveedor = ['tienda.acceder', 'productos.ver', 'compras.ver', 'compras.crear']
        db.execute_query(f"""
            INSERT INTO {schema}.t_rol_permiso (id_rol, id_permiso)
            SELECT r.id_rol, p.id_permiso
            FROM {schema}.t_rol r
            JOIN {schema}.t_permiso p ON p.codigo = ANY(%s)
            WHERE UPPER(r.nombre) = 'PROVEEDOR'
            AND NOT EXISTS (
                SELECT 1 FROM {schema}.t_rol_permiso rp 
                WHERE rp.id_rol = r.id_rol AND rp.id_permiso = p.id_permiso
            );
        """, (codigos_proveedor,), commit=True)

        # 5. Migración de usuarios existentes de t_usuario.id_rol a t_usuario_rol
        db.execute_query(f"""
            INSERT INTO {schema}.t_usuario_rol (id_usuario, id_rol)
            SELECT id_usuario, id_rol 
            FROM {schema}.t_usuario 
            WHERE id_rol IS NOT NULL
            AND NOT EXISTS (
                SELECT 1 FROM {schema}.t_usuario_rol ur 
                WHERE ur.id_usuario = {schema}.t_usuario.id_usuario AND ur.id_rol = {schema}.t_usuario.id_rol
            );
        """, commit=True)

        # 6. Seed de Sucursal por defecto si no existen sucursales
        db.execute_query(f"""
            INSERT INTO {schema}.t_sucursal (nombre, direccion)
            SELECT 'Sucursal Principal - Aura Atelier', 'Av. Equipetrol #100, Santa Cruz'
            WHERE NOT EXISTS (SELECT 1 FROM {schema}.t_sucursal);
        """, commit=True)

        return True

    except Exception as e:
        if db.conn:
            db.conn.rollback()
        raise
    finally:
        db.close_connection()

if __name__ == "__main__":
    ejecutar_migracion_rbac()
