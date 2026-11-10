"""
Pruebas Unitarias de Límites SaaS para Administrador de Tienda (AuroraStore).
Valida:
1. Cálculo de campos enriquecidos (dias_restantes, proximo_a_vencer, modo_solo_lectura).
2. Bloqueo de operaciones de escritura ante suscripción no vigente (Modo Solo Lectura).
3. Bloqueo de cupo de sucursales ante límite de plan alcanzado (LIMITE_SUCURSALES).
4. Restricción del motor de reportes generativo en Plan Básico (PLAN_NO_HABILITA_REPORTES).
"""
import unittest
from unittest.mock import patch
from fastapi import HTTPException
from app.modules.saas.services.saas_services import (
    consultar_plan,
    exigir_vigencia,
    validar_capacidad_sucursales
)


class TestSaasLimitesStoreAdmin(unittest.TestCase):

    def test_01_consultar_plan_campos_enriquecidos(self):
        """Verifica que consultar_plan calcule dias_restantes, modo_solo_lectura y limites."""
        plan_empresa_1 = consultar_plan(1)
        self.assertTrue(plan_empresa_1['vigente'])
        self.assertFalse(plan_empresa_1['modo_solo_lectura'])
        self.assertIsNotNone(plan_empresa_1['dias_restantes'])
        self.assertGreater(plan_empresa_1['dias_restantes'], 0)
        self.assertIn('proximo_a_vencer', plan_empresa_1)
        self.assertEqual(plan_empresa_1['codigo_plan'], 'PROFESIONAL')
        self.assertTrue(plan_empresa_1['capacidades']['reportes_generativos'])

    def test_02_limite_sucursales_plan_basico_alcanzado(self):
        """Tenant 2 tiene Plan BASICO y 2/2 sucursales; validar_capacidad_sucursales debe rechazar con 409."""
        plan_empresa_2 = consultar_plan(2)
        self.assertEqual(plan_empresa_2['codigo_plan'], 'BASICO')
        self.assertEqual(plan_empresa_2['disponibles'], 0)

        with self.assertRaises(HTTPException) as ctx:
            validar_capacidad_sucursales(2)
        self.assertEqual(ctx.exception.status_code, 409)
        self.assertEqual(ctx.exception.detail['code'], 'LIMITE_SUCURSALES')
        self.assertIn('Plan BASICO', ctx.exception.detail['message'])

    def test_03_reportes_generativos_restringidos_en_basico(self):
        """En Plan BASICO, exigir_vigencia(reportes=True) debe lanzar 403 PLAN_NO_HABILITA_REPORTES."""
        with self.assertRaises(HTTPException) as ctx:
            exigir_vigencia(2, reportes=True)
        self.assertEqual(ctx.exception.status_code, 403)
        self.assertEqual(ctx.exception.detail['code'], 'PLAN_NO_HABILITA_REPORTES')

    def test_04_reportes_generativos_permitidos_en_profesional(self):
        """En Plan PROFESIONAL, exigir_vigencia(reportes=True) debe pasar con éxito."""
        res = exigir_vigencia(1, reportes=True)
        self.assertTrue(res['vigente'])
        self.assertTrue(res['capacidades']['reportes_generativos'])

    def test_05_bloqueo_modo_solo_lectura_cuando_no_vigente(self):
        """Simular una empresa vencida o sin suscripción activa: exigir_vigencia debe lanzar 403 con Modo Solo Lectura."""
        mock_plan_vencido = {
            'id_empresa': 99,
            'estado': 'VENCIDA',
            'vigente': False,
            'modo_solo_lectura': True,
            'dias_restantes': -2,
            'proximo_a_vencer': False,
            'codigo_plan': 'BASICO',
            'capacidades': {'reportes_generativos': False},
            'disponibles': 0,
            'limites': {'sucursales_activas': 2}
        }
        with patch('app.modules.saas.services.saas_services.consultar_plan', return_value=mock_plan_vencido):
            with self.assertRaises(HTTPException) as ctx:
                exigir_vigencia(99, operacion="abrir turnos de caja POS")
            self.assertEqual(ctx.exception.status_code, 403)
            self.assertEqual(ctx.exception.detail['code'], 'SUSCRIPCION_NO_VIGENTE')
            self.assertIn('Modo Solo Lectura', ctx.exception.detail['message'])
            self.assertIn('abrir turnos de caja POS', ctx.exception.detail['message'])

    def test_06_alerta_preventiva_proximo_a_vencer(self):
        """Si la suscripción vence en <= 5 días, proximo_a_vencer debe ser True."""
        from datetime import datetime, timedelta, timezone
        now_utc = datetime.now(timezone.utc)
        fin_cercano = now_utc + timedelta(days=3)

        # Mockear execute_query para que devuelva una suscripción que vence en 3 días
        with patch('app.core.postgres.PostgreSQL.execute_query') as mock_query:
            def side_effect_query(query, params=None, fetchone=False, fetchall=False):
                if 't_suscripcion' in query and 't_plan' in query:
                    return (999, 'PROFESIONAL', now_utc - timedelta(days=27), fin_cercano, 10, True)
                if 't_sucursal' in query:
                    return (2,)
                if 'empresa' in query:
                    return ('ACTIVO',)
                if 't_solicitud_contratacion' in query:
                    return None
                return None

            mock_query.side_effect = side_effect_query
            plan = consultar_plan(1)
            self.assertTrue(plan['vigente'])
            self.assertTrue(plan['proximo_a_vencer'])
            self.assertIn(plan['dias_restantes'], [2, 3])


if __name__ == '__main__':
    unittest.main()
