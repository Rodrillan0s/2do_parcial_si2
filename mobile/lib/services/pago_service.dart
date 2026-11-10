import 'dart:convert';
import 'package:dio/dio.dart';
import 'package:flutter/foundation.dart';
import 'package:uuid/uuid.dart';
import 'api_client.dart';

class ItemResumenPagoModel {
  final int idVariante;
  final int cantidad;
  final double precioUnitario;
  final double subtotal;
  final String productoNombre;
  final String? sku;
  final String talla;
  final String color;

  ItemResumenPagoModel({
    required this.idVariante,
    required this.cantidad,
    required this.precioUnitario,
    required this.subtotal,
    required this.productoNombre,
    this.sku,
    required this.talla,
    required this.color,
  });

  factory ItemResumenPagoModel.fromJson(Map<String, dynamic> json) {
    return ItemResumenPagoModel(
      idVariante: json['id_variante'] ?? 0,
      cantidad: json['cantidad'] ?? 1,
      precioUnitario: (json['precio_unitario'] != null)
          ? double.tryParse(json['precio_unitario'].toString()) ?? 0.0
          : 0.0,
      subtotal: (json['subtotal'] != null)
          ? double.tryParse(json['subtotal'].toString()) ?? 0.0
          : 0.0,
      productoNombre: json['producto_nombre'] ?? '',
      sku: json['sku'],
      talla: json['talla'] ?? '',
      color: json['color'] ?? '',
    );
  }
}

class ResumenPedidoPagoModel {
  final int idPedido;
  final String codigoPedido;
  final int idCliente;
  final int idEmpresa;
  final int idSucursal;
  final String estado;
  final String estadoPago;
  final double subtotal;
  final double costoEnvio;
  final double descuento;
  final double total;
  final String correoContacto;
  final String nombreContacto;
  final int? idVenta;
  final String sucursalNombre;
  final String nombreEmpresa;
  final String? paypalClientId;
  final List<ItemResumenPagoModel> items;

  ResumenPedidoPagoModel({
    required this.idPedido,
    required this.codigoPedido,
    required this.idCliente,
    required this.idEmpresa,
    required this.idSucursal,
    required this.estado,
    required this.estadoPago,
    required this.subtotal,
    required this.costoEnvio,
    required this.descuento,
    required this.total,
    required this.correoContacto,
    required this.nombreContacto,
    this.idVenta,
    required this.sucursalNombre,
    required this.nombreEmpresa,
    this.paypalClientId,
    required this.items,
  });

  factory ResumenPedidoPagoModel.fromJson(Map<String, dynamic> json) {
    final listItems = (json['items'] as List<dynamic>? ?? [])
        .map((e) => ItemResumenPagoModel.fromJson(e as Map<String, dynamic>))
        .toList();

    return ResumenPedidoPagoModel(
      idPedido: json['id_pedido'] ?? 0,
      codigoPedido: json['codigo_pedido'] ?? '',
      idCliente: json['id_cliente'] ?? 0,
      idEmpresa: json['id_empresa'] ?? 0,
      idSucursal: json['id_sucursal'] ?? 0,
      estado: json['estado'] ?? 'PENDIENTE',
      estadoPago: json['estado_pago'] ?? 'PENDIENTE_PAGO',
      subtotal: (json['subtotal'] != null)
          ? double.tryParse(json['subtotal'].toString()) ?? 0.0
          : 0.0,
      costoEnvio: (json['costo_envio'] != null)
          ? double.tryParse(json['costo_envio'].toString()) ?? 0.0
          : 0.0,
      descuento: (json['descuento'] != null)
          ? double.tryParse(json['descuento'].toString()) ?? 0.0
          : 0.0,
      total: (json['total'] != null)
          ? double.tryParse(json['total'].toString()) ?? 0.0
          : 0.0,
      correoContacto: json['correo_contacto'] ?? '',
      nombreContacto: json['nombre_contacto'] ?? '',
      idVenta: json['id_venta'],
      sucursalNombre: json['sucursal_nombre'] ?? 'Sucursal Central',
      nombreEmpresa: json['nombre_empresa'] ?? 'Aurora Store',
      paypalClientId: json['paypal_client_id'],
      items: listItems,
    );
  }
}

class ResultadoPagoModel {
  final int idPedido;
  final String codigoPedido;
  final int idVenta;
  final String numeroVenta;
  final String tipoDocumento;
  final double total;
  final String metodoPago;
  final String codigoTransaccion;
  final String? urlDescargaPdf;

