"""Directed regressions. Every database mutation targets disposable LocalPostgres."""
from concurrent.futures import ThreadPoolExecutor
from copy import deepcopy
from decimal import Decimal
from datetime import datetime, timedelta
from pathlib import Path
import sys
import subprocess
import json
import unittest
from unittest.mock import patch

import psycopg2
from fastapi import HTTPException

sys.path.insert(0, str(Path(__file__).resolve().parent))
import test_devoluciones_iter3 as returns_fixture
import test_sync_transactional as stock_fixture
from app.core.postgres import PostgreSQL, atomic, _invalidar_caches_seguridad
from app.core.inventory_integrity import lock_position
from app.modules.pedidos.repos.devolucion_importes import line_entitlements, partial_amount
from app.modules.pedidos.services import devoluciones_services as returns
from app.modules.ecommerce.repos.carrito_repos import obtener_o_crear_cliente
from app.modules.catalogo.repos import productos_repos
from app.modules.pos.repos import pos_repos, caja_pago_repos, caja_repos
from app.modules.reservas.repos import reserva_repos
from app.modules.inventario.repos import inventario_repos
from app.modules.ecommerce.repos import pago_repos
from app.modules.inventario.services import compras_lotes_services as purchases
from app.modules.reservas.repos import atender_reserva_repos
from app.core.security import _contexto_vigente
from app.core.config import Config
from migrate import render

ROOT = Path(__file__).resolve().parents[1]


class RefundMoneyUnitTests(unittest.TestCase):
    def test_header_discount_applied_once(self):
        for line in (Decimal('300'), Decimal('270')):
            allocation = line_entitlements([(1,1,3,100,0,line)],300,30,270)
            self.assertEqual(allocation,{1:27000})

    def test_residual_cent_and_partial_cap(self):
        values = [partial_amount(10000,3,n,1) for n in range(3)]
        self.assertEqual(values,[Decimal('33.33'),Decimal('33.33'),Decimal('33.34')])
        self.assertEqual(sum(values),Decimal('100'))
        with self.assertRaises(HTTPException):
            partial_amount(10000,3,3,1)

    def test_largest_remainder_is_stable(self):
        rows = [(3,1,1,1,0,1),(1,1,1,1,0,1),(2,1,1,1,0,1)]
        self.assertEqual(line_entitlements(rows,3,'0.01','2.99'),{1:100,2:100,3:99})

    def test_shipping_does_not_increase_merchandise_cap(self):
        self.assertEqual(line_entitlements([(1,1,1,300,0,300)],300,30,290),{1:27000})

    def test_ambiguous_totals_fail_closed(self):
        with self.assertRaises(HTTPException):
            line_entitlements([(1,1,1,100,0,100)],300,30,270)


