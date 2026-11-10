"""
Suite de Pruebas Automatizadas — Iteración 3: Devoluciones Online (CU24W / CU25W)
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
from app.core.security import _contexto_vigente, verificar_token, require_permission
from app.modules.pedidos.routes import devoluciones_routes
from migrate import render

DEVOLUCIONES_BASE_SCHEMA = """
ALTER TABLE empresa
    ADD COLUMN IF NOT EXISTS razon_social TEXT,
    ADD COLUMN IF NOT EXISTS logo TEXT,
    ADD COLUMN IF NOT EXISTS ciudad TEXT DEFAULT 'Santa Cruz',
    ADD COLUMN IF NOT EXISTS politica_devolucion JSONB DEFAULT '{"dias_limite_cambio": 15, "dias_limite_defecto": 90, "permite_cambio": true, "permite_saldo_favor": true, "permite_reembolso": true}'::jsonb;

INSERT INTO t_rol (id_rol, nombre, descripcion) 
VALUES (104, 'ENCARGADO_SUCURSAL', 'Encargado de Sucursal')
ON CONFLICT (id_rol) DO NOTHING;

CREATE TABLE IF NOT EXISTS t_categoria (
    id_categoria SERIAL PRIMARY KEY,
    nombre TEXT NOT NULL,
    id_empresa INTEGER NOT NULL REFERENCES empresa(id_empresa),
    estado BOOLEAN DEFAULT TRUE
);

CREATE TABLE IF NOT EXISTS t_talla (
    id_talla SERIAL PRIMARY KEY,
    nombre TEXT NOT NULL,
    id_empresa INTEGER NOT NULL REFERENCES empresa(id_empresa),
    estado BOOLEAN DEFAULT TRUE
);

CREATE TABLE IF NOT EXISTS t_color (
    id_color SERIAL PRIMARY KEY,
    nombre TEXT NOT NULL,
    codigo_hex TEXT NOT NULL,
    id_empresa INTEGER NOT NULL REFERENCES empresa(id_empresa),
    estado BOOLEAN DEFAULT TRUE
);

CREATE TABLE IF NOT EXISTS t_producto (
    id_producto SERIAL PRIMARY KEY,
    nombre TEXT NOT NULL,
    id_categoria INTEGER REFERENCES t_categoria(id_categoria),
    id_empresa INTEGER NOT NULL REFERENCES empresa(id_empresa),
    precio NUMERIC(12, 2) NOT NULL DEFAULT 150.00,
    estado BOOLEAN DEFAULT TRUE
);

CREATE TABLE IF NOT EXISTS t_producto_imagen (
    id_imagen SERIAL PRIMARY KEY,
    id_producto INTEGER NOT NULL REFERENCES t_producto(id_producto),
    imagen_url TEXT NOT NULL,
    es_principal BOOLEAN DEFAULT FALSE,
    orden INTEGER DEFAULT 1
);

CREATE TABLE IF NOT EXISTS t_producto_talla_color (
    id_variante SERIAL PRIMARY KEY,
    id_producto INTEGER NOT NULL REFERENCES t_producto(id_producto),
    id_talla INTEGER NOT NULL REFERENCES t_talla(id_talla),
    id_color INTEGER NOT NULL REFERENCES t_color(id_color),
    sku TEXT UNIQUE NOT NULL,
    precio NUMERIC(12, 2) DEFAULT 150.00,
    estado BOOLEAN DEFAULT TRUE
);

CREATE TABLE IF NOT EXISTS t_inventario (
    id_inventario SERIAL PRIMARY KEY,
    id_sucursal INTEGER NOT NULL REFERENCES t_sucursal(id_sucursal),
    id_variante INTEGER NOT NULL REFERENCES t_producto_talla_color(id_variante),
    stock_actual INTEGER NOT NULL DEFAULT 0,
    stock_reservado INTEGER NOT NULL DEFAULT 0,
    stock_disponible INTEGER NOT NULL DEFAULT 0,
    stock_minimo INTEGER NOT NULL DEFAULT 2,
    estado BOOLEAN DEFAULT TRUE,
    fecha_actualizacion TIMESTAMP DEFAULT now()
);

