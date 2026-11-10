import json
from pathlib import Path
import sys
import unittest
import uuid
from datetime import datetime, timedelta, timezone

import psycopg2
from fastapi.testclient import TestClient

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tests"))
sys.path.insert(0, str(ROOT / "backend"))
from isolated_postgres import LocalPostgres

from app.core.config import Config
from app.core.postgres import PostgreSQL, _invalidar_caches_seguridad
from app.core.security import _contexto_vigente
from migrate import render


PWA_SYNC_SCHEMA_SQL = """
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

CREATE TABLE t_categoria (
    id_categoria SERIAL PRIMARY KEY,
    nombre TEXT NOT NULL,
    descripcion TEXT,
    id_padre INTEGER REFERENCES t_categoria(id_categoria),
    id_empresa INTEGER NOT NULL REFERENCES empresa(id_empresa),
    imagen_url TEXT,
    imagen_public_id TEXT,
    activo BOOLEAN DEFAULT TRUE,
    estado BOOLEAN DEFAULT TRUE,
    created_at TIMESTAMP DEFAULT now(),
    updated_at TIMESTAMP DEFAULT now()
);

CREATE TABLE t_talla (
    id_talla SERIAL PRIMARY KEY,
    nombre TEXT NOT NULL,
    descripcion TEXT,
    id_empresa INTEGER NOT NULL REFERENCES empresa(id_empresa),
    activo BOOLEAN DEFAULT TRUE,
    estado BOOLEAN DEFAULT TRUE,
    created_at TIMESTAMP DEFAULT now(),
    updated_at TIMESTAMP DEFAULT now()
);

CREATE TABLE t_color (
    id_color SERIAL PRIMARY KEY,
    nombre TEXT NOT NULL,
    codigo_hex TEXT NOT NULL,
    id_empresa INTEGER NOT NULL REFERENCES empresa(id_empresa),
    activo BOOLEAN DEFAULT TRUE,
    estado BOOLEAN DEFAULT TRUE,
    created_at TIMESTAMP DEFAULT now(),
    updated_at TIMESTAMP DEFAULT now()
);

CREATE TABLE t_producto (
    id_producto SERIAL PRIMARY KEY,
    nombre TEXT NOT NULL,
    descripcion TEXT,
    codigo_producto TEXT,
    sku TEXT,
    codigo TEXT,
    marca TEXT DEFAULT 'Aurora Atelier',
    genero TEXT DEFAULT 'Mujer',
    coleccion TEXT DEFAULT 'Atelier 2026',
    precio NUMERIC(12, 2) NOT NULL DEFAULT 150.00,
    precio_venta NUMERIC(12, 2) NOT NULL DEFAULT 150.00,
    costo NUMERIC(12, 2) DEFAULT 60.00,
    id_categoria INTEGER REFERENCES t_categoria(id_categoria),
    id_empresa INTEGER NOT NULL REFERENCES empresa(id_empresa),
    temporada TEXT DEFAULT 'PERMANENTE',
    imagen_url TEXT,
    tiene_ra BOOLEAN DEFAULT FALSE,
    tipo_prenda_ra TEXT,
    modelo_2d_url TEXT,
    stock_minimo INTEGER DEFAULT 5,
    activo BOOLEAN DEFAULT TRUE,
    estado BOOLEAN DEFAULT TRUE,
    fecha_registro TIMESTAMP DEFAULT now(),
    created_at TIMESTAMP DEFAULT now(),
    updated_at TIMESTAMP DEFAULT now()
);

CREATE TABLE t_producto_imagen (
    id_imagen SERIAL PRIMARY KEY,
    id_producto INTEGER NOT NULL REFERENCES t_producto(id_producto) ON DELETE CASCADE,
    imagen_url TEXT NOT NULL,
    url TEXT,
    public_id TEXT,
    es_principal BOOLEAN DEFAULT FALSE,
    orden INTEGER DEFAULT 1,
    created_at TIMESTAMP DEFAULT now()
);

CREATE TABLE t_producto_talla_color (
    id_variante SERIAL PRIMARY KEY,
    id_producto INTEGER NOT NULL REFERENCES t_producto(id_producto) ON DELETE CASCADE,
    id_talla INTEGER NOT NULL REFERENCES t_talla(id_talla),
    id_color INTEGER NOT NULL REFERENCES t_color(id_color),
    sku TEXT,
    sku_variante TEXT,
    codigo_barras TEXT,
    precio NUMERIC(12, 2) DEFAULT 150.00,
    precio_adicional NUMERIC(12, 2) DEFAULT 0,
    costo_unitario NUMERIC(12, 2) DEFAULT 60,
    activo BOOLEAN DEFAULT TRUE,
    estado BOOLEAN DEFAULT TRUE,
    created_at TIMESTAMP DEFAULT now(),
    updated_at TIMESTAMP DEFAULT now(),
    UNIQUE(id_producto, id_talla, id_color)
);

CREATE TABLE t_promocion (
    id_promocion SERIAL PRIMARY KEY,
    nombre TEXT NOT NULL,
    descripcion TEXT,
    porcentaje_descuento NUMERIC(5, 2) NOT NULL,
    fecha_inicio DATE NOT NULL,
    fecha_fin DATE NOT NULL,
    activo BOOLEAN DEFAULT TRUE,
    estado BOOLEAN DEFAULT TRUE,
    id_empresa INTEGER REFERENCES empresa(id_empresa)
);

CREATE TABLE t_promocion_producto (
    id_promocion INTEGER NOT NULL REFERENCES t_promocion(id_promocion) ON DELETE CASCADE,
    id_producto INTEGER NOT NULL REFERENCES t_producto(id_producto) ON DELETE CASCADE,
    porcentaje_descuento NUMERIC(5, 2) DEFAULT 10.00,
    PRIMARY KEY (id_promocion, id_producto)
);

CREATE TABLE t_inventario (
    id_inventario SERIAL PRIMARY KEY,
    id_sucursal INTEGER NOT NULL REFERENCES t_sucursal(id_sucursal),
    id_variante INTEGER NOT NULL REFERENCES t_producto_talla_color(id_variante),
    stock_actual INTEGER NOT NULL DEFAULT 0,
    stock_reservado INTEGER NOT NULL DEFAULT 0,
    stock_disponible INTEGER NOT NULL DEFAULT 0,
    stock_minimo INTEGER NOT NULL DEFAULT 5,
    estado BOOLEAN DEFAULT TRUE,
    ubicacion TEXT,
    fecha_actualizacion TIMESTAMP DEFAULT now(),
    updated_at TIMESTAMP DEFAULT now(),
    UNIQUE(id_sucursal, id_variante)
);

CREATE TABLE t_cliente (
    id_cliente SERIAL PRIMARY KEY,
    id_usuario INTEGER UNIQUE REFERENCES t_usuario(id_usuario),
    nombre_completo TEXT,
    telefono TEXT,
    direccion TEXT,
    ciudad TEXT,
    ci_nit TEXT,
    fecha_registro TIMESTAMP DEFAULT now()
);

CREATE TABLE t_carrito (
    id_carrito SERIAL PRIMARY KEY,
    id_cliente INTEGER NOT NULL REFERENCES t_cliente(id_cliente),
    id_empresa INTEGER NOT NULL REFERENCES empresa(id_empresa),
    estado TEXT NOT NULL DEFAULT 'ACTIVO',
    fecha_creacion TIMESTAMP DEFAULT now(),
    fecha_actualizacion TIMESTAMP DEFAULT now(),
    updated_at TIMESTAMP DEFAULT now()
);

CREATE TABLE t_detalle_carrito (
    id_detalle_carrito SERIAL PRIMARY KEY,
    id_carrito INTEGER NOT NULL REFERENCES t_carrito(id_carrito) ON DELETE CASCADE,
    id_variante INTEGER NOT NULL REFERENCES t_producto_talla_color(id_variante),
    cantidad INTEGER NOT NULL DEFAULT 1,
    precio_unitario NUMERIC(12, 2) NOT NULL DEFAULT 150.00,
    subtotal NUMERIC(12, 2) NOT NULL DEFAULT 150.00,
    fecha_agregado TIMESTAMP DEFAULT now()
);

CREATE TABLE t_reserva (
    id_reserva SERIAL PRIMARY KEY,
    id_cliente INTEGER REFERENCES t_cliente(id_cliente),
    id_sucursal INTEGER REFERENCES t_sucursal(id_sucursal),
    id_empresa INTEGER REFERENCES empresa(id_empresa),
    codigo_reserva TEXT,
    fecha_reserva TIMESTAMP DEFAULT now(),
    fecha_hora_visita TIMESTAMP,
    estado TEXT NOT NULL DEFAULT 'PENDIENTE',
    observaciones TEXT,
    con_pago BOOLEAN DEFAULT FALSE,
    estado_pago TEXT DEFAULT 'SIN_PAGO',
    monto_pagado NUMERIC(12, 2) DEFAULT 0.00,
    created_at TIMESTAMP DEFAULT now()
);

CREATE TABLE t_detalle_reserva (
    id_detalle_reserva SERIAL PRIMARY KEY,
    id_reserva INTEGER NOT NULL REFERENCES t_reserva(id_reserva) ON DELETE CASCADE,
    id_variante INTEGER REFERENCES t_producto_talla_color(id_variante),
    id_producto INTEGER REFERENCES t_producto(id_producto),
    id_talla INTEGER REFERENCES t_talla(id_talla),
    id_color INTEGER REFERENCES t_color(id_color),
    cantidad INTEGER NOT NULL DEFAULT 1,
    estado_prenda TEXT DEFAULT 'RESERVADA'
);

CREATE OR REPLACE FUNCTION fn_reservar_stock(
    p_id_sucursal INTEGER,
    p_id_variante INTEGER,
    p_cantidad INTEGER,
    p_id_usuario INTEGER
) RETURNS JSONB AS $$
DECLARE
    v_disp INTEGER;
BEGIN
    SELECT (stock_actual - COALESCE(stock_reservado, 0))
    INTO v_disp
    FROM t_inventario
    WHERE id_sucursal = p_id_sucursal AND id_variante = p_id_variante
    FOR UPDATE;

    IF v_disp IS NULL OR v_disp < p_cantidad THEN
        RETURN jsonb_build_object('success', false, 'message', 'Stock insuficiente en sucursal.');
    END IF;

    UPDATE t_inventario
    SET stock_reservado = COALESCE(stock_reservado, 0) + p_cantidad,
        stock_disponible = GREATEST(stock_actual - (COALESCE(stock_reservado, 0) + p_cantidad), 0)
    WHERE id_sucursal = p_id_sucursal AND id_variante = p_id_variante;

    RETURN jsonb_build_object('success', true, 'reserved', p_cantidad);
END;
$$ LANGUAGE plpgsql;

ALTER TABLE t_cliente
    ADD COLUMN IF NOT EXISTS nit_ci TEXT,
    ADD COLUMN IF NOT EXISTS ci TEXT;

CREATE TABLE t_denominacion (
    id_denominacion SERIAL PRIMARY KEY,
    valor NUMERIC(12, 2) NOT NULL,
    moneda TEXT DEFAULT 'BOB',
    tipo TEXT DEFAULT 'BILLETE',
    orden INTEGER DEFAULT 1,
    activo BOOLEAN DEFAULT TRUE
);

CREATE TABLE t_caja_sesion (
    id_sesion_caja SERIAL PRIMARY KEY,
    id_caja INTEGER NOT NULL REFERENCES t_caja(id_caja),
    id_usuario INTEGER NOT NULL REFERENCES t_usuario(id_usuario),
    id_sucursal INTEGER NOT NULL REFERENCES t_sucursal(id_sucursal),
    id_empresa INTEGER NOT NULL REFERENCES empresa(id_empresa),
    fecha_apertura TIMESTAMP DEFAULT now(),
    fecha_cierre TIMESTAMP,
    monto_inicial NUMERIC(12, 2) DEFAULT 0.00,
    efectivo_esperado NUMERIC(12, 2),
    efectivo_contado NUMERIC(12, 2),
    diferencia NUMERIC(12, 2),
    estado TEXT NOT NULL DEFAULT 'ABIERTA',
    observacion_apertura TEXT,
    observacion_cierre TEXT
);

CREATE TABLE t_caja_conteo (
    id_conteo SERIAL PRIMARY KEY,
    id_sesion_caja INTEGER NOT NULL REFERENCES t_caja_sesion(id_sesion_caja) ON DELETE CASCADE,
    tipo_conteo TEXT NOT NULL,
    id_denominacion INTEGER REFERENCES t_denominacion(id_denominacion),
    valor_denominacion NUMERIC(12, 2),
    cantidad INTEGER NOT NULL DEFAULT 0,
    subtotal NUMERIC(12, 2) NOT NULL DEFAULT 0.00
);

CREATE TABLE t_metodo_pago (
    id_metodo_pago SERIAL PRIMARY KEY,
    nombre TEXT NOT NULL,
    tipo TEXT NOT NULL,
    estado BOOLEAN DEFAULT TRUE
);

CREATE TABLE t_venta (
    id_venta SERIAL PRIMARY KEY,
    numero_venta TEXT,
    id_sesion_caja INTEGER REFERENCES t_caja_sesion(id_sesion_caja),
    id_usuario INTEGER REFERENCES t_usuario(id_usuario),
    id_sucursal INTEGER REFERENCES t_sucursal(id_sucursal),
    id_empresa INTEGER REFERENCES empresa(id_empresa),
    id_cliente INTEGER REFERENCES t_cliente(id_cliente),
    id_reserva INTEGER REFERENCES t_reserva(id_reserva),
    fecha_venta TIMESTAMP DEFAULT now(),
    subtotal NUMERIC(12, 2) NOT NULL DEFAULT 0.00,
    descuento NUMERIC(12, 2) NOT NULL DEFAULT 0.00,
    total NUMERIC(12, 2) NOT NULL DEFAULT 0.00,
    estado TEXT NOT NULL DEFAULT 'PENDIENTE_PAGO',
    tipo_venta TEXT DEFAULT 'PRESENCIAL',
    observacion TEXT,
    nit_ci TEXT,
    razon_social TEXT,
    correo_facturacion TEXT,
    tipo_documento TEXT DEFAULT 'COMPROBANTE'
);

CREATE TABLE t_detalle_venta (
    id_detalle_venta SERIAL PRIMARY KEY,
    id_venta INTEGER NOT NULL REFERENCES t_venta(id_venta) ON DELETE CASCADE,
    id_variante INTEGER NOT NULL REFERENCES t_producto_talla_color(id_variante),
    cantidad INTEGER NOT NULL DEFAULT 1,
    precio_unitario NUMERIC(12, 2) NOT NULL DEFAULT 0.00,
    descuento NUMERIC(12, 2) NOT NULL DEFAULT 0.00,
    subtotal NUMERIC(12, 2) NOT NULL DEFAULT 0.00
);

CREATE TABLE t_pago (
    id_pago SERIAL PRIMARY KEY,
    id_venta INTEGER NOT NULL REFERENCES t_venta(id_venta) ON DELETE CASCADE,
    id_metodo_pago INTEGER NOT NULL REFERENCES t_metodo_pago(id_metodo_pago),
    codigo_transaccion TEXT,
    referencia_externa TEXT,
    monto NUMERIC(12, 2) NOT NULL DEFAULT 0.00,
    fecha_pago TIMESTAMP DEFAULT now(),
    estado TEXT NOT NULL DEFAULT 'APROBADO'
);

CREATE TABLE t_pago_denominacion (
    id_pago_denom SERIAL PRIMARY KEY,
    id_pago INTEGER NOT NULL REFERENCES t_pago(id_pago) ON DELETE CASCADE,
    id_venta INTEGER NOT NULL REFERENCES t_venta(id_venta) ON DELETE CASCADE,
    id_sesion_caja INTEGER REFERENCES t_caja_sesion(id_sesion_caja),
    tipo_movimiento TEXT NOT NULL,
    id_denominacion INTEGER REFERENCES t_denominacion(id_denominacion),
    valor_denominacion NUMERIC(12, 2) NOT NULL,
    cantidad INTEGER NOT NULL,
    subtotal NUMERIC(12, 2) NOT NULL
);

CREATE OR REPLACE FUNCTION fn_registrar_venta_pos(
    p_id_sesion_caja INTEGER,
    p_id_usuario INTEGER,
    p_id_sucursal INTEGER,
    p_id_empresa INTEGER,
    p_id_cliente INTEGER,
    p_items JSON,
    p_descuento NUMERIC,
    p_observacion TEXT,
    p_id_reserva INTEGER DEFAULT NULL
) RETURNS JSONB AS $$
DECLARE
    v_item JSON;
    v_id_var INTEGER;
    v_cant INTEGER;
    v_precio NUMERIC(12, 2);
    v_disp INTEGER;
    v_subtotal NUMERIC(12, 2) := 0.00;
    v_total NUMERIC(12, 2) := 0.00;
    v_id_venta INTEGER;
    v_numero_venta TEXT;
BEGIN
    FOR v_item IN SELECT * FROM json_array_elements(p_items)
    LOOP
        v_id_var := (v_item->>'id_variante')::INTEGER;
        v_cant := (v_item->>'cantidad')::INTEGER;

        SELECT COALESCE(v.precio, p.precio, 0)
        INTO v_precio
        FROM t_producto_talla_color v
        JOIN t_producto p ON p.id_producto = v.id_producto
        WHERE v.id_variante = v_id_var AND p.id_empresa = p_id_empresa;

        SELECT stock_disponible
        INTO v_disp
        FROM t_inventario
        WHERE id_sucursal = p_id_sucursal AND id_variante = v_id_var
        FOR UPDATE;

        IF v_disp IS NULL OR v_disp < v_cant THEN
            RETURN jsonb_build_object(
                'success', false,
                'error', 'STOCK_INSUFICIENTE',
                'message', 'Stock insuficiente en sucursal para la variante ' || v_id_var
            );
        END IF;

        v_subtotal := v_subtotal + ROUND(v_precio * v_cant, 2);
    END LOOP;

    v_total := GREATEST(ROUND(v_subtotal - COALESCE(p_descuento, 0), 2), 0.00);
    v_numero_venta := 'VTA-' || LPAD(nextval(pg_get_serial_sequence('t_venta', 'id_venta'))::TEXT, 6, '0');

    INSERT INTO t_venta (
        id_venta, numero_venta, id_sesion_caja, id_usuario, id_sucursal,
        id_empresa, id_cliente, id_reserva, subtotal, descuento, total,
        estado, tipo_venta, observacion
    ) VALUES (
        currval(pg_get_serial_sequence('t_venta', 'id_venta')),
        v_numero_venta, p_id_sesion_caja, p_id_usuario, p_id_sucursal,
        p_id_empresa, p_id_cliente, p_id_reserva, v_subtotal, COALESCE(p_descuento, 0), v_total,
        'PENDIENTE_PAGO', 'PRESENCIAL', p_observacion
    ) RETURNING id_venta INTO v_id_venta;

    FOR v_item IN SELECT * FROM json_array_elements(p_items)
    LOOP
        v_id_var := (v_item->>'id_variante')::INTEGER;
        v_cant := (v_item->>'cantidad')::INTEGER;

        SELECT COALESCE(v.precio, p.precio, 0)
        INTO v_precio
        FROM t_producto_talla_color v
        JOIN t_producto p ON p.id_producto = v.id_producto
        WHERE v.id_variante = v_id_var;

        INSERT INTO t_detalle_venta (
            id_venta, id_variante, cantidad, precio_unitario, descuento, subtotal
        ) VALUES (
            v_id_venta, v_id_var, v_cant, v_precio, 0, ROUND(v_precio * v_cant, 2)
        );

        UPDATE t_inventario
        SET stock_actual = stock_actual - v_cant,
            stock_disponible = GREATEST((stock_actual - v_cant) - COALESCE(stock_reservado, 0), 0),
            updated_at = now()
        WHERE id_sucursal = p_id_sucursal AND id_variante = v_id_var;
    END LOOP;

    RETURN jsonb_build_object(
        'success', true,
        'id_venta', v_id_venta,
        'numero_venta', v_numero_venta,
        'subtotal', v_subtotal,
        'descuento', COALESCE(p_descuento, 0),
        'total', v_total
    );
END;
$$ LANGUAGE plpgsql;
"""


