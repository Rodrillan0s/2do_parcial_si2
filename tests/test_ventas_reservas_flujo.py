"""
Suite de Pruebas Automatizadas — Flujo Integrado de Ventas Online y Reservas de Probador
Verifica:
1. Creación atómica de pedidos online con apartado estricto de stock en t_inventario (stock_reservado += cant, stock_disponible -= cant).
2. Cancelación de pedido online con liberación atómica del stock reservado a stock_disponible.
3. Expiración automática de pedidos pendientes vencidos (+48h).
4. Expiración de citas de probador respetando tolerancia de llegada y ventana de retención en boutique.
"""
from pathlib import Path
import sys
import unittest
import uuid
from datetime import datetime, timedelta, timezone

import psycopg2
from fastapi import FastAPI
from fastapi.testclient import TestClient

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tests"))
sys.path.insert(0, str(ROOT / "backend"))

from isolated_postgres import LocalPostgres
from app.core.config import Config
from app.core.postgres import PostgreSQL, _invalidar_caches_seguridad
from app.core.security import _contexto_vigente
from app.modules.pedidos.routes import pedido_routes
from app.modules.pedidos.repos import pedido_repos
from app.modules.reservas.repos import reserva_repos
from app.modules.ecommerce.repos import carrito_repos
from app.core.tenant_guard import obtener_alcance_usuario
from migrate import render