class CriticalReturnsIntegration(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        returns_fixture.TestDevolucionesIteracion3.setUpClass.__func__(cls)
        cls.addClassCleanup(returns_fixture.TestDevolucionesIteracion3.tearDownClass.__func__,cls)
        # Real schema has no unique account/profile constraint; reproduce it here.
        with psycopg2.connect(**cls.pg.params) as conn, conn.cursor() as cur:
            cur.execute(f'ALTER TABLE {cls.schema}.t_cliente DROP CONSTRAINT t_cliente_id_usuario_key')

    def sql(self,query,params=None):
        with psycopg2.connect(**self.pg.params) as conn, conn.cursor() as cur:
            cur.execute(f'SET search_path TO {self.schema}')
            cur.execute(query,params)
            return cur.fetchall() if cur.description else None

    def setUp(self):
        returns_fixture.TestDevolucionesIteracion3.setUp(self)
        self.sql('DELETE FROM t_bitacora')
        self.sql('DELETE FROM t_sync_operacion')
        self.sql('DELETE FROM t_cliente WHERE id_cliente=99')
        self.sql('UPDATE t_venta SET subtotal=600,descuento=50,total=550 WHERE id_venta=1')
        self.sql('UPDATE t_detalle_venta SET cantidad=2,subtotal=550 WHERE id_detalle_venta=1')
        self.sql('UPDATE t_producto_talla_color SET id_talla=1 WHERE id_variante=1')
        self.__class__.actor_actual=self.user_cliente
        self.payload=dict(id_venta=1,motivo='TALLA_INCORRECTA',descripcion='critical test',
                          items=[dict(id_detalle_venta=1,cantidad=1)])

    def request(self,**changes):
        payload={**deepcopy(self.payload),**changes}
        return self.client.post('/api/devoluciones/solicitudes',json=payload)

    def approve(self,quantity=1):
        result=self.request(items=[dict(id_detalle_venta=1,cantidad=quantity)])
        self.assertEqual(result.status_code,201,result.text)
        key=result.json()['id_devolucion']
        self.__class__.actor_actual=self.user_encargado
        approved=self.client.post(f'/api/devoluciones/{key}/revisar',json=dict(accion='APROBAR',observaciones='Aprobado'))
        self.assertEqual(approved.status_code,200,approved.text)
        detail=self.sql('SELECT id_detalle_devolucion FROM t_detalle_devolucion WHERE id_devolucion=%s',(key,))[0][0]
        return key,detail

    def receive(self,key,detail,quantity=1,condition='REVENDIBLE',branch=1):
        return self.client.post(f'/api/devoluciones/{key}/recepcion',json=dict(id_sucursal=branch,
            items=[dict(id_detalle_devolucion=detail,cantidad_recibida=quantity,condicion=condition)]))

    def test_client_tenant_derived_and_old_profile_authorized(self):
        self.sql('INSERT INTO t_cliente(id_cliente,id_usuario) VALUES(99,5)')
        self.sql('UPDATE t_venta SET id_cliente=99 WHERE id_venta=1')
        try:
            with self.assertRaises(HTTPException) as err:
                obtener_o_crear_cliente(5)
            self.assertEqual(err.exception.status_code,409)
            result=self.request()
            self.assertEqual(result.status_code,201,result.text)
            self.assertEqual(self.sql('SELECT id_empresa FROM t_devolucion')[0][0],1)
            self.assertEqual(self.request(id_empresa=2).status_code,403)
        finally:
            self.sql('UPDATE t_venta SET id_cliente=1 WHERE id_venta=1')

    def test_duplicate_body_rejected_without_mutation(self):
        result=self.request(items=[dict(id_detalle_venta=1,cantidad=2)]*2)
        self.assertEqual(result.status_code,400,result.text)
        self.assertEqual(self.sql('SELECT count(*) FROM t_devolucion')[0][0],0)

    def test_repeat_and_concurrent_same_intent_one_request(self):
        with ThreadPoolExecutor(max_workers=6) as pool:
            responses=list(pool.map(lambda _:self.request(),range(6)))
        self.assertTrue(all(r.status_code==201 for r in responses),[r.text for r in responses])
        self.assertEqual(len({r.json()['id_devolucion'] for r in responses}),1)
        self.assertEqual(self.sql('SELECT count(*) FROM t_devolucion')[0][0],1)
        self.assertEqual(self.sql('SELECT count(*) FROM t_bitacora')[0][0],1)

    def test_lost_response_new_process_replays_committed_request(self):
        config={name:getattr(Config,name) for name in ('DB_HOST','DB_PORT','DB_NAME','DB_USER','DB_PASSWORD','SCHEMA','TOKEN_KEY','SECRET_KEY')}
        command=[sys.executable,str(ROOT/'tests/critical_process_worker.py')]
        lost=subprocess.run(command,input=json.dumps(dict(config=config,payload=self.payload,drop_response=True)),
                            text=True,capture_output=True,timeout=30)
        self.assertEqual(lost.returncode,0,lost.stderr)
        self.assertEqual(lost.stdout,'')
        committed=self.sql('SELECT id_devolucion FROM t_devolucion')[0][0]
        replay=subprocess.run(command,input=json.dumps(dict(config=config,payload=self.payload)),
                              text=True,capture_output=True,timeout=30)
        self.assertEqual(replay.returncode,0,replay.stderr)
        result=json.loads(replay.stdout)
        self.assertEqual(result['http_status'],201,result)
        self.assertEqual(result['body']['id_devolucion'],committed)
        self.assertTrue(result['body']['idempotent_replay'])
        self.assertEqual(self.sql('SELECT count(*) FROM t_devolucion')[0][0],1)

    def test_concurrent_distinct_requests_cannot_exceed_sold(self):
        with ThreadPoolExecutor(max_workers=2) as pool:
            responses=list(pool.map(lambda n:self.request(descripcion=f'intent {n}',items=[dict(id_detalle_venta=1,cantidad=2)]),range(2)))
        self.assertEqual(sorted(r.status_code for r in responses),[201,400],[r.text for r in responses])
        self.assertEqual(self.sql('SELECT sum(cantidad) FROM t_detalle_devolucion')[0][0],2)

    def test_header_discount_is_not_refunded(self):
        self.sql('UPDATE t_detalle_venta SET subtotal=600 WHERE id_detalle_venta=1')
        result=self.request()
        self.assertEqual(result.status_code,201,result.text)
        self.assertEqual(result.json()['monto_reembolso'],275)
        self.assertEqual(self.sql('SELECT monto_reembolso FROM t_detalle_devolucion')[0][0],Decimal('275'))

    def test_existing_overallocated_money_cannot_increase_refund_cap(self):
        self.assertEqual(self.request().status_code,201)
        self.sql('UPDATE t_detalle_devolucion SET monto_reembolso=550')
        result=self.request(descripcion='another actual request')
        self.assertEqual(result.status_code,409,result.text)
        self.assertEqual(self.sql('SELECT sum(monto_reembolso) FROM t_detalle_devolucion')[0][0],Decimal('550'))

    def test_partial_receipt_rejected_without_stock_or_state_change(self):
        key,detail=self.approve(2)
        result=self.receive(key,detail,1)
        self.assertEqual(result.status_code,409,result.text)
        self.assertIn('PARTIAL_RECEIPT_REQUIRES_MIGRATION',result.text)
        self.assertEqual(self.sql('SELECT stock_actual,stock_disponible FROM t_inventario')[0],(10,10))
        self.assertEqual(self.sql('SELECT estado FROM t_devolucion')[0][0],'PENDIENTE_RECEPCION')

    def test_full_receipt_replay_once_with_durable_audit(self):
        key,detail=self.approve()
        first=self.receive(key,detail)
        self.assertEqual(first.status_code,200,first.text)
        # Recreate the connection pool to discard all per-process connection state.
        PostgreSQL._pool.closeall();PostgreSQL._pool=None
        repeat=self.receive(key,detail)
        self.assertEqual(repeat.status_code,200,repeat.text)
        self.assertTrue(repeat.json()['idempotent_replay'])
        self.assertEqual(self.sql('SELECT stock_actual,stock_disponible FROM t_inventario')[0],(11,11))
        self.assertEqual(self.sql('SELECT count(*) FROM t_movimiento_inventario')[0][0],1)
        audit=self.sql("SELECT datos_nuevos FROM t_bitacora WHERE accion='RECEPCION_PRENDAS_DEVOLUCION'")[0][0]
        self.assertEqual(audit['items_recibidos'][0]['cantidad_recibida'],1)
        self.assertEqual(audit['id_usuario_receptor'],6)

    def test_audit_failure_rolls_back_receipt_and_stock(self):
        key,detail=self.approve()
        with patch.object(returns,'registrar_evento_db',side_effect=RuntimeError('injected audit failure')):
            result=self.receive(key,detail)
        self.assertEqual(result.status_code,500,result.text)
        self.assertEqual(self.sql('SELECT stock_actual FROM t_inventario')[0][0],10)
        self.assertEqual(self.sql('SELECT estado FROM t_devolucion')[0][0],'PENDIENTE_RECEPCION')
        self.assertEqual(self.sql('SELECT count(*) FROM t_movimiento_inventario')[0][0],0)
        self.assertEqual(self.receive(key,detail).status_code,200)

    def test_audit_failure_rolls_back_request(self):
        with patch.object(returns,'registrar_evento_db',return_value=None):
            result=self.request()
        self.assertEqual(result.status_code,503,result.text)
        self.assertEqual(self.sql('SELECT count(*) FROM t_devolucion')[0][0],0)

    def test_foreign_destination_and_branch_rejected(self):
        key,detail=self.approve()
        self.assertEqual(self.receive(key,detail,branch=2).status_code,403)
        self.assertEqual(self.sql('SELECT count(*) FROM t_movimiento_inventario')[0][0],0)

    def test_platform_and_company_admin_can_review(self):
        for actor in (self.user_admin,self.user_admin_tienda):
            self.setUp()
            created=self.request()
            self.__class__.actor_actual=actor
            key=created.json()['id_devolucion']
            result=self.client.post(f'/api/devoluciones/{key}/revisar',json=dict(accion='RECHAZAR',observaciones='Rechazo validado'))
            self.assertEqual(result.status_code,200,result.text)
            self.assertEqual(result.json()['nuevo_estado'],'RECHAZADA')

    def test_cashier_cannot_review_and_foreign_client_cannot_receive(self):
        key,detail=self.approve()
        for actor in (self.user_cajero,self.user_cliente2):
            self.__class__.actor_actual=actor
            result=self.client.post(f'/api/devoluciones/{key}/revisar',json=dict(accion='RECHAZAR',observaciones='No autorizado'))
            self.assertEqual(result.status_code,403,result.text)

    def test_nested_sync_receipt_conflict_blocks_request(self):
        self.sql('''INSERT INTO t_sync_operacion(operation_id,id_usuario,id_empresa,kind,status,http_status,conflict_code,response_json)
            VALUES('00000000-0000-0000-0000-000000000123',5,1,'VENTA_CONTADO','reconciliation_required',409,'LEGACY',%s::jsonb)''', ('{"data":{"id_venta":1}}',))
        result=self.request()
        self.assertEqual(result.status_code,409,result.text)
        self.assertEqual(self.sql('SELECT count(*) FROM t_devolucion')[0][0],0)

    def test_legacy_synced_receipt_without_proof_blocks_request(self):
        self.sql('''INSERT INTO t_sync_operacion(operation_id,id_usuario,id_empresa,kind,status,http_status,response_json)
            VALUES('00000000-0000-0000-0000-000000000124',3,1,'VENTA_CONTADO','synced',200,%s::jsonb)''', ('{"id_venta":1}',))
        result=self.request()
        self.assertEqual(result.status_code,409,result.text)
        self.assertEqual(self.sql('SELECT count(*) FROM t_devolucion')[0][0],0)

    def test_verified_nested_receipt_allows_own_sale(self):
        key='00000000-0000-0000-0000-000000000125'
        receipt=dict(data=dict(id_venta=1),confirmation_verified=True,
                     confirmation=dict(operation_id=key,id_usuario=3,id_empresa=1,request_hash='a'*64))
        self.sql('''INSERT INTO t_sync_operacion(operation_id,id_usuario,id_empresa,kind,status,http_status,response_json,request_hash)
            VALUES(%s,3,1,'VENTA_CONTADO','synced',200,%s::jsonb,%s)''', (key,json.dumps(receipt),'a'*64))
        self.assertEqual(self.request().status_code,201)

    def test_missing_schema_or_receipts_fails_closed(self):
        self.sql('ALTER TABLE t_devolucion RENAME COLUMN codigo_devolucion TO codigo_unavailable')
        try:
            self.assertEqual(self.request().status_code,503)
        finally:
            self.sql('ALTER TABLE t_devolucion RENAME COLUMN codigo_unavailable TO codigo_devolucion')
        self.sql('ALTER TABLE t_sync_operacion RENAME TO sync_unavailable')
        try:
            self.assertEqual(self.request().status_code,503)
        finally:
            self.sql('ALTER TABLE sync_unavailable RENAME TO t_sync_operacion')
        self.sql('ALTER TABLE t_sync_operacion RENAME COLUMN request_hash TO hash_unavailable')
        try:
            self.assertEqual(self.request().status_code,503)
        finally:
            self.sql('ALTER TABLE t_sync_operacion RENAME COLUMN hash_unavailable TO request_hash')


class CriticalStockIntegration(unittest.TestCase):
    _headers_for_user=stock_fixture.TransactionalSyncSuite._headers_for_user
    sql=stock_fixture.TransactionalSyncSuite.sql
    stock=stock_fixture.TransactionalSyncSuite.stock
    effects=stock_fixture.TransactionalSyncSuite.effects

    @classmethod
    def setUpClass(cls):
        stock_fixture.TransactionalSyncSuite.setUpClass.__func__(cls)
        with psycopg2.connect(**cls.pg.params) as conn, conn.cursor() as cur:
            # Match missing real constraints so races cannot be hidden by the fixture.
            cur.execute(f'''ALTER TABLE {cls.schema}.t_inventario DROP CONSTRAINT t_inventario_id_sucursal_id_variante_key;
                ALTER TABLE {cls.schema}.t_cliente DROP CONSTRAINT t_cliente_id_usuario_key;
                ALTER TABLE {cls.schema}.t_producto_talla_color DROP CONSTRAINT t_producto_talla_color_id_producto_id_talla_id_color_key;
                ALTER TABLE {cls.schema}.t_reserva ADD COLUMN fecha_cancelacion TIMESTAMP,ADD COLUMN motivo_cancelacion TEXT;
                ALTER TABLE {cls.schema}.t_cliente ADD COLUMN IF NOT EXISTS ci TEXT;
                CREATE TABLE {cls.schema}.t_pedido(id_pedido SERIAL PRIMARY KEY,codigo_pedido TEXT,id_cliente INTEGER,
                    id_empresa INTEGER,id_sucursal INTEGER,estado TEXT DEFAULT 'PENDIENTE_PAGO',estado_pago TEXT DEFAULT 'PENDIENTE',
                    subtotal NUMERIC,descuento NUMERIC,total NUMERIC,id_venta INTEGER,fecha_actualizacion TIMESTAMP);
                CREATE TABLE {cls.schema}.t_detalle_pedido(id_detalle_pedido SERIAL PRIMARY KEY,id_pedido INTEGER,
                    id_variante INTEGER,cantidad INTEGER,precio_unitario NUMERIC,subtotal NUMERIC);
                CREATE TABLE {cls.schema}.t_proveedor(id_proveedor SERIAL PRIMARY KEY,razon_social TEXT,estado BOOLEAN);
                CREATE TABLE {cls.schema}.t_lote(id_lote SERIAL PRIMARY KEY,id_empresa INTEGER,id_sucursal INTEGER,
                    id_orden_compra INTEGER,id_proveedor INTEGER,numero_lote TEXT,guia_remision TEXT,total_prendas INTEGER,
                    costo_total_lote NUMERIC,id_usuario_receptor INTEGER,observaciones TEXT);
                CREATE TABLE {cls.schema}.t_orden_compra(id_orden_compra SERIAL PRIMARY KEY,id_empresa INTEGER,id_sucursal INTEGER,
                    id_proveedor INTEGER,estado TEXT,numero_orden TEXT,total_estimado NUMERIC);
                CREATE TABLE {cls.schema}.t_detalle_orden_compra(id_detalle_orden SERIAL PRIMARY KEY,id_orden_compra INTEGER,
                    id_producto INTEGER,id_variante INTEGER,cantidad_solicitada INTEGER,cantidad_recibida INTEGER,
                    costo_unitario NUMERIC,sku TEXT,nombre_producto TEXT);
            ''')
            for name in ('fn_confirmar_pago_pedido','fn_movimiento_inventario'):
                cur.execute(render(ROOT/f'tests/sql/{name}_snapshot.sql',cls.schema))
            for table,key in [('t_categoria','id_categoria'),('t_talla','id_talla'),('t_color','id_color'),
                              ('t_producto','id_producto'),('t_producto_talla_color','id_variante')]:
                cur.execute(f"SELECT setval(pg_get_serial_sequence('{cls.schema}.{table}','{key}'),(SELECT max({key}) FROM {cls.schema}.{table}),true)")

    def setUp(self):
        stock_fixture.TransactionalSyncSuite.setUp(self)
        self.sql(f'UPDATE {self.schema}.t_producto_talla_color SET id_talla=1 WHERE id_variante=100')
        self.sql(f"UPDATE {self.schema}.t_caja_sesion SET estado='ABIERTA' WHERE id_usuario=3 AND id_sucursal=1")

    def sale(self,quantity=1,variant=100):
        session=self.sql(f"SELECT id_sesion_caja FROM {self.schema}.t_caja_sesion WHERE id_usuario=3 AND id_sucursal=1 AND estado='ABIERTA' ORDER BY id_sesion_caja LIMIT 1")[0][0]
        return pos_repos.ejecutar_registro_venta_pos(session,3,1,1,None,[dict(id_variante=variant,cantidad=quantity)])

    def test_cross_tenant_catalog_rejected_without_new_variant(self):
        with self.assertRaises(HTTPException) as err:
            productos_repos.sincronizar_variantes_producto(10,[3],[1],150)
        self.assertEqual(err.exception.status_code,403)

    def test_pos_rejects_crossed_historical_variant(self):
        self.sql(f'UPDATE {self.schema}.t_producto_talla_color SET id_talla=3 WHERE id_variante=100')
        with self.assertRaises(HTTPException) as err:
            self.sale()
        self.assertEqual(err.exception.status_code,403)
        self.assertEqual(self.effects(),self.before)

    def test_last_unit_concurrent_direct_sales(self):
        self.sql(f'UPDATE {self.schema}.t_inventario SET stock_actual=1,stock_disponible=1 WHERE id_sucursal=1 AND id_variante=100')
        def sell(_):
            try:return self.sale()['success']
            except (HTTPException,ValueError):return False
        with ThreadPoolExecutor(max_workers=4) as pool:
            results=list(pool.map(sell,range(4)))
        self.assertEqual(sum(results),1,results)
        self.assertEqual(self.stock(),(0,0,0))

    def test_dirty_stock_is_not_silently_recalculated(self):
        self.sql(f'UPDATE {self.schema}.t_inventario SET stock_disponible=999 WHERE id_sucursal=1 AND id_variante=100')
        with self.assertRaises(HTTPException) as err:self.sale()
        self.assertEqual(err.exception.status_code,409)
        self.assertEqual(self.stock(),(20,0,999))
        self.assertEqual(self.effects(),self.before)

    def test_inventory_duplicate_guard(self):
        self.sql(f'INSERT INTO {self.schema}.t_inventario(id_sucursal,id_variante,stock_actual,stock_reservado,stock_disponible) VALUES(1,100,1,0,1)')
        try:
            with self.assertRaises(HTTPException) as err:self.sale()
            self.assertEqual(err.exception.status_code,409)
        finally:
            self.sql(f'DELETE FROM {self.schema}.t_inventario WHERE id_sucursal=1 AND id_variante=100 AND id_inventario<>(SELECT min(id_inventario) FROM {self.schema}.t_inventario WHERE id_sucursal=1 AND id_variante=100)')

    def test_absent_position_concurrent_receipts_one_position(self):
        from app.modules.pedidos.repos.devoluciones_repos import _reincorporar_stock_inventario
        # A legitimate tenant-1 variant without a position, not the foreign variant 200.
        self.sql(f'INSERT INTO {self.schema}.t_producto_talla_color(id_variante,id_producto,id_talla,id_color,sku,precio) VALUES(900,10,1,1,\'ABSENT-900\',150) ON CONFLICT DO NOTHING')
        @atomic
        def receive_valid(_):
            db=PostgreSQL();db.create_connection()
            try:_reincorporar_stock_inventario(db,self.schema,1,900,1,3,'test absent receipt')
            finally:db.close_connection()
        with ThreadPoolExecutor(max_workers=6) as pool:list(pool.map(receive_valid,range(6)))
        self.assertEqual(self.sql(f'SELECT count(*),sum(stock_actual),sum(stock_disponible) FROM {self.schema}.t_inventario WHERE id_sucursal=1 AND id_variante=900')[0],(1,6,6))

    def test_generated_sku_collision_does_not_change_history(self):
        self.sql(f"INSERT INTO {self.schema}.t_color(id_color,nombre,codigo_hex,id_empresa) VALUES(90,'Negrura','#111111',1) ON CONFLICT DO NOTHING")
        code=self.sql(f'SELECT codigo_producto FROM {self.schema}.t_producto WHERE id_producto=10')[0][0]
        expected=f'{code}-M-NEGR'
        self.sql(f'UPDATE {self.schema}.t_producto_talla_color SET sku=%s WHERE id_variante=100',(expected,))
        try:
            with self.assertRaises(HTTPException) as err:
                productos_repos.sincronizar_variantes_producto(10,[1],[90],150)
            self.assertEqual(err.exception.status_code,409)
            self.assertEqual(self.sql(f'SELECT sku FROM {self.schema}.t_producto_talla_color WHERE id_variante=100')[0][0],expected)
        finally:
            self.sql(f"UPDATE {self.schema}.t_producto_talla_color SET sku='SKU-A10-M-NEG' WHERE id_variante=100")

    def test_concurrent_generation_without_triple_unique_one_variant(self):
        self.sql(f"INSERT INTO {self.schema}.t_producto(id_producto,nombre,codigo_producto,precio,id_categoria,id_empresa) VALUES(800,'Concurrent product','CRITICAL-800',150,1,1)")
        with ThreadPoolExecutor(max_workers=4) as pool:
            list(pool.map(lambda _:productos_repos.sincronizar_variantes_producto(800,[1],[1],150),range(4)))
        self.assertEqual(self.sql(f'SELECT count(*) FROM {self.schema}.t_producto_talla_color WHERE id_producto=800')[0][0],1)

    def test_cashbox_concurrent_opening_one_session(self):
        self.sql(f"INSERT INTO {self.schema}.t_caja(id_caja,id_sucursal,id_empresa,codigo_caja,nombre,estado) VALUES(99,1,1,'CRITICAL-99','Critical','ACTIVA')")
        self.sql(f"UPDATE {self.schema}.t_caja_sesion SET estado='CERRADA' WHERE id_usuario=3 AND id_sucursal=1")
        def opening(user):
            try:return bool(caja_repos.abrir_caja_sesion(user,1,1,99,[]))
            except ValueError:return False
        try:
            with ThreadPoolExecutor(max_workers=2) as pool:results=list(pool.map(opening,[2,3]))
            self.assertEqual(sum(results),1,results)
            self.assertEqual(self.sql(f"SELECT count(*) FROM {self.schema}.t_caja_sesion WHERE id_caja=99 AND estado='ABIERTA'")[0][0],1)
        finally:
            self.sql(f'DELETE FROM {self.schema}.t_caja_sesion WHERE id_caja=99')

    def test_underpayment_cannot_create_sale(self):
        client=obtener_o_crear_cliente(5)
        key=self.sql(f"INSERT INTO {self.schema}.t_pedido(codigo_pedido,id_cliente,id_empresa,id_sucursal,subtotal,descuento,total) VALUES('UNDERPAY',%s,1,1,150,0,150) RETURNING id_pedido",(client,))[0][0]
        self.sql(f'INSERT INTO {self.schema}.t_detalle_pedido(id_pedido,id_variante,cantidad,precio_unitario,subtotal) VALUES(%s,100,1,150,150)',(key,))
        with self.assertRaises(HTTPException) as err:pago_repos.ejecutar_confirmacion_pago(key,'EFECTIVO','underpayment',1,5)
        self.assertEqual(err.exception.status_code,400)
        self.assertEqual(self.effects(),self.before)

    def test_cashbox_tenant_pair_rejected(self):
        with self.assertRaises(HTTPException) as err:
            caja_repos.abrir_caja_sesion(3,1,1,2,[])
        self.assertEqual(err.exception.status_code,403)

    def test_stock_manual_adjustment_cannot_consume_reserved(self):
        self.sql(f'UPDATE {self.schema}.t_inventario SET stock_reservado=19,stock_disponible=1 WHERE id_sucursal=1 AND id_variante=100')
        with self.assertRaises(HTTPException) as err:
            inventario_repos.registrar_movimiento_inventario(1,100,'SALIDA',2,3,'critical',1)
        self.assertEqual(err.exception.status_code,400)
        self.assertEqual(self.stock(),(20,19,1))

    def test_profile_creation_concurrent_one_global_account(self):
        # User 4 has no commercial profile in this fixture.
        with ThreadPoolExecutor(max_workers=6) as pool:
            ids=list(pool.map(lambda _:obtener_o_crear_cliente(4),range(6)))
        self.assertEqual(len(set(ids)),1)
        self.assertEqual(self.sql(f'SELECT count(*) FROM {self.schema}.t_cliente WHERE id_usuario=4')[0][0],1)

    def test_payment_retry_concurrent_one_sale_and_stock_effect(self):
        client=obtener_o_crear_cliente(5)
        key=self.sql(f"INSERT INTO {self.schema}.t_pedido(codigo_pedido,id_cliente,id_empresa,id_sucursal,subtotal,descuento,total) VALUES('CRITICAL',%s,1,1,150,0,150) RETURNING id_pedido",(client,))[0][0]
        self.sql(f'INSERT INTO {self.schema}.t_detalle_pedido(id_pedido,id_variante,cantidad,precio_unitario,subtotal) VALUES(%s,100,1,150,150)',(key,))
        def pay(_):
            try:return pago_repos.ejecutar_confirmacion_pago(key,'EFECTIVO','critical-reference',150,5)['success']
            except HTTPException as err:
                self.assertEqual(err.status_code,409)
                return False
        with ThreadPoolExecutor(max_workers=4) as pool:results=list(pool.map(pay,range(4)))
        self.assertEqual(sum(results),1,results)
        self.assertEqual(self.stock(),(19,0,19))
        self.assertEqual(self.effects()['t_pago']-self.before['t_pago'],1)
        self.assertIsNotNone(self.sql(f'SELECT id_venta FROM {self.schema}.t_pedido WHERE id_pedido=%s',(key,))[0][0])

    def test_import_resolves_catalog_inside_tenant_and_concurrent_position(self):
        actor=_contexto_vigente({'id_usuario':2})
        row=dict(codigo_producto='CRIT-IMPORT',nombre_producto='Critical Import',categoria='Prueba',
                 talla='S',color='Rojo',cantidad=1,costo_unitario=10,subtotal_costo=10,precio_venta=20)
        payload=dict(id_empresa=1,id_sucursal=1,generar_orden_compra=False,filas=[row])
        with ThreadPoolExecutor(max_workers=3) as pool:
            results=list(pool.map(lambda _:purchases.confirmar_e_importar_lote_db(payload,actor),range(3)))
        self.assertTrue(all(r['success'] for r in results))
        rows=self.sql(f'''SELECT p.id_empresa,t.id_empresa,c.id_empresa,count(i.id_inventario),sum(i.stock_actual)
            FROM {self.schema}.t_producto p JOIN {self.schema}.t_producto_talla_color v USING(id_producto)
            JOIN {self.schema}.t_talla t USING(id_talla) JOIN {self.schema}.t_color c USING(id_color)
            JOIN {self.schema}.t_inventario i USING(id_variante)
            WHERE p.codigo_producto='CRIT-IMPORT' GROUP BY p.id_empresa,t.id_empresa,c.id_empresa''')
        self.assertEqual(rows,[(1,1,1,1,3)])

    def test_purchase_receipt_concurrent_once(self):
        actor=_contexto_vigente({'id_usuario':2})
        key=self.sql(f"INSERT INTO {self.schema}.t_orden_compra(id_empresa,id_sucursal,estado,numero_orden,total_estimado) VALUES(1,1,'APROBADA','CRITICAL-OC',150) RETURNING id_orden_compra")[0][0]
        self.sql(f'INSERT INTO {self.schema}.t_detalle_orden_compra(id_orden_compra,id_producto,id_variante,cantidad_solicitada,costo_unitario) VALUES(%s,10,100,2,75)',(key,))
        def receive(_):
            try:return purchases.recibir_mercaderia_orden_db(key,{},actor)['success']
            except ValueError:return False
        with ThreadPoolExecutor(max_workers=3) as pool:results=list(pool.map(receive,range(3)))
        self.assertEqual(sum(results),1,results)
        self.assertEqual(self.stock(),(22,0,22))

    def test_reservation_duplicate_quantities_and_cancel_once(self):
        self.sql(f'UPDATE {self.schema}.t_inventario SET stock_actual=2,stock_disponible=2 WHERE id_sucursal=1 AND id_variante=100')
        data=dict(id_sucursal=1,fecha_hora_visita=(datetime.now()+timedelta(days=1)).isoformat(),con_pago=False,
                  items=[dict(id_variante=100,cantidad=2)]*2)
        with self.assertRaises(ValueError):reserva_repos.crear_reserva(5,1,data)
        self.assertEqual(self.stock(),(2,0,2))
        data['items']=data['items'][:1]
        created=reserva_repos.crear_reserva(5,1,data)
        key=created['id_reserva']
        def cancel(_):
            try:return bool(reserva_repos.cancelar_reserva(key,5,1,'critical'))
            except ValueError:return False
        with ThreadPoolExecutor(max_workers=3) as pool:results=list(pool.map(cancel,range(3)))
        self.assertEqual(sum(results),1)
        self.assertEqual(self.stock(),(2,0,2))

    def test_company_platform_and_public_customer_multistore(self):
        actor=_contexto_vigente({'id_usuario':1})
        # Platform chooses a legitimate company/branch; it cannot mix them.
        result=purchases.confirmar_e_importar_lote_db(dict(id_empresa=2,id_sucursal=2,generar_orden_compra=False,
            filas=[dict(codigo_producto='CRIT-B',nombre_producto='Critical B',categoria='General',talla='M',
                        color='Azul',cantidad=1,costo_unitario=10,subtotal_costo=10,precio_venta=20)]),actor)
        self.assertTrue(result['success'])
        client=obtener_o_crear_cliente(5)
        data=dict(id_sucursal=2,con_pago=False,fecha_hora_visita=(datetime.now()+timedelta(days=1)).isoformat(),
                  items=[dict(id_variante=200,cantidad=1)])
        result=reserva_repos.crear_reserva(5,2,data)
        self.assertEqual(self.sql(f'SELECT id_cliente FROM {self.schema}.t_reserva WHERE id_reserva=%s',(result['id_reserva'],))[0][0],client)

    def test_duplicate_cash_payment_cannot_insert_second_payment(self):
        created=self.sale()
        key=created['id_venta']
        def pay(_):
            try:return bool(caja_pago_repos.ejecutar_pago_caja(key,3,1,monto_recibido=200,id_sucursal=1,id_empresa=1))
            except ValueError:return False
        with ThreadPoolExecutor(max_workers=3) as pool:results=list(pool.map(pay,range(3)))
        self.assertEqual(sum(results),1,results)
        self.assertEqual(self.sql(f'SELECT count(*) FROM {self.schema}.t_pago WHERE id_venta=%s',(key,))[0][0],1)

    def test_reservation_attention_rejects_other_cashiers_session_atomically(self):
        data=dict(id_sucursal=1,con_pago=False,fecha_hora_visita=(datetime.now()+timedelta(days=1)).isoformat(),
                  items=[dict(id_variante=100,cantidad=1)])
        created=reserva_repos.crear_reserva(5,1,data)
        key=created['id_reserva']
        session=self.sql(f"SELECT id_sesion_caja FROM {self.schema}.t_caja_sesion WHERE id_usuario=3 AND estado='ABIERTA'")[0][0]
        before=self.stock()
        with self.assertRaises(HTTPException) as err:
            atender_reserva_repos.cobrar_y_atender_reserva_pos(key,1,1,2,dict(id_sesion_caja=session))
        self.assertEqual(err.exception.status_code,403)
        self.assertEqual(self.stock(),before)
        self.assertEqual(self.sql(f'SELECT estado FROM {self.schema}.t_reserva WHERE id_reserva=%s',(key,))[0][0],'PENDIENTE')


if __name__=='__main__':
    unittest.main(verbosity=2)
