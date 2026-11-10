"""Read-only critical-integrity diagnostics. Never imports app or executes repairs."""
import csv
import hashlib
import json
import os
from pathlib import Path

import psycopg2
from psycopg2 import sql
from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parents[1]
OUTPUT = ROOT / 'docs/evidencias/correcciones_criticas_2026-11-01'


def main():
    load_dotenv(ROOT / 'backend/app/core/.env', override=True)
    load_dotenv(ROOT / 'backend/app/.env', override=True)
    load_dotenv(ROOT / 'backend/.env', override=True)
    schema = os.getenv('DB_SCHEMA', 'comercio')
    previous = json.loads((ROOT / 'docs/evidencias/NORMALIZACION_DIAGNOSTICO_2026-11-01.json').read_text(encoding='utf-8'))
    OUTPUT.mkdir(parents=True, exist_ok=True)
    report = {'schema': schema, 'mode': 'READ ONLY REPEATABLE READ', 'repairs_executed': False}
    conn = psycopg2.connect(host=os.getenv('DB_HOST'), port=os.getenv('DB_PORT', '5432'),
                            dbname=os.getenv('DB_NAME'), user=os.getenv('DB_USER'), password=os.getenv('DB_PASSWORD'),
                            connect_timeout=10, application_name='aurora_critical_readonly')
    try:
        conn.set_session(readonly=True, isolation_level='REPEATABLE READ')
        with conn.cursor() as cur:
            cur.execute("SET LOCAL statement_timeout='20s'")
            cur.execute(sql.SQL('SET LOCAL search_path TO {},pg_catalog').format(sql.Identifier(schema)))
            cur.execute('SHOW transaction_read_only')
            assert cur.fetchone()[0] == 'on'
            cur.execute('SELECT now()::text')
            report['snapshot_time'] = cur.fetchone()[0]
            report['checks'] = {}
            report['sql'] = previous['check_sql']
            for name, query in report['sql'].items():
                cur.execute(query)
                report['checks'][name] = {'previous': previous['aggregate_checks'][name], 'current': cur.fetchone()[0]}
            cur.execute('SELECT version,checksum FROM schema_migrations ORDER BY version')
            report['applied_migrations'] = cur.fetchall()
            cur.execute("SELECT table_name,column_name,is_nullable,data_type FROM information_schema.columns WHERE table_schema=%s ORDER BY table_name,ordinal_position", (schema,))
            report['columns'] = cur.fetchall()
            cur.execute("SELECT c.conrelid::regclass::text,c.conname,pg_get_constraintdef(c.oid),c.convalidated FROM pg_constraint c WHERE c.connamespace=%s::regnamespace ORDER BY 1,2", (schema,))
            report['constraints'] = cur.fetchall()
            cur.execute('SELECT tablename,indexname,indexdef FROM pg_indexes WHERE schemaname=%s ORDER BY 1,2', (schema,))
            report['indexes'] = cur.fetchall()
            cur.execute("SELECT p.proname,pg_get_functiondef(p.oid) FROM pg_proc p JOIN pg_namespace n ON n.oid=p.pronamespace WHERE n.nspname=%s AND (p.prosrc ILIKE '%%stock_actual%%' OR p.prosrc ILIKE '%%stock_reservado%%')", (schema,))
            functions = cur.fetchall()
            report['stock_functions'] = [{'name': n, 'sha256': hashlib.sha256(body.encode()).hexdigest()} for n, body in functions]
            (OUTPUT / 'stock_functions.sql').write_text('\n\n'.join(body + ';' for _, body in functions), encoding='utf-8')
            cur.execute("SELECT c.relname,t.tgname,pg_get_triggerdef(t.oid) FROM pg_trigger t JOIN pg_class c ON c.oid=t.tgrelid WHERE c.relnamespace=%s::regnamespace AND NOT t.tgisinternal ORDER BY 1,2", (schema,))
            report['triggers'] = cur.fetchall()

            cur.execute('''SELECT i.id_inventario,i.id_sucursal,i.id_variante,s.id_empresa,
                i.stock_actual,i.stock_reservado,i.stock_disponible,i.fecha_actualizacion,
                count(m.id_movimiento) AS movimientos_registrados,max(m.id_movimiento) AS ultimo_id_movimiento
                FROM t_inventario i JOIN t_sucursal s USING(id_sucursal)
                LEFT JOIN t_movimiento_inventario m USING(id_inventario)
                WHERE i.stock_disponible IS DISTINCT FROM i.stock_actual-i.stock_reservado
                GROUP BY i.id_inventario,s.id_empresa ORDER BY i.id_sucursal,i.id_inventario''')
            inventory = cur.fetchall()
            with (OUTPUT / 'inventario_discrepancias.csv').open('w', encoding='utf-8', newline='') as file:
                writer = csv.writer(file)
                writer.writerow([d[0] for d in cur.description])
                writer.writerows(inventory)
            report['inventory_by_branch_and_evidence'] = {}
            for row in inventory:
                key = f'empresa:{row[3]}|sucursal:{row[1]}|' + ('con_movimientos' if row[8] else 'sin_movimientos')
                report['inventory_by_branch_and_evidence'][key] = report['inventory_by_branch_and_evidence'].get(key, 0) + 1

            cur.execute('''SELECT v.id_variante,v.id_producto,p.id_empresa,v.id_talla,t.id_empresa,v.id_color,c.id_empresa,
                ARRAY(SELECT tx.id_talla FROM t_talla tx WHERE tx.id_empresa=p.id_empresa AND lower(trim(tx.nombre))=lower(trim(t.nombre)) ORDER BY 1),
                ARRAY(SELECT cx.id_color FROM t_color cx WHERE cx.id_empresa=p.id_empresa AND lower(trim(cx.nombre))=lower(trim(c.nombre)) AND upper(trim(cx.codigo_hex))=upper(trim(c.codigo_hex)) ORDER BY 1)
                FROM t_producto_talla_color v JOIN t_producto p USING(id_producto)
                JOIN t_talla t USING(id_talla) JOIN t_color c USING(id_color)
                WHERE (t.id_empresa IS NOT NULL AND p.id_empresa<>t.id_empresa)
                   OR (c.id_empresa IS NOT NULL AND p.id_empresa<>c.id_empresa) ORDER BY v.id_variante''')
            report['variant_candidates_NOT_APPROVED'] = [dict(zip(
                ('id_variante', 'id_producto', 'tenant_producto', 'talla_origen', 'tenant_talla', 'color_origen', 'tenant_color',
                 'candidatos_talla_por_nombre_NO_AUTORIZADOS', 'candidatos_color_por_nombre_hex_NO_AUTORIZADOS'), row)) for row in cur.fetchall()]
            cur.execute('SELECT id_usuario,array_agg(id_cliente ORDER BY id_cliente) FROM t_cliente WHERE id_usuario IS NOT NULL GROUP BY 1 HAVING count(*)>1 ORDER BY 1')
            clients = cur.fetchall()
            report['duplicate_clients_NOT_MERGED'] = []
            cur.execute("SELECT c.conrelid::regclass::text,a.attname,pk.attname FROM pg_constraint c JOIN pg_attribute a ON a.attrelid=c.conrelid AND a.attnum=c.conkey[1] LEFT JOIN pg_constraint p ON p.conrelid=c.conrelid AND p.contype='p' LEFT JOIN pg_attribute pk ON pk.attrelid=p.conrelid AND pk.attnum=p.conkey[1] WHERE c.contype='f' AND c.confrelid='t_cliente'::regclass")
            references = cur.fetchall()
            for user_id, ids in clients:
                entry = {'id_usuario': user_id, 'perfiles': ids, 'references': {}}
                for qualified, column, pk in references:
                    if not pk:
                        continue
                    table = qualified.rsplit('.', 1)[-1]
                    cur.execute(sql.SQL('SELECT {},array_agg({} ORDER BY {}) FROM {} WHERE {}=ANY(%s) GROUP BY 1').format(
                        sql.Identifier(column), sql.Identifier(pk), sql.Identifier(pk), sql.Identifier(table), sql.Identifier(column)), (ids,))
                    entry['references'][table] = cur.fetchall()
                report['duplicate_clients_NOT_MERGED'].append(entry)

            cur.execute("SELECT id_pedido,codigo_pedido,id_cliente,id_empresa,id_sucursal,id_carrito_origen,fecha_pedido::text,total,estado_pago,id_venta FROM t_pedido WHERE estado_pago='PAGADO' AND id_venta IS NULL ORDER BY id_pedido")
            report['paid_orders_without_sale_NOT_REPAIRED'] = [dict(zip([d[0] for d in cur.description], row)) for row in cur.fetchall()]
            report['paid_order_trace_NOT_A_MATCH'] = []
            for order in report['paid_orders_without_sale_NOT_REPAIRED']:
                # Potential links are evidence to inspect, never an automatic mapping.
                trace = {'id_pedido': order['id_pedido'], 'sql': {}}
                queries = {
                    'details': ('''SELECT id_detalle_pedido,id_variante,cantidad,subtotal FROM t_detalle_pedido WHERE id_pedido=%s ORDER BY 1''', (order['id_pedido'],)),
                    'receipts_explicit_order_id': ('''SELECT operation_id,status,id_usuario,id_empresa,response_json->'data'->>'id_venta'
                        FROM t_sync_operacion WHERE response_json->'data'->>'id_pedido'=%s OR response_json->>'id_pedido'=%s''', (str(order['id_pedido']),str(order['id_pedido']))),
                    'audit_explicit_order_id': ('''SELECT id_bitacora,modulo,accion,entidad,id_entidad,fecha_hora,
                        datos_nuevos->>'id_venta' FROM t_bitacora
                        WHERE (entidad IN ('t_pedido','Pedido','PEDIDO') AND id_entidad=%s)
                           OR datos_nuevos->>'id_pedido'=%s ORDER BY id_bitacora''', (str(order['id_pedido']),str(order['id_pedido']))),
                    'candidate_sales_same_client_tenant_total_NOT_APPROVED': ('''SELECT v.id_venta,v.id_sucursal,v.fecha_venta,v.total,v.estado,
                        array_agg(p.id_pago ORDER BY p.id_pago) FILTER (WHERE p.id_pago IS NOT NULL),
                        COALESCE(sum(p.monto) FILTER (WHERE p.estado='APROBADO'),0)
                        FROM t_venta v LEFT JOIN t_pago p ON p.id_venta=v.id_venta
                        WHERE v.id_cliente=%s AND v.id_empresa=%s AND v.total=%s
                        GROUP BY v.id_venta ORDER BY v.id_venta''', (order['id_cliente'],order['id_empresa'],order['total'])),
                }
                for key,(query,params) in queries.items():
                    trace['sql'][key] = {'query': query, 'params': params}
                    cur.execute(query,params)
                    trace[key] = [dict(zip([d[0] for d in cur.description],row)) for row in cur.fetchall()]
                report['paid_order_trace_NOT_A_MATCH'].append(trace)
            cur.execute('''SELECT p.id_empresa,lower(trim(v.sku)),array_agg(v.id_variante ORDER BY v.id_variante)
                FROM t_producto_talla_color v JOIN t_producto p USING(id_producto)
                WHERE nullif(trim(v.sku),'') IS NOT NULL GROUP BY 1,2 HAVING count(*)>1''')
            report['sku_duplicates_NOT_RENAMED'] = cur.fetchall()
            cur.execute('SELECT count(*) FROM t_devolucion')
            report['return_headers'] = cur.fetchone()[0]
            cur.execute('SELECT count(*) FROM t_detalle_devolucion')
            report['return_details'] = cur.fetchone()[0]
    finally:
        conn.close()
    protected = ['backend/app/modules/ecommerce/routes/sync_routes.py']
    protected += [str(p.relative_to(ROOT)) for p in (ROOT / 'backend/migrations').glob('*.sql')]
    report['protected_source_hashes'] = {p: hashlib.sha256((ROOT / p).read_bytes()).hexdigest() for p in protected}
    (OUTPUT / 'diagnostico.json').write_text(json.dumps(report, indent=2, ensure_ascii=False, default=str), encoding='utf-8')
    print(json.dumps({'mode': report['mode'], 'snapshot_time': report['snapshot_time'],
                      'checks': report['checks'], 'applied_migrations': report['applied_migrations'],
                      'stock_functions': report['stock_functions'], 'inventory_by_branch_and_evidence': report['inventory_by_branch_and_evidence'],
                      'affected_variants': len(report['variant_candidates_NOT_APPROVED']),
                      'duplicate_client_accounts': len(clients), 'paid_orders_without_sale': len(report['paid_orders_without_sale_NOT_REPAIRED']),
                      'return_headers': report['return_headers'], 'return_details': report['return_details']}, indent=2))


if __name__ == '__main__':
    main()
