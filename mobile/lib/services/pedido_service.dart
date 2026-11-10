import 'package:dio/dio.dart';
import 'package:flutter/foundation.dart';
import 'api_client.dart';

class SucursalCheckoutModel {
  final int idSucursal;
  final int idEmpresa;
  final String nombre;
  final String direccion;
  final String? telefono;
  final String ciudad;
  final bool tieneStockCompleto;
  final String stockEstado;
  final String stockLabel;

  SucursalCheckoutModel({
    required this.idSucursal,
    required this.idEmpresa,
    required this.nombre,
    required this.direccion,
    this.telefono,
    required this.ciudad,
    this.tieneStockCompleto = true,
    this.stockEstado = 'DISPONIBLE',
    this.stockLabel = '✓ Disponible',
  });

  factory SucursalCheckoutModel.fromJson(Map<String, dynamic> json) {
    return SucursalCheckoutModel(
      idSucursal: json['id_sucursal'] ?? 0,
      idEmpresa: json['id_empresa'] ?? 0,
      nombre: json['nombre'] ?? '',
      direccion: json['direccion'] ?? '',
      telefono: json['telefono']?.toString(),
      ciudad: json['ciudad'] ?? '',
      tieneStockCompleto: json['tiene_stock_completo'] ?? true,
      stockEstado: json['stock_estado'] ?? 'DISPONIBLE',
      stockLabel: json['stock_label'] ?? '✓ Disponible',
    );
  }
}

class PedidoItemModel {
  final int idDetallePedido;
  final int idVariante;
  final String productoNombre;
  final String tallaNombre;
  final String colorNombre;
  final String codigoHex;
  final int cantidad;
  final double precioUnitario;
  final double subtotal;
  final String? imagenUrl;

  String get talla => tallaNombre;
  String get color => colorNombre;

  PedidoItemModel({
    required this.idDetallePedido,
    required this.idVariante,
    required this.productoNombre,
    required this.tallaNombre,
    required this.colorNombre,
    required this.codigoHex,
    required this.cantidad,
    required this.precioUnitario,
    required this.subtotal,
    this.imagenUrl,
  });

  factory PedidoItemModel.fromJson(Map<String, dynamic> json) {
    return PedidoItemModel(
      idDetallePedido: json['id_detalle_pedido'] ?? 0,
      idVariante: json['id_variante'] ?? 0,
      productoNombre: json['producto_nombre'] ?? '',
      tallaNombre: json['talla_nombre'] ?? '',
      colorNombre: json['color_nombre'] ?? '',
      codigoHex: json['codigo_hex'] ?? '#000000',
      cantidad: json['cantidad'] ?? 1,
      precioUnitario: (json['precio_unitario'] != null)
          ? double.tryParse(json['precio_unitario'].toString()) ?? 0.0
          : 0.0,
      subtotal: (json['subtotal'] != null)
          ? double.tryParse(json['subtotal'].toString()) ?? 0.0
          : 0.0,
      imagenUrl: json['imagen_url'],
    );
  }
}

class PedidoModel {
  final int idPedido;
  final int? idEmpresa;
  final int? idSucursal;
  final String codigoPedido;
  final String fechaPedido;
  final String estado;
  final String estadoPago;
  final String modalidadCompra;
  final String nombreContacto;
  final String telefonoContacto;
  final String? correoContacto;
  final String? direccionEntrega;
  final String? ciudadEntrega;
  final String? sucursalNombre;
  final String? nombreEmpresa;
  final double subtotal;
  final double costoEnvio;
  final double descuento;
  final double total;
  final int totalItems;
  final List<PedidoItemModel> items;

  int get idVenta => idPedido;

  PedidoModel({
    required this.idPedido,
    this.idEmpresa,
    this.idSucursal,
    required this.codigoPedido,
    required this.fechaPedido,
    required this.estado,
    required this.estadoPago,
    required this.modalidadCompra,
    required this.nombreContacto,
    required this.telefonoContacto,
    this.correoContacto,
    this.direccionEntrega,
    this.ciudadEntrega,
    this.sucursalNombre,
    this.nombreEmpresa,
    required this.subtotal,
    required this.costoEnvio,
    required this.descuento,
    required this.total,
    required this.totalItems,
    this.items = const [],
  });

  factory PedidoModel.fromJson(Map<String, dynamic> json) {
    final rawItems = (json['items'] as List<dynamic>?) ?? (json['items_resumen'] as List<dynamic>?) ?? [];
    return PedidoModel(
      idPedido: json['id_pedido'] ?? 0,
      idEmpresa: json['id_empresa'] as int?,
      idSucursal: json['id_sucursal'] as int?,
      codigoPedido: json['codigo_pedido'] ?? '',
      fechaPedido: json['fecha_pedido'] ?? '',
      estado: json['estado'] ?? 'PENDIENTE',
      estadoPago: json['estado_pago'] ?? 'PENDIENTE',
      modalidadCompra: json['modalidad_compra'] ?? 'RETIRO_SUCURSAL',
      nombreContacto: json['nombre_contacto'] ?? '',
      telefonoContacto: json['telefono_contacto'] ?? '',
      correoContacto: json['correo_contacto'],
      direccionEntrega: json['direccion_entrega'],
      ciudadEntrega: json['ciudad_entrega'],
      sucursalNombre: json['sucursal_nombre'],
      nombreEmpresa: json['nombre_empresa'],
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
      totalItems: json['total_items'] ?? rawItems.length,
      items: rawItems
          .map((e) => PedidoItemModel.fromJson(Map<String, dynamic>.from(e)))
          .toList(),
    );
  }
}

