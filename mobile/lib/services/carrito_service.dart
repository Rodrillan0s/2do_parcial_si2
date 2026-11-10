import 'package:dio/dio.dart';
import 'package:flutter/foundation.dart';
import 'api_client.dart';
import 'token_storage.dart';
import '../core/connectivity/connectivity_service.dart';
import '../core/database/database_helper.dart';
import '../core/sync/sync_coordinator.dart';
import '../core/tenant/tenant_context_manager.dart';

class DifferentStoreCartException implements Exception {
  final String existingTenantName;
  final int existingTenantId;
  final int newTenantId;

  DifferentStoreCartException({
    required this.existingTenantName,
    required this.existingTenantId,
    required this.newTenantId,
  });

  @override
  String toString() =>
      'Tu bolsa actual contiene prendas de $existingTenantName. ¿Deseas conservarla o iniciar una nueva bolsa para esta tienda?';
}

class ItemCarritoModel {
  final int idDetalleCarrito;
  final int idVariante;
  final int idProducto;
  final String productoNombre;
  final String? codigoProducto;
  final String tallaNombre;
  final String colorNombre;
  final String codigoHex;
  final String? sku;
  final String? imagenUrl;
  int cantidad;
  final double precioUnitario;
  double subtotal;
  final int stockDisponible;
  final bool disponible;
  final String? advertenciaStock;

  ItemCarritoModel({
    required this.idDetalleCarrito,
    required this.idVariante,
    required this.idProducto,
    required this.productoNombre,
    this.codigoProducto,
    required this.tallaNombre,
    required this.colorNombre,
    required this.codigoHex,
    this.sku,
    this.imagenUrl,
    required this.cantidad,
    required this.precioUnitario,
    required this.subtotal,
    required this.stockDisponible,
    required this.disponible,
    this.advertenciaStock,
  });

  factory ItemCarritoModel.fromJson(Map<String, dynamic> json) {
    return ItemCarritoModel(
      idDetalleCarrito: json['id_detalle_carrito'] ?? 0,
      idVariante: json['id_variante'] ?? 0,
      idProducto: json['id_producto'] ?? 0,
      productoNombre: json['producto_nombre'] ?? '',
      codigoProducto: json['codigo_producto'],
      tallaNombre: json['talla_nombre'] ?? '',
      colorNombre: json['color_nombre'] ?? '',
      codigoHex: json['codigo_hex'] ?? '#000000',
      sku: json['sku'],
      imagenUrl: json['imagen_url'],
      cantidad: json['cantidad'] ?? 1,
      precioUnitario: (json['precio_unitario'] != null)
          ? double.tryParse(json['precio_unitario'].toString()) ?? 0.0
          : 0.0,
      subtotal: (json['subtotal'] != null)
          ? double.tryParse(json['subtotal'].toString()) ?? 0.0
          : 0.0,
      stockDisponible: json['stock_disponible'] ?? 0,
      disponible: json['disponible'] ?? true,
      advertenciaStock: json['advertencia_stock'],
    );
  }
}

class CarritoModel {
  final int idCarrito;
  final int idEmpresa;
  final String nombreEmpresa;
  final List<ItemCarritoModel> items;
  final int totalItems;
  final double subtotal;
  final double descuento;
  final double total;
  final bool puedeContinuarCompra;

  CarritoModel({
    required this.idCarrito,
    required this.idEmpresa,
    required this.nombreEmpresa,
    required this.items,
    required this.totalItems,
    required this.subtotal,
    required this.descuento,
    required this.total,
    required this.puedeContinuarCompra,
  });

  factory CarritoModel.fromJson(Map<String, dynamic> json) {
    final itemsRaw = json['items'] as List<dynamic>? ?? [];
    return CarritoModel(
      idCarrito: json['id_carrito'] ?? 0,
      idEmpresa: json['id_empresa'] ?? 0,
      nombreEmpresa: json['nombre_empresa'] ?? '',
      items: itemsRaw
          .map((e) => ItemCarritoModel.fromJson(Map<String, dynamic>.from(e)))
          .toList(),
      totalItems: json['total_items'] ?? 0,
      subtotal: (json['subtotal'] != null)
          ? double.tryParse(json['subtotal'].toString()) ?? 0.0
          : 0.0,
      descuento: (json['descuento'] != null)
          ? double.tryParse(json['descuento'].toString()) ?? 0.0
          : 0.0,
      total: (json['total'] != null)
          ? double.tryParse(json['total'].toString()) ?? 0.0
          : 0.0,
      puedeContinuarCompra: json['puede_continuar_compra'] ?? true,
    );
  }
}