  ResultadoPagoModel({
    required this.idPedido,
    required this.codigoPedido,
    required this.idVenta,
    required this.numeroVenta,
    required this.tipoDocumento,
    required this.total,
    required this.metodoPago,
    required this.codigoTransaccion,
    this.urlDescargaPdf,
  });

  factory ResultadoPagoModel.fromJson(Map<String, dynamic> json) {
    return ResultadoPagoModel(
      idPedido: json['id_pedido'] ?? 0,
      codigoPedido: json['codigo_pedido'] ?? '',
      idVenta: json['id_venta'] ?? 0,
      numeroVenta: json['numero_venta'] ?? '',
      tipoDocumento: json['tipo_documento'] ?? 'COMPROBANTE',
      total: (json['total'] != null)
          ? double.tryParse(json['total'].toString()) ?? 0.0
          : 0.0,
      metodoPago: json['metodo_pago'] ?? 'TARJETA',
      codigoTransaccion: json['codigo_transaccion'] ?? '',
      urlDescargaPdf: json['url_descarga_pdf'],
    );
  }
}

class PagoService extends ChangeNotifier {
  final Dio _dio = ApiClient.dio;

  bool _cargando = false;
  String? _error;
  ResumenPedidoPagoModel? _resumen;
  ResultadoPagoModel? _resultado;

  bool get cargando => _cargando;
  String? get error => _error;
  ResumenPedidoPagoModel? get resumen => _resumen;
  ResultadoPagoModel? get resultado => _resultado;

  void limpiar() {
    _cargando = false;
    _error = null;
    _resumen = null;
    _resultado = null;
    notifyListeners();
  }

  Future<ResumenPedidoPagoModel?> obtenerResumen(int idPedido, {int? idEmpresa}) async {
    _cargando = true;
    _error = null;
    notifyListeners();

    try {
      final params = <String, dynamic>{};
      if (idEmpresa != null) params['id_empresa'] = idEmpresa;

      final res = await _dio.get('/api/pagos/resumen/$idPedido', queryParameters: params);
      if (res.data['success'] == true && res.data['data'] != null) {
        _resumen = ResumenPedidoPagoModel.fromJson(res.data['data']);
        return _resumen;
      } else {
        _error = 'No se encontró el resumen del pedido.';
        return null;
      }
    } on DioException catch (e) {
      if (e.response?.statusCode == 401) {
        _error = 'Debes iniciar sesión para consultar el pago del pedido.';
      } else {
        _error = e.response?.data?['detail'] ?? 'Error al cargar resumen del pago.';
      }
      return null;
    } catch (e) {
      _error = 'Error de conexión con el servicio de pagos.';
      return null;
    } finally {
      _cargando = false;
      notifyListeners();
    }
  }

  Future<ResultadoPagoModel?> procesarTarjeta({
    required int idPedido,
    required String titular,
    required String numeroTarjeta,
    required String mesExp,
    required String anioExp,
    required String cvv,
    String? nitCi,
    String? razonSocial,
    int? idEmpresa,
  }) async {
    _cargando = true;
    _error = null;
    notifyListeners();

    try {
      final payload = <String, dynamic>{
        'id_pedido': idPedido,
        'titular': titular.trim(),
        'numero_tarjeta': numeroTarjeta.replaceAll(' ', ''),
        'mes_exp': mesExp.trim(),
        'anio_exp': anioExp.trim(),
        'cvv': cvv.trim(),
        if (nitCi != null && nitCi.trim().isNotEmpty) 'nit_ci': nitCi.trim(),
        if (razonSocial != null && razonSocial.trim().isNotEmpty) 'razon_social': razonSocial.trim(),
        if (idEmpresa != null) 'id_empresa': idEmpresa,
      };

      final res = await _dio.post('/api/pagos/tarjeta/procesar', data: payload);
      if (res.data['success'] == true && res.data['data'] != null) {
        _resultado = ResultadoPagoModel.fromJson(res.data['data']);
        return _resultado;
      } else {
        _error = res.data['message'] ?? 'No se pudo autorizar la transacción.';
        return null;
      }
    } on DioException catch (e) {
      if (e.response?.statusCode == 401) {
        _error = 'Tu sesión ha expirado. Por favor inicia sesión nuevamente.';
      } else {
        _error = e.response?.data?['detail'] ?? 'Error al procesar el pago con tarjeta.';
      }
      return null;
    } catch (e) {
      _error = 'Error inesperado al conectar con la pasarela bancaria.';
      return null;
    } finally {
      _cargando = false;
      notifyListeners();
    }
  }