CREATE TABLE IF NOT EXISTS t_movimiento_inventario (
    id_movimiento SERIAL PRIMARY KEY,
    id_inventario INTEGER NOT NULL REFERENCES t_inventario(id_inventario),
    id_usuario INTEGER NOT NULL REFERENCES t_usuario(id_usuario),
    tipo_movimiento VARCHAR(40) NOT NULL,
    cantidad INTEGER NOT NULL,
    stock_anterior INTEGER NOT NULL,
    stock_nuevo INTEGER NOT NULL,
    motivo VARCHAR(255),
    fecha_movimiento TIMESTAMP DEFAULT now()
);

CREATE TABLE IF NOT EXISTS t_cliente (
    id_cliente SERIAL PRIMARY KEY,
    id_usuario INTEGER NOT NULL UNIQUE REFERENCES t_usuario(id_usuario),
    ci TEXT,
    telefono TEXT
);

CREATE TABLE IF NOT EXISTS t_metodo_pago (
    id_metodo_pago SERIAL PRIMARY KEY,
    nombre TEXT NOT NULL,
    tipo TEXT NOT NULL,
    estado BOOLEAN DEFAULT TRUE
);

CREATE TABLE IF NOT EXISTS t_venta (
    id_venta SERIAL PRIMARY KEY,
    id_cliente INTEGER REFERENCES t_cliente(id_cliente),
    id_sucursal INTEGER REFERENCES t_sucursal(id_sucursal),
    id_usuario INTEGER REFERENCES t_usuario(id_usuario),
    numero_venta TEXT UNIQUE NOT NULL,
    tipo_venta TEXT DEFAULT 'ONLINE',
    fecha_venta TIMESTAMP DEFAULT now(),
    subtotal NUMERIC(12, 2) NOT NULL,
    descuento NUMERIC(12, 2) DEFAULT 0,
    total NUMERIC(12, 2) NOT NULL,
    estado TEXT NOT NULL DEFAULT 'COMPLETADA',
    observacion TEXT,
    id_empresa INTEGER NOT NULL REFERENCES empresa(id_empresa),
    nit_ci TEXT,
    razon_social TEXT,
    tipo_documento TEXT DEFAULT 'COMPROBANTE',
    id_sesion_caja INTEGER,
    correo_facturacion TEXT
);

CREATE TABLE IF NOT EXISTS t_caja (
    id_caja SERIAL PRIMARY KEY,
    id_sucursal INTEGER REFERENCES t_sucursal(id_sucursal),
    id_empresa INTEGER REFERENCES empresa(id_empresa),
    nombre TEXT DEFAULT 'Caja 1',
    estado TEXT DEFAULT 'ACTIVA'
);

CREATE TABLE IF NOT EXISTS t_caja_sesion (
    id_sesion_caja SERIAL PRIMARY KEY,
    id_caja INTEGER REFERENCES t_caja(id_caja),
    id_usuario INTEGER REFERENCES t_usuario(id_usuario),
    id_sucursal INTEGER REFERENCES t_sucursal(id_sucursal),
    id_empresa INTEGER REFERENCES empresa(id_empresa),
    fecha_apertura TIMESTAMP DEFAULT now(),
    fecha_cierre TIMESTAMP,
    monto_inicial NUMERIC(12, 2) NOT NULL DEFAULT 0.00,
    estado TEXT NOT NULL DEFAULT 'ABIERTA'
);

CREATE TABLE IF NOT EXISTS t_pedido (
    id_pedido SERIAL PRIMARY KEY,
    id_venta INTEGER REFERENCES t_venta(id_venta),
    codigo_pedido TEXT,
    nombre_contacto TEXT
);

CREATE TABLE IF NOT EXISTS t_pago (
    id_pago SERIAL PRIMARY KEY,
    id_venta INTEGER REFERENCES t_venta(id_venta),
    id_metodo_pago INTEGER REFERENCES t_metodo_pago(id_metodo_pago),
    monto NUMERIC(12, 2) NOT NULL,
    codigo_transaccion TEXT,
    estado TEXT DEFAULT 'APROBADO'
);

