-- Minimal P1 contract fixture, NOT a replacement schema or production bootstrap.
CREATE TABLE empresa(id_empresa SERIAL PRIMARY KEY,nombre_empresa TEXT NOT NULL,estado TEXT DEFAULT 'ACTIVO',updated_at TIMESTAMP DEFAULT now());
CREATE TABLE t_rol(id_rol SERIAL PRIMARY KEY,nombre TEXT UNIQUE,descripcion TEXT,activo BOOLEAN DEFAULT TRUE,created_at TIMESTAMP DEFAULT now());
CREATE TABLE t_permiso(id_permiso SERIAL PRIMARY KEY,codigo TEXT UNIQUE,nombre TEXT,descripcion TEXT,modulo TEXT,activo BOOLEAN DEFAULT TRUE,created_at TIMESTAMP DEFAULT now());
CREATE TABLE t_usuario(id_usuario SERIAL PRIMARY KEY,id_empresa INTEGER,id_rol INTEGER,username TEXT UNIQUE,correo TEXT,password_hash TEXT,nombre TEXT,apellido TEXT,telefono TEXT,estado BOOLEAN DEFAULT TRUE,direccion TEXT,ciudad TEXT,fecha_registro TIMESTAMP DEFAULT now());
CREATE TABLE t_rol_permiso(id_rol INTEGER REFERENCES t_rol,id_permiso INTEGER REFERENCES t_permiso,PRIMARY KEY(id_rol,id_permiso));
CREATE TABLE t_usuario_rol(id_usuario INTEGER REFERENCES t_usuario,id_rol INTEGER REFERENCES t_rol,PRIMARY KEY(id_usuario,id_rol));
CREATE TABLE t_usuario_permiso(id_usuario INTEGER REFERENCES t_usuario,id_permiso INTEGER REFERENCES t_permiso,activo BOOLEAN DEFAULT TRUE,created_at TIMESTAMP DEFAULT now(),PRIMARY KEY(id_usuario,id_permiso));
CREATE TABLE t_ciudad(id_ciudad SERIAL PRIMARY KEY,nombre TEXT,departamento TEXT,activo BOOLEAN DEFAULT TRUE);
CREATE TABLE t_sucursal(id_sucursal SERIAL PRIMARY KEY,id_empresa INTEGER,activo BOOLEAN DEFAULT TRUE,estado BOOLEAN DEFAULT TRUE,nombre TEXT,direccion TEXT,telefono TEXT,id_ciudad INTEGER,codigo_sucursal TEXT,latitud NUMERIC,longitud NUMERIC,created_at TIMESTAMP DEFAULT now());
CREATE TABLE t_usuario_sucursal(id_usuario INTEGER REFERENCES t_usuario,id_sucursal INTEGER REFERENCES t_sucursal,created_at TIMESTAMP DEFAULT now(),PRIMARY KEY(id_usuario,id_sucursal));
CREATE TABLE t_empleado(id_empleado SERIAL PRIMARY KEY,id_usuario INTEGER,id_sucursal INTEGER,codigo_empleado TEXT,cargo TEXT,fecha_contratacion DATE,estado BOOLEAN);
CREATE TABLE t_caja(id_caja SERIAL PRIMARY KEY,id_sucursal INTEGER,id_empresa INTEGER,codigo_caja TEXT,nombre TEXT,estado TEXT);
CREATE TABLE t_bitacora(id_bitacora SERIAL PRIMARY KEY,id_usuario INTEGER,id_empresa INTEGER,id_sucursal INTEGER,modulo TEXT,accion TEXT,entidad TEXT,resultado TEXT,nivel TEXT,descripcion TEXT,datos_nuevos JSONB,datos_anteriores JSONB,metadatos JSONB,fecha_hora TIMESTAMP DEFAULT now(),usuario_nombre TEXT,usuario_email TEXT,id_entidad TEXT,ip TEXT,user_agent TEXT,request_id TEXT);
INSERT INTO empresa VALUES (1,'Empresa A','ACTIVO',now()),(2,'Empresa B','ACTIVO',now());
-- Deliberately non-P1 role IDs to detect authorization by hardcoded IDs.
INSERT INTO t_rol(id_rol,nombre) VALUES(101,'ADMINISTRADOR'),(103,'ADMINISTRADOR_TIENDA'),(105,'CAJERO'),(102,'CLIENTE');
INSERT INTO t_usuario(id_usuario,username,id_empresa,id_rol,nombre,apellido) VALUES
    (1,'platform',NULL,101,'Platform','Admin'),(2,'admin_a',1,103,'Admin','A'),
    (3,'employee_a',1,105,'Employee','A'),(4,'employee_b',2,105,'Employee','B'),(5,'client',NULL,102,'Client','Global');
INSERT INTO t_usuario_rol VALUES(1,101),(2,103),(3,105),(4,105),(5,102);
INSERT INTO t_ciudad VALUES(1,'Ciudad','Departamento',TRUE);
INSERT INTO t_sucursal(id_sucursal,id_empresa,nombre,id_ciudad) VALUES(1,1,'A1',1),(2,2,'B1',1);
INSERT INTO t_usuario_sucursal VALUES(3,1,now()),(4,2,now());
INSERT INTO t_permiso(codigo,nombre,activo) VALUES
    ('usuarios.ver','Ver usuarios',TRUE),('usuarios.crear','Crear usuarios',TRUE),('usuarios.editar','Editar usuarios',TRUE),
    ('sucursales.ver','Ver sucursales',TRUE),('sucursales.asignar','Asignar sucursales',TRUE),('reportes.ver','Ver reportes',TRUE),
    ('permisos.asignar','Delegar permisos',TRUE),('permisos.ver','Ver permisos',TRUE),('ventas.crear','Vender',TRUE);
INSERT INTO t_rol_permiso SELECT 103,id_permiso FROM t_permiso;
INSERT INTO t_rol_permiso SELECT 105,id_permiso FROM t_permiso WHERE codigo IN ('sucursales.ver','reportes.ver','ventas.crear');
SELECT setval(pg_get_serial_sequence('t_usuario','id_usuario'),10);
SELECT setval(pg_get_serial_sequence('t_sucursal','id_sucursal'),10);
