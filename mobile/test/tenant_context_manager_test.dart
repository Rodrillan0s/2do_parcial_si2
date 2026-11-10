import 'package:flutter/services.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:aurora_store_mobile/core/tenant/tenant_context_manager.dart';
import 'package:aurora_store_mobile/services/catalogo_service.dart';

void main() {
  TestWidgetsFlutterBinding.ensureInitialized();

  // Mock platform channel for FlutterSecureStorage
  const channel = MethodChannel('plugins.it_nomads.com/flutter_secure_storage');
  final Map<String, String> mockStorage = {};

  setUpAll(() {
    TestDefaultBinaryMessengerBinding.instance.defaultBinaryMessenger
        .setMockMethodCallHandler(channel, (MethodCall methodCall) async {
      switch (methodCall.method) {
        case 'write':
          final key = methodCall.arguments['key'] as String;
          final value = methodCall.arguments['value'] as String;
          mockStorage[key] = value;
          return null;
        case 'read':
          final key = methodCall.arguments['key'] as String;
          return mockStorage[key];
        case 'delete':
          final key = methodCall.arguments['key'] as String;
          mockStorage.remove(key);
          return null;
        case 'deleteAll':
          mockStorage.clear();
          return null;
        default:
          return null;
      }
    });
  });

  group('TenantContextManager Unit Tests', () {
    late TenantContextManager manager;

    setUp(() {
      manager = TenantContextManager();
    });

    test('1. Inicialmente no tiene tienda o tiene la instancia singleton lista', () {
      expect(manager, isNotNull);
      // Singleton pattern verification
      final anotherInstance = TenantContextManager();
      expect(identical(manager, anotherInstance), isTrue);
    });

    test('2. Seleccionar tienda actualiza idEmpresaActiva y nombreTiendaActiva', () async {
      final dummyTenant = TenantModel(
        idEmpresa: 1,
        nombreEmpresa: 'Shopping Bolivia',
        razonSocial: 'Shopping Bolivia S.R.L.',
        direccionFiscal: 'Av. San Martín #450',
        ciudad: 'Santa Cruz',
      );

      await manager.seleccionarTienda(dummyTenant);

      expect(manager.tieneTiendaSeleccionada, isTrue);
      expect(manager.idEmpresaActiva, equals(1));
      expect(manager.nombreTiendaActiva, equals('Shopping Bolivia'));
      expect(manager.ciudadTiendaActiva, equals('Santa Cruz'));
    });

    test('3. Cambiar de tienda limpia la sucursal activa previa para evitar contaminación', () async {
      final tenant1 = TenantModel(
        idEmpresa: 1,
        nombreEmpresa: 'Tienda 1',
      );
      final tenant2 = TenantModel(
        idEmpresa: 2,
        nombreEmpresa: 'Tienda 2',
      );

      await manager.seleccionarTienda(tenant1);
      const sucursal1 = SucursalContextModel(
        idSucursal: 101,
        idEmpresa: 1,
        nombre: 'Sucursal Tienda 1',
        direccion: 'Av. Principal #1',
      );
      await manager.seleccionarSucursal(sucursal1);
      expect(manager.sucursalActual?.idSucursal, equals(101));

      // Switch to tenant 2
      await manager.seleccionarTienda(tenant2);
      expect(manager.idEmpresaActiva, equals(2));
      expect(manager.sucursalActual, isNull);
    });

    test('4. Seleccionar sucursal de otra empresa es rechazado por seguridad', () async {
      final tenant1 = TenantModel(
        idEmpresa: 1,
        nombreEmpresa: 'Tienda 1',
      );
      await manager.seleccionarTienda(tenant1);
      await manager.seleccionarSucursal(null);
      expect(manager.sucursalActual, isNull);

      // Intentar forzar sucursal de empresa 2
      const sucursalInvalida = SucursalContextModel(
        idSucursal: 202,
        idEmpresa: 2,
        nombre: 'Sucursal Foránea',
        direccion: 'Calle Falsa 123',
      );
      await manager.seleccionarSucursal(sucursalInvalida);

      // Debe permanecer null
      expect(manager.sucursalActual, isNull);
    });
  });
}
