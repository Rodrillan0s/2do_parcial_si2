from fastapi import APIRouter, Depends
import io
import importlib
import traceback
import unittest
import app.core.db_init
from app.core.postgres import PostgreSQL
from app.core.security import require_platform_admin

router = APIRouter(tags=["Principal"])

@router.get("/")
def index():
    return {
        "sistema": "Plataforma E-Commerce Multi-Tenant",
        "estado": "En línea",
        "version": "2.0.0"
    }

@router.get("/check-tables")
def check_tables(_: dict = Depends(require_platform_admin)):
    db = PostgreSQL()
    try:
        db.create_connection()
        t_rol = db.execute_query("""
            SELECT column_name, data_type 
            FROM information_schema.columns 
            WHERE table_schema = 'comercio' AND table_name = 't_rol';
        """, fetchall=True)
        return {"t_rol": t_rol}
    except Exception as e:
        return {"error": str(e)}
    finally:
        db.close_connection()




@router.get("/init-db")
def init_db(_: dict = Depends(require_platform_admin)):
    try:
        importlib.reload(app.utils.db_init)
        app.utils.db_init.inicializar_tablas_seguridad()
        return {"success": True, "message": "Tablas del esquema comercio inicializadas correctamente."}
    except Exception as e:
        return {"success": False, "error": str(e), "traceback": traceback.format_exc()}


@router.get("/run-tests")
def run_tests(test: int = 0, _: dict = Depends(require_platform_admin)):
    init_err = None
    try:
        importlib.reload(app.utils.db_init)
        app.utils.db_init.inicializar_tablas_seguridad()
    except Exception as e:
        init_err = traceback.format_exc()

    import test_auth_flow
    importlib.reload(test_auth_flow)

    suite = unittest.TestSuite()
    if test == 1:
        suite.addTest(test_auth_flow.TestAuthFlow('test_01_registro_validaciones'))
    elif test == 2:
        suite.addTest(test_auth_flow.TestAuthFlow('test_02_bloqueo_tres_intentos'))
    elif test == 3:
        suite.addTest(test_auth_flow.TestAuthFlow('test_03_verificacion_dispositivo_exotico'))
    elif test == 4:
        suite.addTest(test_auth_flow.TestAuthFlow('test_04_recuperacion_contrasena'))
    else:
        suite = unittest.TestLoader().loadTestsFromTestCase(test_auth_flow.TestAuthFlow)

    stream = io.StringIO()
    runner = unittest.TextTestRunner(stream=stream, verbosity=2)
    result = runner.run(suite)
    output = stream.getvalue()
    return {
        "test_num": test,
        "init_error": init_err,
        "was_successful": result.wasSuccessful(),
        "tests_run": result.testsRun,
        "errors": len(result.errors),
        "failures": len(result.failures),
        "output": output
    }