VENTAS_RESERVAS_EXTRA_SQL = """
ALTER TABLE empresa
    ADD COLUMN IF NOT EXISTS razon_social TEXT,
    ADD COLUMN IF NOT EXISTS logo TEXT,
    ADD COLUMN IF NOT EXISTS ciudad TEXT DEFAULT 'Santa Cruz',
    ADD COLUMN IF NOT EXISTS correo TEXT,
    ADD COLUMN IF NOT EXISTS telefono TEXT,
    ADD COLUMN IF NOT EXISTS direccion_fiscal TEXT;

ALTER TABLE t_sucursal
    ADD COLUMN IF NOT EXISTS horario_apertura TIME DEFAULT '09:00:00',
    ADD COLUMN IF NOT EXISTS horario_cierre TIME DEFAULT '21:00:00';

CREATE TABLE IF NOT EXISTS t_categoria (
    id_categoria SERIAL PRIMARY KEY,
    nombre TEXT NOT NULL,
    descripcion TEXT,
    id_padre INTEGER REFERENCES t_categoria(id_categoria),
    id_empresa INTEGER NOT NULL REFERENCES empresa(id_empresa),
    activo BOOLEAN DEFAULT TRUE,
    estado BOOLEAN DEFAULT TRUE
);

CREATE TABLE IF NOT EXISTS t_talla (
    id_talla SERIAL PRIMARY KEY,
    nombre TEXT NOT NULL,
    descripcion TEXT,
    id_empresa INTEGER NOT NULL REFERENCES empresa(id_empresa),
    activo BOOLEAN DEFAULT TRUE,
    estado BOOLEAN DEFAULT TRUE
);

CREATE TABLE IF NOT EXISTS t_color (
    id_color SERIAL PRIMARY KEY,
    nombre TEXT NOT NULL,
    codigo_hex TEXT NOT NULL,
    id_empresa INTEGER NOT NULL REFERENCES empresa(id_empresa),
    activo BOOLEAN DEFAULT TRUE,
    estado BOOLEAN DEFAULT TRUE
);

CREATE TABLE IF NOT EXISTS t_producto (
    id_producto SERIAL PRIMARY KEY,
    nombre TEXT NOT NULL,
    descripcion TEXT,
    codigo_producto TEXT,
    sku TEXT,
    precio NUMERIC(12, 2) NOT NULL DEFAULT 150.00,
    costo NUMERIC(12, 2) DEFAULT 60.00,
    imagen_url TEXT,
    id_categoria INTEGER REFERENCES t_categoria(id_categoria),
    id_empresa INTEGER NOT NULL REFERENCES empresa(id_empresa),
    activo BOOLEAN DEFAULT TRUE,
    estado BOOLEAN DEFAULT TRUE
);

CREATE TABLE IF NOT EXISTS t_producto_talla_color (
    id_variante SERIAL PRIMARY KEY,
    id_producto INTEGER NOT NULL REFERENCES t_producto(id_producto),
    id_talla INTEGER NOT NULL REFERENCES t_talla(id_talla),
    id_color INTEGER NOT NULL REFERENCES t_color(id_color),
    sku TEXT,
    codigo_barras TEXT,
    precio NUMERIC(12, 2),
    activo BOOLEAN DEFAULT TRUE,
    estado BOOLEAN DEFAULT TRUE
);

CREATE TABLE IF NOT EXISTS t_producto_imagen (
    id_imagen SERIAL PRIMARY KEY,
    id_producto INTEGER NOT NULL REFERENCES t_producto(id_producto),
    imagen_url TEXT NOT NULL,
    public_id TEXT,
    es_principal BOOLEAN DEFAULT FALSE,
    orden INTEGER DEFAULT 0
);

CREATE TABLE IF NOT EXISTS t_inventario (
    id_inventario SERIAL PRIMARY KEY,
    id_sucursal INTEGER NOT NULL REFERENCES t_sucursal(id_sucursal),
    id_variante INTEGER NOT NULL REFERENCES t_producto_talla_color(id_variante),
    stock_actual INTEGER NOT NULL DEFAULT 0,
    stock_reservado INTEGER NOT NULL DEFAULT 0,
    stock_disponible INTEGER NOT NULL DEFAULT 0,
    stock_contingencia INTEGER NOT NULL DEFAULT 0,
    stock_minimo INTEGER DEFAULT 2,
    stock_maximo INTEGER DEFAULT 50,
    estado BOOLEAN DEFAULT TRUE,
    fecha_actualizacion TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS t_movimiento_inventario (
    id_movimiento SERIAL PRIMARY KEY,
    id_inventario INTEGER NOT NULL REFERENCES t_inventario(id_inventario),
    id_usuario INTEGER,
    tipo_movimiento VARCHAR(50) NOT NULL,
    cantidad INTEGER NOT NULL,
    stock_anterior INTEGER,
    stock_nuevo INTEGER,
    motivo TEXT,
    fecha_movimiento TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS t_cliente (
    id_cliente SERIAL PRIMARY KEY,
    id_usuario INTEGER NOT NULL REFERENCES t_usuario(id_usuario),
    direccion TEXT,
    telefono TEXT,
    preferencias_talla TEXT,
    creado_en TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS t_carrito (
    id_carrito SERIAL PRIMARY KEY,
    id_cliente INTEGER NOT NULL REFERENCES t_cliente(id_cliente),
    id_empresa INTEGER NOT NULL REFERENCES empresa(id_empresa),
    estado VARCHAR(50) NOT NULL DEFAULT 'ACTIVO',
    fecha_creacion TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    creado_en TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    fecha_actualizacion TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS t_detalle_carrito (
    id_detalle_carrito SERIAL PRIMARY KEY,
    id_carrito INTEGER NOT NULL REFERENCES t_carrito(id_carrito),
    id_variante INTEGER NOT NULL REFERENCES t_producto_talla_color(id_variante),
    cantidad INTEGER NOT NULL DEFAULT 1,
    precio_unitario NUMERIC(12, 2) NOT NULL DEFAULT 0,
    subtotal NUMERIC(12, 2) NOT NULL DEFAULT 0,
    creado_en TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS t_venta (
    id_venta SERIAL PRIMARY KEY,
    numero_venta VARCHAR(50) NOT NULL,
    id_empresa INTEGER NOT NULL REFERENCES empresa(id_empresa),
    id_sucursal INTEGER NOT NULL REFERENCES t_sucursal(id_sucursal),
    id_usuario INTEGER NOT NULL,
    id_cliente INTEGER,
    fecha_venta TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    subtotal NUMERIC(12, 2) NOT NULL,
    descuento NUMERIC(12, 2) DEFAULT 0,
    total NUMERIC(12, 2) NOT NULL,
    tipo_documento VARCHAR(50) DEFAULT 'NOTA_VENTA',
    estado VARCHAR(50) NOT NULL DEFAULT 'COMPLETADA',
    tipo_venta VARCHAR(50) DEFAULT 'VENTA_POS'
);

CREATE TABLE IF NOT EXISTS t_pedido (
    id_pedido SERIAL PRIMARY KEY,
    codigo_pedido VARCHAR(50) UNIQUE NOT NULL,
    id_cliente INTEGER NOT NULL REFERENCES t_cliente(id_cliente),
    id_empresa INTEGER NOT NULL REFERENCES empresa(id_empresa),
    id_sucursal INTEGER NOT NULL REFERENCES t_sucursal(id_sucursal),
    id_carrito_origen INTEGER REFERENCES t_carrito(id_carrito),
    fecha_pedido TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    fecha_actualizacion TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    estado VARCHAR(50) NOT NULL DEFAULT 'PENDIENTE_PAGO',
    estado_pago VARCHAR(50) NOT NULL DEFAULT 'PENDIENTE',
    modalidad_compra VARCHAR(50) NOT NULL DEFAULT 'RETIRO_SUCURSAL',
    nombre_contacto VARCHAR(150) NOT NULL,
    telefono_contacto VARCHAR(50) NOT NULL,
    correo_contacto VARCHAR(150),
    direccion_entrega TEXT,
    ciudad_entrega VARCHAR(100),
    notas_entrega TEXT,
    subtotal NUMERIC(12, 2) NOT NULL,
    costo_envio NUMERIC(12, 2) DEFAULT 0,
    descuento NUMERIC(12, 2) DEFAULT 0,
    total NUMERIC(12, 2) NOT NULL,
    id_venta INTEGER REFERENCES t_venta(id_venta)
);

CREATE TABLE IF NOT EXISTS t_detalle_pedido (
    id_detalle_pedido SERIAL PRIMARY KEY,
    id_pedido INTEGER NOT NULL REFERENCES t_pedido(id_pedido),
    id_variante INTEGER NOT NULL REFERENCES t_producto_talla_color(id_variante),
    cantidad INTEGER NOT NULL DEFAULT 1,
    precio_unitario NUMERIC(12, 2) NOT NULL,
    subtotal NUMERIC(12, 2) NOT NULL
);

CREATE TABLE IF NOT EXISTS t_reserva (
    id_reserva SERIAL PRIMARY KEY,
    codigo_reserva VARCHAR(50) UNIQUE NOT NULL,
    id_cliente INTEGER NOT NULL REFERENCES t_cliente(id_cliente),
    id_sucursal INTEGER NOT NULL REFERENCES t_sucursal(id_sucursal),
    fecha_reserva TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    fecha_hora_visita TIMESTAMP WITH TIME ZONE NOT NULL,
    estado VARCHAR(50) NOT NULL DEFAULT 'PENDIENTE',
    con_pago BOOLEAN DEFAULT FALSE,
    monto_pagado NUMERIC(12, 2) DEFAULT 0,
    observaciones TEXT,
    fecha_cancelacion TIMESTAMP WITH TIME ZONE,
    motivo_cancelacion TEXT
);

CREATE TABLE IF NOT EXISTS t_detalle_reserva (
    id_detalle_reserva SERIAL PRIMARY KEY,
    id_reserva INTEGER NOT NULL REFERENCES t_reserva(id_reserva),
    id_variante INTEGER NOT NULL REFERENCES t_producto_talla_color(id_variante),
    cantidad INTEGER NOT NULL DEFAULT 1,
    precio_referencial NUMERIC(12, 2) NOT NULL DEFAULT 0,
    estado_prenda VARCHAR(50) NOT NULL DEFAULT 'RESERVADA'
);

CREATE TABLE IF NOT EXISTS t_bitacora (
    id_bitacora SERIAL PRIMARY KEY,
    id_usuario INTEGER,
    usuario_nombre VARCHAR(150),
    usuario_email VARCHAR(150),
    id_empresa INTEGER,
    id_sucursal INTEGER,
    modulo VARCHAR(50) NOT NULL,
    accion VARCHAR(100) NOT NULL,
    entidad VARCHAR(50),
    id_entidad VARCHAR(50),
    descripcion TEXT,
    resultado VARCHAR(50),
    nivel VARCHAR(20),
    ip VARCHAR(50),
    user_agent TEXT,
    datos_anteriores JSONB,
    datos_nuevos JSONB,
    metadatos JSONB,
    request_id VARCHAR(50),
    fecha_evento TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);
"""

