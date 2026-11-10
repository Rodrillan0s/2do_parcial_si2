import io
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "backend"))

from app.modules.pedidos.services.reports.export_utils import exportar_a_csv, exportar_a_xlsx
from app.modules.ia.services import demanda_forecast_services
from app.modules.catalogo.repos import catalogo_repos

class TestKpisReportesIA(unittest.TestCase):

    def test_export_csv_utf8_sig(self):
        """Verifica que el generador CSV produce un buffer válido con BOM UTF-8."""
        headers = ["N° Venta", "Fecha", "Monto"]
        keys = ["nro", "fecha", "monto"]
        filas = [
            {"nro": "VTA-001", "fecha": "2026-11-01", "monto": 150.50},
            {"nro": "VTA-002", "fecha": "2026-11-02", "monto": 220.00}
        ]
        csv_buffer = exportar_a_csv(headers, keys, filas)
        self.assertIsInstance(csv_buffer, io.BytesIO)
        content = csv_buffer.getvalue()
        # Verificar prefijo BOM UTF-8 (\xef\xbb\xbf)
        self.assertTrue(content.startswith(b'\xef\xbb\xbf'))
        # Decodificar y verificar contenido
        text = content.decode('utf-8-sig')
        self.assertIn("N° Venta", text)
        self.assertIn("VTA-001", text)
        self.assertIn("150.50", text)

    def test_export_xlsx_openpyxl(self):
        """Verifica que el generador XLSX produce un libro Excel válido con openpyxl."""
        headers = ["Producto", "Talla", "Precio"]
        keys = ["prod", "talla", "precio"]
        tipos = ["string", "string", "currency"]
        filas = [
            {"prod": "Vestido Gala", "talla": "M", "precio": 350.00},
            {"prod": "Blusa Seda", "talla": "S", "precio": 180.00}
        ]
        resumen = {"total_items": 2, "total_monto": 530.00}
        xlsx_buffer = exportar_a_xlsx("Ventas Test", headers, keys, tipos, filas, resumen)
        self.assertIsInstance(xlsx_buffer, io.BytesIO)
        content = xlsx_buffer.getvalue()
        # Los archivos XLSX comienzan con firma ZIP b'PK\x03\x04'
        self.assertTrue(content.startswith(b'PK\x03\x04'))

    def test_delta_catalogo_structure(self):
        """Verifica que el repositorio de catálogo delta retorne cursor y estructura esperada."""
        delta = catalogo_repos.obtener_delta_catalogo(id_empresa=1, limit=10)
        self.assertIn("cursor", delta)
        self.assertIn("total_modificados", delta)
        self.assertIn("modificados", delta)
        self.assertIn("eliminados_ids", delta)
        self.assertIsInstance(delta["modificados"], list)

    def test_demanda_forecasting_intervalos(self):
        """Verifica que el modelo de demanda calcule predicciones e intervalos al 95%."""
        serie_test = [
            {"fecha": "2026-10-01", "unidades": 5, "ingresos": 500, "transacciones": 3},
            {"fecha": "2026-10-02", "unidades": 7, "ingresos": 700, "transacciones": 4},
            {"fecha": "2026-10-03", "unidades": 6, "ingresos": 600, "transacciones": 4},
            {"fecha": "2026-10-04", "unidades": 8, "ingresos": 800, "transacciones": 5},
            {"fecha": "2026-10-05", "unidades": 10, "ingresos": 1000, "transacciones": 6},
            {"fecha": "2026-10-06", "unidades": 9, "ingresos": 900, "transacciones": 5},
            {"fecha": "2026-10-07", "unidades": 12, "ingresos": 1200, "transacciones": 7},
        ]
        res = demanda_forecast_services.predecir_demanda_serie(serie_test, dias_proyeccion=5)
        self.assertIn("proyecciones", res)
        self.assertIn("tendencia", res)
        self.assertEqual(len(res["proyecciones"]), 5)
        
        # Verificar que límite inferior <= predicción <= límite superior
        for p in res["proyecciones"]:
            self.assertGreaterEqual(p["prediccion"], 0.0)
            self.assertLessEqual(p["limite_inferior"], p["prediccion"])
            self.assertGreaterEqual(p["limite_superior"], p["prediccion"])

    def test_backtesting_metricas(self):
        """Verifica que el backtesting calcule MAE, RMSE y MAPE válidos."""
        serie_larga = [
            {"fecha": f"2026-10-{i:02d}", "unidades": 10 + (i % 5), "ingresos": 100, "transacciones": 2}
            for i in range(1, 25)
        ]
        evaluacion = demanda_forecast_services.evaluar_backtesting_modelo(serie_larga, dias_test=5)
        self.assertIn("mae", evaluacion)
        self.assertIn("rmse", evaluacion)
        self.assertIn("mape", evaluacion)
        self.assertIn("precision_pct", evaluacion)
        self.assertGreaterEqual(evaluacion["mae"], 0.0)
        self.assertGreaterEqual(evaluacion["rmse"], 0.0)
        self.assertGreaterEqual(evaluacion["precision_pct"], 0.0)
        self.assertLessEqual(evaluacion["precision_pct"], 100.0)

    def test_deducir_empresa_desde_sucursal_en_predicciones(self):
        """Verifica que si no se envía id_empresa pero sí id_sucursal, se resuelva el tenant de la sucursal sin error 400."""
        from app.modules.ia.routes.predicciones_routes import _validar_permisos_ia
        token_global = {
            "id_usuario": 1,
            "roles": ["ADMINISTRADOR"],
            "permisos": ["ia.recomendar"],
            "id_empresa": None,
            "alcance": "PLATAFORMA"
        }
        empresa_id, sucursal_id = _validar_permisos_ia(token_global, id_empresa_param=None, id_sucursal_param=3)
        self.assertIsNotNone(empresa_id)
        self.assertGreater(empresa_id, 0)
        self.assertEqual(sucursal_id, 3)

    def test_todos_los_14_reportes_construyen_sql_valido(self):
        """Verifica que los 14 reportes del motor dinámico construyan SQL válido y ejecutable sin error de columnas."""
        from app.modules.pedidos.services.reports.engine.catalog import CATALOGO_REPORTES
        from app.modules.pedidos.services.reports.engine.query_builder import construir_consulta_reporte
        from app.core.postgres import PostgreSQL
        
        self.assertIn("valoraciones", CATALOGO_REPORTES)
        self.assertEqual(len(CATALOGO_REPORTES), 14)

        db = PostgreSQL()
        db.create_connection()
        try:
            for cod, defn in CATALOGO_REPORTES.items():
                req = {"tipo_reporte": cod, "filtros": {}}
                sql, params, meta = construir_consulta_reporte(defn, req, id_empresa=1)
                self.assertIn("FROM", sql)
                self.assertIn("id_empresa = %s", sql)
                # Ejecutar contra PostgreSQL real para validar sintaxis de columnas
                rows = db.execute_query(sql, params, fetchall=True)
                self.assertIsNotNone(rows, f"Fallo ejecutando reporte {cod}")
        finally:
            db.close_connection()

    def test_comando_voz_valoraciones_y_calidad(self):
        """Verifica que los comandos de voz y texto para valoraciones y quejas se interpreten correctamente."""
        from app.modules.pedidos.services.reports.parser.command_parser import parsear_comando_voz
        from app.modules.pedidos.services.reports.engine.catalog import CATALOGO_REPORTES
        from app.modules.pedidos.services.reports.engine.query_builder import construir_consulta_reporte
        from app.core.postgres import PostgreSQL

        comandos_val = [
            ("Reporte de valoraciones de clientes", "valoraciones", None),
            ("Calificaciones de prendas por estrellas", "valoraciones", "puntuacion"),
            ("Opiniones de clientes por sucursal", "valoraciones", "sucursal"),
            ("Quejas de calidad de prendas", "valoraciones", None),
        ]

        db = PostgreSQL()
        db.create_connection()
        try:
            for cmd, expected_rep, expected_group in comandos_val:
                parsed = parsear_comando_voz(cmd, id_empresa=1)
                self.assertTrue(parsed["valido"], f"Comando inválido: {cmd}")
                req = parsed["report_request"]
                self.assertEqual(req["tipo_reporte"], expected_rep)
                if expected_group:
                    self.assertEqual(req.get("groupBy"), expected_group)

                defn = CATALOGO_REPORTES[req["tipo_reporte"]]
                sql, params, meta = construir_consulta_reporte(defn, req, id_empresa=1)
                rows = db.execute_query(sql, params, fetchall=True)
                self.assertIsNotNone(rows)
        finally:
            db.close_connection()

    def test_comando_ventas_pendientes_sin_error_estado(self):
        """Verifica que el comando 'Ventas pendientes de pago' se parsee y ejecute sin error de columna estado."""
        from app.modules.pedidos.services.reports.parser.command_parser import parsear_comando_voz
        from app.modules.pedidos.services.reports.engine.catalog import CATALOGO_REPORTES
        from app.modules.pedidos.services.reports.engine.query_builder import construir_consulta_reporte
        from app.core.postgres import PostgreSQL

        parsed = parsear_comando_voz("Ventas pendientes de pago", id_empresa=1)
        self.assertTrue(parsed["valido"])
        req = parsed["report_request"]
        self.assertEqual(req["tipo_reporte"], "ventas_pendientes")

        defn = CATALOGO_REPORTES["ventas_pendientes"]
        sql, params, meta = construir_consulta_reporte(defn, req, id_empresa=1)
        
        db = PostgreSQL()
        db.create_connection()
        try:
            rows = db.execute_query(sql, params, fetchall=True)
            self.assertIsNotNone(rows)
        finally:
            db.close_connection()

    def test_comandos_voz_agrupaciones_y_ordenamientos(self):
        """Verifica comandos dinámicos con GROUP BY y ORDER BY para múltiples dominios."""
        from app.modules.pedidos.services.reports.parser.command_parser import parsear_comando_voz
        from app.modules.pedidos.services.reports.engine.catalog import CATALOGO_REPORTES
        from app.modules.pedidos.services.reports.engine.query_builder import construir_consulta_reporte
        from app.core.postgres import PostgreSQL

        comandos = [
            ("Ventas por sucursal", "ventas", "sucursal"),
            ("Ventas por metodo de pago", "ventas", "metodo_pago"),
            ("Inventario por categoria", "inventario", "categoria"),
            ("Rentabilidad por sucursal", "rentabilidad", "sucursal")
        ]

        db = PostgreSQL()
        db.create_connection()
        try:
            for cmd, expected_rep, expected_group in comandos:
                parsed = parsear_comando_voz(cmd, id_empresa=1)
                req = parsed["report_request"]
                self.assertEqual(req["tipo_reporte"], expected_rep)
                self.assertEqual(req["groupBy"], expected_group)

                defn = CATALOGO_REPORTES[expected_rep]
                sql, params, meta = construir_consulta_reporte(defn, req, id_empresa=1)
                rows = db.execute_query(sql, params, fetchall=True)
                self.assertIsNotNone(rows)
        finally:
            db.close_connection()

    def test_kpis_satisfaccion_canales_inventario_db(self):
        """Verifica que el resumen de KPIs consolide satisfacción, canales, probador, devoluciones e inventario valuado sin N+1."""
        from app.modules.pedidos.repos import kpis_repos
        res = kpis_repos.obtener_resumen_kpis_db(id_empresa=1)
        self.assertIn("satisfaccion", res)
        self.assertIn("canales", res)
        self.assertIn("reservas_probador", res)
        self.assertIn("devoluciones", res)
        self.assertIn("inventario", res)
        self.assertIn("valoracion_inventario_disponible", res["inventario"])
        self.assertIn("tasa_disponibilidad_stock", res["inventario"])

        ranking = kpis_repos.obtener_ranking_satisfaccion_prendas_db(id_empresa=1, limit=5)
        self.assertIsInstance(ranking, list)

        alertas = kpis_repos.obtener_alertas_calidad_criticas_db(id_empresa=1, limit=10)
        self.assertIsInstance(alertas, list)

    def test_kpis_services_endpoints_autorizacion(self):
        """Verifica que los servicios de KPIs resuelvan el contexto tenant y bloqueen a clientes."""
        from app.modules.pedidos.services import kpis_services
        token_admin = {
            "id_usuario": 1,
            "roles": ["ADMINISTRADOR"],
            "permisos": ["kpis.ver"],
            "id_empresa": 1,
            "alcance": "EMPRESA"
        }
        res_ranking = kpis_services.obtener_ranking_satisfaccion_prendas(token_admin)
        self.assertTrue(res_ranking["success"])

        res_alertas = kpis_services.obtener_alertas_calidad_criticas(token_admin)
        self.assertTrue(res_alertas["success"])

        token_cliente = {
            "id_usuario": 99,
            "roles": ["CLIENTE"],
            "permisos": [],
            "id_empresa": None,
            "alcance": "CLIENTE"
        }
        with self.assertRaises(ValueError):
            kpis_services.obtener_ranking_satisfaccion_prendas(token_cliente)


if __name__ == "__main__":
    unittest.main()
