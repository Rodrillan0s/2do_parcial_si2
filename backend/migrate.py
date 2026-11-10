"""Explicit versioned migrations. Default prints SQL; never imports app/startup."""
import argparse
import hashlib
import os
from pathlib import Path
import re

import psycopg2
from psycopg2 import sql
from dotenv import load_dotenv


def render(path, schema):
    if not re.fullmatch(r'[A-Za-z_][A-Za-z0-9_]*', schema):
        raise ValueError('DB_SCHEMA inválido')
    return path.read_text(encoding='utf-8').replace('__SCHEMA__', '"' + schema + '"')


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('direction', choices=['up', 'down'])
    parser.add_argument('--apply', action='store_true', help='Aplicar explícitamente a la base configurada')
    parser.add_argument('--version', default='001_iter1_saas', help='Nombre base de la migración (por defecto: 001_iter1_saas)')
    args = parser.parse_args()
    if not re.fullmatch(r'[A-Za-z0-9_]+', args.version):
        raise ValueError('Versión de migración inválida')
    root = Path(__file__).resolve().parent
    load_dotenv(root / 'app' / '.env', override=False)
    load_dotenv(root / '.env', override=False)
    schema = os.getenv('DB_SCHEMA', 'comercio')
    source = root / 'migrations' / f'{args.version}.{args.direction}.sql'
    query = render(source, schema)
    if not args.apply:
        print(query)
        return
    checksum = hashlib.sha256((root / 'migrations' / f'{args.version}.up.sql').read_bytes()).hexdigest()
    with psycopg2.connect(host=os.getenv('DB_HOST'), port=os.getenv('DB_PORT', '5432'),
                          dbname=os.getenv('DB_NAME'), user=os.getenv('DB_USER'),
                          password=os.getenv('DB_PASSWORD'), connect_timeout=10) as conn:
        with conn.cursor() as cur:
            cur.execute('SELECT pg_advisory_xact_lock(%s)', (134001,))
            cur.execute(sql.SQL('CREATE TABLE IF NOT EXISTS {}.schema_migrations (version TEXT PRIMARY KEY, checksum TEXT NOT NULL, applied_at TIMESTAMPTZ NOT NULL DEFAULT now())').format(sql.Identifier(schema)))
            table = sql.SQL('{}.schema_migrations').format(sql.Identifier(schema))
            cur.execute(sql.SQL('SELECT checksum FROM {} WHERE version=%s').format(table), (args.version,))
            existing = cur.fetchone()
            if existing and existing[0] != checksum:
                raise RuntimeError('La migración aplicada tiene un checksum diferente.')
            if (args.direction == 'up') == bool(existing):
                print('Sin cambios: versión ya aplicada/no aplicada.')
                return
            cur.execute(query)
            if args.direction == 'up':
                cur.execute(sql.SQL('INSERT INTO {}(version,checksum) VALUES (%s,%s)').format(table), (args.version, checksum))
            else:
                cur.execute(sql.SQL('DELETE FROM {} WHERE version=%s').format(table), (args.version,))
    print('Migración completada en una transacción.')


if __name__ == '__main__':
    main()
