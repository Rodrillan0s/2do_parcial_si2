from app.core.config import Config
import psycopg2
import psycopg2.extensions
from psycopg2 import pool
import logging
import re
import time
from contextlib import contextmanager
from contextvars import ContextVar
from functools import wraps

_transaction_db = ContextVar('transaction_db', default=None)
_request_db_metrics = ContextVar('aurora_request_db_metrics', default=None)

_MUTATING_OR_LOCKING_SQL_RE = re.compile(
    r"\b(FOR\s+UPDATE|FOR\s+SHARE|FOR\s+NO\s+KEY\s+UPDATE|FOR\s+KEY\s+SHARE|"
    r"INSERT|UPDATE|DELETE|CREATE|ALTER|DROP|TRUNCATE|LOCK|GRANT|REVOKE|"
    r"SET\s+LOCAL|PG_ADVISORY|NEXTVAL|SETVAL|FN_)\b",
    re.IGNORECASE,
)


def _es_consulta_lectura_pura(query: str) -> bool:
    if not query:
        return False
    q_strip = query.lstrip()
    upper_prefix = q_strip[:12].upper()
    if not (
        upper_prefix.startswith("SELECT")
        or upper_prefix.startswith("WITH")
        or upper_prefix.startswith("SHOW")
        or upper_prefix.startswith("EXPLAIN")
    ):
        return False
    return _MUTATING_OR_LOCKING_SQL_RE.search(q_strip) is None


def iniciar_metricas_db_request() -> dict:
    data = {"queries": 0, "db_ms": 0.0, "pool_ms": 0.0}
    _request_db_metrics.set(data)
    return data


def obtener_metricas_db_request() -> dict:
    return _request_db_metrics.get() or {"queries": 0, "db_ms": 0.0, "pool_ms": 0.0}


def _invalidar_caches_seguridad() -> None:
    try:
        from app.core.security import invalidar_cache_contexto
        invalidar_cache_contexto()
    except Exception:
        pass
    try:
        from app.core.tenant_guard import invalidar_cache_tenant
        invalidar_cache_tenant()
    except Exception:
        pass
    try:
        from app.modules.catalogo.repos.categorias_repos import invalidar_cache_categorias
        invalidar_cache_categorias()
    except Exception:
        pass
    try:
        from app.modules.catalogo.repos.tallas_colores_repos import invalidar_cache_tallas_colores
        invalidar_cache_tallas_colores()
    except Exception:
        pass
    try:
        from app.modules.catalogo.routes.catalogo_routes import invalidar_cache_catalogo_publico
        invalidar_cache_catalogo_publico()
    except Exception:
        pass


@contextmanager
def transaction():
    """Share one connection across existing repositories; commit only at the boundary."""
    if _transaction_db.get() is not None:
        yield _transaction_db.get()
        return
    db = PostgreSQL()
    db.create_connection()
    if db.conn is None:
        raise RuntimeError('No se pudo abrir la transacción.')
    try:
        if db.conn.info.transaction_status == psycopg2.extensions.TRANSACTION_STATUS_IDLE and db.conn.autocommit:
            db.conn.autocommit = False
    except Exception:
        pass
    token = _transaction_db.set(db)
    try:
        yield db
        if getattr(db, '_rollback_only', False):
            raise RuntimeError('La transacción fue revertida por un error previo.')
        db.conn.commit()
        _invalidar_caches_seguridad()
    except BaseException:
        db.conn.rollback()
        raise
    finally:
        _transaction_db.reset(token)
        db.close_connection()


def atomic(fn):
    @wraps(fn)
    def wrapped(*args, **kwargs):
        with transaction():
            return fn(*args, **kwargs)
    return wrapped

logger = logging.getLogger(__name__)