class CarritoService extends ChangeNotifier {
  final Dio _dio = ApiClient.dio;
  final DatabaseHelper _dbHelper = DatabaseHelper();
  final SyncCoordinator _syncCoordinator = SyncCoordinator();
  final TenantContextManager _tenantManager = TenantContextManager();

  CarritoModel? _carrito;
  bool _cargando = false;
  String? _error;

  CarritoModel? get carrito => _carrito;
  bool get cargando => _cargando;
  String? get error => _error;
  int get totalItems => _carrito?.totalItems ?? 0;
  double get total => _carrito?.total ?? 0.0;

  Future<void> cargarCarrito({int? idEmpresa}) async {
    _cargando = true;
    _error = null;
    notifyListeners();

    final activeEmpresa = idEmpresa ?? (await TokenStorage.getEmpresaId()) ?? 1;
    final userId = (await TokenStorage.getUsuario())?['id_usuario'] as int? ?? 1;

    try {
      final params = <String, dynamic>{};
      if (idEmpresa != null) params['id_empresa'] = idEmpresa;

      final res = await _dio.get('/api/carrito', queryParameters: params);
      if (res.data['success'] == true && res.data['data'] != null) {
        final dataMap = Map<String, dynamic>.from(res.data['data'] as Map);
        _carrito = CarritoModel.fromJson(dataMap);
        // Persistir borrador local en SQLite
        await _dbHelper.saveCartDraft(activeEmpresa, userId, _carrito!.items);
      } else {
        _carrito = null;
      }
    } on DioException catch (e) {
      if (e.response?.statusCode == 401) {
        _carrito = null;
        _error = null; // No mostrar error en banner para no autenticado
      } else {
        // Fallback a SQLite
        final cached = await _dbHelper.getCartDraft(activeEmpresa, userId);
        if (cached.isNotEmpty) {
          _carrito = CarritoModel(
            idCarrito: 0,
            idEmpresa: activeEmpresa,
            nombreEmpresa: _tenantManager.nombreTiendaActiva,
            totalItems: cached.fold(0, (sum, i) => sum + i.cantidad),
            subtotal: cached.fold(0.0, (sum, i) => sum + i.subtotal),
            descuento: 0.0,
            total: cached.fold(0.0, (sum, i) => sum + i.subtotal),
            items: cached,
            puedeContinuarCompra: true,
          );
          _error = null;
        } else {
          _error = e.response?.data?['detail'] ?? 'Error al consultar la bolsa.';
        }
      }
    } catch (e) {
      final cached = await _dbHelper.getCartDraft(activeEmpresa, userId);
      if (cached.isNotEmpty) {
        _carrito = CarritoModel(
          idCarrito: 0,
          idEmpresa: activeEmpresa,
          nombreEmpresa: _tenantManager.nombreTiendaActiva,
          totalItems: cached.fold(0, (sum, i) => sum + i.cantidad),
          subtotal: cached.fold(0.0, (sum, i) => sum + i.subtotal),
          descuento: 0.0,
          total: cached.fold(0.0, (sum, i) => sum + i.subtotal),
          items: cached,
          puedeContinuarCompra: true,
        );
        _error = null;
      } else {
        _error = 'Error de conexión con el carrito.';
      }
    } finally {
      _cargando = false;
      notifyListeners();
    }
  }

  bool _isNetworkError(DioException e) {
    return e.type == DioExceptionType.connectionError ||
        e.type == DioExceptionType.connectionTimeout ||
        e.type == DioExceptionType.sendTimeout ||
        e.type == DioExceptionType.receiveTimeout ||
        (e.type == DioExceptionType.unknown && e.error != null);
  }

