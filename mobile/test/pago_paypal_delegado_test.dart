import 'dart:convert';
import 'package:flutter_test/flutter_test.dart';
import 'package:aurora_store_mobile/services/pago_service.dart';

void main() {
  group('Flujo de Pago Offline Delegado con PayPal (Mobile)', () {
    late PagoService pagoService;

    setUp(() {
      pagoService = PagoService();
    });

    test('1. generarIntentId produce un UUID v4 válido de 36 caracteres', () {
      final intentId = pagoService.generarIntentId();
      expect(intentId, isNotEmpty);
      expect(intentId.length, 36);
      expect(RegExp(r'^[0-9a-f]{8}-[0-9a-f]{4}-4[0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$', caseSensitive: false).hasMatch(intentId), isTrue);
    });

    test('2. generarPayloadQrOffline codifica payload completo en Base64 URL legible', () {
      final intentId = pagoService.generarIntentId();
      final qrPayload = pagoService.generarPayloadQrOffline(
        intentId: intentId,
        idEmpresa: 1,
        idSucursal: 2,
        total: 450.0,
        items: [
          {'id_variante': 100, 'cantidad': 2, 'precio_unitario': 225.0, 'producto_nombre': 'Saco Lino'}
        ],
        idPedido: 42,
        codigoPedido: 'PED-42',
      );

      expect(qrPayload, isNotEmpty);

      // Decodificar Base64 URL y verificar integridad de los campos
      final decodedJson = utf8.decode(base64Url.decode(qrPayload));
      final Map<String, dynamic> data = jsonDecode(decodedJson);

      expect(data['intent_id'], intentId);
      expect(data['id_empresa'], 1);
      expect(data['id_sucursal'], 2);
      expect(data['monto_total'], 450.0);
      expect(data['id_pedido'], 42);
      expect(data['codigo_pedido'], 'PED-42');
      expect((data['items'] as List).length, 1);
      expect(data['items'][0]['producto_nombre'], 'Saco Lino');
      expect(data['timestamp'], isNotNull);
    });

    test('3. ResultadoPagoModel parsea respuesta de captura delegada de PayPal', () {
      final jsonResponse = {
        'id_pedido': 42,
        'codigo_pedido': 'PED-42',
        'id_venta': 105,
        'numero_venta': 'VTA-2026-0105',
        'tipo_documento': 'FACTURA',
        'total': 450.0,
        'metodo_pago': 'PayPal',
        'codigo_transaccion': 'CAP-PAYPAL-987654321',
        'url_descarga_pdf': '/api/comprobantes/venta/105/pdf'
      };

      final model = ResultadoPagoModel.fromJson(jsonResponse);
      expect(model.idPedido, 42);
      expect(model.idVenta, 105);
      expect(model.numeroVenta, 'VTA-2026-0105');
      expect(model.metodoPago, 'PayPal');
      expect(model.codigoTransaccion, 'CAP-PAYPAL-987654321');
      expect(model.total, 450.0);
    });
  });
}