class PedidoService extends ChangeNotifier {
  final Dio _dio = ApiClient.dio;

  List<PedidoModel> _misPedidos = [];
  bool _cargando = false;
  String? _error;

  List<PedidoModel> get misPedidos => _misPedidos;
  bool get cargando => _cargando;
  String? get error => _error;

  Future<List<SucursalCheckoutModel>> obtenerSucursalesCheckout({int? idEmpresa}) async {
    try {
      final params = <String, dynamic>{};
      if (idEmpresa != null) params['id_empresa'] = idEmpresa;

      final res = await _dio.get('/api/pedidos/sucursales', queryParameters: params);
      if (res.data['success'] == true && res.data['data'] != null) {
        final listRaw = res.data['data'] as List<dynamic>;
        return listRaw
            .map((e) => SucursalCheckoutModel.fromJson(Map<String, dynamic>.from(e)))
            .toList();
      }
      return [];
    } catch (_) {
      return [];
    }
  }

  Future<PedidoModel> crearPedido({
    required int idSucursal,
    required String modalidadCompra, // 'RETIRO_SUCURSAL' | 'ENTREGA_DOMICILIO'
    required String nombreContacto,
    required String telefonoContacto,
    String? correoContacto,
    String? direccionEntrega,
    String? ciudadEntrega,
    String? notasEntrega,
    int? idEmpresa,
  }) async {
    try {
      final body = <String, dynamic>{
        'id_sucursal': idSucursal,
        'modalidad_compra': modalidadCompra,
        'nombre_contacto': nombreContacto.trim(),
        'telefono_contacto': telefonoContacto.trim(),
        if (correoContacto != null && correoContacto.isNotEmpty) 'correo_contacto': correoContacto.trim(),
        if (direccionEntrega != null && direccionEntrega.isNotEmpty) 'direccion_entrega': direccionEntrega.trim(),
        if (ciudadEntrega != null && ciudadEntrega.isNotEmpty) 'ciudad_entrega': ciudadEntrega.trim(),
        if (notasEntrega != null && notasEntrega.isNotEmpty) 'notas_entrega': notasEntrega.trim(),
        if (idEmpresa != null) 'id_empresa': idEmpresa,
      };

      final res = await _dio.post('/api/pedidos', data: body);
      if (res.data['success'] == true && res.data['data'] != null) {
        final pedido = PedidoModel.fromJson(res.data['data']);
        cargarMisPedidos();
        return pedido;
      }
      throw Exception(res.data['message'] ?? 'Error al procesar pedido.');
    } on DioException catch (e) {
      final msg = e.response?.data?['detail'] ?? 'Error de validación al generar el pedido.';
      throw Exception(msg.toString());
    }
  }

  Future<void> cargarMisPedidos({int? idEmpresa}) async {
    _cargando = true;
    _error = null;
    notifyListeners();

    try {
      final params = <String, dynamic>{
        'limit': 50,
      };
      if (idEmpresa != null) params['id_empresa'] = idEmpresa;

      final res = await _dio.get('/api/pedidos', queryParameters: params);
      if (res.data['success'] == true && res.data['data'] != null) {
        final rawList = res.data['data'] as List<dynamic>;
        _misPedidos = rawList
            .map((e) => PedidoModel.fromJson(Map<String, dynamic>.from(e)))
            .toList();
      } else {
        _misPedidos = [];
      }
    } on DioException catch (e) {
      if (e.response?.statusCode == 401) {
        _misPedidos = [];
      } else {
        _error = e.response?.data?['detail'] ?? 'Error al consultar historial de pedidos.';
      }
    } catch (_) {
      _error = 'Error de conexión con el servicio de pedidos.';
    } finally {
      _cargando = false;
      notifyListeners();
    }
  }

  Future<PedidoModel> obtenerDetallePedido(int idPedido, {int? idEmpresa}) async {
    try {
      final params = <String, dynamic>{};
      if (idEmpresa != null) params['id_empresa'] = idEmpresa;

      final res = await _dio.get('/api/pedidos/$idPedido', queryParameters: params);
      if (res.data['success'] == true && res.data['data'] != null) {
        return PedidoModel.fromJson(res.data['data']);
      }
      throw Exception('No se encontró el detalle del pedido.');
    } on DioException catch (e) {
      final msg = e.response?.data?['detail'] ?? 'Error al cargar pedido.';
      throw Exception(msg.toString());
    }
  }
}