  Future<bool> agregarItem({
    required int idVariante,
    int cantidad = 1,
    int? idEmpresa,
    String? productoNombre,
    double? precioUnitario,
    String? tallaNombre,
    String? colorNombre,
    String? codigoHex,
    String? imagenUrl,
  }) async {
    // 1. Detección estricta de conflicto multitenant (no borrar silenciosamente)
    if (idEmpresa != null &&
        _carrito != null &&
        _carrito!.items.isNotEmpty &&
        _carrito!.idEmpresa != 0 &&
        _carrito!.idEmpresa != idEmpresa) {
      throw DifferentStoreCartException(
        existingTenantName: _carrito!.nombreEmpresa.isNotEmpty
            ? _carrito!.nombreEmpresa
            : 'otra tienda',
        existingTenantId: _carrito!.idEmpresa,
        newTenantId: idEmpresa,
      );
    }

    _cargando = true;
    _error = null;
    notifyListeners();

    final activeEmpresa = idEmpresa ?? _carrito?.idEmpresa ?? (await TokenStorage.getEmpresaId()) ?? 1;
    final userId = (await TokenStorage.getUsuario())?['id_usuario'] as int? ?? 1;

    // Si ya estamos desconectados, aplicar flujo offline directamente
    if (ConnectivityService().isOffline) {
      await _aplicarAgregarItemOffline(
        idVariante: idVariante,
        cantidad: cantidad,
        activeEmpresa: activeEmpresa,
        userId: userId,
        productoNombre: productoNombre,
        precioUnitario: precioUnitario,
        tallaNombre: tallaNombre,
        colorNombre: colorNombre,
        codigoHex: codigoHex,
        imagenUrl: imagenUrl,
      );
      _cargando = false;
      notifyListeners();
      return true;
    }

    try {
      final body = <String, dynamic>{
        'id_variante': idVariante,
        'cantidad': cantidad,
        if (idEmpresa != null) 'id_empresa': idEmpresa,
      };

      final res = await _dio.post('/api/carrito/items', data: body);
      if (res.data['success'] == true && res.data['data'] != null) {
        final dataMap = Map<String, dynamic>.from(res.data['data'] as Map);
        _carrito = CarritoModel.fromJson(dataMap);
        await _dbHelper.saveCartDraft(activeEmpresa, userId, _carrito!.items);
        notifyListeners();
        return true;
      }
      return false;
    } on DioException catch (e) {
      if (e.response?.statusCode == 401) {
        _error = 'Debes iniciar sesión para agregar prendas a la bolsa.';
      } else if (_isNetworkError(e)) {
        await _aplicarAgregarItemOffline(
          idVariante: idVariante,
          cantidad: cantidad,
          activeEmpresa: activeEmpresa,
          userId: userId,
          productoNombre: productoNombre,
          precioUnitario: precioUnitario,
          tallaNombre: tallaNombre,
          colorNombre: colorNombre,
          codigoHex: codigoHex,
          imagenUrl: imagenUrl,
        );
        notifyListeners();
        return true;
      } else {
        _error = e.response?.data?['detail'] ?? 'Stock insuficiente o error al agregar.';
      }
      notifyListeners();
      return false;
    } catch (_) {
      _error = 'No se pudo agregar a la bolsa.';
      notifyListeners();
      return false;
    } finally {
      _cargando = false;
      notifyListeners();
    }
  }

  Future<void> _aplicarAgregarItemOffline({
    required int idVariante,
    required int cantidad,
    required int activeEmpresa,
    required int userId,
    String? productoNombre,
    double? precioUnitario,
    String? tallaNombre,
    String? colorNombre,
    String? codigoHex,
    String? imagenUrl,
  }) async {
    await _syncCoordinator.enqueueOperation(
      kind: 'CART_ADD_ITEM',
      tenantId: activeEmpresa,
      payload: {
        'id_variante': idVariante,
        'cantidad': cantidad,
        'id_empresa': activeEmpresa,
      },
    );

    // Actualizar borrador en memoria y base de datos local
    final currentItems = List<ItemCarritoModel>.from(_carrito?.items ?? []);
    final idx = currentItems.indexWhere((it) => it.idVariante == idVariante);
    final pUnit = precioUnitario ?? 0.0;

    if (idx >= 0) {
      final existing = currentItems[idx];
      existing.cantidad += cantidad;
      existing.subtotal = existing.cantidad * existing.precioUnitario;
    } else {
      currentItems.add(ItemCarritoModel(
        idDetalleCarrito: -DateTime.now().millisecondsSinceEpoch,
        idVariante: idVariante,
        idProducto: 0,
        productoNombre: productoNombre ?? 'Prenda agregada offline',
        tallaNombre: tallaNombre ?? '',
        colorNombre: colorNombre ?? '',
        codigoHex: codigoHex ?? '#000000',
        cantidad: cantidad,
        precioUnitario: pUnit,
        subtotal: cantidad * pUnit,
        stockDisponible: 99,
        disponible: true,
        imagenUrl: imagenUrl,
        advertenciaStock: 'Operación guardada localmente. Sujeta a confirmación de stock.',
      ));
    }

    final totalItems = currentItems.fold(0, (sum, i) => sum + i.cantidad);
    final subtotal = currentItems.fold(0.0, (sum, i) => sum + i.subtotal);

    _carrito = CarritoModel(
      idCarrito: _carrito?.idCarrito ?? 0,
      idEmpresa: activeEmpresa,
      nombreEmpresa: _carrito?.nombreEmpresa ?? _tenantManager.nombreTiendaActiva,
      items: currentItems,
      totalItems: totalItems,
      subtotal: subtotal,
      descuento: _carrito?.descuento ?? 0.0,
      total: subtotal,
      puedeContinuarCompra: true,
    );

    await _dbHelper.saveCartDraft(activeEmpresa, userId, currentItems);
    _error = 'Prenda guardada localmente (modo sin conexión). Se sincronizará al reconectar.';
  }

