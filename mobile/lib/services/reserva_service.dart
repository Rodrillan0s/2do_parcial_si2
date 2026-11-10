import 'package:dio/dio.dart';
import 'package:flutter/foundation.dart';
import 'api_client.dart';
import 'token_storage.dart';
import '../core/database/database_helper.dart';
import '../core/sync/sync_coordinator.dart';

class SucursalReservaModel {
  final int idSucursal;
  final String nombre;
  final String direccion;
  final String? telefono;
  final String ciudad;

  SucursalReservaModel({
    required this.idSucursal,
    required this.nombre,
    required this.direccion,
    this.telefono,
    required this.ciudad,
  });

  factory SucursalReservaModel.fromJson(Map<String, dynamic> json) {
    return SucursalReservaModel(
      idSucursal: json['id_sucursal'] ?? 0,
      nombre: json['nombre'] ?? '',
      direccion: json['direccion'] ?? '',
      telefono: json['telefono']?.toString(),
      ciudad: json['ciudad'] ?? '',
    );
  }
}

class ItemReservaModel {
  final int idDetalleReserva;
  final int idVariante;
  final int cantidad;
  final String productoNombre;
  final double precio;
  final String talla;
  final String color;
  final String codigoHex;
  final String? imagenUrl;

  ItemReservaModel({
    required this.idDetalleReserva,
    required this.idVariante,
    required this.cantidad,
    required this.productoNombre,
    required this.precio,
    required this.talla,
    required this.color,
    required this.codigoHex,
    this.imagenUrl,
  });

  factory ItemReservaModel.fromJson(Map<String, dynamic> json) {
    return ItemReservaModel(
      idDetalleReserva: json['id_detalle_reserva'] ?? 0,
      idVariante: json['id_variante'] ?? 0,
      cantidad: json['cantidad'] ?? 1,
      productoNombre: json['producto_nombre'] ?? '',
      precio: (json['precio'] != null)
          ? double.tryParse(json['precio'].toString()) ?? 0.0
          : 0.0,
      talla: json['talla'] ?? '',
      color: json['color'] ?? '',
      codigoHex: json['codigo_hex'] ?? '#000000',
      imagenUrl: json['imagen_url'],
    );
  }
}

class ReservaModel {
  final int idReserva;
  final String codigoReserva;
  final String fechaReserva;
  final String fechaHoraVisita;
  final String estado; // 'PENDIENTE' | 'CONFIRMADA' | 'CANCELADA' | 'ATENDIDA' | 'VENCIDA'
  final String? observaciones;
  final String? motivoCancelacion;
  final SucursalReservaModel? sucursal;
  final List<ItemReservaModel> items;
  final int totalPrendas;
  final bool conPago;
  final String estadoPago;
  final double montoPagado;

  ReservaModel({
    required this.idReserva,
    required this.codigoReserva,
    required this.fechaReserva,
    required this.fechaHoraVisita,
    required this.estado,
    this.observaciones,
    this.motivoCancelacion,
    this.sucursal,
    this.items = const [],
    required this.totalPrendas,
    this.conPago = false,
    this.estadoPago = 'SIN_PAGO',
    this.montoPagado = 0.0,
  });

  factory ReservaModel.fromJson(Map<String, dynamic> json) {
    final rawItems = json['items'] as List<dynamic>? ?? [];
    return ReservaModel(
      idReserva: json['id_reserva'] ?? 0,
      codigoReserva: json['codigo_reserva'] ?? '',
      fechaReserva: json['fecha_reserva'] ?? '',
      fechaHoraVisita: json['fecha_hora_visita'] ?? '',
      estado: json['estado'] ?? 'PENDIENTE',
      observaciones: json['observaciones'],
      motivoCancelacion: json['motivo_cancelacion'],
      sucursal: json['sucursal'] != null
          ? SucursalReservaModel.fromJson(Map<String, dynamic>.from(json['sucursal']))
          : null,
      items: rawItems
          .map((e) => ItemReservaModel.fromJson(Map<String, dynamic>.from(e)))
          .toList(),
      totalPrendas: json['total_prendas'] ?? rawItems.length,
      conPago: json['con_pago'] == true,
      estadoPago: json['estado_pago'] ?? 'SIN_PAGO',
      montoPagado: (json['monto_pagado'] != null)
          ? double.tryParse(json['monto_pagado'].toString()) ?? 0.0
          : 0.0,
    );
  }
}

class ReservaService extends ChangeNotifier {
  final Dio _dio = ApiClient.dio;
  final DatabaseHelper _dbHelper = DatabaseHelper();
  final SyncCoordinator _syncCoordinator = SyncCoordinator();

  List<ReservaModel> _misReservas = [];
  bool _cargando = false;
  String? _error;

  List<ReservaModel> get misReservas => _misReservas;
  bool get cargando => _cargando;
  String? get error => _error;

