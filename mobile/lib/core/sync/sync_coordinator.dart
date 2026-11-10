import 'dart:convert';
import 'package:dio/dio.dart';
import 'package:flutter/foundation.dart';
import 'package:uuid/uuid.dart';
import '../../services/api_client.dart';
import '../../services/token_storage.dart';
import '../database/database_helper.dart';

class SyncResultSummary {
  final int total;
  final int synced;
  final int conflicts;
  final int reconciliations;
  final int retrying;
  final List<String> errorMessages;

  SyncResultSummary({
    required this.total,
    required this.synced,
    required this.conflicts,
    this.reconciliations = 0,
    required this.retrying,
    this.errorMessages = const [],
  });
}

class SyncCoordinator extends ChangeNotifier {
  static final SyncCoordinator _instance = SyncCoordinator._internal();
  factory SyncCoordinator() => _instance;
  SyncCoordinator._internal();

  final DatabaseHelper _dbHelper = DatabaseHelper();
  final Dio _dio = ApiClient.dio;
  final Uuid _uuid = const Uuid();

  bool _isSyncing = false;
  DateTime? _lastSyncTime;
  int _pendingCount = 0;

  bool get isSyncing => _isSyncing;
  DateTime? get lastSyncTime => _lastSyncTime;
  int get pendingCount => _pendingCount;

  Future<void> inicializar() async {
    await actualizarContadorPendientes();
  }

  Future<void> actualizarContadorPendientes() async {
    final pending = await _dbHelper.getPendingSyncOperations();
    _pendingCount = pending.length;
    notifyListeners();
  }

  /// Encola una operación offline con un UUID estable (idempotente)
  Future<String> encolarOperacion({
    required int idEmpresa,
    required int idUsuario,
    int? idSucursal,
    required String kind,
    required Map<String, dynamic> payload,
  }) async {
    final opId = _uuid.v4();

    await _dbHelper.enqueueSyncOperation(
      operationId: opId,
      idEmpresa: idEmpresa,
      idUsuario: idUsuario,
      idSucursal: idSucursal,
      kind: kind,
      payload: payload,
    );

    await actualizarContadorPendientes();
    return opId;
  }

  /// Alias de conveniencia con tenantId
  Future<String> enqueueOperation({
    required String kind,
    required int tenantId,
    int? idUsuario,
    int? idSucursal,
    required Map<String, dynamic> payload,
  }) async {
    final uid = idUsuario ?? (await TokenStorage.getUsuario())?['id_usuario'] as int? ?? 1;
    return encolarOperacion(
      idEmpresa: tenantId,
      idUsuario: uid,
      idSucursal: idSucursal,
      kind: kind,
      payload: payload,
    );
  }

  /// Sincroniza todas las operaciones pendientes con POST /api/sync/lote
  Future<SyncResultSummary> sincronizarLote({int? idEmpresa, int? idUsuario}) async {
    if (_isSyncing) {
      return SyncResultSummary(total: 0, synced: 0, conflicts: 0, retrying: 0);
    }

    _isSyncing = true;
    notifyListeners();

    int totalSynced = 0;
    int totalConflicts = 0;
    int totalReconciliations = 0;
    int totalRetrying = 0;
    final errors = <String>[];

    try {
      final token = await TokenStorage.getToken();
      if (token == null || token.isEmpty) {
        // No sincronizar si no hay sesión activa
        _isSyncing = false;
        notifyListeners();
        return SyncResultSummary(total: 0, synced: 0, conflicts: 0, reconciliations: 0, retrying: 0);
      }

      final pendingOps = await _dbHelper.getPendingSyncOperations(
        idEmpresa: idEmpresa,
        idUsuario: idUsuario,
      );

      if (pendingOps.isEmpty) {
        _isSyncing = false;
        await actualizarContadorPendientes();
        return SyncResultSummary(total: 0, synced: 0, conflicts: 0, reconciliations: 0, retrying: 0);
      }

      // Preparar payload conforme a SyncBatchRequestDTO
      final opItems = pendingOps.map((op) {
        Map<String, dynamic> payloadMap = {};
        try {
          payloadMap = jsonDecode(op['payload_json'] as String) as Map<String, dynamic>;
        } catch (_) {}

        return {
          'operation_id': op['operation_id'],
          'kind': op['kind'],
          'tenant_id': op['id_empresa'],
          'branch_id': op['id_sucursal'],
          'client_version': '1.0.0',
          'created_at': op['created_at'],
          'payload': payloadMap,
        };
      }).toList();

      final response = await _dio.post(
        '/api/sync/lote',
        data: {'operations': opItems},
      );

      if (response.statusCode == 200 && response.data != null) {
        final results = response.data['results'] as List<dynamic>? ?? [];

        for (final res in results) {
          final opId = res['operation_id']?.toString() ?? '';
          final status = res['status']?.toString() ?? 'failed_retryable';
          final kind = res['kind']?.toString() ?? '';
          final conflictCode = res['conflict_code']?.toString();
          final message = res['message']?.toString();
          final data = res['data'] is Map ? Map<String, dynamic>.from(res['data']) : null;

          if (status == 'synced') {
            totalSynced++;
            await _dbHelper.markSyncOperationResult(
              operationId: opId,
              status: 'synced',
              responseData: Map<String, dynamic>.from(res),
            );

            // Confirmar borrador local si fue una reserva
            if (kind == 'RESERVA_SOLICITUD') {
              final codReserva = data?['codigo_reserva']?.toString();
              await _dbHelper.confirmReservationDraft(
                operationId: opId,
                codigoReserva: codReserva,
              );
            }
          } else if (status == 'reconciliation_required') {
            totalReconciliations++;
            if (message != null) errors.add(message);
            await _dbHelper.markSyncOperationResult(
              operationId: opId,
              status: 'reconciliation_required',
              conflictCode: conflictCode,
              message: message,
            );
          } else if (status == 'conflict' || status == 'failed_permanent') {
            totalConflicts++;
            if (message != null) errors.add(message);
            await _dbHelper.markSyncOperationResult(
              operationId: opId,
              status: 'conflict',
              conflictCode: conflictCode,
              message: message,
            );

            // Si falló la reserva, marcar borrador local en conflicto
            if (kind == 'RESERVA_SOLICITUD') {
              await _dbHelper.rejectReservationDraft(
                operationId: opId,
                motivo: message,
              );
            }
          } else {
            totalRetrying++;
            await _dbHelper.markSyncOperationResult(
              operationId: opId,
              status: 'failed_retryable',
              conflictCode: conflictCode,
              message: message,
            );
          }
        }

        _lastSyncTime = DateTime.now().toUtc();
      }
    } catch (e) {
      // Error de red general, las operaciones quedan para el próximo intento
      totalRetrying = _pendingCount;
      errors.add('Error al comunicar lote de sincronización: $e');
    } finally {
      _isSyncing = false;
      await actualizarContadorPendientes();
      notifyListeners();
    }

    return SyncResultSummary(
      total: totalSynced + totalConflicts + totalReconciliations + totalRetrying,
      synced: totalSynced,
      conflicts: totalConflicts,
      reconciliations: totalReconciliations,
      retrying: totalRetrying,
      errorMessages: errors,
    );
  }
}
