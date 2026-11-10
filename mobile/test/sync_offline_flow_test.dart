import 'package:flutter_test/flutter_test.dart';
import 'package:aurora_store_mobile/core/sync/sync_coordinator.dart';
import 'package:aurora_store_mobile/core/database/database_helper.dart';
import 'package:aurora_store_mobile/services/carrito_service.dart';
import 'package:sqflite_common_ffi/sqflite_ffi.dart';

void main() {
  TestWidgetsFlutterBinding.ensureInitialized();
  sqfliteFfiInit();
  databaseFactory = databaseFactoryFfi;

  group('Sync & Offline Flow Unit Tests (Mobile)', () {
    late Database db;

    setUp(() async {
      db = await databaseFactory.openDatabase(inMemoryDatabasePath);
      // Run DatabaseHelper schema creation on in-memory db
      final helper = DatabaseHelper();
      DatabaseHelper.setMockDatabase(db);
      // Create tables
      await db.execute('''
        CREATE TABLE local_sync_operations (
          operation_id TEXT PRIMARY KEY,
          id_empresa INTEGER NOT NULL,
          id_usuario INTEGER NOT NULL,
          id_sucursal INTEGER,
          kind TEXT NOT NULL,
          payload_json TEXT NOT NULL,
          status TEXT NOT NULL,
          conflict_code TEXT,
          message TEXT,
          retry_count INTEGER DEFAULT 0,
          created_at TEXT NOT NULL,
          updated_at TEXT NOT NULL
        );
      ''');
      await db.execute('''
        CREATE TABLE local_sync_receipts (
          operation_id TEXT PRIMARY KEY,
          id_empresa INTEGER NOT NULL,
          id_usuario INTEGER NOT NULL,
          response_json TEXT NOT NULL,
          created_at TEXT NOT NULL
        );
      ''');
      await db.execute('''
        CREATE TABLE local_reservations (
          id_reserva_local TEXT PRIMARY KEY,
          codigo_reserva TEXT,
          id_empresa INTEGER NOT NULL,
          id_usuario INTEGER NOT NULL,
          id_sucursal INTEGER,
          sucursal_nombre TEXT,
          fecha_hora_visita TEXT,
          items_json TEXT,
          observaciones TEXT,
          estado TEXT NOT NULL,
          is_offline_draft INTEGER DEFAULT 0,
          created_at TEXT NOT NULL
        );
      ''');
      await db.execute('''
        CREATE TABLE local_cart_drafts (
          id_empresa INTEGER NOT NULL,
          id_usuario INTEGER NOT NULL,
          id_variante INTEGER NOT NULL,
          id_producto INTEGER NOT NULL,
          producto_nombre TEXT NOT NULL,
          talla_nombre TEXT,
          color_nombre TEXT,
          codigo_hex TEXT,
          precio_unitario REAL NOT NULL,
          cantidad INTEGER NOT NULL,
          imagen_url TEXT,
          updated_at TEXT NOT NULL,
          PRIMARY KEY (id_empresa, id_usuario, id_variante)
        );
      ''');
    });

    tearDown(() async {
      await db.close();
      DatabaseHelper.setMockDatabase(null);
    });

    test('1. SyncResultSummary calcula correctamente reconciliaciones y conflictos', () {
      final summary = SyncResultSummary(
        total: 5,
        synced: 2,
        conflicts: 1,
        reconciliations: 1,
        retrying: 1,
        errorMessages: ['Reconciliación requerida en venta POS'],
      );

      expect(summary.total, 5);
      expect(summary.synced, 2);
      expect(summary.conflicts, 1);
      expect(summary.reconciliations, 1);
      expect(summary.retrying, 1);
      expect(summary.errorMessages.length, 1);
    });

    test('2. DatabaseHelper encola operaciones de sincronización con estado pending y UTC', () async {
      final helper = DatabaseHelper();
      await helper.enqueueSyncOperation(
        operationId: 'test-uuid-1234',
        idEmpresa: 1,
        idUsuario: 3,
        idSucursal: 1,
        kind: 'CART_ADD_ITEM',
        payload: {'id_variante': 100, 'cantidad': 2},
      );

      final pending = await helper.getPendingSyncOperations(idEmpresa: 1, idUsuario: 3);
      expect(pending.length, 1);
      expect(pending.first['operation_id'], 'test-uuid-1234');
      expect(pending.first['kind'], 'CART_ADD_ITEM');
      expect(pending.first['status'], 'pending');
    });

    test('3. Marcar resultado como reconciliation_required no se reintenta automáticamente', () async {
      final helper = DatabaseHelper();
      await helper.enqueueSyncOperation(
        operationId: 'vta-pos-rec-1',
        idEmpresa: 1,
        idUsuario: 3,
        idSucursal: 1,
        kind: 'VENTA_CONTADO',
        payload: {'items': []},
      );

      await helper.markSyncOperationResult(
        operationId: 'vta-pos-rec-1',
        status: 'reconciliation_required',
        conflictCode: 'CAJA_CERRADA',
        message: 'Sesión de caja cerrada',
      );

      final pending = await helper.getPendingSyncOperations(idEmpresa: 1, idUsuario: 3);
      // Las operaciones reconciliation_required no deben ser re-enviadas a ciegas
      expect(pending.isEmpty, true);
    });

    test('4. Confirmar borrador de reserva actualiza estado a CONFIRMADA con código oficial', () async {
      final helper = DatabaseHelper();
      await helper.saveReservationDraft(
        draftId: 'res_draft_99',
        idEmpresa: 1,
        idUsuario: 3,
        idSucursal: 1,
        sucursalNombre: 'Central Boutique',
        fechaHoraVisita: '2026-11-15 15:00:00',
        items: [{'id_variante': 100, 'cantidad': 1}],
      );

      var local = await helper.getLocalReservations(1, 3);
      expect(local.length, 1);
      expect(local.first.estado, 'PENDIENTE_SYNC');

      await helper.confirmReservationDraft(
        operationId: 'res_draft_99',
        codigoReserva: 'RES-20261115-ABCDEF',
      );

      local = await helper.getLocalReservations(1, 3);
      expect(local.length, 1);
      expect(local.first.estado, 'CONFIRMADA');
      expect(local.first.codigoReserva, 'RES-20261115-ABCDEF');
    });
  });
}