CREATE TABLE IF NOT EXISTS t_detalle_venta (
    id_detalle_venta SERIAL PRIMARY KEY,
    id_venta INTEGER NOT NULL REFERENCES t_venta(id_venta) ON DELETE CASCADE,
    id_variante INTEGER NOT NULL REFERENCES t_producto_talla_color(id_variante),
    cantidad INTEGER NOT NULL,
    precio_unitario NUMERIC(12, 2) NOT NULL,
    descuento NUMERIC(12, 2) DEFAULT 0,
    subtotal NUMERIC(12, 2) NOT NULL
);

CREATE TABLE IF NOT EXISTS t_devolucion (
    id_devolucion SERIAL PRIMARY KEY,
    id_venta INTEGER REFERENCES t_venta(id_venta),
    id_usuario INTEGER REFERENCES t_usuario(id_usuario),
    fecha_devolucion TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    motivo VARCHAR,
    monto_reembolso NUMERIC,
    estado VARCHAR
);

CREATE TABLE IF NOT EXISTS t_detalle_devolucion (
    id_detalle_devolucion SERIAL PRIMARY KEY,
    id_devolucion INTEGER REFERENCES t_devolucion(id_devolucion),
    id_detalle_venta INTEGER REFERENCES t_detalle_venta(id_detalle_venta),
    cantidad INTEGER
);
"""

class TestDevolucionesIteracion3(unittest.TestCase):
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
            Config.TOKEN_KEY = "iter3_dev_test_secret_key"

        cls.schema = f"dev_{uuid.uuid4().hex[:10]}"
        Config.SCHEMA = cls.schema
        _invalidar_caches_seguridad()

        with psycopg2.connect(**cls.pg.params) as conn:
            with conn.cursor() as cur:
                cur.execute(f"CREATE SCHEMA {cls.schema}; SET search_path TO {cls.schema};")
                cur.execute(f"ALTER DATABASE postgres SET search_path TO {cls.schema}, public;")
                # 1. Esquema base P1
                cur.execute((ROOT / "tests/p1_fixture.sql").read_text(encoding="utf-8"))
                # 2. Esquema SaaS Iter 1
                cur.execute(render(ROOT / "backend/migrations/001_iter1_saas.up.sql", cls.schema))
                # 3. Tablas base de productos/ventas/inventario/devoluciones y rol 104
                cur.execute(DEVOLUCIONES_BASE_SCHEMA)
                # Match deployed persistent receipt infrastructure; never skip its check.
                cur.execute(render(ROOT / "backend/migrations/003_iter2_sync_idempotency.up.sql", cls.schema))
                cur.execute(render(ROOT / "backend/migrations/004_iter2_sync_transactional.up.sql", cls.schema))
                # 4. Migración 005 (UP) de Devoluciones
                cur.execute(render(ROOT / "backend/migrations/005_iter3_devoluciones.up.sql", cls.schema))
                # 5. Migración 007 (UP) de Devoluciones y Políticas Triples
                cur.execute(render(ROOT / "backend/migrations/007_iter5_devoluciones_politicas.up.sql", cls.schema))

                # Semillas de usuarios adicionales
                # Usuario 6: ENCARGADO_SUCURSAL (rol 104, empresa 1, sucursal 1)
                # Usuario 7: CLIENTE_2 (rol 102, empresa 2)
                cur.execute("""
                    INSERT INTO t_usuario (id_usuario, id_rol, username, password_hash, correo, nombre, apellido, id_empresa, estado)
                    VALUES 
                        (6, 104, 'encargado1', 'hash', 'encargado1@aurora.com', 'Elena', 'Encargada', 1, true),
                        (7, 102, 'cliente2', 'hash', 'cliente2@gmail.com', 'Beatriz', 'Cliente', 2, true)
                    ON CONFLICT (id_usuario) DO NOTHING;
                """)
                cur.execute("""
                    INSERT INTO t_usuario_rol (id_usuario, id_rol)
                    VALUES (6, 104), (7, 102)
                    ON CONFLICT DO NOTHING;
                """)
                cur.execute("""
                    INSERT INTO t_usuario_sucursal (id_usuario, id_sucursal)
                    VALUES (6, 1)
                    ON CONFLICT DO NOTHING;
                """)
                # Clientes
                cur.execute("""
                    INSERT INTO t_cliente (id_cliente, id_usuario, ci, telefono)
                    VALUES 
                        (1, 5, '1234567', '70011223'),
                        (2, 7, '7654321', '70099887')
                    ON CONFLICT DO NOTHING;
                """)
                # Catálogo
                cur.execute("""
                    INSERT INTO t_categoria (id_categoria, nombre, id_empresa) VALUES (1, 'Vestidos', 1);
                    INSERT INTO t_talla (id_talla, nombre, id_empresa) VALUES (1, 'M', 1);
                    INSERT INTO t_color (id_color, nombre, codigo_hex, id_empresa) VALUES (1, 'Negro', '#000000', 1);
                    INSERT INTO t_producto (id_producto, nombre, id_categoria, id_empresa, precio) 
                    VALUES (1, 'Vestido Seda Noir', 1, 1, 300.00);
                    INSERT INTO t_producto_talla_color (id_variante, id_producto, id_talla, id_color, sku, precio)
                    VALUES (1, 1, 1, 1, 'SKU-VES-NOIR-M', 300.00);
                    INSERT INTO t_inventario (id_inventario, id_sucursal, id_variante, stock_actual, stock_disponible, stock_reservado)
                    VALUES (1, 1, 1, 10, 10, 0);
                """)
                # Ventas
                cur.execute("""
                    INSERT INTO t_venta (id_venta, id_cliente, id_sucursal, id_usuario, numero_venta, tipo_venta, subtotal, descuento, total, estado, id_empresa)
                    VALUES 
                        (1, 1, 1, 5, 'VTA-202610-001', 'ONLINE', 600.00, 50.00, 550.00, 'COMPLETADA', 1),
                        (2, 1, 1, 5, 'VTA-202610-002', 'ONLINE', 300.00, 0.00, 300.00, 'PENDIENTE_PAGO', 1),
                        (3, 2, 2, 7, 'VTA-202610-003', 'ONLINE', 300.00, 0.00, 300.00, 'COMPLETADA', 2);
                    INSERT INTO t_detalle_venta (id_detalle_venta, id_venta, id_variante, cantidad, precio_unitario, descuento, subtotal)
                    VALUES 
                        (1, 1, 1, 2, 300.00, 25.00, 550.00),
                        (2, 2, 1, 1, 300.00, 0.00, 300.00),
                        (3, 3, 1, 1, 300.00, 0.00, 300.00);
                """)

        cls.user_cliente = _contexto_vigente({"id_usuario": 5})
        cls.user_cliente2 = _contexto_vigente({"id_usuario": 7})
        cls.user_admin = _contexto_vigente({"id_usuario": 1})
        cls.user_admin_tienda = _contexto_vigente({"id_usuario": 2})
        cls.user_cajero = _contexto_vigente({"id_usuario": 3})
        cls.user_encargado = _contexto_vigente({"id_usuario": 6})

        cls.app = FastAPI()
        cls.app.include_router(devoluciones_routes.router)
        cls.actor_actual = cls.user_cliente

        cls.app.dependency_overrides[verificar_token] = lambda: cls.actor_actual

        def override_require_permission(perm: str):
            def dep():
                from app.core.security import tiene_permiso
                if not tiene_permiso(cls.actor_actual, perm):
                    from fastapi import HTTPException
                    raise HTTPException(status_code=403, detail=f"Permiso denegado: {perm}")
                return cls.actor_actual
            return dep

        cls.app.dependency_overrides[require_permission] = override_require_permission
        cls.client = TestClient(cls.app)

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
        # Resetear datos de devoluciones antes de cada prueba
        with psycopg2.connect(**self.pg.params) as conn:
            with conn.cursor() as cur:
                cur.execute(f"SET search_path TO {self.schema};")
                cur.execute("DELETE FROM t_detalle_devolucion;")
                cur.execute("DELETE FROM t_devolucion;")
                cur.execute("DELETE FROM t_movimiento_inventario;")
                cur.execute("UPDATE t_inventario SET stock_actual = 10, stock_disponible = 10, stock_reservado = 0 WHERE id_inventario = 1;")

    # =========================================================================
    # CASOS DE PRUEBA
    # =========================================================================

    def test_01_cliente_solicita_devolucion_valida(self):
        """CU25W: Cliente solicita devolución válida de una prenda de su compra propia."""
        self.__class__.actor_actual = self.user_cliente
        payload = {
            "id_venta": 1,
            "id_empresa": 1,
            "motivo": "TALLA_INCORRECTA",
            "descripcion": "El vestido queda holgado en el talle",
            "evidencia_url": None,
            "items": [
                {"id_detalle_venta": 1, "cantidad": 1}
            ]
        }
        res = self.client.post("/api/devoluciones/solicitudes", json=payload)
        self.assertEqual(res.status_code, 201)
        data = res.json()
        self.assertTrue(data["success"])
        self.assertEqual(data["estado"], "SOLICITADA")
        self.assertIn("DEV-", data["codigo_devolucion"])
        # Monto reembolso de 1 unidad con descuento proporcional: 550 / 2 = 275.00
        self.assertEqual(data["monto_reembolso"], 275.00)

        # Consultar mis devoluciones
        res_mis = self.client.get("/api/devoluciones/mis-solicitudes")
        self.assertEqual(res_mis.status_code, 200)
        mis_data = res_mis.json()
        self.assertEqual(mis_data["total"], 1)
        self.assertEqual(mis_data["data"][0]["codigo_devolucion"], data["codigo_devolucion"])

    def test_02_cliente_no_puede_ver_ni_devolver_venta_ajena(self):
        """CU25W: Cliente no puede ver ni solicitar devolución de compra ajena ni de otro tenant."""
        self.__class__.actor_actual = self.user_cliente
        # Intento de solicitar devolución sobre Venta 3 (pertenece a Cliente 2 / Empresa 2)
        payload = {
            "id_venta": 3,
            "motivo": "FRAUDE",
            "items": [{"id_detalle_venta": 3, "cantidad": 1}]
        }
        res = self.client.post("/api/devoluciones/solicitudes", json=payload)
        self.assertEqual(res.status_code, 403)

        # Intento de consultar elegibilidad de la Venta 3
        res_eleg = self.client.get("/api/devoluciones/ventas/3/elegibilidad")
        self.assertEqual(res_eleg.status_code, 403)

    def test_03_rechazo_cantidades_mayores_a_elegibles(self):
        """Integridad: Rechaza cantidades mayores a las compradas o disponibles."""
        self.__class__.actor_actual = self.user_cliente
        # Compra fue de 2 unidades; solicita 5
        payload = {
            "id_venta": 1,
            "motivo": "DEFECTO",
            "items": [{"id_detalle_venta": 1, "cantidad": 5}]
        }
        res = self.client.post("/api/devoluciones/solicitudes", json=payload)
        self.assertEqual(res.status_code, 400)
        self.assertIn("supera la cantidad elegible", res.json()["detail"])

    def test_04_bloqueo_venta_no_confirmada(self):
        """Integridad: Venta no pagada (PENDIENTE_PAGO) está bloqueada para devolución."""
        self.__class__.actor_actual = self.user_cliente
        payload = {
            "id_venta": 2,
            "motivo": "CANCELACION",
            "items": [{"id_detalle_venta": 2, "cantidad": 1}]
        }
        res = self.client.post("/api/devoluciones/solicitudes", json=payload)
        self.assertEqual(res.status_code, 400)
        self.assertIn("No se pueden devolver ventas en estado", res.json()["detail"])

    def test_05_aprobacion_recepcion_y_bloqueo_reembolso_sin_evidencia(self):
        """CU24W: Recepción completa; no liquidar una transferencia solo por referencia."""
        # 1. Cliente solicita devolución de 1 prenda
        self.__class__.actor_actual = self.user_cliente
        res_sol = self.client.post("/api/devoluciones/solicitudes", json={
            "id_venta": 1,
            "id_empresa": 1,
            "motivo": "COSTURA_DEFECTUOSA",
            "items": [{"id_detalle_venta": 1, "cantidad": 1}]
        })
        self.assertEqual(res_sol.status_code, 201)
        id_dev = res_sol.json()["id_devolucion"]

        # 2. Encargado revisa y aprueba
        self.__class__.actor_actual = self.user_encargado
        res_rev = self.client.post(f"/api/devoluciones/{id_dev}/revisar", json={
            "accion": "APROBAR",
            "observaciones": "Prenda autorizada para inspección en tienda",
            "id_empresa": 1
        })
        self.assertEqual(res_rev.status_code, 200)
        self.assertEqual(res_rev.json()["nuevo_estado"], "PENDIENTE_RECEPCION")

        # 3. Cajero/Encargado recibe físicamente la prenda como REVENDIBLE
        # Stock inicial en sucursal 1 = 10
        res_det = self.client.get(f"/api/devoluciones/{id_dev}")
        id_det_dev = res_det.json()["items"][0]["id_detalle_devolucion"]

        res_rec = self.client.post(f"/api/devoluciones/{id_dev}/recepcion", json={
            "id_sucursal": 1,
            "id_empresa": 1,
            "observaciones": "Prenda con etiqueta intacta",
            "items": [
                {"id_detalle_devolucion": id_det_dev, "cantidad_recibida": 1, "condicion": "REVENDIBLE"}
            ]
        })
        self.assertEqual(res_rec.status_code, 200)
        self.assertEqual(res_rec.json()["nuevo_estado"], "PENDIENTE_REEMBOLSO")

        # Verificar que el inventario se incrementó de 10 a 11
        with psycopg2.connect(**self.pg.params) as conn:
            with conn.cursor() as cur:
                cur.execute(f"SET search_path TO {self.schema};")
                cur.execute("SELECT stock_actual, stock_disponible FROM t_inventario WHERE id_inventario = 1;")
                st_act, st_disp = cur.fetchone()
                self.assertEqual(st_act, 11)
                self.assertEqual(st_disp, 11)

                # Verificar movimiento de inventario registrado
                cur.execute("SELECT tipo_movimiento, cantidad, motivo FROM t_movimiento_inventario ORDER BY id_movimiento DESC LIMIT 1;")
                tipo_m, cant_m, mot_m = cur.fetchone()
                self.assertEqual(tipo_m, "ENTRADA")
                self.assertEqual(cant_m, 1)

        # 4. Registrar liquidación de reembolso financiero
        res_reemb = self.client.post(f"/api/devoluciones/{id_dev}/reembolso", json={
            "metodo_reembolso": "TRANSFERENCIA",
            "referencia_reembolso": "TRANSF-BNB-998811",
            "observaciones": "Transferido a cuenta bancaria del cliente",
            "id_empresa": 1
        })
        self.assertEqual(res_reemb.status_code, 409, res_reemb.text)
        self.assertIn('REFUND_EVIDENCE_REQUIRED',res_reemb.text)
        with psycopg2.connect(**self.pg.params) as conn:
            with conn.cursor() as cur:
                cur.execute(f'SELECT estado,fecha_reembolso FROM {self.schema}.t_devolucion WHERE id_devolucion=%s',(id_dev,))
                self.assertEqual(cur.fetchone(),('PENDIENTE_REEMBOLSO',None))

    def test_06_recepcion_defectuosa_no_incrementa_stock_disponible(self):
        """CU24W: Prenda defectuosa no incrementa stock vendible."""
        # 1. Crear solicitud
        self.__class__.actor_actual = self.user_cliente
        res_sol = self.client.post("/api/devoluciones/solicitudes", json={
            "id_venta": 1,
            "id_empresa": 1,
            "motivo": "MANCHA_INDELEBLE",
            "items": [{"id_detalle_venta": 1, "cantidad": 1}]
        })
        id_dev = res_sol.json()["id_devolucion"]

        # 2. Aprobar
        self.__class__.actor_actual = self.user_encargado
        self.client.post(f"/api/devoluciones/{id_dev}/revisar", json={
            "accion": "APROBAR",
            "observaciones": "Aprobado para recepción",
            "id_empresa": 1
        })

        # 3. Recibir como DEFECTUOSO
        res_det = self.client.get(f"/api/devoluciones/{id_dev}")
        id_det_dev = res_det.json()["items"][0]["id_detalle_devolucion"]

        res_rec = self.client.post(f"/api/devoluciones/{id_dev}/recepcion", json={
            "id_sucursal": 1,
            "id_empresa": 1,
            "observaciones": "Tejido rasgado irreparable",
            "items": [
                {"id_detalle_devolucion": id_det_dev, "cantidad_recibida": 1, "condicion": "DEFECTUOSO"}
            ]
        })
        self.assertEqual(res_rec.status_code, 200)

        # Verificar que el stock disponible NO aumentó (permanece en 10)
        with psycopg2.connect(**self.pg.params) as conn:
            with conn.cursor() as cur:
                cur.execute(f"SET search_path TO {self.schema};")
                cur.execute("SELECT stock_disponible FROM t_inventario WHERE id_inventario = 1;")
                st_disp = cur.fetchone()[0]
                self.assertEqual(st_disp, 10)

    def test_07_reembolso_inmediato_bloqueado_sin_permiso_o_evidencia(self):
        """CU24W: Cajero sin permiso y encargado sin infraestructura no liquidan efectivo."""
        self.__class__.actor_actual = self.user_cajero
        payload = {
            "id_venta": 1,
            "id_sucursal": 1,
            "id_empresa": 1,
            "motivo": "CAMBIO_INMEDIATO_SIN_STOCK",
            "observaciones": "Cliente presente en sucursal con comprobante",
            "items": [
                {"id_detalle_venta": 1, "cantidad": 1, "condicion": "REVENDIBLE"}
            ],
            "registrar_reembolso_inmediato": True,
            "metodo_reembolso": "EFECTIVO",
            "referencia_reembolso": "REC-CAJA-0044"
        }
        res = self.client.post("/api/devoluciones/presencial", json=payload)
        self.assertEqual(res.status_code, 403,res.text)  # CAJERO lacks refund permission in 005.
        self.__class__.actor_actual = self.user_encargado
        res = self.client.post('/api/devoluciones/presencial',json=payload)
        self.assertEqual(res.status_code,409,res.text)
        self.assertIn('REFUND_EVIDENCE_REQUIRED',res.text)
        with psycopg2.connect(**self.pg.params) as conn:
            with conn.cursor() as cur:
                cur.execute(f'SELECT COUNT(*) FROM {self.schema}.t_devolucion')
                self.assertEqual(cur.fetchone()[0],0)
                cur.execute(f'SELECT stock_actual,stock_disponible FROM {self.schema}.t_inventario WHERE id_inventario=1')
                self.assertEqual(cur.fetchone(),(10,10))

    def test_08_reversibilidad_migracion_005_down_up(self):
        """Solo esquema aislado vacío: DOWN/UP no certifica preservación de historia."""
        with psycopg2.connect(**self.pg.params) as conn:
            with conn.cursor() as cur:
                cur.execute(f"SET search_path TO {self.schema};")
                # 1. Ejecutar DOWN
                cur.execute(render(ROOT / "backend/migrations/005_iter3_devoluciones.down.sql", self.schema))
                # Verificar ausencia de columnas y permisos
                cur.execute("SELECT COUNT(*) FROM t_permiso WHERE codigo LIKE 'devoluciones.%';")
                self.assertEqual(cur.fetchone()[0], 0)

                # 2. Re-ejecutar UP
                cur.execute(render(ROOT / "backend/migrations/005_iter3_devoluciones.up.sql", self.schema))
                cur.execute("SELECT COUNT(*) FROM t_permiso WHERE codigo LIKE 'devoluciones.%';")
                self.assertEqual(cur.fetchone()[0], 7)

if __name__ == "__main__":
    unittest.main()
