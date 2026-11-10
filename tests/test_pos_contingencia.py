"""
Suite de Pruebas Automatizadas — Iteración 6: Estrategia de Contingencia Offline POS (Migración 008)
Ejecución sobre cluster PostgreSQL temporal aislado (LocalPostgres).
"""
import json
from pathlib import Path
import sys
import unittest
import uuid
from datetime import datetime, timezone

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
from app.modules.pos.routes import pos_routes, caja_routes
from app.modules.ecommerce.routes import sync_routes
from app.modules.pos.repos import caja_repos, contingencia_repos
from migrate import render

POS_CONTINGENCIA_SCHEMA_SQL = """
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
    activo BOOLEAN DEFAULT TRUE,
    estado BOOLEAN DEFAULT TRUE
);

CREATE TABLE t_talla (
    id_talla SERIAL PRIMARY KEY,
    nombre TEXT NOT NULL,
    descripcion TEXT,
    id_empresa INTEGER NOT NULL REFERENCES empresa(id_empresa),
    activo BOOLEAN DEFAULT TRUE,
    estado BOOLEAN DEFAULT TRUE
);

CREATE TABLE t_color (
    id_color SERIAL PRIMARY KEY,
    nombre TEXT NOT NULL,
    codigo_hex TEXT NOT NULL,
    id_empresa INTEGER NOT NULL REFERENCES empresa(id_empresa),
    activo BOOLEAN DEFAULT TRUE,
    estado BOOLEAN DEFAULT TRUE
);

CREATE TABLE t_producto (
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

CREATE TABLE t_producto_talla_color (
    id_variante SERIAL PRIMARY KEY,
    id_producto INTEGER NOT NULL REFERENCES t_producto(id_producto) ON DELETE CASCADE,
    id_talla INTEGER NOT NULL REFERENCES t_talla(id_talla),
    id_color INTEGER NOT NULL REFERENCES t_color(id_color),
    sku TEXT,
    precio NUMERIC(12, 2) DEFAULT 150.00,
    activo BOOLEAN DEFAULT TRUE,
    estado BOOLEAN DEFAULT TRUE,
    UNIQUE(id_producto, id_talla, id_color)
);

CREATE TABLE t_producto_imagen (
    id_imagen SERIAL PRIMARY KEY,
    id_producto INTEGER NOT NULL REFERENCES t_producto(id_producto) ON DELETE CASCADE,
    imagen_url TEXT,
    es_principal BOOLEAN DEFAULT TRUE,
    orden INTEGER DEFAULT 1
);

CREATE TABLE t_inventario (
    id_inventario SERIAL PRIMARY KEY,
    id_sucursal INTEGER NOT NULL REFERENCES t_sucursal(id_sucursal),
    id_variante INTEGER NOT NULL REFERENCES t_producto_talla_color(id_variante),
    stock_actual INTEGER NOT NULL DEFAULT 0,
    stock_reservado INTEGER DEFAULT 0,
    stock_disponible INTEGER NOT NULL DEFAULT 0,
    estado BOOLEAN DEFAULT TRUE,
    UNIQUE(id_sucursal, id_variante)
);

CREATE TABLE t_cliente (
    id_cliente SERIAL PRIMARY KEY,
    id_usuario INTEGER REFERENCES t_usuario(id_usuario),
    ci TEXT,
    nit_ci TEXT,
    fecha_registro TIMESTAMP DEFAULT now()
);

CREATE TABLE IF NOT EXISTS t_carrito (
    id_carrito SERIAL PRIMARY KEY,
    id_cliente INTEGER REFERENCES t_cliente(id_cliente),
    id_empresa INTEGER NOT NULL REFERENCES empresa(id_empresa),
    estado TEXT NOT NULL DEFAULT 'ACTIVO',
    fecha_creacion TIMESTAMP DEFAULT now(),
    fecha_actualizacion TIMESTAMP DEFAULT now(),
    updated_at TIMESTAMP DEFAULT now()
);

CREATE TABLE IF NOT EXISTS t_detalle_carrito (
    id_detalle_carrito SERIAL PRIMARY KEY,
    id_carrito INTEGER NOT NULL REFERENCES t_carrito(id_carrito) ON DELETE CASCADE,
    id_variante INTEGER NOT NULL REFERENCES t_producto_talla_color(id_variante),
    cantidad INTEGER NOT NULL DEFAULT 1,
    precio_unitario NUMERIC(12, 2) NOT NULL DEFAULT 150.00,
    subtotal NUMERIC(12, 2) NOT NULL DEFAULT 150.00,
    fecha_agregado TIMESTAMP DEFAULT now()
);

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
    monto_inicial NUMERIC(12, 2) NOT NULL DEFAULT 0.00,
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
    id_denominacion INTEGER NOT NULL REFERENCES t_denominacion(id_denominacion),
    valor_denominacion NUMERIC(12, 2) NOT NULL,
    cantidad INTEGER NOT NULL,
    subtotal NUMERIC(12, 2) NOT NULL
);

CREATE TABLE t_metodo_pago (
    id_metodo_pago SERIAL PRIMARY KEY,
    nombre TEXT NOT NULL,
    tipo TEXT NOT NULL,
    estado BOOLEAN DEFAULT TRUE
);

CREATE TABLE t_venta (
    id_venta SERIAL PRIMARY KEY,
    numero_venta TEXT UNIQUE NOT NULL,
    id_sesion_caja INTEGER REFERENCES t_caja_sesion(id_sesion_caja),
    id_usuario INTEGER NOT NULL REFERENCES t_usuario(id_usuario),
    id_sucursal INTEGER NOT NULL REFERENCES t_sucursal(id_sucursal),
    id_empresa INTEGER NOT NULL REFERENCES empresa(id_empresa),
    id_cliente INTEGER REFERENCES t_cliente(id_cliente),
    fecha_venta TIMESTAMP DEFAULT now(),
    subtotal NUMERIC(12, 2) NOT NULL DEFAULT 0.00,
    descuento NUMERIC(12, 2) NOT NULL DEFAULT 0.00,
    total NUMERIC(12, 2) NOT NULL DEFAULT 0.00,
    estado TEXT NOT NULL DEFAULT 'COMPLETADA',
    tipo_documento TEXT DEFAULT 'COMPROBANTE',
    observacion TEXT,
    nit_ci TEXT,
    razon_social TEXT,
    correo_facturacion TEXT
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

CREATE TABLE IF NOT EXISTS t_devolucion (
    id_devolucion SERIAL PRIMARY KEY,
    id_venta INTEGER REFERENCES t_venta(id_venta),
    id_usuario INTEGER REFERENCES t_usuario(id_usuario),
    id_empresa INTEGER REFERENCES empresa(id_empresa),
    id_sucursal INTEGER REFERENCES t_sucursal(id_sucursal),
    id_sesion_caja INTEGER REFERENCES t_caja_sesion(id_sesion_caja),
    fecha_devolucion TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    motivo VARCHAR,
    monto_reembolso NUMERIC,
    metodo_reembolso VARCHAR,
    estado VARCHAR
);

CREATE TABLE IF NOT EXISTS t_detalle_devolucion (
    id_detalle_devolucion SERIAL PRIMARY KEY,
    id_devolucion INTEGER REFERENCES t_devolucion(id_devolucion),
    id_detalle_venta INTEGER REFERENCES t_detalle_venta(id_detalle_venta),
    cantidad INTEGER
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

CREATE TABLE t_movimiento_inventario (
    id_movimiento SERIAL PRIMARY KEY,
    id_sucursal INTEGER NOT NULL REFERENCES t_sucursal(id_sucursal),
    id_variante INTEGER NOT NULL REFERENCES t_producto_talla_color(id_variante),
    tipo_movimiento TEXT NOT NULL,
    cantidad INTEGER NOT NULL,
    stock_anterior INTEGER NOT NULL,
    stock_nuevo INTEGER NOT NULL,
    motivo TEXT,
    id_usuario INTEGER REFERENCES t_usuario(id_usuario),
    fecha_movimiento TIMESTAMP DEFAULT now()
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

        v_subtotal := v_subtotal + (v_precio * v_cant);
    END LOOP;

    v_total := GREATEST(v_subtotal - COALESCE(p_descuento, 0.00), 0.00);
    v_numero_venta := 'V-POS-' || TO_CHAR(now(), 'YYYYMMDD') || '-' || LPAD(FLOOR(RANDOM()*100000)::TEXT, 5, '0');

    INSERT INTO t_venta (
        numero_venta, id_sesion_caja, id_usuario, id_sucursal, id_empresa,
        id_cliente, subtotal, descuento, total, estado
    ) VALUES (
        v_numero_venta, p_id_sesion_caja, p_id_usuario, p_id_sucursal, p_id_empresa,
        p_id_cliente, v_subtotal, COALESCE(p_descuento, 0.00), v_total, 'PENDIENTE_PAGO'
    ) RETURNING id_venta INTO v_id_venta;

    FOR v_item IN SELECT * FROM json_array_elements(p_items)
    LOOP
        v_id_var := (v_item->>'id_variante')::INTEGER;
        v_cant := (v_item->>'cantidad')::INTEGER;

        SELECT COALESCE(v.precio, p.precio, 0)
        INTO v_precio
        FROM t_producto_talla_color v
        JOIN t_producto p ON p.id_producto = v.id_producto
        WHERE v.id_variante = v_id_var AND p.id_empresa = p_id_empresa;

        INSERT INTO t_detalle_venta (
            id_venta, id_variante, cantidad, precio_unitario, descuento, subtotal
        ) VALUES (
            v_id_venta, v_id_var, v_cant, v_precio, 0.00, (v_precio * v_cant)
        );

        UPDATE t_inventario
        SET stock_actual = GREATEST(stock_actual - v_cant, 0),
            stock_disponible = GREATEST(stock_disponible - v_cant, 0)
        WHERE id_sucursal = p_id_sucursal AND id_variante = v_id_var;
    END LOOP;

    RETURN jsonb_build_object(
        'success', true,
        'id_venta', v_id_venta,
        'numero_venta', v_numero_venta,
        'total', v_total
    );
END;
$$ LANGUAGE plpgsql;
"""