  Future<void> cargarMisReservas({int? idEmpresa}) async {
    _cargando = true;
    _error = null;
    notifyListeners();

    final activeEmpresa = idEmpresa ?? (await TokenStorage.getEmpresaId()) ?? 1;
    final userId = (await TokenStorage.getUsuario())?['id_usuario'] as int? ?? 1;

    try {
      final params = <String, dynamic>{};
      if (idEmpresa != null) params['id_empresa'] = idEmpresa;

      final res = await _dio.get('/api/reservas/mis-reservas', queryParameters: params);
      if (res.data['success'] == true && res.data['data'] != null) {
        final rawList = res.data['data'] as List<dynamic>;
        _misReservas = rawList
            .map((e) => ReservaModel.fromJson(Map<String, dynamic>.from(e)))
            .toList();
      } else {
        _misReservas = [];
      }
    } on DioException catch (e) {
      if (e.response?.statusCode == 401) {
        _misReservas = [];
      } else {
        // Fallback a reservas guardadas localmente
        final localDrafts = await _dbHelper.getReservationDrafts(activeEmpresa, userId);
        if (localDrafts.isNotEmpty) {
          _misReservas = localDrafts;
        } else {
          _error = e.response?.data?['detail'] ?? 'Error al cargar reservas.';
        }
      }
    } catch (_) {
      final localDrafts = await _dbHelper.getReservationDrafts(activeEmpresa, userId);
      if (localDrafts.isNotEmpty) {
        _misReservas = localDrafts;
      } else {
        _error = 'Error de conexión con el servicio de reservas.';
      }
    } finally {
      _cargando = false;
      notifyListeners();
    }
  }

  Future<ReservaModel> crearReserva({
    required int idSucursal,
    required String fechaHoraVisita,
    required List<Map<String, dynamic>> items,
    String? observaciones,
    int? idEmpresa,
    bool conPago = false,
    double montoPagado = 0.0,
  }) async {
    final activeEmpresa = idEmpresa ?? (await TokenStorage.getEmpresaId()) ?? 1;
    final userId = (await TokenStorage.getUsuario())?['id_usuario'] as int? ?? 1;

    try {
      final body = <String, dynamic>{
        'id_sucursal': idSucursal,
        'fecha_hora_visita': fechaHoraVisita,
        'items': items,
        if (observaciones != null && observaciones.isNotEmpty) 'observaciones': observaciones.trim(),
        if (idEmpresa != null) 'id_empresa': idEmpresa,
        'con_pago': false, // Política estricta: citas presenciales son 100% gratuitas
        'monto_pagado': 0.0,
      };

      final res = await _dio.post('/api/reservas', data: body);
      if (res.data['success'] == true && res.data['data'] != null) {
        final reserva = ReservaModel.fromJson(res.data['data']);
        cargarMisReservas(idEmpresa: idEmpresa);
        return reserva;
      }
      throw Exception(res.data['message'] ?? 'Error al agendar reserva.');
    } on DioException catch (e) {
      if (e.type == DioExceptionType.connectionError ||
          e.type == DioExceptionType.connectionTimeout) {
        // Modo offline: encolar sincronización diferida y guardar borrador local
        await _dbHelper.saveReservationDraft(
          draftId: 'draft_${DateTime.now().millisecondsSinceEpoch}',
          idEmpresa: activeEmpresa,
          idUsuario: userId,
          idSucursal: idSucursal,
          sucursalNombre: 'Sucursal Seleccionada',
          fechaHoraVisita: fechaHoraVisita,
          items: items,
          observaciones: observaciones,
        );

        await _syncCoordinator.enqueueOperation(
          kind: 'RESERVA_SOLICITUD',
          tenantId: activeEmpresa,
          idSucursal: idSucursal,
          payload: {
            'id_sucursal': idSucursal,
            'fecha_hora_visita': fechaHoraVisita,
            'items': items,
            'observaciones': observaciones,
            'id_empresa': activeEmpresa,
            'con_pago': false,
            'monto_pagado': 0.0,
          },
        );

        cargarMisReservas(idEmpresa: activeEmpresa);

        return ReservaModel(
          idReserva: DateTime.now().millisecondsSinceEpoch,
          codigoReserva: 'OFFLINE-SOLICITUD',
          fechaReserva: DateTime.now().toIso8601String(),
          fechaHoraVisita: fechaHoraVisita,
          estado: 'PENDIENTE_SYNC',
          observaciones: observaciones,
          totalPrendas: items.length,
          conPago: false,
          estadoPago: 'SIN_PAGO',
          montoPagado: 0.0,
        );
      }
      final msg = e.response?.data?['detail'] ?? 'Stock no disponible para reservar en la sucursal seleccionada.';
      throw Exception(msg.toString());
    }
  }

  Future<void> cancelarReserva(int idReserva, {String? motivo, int? idEmpresa}) async {
    try {
      final params = <String, dynamic>{};
      if (idEmpresa != null) params['id_empresa'] = idEmpresa;

      final res = await _dio.post(
        '/api/reservas/$idReserva/cancelar',
        data: {'motivo': motivo ?? 'Cancelación solicitada desde la app móvil.'},
        queryParameters: params,
      );

      if (res.data['success'] == true) {
        cargarMisReservas(idEmpresa: idEmpresa);
      } else {
        throw Exception(res.data['message'] ?? 'No se pudo cancelar la reserva.');
      }
    } on DioException catch (e) {
      final msg = e.response?.data?['detail'] ?? 'Error al cancelar la reserva.';
      throw Exception(msg.toString());
    }
  }
}
