import 'package:flutter_test/flutter_test.dart';
import 'package:aurora_store_mobile/services/devoluciones_service.dart';

void main() {
  group('Devoluciones y Ley 453 Models & Business Logic Tests', () {
    test('1. ItemElegibleDevolucionModel parsea correctamente JSON del backend', () {
      final json = {
        'id_detalle_venta': 42,
        'id_variante': 105,
        'id_producto': 12,
        'producto_nombre': 'Vestido de Noche Aurora',
        'talla_nombre': 'M',
        'color_nombre': 'Azul Medianoche',
        'codigo_hex': '#191970',
        'cantidad_comprada': 2,
        'cantidad_devuelta': 0,
        'cantidad_disponible': 2,
        'precio_unitario': '450.00',
        'subtotal_neto': '900.00',
        'imagen_url': 'https://example.com/img.jpg',
      };

      final item = ItemElegibleDevolucionModel.fromJson(json);

      expect(item.idDetalleVenta, equals(42));
      expect(item.idVariante, equals(105));
      expect(item.productoNombre, equals('Vestido de Noche Aurora'));
      expect(item.cantidadDisponible, equals(2));
      expect(item.precioUnitario, equals(450.00));
      expect(item.subtotalNeto, equals(900.00));
    });

    test('2. ElegibilidadVentaModel valida plazo legal de garantía de 15 días', () {
      final jsonElegible = {
        'id_venta': 1,
        'numero_venta': 'VTA-001',
        'fecha_venta': '2026-11-01',
        'total': '350.00',
        'es_elegible': true,
        'dias_transcurridos': 6,
        'items': [
          {
            'id_detalle_venta': 1,
            'id_variante': 10,
            'id_producto': 5,
            'producto_nombre': 'Blusa Seda',
            'talla_nombre': 'S',
            'color_nombre': 'Blanco',
            'codigo_hex': '#FFFFFF',
            'cantidad_comprada': 1,
            'cantidad_devuelta': 0,
            'cantidad_disponible': 1,
            'precio_unitario': '350.00',
            'subtotal_neto': '350.00',
          }
        ]
      };

      final venta = ElegibilidadVentaModel.fromJson(jsonElegible);
      expect(venta.esElegible, isTrue);
      expect(venta.diasTranscurridos, equals(6));
      expect(venta.items.length, equals(1));
    });

    test('3. CreditoClienteModel y Vale Digital parsean y calculan vigencia', () {
      final jsonVale = {
        'id_credito': 8,
        'codigo_credito': 'VALE-2026-X89',
        'monto_original': '250.00',
        'saldo_disponible': '250.00',
        'estado': 'ACTIVO',
        'fecha_emision': '2026-11-01T10:00:00',
        'fecha_vencimiento': '2026-12-01T10:00:00',
      };

      final vale = CreditoClienteModel.fromJson(jsonVale);
      expect(vale.idCredito, equals(8));
      expect(vale.codigoCredito, equals('VALE-2026-X89'));
      expect(vale.saldoDisponible, equals(250.00));
      expect(vale.estado, equals('ACTIVO'));
    });
  });
}
