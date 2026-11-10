import concurrent.futures
import json
import os
from pathlib import Path
import statistics
import sys
import time
import types
import unittest
import uuid

import psycopg2
from fastapi.testclient import TestClient

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'tests'))
sys.path.insert(0, str(ROOT / 'backend'))
from isolated_postgres import LocalPostgres

from app.core.config import Config
from app.core.postgres import PostgreSQL
from app.core.security import _contexto_vigente, invalidar_cache_contexto
from app.core.tenant_guard import invalidar_cache_tenant
from app.modules.catalogo.repos.categorias_repos import invalidar_cache_categorias
from app.modules.catalogo.repos.tallas_colores_repos import invalidar_cache_tallas_colores
from migrate import render


CATALOG_SCHEMA_SQL = """
CREATE TABLE t_categoria (
    id_categoria SERIAL PRIMARY KEY,
    nombre TEXT NOT NULL,
    descripcion TEXT,
    id_padre INTEGER REFERENCES t_categoria(id_categoria),
    id_empresa INTEGER NOT NULL REFERENCES empresa(id_empresa),
    imagen_url TEXT,
    imagen_public_id TEXT,
    activo BOOLEAN DEFAULT TRUE,
    created_at TIMESTAMP DEFAULT now(),
    updated_at TIMESTAMP DEFAULT now()
);

CREATE TABLE t_talla (
    id_talla SERIAL PRIMARY KEY,
    nombre TEXT NOT NULL,
    descripcion TEXT,
    id_empresa INTEGER NOT NULL REFERENCES empresa(id_empresa),
    activo BOOLEAN DEFAULT TRUE,
    created_at TIMESTAMP DEFAULT now(),
    updated_at TIMESTAMP DEFAULT now()
);

CREATE TABLE t_color (
    id_color SERIAL PRIMARY KEY,
    nombre TEXT NOT NULL,
    codigo_hex TEXT NOT NULL,
    id_empresa INTEGER NOT NULL REFERENCES empresa(id_empresa),
    activo BOOLEAN DEFAULT TRUE,
    created_at TIMESTAMP DEFAULT now(),
    updated_at TIMESTAMP DEFAULT now()
);

CREATE TABLE t_producto (
    id_producto SERIAL PRIMARY KEY,
    nombre TEXT NOT NULL,
    descripcion TEXT,
    sku TEXT,
    codigo TEXT,
    precio NUMERIC(12, 2) NOT NULL DEFAULT 100.00,
    precio_venta NUMERIC(12, 2) NOT NULL DEFAULT 100.00,
    costo NUMERIC(12, 2) DEFAULT 50.00,
    id_categoria INTEGER REFERENCES t_categoria(id_categoria),
    id_empresa INTEGER NOT NULL REFERENCES empresa(id_empresa),
    temporada TEXT DEFAULT 'Todo el Año',
    tipo_tela TEXT,
    color TEXT,
    talla TEXT,
    imagen_url TEXT,
    stock_minimo INTEGER DEFAULT 5,
    activo BOOLEAN DEFAULT TRUE,
    estado BOOLEAN DEFAULT TRUE,
    created_at TIMESTAMP DEFAULT now(),
    updated_at TIMESTAMP DEFAULT now()
);

CREATE TABLE t_producto_imagen (
    id_imagen SERIAL PRIMARY KEY,
    id_producto INTEGER NOT NULL REFERENCES t_producto(id_producto) ON DELETE CASCADE,
    url TEXT NOT NULL,
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
    sku_variante TEXT,
    codigo_barras TEXT,
    precio_adicional NUMERIC(12, 2) DEFAULT 0,
    costo_unitario NUMERIC(12, 2) DEFAULT 50,
    activo BOOLEAN DEFAULT TRUE,
    created_at TIMESTAMP DEFAULT now(),
    updated_at TIMESTAMP DEFAULT now(),
    UNIQUE(id_producto, id_talla, id_color)
);

CREATE TABLE t_promocion (
    id_promocion SERIAL PRIMARY KEY,
    nombre TEXT NOT NULL,
    porcentaje_descuento NUMERIC(5, 2) NOT NULL,
    fecha_inicio DATE NOT NULL,
    fecha_fin DATE NOT NULL,
    activo BOOLEAN DEFAULT TRUE,
    id_empresa INTEGER REFERENCES empresa(id_empresa)
);

CREATE TABLE t_promocion_producto (
    id_promocion INTEGER NOT NULL REFERENCES t_promocion(id_promocion) ON DELETE CASCADE,
    id_producto INTEGER NOT NULL REFERENCES t_producto(id_producto) ON DELETE CASCADE,
    PRIMARY KEY (id_promocion, id_producto)
);

CREATE TABLE t_inventario (
    id_inventario SERIAL PRIMARY KEY,
    id_sucursal INTEGER NOT NULL REFERENCES t_sucursal(id_sucursal),
    id_variante INTEGER NOT NULL REFERENCES t_producto_talla_color(id_variante),
    stock_actual INTEGER NOT NULL DEFAULT 0,
    stock_minimo INTEGER NOT NULL DEFAULT 5,
    ubicacion TEXT,
    updated_at TIMESTAMP DEFAULT now(),
    UNIQUE(id_sucursal, id_variante)
);

CREATE TABLE t_reserva (
    id_reserva SERIAL PRIMARY KEY,
    id_sucursal INTEGER REFERENCES t_sucursal(id_sucursal),
    id_empresa INTEGER REFERENCES empresa(id_empresa),
    estado TEXT NOT NULL DEFAULT 'PENDIENTE',
    created_at TIMESTAMP DEFAULT now()
);

CREATE TABLE t_detalle_reserva (
    id_detalle_reserva SERIAL PRIMARY KEY,
    id_reserva INTEGER NOT NULL REFERENCES t_reserva(id_reserva) ON DELETE CASCADE,
    id_producto INTEGER REFERENCES t_producto(id_producto),
    id_talla INTEGER REFERENCES t_talla(id_talla),
    id_color INTEGER REFERENCES t_color(id_color),
    cantidad INTEGER NOT NULL DEFAULT 1
);
"""


