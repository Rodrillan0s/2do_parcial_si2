import 'package:dio/dio.dart';
import 'package:flutter/foundation.dart';
import 'api_client.dart';

class VarianteDisponibleModel {
  final int idVariante;
  final String talla;
  final String color;
  final String sku;
  final int stock;

  VarianteDisponibleModel({
    required this.idVariante,
    required this.talla,
    required this.color,
    required this.sku,
    required this.stock,
  });

  factory VarianteDisponibleModel.fromJson(Map<String, dynamic> json) {
    return VarianteDisponibleModel(
      idVariante: json['id_variante'] ?? 0,
      talla: json['talla'] ?? '',
      color: json['color'] ?? '',
      sku: json['sku'] ?? '',
      stock: json['stock'] ?? 0,
    );
  }
}

class ItemElegibleDevolucionModel {
  final int idDetalleVenta;
  final int idVariante;
  final int idProducto;
  final String productoNombre;
  final String tallaNombre;
  final String colorNombre;
  final String codigoHex;
  final int cantidadComprada;
  final int cantidadDevuelta;
  final int cantidadDisponible;
  final double precioUnitario;
  final double subtotalNeto;
  final String? imagenUrl;
  final List<VarianteDisponibleModel> variantesDisponibles;

  ItemElegibleDevolucionModel({
    required this.idDetalleVenta,
    required this.idVariante,
    required this.idProducto,
    required this.productoNombre,
    required this.tallaNombre,
    required this.colorNombre,
    required this.codigoHex,
    required this.cantidadComprada,
    required this.cantidadDevuelta,
    required this.cantidadDisponible,
    required this.precioUnitario,
    required this.subtotalNeto,
    this.imagenUrl,
    this.variantesDisponibles = const [],
  });

  factory ItemElegibleDevolucionModel.fromJson(Map<String, dynamic> json) {
    final rawVariantes = json['variantes_disponibles'] as List<dynamic>? ?? [];
    return ItemElegibleDevolucionModel(
      idDetalleVenta: json['id_detalle_venta'] ?? 0,
      idVariante: json['id_variante'] ?? 0,
      idProducto: json['id_producto'] ?? 0,
      productoNombre: json['producto_nombre'] ?? '',
      tallaNombre: json['talla_nombre'] ?? '',
      colorNombre: json['color_nombre'] ?? '',
      codigoHex: json['codigo_hex'] ?? '#000000',
      cantidadComprada: json['cantidad_comprada'] ?? 0,
      cantidadDevuelta: json['cantidad_devuelta'] ?? 0,
      cantidadDisponible: json['cantidad_disponible'] ?? 0,
      precioUnitario: (json['precio_unitario'] != null)
          ? double.tryParse(json['precio_unitario'].toString()) ?? 0.0
          : 0.0,
      subtotalNeto: (json['subtotal_neto'] != null)
          ? double.tryParse(json['subtotal_neto'].toString()) ?? 0.0
          : 0.0,
      imagenUrl: json['imagen_url'],
      variantesDisponibles: rawVariantes
          .map((v) => VarianteDisponibleModel.fromJson(Map<String, dynamic>.from(v)))
          .toList(),
    );
  }
}

class ElegibilidadVentaModel {
  final int idVenta;
  final String numeroVenta;
  final String fechaVenta;
  final double totalVenta;
  final bool esElegible;
  final int diasTranscurridos;
  final String? motivoNoElegible;
  final List<ItemElegibleDevolucionModel> items;

  ElegibilidadVentaModel({
    required this.idVenta,
    required this.numeroVenta,
    required this.fechaVenta,
    required this.totalVenta,
    required this.esElegible,
    required this.diasTranscurridos,
    this.motivoNoElegible,
    required this.items,
  });

  factory ElegibilidadVentaModel.fromJson(Map<String, dynamic> json) {
    final rawItems = json['items'] as List<dynamic>? ?? [];
    return ElegibilidadVentaModel(
      idVenta: json['id_venta'] ?? 0,
      numeroVenta: json['numero_venta'] ?? '',
      fechaVenta: json['fecha_venta'] ?? '',
      totalVenta: (json['total'] != null)
          ? double.tryParse(json['total'].toString()) ?? 0.0
          : 0.0,
      esElegible: json['es_elegible'] ?? true,
      diasTranscurridos: json['dias_transcurridos'] ?? 0,
      motivoNoElegible: json['motivo_no_elegible'],
      items: rawItems
          .map((e) => ItemElegibleDevolucionModel.fromJson(Map<String, dynamic>.from(e)))
          .toList(),
    );
  }
}

