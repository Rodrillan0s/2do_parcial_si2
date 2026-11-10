"""
Pruebas Automatizadas — Flujo de Pago Offline Delegado con PayPal
Verifica el ciclo de vida completo:
1. Dispositivo A (offline) genera una intención de pago (intent_id) para PayPal
2. Dispositivo B (con conexión) inicia la orden delegada en PayPal (/api/pagos/paypal/delegado/iniciar)
3. Dispositivo B autoriza y captura la orden en PayPal (/api/pagos/paypal/delegado/capturar)
4. Dispositivo A (al reconectarse) consulta el estado (/api/pagos/paypal/delegado/estado/{intent_id})
5. Sincronización en lote con kind == "PAYPAL_DELEGADO_CONFIRMACION"
6. Sincronización en lote de VENTA_CONTADO con PayPal delegado ya capturado
7. Manejo de errores: intentos no capturados, no encontrados o no autorizados
"""
import json
import unittest
from datetime import datetime, timezone
from unittest.mock import MagicMock, patch
from fastapi import HTTPException

from app.modules.ecommerce.routes.pago_routes import (
    IniciarPagoDelegadoDTO,
    CapturarPagoDelegadoDTO,
    iniciar_pago_delegado_endpoint,
    capturar_pago_delegado_endpoint,
    consultar_estado_pago_delegado,
)
from app.modules.ecommerce.routes.sync_routes import (
    SyncOperationItemDTO,
    _procesar_operacion_individual,
)