  Future<Map<String, dynamic>?> crearOrdenPayPal(int idPedido, {int? idEmpresa}) async {
    _cargando = true;
    _error = null;
    notifyListeners();

    try {
      final payload = <String, dynamic>{
        'id_pedido': idPedido,
        if (idEmpresa != null) 'id_empresa': idEmpresa,
      };

      final res = await _dio.post('/api/pagos/paypal/crear-orden', data: payload);
      if (res.data['success'] == true && res.data['data'] != null) {
        return res.data['data'] as Map<String, dynamic>;
      } else {
        _error = res.data['message'] ?? 'No se pudo iniciar la orden de PayPal.';
        return null;
      }
    } on DioException catch (e) {
      if (e.response?.statusCode == 401) {
        _error = 'Tu sesión ha expirado. Por favor inicia sesión nuevamente.';
      } else {
        _error = e.response?.data?['detail'] ?? 'Error al conectar con PayPal.';
      }
      return null;
    } catch (e) {
      _error = 'Error de conexión con el servicio de PayPal.';
      return null;
    } finally {
      _cargando = false;
      notifyListeners();
    }
  }

  Future<ResultadoPagoModel?> capturarPayPal({
    required int idPedido,
    required String orderId,
    String? nitCi,
    String? razonSocial,
    int? idEmpresa,
  }) async {
    _cargando = true;
    _error = null;
    notifyListeners();

    try {
      final payload = <String, dynamic>{
        'id_pedido': idPedido,
        'order_id': orderId,
        if (nitCi != null && nitCi.trim().isNotEmpty) 'nit_ci': nitCi.trim(),
        if (razonSocial != null && razonSocial.trim().isNotEmpty) 'razon_social': razonSocial.trim(),
        if (idEmpresa != null) 'id_empresa': idEmpresa,
      };

      final res = await _dio.post('/api/pagos/paypal/capturar', data: payload);
      if (res.data['success'] == true && res.data['data'] != null) {
        _resultado = ResultadoPagoModel.fromJson(res.data['data']);
        return _resultado;
      } else {
        _error = res.data['message'] ?? 'PayPal no confirmó la transacción.';
        return null;
      }
    } on DioException catch (e) {
      if (e.response?.statusCode == 401) {
        _error = 'Tu sesión ha expirado. Por favor inicia sesión nuevamente.';
      } else {
        _error = e.response?.data?['detail'] ?? 'Error al capturar el pago con PayPal.';
      }
      return null;
    } catch (e) {
      _error = 'Error de conexión al verificar el pago con PayPal.';
      return null;
    } finally {
      _cargando = false;
      notifyListeners();
    }
  }

  Future<ResultadoPagoModel?> procesarQR({
    required int idPedido,
    String? codigoTransaccion,
    String? nitCi,
    String? razonSocial,
    int? idEmpresa,
  }) async {
    _cargando = true;
    _error = null;
    notifyListeners();

    try {
      final payload = <String, dynamic>{
        'id_pedido': idPedido,
        if (codigoTransaccion != null && codigoTransaccion.trim().isNotEmpty)
          'codigo_transaccion': codigoTransaccion.trim(),
        if (nitCi != null && nitCi.trim().isNotEmpty) 'nit_ci': nitCi.trim(),
        if (razonSocial != null && razonSocial.trim().isNotEmpty)
          'razon_social': razonSocial.trim(),
        if (idEmpresa != null) 'id_empresa': idEmpresa,
      };

      final res = await _dio.post('/api/pagos/qr/confirmar', data: payload);
      if (res.data['success'] == true && res.data['data'] != null) {
        _resultado = ResultadoPagoModel.fromJson(res.data['data']);
        return _resultado;
      } else {
        _error = res.data['message'] ?? 'Error al procesar el pago QR.';
        return null;
      }
    } on DioException catch (e) {
      if (e.response?.statusCode == 401) {
        _error = 'Tu sesión ha expirado. Por favor inicia sesión nuevamente.';
      } else {
        _error = e.response?.data?['detail'] ?? 'Error al procesar el pago QR.';
      }
      return null;
    } catch (e) {
      _error = 'Error de conexión al procesar el pago QR.';
      return null;
    } finally {
      _cargando = false;
      notifyListeners();
    }
  }