  Future<void> actualizarCantidad({
    required int idDetalleCarrito,
    required int nuevaCantidad,
    int? idEmpresa,
  }) async {
    final activeEmpresa = idEmpresa ?? _carrito?.idEmpresa ?? (await TokenStorage.getEmpresaId()) ?? 1;
    final userId = (await TokenStorage.getUsuario())?['id_usuario'] as int? ?? 1;

    if (ConnectivityService().isOffline) {
      await _aplicarActualizarCantidadOffline(idDetalleCarrito, nuevaCantidad, activeEmpresa, userId);
      notifyListeners();
      return;
    }

    try {
      final body = <String, dynamic>{
        'cantidad': nuevaCantidad,
        if (idEmpresa != null) 'id_empresa': idEmpresa,
      };

      final res = await _dio.put(
        '/api/carrito/items/$idDetalleCarrito',
        data: body,
      );

      if (res.data['success'] == true && res.data['data'] != null) {
        final dataMap = Map<String, dynamic>.from(res.data['data'] as Map);
        _carrito = CarritoModel.fromJson(dataMap);
        await _dbHelper.saveCartDraft(activeEmpresa, userId, _carrito!.items);
        notifyListeners();
      }
    } on DioException catch (e) {
      if (_isNetworkError(e)) {
        await _aplicarActualizarCantidadOffline(idDetalleCarrito, nuevaCantidad, activeEmpresa, userId);
      } else {
        _error = e.response?.data?['detail'] ?? 'Error al actualizar cantidad.';
      }
      notifyListeners();
    }
  }

  Future<void> _aplicarActualizarCantidadOffline(
    int idDetalleCarrito,
    int nuevaCantidad,
    int activeEmpresa,
    int userId,
  ) async {
    await _syncCoordinator.enqueueOperation(
      kind: 'CART_UPDATE_QTY',
      tenantId: activeEmpresa,
      payload: {
        'id_detalle_carrito': idDetalleCarrito,
        'cantidad': nuevaCantidad,
        'id_empresa': activeEmpresa,
      },
    );

    if (_carrito != null) {
      final items = List<ItemCarritoModel>.from(_carrito!.items);
      final idx = items.indexWhere((it) => it.idDetalleCarrito == idDetalleCarrito);
      if (idx >= 0) {
        items[idx].cantidad = nuevaCantidad;
        items[idx].subtotal = nuevaCantidad * items[idx].precioUnitario;
        final subtotal = items.fold(0.0, (sum, i) => sum + i.subtotal);
        final totalItems = items.fold(0, (sum, i) => sum + i.cantidad);

        _carrito = CarritoModel(
          idCarrito: _carrito!.idCarrito,
          idEmpresa: activeEmpresa,
          nombreEmpresa: _carrito!.nombreEmpresa,
          items: items,
          totalItems: totalItems,
          subtotal: subtotal,
          descuento: _carrito!.descuento,
          total: subtotal,
          puedeContinuarCompra: true,
        );
        await _dbHelper.saveCartDraft(activeEmpresa, userId, items);
      }
    }
  }