class VentasReservasFlujoTestSuite(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.cluster = LocalPostgres()
        cls.pg = cls.cluster.__enter__()

        for name, value in [
            ("DB_HOST", cls.pg.params["host"]),
            ("DB_PORT", cls.pg.params["port"]),
            ("DB_USER", "iter1_test"),
            ("DB_NAME", "postgres"),
            ("DB_PASSWORD", ""),
        ]:
            setattr(Config, name, value)

        if not Config.TOKEN_KEY and not Config.SECRET_KEY:
            Config.TOKEN_KEY = "ventas_reservas_secret_key"

        cls.schema = "ventas_res_" + uuid.uuid4().hex[:8]
        Config.SCHEMA = cls.schema
        PostgreSQL._pool = None
        _invalidar_caches_seguridad()

        with psycopg2.connect(**cls.pg.params) as conn:
            conn.autocommit = True
            with conn.cursor() as cur:
                cur.execute(f"CREATE SCHEMA {cls.schema}; SET search_path TO {cls.schema}, public")
                cur.execute(f"ALTER DATABASE postgres SET search_path TO {cls.schema}, public")
                cur.execute((ROOT / "tests/p1_fixture.sql").read_text(encoding="utf-8"))
                cur.execute(render(ROOT / "backend/migrations/001_iter1_saas.up.sql", cls.schema))
                cur.execute(VENTAS_RESERVAS_EXTRA_SQL)
                cur.execute(f"""
                    INSERT INTO {cls.schema}.t_suscripcion (id_empresa, codigo_plan, inicio, fin, motivo, creado_por)
                    VALUES (1, 'PROFESIONAL', now() - interval '1 day', now() + interval '30 days', 'Plan A', 1),
                           (2, 'PROFESIONAL', now() - interval '1 day', now() + interval '30 days', 'Plan B', 1)
                    ON CONFLICT DO NOTHING;
                """)

        app = FastAPI()
        app.include_router(pedido_routes.router)
        cls.client = TestClient(app)

    @classmethod
    def tearDownClass(cls):
        try:
            PostgreSQL().close_connection()
            PostgreSQL._pool = None
            cls.cluster.__exit__(None, None, None)
        except Exception:
            pass

    def setUp(self):
        Config.SCHEMA = self.schema
        _invalidar_caches_seguridad()

        self.conn = psycopg2.connect(**self.pg.params)
        self.conn.autocommit = True
        self.cur = self.conn.cursor()
        self.cur.execute(f"SET search_path TO {self.schema}, public;")

        self.cur.execute("""
            DELETE FROM t_detalle_pedido;
            DELETE FROM t_pedido;
            DELETE FROM t_detalle_carrito;
            DELETE FROM t_carrito;
            DELETE FROM t_detalle_reserva;
            DELETE FROM t_reserva;

            INSERT INTO t_cliente (id_cliente, id_usuario, telefono)
            VALUES (1, 3, '77012345')
            ON CONFLICT (id_cliente) DO NOTHING;

            INSERT INTO t_categoria (id_categoria, id_empresa, nombre)
            VALUES (501, 1, 'Vestidos de Gala')
            ON CONFLICT (id_categoria) DO NOTHING;

            INSERT INTO t_talla (id_talla, id_empresa, nombre)
            VALUES (601, 1, 'M')
            ON CONFLICT (id_talla) DO NOTHING;

            INSERT INTO t_color (id_color, id_empresa, nombre, codigo_hex)
            VALUES (701, 1, 'Negro Ébano', '#000000')
            ON CONFLICT (id_color) DO NOTHING;

            INSERT INTO t_producto (id_producto, id_empresa, id_categoria, nombre, codigo_producto, precio)
            VALUES (801, 1, 501, 'Vestido Seda Midnight', 'PROD-001', 350.00)
            ON CONFLICT (id_producto) DO NOTHING;

            INSERT INTO t_producto_talla_color (id_variante, id_producto, id_talla, id_color, sku, precio)
            VALUES (901, 801, 601, 701, 'SKU-VEST-M-NEG', 350.00)
            ON CONFLICT (id_variante) DO NOTHING;

            INSERT INTO t_inventario (id_inventario, id_sucursal, id_variante, stock_actual, stock_reservado, stock_disponible, stock_contingencia)
            VALUES (1001, 1, 901, 10, 0, 10, 0)
            ON CONFLICT (id_inventario) DO UPDATE
            SET stock_actual = 10, stock_reservado = 0, stock_disponible = 10, stock_contingencia = 0;
        """)

    def tearDown(self):
        self.cur.close()
        self.conn.close()

    def test_01_crear_pedido_reserva_inventario_atomicamente(self):
        """
        Al confirmar un pedido online (incluso RETIRO_SUCURSAL en PENDIENTE_PAGO),
        las existencias solicitadas se apartan inmediatamente en t_inventario:
        stock_reservado += 2, stock_disponible -= 2, stock_actual intacto.
        """
        self.cur.execute("""
            INSERT INTO t_carrito (id_carrito, id_cliente, id_empresa, estado)
            VALUES (1101, 1, 1, 'ACTIVO');
        """)
        self.cur.execute("""
            INSERT INTO t_detalle_carrito (id_detalle_carrito, id_carrito, id_variante, cantidad)
            VALUES (1201, 1101, 901, 2);
        """)

        datos_pedido = {
            "id_sucursal": 1,
            "modalidad_compra": "RETIRO_SUCURSAL",
            "nombre_contacto": "Valentina Mendoza",
            "telefono_contacto": "77012345",
            "correo_contacto": "valentina@example.com"
        }
        res = pedido_repos.validar_y_crear_pedido(id_usuario=3, id_empresa=1, datos=datos_pedido)

        self.assertIsNotNone(res)
        self.assertEqual(res["estado"], "PENDIENTE_PAGO")
        self.assertEqual(res["estado_pago"], "PENDIENTE")
        self.assertEqual(res["total"], 700.0)

        # Verificar inventario en BD
        self.cur.execute("SELECT stock_actual, stock_reservado, stock_disponible FROM t_inventario WHERE id_inventario = 1001;")
        stk_act, stk_res, stk_disp = self.cur.fetchone()
        self.assertEqual(stk_act, 10, "El stock actual no debe disminuir hasta que se pague/despache")
        self.assertEqual(stk_res, 2, "El stock reservado debe incrementarse en 2 prendas")
        self.assertEqual(stk_disp, 8, "El stock disponible debe reducirse a 8 para evitar sobreventas")

        # Verificar movimiento de inventario
        self.cur.execute("""
            SELECT tipo_movimiento, cantidad, motivo 
            FROM t_movimiento_inventario 
            WHERE id_inventario = 1001 
            ORDER BY id_movimiento DESC LIMIT 1;
        """)
        tipo, cant, motivo = self.cur.fetchone()
        self.assertEqual(tipo, "RESERVA")
        self.assertEqual(cant, 2)
        self.assertIn("Reserva de stock para pedido", motivo)

    def test_02_cancelar_pedido_libera_stock_atomicamente(self):
        """
        Al cancelar un pedido no pagado, el stock apartado se restituye a stock_disponible
        y se registra 'LIBERACION_RESERVA'.
        """
        self.cur.execute("""
            INSERT INTO t_carrito (id_carrito, id_cliente, id_empresa, estado)
            VALUES (1102, 1, 1, 'ACTIVO');
        """)
        self.cur.execute("""
            INSERT INTO t_detalle_carrito (id_detalle_carrito, id_carrito, id_variante, cantidad)
            VALUES (1202, 1102, 901, 3);
        """)

        res_crear = pedido_repos.validar_y_crear_pedido(
            id_usuario=3,
            id_empresa=1,
            datos={
                "id_sucursal": 1,
                "modalidad_compra": "RETIRO_SUCURSAL",
                "nombre_contacto": "Valentina Mendoza",
                "telefono_contacto": "77012345"
            }
        )
        id_pedido = res_crear["id_pedido"]

        # Verificar que el stock quedó en reservado=3, disponible=7
        self.cur.execute("SELECT stock_reservado, stock_disponible FROM t_inventario WHERE id_inventario = 1001;")
        res_stk, disp_stk = self.cur.fetchone()
        self.assertEqual(res_stk, 3)
        self.assertEqual(disp_stk, 7)

        # Cancelar el pedido
        res_cancel = pedido_repos.cancelar_pedido_cliente(
            id_pedido=id_pedido,
            id_usuario=3,
            id_empresa=1,
            motivo="Cambio de parecer sobre el evento"
        )
        self.assertEqual(res_cancel["estado"], "CANCELADO")

        # Verificar que el inventario fue liberado completamente
        self.cur.execute("SELECT stock_actual, stock_reservado, stock_disponible FROM t_inventario WHERE id_inventario = 1001;")
        act, res_f, disp_f = self.cur.fetchone()
        self.assertEqual(act, 10)
        self.assertEqual(res_f, 0, "Stock reservado debe volver a 0")
        self.assertEqual(disp_f, 10, "Stock disponible debe volver a 10")

        # Verificar estado del pedido en BD
        self.cur.execute("SELECT estado FROM t_pedido WHERE id_pedido = %s;", (id_pedido,))
        est_bd = self.cur.fetchone()[0]
        self.assertEqual(est_bd, "CANCELADO")

    def test_03_expirar_pedidos_vencidos_libera_stock_automaticamente(self):
        """
        Pedidos en PENDIENTE_PAGO que superen la tolerancia de 48h deben ser
        cancelados automáticamente y su inventario restaurado.
        """
        fecha_antigua = datetime.now(timezone.utc) - timedelta(hours=72)
        self.cur.execute("""
            INSERT INTO t_pedido (
                codigo_pedido, id_cliente, id_empresa, id_sucursal,
                fecha_pedido, estado, estado_pago, modalidad_compra,
                nombre_contacto, telefono_contacto, subtotal, total
            ) VALUES (
                'PED-VENCIDO-01', 1, 1, 1,
                %s, 'PENDIENTE_PAGO', 'PENDIENTE', 'RETIRO_SUCURSAL',
                'Cliente Vencido', '70000000', 350.00, 350.00
            ) RETURNING id_pedido;
        """, (fecha_antigua,))
        id_ped_vencido = self.cur.fetchone()[0]

        self.cur.execute("""
            INSERT INTO t_detalle_pedido (id_pedido, id_variante, cantidad, precio_unitario, subtotal)
            VALUES (%s, 901, 4, 350.00, 1400.00);
        """, (id_ped_vencido,))

        # Simular stock reservado para este pedido vencido
        self.cur.execute("""
            UPDATE t_inventario 
            SET stock_reservado = 4, stock_disponible = 6 
            WHERE id_inventario = 1001;
        """)

        reporte_exp = pedido_repos.expirar_pedidos_vencidos(id_empresa=1, horas_tolerancia=48)
        self.assertGreaterEqual(reporte_exp["pedidos_expirados"], 1)
        self.assertGreaterEqual(reporte_exp["prendas_liberadas"], 4)

        # Verificar que el stock quedó restaurado
        self.cur.execute("SELECT stock_reservado, stock_disponible FROM t_inventario WHERE id_inventario = 1001;")
        res_stk, disp_stk = self.cur.fetchone()
        self.assertEqual(res_stk, 0)
        self.assertEqual(disp_stk, 10)

        # Verificar que el pedido pasó a CANCELADO
        self.cur.execute("SELECT estado FROM t_pedido WHERE id_pedido = %s;", (id_ped_vencido,))
        self.assertEqual(self.cur.fetchone()[0], "CANCELADO")

    def test_04_expirar_reservas_vencidas_distingue_tolerancias(self):
        """
        La expiración de reservas en boutique debe respetar la ventana de retención (horas)
        y la tolerancia de llegada (minutos), liberando existencias atómicamente a VENCIDA.
        """
        fecha_visita_vencida = datetime.now(timezone.utc) - timedelta(hours=24)
        self.cur.execute("""
            INSERT INTO t_reserva (
                codigo_reserva, id_cliente, id_sucursal, fecha_hora_visita, estado, con_pago
            ) VALUES (
                'RES-VENCIDA-01', 1, 1, %s, 'PENDIENTE', FALSE
            ) RETURNING id_reserva;
        """, (fecha_visita_vencida,))
        id_res_vencida = self.cur.fetchone()[0]

        self.cur.execute("""
            INSERT INTO t_detalle_reserva (id_reserva, id_variante, cantidad, precio_referencial, estado_prenda)
            VALUES (%s, 901, 2, 350.00, 'RESERVADA');
        """, (id_res_vencida,))

        # Simular stock reservado por la cita
        self.cur.execute("""
            UPDATE t_inventario 
            SET stock_reservado = 2, stock_disponible = 8 
            WHERE id_inventario = 1001;
        """)

        res_exp = reserva_repos.expirar_reservas_vencidas(
            id_empresa=1,
            tolerancia_horas=12,
            tolerancia_llegada_minutos=60
        )
        self.assertGreaterEqual(res_exp["reservas_expiradas"], 1)
        self.assertGreaterEqual(res_exp["prendas_liberadas"], 2)

        # Verificar estado VENCIDA en BD
        self.cur.execute("SELECT estado FROM t_reserva WHERE id_reserva = %s;", (id_res_vencida,))
        self.assertEqual(self.cur.fetchone()[0], "VENCIDA")

        # Verificar que el inventario volvió a stock disponible
        self.cur.execute("SELECT stock_reservado, stock_disponible FROM t_inventario WHERE id_inventario = 1001;")
        res_stk, disp_stk = self.cur.fetchone()
        self.assertEqual(res_stk, 0)
        self.assertEqual(disp_stk, 10)

    def test_05_prenda_empresa2_con_tallas_generales_se_agrega_al_carrito_y_crea_pedido(self):
        """
        Verifica que prendas pertenecientes a Empresa 2 cuyas variantes usen tallas/colores
        creados históricamente en Empresa 1 (o compartidos) puedan agregarse a la bolsa
        y procesarse en pedidos sin falsos positivos de 'no pertenece a esta tienda'.
        """
        # Crear producto y variante para Empresa 2
        self.cur.execute("""
            INSERT INTO t_categoria (id_categoria, id_empresa, nombre)
            VALUES (502, 2, 'Accesorios Primavera')
            ON CONFLICT (id_categoria) DO NOTHING;

            INSERT INTO t_producto (id_producto, id_empresa, id_categoria, nombre, codigo_producto, precio)
            VALUES (802, 2, 502, 'Cinturón Trenzado Artesanal', 'EMP2-CIN-002-E1', 125.00)
            ON CONFLICT (id_producto) DO NOTHING;

            -- Variante en Empresa 2 usando talla 601 (creada en empresa 1) y color 701 (creado en empresa 1)
            INSERT INTO t_producto_talla_color (id_variante, id_producto, id_talla, id_color, sku, precio)
            VALUES (902, 802, 601, 701, 'EMP2-CIN-002-E1-M-NEG', 125.00)
            ON CONFLICT (id_variante) DO NOTHING;

            -- Inventario en sucursal 2 (pertenece a Empresa 2)
            INSERT INTO t_inventario (id_inventario, id_sucursal, id_variante, stock_actual, stock_reservado, stock_disponible, stock_contingencia)
            VALUES (1002, 2, 902, 15, 0, 15, 0)
            ON CONFLICT (id_inventario) DO UPDATE
            SET stock_actual = 15, stock_reservado = 0, stock_disponible = 15, stock_contingencia = 0;
        """)

        # 1. Agregar prenda al carrito de Empresa 2
        res_cart = carrito_repos.agregar_item_al_carrito(
            id_usuario=3,
            id_empresa=2,
            id_variante=902,
            cantidad=1
        )
        self.assertIsNotNone(res_cart)
        self.assertEqual(res_cart["total_items"], 1)
        self.assertEqual(res_cart["items"][0]["id_variante"], 902)

        # 2. Validar que un usuario CLIENTE tiene alcance 'CLIENTE' incluso si tiene empresa
        alcance_cliente = obtener_alcance_usuario({"roles": ["CLIENTE"], "id_empresa": 1})
        self.assertEqual(alcance_cliente, "CLIENTE", "Un usuario final cliente debe tener alcance CLIENTE para comprar en cualquier tienda")

        # 3. Crear pedido en Empresa 2
        datos_pedido = {
            "id_sucursal": 2,
            "modalidad_compra": "RETIRO_SUCURSAL",
            "nombre_contacto": "Cliente Shopping Bolivia",
            "telefono_contacto": "77112233"
        }
        res_ped = pedido_repos.validar_y_crear_pedido(id_usuario=3, id_empresa=2, datos=datos_pedido)
        self.assertIsNotNone(res_ped)
        self.assertEqual(res_ped["estado"], "PENDIENTE_PAGO")
        self.assertEqual(res_ped["total"], 125.00)

        # 4. Verificar que se descontó el stock disponible de la variante de Empresa 2
        self.cur.execute("SELECT stock_actual, stock_reservado, stock_disponible FROM t_inventario WHERE id_inventario = 1002;")
        act, resv, disp = self.cur.fetchone()
        self.assertEqual(act, 15)
        self.assertEqual(resv, 1)
        self.assertEqual(disp, 14)


if __name__ == '__main__':
    unittest.main()