class TestPagoOfflinePayPalDelegado(unittest.TestCase):

    def test_01_validaciones_dto_iniciar_y_capturar(self):
        """Valida que los DTOs de inicio y captura verifiquen tipos y restricciones."""
        dto_iniciar = IniciarPagoDelegadoDTO(
            intent_id="INTENT-UUID-12345",
            id_empresa=1,
            id_sucursal=2,
            monto_total=250.50,
            items=[{"id_variante": 10, "cantidad": 2, "precio": 125.25}],
            cliente_nombre="Juan Perez",
            nit_ci="1234567"
        )
        self.assertEqual(dto_iniciar.intent_id, "INTENT-UUID-12345")
        self.assertEqual(dto_iniciar.monto_total, 250.50)
        self.assertEqual(len(dto_iniciar.items), 1)

        dto_capturar = CapturarPagoDelegadoDTO(
            intent_id="INTENT-UUID-12345",
            order_id="PAYPAL-ORDER-777",
            nit_ci="1234567",
            razon_social="Juan Perez"
        )
        self.assertEqual(dto_capturar.order_id, "PAYPAL-ORDER-777")

    @patch("app.modules.ecommerce.routes.pago_routes.PostgreSQL")
    @patch("app.modules.ecommerce.routes.pago_routes.paypal_service.crear_orden_paypal")
    def test_02_dispositivo_b_inicia_orden_delegada(self, mock_crear_paypal, mock_pg_class):
        """
        Dispositivo B con conexión invoca iniciar_pago_delegado_endpoint con el payload escaneado.
        El backend crea la orden en PayPal y registra la intención en t_sync_operacion en estado 'pending'.
        """
        mock_db = MagicMock()
        mock_pg_class.return_value = mock_db
        # Primera consulta: no existe intención previa
        mock_db.execute_query.side_effect = [
            None,  # SELECT t_sync_operacion
            None   # INSERT INTO t_sync_operacion
        ]

        mock_crear_paypal.return_value = {
            "success": True,
            "order_id": "ORD-PAYPAL-999",
            "approve_url": "https://www.sandbox.paypal.com/checkoutnow?token=ORD-PAYPAL-999",
            "monto_bob": 300.0,
            "monto_usd": 43.10
        }

        body = IniciarPagoDelegadoDTO(
            intent_id="UUID-OFFLINE-001",
            id_empresa=1,
            id_sucursal=1,
            monto_total=300.0,
            items=[{"id_variante": 1, "cantidad": 1, "precio": 300.0}],
            cliente_nombre="Cliente Remoto"
        )

        res = iniciar_pago_delegado_endpoint(body, token_data={"id_usuario": 5})
        self.assertTrue(res["success"])
        self.assertEqual(res["data"]["order_id"], "ORD-PAYPAL-999")
        self.assertEqual(res["data"]["approve_url"], "https://www.sandbox.paypal.com/checkoutnow?token=ORD-PAYPAL-999")
        self.assertEqual(res["data"]["monto_total"], 300.0)

        # Verificar que se insertó en t_sync_operacion
        mock_db.execute_query.assert_called()

    @patch("app.modules.ecommerce.routes.pago_routes.PostgreSQL")
    def test_03_iniciar_pago_delegado_idempotencia(self, mock_pg_class):
        """
        Si Dispositivo B vuelve a iniciar la misma orden con el mismo intent_id ya existente,
        retorna los datos ya generados sin duplicar llamadas.
        """
        mock_db = MagicMock()
        mock_pg_class.return_value = mock_db
        mock_db.execute_query.return_value = (
            "UUID-OFFLINE-001",
            "pending",
            {
                "order_id": "ORD-PAYPAL-EXISTING",
                "approve_url": "https://paypal.com/existing",
                "monto_total": 300.0,
                "monto_usd": 43.10
            }
        )

        body = IniciarPagoDelegadoDTO(
            intent_id="UUID-OFFLINE-001",
            id_empresa=1,
            monto_total=300.0
        )
        res = iniciar_pago_delegado_endpoint(body, token_data=None)
        self.assertTrue(res["success"])
        self.assertEqual(res["data"]["order_id"], "ORD-PAYPAL-EXISTING")

    @patch("app.modules.ecommerce.routes.pago_routes.PostgreSQL")
    def test_04_consultar_estado_pendiente(self, mock_pg_class):
        """
        Si Dispositivo A consulta el estado antes de que Dispositivo B complete el pago,
        retorna estado 'PENDIENTE' y capturado=False.
        """
        mock_db = MagicMock()
        mock_pg_class.return_value = mock_db
        mock_db.execute_query.return_value = (
            "UUID-OFFLINE-001",
            "pending",
            202,
            None,
            {"order_id": "ORD-PAYPAL-999", "estado": "ESPERANDO_APROBACION"}
        )

        res = consultar_estado_pago_delegado("UUID-OFFLINE-001")
        self.assertTrue(res["success"])
        self.assertEqual(res["status"], "PENDIENTE")
        self.assertFalse(res["capturado"])

    @patch("app.modules.ecommerce.routes.pago_routes.PostgreSQL")
    @patch("app.modules.ecommerce.routes.pago_routes.paypal_service.capturar_orden_paypal")
    def test_05_dispositivo_b_captura_pago_exitosamente(self, mock_capturar_paypal, mock_pg_class):
        """
        Dispositivo B captura la orden en PayPal.
        El backend actualiza t_sync_operacion a status 'synced' y guarda el capture_id.
        """
        mock_db = MagicMock()
        mock_pg_class.return_value = mock_db
        mock_db.execute_query.side_effect = [
            # 1. SELECT t_sync_operacion: intención pendiente
            ("UUID-OFFLINE-001", 5, 1, "pending", {"monto_total": 300.0, "order_id": "ORD-PAYPAL-999"}),
            # 2. UPDATE t_sync_operacion: pasa a synced
            None
        ]

        mock_capturar_paypal.return_value = {
            "success": True,
            "status": "COMPLETED",
            "capture_id": "CAP-PAYPAL-55555",
            "order_id": "ORD-PAYPAL-999"
        }

        body = CapturarPagoDelegadoDTO(
            intent_id="UUID-OFFLINE-001",
            order_id="ORD-PAYPAL-999",
            nit_ci="9876543",
            razon_social="Tienda SA"
        )
        bg_tasks = MagicMock()
        res = capturar_pago_delegado_endpoint(body, background_tasks=bg_tasks, token_data=None)

        self.assertTrue(res["success"])
        self.assertEqual(res["data"]["status"], "COMPLETED")
        self.assertEqual(res["data"]["capture_id"], "CAP-PAYPAL-55555")
        self.assertEqual(res["data"]["metodo_pago"], "PayPal")

    @patch("app.modules.ecommerce.routes.pago_routes.PostgreSQL")
    def test_06_dispositivo_a_reconecta_y_captura_estado_completado(self, mock_pg_class):
        """
        Al recuperar internet, Dispositivo A consulta el estado y recibe COMPLETADO con capturado=True.
        """
        mock_db = MagicMock()
        mock_pg_class.return_value = mock_db
        mock_db.execute_query.return_value = (
            "UUID-OFFLINE-001",
            "synced",
            200,
            None,
            {
                "success": True,
                "status": "COMPLETED",
                "capture_id": "CAP-PAYPAL-55555",
                "monto_total": 300.0,
                "metodo_pago": "PayPal"
            }
        )

        res = consultar_estado_pago_delegado("UUID-OFFLINE-001")
        self.assertTrue(res["success"])
        self.assertEqual(res["status"], "COMPLETADO")
        self.assertTrue(res["capturado"])
        self.assertEqual(res["data"]["capture_id"], "CAP-PAYPAL-55555")

    @patch("app.modules.ecommerce.routes.sync_routes.resolver_empresa_compra", return_value=1)
    def test_07_sync_lote_kind_paypal_delegado_confirmacion_exitoso(self, mock_emp):
        """
        Dispositivo A envía en su lote de sincronización una operación 'PAYPAL_DELEGADO_CONFIRMACION'.
        Como ya fue capturado en backend, el lote confirma la operación con status 'synced'.
        """
        from app.core.postgres import PostgreSQL
        db = PostgreSQL()
        db.create_connection()
        schema = "comercio"
        intent_id = "UUID-OFFLINE-TEST-07"
        op_id = "OP-SYNC-CONFIRM-07"
        try:
            # Insertar intención previa como 'synced'
            db.execute_query(f"""
                INSERT INTO {schema}.t_sync_operacion (
                    operation_id, id_usuario, id_empresa, kind, status, http_status, response_json, created_at, updated_at
                ) VALUES (%s, %s, %s, %s, %s, %s, %s::jsonb, NOW(), NOW())
                ON CONFLICT (id_usuario, id_empresa, operation_id) DO UPDATE SET
                    status = EXCLUDED.status,
                    response_json = EXCLUDED.response_json;
            """, (
                intent_id,
                3,
                1,
                "PAYPAL_OFFLINE_DELEGADO",
                "synced",
                200,
                json.dumps({"status": "COMPLETED", "capture_id": "CAP-PAYPAL-55555", "monto_total": 300.0})
            ), commit=True)

            op = SyncOperationItemDTO(
                operation_id=op_id,
                entity_id=intent_id,
                kind="PAYPAL_DELEGADO_CONFIRMACION",
                payload={"intent_id": intent_id},
                created_at=datetime.now(timezone.utc).isoformat()
            )
            token_data = {"id_usuario": 3, "id_empresa": 1, "roles": ["ADMIN_EMPRESA"]}

            res = _procesar_operacion_individual(op, token_data)
            self.assertEqual(res["status"], "synced")
            self.assertEqual(res["http_status"], 200)
            self.assertEqual(res["data"]["capture_id"], "CAP-PAYPAL-55555")
        finally:
            db.execute_query(f"DELETE FROM {schema}.t_sync_operacion WHERE operation_id IN (%s, %s);", (intent_id, op_id), commit=True)
            db.close_connection()

    @patch("app.modules.ecommerce.routes.sync_routes.resolver_empresa_compra", return_value=1)
    def test_08_sync_lote_kind_paypal_delegado_confirmacion_pendiente_requiere_reconciliacion(self, mock_emp):
        """
        Si Dispositivo A intenta sincronizar la confirmación de PayPal delegado antes de que
        el cliente pague en Dispositivo B, retorna status 'reconciliation_required' y PAYMENT_NOT_YET_CAPTURED.
        """
        from app.core.postgres import PostgreSQL
        db = PostgreSQL()
        db.create_connection()
        schema = "comercio"
        intent_id = "UUID-OFFLINE-TEST-08"
        op_id = "OP-SYNC-CONFIRM-08"
        try:
            # Insertar intención previa como 'pending'
            db.execute_query(f"""
                INSERT INTO {schema}.t_sync_operacion (
                    operation_id, id_usuario, id_empresa, kind, status, http_status, response_json, created_at, updated_at
                ) VALUES (%s, %s, %s, %s, %s, %s, %s::jsonb, NOW(), NOW())
                ON CONFLICT (id_usuario, id_empresa, operation_id) DO UPDATE SET
                    status = EXCLUDED.status,
                    response_json = EXCLUDED.response_json;
            """, (
                intent_id,
                3,
                1,
                "PAYPAL_OFFLINE_DELEGADO",
                "pending",
                202,
                json.dumps({"order_id": "ORD-PAYPAL-999", "estado": "ESPERANDO_APROBACION"})
            ), commit=True)

            op = SyncOperationItemDTO(
                operation_id=op_id,
                entity_id=intent_id,
                kind="PAYPAL_DELEGADO_CONFIRMACION",
                payload={"intent_id": intent_id},
                created_at=datetime.now(timezone.utc).isoformat()
            )
            token_data = {"id_usuario": 3, "id_empresa": 1, "roles": ["ADMIN_EMPRESA"]}

            res = _procesar_operacion_individual(op, token_data)
            self.assertEqual(res["status"], "reconciliation_required")
            self.assertEqual(res["http_status"], 409)
            self.assertEqual(res["conflict_code"], "PAYMENT_NOT_YET_CAPTURED")
        finally:
            db.execute_query(f"DELETE FROM {schema}.t_sync_operacion WHERE operation_id IN (%s, %s);", (intent_id, op_id), commit=True)
            db.close_connection()

    @patch("app.core.tenant_guard.obtener_sucursales_autorizadas", return_value={1})
    @patch("app.modules.ecommerce.routes.sync_routes.resolver_empresa_compra", return_value=1)
    def test_09_venta_offline_con_paypal_delegado_no_capturado_requiere_reconciliacion(self, mock_emp, mock_suc):
        """
        Una VENTA_CONTADO offline con método PAYPAL cuyo intent_id aún no ha sido capturado
        por el segundo dispositivo debe responder reconciliation_required con PAYMENT_NOT_YET_CAPTURED.
        """
        op = SyncOperationItemDTO(
            operation_id="OP-VENTA-PAYPAL-OFF-01",
            entity_id="1",
            kind="VENTA_CONTADO",
            payload={
                "id_sucursal": 1,
                "id_empresa": 1,
                "metodo_pago": "PAYPAL",
                "intent_id": "UUID-NON-EXISTENT-INTENT",
                "items": [{"id_variante": 100, "cantidad": 1, "precio_unitario": 50.0}],
                "monto_recibido": 50.0
            },
            created_at=datetime.now(timezone.utc).isoformat()
        )
        token_data = {"id_usuario": 3, "id_empresa": 1, "id_sucursal": 1, "roles": ["ADMIN_EMPRESA"], "permisos": ["pos.vender", "pos.cobrar"]}

        res = _procesar_operacion_individual(op, token_data)
        self.assertEqual(res["status"], "reconciliation_required")
        self.assertEqual(res["conflict_code"], "PAYMENT_NOT_YET_CAPTURED")

    @patch("app.core.tenant_guard.obtener_sucursales_autorizadas", return_value={1})
    @patch("app.modules.ecommerce.routes.sync_routes.resolver_empresa_compra", return_value=1)
    def test_10_venta_offline_con_paypal_sin_intent_id_es_rechazada(self, mock_emp, mock_suc):
        """
        Una VENTA_CONTADO offline con método PAYPAL que no especifica intent_id de delegación
        debe ser rechazada inmediatamente con PAYMENT_REQUIRES_ONLINE.
        """
        op = SyncOperationItemDTO(
            operation_id="OP-VENTA-PAYPAL-OFF-02",
            entity_id="1",
            kind="VENTA_CONTADO",
            payload={
                "id_sucursal": 1,
                "id_empresa": 1,
                "metodo_pago": "PAYPAL",
                "items": [{"id_variante": 100, "cantidad": 1, "precio_unitario": 50.0}],
                "monto_recibido": 50.0
            },
            created_at=datetime.now(timezone.utc).isoformat()
        )
        token_data = {"id_usuario": 3, "id_empresa": 1, "id_sucursal": 1, "roles": ["ADMIN_EMPRESA"], "permisos": ["pos.vender", "pos.cobrar"]}

        res = _procesar_operacion_individual(op, token_data)
        self.assertEqual(res["status"], "reconciliation_required")
        self.assertEqual(res["conflict_code"], "PAYMENT_REQUIRES_ONLINE")


if __name__ == "__main__":
    unittest.main()
