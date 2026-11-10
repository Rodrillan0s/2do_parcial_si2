"""Read-only deployment audit. Never imports the application or executes DDL."""
import hashlib
import json
import os
import sys
from pathlib import Path

import psycopg2
from psycopg2 import sql
from dotenv import load_dotenv


def main():
    root = Path(__file__).resolve().parent
    # Match Config's dotenv precedence without importing app/core/config.py.
    load_dotenv(root / "app/core/.env", override=True)
    load_dotenv(root / "app/.env", override=True)
    load_dotenv(override=True)
    schema = os.getenv("DB_SCHEMA", "comercio")
    with psycopg2.connect(host=os.getenv("DB_HOST"), port=os.getenv("DB_PORT", "5432"),
                          dbname=os.getenv("DB_NAME"), user=os.getenv("DB_USER"),
                          password=os.getenv("DB_PASSWORD"), connect_timeout=10) as conn:
        conn.set_session(readonly=True)
        with conn.cursor() as cur:
            cur.execute("SET LOCAL statement_timeout = '10s'")
            cur.execute("SHOW transaction_read_only")
            report = {"transaction_read_only": cur.fetchone()[0], "schema": schema}
            cur.execute("SELECT name,setting FROM pg_settings WHERE name IN ('fsync','full_page_writes','synchronous_commit','server_version') ORDER BY name")
            report['postgres_settings'] = dict(cur.fetchall())
            cur.execute("SELECT to_regclass(%s), to_regclass(%s), to_regclass(%s)",
                        (schema + '.t_sync_operacion', schema + '.schema_migrations', schema + '.t_sync_control'))
            report["relations"] = cur.fetchone()
            cur.execute("SELECT table_name, column_name, data_type FROM information_schema.columns "
                        "WHERE table_schema=%s AND table_name IN ('t_sync_operacion','schema_migrations','t_sync_control') "
                        "ORDER BY table_name, ordinal_position", (schema,))
            report["columns"] = cur.fetchall()
            cur.execute("SELECT c.conname, pg_get_constraintdef(c.oid) FROM pg_constraint c "
                        "JOIN pg_class t ON t.oid=c.conrelid JOIN pg_namespace n ON n.oid=t.relnamespace "
                        "WHERE n.nspname=%s AND t.relname='t_sync_operacion' ORDER BY c.conname", (schema,))
            report["constraints"] = cur.fetchall()
            cur.execute("SELECT indexdef FROM pg_indexes WHERE schemaname=%s AND tablename='t_sync_operacion'", (schema,))
            report["indexes"] = [r[0] for r in cur.fetchall()]
            cur.execute("SELECT table_name,column_name,data_type,character_maximum_length "
                        "FROM information_schema.columns WHERE table_schema=%s AND table_name='t_pago' "
                        "AND column_name IN ('codigo_transaccion','referencia_externa')", (schema,))
            report["payment_reference_columns"] = cur.fetchall()
            cur.execute("SELECT p.proname, pg_get_functiondef(p.oid) FROM pg_proc p "
                        "JOIN pg_namespace n ON n.oid=p.pronamespace WHERE n.nspname=%s "
                        "AND p.proname IN ('fn_registrar_venta_pos','fn_reservar_stock')", (schema,))
            report["business_functions"] = [{"name": name, "sha256": hashlib.sha256(body.encode()).hexdigest(),
                                             "has_for_update": "FOR UPDATE" in body.upper(),
                                             **({"definition": body} if "--show-functions" in sys.argv else {})}
                                            for name, body in cur.fetchall()]
            columns = {r[1] for r in report["columns"] if r[0] == "t_sync_operacion"}
            ledger = any(r[0] == "schema_migrations" for r in report["columns"])
            report["migrations"] = []
            if ledger:
                cur.execute(sql.SQL("SELECT version, checksum FROM {}.schema_migrations WHERE version IN (%s,%s)")
                            .format(sql.Identifier(schema)), ("003_iter2_sync_idempotency", "004_iter2_sync_transactional"))
                for version, checksum in cur.fetchall():
                    expected = hashlib.sha256((root / "migrations" / f"{version}.up.sql").read_bytes()).hexdigest()
                    report["migrations"].append({"version": version, "checksum_matches": checksum == expected})
            report["required_columns_present"] = {"request_hash", "response_json", "kind", "status"}.issubset(columns)
            report["cutover_control_present"] = any(r[0] == 't_sync_control' and r[1] == 'inicio_garantia' for r in report['columns'])
            if report['cutover_control_present']:
                cur.execute(sql.SQL('SELECT inicio_garantia FROM {}.t_sync_control WHERE id=1').format(sql.Identifier(schema)))
                boundary = cur.fetchone()
                report['cutover_boundary'] = boundary[0].isoformat() if boundary else None
            # No business/customer rows or credentials are printed.
            print(json.dumps(report, indent=2))


if __name__ == "__main__":
    main()
