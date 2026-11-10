"""
Suite de Pruebas Unitarias y de Integración — Sistema de Valoración de Calidad y Servicio
Verifica:
1. Flujo Normal: Cliente con compra verificada registra valoración exitosa de 5 o 4 estrellas.
2. Flujo A1: Omisión o cierre del modal sin registrar datos basura; permanece disponible en pendientes.
3. Flujo A2: 1 estrella sin justificación rechazada (422); 1 estrella con motivo atendida y marcada para revisión (requiere_revision = True).
4. Seguridad y Anti-fraude: Rechazo de valoraciones para productos no comprados o ventas inexistentes (400).
5. Idempotencia y Prevención de Duplicados: Segunda valoración rechazada (409).
6. Supervisión Administrativa: Listado de valoraciones críticas y registro de resolución de seguimiento.
"""
import os
import sys
import unittest
from unittest.mock import patch, MagicMock
from fastapi import HTTPException

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
sys.path.insert(0, os.path.join(ROOT, "backend"))

from app.modules.valoraciones.schemas.valoracion_schemas import (
    CrearValoracionDTO,
    AtenderValoracionDTO
)
from app.modules.valoraciones.services import valoracion_services
from app.modules.valoraciones.repos import valoracion_repos


class TestSistemaValoraciones(unittest.TestCase):

    def setUp(self):
        self.token_cliente = {
            "nro_usuario": 101,
            "id_usuario": 101,
            "sub": "cliente@aurora.com",
            "rol": "CLIENTE",
            "id_empresa": 1
        }
        self.token_admin = {
            "nro_usuario": 2,
            "id_usuario": 2,
            "sub": "admin@aurora.com",
            "rol": "ADMIN_EMPRESA",
            "id_empresa": 1
        }

    @patch("app.modules.valoraciones.services.valoracion_services.obtener_o_crear_cliente")
    @patch("app.modules.valoraciones.repos.valoracion_repos.validar_elegibilidad_compra")
    @patch("app.modules.valoraciones.repos.valoracion_repos.verificar_valoracion_existente")
    @patch("app.modules.valoraciones.repos.valoracion_repos.registrar_valoracion")
    def test_flujo_normal_valoracion_exitosa(
        self, mock_registrar, mock_existente, mock_validar, mock_cliente
    ):
        """Flujo Normal: Compra verificada -> Calificación de 5 estrellas -> Guardado correcto sin alertas."""
        mock_cliente.return_value = 50
        mock_validar.return_value = {
            "id_empresa": 1,
            "id_sucursal": 2,
            "id_venta": 88,
            "id_pedido": 142
        }
        mock_existente.return_value = False
        mock_registrar.return_value = {
            "id_valoracion": 1,
            "id_empresa": 1,
            "id_sucursal": 2,
            "id_cliente": 50,
            "id_producto": 15,
            "id_pedido": 142,
            "id_venta": 88,
            "puntuacion": 5,
            "comentario": "Excelente calidad de la tela y calce perfecto.",
            "motivo_negativo": None,
            "requiere_revision": False,
            "atendido": False
        }

        dto = CrearValoracionDTO(
            id_producto=15,
            id_pedido=142,
            id_venta=88,
            puntuacion=5,
            comentario="Excelente calidad de la tela y calce perfecto."
        )

        res = valoracion_services.registrar_valoracion_cliente(dto, self.token_cliente)

        self.assertTrue(res["success"])
        self.assertEqual(res["data"]["puntuacion"], 5)
        self.assertFalse(res["data"]["requiere_revision"])
        mock_registrar.assert_called_once()

    @patch("app.modules.valoraciones.services.valoracion_services.obtener_o_crear_cliente")
    @patch("app.modules.valoraciones.repos.valoracion_repos.obtener_compras_pendientes_cliente")
    def test_flujo_a1_cierre_sin_calificar_permanece_pendiente(
        self, mock_pendientes, mock_cliente
    ):
        """Flujo A1: El usuario cierra el modal; no se envía POST y la compra permanece pendiente de calificar."""
        mock_cliente.return_value = 50
        mock_pendientes.return_value = [
            {
                "id_pedido": 142,
                "codigo_pedido": "PED-2026-001",
                "id_producto": 15,
                "nombre_producto": "Vestido de Seda Aurora",
                "estado": "ENTREGADO"
            }
        ]

        res = valoracion_services.obtener_pendientes_cliente(self.token_cliente)

        self.assertTrue(res["success"])
        self.assertEqual(len(res["data"]), 1)
        self.assertEqual(res["data"][0]["id_pedido"], 142)

    @patch("app.modules.valoraciones.services.valoracion_services.obtener_o_crear_cliente")
    def test_flujo_a2_una_estrella_sin_motivo_falla(self, mock_cliente):
        """Flujo A2: 1 estrella sin justificación ni motivo debe ser rechazada con HTTP 422."""
        mock_cliente.return_value = 50

        dto = CrearValoracionDTO(
            id_producto=15,
            id_pedido=142,
            puntuacion=1,
            motivo_negativo=None,
            comentario=None
        )

        with self.assertRaises(HTTPException) as ctx:
            valoracion_services.registrar_valoracion_cliente(dto, self.token_cliente)

        self.assertEqual(ctx.exception.status_code, 422)
        self.assertIn("Para valoraciones de 1 estrella es necesario detallar el motivo", ctx.exception.detail)

    @patch("app.modules.valoraciones.services.valoracion_services.obtener_o_crear_cliente")
    @patch("app.modules.valoraciones.repos.valoracion_repos.validar_elegibilidad_compra")
    @patch("app.modules.valoraciones.repos.valoracion_repos.verificar_valoracion_existente")
    @patch("app.modules.valoraciones.repos.valoracion_repos.registrar_valoracion")
    def test_flujo_a2_una_estrella_con_motivo_activa_alerta(
        self, mock_registrar, mock_existente, mock_validar, mock_cliente
    ):
        """Flujo A2: 1 estrella con motivo detallado se guarda marcando requiere_revision = True."""
        mock_cliente.return_value = 50
        mock_validar.return_value = {
            "id_empresa": 1,
            "id_sucursal": 2,
            "id_venta": 88,
            "id_pedido": 142
        }
        mock_existente.return_value = False
        mock_registrar.return_value = {
            "id_valoracion": 2,
            "id_empresa": 1,
            "id_sucursal": 2,
            "id_cliente": 50,
            "id_producto": 15,
            "puntuacion": 1,
            "comentario": "El cierre vino roto y la costura abierta.",
            "motivo_negativo": "DEFECTO_PRENDA",
            "requiere_revision": True,
            "atendido": False
        }

        dto = CrearValoracionDTO(
            id_producto=15,
            id_pedido=142,
            puntuacion=1,
            motivo_negativo="DEFECTO_PRENDA",
            comentario="El cierre vino roto y la costura abierta."
        )

        res = valoracion_services.registrar_valoracion_cliente(dto, self.token_cliente)

        self.assertTrue(res["success"])
        self.assertEqual(res["data"]["puntuacion"], 1)
        self.assertTrue(res["data"]["requiere_revision"])
        self.assertEqual(res["data"]["motivo_negativo"], "DEFECTO_PRENDA")

    @patch("app.modules.valoraciones.services.valoracion_services.obtener_o_crear_cliente")
    @patch("app.modules.valoraciones.repos.valoracion_repos.validar_elegibilidad_compra")
    def test_rechazo_compra_no_verificada(self, mock_validar, mock_cliente):
        """Seguridad: Intentar valorar un producto no comprado en el pedido es rechazado con HTTP 400."""
        mock_cliente.return_value = 50
        mock_validar.side_effect = ValueError("El producto especificado no forma parte de este pedido.")

        dto = CrearValoracionDTO(
            id_producto=999,
            id_pedido=142,
            puntuacion=4
        )

        with self.assertRaises(HTTPException) as ctx:
            valoracion_services.registrar_valoracion_cliente(dto, self.token_cliente)

        self.assertEqual(ctx.exception.status_code, 400)
        self.assertIn("El producto especificado no forma parte de este pedido", ctx.exception.detail)

    @patch("app.modules.valoraciones.services.valoracion_services.obtener_o_crear_cliente")
    @patch("app.modules.valoraciones.repos.valoracion_repos.validar_elegibilidad_compra")
    @patch("app.modules.valoraciones.repos.valoracion_repos.verificar_valoracion_existente")
    def test_prevencion_duplicados(self, mock_existente, mock_validar, mock_cliente):
        """Idempotencia: Intentar enviar una segunda valoración para el mismo pedido y producto da HTTP 409."""
        mock_cliente.return_value = 50
        mock_validar.return_value = {
            "id_empresa": 1,
            "id_sucursal": 2,
            "id_venta": 88,
            "id_pedido": 142
        }
        mock_existente.return_value = True

        dto = CrearValoracionDTO(
            id_producto=15,
            id_pedido=142,
            puntuacion=5
        )

        with self.assertRaises(HTTPException) as ctx:
            valoracion_services.registrar_valoracion_cliente(dto, self.token_cliente)

        self.assertEqual(ctx.exception.status_code, 409)
        self.assertIn("Ya has registrado una valoración para esta compra", ctx.exception.detail)

    @patch("app.modules.valoraciones.repos.valoracion_repos.resolver_valoracion_admin")
    @patch("app.core.commerce_tenant.resolver_empresa_compra")
    def test_admin_resolver_valoracion_critica(self, mock_resolver_emp, mock_resolver_admin):
        """Admin: El administrador revisa y atiende una valoración de 1 estrella con nota de resolución."""
        mock_resolver_emp.return_value = 1
        mock_resolver_admin.return_value = True

        dto = AtenderValoracionDTO(
            notas_admin="Se contactó al cliente por WhatsApp y se programó el cambio sin costo en Sucursal Centro.",
            atendido=True
        )

        res = valoracion_services.atender_valoracion_admin(
            id_valoracion=2,
            dto=dto,
            token_data=self.token_admin
        )

        self.assertTrue(res["success"])
        self.assertIn("actualizada correctamente", res["message"])
        mock_resolver_admin.assert_called_once_with(
            id_valoracion=2,
            id_empresa=1,
            notas_admin="Se contactó al cliente por WhatsApp y se programó el cambio sin costo en Sucursal Centro.",
            atendido=True
        )


if __name__ == "__main__":
    unittest.main()
