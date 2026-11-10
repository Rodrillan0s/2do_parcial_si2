"""A disposable local PostgreSQL cluster. Never reads project .env for connection."""
import os
from pathlib import Path
import shutil
import socket
import subprocess
import tempfile
import time
import unittest
import psycopg2


class LocalPostgres:
    def __init__(self, durable=False):
        self.durable = durable

    def __enter__(self):
        configured = os.getenv('ITER1_PG_BIN')
        candidates = [Path(configured)] if configured else sorted(Path('C:/Program Files/PostgreSQL').glob('*/bin'), reverse=True)
        executable = '.exe' if os.name == 'nt' else ''
        self.bin = next((p for p in candidates if (p / ('initdb' + executable)).is_file()), None)
        if self.bin is None:
            initdb = shutil.which('initdb')
            self.bin = Path(initdb).parent if initdb else None
        if self.bin is None:
            raise unittest.SkipTest('PostgreSQL local no disponible; instalar o definir ITER1_PG_BIN.')
        self.temp = tempfile.TemporaryDirectory(prefix='aurora_iter1_test_')
        root = Path(self.temp.name)
        self.data = root / 'data'
        self.flags = subprocess.CREATE_NO_WINDOW if os.name == 'nt' else 0
        self.log = (root / 'server.log').open('wb')
        self.proc = None
        try:
            subprocess.run([str(self.bin / 'initdb'), '-D', str(self.data), '-U', 'iter1_test', '-A', 'trust', '--no-locale', '-E', 'UTF8'],
                           check=True, stdout=self.log, stderr=self.log, creationflags=self.flags)
            with socket.socket() as sock:
                sock.bind(('127.0.0.1', 0))
                port = sock.getsockname()[1]
            self.params = dict(host='127.0.0.1', port=port, user='iter1_test', dbname='postgres', connect_timeout=1)
            self.proc = subprocess.Popen([str(self.bin / 'postgres'), '-D', str(self.data), '-h', '127.0.0.1', '-p', str(port)] + ([] if self.durable else ['-F']),
                                         stdout=self.log, stderr=self.log, creationflags=self.flags)
            for _ in range(100):
                try:
                    conn = psycopg2.connect(**self.params)
                    conn.close()
                    return self
                except psycopg2.OperationalError:
                    if self.proc.poll() is not None:
                        break
                    time.sleep(.1)
            raise RuntimeError('No se pudo arrancar PostgreSQL de pruebas.')
        except BaseException:
            self.__exit__(None, None, None)
            raise

    def crash_restart(self):
        assert self.durable and self.params['host'] == '127.0.0.1'
        subprocess.run([str(self.bin / 'pg_ctl'), '-D', str(self.data), '-m', 'immediate', '-w', 'stop'],
                       check=True, stdout=self.log, stderr=self.log, creationflags=self.flags)
        self.proc.wait(timeout=15)
        self.proc = subprocess.Popen([str(self.bin / 'postgres'), '-D', str(self.data), '-h', '127.0.0.1',
                                      '-p', str(self.params['port'])],
                                     stdout=self.log, stderr=self.log, creationflags=self.flags)
        for _ in range(100):
            try:
                conn = psycopg2.connect(**self.params)
                conn.close()
                return
            except psycopg2.OperationalError:
                if self.proc.poll() is not None:
                    break
                time.sleep(.1)
        raise RuntimeError('No se pudo reiniciar PostgreSQL aislado: ' +
                           (self.data.parent / 'server.log').read_text(errors='replace')[-4000:])

    def __exit__(self, *args):
        if self.proc is not None and self.proc.poll() is None:
            subprocess.run([str(self.bin / 'pg_ctl'), '-D', str(self.data), '-m', 'immediate', '-w', 'stop'],
                           stdout=self.log, stderr=self.log, creationflags=self.flags)
            self.proc.wait(timeout=15)
        self.log.close()
        self.temp.cleanup()