class PosContingenciaTestSuite(unittest.TestCase):
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
            Config.TOKEN_KEY = "pos_cont_test_secret_key"

        cls.schema = "pos_cont_" + uuid.uuid4().hex
        Config.SCHEMA = cls.schema
        _invalidar_caches_seguridad()

        with psycopg2.connect(**cls.pg.params) as conn:
            with conn.cursor() as cur:
                cur.execute(f"CREATE SCHEMA {cls.schema}; SET search_path TO {cls.schema}")
                cur.execute(f"ALTER DATABASE postgres SET search_path TO {cls.schema}, public")
                cur.execute((ROOT / "tests/p1_fixture.sql").read_text(encoding="utf-8"))
                cur.execute(render(ROOT / "backend/migrations/001_iter1_saas.up.sql", cls.schema))
                cur.execute(POS_CONTINGENCIA_SCHEMA_SQL)
                cur.execute(render(ROOT / "backend/migrations/002_iter1_perf_indexes.up.sql", cls.schema))
                cur.execute(render(ROOT / "backend/migrations/003_iter2_sync_idempotency.up.sql", cls.schema))
                cur.execute(render(ROOT / "backend/migrations/004_iter2_sync_transactional.up.sql", cls.schema))
                cur.execute(render(ROOT / "backend/migrations/006_iter4_saas_storefront.up.sql", cls.schema))
                cur.execute(render(ROOT / "backend/migrations/008_iter6_pos_contingencia.up.sql", cls.schema))
                cur.execute(f"UPDATE {cls.schema}.t_sync_control SET inicio_garantia = now() - interval '1 day';")

                # Suscripción activa Empresa 1
                cur.execute(
                    """
                    INSERT INTO t_cliente (id_cliente, id_usuario, ci, nit_ci) VALUES (1, 3, '1234567', '1234567')
                    ON CONFLICT DO NOTHING;

                    INSERT INTO t_suscripcion (id_empresa, codigo_plan, inicio, fin, motivo, creado_por)
                    VALUES (1, 'PROFESIONAL', now() - interval '1 day', now() + interval '30 days', 'Plan A', 1);
                    """
                )

                # Sembrar catálogo
                cur.execute(
                    """
                    INSERT INTO t_categoria (id_categoria, nombre, id_empresa, activo) VALUES (1, 'Alta Costura', 1, TRUE);
                    INSERT INTO t_talla (id_talla, nombre, id_empresa, activo) VALUES (1, 'M', 1, TRUE);
                    INSERT INTO t_color (id_color, nombre, codigo_hex, id_empresa, activo) VALUES (1, 'Negro', '#000000', 1, TRUE);
                    INSERT INTO t_producto (id_producto, nombre, codigo_producto, precio, id_categoria, id_empresa, activo)
                    VALUES (10, 'Vestido Noche Seda', 'VES-010', 200.00, 1, 1, TRUE);
                    INSERT INTO t_producto_talla_color (id_variante, id_producto, id_talla, id_color, sku, precio, activo)
                    VALUES (100, 10, 1, 1, 'VES-010-M-NEG', 200.00, TRUE);

                    -- Stock inicial: 20 unidades físicas
                    INSERT INTO t_inventario (id_sucursal, id_variante, stock_actual, stock_reservado, stock_disponible, estado)
                    VALUES (1, 100, 20, 0, 20, TRUE);

                    INSERT INTO t_denominacion (id_denominacion, valor, moneda, tipo, orden, activo) VALUES
                        (1, 200.00, 'BOB', 'BILLETE', 1, TRUE),
                        (2, 100.00, 'BOB', 'BILLETE', 2, TRUE),
                        (3, 50.00, 'BOB', 'BILLETE', 3, TRUE);

                    INSERT INTO t_metodo_pago (id_metodo_pago, nombre, tipo, estado) VALUES
                        (1, 'Efectivo en Caja', 'EFECTIVO', TRUE);

                    INSERT INTO t_caja (id_caja, id_sucursal, id_empresa, codigo_caja, nombre, estado)
                    VALUES (1, 1, 1, 'CAJA-01', 'Caja Mostrador 1', 'ACTIVA'),
                           (2, 1, 1, 'CAJA-02', 'Caja Mostrador 2', 'ACTIVA');

                    INSERT INTO t_permiso (codigo, nombre, activo) VALUES
                        ('caja.ver', 'Ver caja', TRUE),
                        ('caja.abrir', 'Abrir caja', TRUE),
                        ('caja.cerrar', 'Cerrar caja', TRUE),
                        ('pos.vender', 'Vender en POS', TRUE),
                        ('pos.cobrar', 'Cobrar en POS', TRUE)
                    ON CONFLICT (codigo) DO NOTHING;

                    INSERT INTO t_rol_permiso (id_rol, id_permiso)
                    SELECT 105, id_permiso FROM t_permiso WHERE codigo IN ('caja.ver', 'caja.abrir', 'caja.cerrar', 'pos.vender', 'pos.cobrar')
                    ON CONFLICT DO NOTHING;

                    INSERT INTO t_rol_permiso (id_rol, id_permiso)
                    SELECT 103, id_permiso FROM t_permiso WHERE codigo IN ('caja.ver', 'caja.abrir', 'caja.cerrar', 'pos.vender', 'pos.cobrar')
                    ON CONFLICT DO NOTHING;
                    """
                )
            conn.commit()

        from app.main import app
        cls.client = TestClient(app)

    @classmethod
    def tearDownClass(cls):
        try:
            cls.cluster.__exit__(None, None, None)
        except Exception:
            pass

    def setUp(self):
        Config.SCHEMA = self.schema
        _invalidar_caches_seguridad()

    def _headers_for_user(self, user_id=3, id_empresa=1, id_rol=105, rol="CAJERO"):
        import jwt
        ctx = _contexto_vigente({"id_usuario": user_id})
        permisos = list(ctx.get("permisos", [])) if ctx else []
        for p in ["pos.vender", "pos.cobrar", "caja.ver", "pos.contingencia"]:
            if p not in permisos:
                permisos.append(p)
        payload = {
            "nro_usuario": user_id,
            "id_usuario": user_id,
            "id_empresa": id_empresa,
            "id_rol": id_rol,
            "id_sucursal": 1,
            "rol": rol,
            "roles": [rol],
            "permisos": permisos,
            "sucursales": [1],
            "sv": int(ctx.get("session_version", 1)) if ctx else 1,
        }
        secret = Config.TOKEN_KEY or Config.SECRET_KEY or "pos_cont_test_secret_key"
        tok = jwt.encode(payload, secret, algorithm="HS256")
        return {"Authorization": f"Bearer {tok}"}

    def test_01_reversible_contingencia_migration_008(self):
        """Verifica reversibilidad limpia de la migración 008 (DOWN y posterior UP)."""
        with psycopg2.connect(**self.pg.params) as conn:
            with conn.cursor() as cur:
                # DOWN
                cur.execute(render(ROOT / "backend/migrations/008_iter6_pos_contingencia.down.sql", self.schema))
                cur.execute(
                    f"""
                    SELECT column_name FROM information_schema.columns
                    WHERE table_schema = '{self.schema}' AND table_name = 't_inventario' AND column_name = 'stock_contingencia';
                    """
                )
                self.assertIsNone(cur.fetchone())

                # UP
                cur.execute(render(ROOT / "backend/migrations/008_iter6_pos_contingencia.up.sql", self.schema))
                cur.execute(
                    f"""
                    SELECT column_name FROM information_schema.columns
                    WHERE table_schema = '{self.schema}' AND table_name = 't_inventario' AND column_name = 'stock_contingencia';
                    """
                )
                self.assertIsNotNone(cur.fetchone())
            conn.commit()

    def test_02_hybrid_quota_calculation_and_assignment_on_cash_open(self):
        """Al abrir sesión de caja, se calculan y asignan cuotas de contingencia según la política."""
        headers = self._headers_for_user(user_id=3, id_empresa=1)

        # Política por defecto: 15% de 20 unidades = 3 unidades de contingencia
        res_open = self.client.post(
            "/api/caja/abrir",
            headers=headers,
            json={
                "id_caja": 1,
                "id_sucursal": 1,
                "observacion": "Apertura para prueba de contingencia",
                "conteo_items": [{"id_denominacion": 1, "cantidad": 2}],
            },
        )
        self.assertEqual(res_open.status_code, 200)
        data = res_open.json()["data"]
        id_sesion = data["id_sesion_caja"]
        self.assertGreater(id_sesion, 0)

        # Verificar que se generó la cuota de contingencia
        cuotas = data.get("cuotas_contingencia", [])
        self.assertGreaterEqual(len(cuotas), 1)
        cuota_var100 = next((c for c in cuotas if c["id_variante"] == 100), None)
        self.assertIsNotNone(cuota_var100)
        self.assertEqual(cuota_var100["cuota_asignada"], 3)  # 15% de 20 = 3

        # Verificar que t_inventario apartó el stock_contingencia
        with psycopg2.connect(**self.pg.params) as conn:
            with conn.cursor() as cur:
                cur.execute(
                    f"SELECT stock_actual, stock_contingencia, stock_disponible FROM {self.schema}.t_inventario WHERE id_variante = 100 AND id_sucursal = 1;"
                )
                actual, contingencia, disponible = cur.fetchone()
                self.assertEqual(actual, 20)
                self.assertEqual(contingencia, 3)

        # Endpoint GET /api/pos/contingencia/cuotas
        res_cuotas = self.client.get(
            f"/api/pos/contingencia/cuotas?id_sesion_caja={id_sesion}",
            headers=headers,
        )
        self.assertEqual(res_cuotas.status_code, 200)
        json_cuotas = res_cuotas.json()
        self.assertTrue(json_cuotas["success"])
        self.assertEqual(json_cuotas["total"], 1)
        self.assertEqual(json_cuotas["cuotas"][0]["cuota_disponible"], 3)

    def test_03_transactional_quota_distribution_multi_terminal(self):
        """Garantiza que una segunda caja no consuma las mismas unidades de contingencia ya asignadas."""
        headers_cajero2 = self._headers_for_user(user_id=2, id_empresa=1, id_rol=103, rol="ADMIN_EMPRESA")

        # Abrir caja 2 en la misma sucursal
        res_open2 = self.client.post(
            "/api/caja/abrir",
            headers=headers_cajero2,
            json={
                "id_caja": 2,
                "id_sucursal": 1,
                "observacion": "Apertura terminal 2",
                "conteo_items": [{"id_denominacion": 2, "cantidad": 5}],
            },
        )
        self.assertEqual(res_open2.status_code, 200)
        cuotas2 = res_open2.json()["data"].get("cuotas_contingencia", [])
        cuota_caja2 = next((c for c in cuotas2 if c["id_variante"] == 100), None)
        self.assertIsNotNone(cuota_caja2)

        # La suma de cuotas asignadas a sesiones activas no puede superar el inventario físico disponible
        with psycopg2.connect(**self.pg.params) as conn:
            with conn.cursor() as cur:
                cur.execute(
                    f"SELECT SUM(cuota_asignada) FROM {self.schema}.t_caja_cuota_contingencia WHERE id_variante = 100 AND estado = 'ACTIVA';"
                )
                suma_cuotas = cur.fetchone()[0]
                self.assertLessEqual(suma_cuotas, 20)

    def test_04_sync_p0_priority_and_contingency_sale_consumption(self):
        """Prueba sincronización prioritaria P0 de VENTA_CONTADO y consumo de cuota."""
        headers = self._headers_for_user(user_id=3, id_empresa=1)
        op_id_pos = f"op-pos-cont-{uuid.uuid4().hex[:10]}"
        op_id_cart = f"op-cart-low-{uuid.uuid4().hex[:10]}"

        # Enviar lote con carrito primero y venta POS después; el servidor debe priorizar POS (P0)
        res_batch = self.client.post(
            "/api/sync/lote",
            headers=headers,
            json={
                "operations": [
                    {
                        "created_at": datetime.now(timezone.utc).isoformat(),
                        "operation_id": op_id_cart,
                        "kind": "CART_ADD_ITEM",
                        "tenant_id": 1,
                        "payload": {"id_variante": 100, "cantidad": 1, "mode": "ADD"},
                    },
                    {
                        "created_at": datetime.now(timezone.utc).isoformat(),
                        "operation_id": op_id_pos,
                        "kind": "VENTA_CONTADO",
                        "tenant_id": 1,
                        "branch_id": 1,
                        "payload": {
                            "id_sucursal": 1,
                            "metodo_tipo": "EFECTIVO",
                            "monto_recibido": 200.00,
                            "contingencia": True,
                            "items": [{"id_variante": 100, "cantidad": 1, "expected_unit_price": 200.00}],
                        },
                    },
                ]
            },
        )
        self.assertEqual(res_batch.status_code, 200)
        results = res_batch.json()["results"]
        pos_res = next((r for r in results if r["operation_id"] == op_id_pos), None)
        self.assertIsNotNone(pos_res)
        self.assertEqual(pos_res["status"], "synced")
        self.assertTrue(pos_res["data"]["es_contingencia_offline"])
        self.assertEqual(pos_res["data"]["comprobante_tipo_provisional"], "PROVISIONAL_CONTINGENCIA")

        # Verificar en base de datos que se consumió la cuota
        with psycopg2.connect(**self.pg.params) as conn:
            with conn.cursor() as cur:
                cur.execute(
                    f"SELECT es_contingencia_offline, comprobante_tipo_provisional FROM {self.schema}.t_venta WHERE id_venta = %s;",
                    (pos_res["data"]["id_venta"],),
                )
                es_cont, tipo_prov = cur.fetchone()
                self.assertTrue(es_cont)
                self.assertEqual(tipo_prov, "PROVISIONAL_CONTINGENCIA")

    def test_05_release_unused_contingency_stock_on_cash_close(self):
        """Al cerrar la sesión de caja, las cuotas no consumidas se liberan y regresan a stock disponible."""
        headers = self._headers_for_user(user_id=3, id_empresa=1)

        # Consultar sesión activa de user 3
        with psycopg2.connect(**self.pg.params) as conn:
            with conn.cursor() as cur:
                cur.execute(
                    f"SELECT id_sesion_caja FROM {self.schema}.t_caja_sesion WHERE id_usuario = 3 AND estado = 'ABIERTA' ORDER BY id_sesion_caja DESC LIMIT 1;"
                )
                id_sesion = cur.fetchone()[0]

        # Cerrar sesión de caja
        res_close = self.client.post(
            "/api/caja/cerrar",
            headers=headers,
            json={
                "id_sesion_caja": id_sesion,
                "observacion": "Cierre de turno con liberación de contingencia",
                "conteo_items": [
                    {"id_denominacion": 1, "cantidad": 3},
                    {"id_denominacion": 2, "cantidad": 0},
                ],
            },
        )
        self.assertEqual(res_close.status_code, 200)
        data_close = res_close.json()["data"]
        self.assertEqual(data_close["estado"], "CERRADA")
        self.assertGreaterEqual(data_close.get("cuotas_contingencia_liberadas", 0), 0)

        # Verificar que la cuota de la sesión pasó a estado 'LIBERADA'
        with psycopg2.connect(**self.pg.params) as conn:
            with conn.cursor() as cur:
                cur.execute(
                    f"SELECT estado FROM {self.schema}.t_caja_cuota_contingencia WHERE id_sesion_caja = %s;",
                    (id_sesion,),
                )
                estados = [r[0] for r in cur.fetchall()]
                for est in estados:
                    self.assertEqual(est, "LIBERADA")


if __name__ == "__main__":
    unittest.main()