class ItemDevolucionSolicitadaModel {
  final int idDetalleDevolucion;
  final int idDetalleVenta;
  final int idVariante;
  final String productoNombre;
  final String tallaNombre;
  final String colorNombre;
  final int cantidad;
  final double precioUnitario;
  final double subtotalDevuelto;
  final String condicion;
  final String? imagenUrl;
  final String? tallaCambio;
  final String? skuCambio;

  String get talla => tallaNombre;
  String get color => colorNombre;

  ItemDevolucionSolicitadaModel({
    required this.idDetalleDevolucion,
    required this.idDetalleVenta,
    required this.idVariante,
    required this.productoNombre,
    required this.tallaNombre,
    required this.colorNombre,
    required this.cantidad,
    required this.precioUnitario,
    required this.subtotalDevuelto,
    required this.condicion,
    this.imagenUrl,
    this.tallaCambio,
    this.skuCambio,
  });

  factory ItemDevolucionSolicitadaModel.fromJson(Map<String, dynamic> json) {
    return ItemDevolucionSolicitadaModel(
      idDetalleDevolucion: json['id_detalle_devolucion'] ?? 0,
      idDetalleVenta: json['id_detalle_venta'] ?? 0,
      idVariante: json['id_variante'] ?? 0,
      productoNombre: json['producto_nombre'] ?? '',
      tallaNombre: json['talla_nombre'] ?? '',
      colorNombre: json['color_nombre'] ?? '',
      cantidad: json['cantidad'] ?? 1,
      precioUnitario: (json['precio_unitario'] != null)
          ? double.tryParse(json['precio_unitario'].toString()) ?? 0.0
          : 0.0,
      subtotalDevuelto: (json['subtotal'] != null)
          ? double.tryParse(json['subtotal'].toString()) ?? 0.0
          : 0.0,
      condicion: json['condicion'] ?? 'REVENDIBLE',
      imagenUrl: json['imagen_url'],
      tallaCambio: json['talla_cambio'] ?? json['talla_deseada'],
      skuCambio: json['sku_cambio'],
    );
  }
}

class SolicitudDevolucionModel {
  final int idDevolucion;
  final String codigoDevolucion;
  final int idVenta;
  final String? numeroVenta;
  final String fechaSolicitud;
  final String estado; // SOLICITADA, EN_REVISION, APROBADA, RECHAZADA, COMPLETADA
  final String tipoResolucion; // CAMBIO_PRENDA, SALDO_A_FAVOR, REEMBOLSO_DINERO
  final String motivo;
  final String? descripcion;
  final double montoTotal;
  final String? estadoReembolso;
  final String? observacionesDictamen;
  final List<ItemDevolucionSolicitadaModel> items;

  String get codigoSolicitud => codigoDevolucion;
  String get motivoGeneral => motivo;
  double get montoTotalEstimado => montoTotal;

  SolicitudDevolucionModel({
    required this.idDevolucion,
    required this.codigoDevolucion,
    required this.idVenta,
    this.numeroVenta,
    required this.fechaSolicitud,
    required this.estado,
    required this.tipoResolucion,
    required this.motivo,
    this.descripcion,
    required this.montoTotal,
    this.estadoReembolso,
    this.observacionesDictamen,
    this.items = const [],
  });

  factory SolicitudDevolucionModel.fromJson(Map<String, dynamic> json) {
    final rawItems = json['items'] as List<dynamic>? ?? [];
    return SolicitudDevolucionModel(
      idDevolucion: json['id_devolucion'] ?? 0,
      codigoDevolucion: json['codigo_devolucion'] ?? 'DEV-${json['id_devolucion']}',
      idVenta: json['id_venta'] ?? 0,
      numeroVenta: json['numero_venta'],
      fechaSolicitud: json['fecha_solicitud'] ?? '',
      estado: json['estado'] ?? 'SOLICITADA',
      tipoResolucion: json['tipo_resolucion'] ?? 'REEMBOLSO_DINERO',
      motivo: json['motivo'] ?? '',
      descripcion: json['descripcion'],
      montoTotal: (json['monto_total'] != null)
          ? double.tryParse(json['monto_total'].toString()) ?? 0.0
          : 0.0,
      estadoReembolso: json['estado_reembolso'],
      observacionesDictamen: json['observaciones_dictamen'],
      items: rawItems
          .map((e) => ItemDevolucionSolicitadaModel.fromJson(Map<String, dynamic>.from(e)))
          .toList(),
    );
  }
}

