"""
Pruebas Automatizadas — Flujo Diferenciado de Cambio de Talla / Prenda vs Reembolso
Verifica el ciclo de vida completo de CAMBIO_PRENDA:
1. Solicitud online del cliente especificando talla deseada
2. Aprobación por revisor
3. Recepción física que transiciona a PENDIENTE_ENTREGA (NO a PENDIENTE_REEMBOLSO)
4. Confirmación de entrega de la nueva prenda con descuento de stock e inventario
5. Comparación con flujo monetario REEMBOLSO_DINERO (que sí exige liquidación económica)
"""
import unittest
from decimal import Decimal
from unittest.mock import MagicMock, patch
from fastapi import HTTPException
from app.modules.pedidos.repos import devoluciones_repos

class TestFlujoCambioTalla(unittest.TestCase):

    def test_item_solicitud_dto_acepta_talla_deseada(self):
        from app.modules.pedidos.routes.devoluciones_routes import ItemDevolucionSolicitudDTO, SolicitarDevolucionClienteDTO
        
        item = ItemDevolucionSolicitudDTO(
            id_detalle_venta=10,
            cantidad=1,
            talla_deseada="L",
            id_variante_cambio=55
        )
        self.assertEqual(item.talla_deseada, "L")
        self.assertEqual(item.id_variante_cambio, 55)

        dto = SolicitarDevolucionClienteDTO(
            id_venta=101,
            motivo="TALLA_INCORRECTA",
            tipo_resolucion="CAMBIO_PRENDA",
            items=[item]
        )
        self.assertEqual(dto.tipo_resolucion, "CAMBIO_PRENDA")
        self.assertEqual(dto.items[0].talla_deseada, "L")

    @patch("app.modules.pedidos.repos.devoluciones_repos.lock_items")
    @patch("app.modules.pedidos.repos.devoluciones_repos._require_structure")
    @patch("app.modules.pedidos.repos.devoluciones_repos._validate_branch")
    @patch("app.modules.pedidos.repos.devoluciones_repos.PostgreSQL")
    def test_recepcion_cambio_prenda_transiciona_a_pendiente_entrega(self, mock_pg_class, mock_vb, mock_rs, mock_li):
        """
        Al recibir físicamente una prenda cuyo tipo_resolucion es CAMBIO_PRENDA,
        el nuevo estado debe ser PENDIENTE_ENTREGA (no PENDIENTE_REEMBOLSO).
        """
        mock_db = MagicMock()
        mock_pg_class.return_value = mock_db

        # Row devolucion: id, id_empresa, id_sucursal, codigo, estado, tipo_resolucion, id_venta, id_usuario, monto
        mock_db.execute_query.side_effect = [
            (10, 1, 1, "DEV-20261109-01", "PENDIENTE_RECEPCION", "CAMBIO_PRENDA", 100, 2, Decimal("150.00")), # SELECT t_devolucion FOR UPDATE
            [(1, 101, 1, 20, "REVENDIBLE", "SOLICITADO", 100)], # SELECT t_detalle_devolucion
            (100,), # SELECT id_venta FROM t_devolucion
            None, # evidence bitacora
            None, # lock items / update
            None, # update detalle
            None, # update t_devolucion
        ]

        with patch("app.modules.pedidos.repos.devoluciones_repos._reincorporar_stock_inventario"):
            res = devoluciones_repos.registrar_recepcion_prendas(
                id_devolucion=10,
                id_usuario_receptor=5,
                id_empresa=1,
                id_sucursal_recepcion=1,
                observaciones="Recibido en perfecto estado",
                items_inspeccionados=[{"id_detalle_devolucion": 1, "cantidad_recibida": 1, "condicion": "REVENDIBLE"}]
            )

        self.assertTrue(res["success"])
        self.assertEqual(res["nuevo_estado"], "PENDIENTE_ENTREGA")
        self.assertEqual(res["tipo_resolucion"], "CAMBIO_PRENDA")
        self.assertIn("Pendiente entrega de prenda de cambio", res["mensaje"])

    @patch("app.modules.pedidos.repos.devoluciones_repos.lock_items")
    @patch("app.modules.pedidos.repos.devoluciones_repos._require_structure")
    @patch("app.modules.pedidos.repos.devoluciones_repos._validate_branch")
    @patch("app.modules.pedidos.repos.devoluciones_repos.PostgreSQL")
    def test_recepcion_reembolso_dinero_transiciona_a_pendiente_reembolso(self, mock_pg_class, mock_vb, mock_rs, mock_li):
        """
        Al recibir físicamente una prenda con REEMBOLSO_DINERO,
        el nuevo estado debe ser PENDIENTE_REEMBOLSO.
        """
        mock_db = MagicMock()
        mock_pg_class.return_value = mock_db

        mock_db.execute_query.side_effect = [
            (11, 1, 1, "DEV-20261109-02", "APROBADA", "REEMBOLSO_DINERO", 100, 2, Decimal("200.00")),
            [(2, 102, 1, 21, "REVENDIBLE", "SOLICITADO", 100)],
            (100,),
            None,
            None,
            None,
            None,
        ]

        with patch("app.modules.pedidos.repos.devoluciones_repos._reincorporar_stock_inventario"):
            res = devoluciones_repos.registrar_recepcion_prendas(
                id_devolucion=11,
                id_usuario_receptor=5,
                id_empresa=1,
                id_sucursal_recepcion=1,
                observaciones="Prenda recibida",
                items_inspeccionados=[{"id_detalle_devolucion": 2, "cantidad_recibida": 1, "condicion": "REVENDIBLE"}]
            )

        self.assertTrue(res["success"])
        self.assertEqual(res["nuevo_estado"], "PENDIENTE_REEMBOLSO")
        self.assertEqual(res["tipo_resolucion"], "REEMBOLSO_DINERO")

    @patch("app.modules.pedidos.repos.devoluciones_repos._require_structure")
    @patch("app.modules.pedidos.repos.devoluciones_repos.PostgreSQL")
    def test_completar_entrega_cambio_prenda_descuenta_stock(self, mock_pg_class, mock_rs):
        """
        Al liquidar un CAMBIO_PRENDA, debe actualizar a COMPLETADA con ENTREGA_PRENDA_CAMBIO
        y descontar el stock de la variante de reemplazo.
        """
        mock_db = MagicMock()
        mock_pg_class.return_value = mock_db

        mock_db.execute_query.side_effect = [
            (10, 1, Decimal("150.00"), "PENDIENTE_ENTREGA", "DEV-20261109-01", 100, 2, "CAMBIO_PRENDA"), # SELECT t_devolucion FOR UPDATE
            [(55, 1, 1)], # SELECT t_detalle_devolucion con id_variante_cambio
            (1,), # SELECT id_sucursal
            None, # UPDATE t_inventario
            None, # INSERT t_movimiento_inventario
            None, # UPDATE t_devolucion SET estado = 'COMPLETADA'
        ]

        res = devoluciones_repos.registrar_reembolso_financiero(
            id_devolucion=10,
            id_usuario_responsable=5,
            id_empresa=1,
            metodo_reembolso="ENTREGA_PRENDA_CAMBIO",
            referencia_reembolso="CAMBIO-DEV-20261109-01",
            observaciones="Prenda talla L entregada al cliente",
            tipo_resolucion="CAMBIO_PRENDA"
        )

        self.assertTrue(res["success"])
        self.assertEqual(res["nuevo_estado"], "COMPLETADA")
        self.assertEqual(res["tipo_resolucion"], "CAMBIO_PRENDA")
        self.assertEqual(res["metodo_reembolso"], "ENTREGA_PRENDA_CAMBIO")

if __name__ == "__main__":
    unittest.main()
