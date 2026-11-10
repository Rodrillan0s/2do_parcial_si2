import concurrent.futures
from datetime import datetime, timedelta, timezone
import importlib
from pathlib import Path
import sys
import types
import subprocess
import os
import unittest
from unittest.mock import patch
import uuid

import psycopg2
from fastapi import FastAPI, HTTPException
from fastapi.testclient import TestClient
from isolated_postgres import LocalPostgres

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'backend'))
# Import individual backend modules without importing app's router aggregation.
package = types.ModuleType('app')
package.__path__ = [str(ROOT / 'backend/app')]
sys.modules.setdefault('app', package)
from app.config import Config
from app.classes.postgres import PostgreSQL, transaction
from app.services import saas_services, asignaciones_services, users_services
from app.utils.security import verificar_token, _contexto_vigente, tiene_permiso
from app.utils.tenant_guard import obtener_alcance_usuario, resolver_tenant_operacion
from app.routes import saas_routes, rbac_routes, users_routes
from app.utils.saas_errors import install_handlers
from migrate import render


class Iter1Integration(unittest.TestCase):
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
        for name, value in [('DB_HOST',cls.pg.params['host']),('DB_PORT',cls.pg.params['port']),('DB_USER','iter1_test'),('DB_NAME','postgres'),('DB_PASSWORD','')]:
            setattr(Config,name,value)

    @classmethod
    def tearDownClass(cls):
        if PostgreSQL._pool:
            PostgreSQL._pool.closeall()
            PostgreSQL._pool = None
        cls.cluster.__exit__(None,None,None)

    def setUp(self):
        self.schema = 'test_' + uuid.uuid4().hex
        Config.SCHEMA = self.schema
        with psycopg2.connect(**self.pg.params) as conn:
            with conn.cursor() as cur:
                cur.execute(f'CREATE SCHEMA {self.schema}; SET search_path TO {self.schema}')
                cur.execute((ROOT / 'tests/p1_fixture.sql').read_text(encoding='utf-8'))
                cur.execute(render(ROOT / 'backend/migrations/001_iter1_saas.up.sql', self.schema))
        self.platform = _contexto_vigente({'id_usuario':1})
        self.admin = _contexto_vigente({'id_usuario':2})
        self.employee = _contexto_vigente({'id_usuario':3})
        self.app = FastAPI()
        install_handlers(self.app)
        self.app.include_router(saas_routes.router)
        self.app.include_router(rbac_routes.router,prefix='/api/rbac')
        self.app.include_router(users_routes.router,prefix='/api/usuarios')
        self.app.dependency_overrides[verificar_token] = lambda: self.actor
        self.actor = self.admin
        self.client = TestClient(self.app)

    def tearDown(self):
        with psycopg2.connect(**self.pg.params) as conn:
            with conn.cursor() as cur:
                cur.execute(f'DROP SCHEMA {self.schema} CASCADE')

    def sql(self, query, params=None, fetch=False):
        with psycopg2.connect(**self.pg.params) as conn:
            with conn.cursor() as cur:
                cur.execute(f'SET search_path TO {self.schema}')
                cur.execute(query,params)
                return cur.fetchall() if fetch else None

    def subscribe(self, plan='BASICO', empresa=1, inicio=None, fin=None):
        now = datetime.now(timezone.utc)
        return saas_services.crear_suscripcion(empresa, {'codigo_plan':plan,'inicio':inicio or now-timedelta(minutes=1),
            'fin':fin or now+timedelta(days=30),'motivo':'Asignacion de prueba'},self.platform)

    def test_fresh_context_ignores_forged_or_stale_claims(self):
        actual = _contexto_vigente({'id_usuario':3,'roles':['ADMINISTRADOR'],'id_empresa':2,'permisos':['planes.gestionar']})
        self.assertEqual(actual['id_empresa'],1)
        self.assertEqual(actual['alcance'],'SUCURSAL')
        self.assertFalse(tiene_permiso(actual,'planes.gestionar'))
        self.sql('UPDATE t_usuario SET estado=FALSE WHERE id_usuario=3')
        with self.assertRaises(HTTPException) as exc:
            _contexto_vigente({'id_usuario':3})
        self.assertEqual(exc.exception.status_code,401)

    def test_client_never_gets_platform_scope(self):
        self.assertEqual(_contexto_vigente({'id_usuario':5})['alcance'],'CLIENTE')

    def test_company_selector_is_not_authority(self):
        with self.assertRaises(HTTPException):
            resolver_tenant_operacion(self.admin,2)
        self.assertEqual(self.client.get('/api/mi-empresa/plan?id_empresa=2').status_code,403)

    def test_no_automatic_subscription_or_branch_removal(self):
        state=saas_services.consultar_plan(1)
        self.assertEqual(state['estado'],'SIN_SUSCRIPCION')
        self.assertEqual(state['uso']['sucursales_activas'],1)

    def test_basic_limit_reactivation_and_inactive_insert(self):
        self.subscribe()
        self.sql("INSERT INTO t_sucursal(id_empresa,nombre) VALUES(1,'A2')")
        with self.assertRaises(psycopg2.errors.CheckViolation):
            self.sql("INSERT INTO t_sucursal(id_empresa,nombre) VALUES(1,'A3')")
        self.sql("INSERT INTO t_sucursal(id_empresa,nombre,activo,estado) VALUES(1,'Inactive',FALSE,FALSE)")
        with self.assertRaises(psycopg2.errors.CheckViolation):
            self.sql("UPDATE t_sucursal SET activo=TRUE,estado=TRUE WHERE nombre='Inactive'")
        self.assertEqual(saas_services.consultar_plan(1)['uso']['sucursales_activas'],2)

    def test_professional_limit(self):
        self.subscribe('PROFESIONAL')
        self.sql("INSERT INTO t_sucursal(id_empresa,nombre) SELECT 1,'Branch'||n FROM generate_series(1,9) n")
        with self.assertRaises(psycopg2.errors.CheckViolation):
            self.sql("INSERT INTO t_sucursal(id_empresa,nombre) VALUES(1,'Eleven')")
        self.assertTrue(saas_services.exigir_vigencia(1,reportes=True)['vigente'])

    def test_concurrent_branch_creation_cannot_exceed_limit(self):
        self.subscribe()
        def insert(n):
            try:
                self.sql('INSERT INTO t_sucursal(id_empresa,nombre) VALUES(1,%s)',('Concurrent'+str(n),))
                return True
            except psycopg2.errors.CheckViolation:
                return False
        with concurrent.futures.ThreadPoolExecutor(max_workers=2) as executor:
            results=list(executor.map(insert,[1,2]))
        self.assertEqual(sum(results),1)

    def test_overlap_rejected_contiguous_renewal_allowed(self):
        current=self.subscribe()
        with self.assertRaises(HTTPException) as exc:
            self.subscribe()
        self.assertEqual(exc.exception.status_code,409)
        self.subscribe(inicio=current['fin'],fin=current['fin']+timedelta(days=30))
        self.assertEqual(len(saas_services.historial(1)),2)

    def test_downgrade_does_not_deactivate_branches(self):
        current=self.subscribe('PROFESIONAL')
        self.sql("INSERT INTO t_sucursal(id_empresa,nombre) VALUES(1,'A2'),(1,'A3')")
        with self.assertRaises(HTTPException) as exc:
            self.subscribe('BASICO',inicio=current['fin'],fin=current['fin']+timedelta(days=30))
        self.assertEqual(exc.exception.status_code,409)
        self.assertEqual(saas_services.consultar_plan(1)['uso']['sucursales_activas'],3)

    def test_expired_subscription_preserves_history_and_blocks_new_operations(self):
        now=datetime.now(timezone.utc)
        self.sql("INSERT INTO t_suscripcion(id_empresa,codigo_plan,inicio,fin,motivo,creado_por) VALUES(1,'BASICO',%s,%s,'Historical',1)", (now-timedelta(days=2),now-timedelta(days=1)))
        self.assertEqual(saas_services.consultar_plan(1)['estado'],'VENCIDA')
        with self.assertRaises(HTTPException):
            saas_services.exigir_vigencia(1)
        self.assertEqual(len(saas_services.historial(1)),1)
        with self.assertRaises(psycopg2.errors.CheckViolation):
            self.sql("INSERT INTO t_sucursal(id_empresa,nombre) VALUES(1,'Blocked')")

    def test_basic_cannot_use_generative_reports(self):
        self.subscribe()
        with self.assertRaises(HTTPException) as exc:
            saas_services.exigir_vigencia(1,reportes=True)
        self.assertEqual(exc.exception.detail['code'],'PLAN_NO_HABILITA_REPORTES')

    def test_cross_tenant_assignment_is_rejected_by_api_and_database(self):
        response=self.client.post('/api/rbac/usuarios/3/sucursales',json={'ids_sucursales':[2]})
        self.assertEqual(response.status_code,403,response.text)
        self.assertEqual(asignaciones_services.consultar(3,self.admin),[1])
        with self.assertRaises(psycopg2.errors.CheckViolation):
            self.sql('INSERT INTO t_usuario_sucursal(id_usuario,id_sucursal) VALUES(3,2)')
        self.assertEqual(self.client.get('/api/rbac/usuarios/4/sucursales').status_code,403)

    def test_assignment_revocation_is_audited_and_effective_immediately(self):
        response=self.client.post('/api/rbac/usuarios/3/sucursales',json={'ids_sucursales':[]})
        self.assertEqual(response.status_code,200,response.text)
        self.assertEqual(_contexto_vigente({'id_usuario':3})['sucursales'],[])
        self.assertEqual(self.sql("SELECT COUNT(*) FROM t_bitacora WHERE accion='EMPLEADO_SUCURSALES_ASIGNADAS'",fetch=True)[0][0],1)

    def test_company_admin_cannot_administer_platform_subscriptions(self):
        now=datetime.now(timezone.utc)
        response=self.client.post('/api/empresas/1/suscripciones',json={'codigo_plan':'BASICO','inicio':now.isoformat(),'fin':(now+timedelta(days=30)).isoformat(),'motivo':'Test plan'})
        self.assertEqual(response.status_code,403)

    def test_user_create_rolls_back_invalid_assignment_and_uses_password_hash(self):
        data={'nombre_completo':'Nuevo Empleado','nombre_usuario':'new_employee','password':'Secure!1234','correo':'new@example.test','id_rol':105,'ids_sucursales':[2]}
        response=self.client.post('/api/usuarios',json=data)
        self.assertEqual(response.status_code,403,response.text)
        self.assertEqual(self.sql("SELECT COUNT(*) FROM t_usuario WHERE username='new_employee'",fetch=True)[0][0],0)
        data['ids_sucursales']=[1]
        response=self.client.post('/api/usuarios',json=data)
        self.assertEqual(response.status_code,200,response.text)
        uid=response.json()['id_usuario']
        self.assertEqual(asignaciones_services.consultar(uid,self.admin),[1])
        from werkzeug.security import check_password_hash
        stored=self.sql('SELECT password_hash,id_rol FROM t_usuario WHERE id_usuario=%s',(uid,),True)[0]
        self.assertTrue(check_password_hash(stored[0],data['password']))
        self.assertEqual(stored[1],105)

    def test_migration_reverses_without_data_loss_and_blocks_if_history_exists(self):
        self.sql(render(ROOT/'backend/migrations/001_iter1_saas.down.sql',self.schema))
        self.assertEqual(self.sql('SELECT COUNT(*) FROM t_sucursal',fetch=True)[0][0],2)
        self.sql(render(ROOT/'backend/migrations/001_iter1_saas.up.sql',self.schema))
        self.subscribe()
        with self.assertRaises(psycopg2.errors.RaiseException):
            self.sql(render(ROOT/'backend/migrations/001_iter1_saas.down.sql',self.schema))
        self.assertEqual(len(saas_services.historial(1)),1)

    def test_database_audit_failure_rolls_back_subscription(self):
        with patch('app.services.saas_services.auditar', side_effect=RuntimeError('Audit unavailable')):
            with self.assertRaises(RuntimeError):
                self.subscribe()
        self.assertEqual(saas_services.historial(1),[])

    def test_permission_revocation_is_effective_with_existing_jwt(self):
        self.assertTrue(tiene_permiso(self.employee,'reportes.ver'))
        self.sql("DELETE FROM t_rol_permiso WHERE id_rol=105 AND id_permiso=(SELECT id_permiso FROM t_permiso WHERE codigo='reportes.ver')")
        fresh=_contexto_vigente({'id_usuario':3,'permisos':['reportes.ver']})
        self.assertFalse(tiene_permiso(fresh,'reportes.ver'))

    def test_empty_branch_scope_never_means_all_branches(self):
        self.sql('DELETE FROM t_usuario_sucursal WHERE id_usuario=3')
        self.actor=_contexto_vigente({'id_usuario':3})
        response=self.client.get('/api/rbac/sucursales')
        self.assertEqual(response.status_code,200,response.text)
        self.assertEqual(response.json()['sucursales'],[])
        from app.reports.engine.query_builder import construir_consulta_reporte
        query,params,_=construir_consulta_reporte({'vista':'vw_test','columnas':[{'campo':'id_sucursal'}]}, {}, 1, [])
        self.assertIn('FALSE',query)
        self.assertIn(1,params)

    def test_caja_and_kpi_contexts_reject_foreign_company_and_branch(self):
        from app.routes.caja_routes import _contexto_supervision
        from app.services.kpis_services import _resolver_contexto_tenant
        for resolver in [lambda: _contexto_supervision(self.admin,2,None),
                         lambda: _resolver_contexto_tenant(self.admin,2,1),
                         lambda: _contexto_supervision(self.employee,1,2)]:
            with self.assertRaises(HTTPException):
                resolver()

    def test_migration_cli_is_explicit_idempotent_and_checks_checksum(self):
        self.sql(render(ROOT/'backend/migrations/001_iter1_saas.down.sql',self.schema))
        env=dict(os.environ,DB_HOST='127.0.0.1',DB_PORT=str(self.pg.params['port']),DB_USER='iter1_test',DB_PASSWORD='',DB_NAME='postgres',DB_SCHEMA=self.schema)
        def cli(direction):
            return subprocess.run([sys.executable,'-B',str(ROOT/'backend/migrate.py'),direction,'--apply'],env=env,capture_output=True,text=True)
        for direction in ['up','up','down','down']:
            response=cli(direction)
            self.assertEqual(response.returncode,0,response.stderr)
        self.assertEqual(self.sql('SELECT COUNT(*) FROM t_sucursal',fetch=True)[0][0],2)
        self.assertEqual(cli('up').returncode,0)
        self.sql("UPDATE schema_migrations SET checksum='changed'")
        self.assertNotEqual(cli('up').returncode,0)

    def test_platform_api_subscription_confirmation_and_history(self):
        self.actor=self.platform
        now=datetime.now(timezone.utc)
        data={'codigo_plan':'BASICO','inicio':now.isoformat(),'fin':(now+timedelta(days=30)).isoformat(),'motivo':'Asignacion administrativa'}
        response=self.client.post('/api/empresas/1/suscripciones',json=data)
        self.assertEqual(response.status_code,201,response.text)
        sid=response.json()['data']['id_suscripcion']
        self.assertEqual(self.client.post(f'/api/empresas/1/suscripciones/{sid}/cancelar',json={'motivo':'Cancelacion'}).status_code,422)
        response=self.client.post(f'/api/empresas/1/suscripciones/{sid}/cancelar',json={'motivo':'Cancelacion administrativa','confirmar':True})
        self.assertEqual(response.status_code,200,response.text)
        self.assertEqual(saas_services.consultar_plan(1)['estado'],'CANCELADA')
        self.assertEqual(len(saas_services.historial(1)),1)

    def test_company_suspension_preserves_plan_history(self):
        self.subscribe()
        from app.repos.tenant_repos import eliminar_empresa_db
        self.assertTrue(eliminar_empresa_db(1))
        self.assertEqual(saas_services.consultar_plan(1)['estado'],'EMPRESA_INACTIVA')
        self.assertEqual(len(saas_services.historial(1)),1)
        self.assertEqual(self.client.get('/api/mi-empresa/plan').status_code,200)

    def test_application_factory_does_not_connect_or_migrate_on_startup(self):
        import importlib.util
        spec=importlib.util.spec_from_file_location('iter1_factory',ROOT/'backend/app/__init__.py')
        factory=importlib.util.module_from_spec(spec)
        with patch('psycopg2.connect',side_effect=AssertionError('Startup must not access the database')), \
             patch.object(PostgreSQL,'create_connection',side_effect=AssertionError('Startup must not access the database')):
            spec.loader.exec_module(factory)
            app=factory.create_app()
            paths=app.openapi()['paths']
        for path in ['/api/planes','/api/mi-empresa/plan','/api/pedidos','/api/reservas','/api/pos/ventas','/api/backup/manual']:
            self.assertIn(path,paths)

    def test_omitting_assignment_list_does_not_revoke_roles(self):
        response=self.client.post('/api/rbac/usuarios/3/roles',json={})
        self.assertEqual(response.status_code,422,response.text)
        self.assertEqual(_contexto_vigente({'id_usuario':3})['roles'],['CAJERO'])
        self.assertEqual(self.client.post('/api/rbac/usuarios/3/permisos',json={}).status_code,422)

    def test_tenant_admin_cannot_mutate_shared_role_definitions(self):
        response=self.client.post('/api/rbac/roles/105/permisos',json={'ids_permisos':[]})
        self.assertEqual(response.status_code,403,response.text)
        self.assertTrue(tiene_permiso(_contexto_vigente({'id_usuario':3}),'reportes.ver'))

    def test_new_checkout_requires_vigency_and_keeps_p1_success_shape(self):
        from app.routes import pedido_routes
        self.app.include_router(pedido_routes.router)
        body={'id_sucursal':1,'nombre_contacto':'Cliente Prueba','telefono_contacto':'123456789','id_empresa':1}
        with patch('app.repos.pedido_repos.validar_y_crear_pedido', return_value={'id_pedido':123}) as repo:
            response=self.client.post('/api/pedidos',json=body)
            self.assertEqual(response.status_code,403,response.text)
            repo.assert_not_called()
            self.subscribe()
            response=self.client.post('/api/pedidos',json=body)
            self.assertEqual(response.status_code,201,response.text)
            self.assertTrue(response.json()['success'])
            self.assertEqual(response.json()['data']['id_pedido'],123)

    def test_future_basic_plan_also_limits_new_activations(self):
        current=self.subscribe('PROFESIONAL')
        self.subscribe('BASICO',inicio=current['fin'],fin=current['fin']+timedelta(days=30))
        self.sql("INSERT INTO t_sucursal(id_empresa,nombre) VALUES(1,'A2')")
        with self.assertRaises(psycopg2.errors.CheckViolation) as exc:
            self.sql("INSERT INTO t_sucursal(id_empresa,nombre) VALUES(1,'A3')")
        self.assertEqual(exc.exception.diag.message_primary,'LIMITE_PLAN_PROGRAMADO')

    def test_concurrent_subscriptions_cannot_overlap(self):
        def create(_):
            try:
                self.subscribe()
                return True
            except HTTPException as exc:
                self.assertEqual(exc.status_code,409)
                return False
        with concurrent.futures.ThreadPoolExecutor(max_workers=2) as pool:
            self.assertEqual(sum(pool.map(create,[1,2])),1)
        self.assertEqual(len(saas_services.historial(1)),1)


if __name__ == '__main__':
    unittest.main()