class PerformanceIter1Suite(unittest.TestCase):
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
            ('DB_HOST', cls.pg.params['host']),
            ('DB_PORT', cls.pg.params['port']),
            ('DB_USER', 'iter1_test'),
            ('DB_NAME', 'postgres'),
            ('DB_PASSWORD', ''),
        ]:
            setattr(Config, name, value)

        cls.schema = 'perf_' + uuid.uuid4().hex
        Config.SCHEMA = cls.schema

        with psycopg2.connect(**cls.pg.params) as conn:
            with conn.cursor() as cur:
                cur.execute(f'CREATE SCHEMA {cls.schema}; SET search_path TO {cls.schema}')
                cur.execute((ROOT / 'tests/p1_fixture.sql').read_text(encoding='utf-8'))
                cur.execute(render(ROOT / 'backend/migrations/001_iter1_saas.up.sql', cls.schema))
                cur.execute(CATALOG_SCHEMA_SQL)
                # Add catalogue & inventory permissions to roles 101, 103, 105
                cur.execute("""
                    INSERT INTO t_permiso (codigo, nombre, modulo, activo) VALUES
                    ('productos.ver', 'Ver productos', 'CATALOGO', TRUE),
                    ('productos.crear', 'Crear productos', 'CATALOGO', TRUE),
                    ('productos.editar', 'Editar productos', 'CATALOGO', TRUE),
                    ('categorias.ver', 'Ver categorias', 'CATALOGO', TRUE),
                    ('categorias.crear', 'Crear categorias', 'CATALOGO', TRUE),
                    ('categorias.editar', 'Editar categorias', 'CATALOGO', TRUE),
                    ('tallas.ver', 'Ver tallas', 'CATALOGO', TRUE),
                    ('tallas.crear', 'Crear tallas', 'CATALOGO', TRUE),
                    ('tallas.editar', 'Editar tallas', 'CATALOGO', TRUE),
                    ('inventario.ver', 'Ver inventario', 'INVENTARIO', TRUE),
                    ('inventario.editar', 'Editar inventario', 'INVENTARIO', TRUE),
                    ('empresas.ver', 'Ver empresas', 'TENANT', TRUE)
                    ON CONFLICT (codigo) DO NOTHING;
                    INSERT INTO t_rol_permiso (id_rol, id_permiso)
                    SELECT r.id_rol, p.id_permiso
                    FROM t_rol r CROSS JOIN t_permiso p
                    WHERE r.id_rol IN (101, 103)
                    ON CONFLICT DO NOTHING;
                    INSERT INTO t_rol_permiso (id_rol, id_permiso)
                    SELECT 105, id_permiso FROM t_permiso
                    WHERE codigo IN ('productos.ver', 'categorias.ver', 'tallas.ver', 'inventario.ver')
                    ON CONFLICT DO NOTHING;
                    -- Create Store Admin for Empresa B (id_usuario = 6)
                    INSERT INTO t_usuario (id_usuario, username, id_empresa, id_rol, nombre, apellido, estado)
                    VALUES (6, 'admin_b', 2, 103, 'Admin', 'B', TRUE);
                    INSERT INTO t_usuario_rol VALUES (6, 103);
                    -- Add second branch for Empresa 1 (requires subscription first)
                    INSERT INTO t_suscripcion (id_empresa, codigo_plan, inicio, fin, motivo, creado_por)
                    VALUES (1, 'PROFESIONAL', now() - interval '1 day', now() + interval '30 days', 'Plan inicial A', 1),
                           (2, 'BASICO', now() - interval '1 day', now() + interval '30 days', 'Plan inicial B', 1);
                    INSERT INTO t_sucursal (id_sucursal, id_empresa, nombre, id_ciudad, activo, estado)
                    VALUES (3, 1, 'A2', 1, TRUE, TRUE);
                """)
                cls._seed_dataset(cur)
                cur.execute(render(ROOT / 'backend/migrations/002_iter1_perf_indexes.up.sql', cls.schema))
                cur.execute('ANALYZE')

        from app.main import create_app
        cls.app = create_app()
        cls.client = TestClient(cls.app)

    @classmethod
    def _seed_dataset(cls, cur):
        # Seed Categories, Sizes, Colors, Products, Variants, Images, and Inventory for Empresa 1 (150 products) and Empresa 2 (30 products)
        cur.execute("""
            INSERT INTO t_categoria (id_categoria, nombre, descripcion, id_padre, id_empresa, imagen_url, activo)
            SELECT g, 'Categoria A' || g, 'Desc ' || g, CASE WHEN g > 5 THEN ((g - 1) % 5) + 1 ELSE NULL END, 1,
                   'https://res.cloudinary.com/demo/image/upload/v1/sample.jpg', (g % 10 <> 0)
            FROM generate_series(1, 20) g;

            INSERT INTO t_categoria (id_categoria, nombre, descripcion, id_padre, id_empresa, imagen_url, activo)
            SELECT 20 + g, 'Categoria B' || g, 'Desc B' || g, NULL, 2,
                   'https://res.cloudinary.com/demo/image/upload/v1/sample.jpg', TRUE
            FROM generate_series(1, 5) g;

            SELECT setval(pg_get_serial_sequence('t_categoria', 'id_categoria'), 50);

            INSERT INTO t_talla (id_talla, nombre, descripcion, id_empresa, activo) VALUES
            (1, 'XS', 'Extra Small', 1, TRUE),
            (2, 'S', 'Small', 1, TRUE),
            (3, 'M', 'Medium', 1, TRUE),
            (4, 'L', 'Large', 1, TRUE),
            (5, 'XL', 'Extra Large', 1, FALSE),
            (6, 'S-B', 'Small B', 2, TRUE),
            (7, 'M-B', 'Medium B', 2, TRUE);
            SELECT setval(pg_get_serial_sequence('t_talla', 'id_talla'), 20);

            INSERT INTO t_color (id_color, nombre, codigo_hex, id_empresa, activo) VALUES
            (1, 'Negro', '#000000', 1, TRUE),
            (2, 'Blanco', '#FFFFFF', 1, TRUE),
            (3, 'Dorado', '#D4AF37', 1, TRUE),
            (4, 'Rosa', '#E8C5C8', 1, TRUE),
            (5, 'Gris', '#888888', 1, FALSE),
            (6, 'Azul B', '#0033AA', 2, TRUE),
            (7, 'Rojo B', '#AA0033', 2, TRUE);
            SELECT setval(pg_get_serial_sequence('t_color', 'id_color'), 20);

            -- 150 products for Empresa 1
            INSERT INTO t_producto (id_producto, nombre, descripcion, sku, codigo, precio, precio_venta, costo, id_categoria, id_empresa, temporada, activo, estado)
            SELECT g,
                   'Prenda Atelier A-' || lpad(g::text, 3, '0'),
                   'Descripción detallada de prenda ' || g,
                   'SKU-A-' || lpad(g::text, 4, '0'),
                   'SKU-A-' || lpad(g::text, 4, '0'),
                   120.00 + (g % 50),
                   120.00 + (g % 50),
                   60.00,
                   ((g - 1) % 20) + 1,
                   1,
                   CASE WHEN g % 3 = 0 THEN 'Primavera / Verano' WHEN g % 3 = 1 THEN 'Otoño / Invierno' ELSE 'Todo el Año' END,
                   (g <= 135),
                   (g <= 135)
            FROM generate_series(1, 150) g;

            -- 30 products for Empresa 2
            INSERT INTO t_producto (id_producto, nombre, descripcion, sku, codigo, precio, precio_venta, costo, id_categoria, id_empresa, temporada, activo, estado)
            SELECT 150 + g,
                   'Prenda Exclusiva B-' || lpad(g::text, 3, '0'),
                   'Descripción B ' || g,
                   'SKU-B-' || lpad(g::text, 4, '0'),
                   'SKU-B-' || lpad(g::text, 4, '0'),
                   200.00,
                   200.00,
                   90.00,
                   21 + ((g - 1) % 5),
                   2,
                   'Todo el Año',
                   TRUE,
                   TRUE
            FROM generate_series(1, 30) g;
            SELECT setval(pg_get_serial_sequence('t_producto', 'id_producto'), 300);

            -- Images for products
            INSERT INTO t_producto_imagen (id_producto, url, public_id, es_principal, orden)
            SELECT id_producto,
                   'https://res.cloudinary.com/demo/image/upload/v1/prod_' || id_producto || '_main.jpg',
                   'prod_' || id_producto || '_main',
                   TRUE,
                   1
            FROM t_producto;

            INSERT INTO t_producto_imagen (id_producto, url, public_id, es_principal, orden)
            SELECT id_producto,
                   'https://res.cloudinary.com/demo/image/upload/v1/prod_' || id_producto || '_sec.jpg',
                   'prod_' || id_producto || '_sec',
                   FALSE,
                   2
            FROM t_producto;

            -- 16 variants (4 tallas x 4 colores) per Empresa 1 product = 2,400 variants
            INSERT INTO t_producto_talla_color (id_producto, id_talla, id_color, sku_variante, codigo_barras, precio_adicional, costo_unitario, activo)
            SELECT p.id_producto, t.id_talla, c.id_color,
                   p.sku || '-' || t.nombre || '-' || c.id_color,
                   'CB-' || p.id_producto || '-' || t.id_talla || '-' || c.id_color,
                   0, 60, TRUE
            FROM t_producto p
            CROSS JOIN t_talla t
            CROSS JOIN t_color c
            WHERE p.id_empresa = 1 AND t.id_empresa = 1 AND t.id_talla <= 4 AND c.id_empresa = 1 AND c.id_color <= 4;

            -- 4 variants (2 tallas x 2 colores) per Empresa 2 product = 120 variants
            INSERT INTO t_producto_talla_color (id_producto, id_talla, id_color, sku_variante, codigo_barras, precio_adicional, costo_unitario, activo)
            SELECT p.id_producto, t.id_talla, c.id_color,
                   p.sku || '-' || t.nombre || '-' || c.id_color,
                   'CB-B-' || p.id_producto || '-' || t.id_talla || '-' || c.id_color,
                   0, 90, TRUE
            FROM t_producto p
            CROSS JOIN t_talla t
            CROSS JOIN t_color c
            WHERE p.id_empresa = 2 AND t.id_empresa = 2 AND c.id_empresa = 2;

            -- Inventory for Empresa 1 (Branch 1 and Branch 3) and Empresa 2 (Branch 2)
            INSERT INTO t_inventario (id_sucursal, id_variante, stock_actual, stock_minimo, ubicacion)
            SELECT 1, v.id_variante, (v.id_variante % 25), 5, 'Estante A'
            FROM t_producto_talla_color v
            JOIN t_producto p ON p.id_producto = v.id_producto
            WHERE p.id_empresa = 1;

            INSERT INTO t_inventario (id_sucursal, id_variante, stock_actual, stock_minimo, ubicacion)
            SELECT 3, v.id_variante, ((v.id_variante + 7) % 15), 5, 'Estante B'
            FROM t_producto_talla_color v
            JOIN t_producto p ON p.id_producto = v.id_producto
            WHERE p.id_empresa = 1 AND p.id_producto <= 50;

            INSERT INTO t_inventario (id_sucursal, id_variante, stock_actual, stock_minimo, ubicacion)
            SELECT 2, v.id_variante, 12, 4, 'Estante Central B'
            FROM t_producto_talla_color v
            JOIN t_producto p ON p.id_producto = v.id_producto
            WHERE p.id_empresa = 2;
        """)

    @classmethod
    def tearDownClass(cls):
        if PostgreSQL._pool:
            PostgreSQL._pool.closeall()
            PostgreSQL._pool = None
        cls.cluster.__exit__(None, None, None)

    def setUp(self):
        invalidar_cache_contexto()
        invalidar_cache_tenant()
        invalidar_cache_categorias()
        invalidar_cache_tallas_colores()

    def _token_for(self, uid: int) -> str:
        import jwt
        ctx = _contexto_vigente({'id_usuario': uid})
        payload = {
            'id_usuario': uid,
            'id_empresa': ctx.get('id_empresa'),
            'id_rol': ctx.get('id_rol'),
            'roles': ctx.get('roles', []),
            'permisos': ctx.get('permisos', []),
            'sucursales': ctx.get('sucursales', []),
        }
        return jwt.encode(payload, Config.SECRET_KEY, algorithm='HS256')

    def _headers(self, uid: int) -> dict:
        return {'Authorization': f'Bearer {self._token_for(uid)}'}

    def test_01_productos_pagination_filters_and_contract(self):
        headers_a = self._headers(2)  # Admin Empresa A (150 products: 135 active, 15 inactive)
        res = self.client.get('/api/productos?limit=20&offset=0', headers=headers_a)
        self.assertEqual(res.status_code, 200, res.text)
        body = res.json()
        self.assertTrue(body['success'])
        self.assertEqual(len(body['data']), 20)
        self.assertEqual(body['total'], 150)
        self.assertIn('X-Response-Time-Ms', res.headers)
        self.assertIn('X-DB-Query-Count', res.headers)
        self.assertIn('Server-Timing', res.headers)

        # Verify item contract fields required by Angular & Flutter
        first = body['data'][0]
        for field in [
            'id_producto', 'nombre', 'sku', 'precio', 'precio_venta', 'id_categoria',
            'categoria_nombre', 'id_empresa', 'activo', 'imagen_principal',
            'imagenes', 'variantes', 'stock_total', 'total_variantes'
        ]:
            self.assertIn(field, first)
        self.assertEqual(first['id_empresa'], 1)
        self.assertEqual(len(first['variantes']), 16)

        # Filter by activo=true (135 products) and activo=false (15 products)
        res_act = self.client.get('/api/productos?limit=20&offset=0&activo=true', headers=headers_a)
        self.assertEqual(res_act.status_code, 200)
        self.assertEqual(res_act.json()['total'], 135)
        self.assertTrue(all(p['activo'] is True for p in res_act.json()['data']))

        res_inact = self.client.get('/api/productos?limit=20&offset=0&activo=false', headers=headers_a)
        self.assertEqual(res_inact.status_code, 200)
        self.assertEqual(res_inact.json()['total'], 15)
        self.assertEqual(len(res_inact.json()['data']), 15)
        self.assertTrue(all(p['activo'] is False for p in res_inact.json()['data']))

        # Filter by temporada
        res_temp = self.client.get('/api/productos?limit=20&offset=0&temporada=Primavera%20/%20Verano', headers=headers_a)
        self.assertEqual(res_temp.status_code, 200)
        self.assertEqual(res_temp.json()['total'], 50)

        # Filter by busqueda
        res_search = self.client.get('/api/productos?limit=20&offset=0&busqueda=SKU-A-0005', headers=headers_a)
        self.assertEqual(res_search.status_code, 200)
        self.assertEqual(res_search.json()['total'], 1)
        self.assertEqual(res_search.json()['data'][0]['sku'], 'SKU-A-0005')

    def test_02_multitenant_isolation_and_no_cache_leakage(self):
        headers_a = self._headers(2)  # Admin Empresa A (id_empresa=1)
        headers_b = self._headers(6)  # Admin Empresa B (id_empresa=2)
        headers_emp_a = self._headers(3)  # Employee Empresa A (branch 1 only)

        # 1. Warm up caches as Empresa A
        cat_a = self.client.get('/api/categorias/', headers=headers_a).json()
        tallas_a = self.client.get('/api/tallas/', headers=headers_a).json()
        colores_a = self.client.get('/api/colores/', headers=headers_a).json()
        prod_a = self.client.get('/api/productos?limit=20&offset=0', headers=headers_a).json()
        inv_a = self.client.get('/api/inventario/?page=1&limit=15', headers=headers_a).json()

        self.assertEqual(cat_a['total'], 20)
        self.assertEqual(tallas_a['total'], 5)
        self.assertEqual(colores_a['total'], 5)
        self.assertEqual(prod_a['total'], 150)
        self.assertEqual(inv_a['data']['total'], 3200)  # 2400 in Branch 1 + 800 in Branch 3

        # 2. Immediately query as Empresa B -> must NEVER receive Empresa A cached data
        cat_b = self.client.get('/api/categorias/', headers=headers_b).json()
        tallas_b = self.client.get('/api/tallas/', headers=headers_b).json()
        colores_b = self.client.get('/api/colores/', headers=headers_b).json()
        prod_b = self.client.get('/api/productos?limit=20&offset=0', headers=headers_b).json()
        inv_b = self.client.get('/api/inventario/?page=1&limit=15', headers=headers_b).json()

        self.assertEqual(cat_b['total'], 5)
        self.assertTrue(all(c['id_empresa'] == 2 for c in cat_b['data']))
        self.assertEqual(tallas_b['total'], 2)
        self.assertTrue(all(t['id_empresa'] == 2 for t in tallas_b['data']))
        self.assertEqual(colores_b['total'], 2)
        self.assertTrue(all(c['id_empresa'] == 2 for c in colores_b['data']))
        self.assertEqual(prod_b['total'], 30)
        self.assertTrue(all(p['id_empresa'] == 2 for p in prod_b['data']))
        self.assertEqual(inv_b['data']['total'], 120)
        self.assertTrue(all(i['id_sucursal'] == 2 for i in inv_b['data']['items']))

        # 3. Empresa A attempting to pass ?id_empresa=2 must be rejected or scoped to Empresa 1
        res_forged_inv = self.client.get('/api/inventario/?id_empresa=2', headers=headers_a)
        self.assertEqual(res_forged_inv.status_code, 403)
        res_forged_cat = self.client.get('/api/categorias/?id_empresa=2', headers=headers_a)
        self.assertEqual(res_forged_cat.status_code, 403)

        # 4. Branch-scoped employee (uid=3, only Branch 1) cannot see Branch 3 inventory
        inv_emp_a = self.client.get('/api/inventario/?page=1&limit=15', headers=headers_emp_a).json()
        self.assertEqual(inv_emp_a['data']['total'], 2400)  # Only Branch 1 (2400), not Branch 3 (800)
        res_foreign_branch = self.client.get('/api/inventario/?id_sucursal=3', headers=headers_emp_a)
        self.assertEqual(res_foreign_branch.status_code, 403)

    def test_03_cache_invalidation_on_mutations(self):
        headers_a = self._headers(2)
        # Prime cache
        r1 = self.client.get('/api/tallas/', headers=headers_a)
        self.assertEqual(r1.status_code, 200)
        before_total = r1.json()['total']

        # Create a new size
        r_create = self.client.post(
            '/api/tallas/',
            json={'nombre': 'XXL-TEST', 'descripcion': 'Prueba cache', 'id_empresa': 1, 'activo': True},
            headers=headers_a
        )
        self.assertIn(r_create.status_code, (200, 201), r_create.text)
        new_id = r_create.json()['data']['id_talla']

        # Immediate GET must reflect the new size without stale cache
        r2 = self.client.get('/api/tallas/', headers=headers_a)
        self.assertEqual(r2.json()['total'], before_total + 1)

        # Clean up created size
        r_del = self.client.delete(f'/api/tallas/{new_id}', headers=headers_a)
        self.assertEqual(r_del.status_code, 200)
        r3 = self.client.get('/api/tallas/', headers=headers_a)
        self.assertEqual(r3.json()['total'], before_total)

    def test_04_reversible_index_migration(self):
        with psycopg2.connect(**self.pg.params) as conn:
            with conn.cursor() as cur:
                cur.execute(render(ROOT / 'backend/migrations/002_iter1_perf_indexes.down.sql', self.schema))
                cur.execute(
                    "SELECT COUNT(*) FROM pg_indexes WHERE schemaname = %s AND indexname LIKE 'idx_iter1_%%'",
                    (self.schema,)
                )
                self.assertEqual(cur.fetchone()[0], 0)

                cur.execute(render(ROOT / 'backend/migrations/002_iter1_perf_indexes.up.sql', self.schema))
                cur.execute(
                    "SELECT COUNT(*) FROM pg_indexes WHERE schemaname = %s AND indexname LIKE 'idx_iter1_%%'",
                    (self.schema,)
                )
                self.assertGreaterEqual(cur.fetchone()[0], 11)

    def test_05_concurrency_and_benchmark_metrics(self):
        headers_a = self._headers(2)
        endpoints = [
            '/api/productos?limit=20&offset=0',
            '/api/inventario/?page=1&limit=15',
            '/api/categorias/',
            '/api/tallas/',
            '/api/colores/',
            '/api/mi-empresa/plan',
        ]

        # Warmup
        for ep in endpoints:
            r = self.client.get(ep, headers=headers_a)
            self.assertEqual(r.status_code, 200, f'{ep} failed: {r.text}')

        # Concurrency stress test (24 concurrent requests across endpoints)
        def call_ep(idx: int):
            ep = endpoints[idx % len(endpoints)]
            res = self.client.get(ep, headers=headers_a)
            return ep, res.status_code, float(res.headers.get('X-Response-Time-Ms', '0')), int(res.headers.get('X-DB-Query-Count', '0')), len(res.content)

        with concurrent.futures.ThreadPoolExecutor(max_workers=6) as pool:
            results = list(pool.map(call_ep, range(24)))

        for ep, status, ms, qcount, size in results:
            self.assertEqual(status, 200, f'Concurrent error on {ep}: {status}')

        # Detailed p50/p95 benchmark (15 samples per endpoint, cold vs warm cache)
        metrics_report = {}
        for ep in endpoints:
            samples_ms = []
            query_counts = []
            sizes = []
            for i in range(15):
                if i == 0:
                    invalidar_cache_contexto()
                    invalidar_cache_tenant()
                    invalidar_cache_categorias()
                    invalidar_cache_tallas_colores()
                t0 = time.perf_counter()
                res = self.client.get(ep, headers=headers_a)
                elapsed = (time.perf_counter() - t0) * 1000.0
                self.assertEqual(res.status_code, 200)
                samples_ms.append(round(elapsed, 2))
                query_counts.append(int(res.headers.get('X-DB-Query-Count', '0')))
                sizes.append(len(res.content))

            warm_samples = sorted(samples_ms[1:])
            p50 = warm_samples[len(warm_samples) // 2]
            p95 = warm_samples[int(len(warm_samples) * 0.95) - 1]
            metrics_report[ep] = {
                'cold_ms': samples_ms[0],
                'warm_p50_ms': p50,
                'warm_p95_ms': p95,
                'cold_queries': query_counts[0],
                'warm_queries': query_counts[-1],
                'payload_bytes': sizes[-1],
            }

        print('\nBENCHMARK_METRICS_JSON=' + json.dumps(metrics_report))


if __name__ == '__main__':
    unittest.main()