class PwaOfflineIter2Suite(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        if PostgreSQL._pool:
            try:
                PostgreSQL._pool.closeall()
            except Exception:
                pass
            PostgreSQL._pool = None

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
            Config.TOKEN_KEY = "iter2_pwa_test_secret_key"

        cls.schema = "pwa_" + uuid.uuid4().hex
        Config.SCHEMA = cls.schema

        with psycopg2.connect(**cls.pg.params) as conn:
            with conn.cursor() as cur:
                cur.execute(f"CREATE SCHEMA {cls.schema}; SET search_path TO {cls.schema}")
                cur.execute(f"ALTER DATABASE postgres SET search_path TO {cls.schema}, public")
                cur.execute((ROOT / "tests/p1_fixture.sql").read_text(encoding="utf-8"))
                cur.execute(render(ROOT / "backend/migrations/001_iter1_saas.up.sql", cls.schema))
                cur.execute(PWA_SYNC_SCHEMA_SQL)
                cur.execute(render(ROOT / "backend/migrations/002_iter1_perf_indexes.up.sql", cls.schema))
                cur.execute(render(ROOT / "backend/migrations/003_iter2_sync_idempotency.up.sql", cls.schema))
                cur.execute(render(ROOT / "backend/migrations/004_iter2_sync_transactional.up.sql", cls.schema))
                cur.execute(render(ROOT / "backend/migrations/006_iter4_saas_storefront.up.sql", cls.schema))

                # Suscripción activa para Empresa 1 y Empresa 2
                cur.execute(
                    """
                    INSERT INTO t_suscripcion (id_empresa, codigo_plan, inicio, fin, motivo, creado_por)
                    VALUES
                        (1, 'PROFESIONAL', now() - interval '1 day', now() + interval '30 days', 'Plan A', 1),
                        (2, 'BASICO', now() - interval '1 day', now() + interval '30 days', 'Plan B', 1);
                    """
                )

                # Sembrar catálogo para Empresa 1 y Empresa 2
                cur.execute(
                    """
                    INSERT INTO t_categoria (id_categoria, nombre, id_empresa, activo) VALUES
                        (1, 'Abrigos', 1, TRUE),
                        (2, 'Vestidos', 2, TRUE);
                    INSERT INTO t_talla (id_talla, nombre, id_empresa, activo) VALUES
                        (1, 'M', 1, TRUE),
                        (2, 'L', 1, TRUE),
                        (3, 'S', 2, TRUE);
                    INSERT INTO t_color (id_color, nombre, codigo_hex, id_empresa, activo) VALUES
                        (1, 'Negro', '#000000', 1, TRUE),
                        (2, 'Marfil', '#FFFFF0', 1, TRUE),
                        (3, 'Rojo', '#AA0000', 2, TRUE);

                    INSERT INTO t_producto (id_producto, nombre, codigo_producto, precio, id_categoria, id_empresa, temporada, activo) VALUES
                        (10, 'Abrigo Cachemira Imperial', 'ABR-010', 150.00, 1, 1, 'PERMANENTE', TRUE),
                        (11, 'Blazer Sastre Aurora', 'BLZ-011', 200.00, 1, 1, 'PERMANENTE', TRUE),
                        (20, 'Vestido Seda Tenant B', 'VES-020', 180.00, 2, 2, 'PERMANENTE', TRUE);

                    INSERT INTO t_producto_talla_color (id_variante, id_producto, id_talla, id_color, sku, precio, activo) VALUES
                        (100, 10, 1, 1, 'ABR-010-M-NEG', 150.00, TRUE),
                        (101, 10, 2, 2, 'ABR-010-L-MAR', 150.00, TRUE),
                        (102, 11, 1, 1, 'BLZ-011-M-NEG', 200.00, TRUE),
                        (200, 20, 3, 3, 'VES-020-S-ROJ', 180.00, TRUE);

                    INSERT INTO t_inventario (id_sucursal, id_variante, stock_actual, stock_reservado, stock_disponible, estado) VALUES
                        (1, 100, 15, 0, 15, TRUE),
                        (1, 101, 8, 0, 8, TRUE),
                        (1, 102, 12, 0, 12, TRUE),
                        (2, 200, 10, 0, 10, TRUE);

                    INSERT INTO t_denominacion (id_denominacion, valor, moneda, tipo, orden, activo) VALUES
                        (1, 200.00, 'BOB', 'BILLETE', 1, TRUE),
                        (2, 100.00, 'BOB', 'BILLETE', 2, TRUE),
                        (3, 50.00, 'BOB', 'BILLETE', 3, TRUE),
                        (4, 20.00, 'BOB', 'BILLETE', 4, TRUE),
                        (5, 10.00, 'BOB', 'BILLETE', 5, TRUE),
                        (6, 5.00, 'BOB', 'MONEDA', 6, TRUE),
                        (7, 2.00, 'BOB', 'MONEDA', 7, TRUE),
                        (8, 1.00, 'BOB', 'MONEDA', 8, TRUE);

                    INSERT INTO t_metodo_pago (id_metodo_pago, nombre, tipo, estado) VALUES
                        (1, 'Efectivo', 'EFECTIVO', TRUE),
                        (2, 'Tarjeta Débito/Crédito', 'TARJETA', TRUE),
                        (3, 'QR Simple', 'QR', TRUE);

                    INSERT INTO t_caja (id_caja, id_sucursal, id_empresa, codigo_caja, nombre, estado) VALUES
                        (1, 1, 1, 'CAJA-SUC-1-01', 'Caja 01 - A1', 'ACTIVA'),
                        (2, 2, 2, 'CAJA-SUC-2-01', 'Caja 01 - B1', 'ACTIVA');
                    """
                )
            conn.commit()

        from app.main import app

        cls.client = TestClient(app)

    @classmethod
    def tearDownClass(cls):
        if PostgreSQL._pool:
            try:
                PostgreSQL._pool.closeall()
            except Exception:
                pass
            PostgreSQL._pool = None
        cls.cluster.__exit__(None, None, None)

    def setUp(self):
        _invalidar_caches_seguridad()

    def _headers_for_user(self, user_id: int, id_empresa: int = 1, id_rol: int = 103, rol: str = "ADMIN_EMPRESA"):
        import jwt
        ctx = _contexto_vigente({"id_usuario": user_id})
        payload = {
            "nro_usuario": user_id,
            "id_usuario": user_id,
            "id_empresa": ctx.get("id_empresa") if ctx else id_empresa,
            "id_rol": ctx.get("id_rol") if ctx else id_rol,
            "rol": rol,
            "roles": ctx.get("roles", []) if ctx else [rol],
            "permisos": ctx.get("permisos", []) if ctx else [],
            "sucursales": ctx.get("sucursales", []) if ctx else [],
            "sv": int(ctx.get("session_version", 1)) if ctx else 1,
        }
        secret = Config.TOKEN_KEY or Config.SECRET_KEY or "iter2_pwa_test_secret_key"
        tok = jwt.encode(payload, secret, algorithm="HS256")
        return {"Authorization": f"Bearer {tok}"}

    def test_01_reversible_sync_migration_003(self):
        with psycopg2.connect(**self.pg.params) as conn:
            with conn.cursor() as cur:
                cur.execute(render(ROOT / "backend/migrations/004_iter2_sync_transactional.down.sql", self.schema))
                cur.execute(render(ROOT / "backend/migrations/003_iter2_sync_idempotency.down.sql", self.schema))
                cur.execute(
                    "SELECT to_regclass(%s);",
                    (f"{self.schema}.t_sync_operacion",),
                )
                self.assertIsNone(cur.fetchone()[0])

                cur.execute(render(ROOT / "backend/migrations/003_iter2_sync_idempotency.up.sql", self.schema))
                cur.execute(render(ROOT / "backend/migrations/004_iter2_sync_transactional.up.sql", self.schema))
                cur.execute(
                    "SELECT to_regclass(%s);",
                    (f"{self.schema}.t_sync_operacion",),
                )
                self.assertIsNotNone(cur.fetchone()[0])
            conn.commit()

    def test_02_sync_ping_zero_sql_queries(self):
        res = self.client.get("/api/sync/ping")
        self.assertEqual(res.status_code, 200)
        body = res.json()
        self.assertTrue(body["success"])
        self.assertEqual(body["status"], "ONLINE")
        self.assertEqual(int(res.headers.get("X-DB-Query-Count", "99")), 0)

    def test_03_sync_cart_operations_idempotency_and_n_plus_1_elimination(self):
        headers = self._headers_for_user(user_id=2, id_empresa=1)
        op_id_1 = f"op-add-{uuid.uuid4().hex[:12]}"
        op_id_2 = f"op-add-{uuid.uuid4().hex[:12]}"

        # 1. Enviar lote inicial con 2 prendas distintas (CU38W)
        res1 = self.client.post(
            "/api/sync/operations",
            headers=headers,
            json={
                "operations": [
                    {
                        "created_at": datetime.now(timezone.utc).isoformat(),
                        "operation_id": op_id_1,
                        "kind": "CART_ADD_ITEM",
                        "tenant_id": 1,
                        "payload": {"id_variante": 100, "cantidad": 2, "expected_unit_price": 150.00},
                    },
                    {
                        "created_at": datetime.now(timezone.utc).isoformat(),
                        "operation_id": op_id_2,
                        "kind": "CART_ADD_ITEM",
                        "tenant_id": 1,
                        "payload": {"id_variante": 101, "cantidad": 1, "expected_unit_price": 150.00},
                    },
                ]
            },
        )
        self.assertEqual(res1.status_code, 200)
        data1 = res1.json()
        self.assertEqual(data1["synced_count"], 2)
        self.assertFalse(data1["results"][0]["idempotent_replay"])
        self.assertEqual(data1["results"][1]["data"]["total_items"], 3)

        # 2. Reenviar exactamente el mismo operation_id (simulación de reintento por corte de red)
        res_replay = self.client.post(
            "/api/sync/operations",
            headers=headers,
            json={
                "operations": [
                    {
                        "created_at": datetime.now(timezone.utc).isoformat(),
                        "operation_id": op_id_1,
                        "kind": "CART_ADD_ITEM",
                        "tenant_id": 1,
                        "payload": {"id_variante": 100, "cantidad": 2, "expected_unit_price": 150.00},
                    }
                ]
            },
        )
        self.assertEqual(res_replay.status_code, 200)
        replay_item = res_replay.json()["results"][0]
        self.assertEqual(replay_item["status"], "synced")
        self.assertTrue(replay_item["idempotent_replay"])

        # Verificar que la cantidad en el carrito NO se duplicó (sigue siendo 3 en total)
        cart_res = self.client.get("/api/carrito?id_empresa=1", headers=headers)
        self.assertEqual(cart_res.status_code, 200)
        self.assertEqual(cart_res.json()["data"]["total_items"], 3)
        # Verificar eliminación de N+1 en GET /api/carrito (con contexto caliente <= 4 queries aunque haya múltiples ítems)
        cart_res_warm = self.client.get("/api/carrito?id_empresa=1", headers=headers)
        self.assertLessEqual(int(cart_res_warm.headers.get("X-DB-Query-Count", "99")), 4)

    def test_04_sync_conflict_detection_and_resolution_cu39w(self):
        headers = self._headers_for_user(user_id=2, id_empresa=1)

        # Conflicto A: STOCK_INSUFFICIENT (solicita 50, disponibles 15)
        op_stock = f"op-stock-{uuid.uuid4().hex[:10]}"
        res_stock = self.client.post(
            "/api/sync/operations",
            headers=headers,
            json={
                "operations": [
                    {
                        "created_at": datetime.now(timezone.utc).isoformat(),
                        "operation_id": op_stock,
                        "kind": "CART_ADD_ITEM",
                        "tenant_id": 1,
                        "payload": {"id_variante": 100, "cantidad": 50, "mode": "SET"},
                    }
                ]
            },
        )
        self.assertEqual(res_stock.status_code, 200)
        r_st = res_stock.json()["results"][0]
        self.assertEqual(r_st["status"], "conflict")
        self.assertEqual(r_st["conflict_code"], "STOCK_INSUFFICIENT")
        self.assertEqual(r_st["conflict_detail"]["available_stock"], 15)

        # Resolución CU39W: usuario ajusta a cantidad disponible (5) y reintenta
        res_stock_resolved = self.client.post(
            "/api/sync/operations",
            headers=headers,
            json={
                "operations": [
                    {
                        "created_at": datetime.now(timezone.utc).isoformat(),
                        "operation_id": op_stock,
                        "kind": "CART_ADD_ITEM",
                        "tenant_id": 1,
                        "payload": {"id_variante": 100, "cantidad": 5, "mode": "SET"},
                    }
                ]
            },
        )
        self.assertEqual(res_stock_resolved.json()["results"][0]["status"], "synced")

        # Conflicto B: PRICE_CHANGED (cliente vio Bs. 120.00 offline, precio actual es Bs. 200.00)
        op_price = f"op-price-{uuid.uuid4().hex[:10]}"
        res_price = self.client.post(
            "/api/sync/operations",
            headers=headers,
            json={
                "operations": [
                    {
                        "created_at": datetime.now(timezone.utc).isoformat(),
                        "operation_id": op_price,
                        "kind": "CART_ADD_ITEM",
                        "tenant_id": 1,
                        "payload": {
                            "id_variante": 102,
                            "cantidad": 1,
                            "expected_unit_price": 120.00,
                        },
                    }
                ]
            },
        )
        r_pr = res_price.json()["results"][0]
        self.assertEqual(r_pr["status"], "conflict")
        self.assertEqual(r_pr["conflict_code"], "PRICE_CHANGED")
        self.assertEqual(r_pr["conflict_detail"]["current_unit_price"], 200.0)

        # Resolución CU39W: usuario acepta nuevo precio vigente y reintenta
        res_price_resolved = self.client.post(
            "/api/sync/operations",
            headers=headers,
            json={
                "operations": [
                    {
                        "created_at": datetime.now(timezone.utc).isoformat(),
                        "operation_id": op_price,
                        "kind": "CART_ADD_ITEM",
                        "tenant_id": 1,
                        "payload": {
                            "id_variante": 102,
                            "cantidad": 1,
                            "expected_unit_price": 200.00,
                            "accept_price_change": True,
                        },
                    }
                ]
            },
        )
        self.assertEqual(res_price_resolved.json()["results"][0]["status"], "synced")

    def test_05_sync_reserva_solicitud_and_payment_guard_cu10w(self):
        headers = self._headers_for_user(user_id=2, id_empresa=1)
        manana = (datetime.now() + timedelta(days=1)).strftime("%Y-%m-%d 15:00")

        # 1. Regla #6: Rechazar reserva con pago en cola offline (PAYMENT_REQUIRES_ONLINE)
        op_paid_res = f"op-res-paid-{uuid.uuid4().hex[:10]}"
        res_paid = self.client.post(
            "/api/sync/operations",
            headers=headers,
            json={
                "operations": [
                    {
                        "created_at": datetime.now(timezone.utc).isoformat(),
                        "operation_id": op_paid_res,
                        "kind": "RESERVA_SOLICITUD",
                        "tenant_id": 1,
                        "branch_id": 1,
                        "payload": {
                            "id_sucursal": 1,
                            "fecha_hora_visita": manana,
                            "con_pago": True,
                            "monto_pagado": 150.0,
                            "items": [{"id_variante": 100, "cantidad": 1}],
                        },
                    }
                ]
            },
        )
        r_paid = res_paid.json()["results"][0]
        self.assertEqual(r_paid["status"], "conflict")
        self.assertEqual(r_paid["conflict_code"], "PAYMENT_REQUIRES_ONLINE")

        # 2. Solicitud de reserva gratuita (SIN_PAGO) encolada offline -> validada y confirmada online
        op_free_res = f"op-res-free-{uuid.uuid4().hex[:10]}"
        res_free = self.client.post(
            "/api/sync/operations",
            headers=headers,
            json={
                "operations": [
                    {
                        "created_at": datetime.now(timezone.utc).isoformat(),
                        "operation_id": op_free_res,
                        "kind": "RESERVA_SOLICITUD",
                        "tenant_id": 1,
                        "branch_id": 1,
                        "payload": {
                            "id_sucursal": 1,
                            "fecha_hora_visita": manana,
                            "con_pago": False,
                            "items": [{"id_variante": 101, "cantidad": 1}],
                        },
                    }
                ]
            },
        )
        r_free = res_free.json()["results"][0]
        self.assertEqual(r_free["status"], "synced")
        self.assertTrue(str(r_free["data"]["codigo_reserva"]).startswith("RES-"))

        # 3. Reintento idempotente de la misma reserva NO vuelve a descontar stock
        res_free_replay = self.client.post(
            "/api/sync/operations",
            headers=headers,
            json={
                "operations": [
                    {
                        "created_at": datetime.now(timezone.utc).isoformat(),
                        "operation_id": op_free_res,
                        "kind": "RESERVA_SOLICITUD",
                        "tenant_id": 1,
                        "branch_id": 1,
                        "payload": {
                            "id_sucursal": 1,
                            "fecha_hora_visita": manana,
                            "con_pago": False,
                            "items": [{"id_variante": 101, "cantidad": 1}],
                        },
                    }
                ]
            },
        )
        self.assertTrue(res_free_replay.json()["results"][0]["idempotent_replay"])

    def test_06_multitenant_isolation_and_public_catalog_cache(self):
        # Usuario de Empresa 1 (ADMIN_EMPRESA) intenta sincronizar hacia Empresa 2 -> TENANT_FORBIDDEN
        headers_emp1 = self._headers_for_user(user_id=2, id_empresa=1, id_rol=103, rol="ADMIN_EMPRESA")
        res_cross = self.client.post(
            "/api/sync/operations",
            headers=headers_emp1,
            json={
                "operations": [
                    {
                        "created_at": datetime.now(timezone.utc).isoformat(),
                        "operation_id": f"op-cross-{uuid.uuid4().hex[:10]}",
                        "kind": "CART_ADD_ITEM",
                        "tenant_id": 2,
                        "payload": {"id_variante": 200, "cantidad": 1},
                    }
                ]
            },
        )
        r_cross = res_cross.json()["results"][0]
        self.assertEqual(r_cross["status"], "conflict")
        self.assertEqual(r_cross["conflict_code"], "TENANT_FORBIDDEN")

        # Catálogo público: primera llamada a /api/catalogo/filtros?id_empresa=1 consulta BD, segunda usa caché (0 SQL)
        f1 = self.client.get("/api/catalogo/filtros?id_empresa=1")
        self.assertEqual(f1.status_code, 200)
        self.assertGreater(int(f1.headers.get("X-DB-Query-Count", "0")), 0)

        f2 = self.client.get("/api/catalogo/filtros?id_empresa=1")
        self.assertEqual(f2.status_code, 200)
        self.assertEqual(int(f2.headers.get("X-DB-Query-Count", "99")), 0)

    def test_07_sync_lote_venta_contado_efectivo_idempotency_and_guards_cu24w(self):
        # 1. Cliente (rol CLIENTE, user 5) NO puede sincronizar VENTA_CONTADO -> 403 ROLE_FORBIDDEN
        headers_cliente = self._headers_for_user(user_id=5, id_empresa=1, id_rol=102, rol="CLIENTE")
        res_cli = self.client.post(
            "/api/sync/lote",
            headers=headers_cliente,
            json={
                "operations": [
                    {
                        "created_at": datetime.now(timezone.utc).isoformat(),
                        "operation_id": f"op-vta-cli-{uuid.uuid4().hex[:10]}",
                        "kind": "VENTA_CONTADO",
                        "tenant_id": 1,
                        "branch_id": 1,
                        "payload": {
                            "id_sucursal": 1,
                            "metodo_tipo": "EFECTIVO",
                            "monto_recibido": 150.0,
                            "items": [{"id_variante": 100, "cantidad": 1, "expected_unit_price": 150.0}],
                        },
                    }
                ]
            },
        )
        self.assertEqual(res_cli.status_code, 200)
        r_cli = res_cli.json()["results"][0]
        self.assertEqual(r_cli["status"], "conflict")
        self.assertEqual(r_cli["conflict_code"], "ROLE_FORBIDDEN")

        # 2. Cajero autorizado (user 3, CAJERO, sucursal 1) intenta VENTA_CONTADO con pago electrónico (QR) -> 409 PAYMENT_REQUIRES_ONLINE
        headers_cajero = self._headers_for_user(user_id=3, id_empresa=1, id_rol=105, rol="CAJERO")
        op_qr = f"op-vta-qr-{uuid.uuid4().hex[:10]}"
        res_qr = self.client.post(
            "/api/sync/lote",
            headers=headers_cajero,
            json={
                "operations": [
                    {
                        "created_at": datetime.now(timezone.utc).isoformat(),
                        "operation_id": op_qr,
                        "kind": "VENTA_CONTADO",
                        "tenant_id": 1,
                        "branch_id": 1,
                        "payload": {
                            "id_sucursal": 1,
                            "metodo_tipo": "QR",
                            "monto_recibido": 150.0,
                            "items": [{"id_variante": 100, "cantidad": 1, "expected_unit_price": 150.0}],
                        },
                    }
                ]
            },
        )
        r_qr = res_qr.json()["results"][0]
        self.assertEqual(r_qr["status"], "reconciliation_required")
        self.assertTrue(r_qr["reconciliation_required"])
        self.assertEqual(r_qr["conflict_code"], "PAYMENT_REQUIRES_ONLINE")

        # 3. Cajero intenta VENTA_CONTADO en EFECTIVO con caja cerrada -> CAJA_CERRADA (incidencia persistida para conciliación)
        op_cash_sale = f"op-vta-cash-{uuid.uuid4().hex[:10]}"
        res_closed = self.client.post(
            "/api/sync/lote",
            headers=headers_cajero,
            json={
                "operations": [
                    {
                        "created_at": datetime.now(timezone.utc).isoformat(),
                        "operation_id": op_cash_sale,
                        "kind": "VENTA_CONTADO",
                        "tenant_id": 1,
                        "branch_id": 1,
                        "payload": {
                            "id_sucursal": 1,
                            "metodo_tipo": "EFECTIVO",
                            "monto_recibido": 350.0,
                            "datos_facturacion": {"nit_ci": "7788990", "razon_social": "Cliente Contado"},
                            "items": [{"id_variante": 100, "cantidad": 2, "expected_unit_price": 150.0}],
                        },
                    }
                ]
            },
        )
        r_closed = res_closed.json()["results"][0]
        self.assertEqual(r_closed["status"], "reconciliation_required")
        self.assertTrue(r_closed["reconciliation_required"])
        self.assertEqual(r_closed["conflict_code"], "CAJA_CERRADA")

        # Verificar que la incidencia de caja fue persistida en t_sync_operacion (nunca descartada silenciosamente)
        with psycopg2.connect(**self.pg.params) as conn:
            with conn.cursor() as cur:
                cur.execute(
                    f"SELECT status, response_json FROM {self.schema}.t_sync_operacion WHERE operation_id = %s;",
                    (op_cash_sale,),
                )
                row_inc = cur.fetchone()
                self.assertIsNotNone(row_inc)
                self.assertEqual(row_inc[0], "reconciliation_required")

        # 4. Abrir sesión de caja activa para user 3 en sucursal 1 y reintentar la venta en efectivo
        with psycopg2.connect(**self.pg.params) as conn:
            with conn.cursor() as cur:
                cur.execute(
                    f"SELECT stock_actual, stock_disponible FROM {self.schema}.t_inventario WHERE id_sucursal = 1 AND id_variante = 100;"
                )
                stock_before = cur.fetchone()
                cur.execute(
                    f"""
                    INSERT INTO {self.schema}.t_caja_sesion (
                        id_caja, id_usuario, id_sucursal, id_empresa, monto_inicial, estado, observacion_apertura
                    ) VALUES (1, 3, 1, 1, 500.00, 'ABIERTA', 'Apertura test CU24W');
                    """
                )
            conn.commit()

        res_ok = self.client.post(
            "/api/sync/lote",
            headers=headers_cajero,
            json={
                "operations": [
                    {
                        "created_at": datetime.now(timezone.utc).isoformat(),
                        "operation_id": op_cash_sale,
                        "kind": "VENTA_CONTADO",
                        "tenant_id": 1,
                        "branch_id": 1,
                        "payload": {
                            "id_sucursal": 1,
                            "metodo_tipo": "EFECTIVO",
                            "monto_recibido": 350.0,
                            "datos_facturacion": {"nit_ci": "7788990", "razon_social": "Cliente Contado"},
                            "items": [{"id_variante": 100, "cantidad": 2, "expected_unit_price": 150.0}],
                        },
                    }
                ]
            },
        )
        self.assertEqual(res_ok.status_code, 200)
        r_ok = res_ok.json()["results"][0]
        self.assertEqual(r_ok["status"], "synced")
        self.assertFalse(r_ok["idempotent_replay"])
        self.assertEqual(r_ok["data"]["estado_venta"], "PAGADO")
        self.assertEqual(r_ok["data"]["total"], 300.0)
        self.assertEqual(r_ok["data"]["monto_recibido"], 350.0)
        self.assertEqual(r_ok["data"]["cambio"], 50.0)

        # 5. Reintento idempotente del mismo operation_id en /api/sync/lote NO duplica venta, cobro ni descuento de inventario
        res_replay = self.client.post(
            "/api/sync/lote",
            headers=headers_cajero,
            json={
                "operations": [
                    {
                        "created_at": datetime.now(timezone.utc).isoformat(),
                        "operation_id": op_cash_sale,
                        "kind": "VENTA_CONTADO",
                        "tenant_id": 1,
                        "branch_id": 1,
                        "payload": {
                            "id_sucursal": 1,
                            "metodo_tipo": "EFECTIVO",
                            "monto_recibido": 350.0,
                            "datos_facturacion": {"nit_ci": "7788990", "razon_social": "Cliente Contado"},
                            "items": [{"id_variante": 100, "cantidad": 2, "expected_unit_price": 150.0}],
                        },
                    }
                ]
            },
        )
        self.assertEqual(res_replay.status_code, 200)
        r_rep = res_replay.json()["results"][0]
        self.assertEqual(r_rep["status"], "synced")
        self.assertTrue(r_rep["idempotent_replay"])
        self.assertEqual(r_rep["data"]["id_venta"], r_ok["data"]["id_venta"])

        with psycopg2.connect(**self.pg.params) as conn:
            with conn.cursor() as cur:
                cur.execute(
                    f"SELECT stock_actual, stock_disponible FROM {self.schema}.t_inventario WHERE id_sucursal = 1 AND id_variante = 100;"
                )
                stock_after = cur.fetchone()
                self.assertEqual(stock_after[0], stock_before[0] - 2)
                self.assertEqual(stock_after[1], stock_before[1] - 2)

                cur.execute(f"SELECT COUNT(*) FROM {self.schema}.t_venta WHERE id_venta = %s;", (r_ok["data"]["id_venta"],))
                self.assertEqual(cur.fetchone()[0], 1)
                cur.execute(f"SELECT COUNT(*) FROM {self.schema}.t_pago WHERE id_venta = %s;", (r_ok["data"]["id_venta"],))
                self.assertEqual(cur.fetchone()[0], 1)

    def test_08_sync_lote_venta_contado_conflicts_and_reconciliation_cu39w(self):
        headers_cajero = self._headers_for_user(user_id=3, id_empresa=1, id_rol=105, rol="CAJERO")

        # Asegurar sesión de caja ABIERTA para user 3 en sucursal 1
        with psycopg2.connect(**self.pg.params) as conn:
            with conn.cursor() as cur:
                cur.execute(
                    f"SELECT id_sesion_caja FROM {self.schema}.t_caja_sesion WHERE id_usuario = 3 AND id_sucursal = 1 AND estado = 'ABIERTA';"
                )
                if not cur.fetchone():
                    cur.execute(
                        f"""
                        INSERT INTO {self.schema}.t_caja_sesion (
                            id_caja, id_usuario, id_sucursal, id_empresa, monto_inicial, estado, observacion_apertura
                        ) VALUES (1, 3, 1, 1, 500.00, 'ABIERTA', 'Apertura test CU39W');
                        """
                    )
            conn.commit()

        # 1. Conflicto de precio en VENTA_CONTADO (esperaba Bs. 120.00, servidor tiene Bs. 200.00 en variante 102)
        op_vta_price = f"op-vta-pr-{uuid.uuid4().hex[:10]}"
        res_pr = self.client.post(
            "/api/sync/lote",
            headers=headers_cajero,
            json={
                "operations": [
                    {
                        "created_at": datetime.now(timezone.utc).isoformat(),
                        "operation_id": op_vta_price,
                        "kind": "VENTA_CONTADO",
                        "tenant_id": 1,
                        "branch_id": 1,
                        "payload": {
                            "id_sucursal": 1,
                            "metodo_tipo": "EFECTIVO",
                            "monto_recibido": 200.0,
                            "items": [{"id_variante": 102, "cantidad": 1, "expected_unit_price": 120.0}],
                        },
                    }
                ]
            },
        )
        r_pr = res_pr.json()["results"][0]
        self.assertEqual(r_pr["status"], "reconciliation_required")
        self.assertTrue(r_pr["reconciliation_required"])
        self.assertEqual(r_pr["conflict_code"], "PRICE_CHANGED")
        self.assertEqual(r_pr["conflict_detail"]["current_unit_price"], 200.0)

        # 2. Conflicto de stock insuficiente en VENTA_CONTADO (solicita 50, disponibles 12 en variante 102)
        op_vta_stock = f"op-vta-st-{uuid.uuid4().hex[:10]}"
        res_st = self.client.post(
            "/api/sync/lote",
            headers=headers_cajero,
            json={
                "operations": [
                    {
                        "created_at": datetime.now(timezone.utc).isoformat(),
                        "operation_id": op_vta_stock,
                        "kind": "VENTA_CONTADO",
                        "tenant_id": 1,
                        "branch_id": 1,
                        "payload": {
                            "id_sucursal": 1,
                            "metodo_tipo": "EFECTIVO",
                            "monto_recibido": 10000.0,
                            "items": [{"id_variante": 102, "cantidad": 50, "expected_unit_price": 200.0}],
                        },
                    }
                ]
            },
        )
        r_st = res_st.json()["results"][0]
        self.assertEqual(r_st["status"], "reconciliation_required")
        self.assertTrue(r_st["reconciliation_required"])
        self.assertEqual(r_st["conflict_code"], "STOCK_INSUFFICIENT")
        self.assertEqual(r_st["conflict_detail"]["available_stock"], 12)

        # Verificar que ambas incidencias quedaron persistidas en t_sync_operacion para conciliación
        with psycopg2.connect(**self.pg.params) as conn:
            with conn.cursor() as cur:
                cur.execute(
                    f"SELECT status FROM {self.schema}.t_sync_operacion WHERE operation_id IN (%s, %s);",
                    (op_vta_price, op_vta_stock),
                )
                rows_st = cur.fetchall()
                self.assertEqual(len(rows_st), 2)
                for row in rows_st:
                    self.assertEqual(row[0], "reconciliation_required")

        # 3. Resolución CU39W: ajustar cantidad a stock disponible (2 unidades) y reenviar mismo operation_id
        res_st_resolved = self.client.post(
            "/api/sync/lote",
            headers=headers_cajero,
            json={
                "operations": [
                    {
                        "created_at": datetime.now(timezone.utc).isoformat(),
                        "operation_id": op_vta_stock,
                        "kind": "VENTA_CONTADO",
                        "tenant_id": 1,
                        "branch_id": 1,
                        "payload": {
                            "id_sucursal": 1,
                            "metodo_tipo": "EFECTIVO",
                            "monto_recibido": 400.0,
                            "items": [{"id_variante": 102, "cantidad": 2, "expected_unit_price": 200.0}],
                        },
                    }
                ]
            },
        )
        r_resolved = res_st_resolved.json()["results"][0]
        self.assertEqual(r_resolved["status"], "synced")
        self.assertEqual(r_resolved["data"]["estado_venta"], "PAGADO")
        self.assertEqual(r_resolved["data"]["total"], 400.0)


if __name__ == "__main__":
    unittest.main()