class PostgreSQL:
    _pool = None

    @classmethod
    def get_pool(cls):
        if cls._pool is None:
            try:
                cls._pool = pool.ThreadedConnectionPool(
                    minconn=2,
                    maxconn=20,
                    host=Config.DB_HOST,
                    port=Config.DB_PORT,
                    dbname=Config.DB_NAME,
                    user=Config.DB_USER,
                    password=Config.DB_PASSWORD,
                    connect_timeout=10
                )
            except Exception as e:
                logger.error(f"Error inicializando Connection Pool: {e}")
                cls._pool = None
        return cls._pool

    def __init__(self):
        self.db_host = Config.DB_HOST
        self.db_port = Config.DB_PORT
        self.db_name = Config.DB_NAME
        self.db_user = Config.DB_USER
        self.db_password = Config.DB_PASSWORD
        self.conn = None
        self.cur = None
        self._from_pool = False

    def create_connection(self):
        shared = _transaction_db.get()
        if shared is not None:
            self.conn, self.cur = shared.conn, shared.cur
            return
        t0 = time.perf_counter()
        try:
            p = self.get_pool()
            if p is not None:
                self.conn = p.getconn()
                self._from_pool = True

                # Verificar si la conexión del pool está activa sin sobrecosto de red
                if not self.conn or self.conn.closed != 0:
                    try:
                        p.putconn(self.conn, close=True)
                    except Exception:
                        pass
                    self.conn = psycopg2.connect(
                        host=self.db_host,
                        port=self.db_port,
                        dbname=self.db_name,
                        user=self.db_user,
                        password=self.db_password,
                        connect_timeout=10
                    )
                    self._from_pool = False
            else:
                self.conn = psycopg2.connect(
                    host=self.db_host,
                    port=self.db_port,
                    dbname=self.db_name,
                    user=self.db_user,
                    password=self.db_password,
                    connect_timeout=10
                )
                self._from_pool = False

            self.cur = self.conn.cursor()
        except Exception as e:
            # Fallback en caso de error
            try:
                self.conn = psycopg2.connect(
                    host=self.db_host,
                    port=self.db_port,
                    dbname=self.db_name,
                    user=self.db_user,
                    password=self.db_password,
                    connect_timeout=10
                )
                self._from_pool = False
                self.cur = self.conn.cursor()
            except Exception as ex:
                print(f'ERROR DE CONEXION A LA DB: {ex}')
        finally:
            metrics = _request_db_metrics.get()
            if metrics is not None:
                metrics["pool_ms"] += (time.perf_counter() - t0) * 1000.0

    def close_connection(self, commit=False):
        if _transaction_db.get() is not None:
            return
        try:
            if self.cur:
                try:
                    self.cur.close()
                except Exception:
                    pass
                self.cur = None

            if self.conn:
                conn_is_bad = (self.conn.closed != 0)
                if not conn_is_bad:
                    try:
                        tx_status = self.conn.info.transaction_status
                        if tx_status == psycopg2.extensions.TRANSACTION_STATUS_INERROR:
                            self.conn.rollback()
                        elif tx_status != psycopg2.extensions.TRANSACTION_STATUS_IDLE:
                            if commit:
                                self.conn.commit()
                            else:
                                self.conn.rollback()
                        elif commit and not self.conn.autocommit:
                            self.conn.commit()
                    except Exception:
                        conn_is_bad = True

                if self._from_pool and self._pool is not None:
                    try:
                        self._pool.putconn(self.conn, close=conn_is_bad)
                    except Exception:
                        try:
                            self.conn.close()
                        except Exception:
                            pass
                else:
                    try:
                        self.conn.close()
                    except Exception:
                        pass
                self.conn = None
        except Exception as e:
            print(f'ERROR AL CERRAR LA CONEXION CON LA DB: {e}')

    def execute_query(self,query,params=None,fetchall=False,fetchone=False,commit=False):
        if not self.conn or not self.cur:
            print('NO HAY UNA CONEXION ACTIVA A LA BASE DE DATOS')
            return
        
        if fetchall and fetchone:
            print('SOLO PUEDE HACER UNA OPCION "FETCHALL" O "FETCHONE"')
            return

        t0 = time.perf_counter()
        try:
            in_tx_ctx = _transaction_db.get() is not None
            tx_status = self.conn.info.transaction_status
            es_lectura = (not commit) and _es_consulta_lectura_pura(query)
            if in_tx_ctx:
                if tx_status == psycopg2.extensions.TRANSACTION_STATUS_IDLE and self.conn.autocommit:
                    self.conn.autocommit = False
            elif tx_status == psycopg2.extensions.TRANSACTION_STATUS_IDLE:
                if es_lectura:
                    if not self.conn.autocommit:
                        self.conn.autocommit = True
                else:
                    if self.conn.autocommit:
                        self.conn.autocommit = False

            self.cur.execute(query,params)

            if not es_lectura:
                _invalidar_caches_seguridad()

            if commit and not in_tx_ctx and not self.conn.autocommit:
                self.conn.commit()
            
            if fetchone:
                return self.cur.fetchone() if self.cur.description is not None else None
            
            if fetchall:
                return self.cur.fetchall() if self.cur.description is not None else []
            
            return self.cur.rowcount
        except Exception as e:
            # The owner keeps locks until its boundary (or explicit savepoint).
            # An inner rollback would release the idempotency lock too early.
            if self.conn and _transaction_db.get() is None:
                try:
                    if not self.conn.autocommit or self.conn.info.transaction_status != psycopg2.extensions.TRANSACTION_STATUS_IDLE:
                        self.conn.rollback()
                except Exception:
                    pass
            if _transaction_db.get() is not None:
                _transaction_db.get()._rollback_only = True
            from app.core.saas_errors import translate_database_error
            translate_database_error(e)
            print(f'ERROR: {e}, EJECUTANDO ROLLBACK')
            raise
        finally:
            metrics = _request_db_metrics.get()
            if metrics is not None:
                metrics["queries"] += 1
                metrics["db_ms"] += (time.perf_counter() - t0) * 1000.0

    #def insert_log():

    def commit(self):
        if self.conn and _transaction_db.get() is None and not self.conn.autocommit:
            self.conn.commit()

    def rollback(self):
        shared = _transaction_db.get()
        if shared is not None:
            shared._rollback_only = True
        elif self.conn:
            self.conn.rollback()