class CreditoClienteModel {
  final int idCredito;
  final String codigoCredito;
  final double montoOriginal;
  final double saldoDisponible;
  final String fechaEmision;
  final String? fechaVencimiento;
  final String estado; // ACTIVO, CONSUMIDO, VENCIDO
  final String? origenDevolucion;

  String get codigoVoucher => codigoCredito;

  CreditoClienteModel({
    required this.idCredito,
    required this.codigoCredito,
    required this.montoOriginal,
    required this.saldoDisponible,
    required this.fechaEmision,
    this.fechaVencimiento,
    required this.estado,
    this.origenDevolucion,
  });

  factory CreditoClienteModel.fromJson(Map<String, dynamic> json) {
    return CreditoClienteModel(
      idCredito: json['id_credito'] ?? 0,
      codigoCredito: json['codigo_credito'] ?? '',
      montoOriginal: (json['monto_original'] != null)
          ? double.tryParse(json['monto_original'].toString()) ?? 0.0
          : 0.0,
      saldoDisponible: (json['saldo_disponible'] != null)
          ? double.tryParse(json['saldo_disponible'].toString()) ?? 0.0
          : 0.0,
      fechaEmision: json['fecha_emision'] ?? '',
      fechaVencimiento: json['fecha_vencimiento'],
      estado: json['estado'] ?? 'ACTIVO',
      origenDevolucion: json['origen_devolucion'],
    );
  }
}

class PoliticaDevolucionModel {
  final int diasMaximosDevolucion;
  final bool requiereEtiquetaOriginal;
  final bool permiteSaldoFavor;
  final bool permiteCambioPrenda;
  final int diasResolucionEstimados;

  PoliticaDevolucionModel({
    this.diasMaximosDevolucion = 7,
    this.requiereEtiquetaOriginal = true,
    this.permiteSaldoFavor = true,
    this.permiteCambioPrenda = true,
    this.diasResolucionEstimados = 2,
  });

  factory PoliticaDevolucionModel.fromJson(Map<String, dynamic> json) {
    return PoliticaDevolucionModel(
      diasMaximosDevolucion: json['dias_maximos_devolucion'] ?? json['dias_maximos'] ?? 7,
      requiereEtiquetaOriginal: json['requiere_etiqueta_original'] ?? true,
      permiteSaldoFavor: json['permite_saldo_favor'] ?? true,
      permiteCambioPrenda: json['permite_cambio_prenda'] ?? true,
      diasResolucionEstimados: json['dias_resolucion_estimados'] ?? 2,
    );
  }
}

class DevolucionesService extends ChangeNotifier {
  final Dio _dio = ApiClient.dio;

  List<SolicitudDevolucionModel> _misDevoluciones = [];
  List<CreditoClienteModel> _misCreditos = [];
  Map<String, dynamic>? _politicasTienda;
  bool _cargando = false;
  String? _error;

  List<SolicitudDevolucionModel> get misDevoluciones => _misDevoluciones;
  List<SolicitudDevolucionModel> get misSolicitudes => _misDevoluciones;
  List<CreditoClienteModel> get misCreditos => _misCreditos;
  Map<String, dynamic>? get politicasTienda => _politicasTienda;
  bool get cargando => _cargando;
  String? get error => _error;

  double get saldoTotalCreditos =>
      _misCreditos.where((c) => c.estado == 'ACTIVO').fold(0.0, (acc, c) => acc + c.saldoDisponible);