  Future<void> eliminarItem({
    required int idDetalleCarrito,
    int? idEmpresa,
  }) async {
    final activeEmpresa = idEmpresa ?? _carrito?.idEmpresa ?? (await TokenStorage.getEmpresaId()) ?? 1;
    final userId = (await TokenStorage.getUsuario())?['id_usuario'] as int? ?? 1;

    if (ConnectivityService().isOffline) {
      await _aplicarEliminarItemOffline(idDetalleCarrito, activeEmpresa, userId);
      notifyListeners();
      return;
    }

    try {
      final params = <String, dynamic>{};
      if (idEmpresa != null) params['id_empresa'] = idEmpresa;

      final res = await _dio.delete(
        '/api/carrito/items/$idDetalleCarrito',
        queryParameters: params,
      );

      if (res.data['success'] == true && res.data['data'] != null) {
        final dataMap = Map<String, dynamic>.from(res.data['data'] as Map);
        _carrito = CarritoModel.fromJson(dataMap);
        await _dbHelper.saveCartDraft(activeEmpresa, userId, _carrito!.items);
        notifyListeners();
      }
    } on DioException catch (e) {
      if (_isNetworkError(e)) {
        await _aplicarEliminarItemOffline(idDetalleCarrito, activeEmpresa, userId);
      }
    } catch (_) {}
  }

  Future<void> _aplicarEliminarItemOffline(
    int idDetalleCarrito,
    int activeEmpresa,
    int userId,
  ) async {
    await _syncCoordinator.enqueueOperation(
      kind: 'CART_REMOVE_ITEM',
      tenantId: activeEmpresa,
      payload: {
        'id_detalle_carrito': idDetalleCarrito,
        'id_empresa': activeEmpresa,
      },
    );

    if (_carrito != null) {
      final items = List<ItemCarritoModel>.from(_carrito!.items);
      items.removeWhere((it) => it.idDetalleCarrito == idDetalleCarrito);
      final subtotal = items.fold(0.0, (sum, i) => sum + i.subtotal);
      final totalItems = items.fold(0, (sum, i) => sum + i.cantidad);

      _carrito = CarritoModel(
        idCarrito: _carrito!.idCarrito,
        idEmpresa: activeEmpresa,
        nombreEmpresa: _carrito!.nombreEmpresa,
        items: items,
        totalItems: totalItems,
        subtotal: subtotal,
        descuento: _carrito!.descuento,
        total: subtotal,
        puedeContinuarCompra: true,
      );
      await _dbHelper.saveCartDraft(activeEmpresa, userId, items);
    }
  }

  Future<void> vaciarCarrito({int? idEmpresa}) async {
    final activeEmpresa = idEmpresa ?? _carrito?.idEmpresa ?? (await TokenStorage.getEmpresaId()) ?? 1;
    final userId = (await TokenStorage.getUsuario())?['id_usuario'] as int? ?? 1;

    if (ConnectivityService().isOffline) {
      await _aplicarVaciarCarritoOffline(activeEmpresa, userId);
      notifyListeners();
      return;
    }

    try {
      final params = <String, dynamic>{};
      if (idEmpresa != null) params['id_empresa'] = idEmpresa;

      final res = await _dio.delete(
        '/api/carrito/vaciar',
        queryParameters: params,
      );

      if (res.data['success'] == true && res.data['data'] != null) {
        final dataMap = Map<String, dynamic>.from(res.data['data'] as Map);
        _carrito = CarritoModel.fromJson(dataMap);
        await _dbHelper.clearCartDraft(activeEmpresa, userId);
        notifyListeners();
      }
    } on DioException catch (e) {
      if (_isNetworkError(e)) {
        await _aplicarVaciarCarritoOffline(activeEmpresa, userId);
      }
    } catch (_) {}
  }

  Future<void> _aplicarVaciarCarritoOffline(int activeEmpresa, int userId) async {
    await _syncCoordinator.enqueueOperation(
      kind: 'CART_CLEAR',
      tenantId: activeEmpresa,
      payload: {'id_empresa': activeEmpresa},
    );

    _carrito = CarritoModel(
      idCarrito: 0,
      idEmpresa: activeEmpresa,
      nombreEmpresa: _tenantManager.nombreTiendaActiva,
      items: [],
      totalItems: 0,
      subtotal: 0.0,
      descuento: 0.0,
      total: 0.0,
      puedeContinuarCompra: true,
    );
    await _dbHelper.clearCartDraft(activeEmpresa, userId);
  }
}
