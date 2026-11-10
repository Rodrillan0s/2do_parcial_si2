"""Integration against disposable PostgreSQL and read-only production SQL snapshots."""
from concurrent.futures import ThreadPoolExecutor
from copy import deepcopy
from datetime import datetime, timedelta, timezone
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys
import threading
import unittest
import uuid
from unittest.mock import patch

import psycopg2

import test_pwa_iter2 as fixture
from isolated_postgres import LocalPostgres
from app.core.config import Config
from app.core.postgres import PostgreSQL, _invalidar_caches_seguridad
from app.modules.ecommerce.routes import sync_routes
from migrate import render

ROOT = Path(__file__).resolve().parents[1]


class TransactionalSyncSuite(unittest.TestCase):
    _headers_for_user = fixture.PwaOfflineIter2Suite._headers_for_user

    @classmethod
    def setUpClass(cls):
        with patch.object(fixture, 'LocalPostgres', lambda: LocalPostgres(durable=True)):
            fixture.PwaOfflineIter2Suite.setUpClass.__func__(cls)
        cls.addClassCleanup(fixture.PwaOfflineIter2Suite.tearDownClass.__func__, cls)
        with psycopg2.connect(**cls.pg.params) as conn, conn.cursor() as cur:
            cur.execute(f"""
                ALTER TABLE {cls.schema}.t_inventario ADD COLUMN IF NOT EXISTS fecha_actualizacion TIMESTAMP;
                ALTER TABLE {cls.schema}.t_reserva ADD COLUMN id_venta INTEGER;
                CREATE TABLE {cls.schema}.t_movimiento_inventario (
                    id_movimiento SERIAL PRIMARY KEY,
                    id_inventario INTEGER REFERENCES {cls.schema}.t_inventario,
                    id_usuario INTEGER, tipo_movimiento TEXT, cantidad INTEGER,
                    stock_anterior INTEGER, stock_nuevo INTEGER, motivo TEXT,
                    fecha_movimiento TIMESTAMP
                );
                DROP FUNCTION {cls.schema}.fn_registrar_venta_pos(integer,integer,integer,integer,integer,json,numeric,text,integer);
                DROP FUNCTION {cls.schema}.fn_reservar_stock(integer,integer,integer,integer);
                INSERT INTO {cls.schema}.t_caja_sesion
                    (id_caja,id_usuario,id_sucursal,id_empresa,monto_inicial,estado)
                    VALUES (1,3,1,1,500,'ABIERTA');
            """)
            for name in ('fn_registrar_venta_pos', 'fn_reservar_stock'):
                cur.execute(render(ROOT / f'tests/sql/{name}_snapshot.sql', cls.schema))
            cur.execute('SHOW fsync')
            assert cur.fetchone()[0] == 'on'

    def setUp(self):
        _invalidar_caches_seguridad()
        self.sql(f"UPDATE {self.schema}.t_inventario SET stock_actual=20,stock_reservado=0,stock_disponible=20 WHERE id_sucursal=1 AND id_variante=100")
        self.sql(f"UPDATE {self.schema}.t_reserva SET estado='CANCELADA' WHERE estado='PENDIENTE'")
        self.before = self.effects()

    def sql(self, query, params=None):
        with psycopg2.connect(**self.pg.params) as conn, conn.cursor() as cur:
            cur.execute(query, params)
            return cur.fetchall() if cur.description else None

    def effects(self):
        tables = ('t_venta', 't_detalle_venta', 't_pago', 't_pago_denominacion', 't_reserva', 't_detalle_reserva', 't_movimiento_inventario')
        return {t: self.sql(f'SELECT count(*) FROM {self.schema}.{t}')[0][0] for t in tables}

    def stock(self):
        return self.sql(f'SELECT stock_actual,stock_reservado,stock_disponible FROM {self.schema}.t_inventario WHERE id_sucursal=1 AND id_variante=100')[0]

    def operation(self, kind='VENTA_CONTADO', quantity=2):
        payload = {'id_sucursal': 1, 'items': [{'id_variante': 100, 'cantidad': quantity, 'expected_unit_price': 150.0}]}
        if kind == 'VENTA_CONTADO':
            payload.update(metodo_tipo='EFECTIVO', id_metodo_pago=1, monto_recibido=quantity * 150.0)
        else:
            payload.update(con_pago=False, fecha_hora_visita=(datetime.now() + timedelta(days=2)).replace(hour=10, minute=0, second=0).isoformat())
        return dict(operation_id=str(uuid.uuid4()), created_at=datetime.now(timezone.utc).isoformat(), kind=kind, tenant_id=1, branch_id=1, payload=payload)

    def send(self, operation, user_id=3, endpoint='/api/sync/lote'):
        response = self.client.post(endpoint, headers=self._headers_for_user(user_id), json={'operations': [operation]})
        self.assertEqual(response.status_code, 200, response.text)
        return response.json()['results'][0]

    def assert_one_effect(self, kind, quantity=2):
        after = self.effects()
        expected = {'t_movimiento_inventario': 1}
        if kind == 'VENTA_CONTADO':
            expected.update(t_venta=1, t_detalle_venta=1, t_pago=1)
            self.assertEqual(self.stock(), (20 - quantity, 0, 20 - quantity))
        else:
            expected.update(t_reserva=1, t_detalle_reserva=1)
            self.assertEqual(self.stock(), (20, quantity, 20 - quantity))
        for table, count in expected.items():
            self.assertEqual(after[table] - self.before[table], count, table)

    def worker_settings(self, op, pause=None):
        return {**{k: getattr(Config, k) for k in ('DB_HOST','DB_PORT','DB_NAME','DB_USER','DB_PASSWORD','SCHEMA','TOKEN_KEY','SECRET_KEY')},
                'operation': op, 'pause': pause}

    def worker(self, op):
        result = subprocess.run([sys.executable, '-B', str(ROOT / 'tests/sync_process_worker.py')],
                                input=json.dumps(self.worker_settings(op)) + '\n', capture_output=True, text=True, timeout=30)
        self.assertEqual(result.returncode, 0, result.stderr + result.stdout)
        return json.loads(next(line.split('=', 1)[1] for line in result.stdout.splitlines() if line.startswith('SYNC_RESULT=')))

    def kill_worker(self, op, pause):
        proc = subprocess.Popen([sys.executable, '-B', str(ROOT / 'tests/sync_process_worker.py')],
                                stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True,
                                creationflags=subprocess.CREATE_NO_WINDOW if sys.platform == 'win32' else 0)
        try:
            proc.stdin.write(json.dumps(self.worker_settings(op, pause)) + '\n')
            proc.stdin.flush()
            with ThreadPoolExecutor(max_workers=1) as pool:
                def marker():
                    for line in proc.stdout:
                        if line.startswith('SYNC_PAUSED='):
                            return line.strip()
                    raise AssertionError(proc.stderr.read())
                future = pool.submit(marker)
                try:
                    self.assertEqual(future.result(timeout=30), 'SYNC_PAUSED=' + pause)
                finally:
                    proc.kill()
                    proc.wait(timeout=10)
        finally:
            if proc.poll() is None:
                proc.kill()
            proc.communicate(timeout=10)

    def test_01_missing_table_or_column_fails_closed(self):
        for missing in ('table', 'column'):
            with self.subTest(missing=missing):
                if missing == 'table':
                    self.sql(f'ALTER TABLE {self.schema}.t_sync_operacion RENAME TO sync_unavailable')
                else:
                    self.sql(f'ALTER TABLE {self.schema}.t_sync_operacion RENAME COLUMN request_hash TO hash_unavailable')
                try:
                    for kind in ('VENTA_CONTADO', 'RESERVA_SOLICITUD', 'CART_ADD_ITEM'):
                        op = self.operation(kind)
                        with self.assertLogs(sync_routes.logger, level='ERROR'):
                            result = self.send(op)
                        self.assertEqual(result['status'], 'failed_retryable')
                        self.assertFalse(result['confirmation_verified'])
                    self.assertEqual(self.effects(), self.before)
                    self.assertEqual(self.stock(), (20, 0, 20))
                finally:
                    if missing == 'table':
                        self.sql(f'ALTER TABLE {self.schema}.sync_unavailable RENAME TO t_sync_operacion')
                    else:
                        self.sql(f'ALTER TABLE {self.schema}.t_sync_operacion RENAME COLUMN hash_unavailable TO request_hash')

    def test_02_concurrent_same_key_http(self):
        for kind in ('VENTA_CONTADO', 'RESERVA_SOLICITUD'):
            with self.subTest(kind=kind):
                self.setUp()
                op = self.operation(kind)
                barrier = threading.Barrier(8)
                def request(_):
                    barrier.wait(timeout=10)
                    return self.send(op)
                with ThreadPoolExecutor(max_workers=8) as pool:
                    results = list(pool.map(request, range(8)))
                self.assertTrue(all(r['status'] == 'synced' and r['confirmation_verified'] for r in results), results)
                self.assertEqual(sum(not r['idempotent_replay'] for r in results), 1)
                self.assert_one_effect(kind)

    def test_03_concurrent_different_keys_cannot_oversell(self):
        self.sql(f'UPDATE {self.schema}.t_inventario SET stock_actual=2,stock_disponible=2 WHERE id_sucursal=1 AND id_variante=100')
        ops = [self.operation(kind, 2) for kind in ('VENTA_CONTADO', 'RESERVA_SOLICITUD')]
        with ThreadPoolExecutor(max_workers=2) as pool:
            results = list(pool.map(self.send, ops))
        self.assertEqual(sum(r['status'] == 'synced' for r in results), 1, results)
        self.assertTrue(all(s >= 0 for s in self.stock()))
        self.assertEqual(self.stock()[2], 0)
        self.assertEqual(self.effects()['t_movimiento_inventario'] - self.before['t_movimiento_inventario'], 1)

    def test_04_failure_after_payment_rolls_back_all_business_effects(self):
        original = sync_routes.caja_pago_repos.ejecutar_pago_caja
        def fail(**kwargs):
            original(**kwargs)
            raise ValueError('Injected failure after payment and denominations')
        op = self.operation()
        with patch.object(sync_routes.caja_pago_repos, 'ejecutar_pago_caja', fail):
            result = self.send(op)
        self.assertEqual(result['status'], 'reconciliation_required')
        self.assertEqual(self.effects(), self.before)
        self.assertEqual(self.stock(), (20, 0, 20))
        self.assertEqual(self.send(op)['status'], 'synced')
        self.assert_one_effect('VENTA_CONTADO')

    def test_05_receipt_write_failure_rolls_back_sale_and_reservation(self):
        for kind in ('VENTA_CONTADO', 'RESERVA_SOLICITUD'):
            with self.subTest(kind=kind):
                self.setUp()
                op = self.operation(kind)
                self.sql(f"""CREATE OR REPLACE FUNCTION {self.schema}.reject_receipt() RETURNS trigger AS $$
                    BEGIN RAISE EXCEPTION 'Injected receipt write failure'; END; $$ LANGUAGE plpgsql;
                    CREATE TRIGGER reject_receipt BEFORE INSERT OR UPDATE ON {self.schema}.t_sync_operacion
                    FOR EACH ROW EXECUTE FUNCTION {self.schema}.reject_receipt();""")
                try:
                    with self.assertLogs(sync_routes.logger, level='ERROR'):
                        result = self.send(op)
                    self.assertEqual(result['status'], 'failed_retryable')
                    self.assertFalse(result['confirmation_verified'])
                    self.assertEqual(self.effects(), self.before)
                    self.assertEqual(self.stock(), (20, 0, 20))
                finally:
                    self.sql(f'DROP TRIGGER reject_receipt ON {self.schema}.t_sync_operacion; DROP FUNCTION {self.schema}.reject_receipt()')
                self.assertEqual(self.send(op)['status'], 'synced')
                self.assert_one_effect(kind)

    def test_06_killed_process_before_commit_can_retry_once(self):
        for kind in ('VENTA_CONTADO', 'RESERVA_SOLICITUD'):
            with self.subTest(kind=kind):
                self.setUp()
                op = self.operation(kind)
                self.kill_worker(op, 'before_commit')
                self.assertEqual(self.effects(), self.before)
                self.assertEqual(self.worker(op)['status'], 'synced')
                self.assert_one_effect(kind)

    def test_07_lost_http_response_replays_after_process_restart(self):
        for kind in ('VENTA_CONTADO', 'RESERVA_SOLICITUD'):
            with self.subTest(kind=kind):
                self.setUp()
                op = self.operation(kind)
                self.kill_worker(op, 'after_commit')
                result = self.worker(op)
                self.assertEqual(result['status'], 'synced')
                self.assertTrue(result['idempotent_replay'])
                self.assertTrue(result['confirmation_verified'])
                self.assert_one_effect(kind)

    def test_08_same_key_concurrent_processes(self):
        op = self.operation()
        with ThreadPoolExecutor(max_workers=2) as pool:
            results = list(pool.map(self.worker, [op, op]))
        self.assertTrue(all(r['status'] == 'synced' for r in results), results)
        self.assertEqual(sum(not r['idempotent_replay'] for r in results), 1)
        self.assert_one_effect('VENTA_CONTADO')

    def test_09_key_reuse_and_legacy_receipt_require_review(self):
        op = self.operation()
        first = self.send(op)
        self.assertEqual(first['status'], 'synced')
        changed = deepcopy(op)
        changed['payload']['items'][0]['cantidad'] = 3
        self.assertEqual(self.send(changed)['conflict_code'], 'IDEMPOTENCY_KEY_REUSED')
        changed['kind'] = 'RESERVA_SOLICITUD'
        self.assertEqual(self.send(changed)['conflict_code'], 'IDEMPOTENCY_KEY_REUSED')
        self.sql(f'UPDATE {self.schema}.t_sync_operacion SET request_hash=NULL WHERE operation_id=%s', (op['operation_id'],))
        result = self.send(op)
        self.assertEqual(result['conflict_code'], 'LEGACY_RECEIPT_REQUIRES_REVIEW')
        self.assertFalse(result['confirmation_verified'])
        self.assert_one_effect('VENTA_CONTADO')

    def test_10_replay_still_checks_tenant_and_branch_authority(self):
        op = self.operation()
        self.assertEqual(self.send(op)['status'], 'synced')
        result = self.send(op, user_id=4)
        self.assertEqual(result['conflict_code'], 'TENANT_FORBIDDEN')
        self.assertFalse(result['confirmation_verified'])
        self.assert_one_effect('VENTA_CONTADO')

    def test_11_duplicate_variants_are_rejected_without_side_effects(self):
        op = self.operation()
        op['payload']['items'] *= 2
        result = self.send(op)
        self.assertEqual(result['conflict_code'], 'INVALID_PAYLOAD')
        self.assertEqual(self.effects(), self.before)

    def test_11_unknown_operations_before_cutover_are_preserved_for_review(self):
        for kind in ('VENTA_CONTADO', 'RESERVA_SOLICITUD'):
            for created in (None, '2020-01-01T00:00:00Z', 'invalid-date'):
                with self.subTest(kind=kind, created=created):
                    op = self.operation(kind)
                    op['created_at'] = created
                    result = self.send(op)
                    self.assertEqual(result['conflict_code'], 'LEGACY_OPERATION_REQUIRES_REVIEW')
                    self.assertFalse(result['confirmation_verified'])
                    self.assertEqual(result['operation_id'], op['operation_id'])
                    self.assertEqual(self.effects(), self.before)

    def test_12_migration_004_reversal_preserves_receipts(self):
        op = self.operation()
        self.assertEqual(self.send(op)['status'], 'synced')
        receipt = self.sql(f'SELECT response_json FROM {self.schema}.t_sync_operacion WHERE operation_id=%s', (op['operation_id'],))
        self.sql(render(ROOT / 'backend/migrations/004_iter2_sync_transactional.down.sql', self.schema))
        self.assertEqual(self.sql(f'SELECT response_json FROM {self.schema}.t_sync_operacion WHERE operation_id=%s', (op['operation_id'],)), receipt)
        self.sql(render(ROOT / 'backend/migrations/004_iter2_sync_transactional.up.sql', self.schema))
        self.assertEqual(self.send(op)['conflict_code'], 'LEGACY_RECEIPT_REQUIRES_REVIEW')

    def test_12_migration_cli_004_checksums_and_idempotency(self):
        schema = 'migration_' + uuid.uuid4().hex
        with psycopg2.connect(**self.pg.params) as conn, conn.cursor() as cur:
            cur.execute(f'CREATE SCHEMA {schema}; SET search_path TO {schema}')
            cur.execute((ROOT / 'tests/p1_fixture.sql').read_text(encoding='utf-8'))
            cur.execute(render(ROOT / 'backend/migrations/003_iter2_sync_idempotency.up.sql', schema))
        env = dict(os.environ, DB_HOST='127.0.0.1', DB_PORT=str(self.pg.params['port']),
                   DB_NAME='postgres', DB_USER='iter1_test', DB_PASSWORD='', DB_SCHEMA=schema)
        version = '004_iter2_sync_transactional'
        def migrate(direction):
            return subprocess.run([sys.executable, '-B', str(ROOT / 'backend/migrate.py'), direction,
                                   '--version', version, '--apply'], env=env, capture_output=True, text=True, timeout=20)
        first = migrate('up')
        self.assertEqual(first.returncode, 0, first.stderr)
        self.assertIn('Sin cambios', migrate('up').stdout)
        self.sql(f"UPDATE {schema}.schema_migrations SET checksum='bad' WHERE version=%s", (version,))
        self.assertNotEqual(migrate('up').returncode, 0)
        checksum = hashlib.sha256((ROOT / f'backend/migrations/{version}.up.sql').read_bytes()).hexdigest()
        self.sql(f'UPDATE {schema}.schema_migrations SET checksum=%s WHERE version=%s', (checksum, version))
        self.assertEqual(migrate('down').returncode, 0)
        self.assertIsNone(self.sql('SELECT to_regclass(%s)', (schema + '.t_sync_control',))[0][0])
        self.assertEqual(migrate('up').returncode, 0)

    def test_12_cart_update_missing_item_keeps_original_operation_identity(self):
        op = dict(operation_id=str(uuid.uuid4()), kind='CART_UPDATE_QTY', tenant_id=1,
                  payload={'id_variante': 102, 'id_detalle_carrito': -1, 'cantidad': 2})
        result = self.send(op)
        self.assertEqual(result['status'], 'synced', result)
        self.assertEqual(result['kind'], 'CART_UPDATE_QTY')
        replay = self.send(op, endpoint='/api/sync/operations')
        self.assertTrue(replay['idempotent_replay'])
        self.assertEqual(replay['data'], result['data'])
        stored = self.sql(f'SELECT kind,request_hash FROM {self.schema}.t_sync_operacion WHERE operation_id=%s', (op['operation_id'],))[0]
        self.assertEqual(stored, ('CART_UPDATE_QTY', result['confirmation']['request_hash']))
        self.assertEqual(self.effects(), self.before)

    def test_13_postgres_crash_restart_retains_committed_receipts(self):
        ops = [self.operation(kind) for kind in ('VENTA_CONTADO', 'RESERVA_SOLICITUD')]
        first = [self.send(op) for op in ops]
        self.assertTrue(all(r['status'] == 'synced' for r in first), first)
        expected_effects, expected_stock = self.effects(), self.stock()
        if PostgreSQL._pool:
            PostgreSQL._pool.closeall()
            PostgreSQL._pool = None
        # Only the disposable cluster is stopped, with fsync ON. This forces WAL
        # recovery rather than a graceful database shutdown.
        assert self.pg.durable and self.pg.params['host'] == '127.0.0.1'
        self.pg.crash_restart()
        for op, stored in zip(ops, first):
            replay = self.worker(op)
            self.assertEqual(replay['data'], stored['data'])
            self.assertTrue(replay['idempotent_replay'])
            self.assertTrue(replay['confirmation_verified'])
        self.assertEqual(self.effects(), expected_effects)
        self.assertEqual(self.stock(), expected_stock)


if __name__ == '__main__':
    unittest.main(verbosity=2)
