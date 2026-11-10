import unittest
from unittest.mock import patch, MagicMock
from app.modules.admin.services import backup_services


class TestBackupOracleCloud(unittest.TestCase):

    def test_info_gestor_oracle_cloud(self):
        info = backup_services.obtener_info_gestor_cloud()
        self.assertEqual(info["gestor"], "Oracle Cloud")
        self.assertIn("Oracle Cloud Infrastructure", info["proveedor"])
        self.assertEqual(info["region"], "sa-saopaulo-1")
        self.assertEqual(info["estado_servicio"], "OPERATIVO")

    def test_empresas_registradas_consulta(self):
        empresas = backup_services.obtener_empresas_registradas()
        self.assertIsInstance(empresas, list)
        self.assertGreaterEqual(len(empresas), 1)
        # Verificar campos requeridos para selector
        first = empresas[0]
        self.assertIn("id_empresa", first)
        self.assertIn("nombre_empresa", first)

    def test_generar_dump_simulado_oracle_cloud(self):
        res = backup_services.generar_contenido_dump_oracle_cloud(id_empresa=1, nombre_empresa="SHOPPING BOLIVIA")
        self.assertIn("aurorastore_oraclecloud_empresa_1_", res["file_name"])
        self.assertTrue(res["file_name"].endswith(".dump"))
        
        contenido = res["file_bytes"].decode("utf-8")
        self.assertIn("ORACLE CLOUD INFRASTRUCTURE (OCI) DATABASE ARCHIVE DUMP", contenido)
        self.assertIn("Gestor Cloud: Oracle Cloud", contenido)
        self.assertIn("Región OCI: sa-saopaulo-1", contenido)
        self.assertIn("SHOPPING BOLIVIA", contenido)
        self.assertIn("Checksum SHA-256:", contenido)

        # Verificar que se registró en historial
        historial = backup_services.obtener_historial_backups()
        self.assertEqual(historial[0]["gestor"], "Oracle Cloud")
        self.assertEqual(historial[0]["archivo_dump"], res["file_name"])

    def test_configuracion_automatica_frecuencias(self):
        # Probar frecuencia 'hora'
        c1 = backup_services.guardar_configuracion_automatica({
            "habilitado": True,
            "frecuencia": "hora",
            "intervalo_horas": 3
        })
        self.assertEqual(c1["gestor"], "Oracle Cloud")
        self.assertEqual(c1["frecuencia"], "hora")
        self.assertEqual(c1["intervalo_horas"], 3)

        # Probar frecuencia 'mes'
        c2 = backup_services.guardar_configuracion_automatica({
            "habilitado": True,
            "frecuencia": "mes",
            "dia_mes": 1,
            "hora_ejecucion": "04:00"
        })
        self.assertEqual(c2["frecuencia"], "mes")
        self.assertEqual(c2["dia_mes"], 1)

    def test_simulacion_restauracion_oracle_cloud(self):
        sim = backup_services.simular_restauracion_oracle_cloud("test_backup.dump", id_empresa=1)
        self.assertTrue(sim["success"])
        self.assertEqual(sim["gestor"], "Oracle Cloud")
        self.assertEqual(sim["archivo_dump"], "test_backup.dump")
        self.assertEqual(sim["id_empresa_destino"], 1)


if __name__ == "__main__":
    unittest.main()