  /// Genera un identificador único UUID para el intento de pago offline en Dispositivo A
  String generarIntentId() {
    return const Uuid().v4();
  }

  /// Construye el payload en Base64 para el código QR de pago delegado offline
  String generarPayloadQrOffline({
    required String intentId,
    required int idEmpresa,
    int? idSucursal,
    required double total,
    List<Map<String, dynamic>>? items,
    int? idPedido,
    String? codigoPedido,
  }) {
    final Map<String, dynamic> data = {
      'intent_id': intentId,
      'id_empresa': idEmpresa,
      'id_sucursal': idSucursal,
      'monto_total': total,
      'items': items ?? [],
      'id_pedido': idPedido,
      'codigo_pedido': codigoPedido,
      'timestamp': DateTime.now().toUtc().toIso8601String(),
    };
    final jsonStr = jsonEncode(data);
    return base64UrlEncode(utf8.encode(jsonStr));
  }

  /// Dispositivo B (con conexión): Inicia la orden de PayPal delegada en el servidor
  Future<Map<String, dynamic>?> iniciarPagoDelegado({
    required String intentId,
    required int idEmpresa,
    int? idSucursal,
    required double montoTotal,
    List<Map<String, dynamic>>? items,
    int? idPedido,
    String? codigoReferencia,
    String? clienteNombre,
    String? nitCi,
    String? razonSocial,
  }) async {
    _cargando = true;
    _error = null;
    notifyListeners();

    try {
      final payload = <String, dynamic>{
        'intent_id': intentId,
        'id_empresa': idEmpresa,
        if (idSucursal != null) 'id_sucursal': idSucursal,
        'monto_total': montoTotal,
        'items': items ?? [],
        if (idPedido != null) 'id_pedido': idPedido,
        if (codigoReferencia != null) 'codigo_referencia': codigoReferencia,
        if (clienteNombre != null) 'cliente_nombre': clienteNombre,
        if (nitCi != null) 'nit_ci': nitCi,
        if (razonSocial != null) 'razon_social': razonSocial,
      };

      final res = await _dio.post('/api/pagos/paypal/delegado/iniciar', data: payload);
      if (res.data['success'] == true && res.data['data'] != null) {
        return res.data['data'] as Map<String, dynamic>;
      } else {
        _error = res.data['message'] ?? 'No se pudo iniciar el pago delegado.';
        return null;
      }
    } on DioException catch (e) {
      _error = e.response?.data?['detail'] ?? 'Error al conectar para iniciar pago delegado.';
      return null;
    } catch (e) {
      _error = 'Error inesperado al iniciar pago delegado.';
      return null;
    } finally {
      _cargando = false;
      notifyListeners();
    }
  }

  /// Dispositivo B (con conexión): Captura la orden de PayPal aprobada
  Future<ResultadoPagoModel?> capturarPagoDelegado({
    required String intentId,
    required String orderId,
    String? nitCi,
    String? razonSocial,
  }) async {
    _cargando = true;
    _error = null;
    notifyListeners();

    try {
      final payload = <String, dynamic>{
        'intent_id': intentId,
        'order_id': orderId,
        if (nitCi != null && nitCi.trim().isNotEmpty) 'nit_ci': nitCi.trim(),
        if (razonSocial != null && razonSocial.trim().isNotEmpty) 'razon_social': razonSocial.trim(),
      };

      final res = await _dio.post('/api/pagos/paypal/delegado/capturar', data: payload);
      if (res.data['success'] == true && res.data['data'] != null) {
        _resultado = ResultadoPagoModel.fromJson(res.data['data']);
        return _resultado;
      } else {
        _error = res.data['message'] ?? 'No se pudo capturar el pago delegado.';
        return null;
      }
    } on DioException catch (e) {
      _error = e.response?.data?['detail'] ?? 'Error al capturar pago delegado en PayPal.';
      return null;
    } catch (e) {
      _error = 'Error de conexión al verificar el pago delegado.';
      return null;
    } finally {
      _cargando = false;
      notifyListeners();
    }
  }

  /// Dispositivo A (al reconectar): Consulta si el pago delegado ya fue completado y capturado
  Future<Map<String, dynamic>?> consultarEstadoPagoDelegado(String intentId) async {
    try {
      final res = await _dio.get('/api/pagos/paypal/delegado/estado/$intentId');
      if (res.data != null && res.data is Map<String, dynamic>) {
        return res.data as Map<String, dynamic>;
      }
      return null;
    } catch (e) {
      return null;
    }
  }
}