  Future<ElegibilidadVentaModel> consultarElegibilidadVenta(int idVenta, {int? idEmpresa}) async {
    try {
      final params = <String, dynamic>{};
      if (idEmpresa != null) params['id_empresa'] = idEmpresa;

      final res = await _dio.get(
        '/api/devoluciones/ventas/$idVenta/elegibilidad',
        queryParameters: params,
      );

      if (res.data['success'] == true && res.data['data'] != null) {
        return ElegibilidadVentaModel.fromJson(res.data['data']);
      }
      throw Exception(res.data['message'] ?? 'No se pudo verificar la compra.');
    } on DioException catch (e) {
      final msg = e.response?.data?['detail'] ?? 'Error al verificar la compra para devolución.';
      throw Exception(msg.toString());
    }
  }

  Future<SolicitudDevolucionModel> solicitarDevolucion({
    required int idVenta,
    required String motivo,
    String tipoResolucion = 'REEMBOLSO_DINERO',
    String? descripcion,
    String? evidenciaUrl,
    required List<Map<String, dynamic>> items,
    int? idEmpresa,
  }) async {
    _cargando = true;
    _error = null;
    notifyListeners();

    try {
      final body = <String, dynamic>{
        'id_venta': idVenta,
        'motivo': motivo.trim(),
        'tipo_resolucion': tipoResolucion,
        if (descripcion != null && descripcion.isNotEmpty) 'descripcion': descripcion.trim(),
        if (evidenciaUrl != null) 'evidencia_url': evidenciaUrl,
        'items': items,
        if (idEmpresa != null) 'id_empresa': idEmpresa,
      };

      final res = await _dio.post('/api/devoluciones/solicitudes', data: body);

      if (res.data['success'] == true && res.data['data'] != null) {
        final solicitud = SolicitudDevolucionModel.fromJson(res.data['data']);
        cargarMisDevoluciones(idEmpresa: idEmpresa);
        return solicitud;
      }
      throw Exception(res.data['message'] ?? 'No se pudo registrar la solicitud.');
    } on DioException catch (e) {
      final msg = e.response?.data?['detail'] ?? 'Error de validación al solicitar devolución.';
      throw Exception(msg.toString());
    } finally {
      _cargando = false;
      notifyListeners();
    }
  }

  Future<void> cargarMisDevoluciones({int? idEmpresa}) async {
    _cargando = true;
    _error = null;
    notifyListeners();

    try {
      final params = <String, dynamic>{};
      if (idEmpresa != null) params['id_empresa'] = idEmpresa;

      final res = await _dio.get('/api/devoluciones/mis-solicitudes', queryParameters: params);
      if (res.data['success'] == true && res.data['data'] != null) {
        final list = res.data['data'] as List<dynamic>;
        _misDevoluciones = list
            .map((e) => SolicitudDevolucionModel.fromJson(Map<String, dynamic>.from(e)))
            .toList();
      } else {
        _misDevoluciones = [];
      }
    } on DioException catch (e) {
      if (e.response?.statusCode == 401) {
        _misDevoluciones = [];
      } else {
        _error = e.response?.data?['detail'] ?? 'Error al cargar devoluciones.';
      }
    } catch (_) {
      _error = 'Error de conexión con el servicio de devoluciones.';
    } finally {
      _cargando = false;
      notifyListeners();
    }
  }

  Future<void> cargarMisCreditos({int? idEmpresa}) async {
    try {
      final params = <String, dynamic>{};
      if (idEmpresa != null) params['id_empresa'] = idEmpresa;

      final res = await _dio.get('/api/devoluciones/mis-creditos', queryParameters: params);
      if (res.data['success'] == true && res.data['data'] != null) {
        final list = res.data['data'] as List<dynamic>;
        _misCreditos = list
            .map((e) => CreditoClienteModel.fromJson(Map<String, dynamic>.from(e)))
            .toList();
        notifyListeners();
      }
    } catch (_) {
      // Ignorar fallo de red
    }
  }

  Future<PoliticaDevolucionModel?> consultarPoliticasTienda({int? idEmpresa}) async {
    try {
      final params = <String, dynamic>{};
      if (idEmpresa != null) params['id_empresa'] = idEmpresa;

      final res = await _dio.get('/api/devoluciones/politicas', queryParameters: params);
      if (res.data['success'] == true && res.data['data'] != null) {
        _politicasTienda = Map<String, dynamic>.from(res.data['data']);
        notifyListeners();
        return PoliticaDevolucionModel.fromJson(_politicasTienda!);
      }
    } catch (_) {}
    return PoliticaDevolucionModel();
  }
}
