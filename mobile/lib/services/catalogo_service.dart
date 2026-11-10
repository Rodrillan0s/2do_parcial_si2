import 'package:dio/dio.dart';
import 'package:flutter/foundation.dart';
import 'api_client.dart';
import 'token_storage.dart';
import '../core/database/database_helper.dart';

class TenantModel {
  final int idEmpresa;
  final String nombreEmpresa;
  final String? razonSocial;
  final String? logo;
  final String? ciudad;
  final String? direccionFiscal;

  TenantModel({
    required this.idEmpresa,
    required this.nombreEmpresa,
    this.razonSocial,
    this.logo,
    this.ciudad,
    this.direccionFiscal,
  });

  factory TenantModel.fromJson(Map<String, dynamic> json) {
    return TenantModel(
      idEmpresa: json['id_empresa'] ?? 0,
      nombreEmpresa: json['nombre_empresa'] ?? '',
      razonSocial: json['razon_social'],
      logo: json['logo'],
      ciudad: json['ciudad'],
      direccionFiscal: json['direccion_fiscal'],
    );
  }
}

class CategoriaFiltroModel {
  final int idCategoria;
  final String nombre;
  final int totalPrendas;

  CategoriaFiltroModel({
    required this.idCategoria,
    required this.nombre,
    required this.totalPrendas,
  });

  factory CategoriaFiltroModel.fromJson(Map<String, dynamic> json) {
    return CategoriaFiltroModel(
      idCategoria: json['id_categoria'] ?? 0,
      nombre: json['nombre'] ?? '',
      totalPrendas: json['total_prendas'] ?? 0,
    );
  }
}

class TallaFiltroModel {
  final int idTalla;
  final String nombre;

  TallaFiltroModel({required this.idTalla, required this.nombre});

  factory TallaFiltroModel.fromJson(Map<String, dynamic> json) {
    return TallaFiltroModel(
      idTalla: json['id_talla'] ?? 0,
      nombre: json['nombre'] ?? '',
    );
  }
}

class ColorFiltroModel {
  final int idColor;
  final String nombre;
  final String codigoHex;

  ColorFiltroModel({
    required this.idColor,
    required this.nombre,
    required this.codigoHex,
  });

  factory ColorFiltroModel.fromJson(Map<String, dynamic> json) {
    return ColorFiltroModel(
      idColor: json['id_color'] ?? 0,
      nombre: json['nombre'] ?? '',
      codigoHex: json['codigo_hex'] ?? '#000000',
    );
  }
}

class FiltrosCatalogoModel {
  final List<CategoriaFiltroModel> categorias;
  final List<TallaFiltroModel> tallas;
  final List<ColorFiltroModel> colores;
  final List<String> temporadas;
  final List<String> colecciones;
  final double? precioMin;
  final double? precioMax;

  FiltrosCatalogoModel({
    required this.categorias,
    required this.tallas,
    required this.colores,
    required this.temporadas,
    required this.colecciones,
    this.precioMin,
    this.precioMax,
  });

  factory FiltrosCatalogoModel.fromJson(Map<String, dynamic> json) {
    return FiltrosCatalogoModel(
      categorias: (json['categorias'] as List<dynamic>?)
              ?.map((e) => CategoriaFiltroModel.fromJson(e))
              .toList() ??
          [],
      tallas: (json['tallas'] as List<dynamic>?)
              ?.map((e) => TallaFiltroModel.fromJson(e))
              .toList() ??
          [],
      colores: (json['colores'] as List<dynamic>?)
              ?.map((e) => ColorFiltroModel.fromJson(e))
              .toList() ??
          [],
      temporadas: (json['temporadas'] as List<dynamic>?)
              ?.map((e) => e.toString())
              .toList() ??
          [],
      colecciones: (json['colecciones'] as List<dynamic>?)
              ?.map((e) => e.toString())
              .toList() ??
          [],
      precioMin: json['precio_min'] != null
          ? double.tryParse(json['precio_min'].toString())
          : null,
      precioMax: json['precio_max'] != null
          ? double.tryParse(json['precio_max'].toString())
          : null,
    );
  }
}

class PrendaModel {
  final int idProducto;
  final int idEmpresa;
  final int idCategoria;
  final String categoriaNombre;
  final String? codigoProducto;
  final String nombre;
  final String descripcion;
  final String marca;
  final String genero;
  final double precio;
  final Map<String, dynamic>? promocion;
  final String estadoStock;
  final int stockDisponibleCatalogo;
  final String? imagenPrincipal;
  final int totalImagenes;
  final int totalVariantes;
  final List<Map<String, dynamic>> tallasDisponibles;
  final List<Map<String, dynamic>> coloresDisponibles;
  final bool tieneRa;
  final String? modelo2dUrl;
  final String? tipoPrendaRa;

  PrendaModel({
    required this.idProducto,
    required this.idEmpresa,
    required this.idCategoria,
    required this.categoriaNombre,
    this.codigoProducto,
    required this.nombre,
    required this.descripcion,
    required this.marca,
    required this.genero,
    required this.precio,
    this.promocion,
    this.estadoStock = 'DISPONIBLE',
    this.stockDisponibleCatalogo = 0,
    this.imagenPrincipal,
    this.totalImagenes = 0,
    this.totalVariantes = 0,
    this.tallasDisponibles = const [],
    this.coloresDisponibles = const [],
    this.tieneRa = false,
    this.modelo2dUrl,
    this.tipoPrendaRa,
  });

  factory PrendaModel.fromJson(Map<String, dynamic> json) {
    return PrendaModel(
      idProducto: json['id_producto'] ?? 0,
      idEmpresa: json['id_empresa'] ?? 0,
      idCategoria: json['id_categoria'] ?? 0,
      categoriaNombre: json['categoria_nombre'] ?? '',
      codigoProducto: json['codigo_producto'],
      nombre: json['nombre'] ?? '',
      descripcion: json['descripcion'] ?? '',
      marca: json['marca'] ?? '',
      genero: json['genero'] ?? '',
      precio: (json['precio'] != null)
          ? double.tryParse(json['precio'].toString()) ?? 0.0
          : 0.0,
      promocion: json['promocion'] is Map
          ? Map<String, dynamic>.from(json['promocion'] as Map)
          : null,
      estadoStock: json['estado_stock']?.toString() ?? 'DISPONIBLE',
      stockDisponibleCatalogo:
          int.tryParse(json['stock_disponible_catalogo']?.toString() ?? '') ??
              0,
      imagenPrincipal: json['imagen_principal'],
      totalImagenes: json['total_imagenes'] ?? 0,
      totalVariantes: json['total_variantes'] ?? 0,
      tallasDisponibles: (json['tallas_disponibles'] as List<dynamic>?)
              ?.map((e) => Map<String, dynamic>.from(e as Map))
              .toList() ??
          [],
      coloresDisponibles: (json['colores_disponibles'] as List<dynamic>?)
              ?.map((e) => Map<String, dynamic>.from(e as Map))
              .toList() ??
          [],
      tieneRa: json['tiene_ra'] == true,
      modelo2dUrl: json['modelo_2d_url'],
      tipoPrendaRa: json['tipo_prenda_ra'],
    );
  }
}

class VarianteModel {
  final int idVariante;
  final int idTalla;
  final String tallaNombre;
  final int idColor;
  final String colorNombre;
  final String codigoHex;
  final String? sku;
  final double precio;

  VarianteModel({
    required this.idVariante,
    required this.idTalla,
    required this.tallaNombre,
    required this.idColor,
    required this.colorNombre,
    required this.codigoHex,
    this.sku,
    required this.precio,
  });

  factory VarianteModel.fromJson(Map<String, dynamic> json) {
    return VarianteModel(
      idVariante: json['id_variante'] ?? 0,
      idTalla: json['id_talla'] ?? 0,
      tallaNombre: json['talla_nombre'] ?? '',
      idColor: json['id_color'] ?? 0,
      colorNombre: json['color_nombre'] ?? '',
      codigoHex: json['codigo_hex'] ?? '#000000',
      sku: json['sku'],
      precio: (json['precio'] != null)
          ? double.tryParse(json['precio'].toString()) ?? 0.0
          : 0.0,
    );
  }
}

class DetallePrendaModel {
  final int idProducto;
  final int idEmpresa;
  final String empresaNombre;
  final int idCategoria;
  final String categoriaNombre;
  final String? codigoProducto;
  final String nombre;
  final String descripcion;
  final String marca;
  final String genero;
  final double precio;
  final String? imagenPrincipal;
  final List<String> imagenes;
  final List<VarianteModel> variantes;
  final List<Map<String, dynamic>> tallas;
  final List<Map<String, dynamic>> colores;
  final int stockTotalGeneral;
  final bool hayStockDisponible;
  final bool permiteReserva;
  final bool permiteCompra;
  final bool tieneRa;
  final String? modelo2dUrl;
  final String? modelo3dUrl;
  final String? tipoPrendaRa;

  DetallePrendaModel({
    required this.idProducto,
    required this.idEmpresa,
    required this.empresaNombre,
    required this.idCategoria,
    required this.categoriaNombre,
    this.codigoProducto,
    required this.nombre,
    required this.descripcion,
    required this.marca,
    required this.genero,
    required this.precio,
    this.imagenPrincipal,
    required this.imagenes,
    required this.variantes,
    required this.tallas,
    required this.colores,
    required this.stockTotalGeneral,
    required this.hayStockDisponible,
    required this.permiteReserva,
    required this.permiteCompra,
    this.tieneRa = false,
    this.modelo2dUrl,
    this.modelo3dUrl,
    this.tipoPrendaRa,
  });

  factory DetallePrendaModel.fromJson(Map<String, dynamic> json) {
    final imagenesRaw = json['imagenes'] as List<dynamic>? ?? [];
    final imagenesList = <String>[];

    for (final img in imagenesRaw) {
      if (img is Map && img['imagen_url'] != null) {
        imagenesList.add(img['imagen_url'].toString());
      } else if (img is String) {
        imagenesList.add(img);
      }
    }

    if (imagenesList.isEmpty && json['imagen_principal'] != null) {
      imagenesList.add(json['imagen_principal'].toString());
    }

    return DetallePrendaModel(
      idProducto: json['id_producto'] ?? 0,
      idEmpresa: json['id_empresa'] ?? 0,
      empresaNombre: json['empresa_nombre'] ?? '',
      idCategoria: json['id_categoria'] ?? 0,
      categoriaNombre: json['categoria_nombre'] ?? '',
      codigoProducto: json['codigo_producto'],
      nombre: json['nombre'] ?? '',
      descripcion: json['descripcion'] ?? '',
      marca: json['marca'] ?? '',
      genero: json['genero'] ?? '',
      precio: (json['precio'] != null)
          ? double.tryParse(json['precio'].toString()) ?? 0.0
          : 0.0,
      imagenPrincipal: json['imagen_principal'],
      imagenes: imagenesList,
      variantes: (json['variantes'] as List<dynamic>?)
              ?.map((e) => VarianteModel.fromJson(Map<String, dynamic>.from(e)))
              .toList() ??
          [],
      tallas: (json['tallas'] as List<dynamic>?)
              ?.map((e) => Map<String, dynamic>.from(e as Map))
              .toList() ??
          [],
      colores: (json['colores'] as List<dynamic>?)
              ?.map((e) => Map<String, dynamic>.from(e as Map))
              .toList() ??
          [],
      stockTotalGeneral: json['stock_total_general'] ?? 0,
      hayStockDisponible: json['hay_stock_disponible'] ?? false,
      permiteReserva: json['permite_reserva'] ?? true,
      permiteCompra: json['permite_compra'] ?? true,
      tieneRa: json['tiene_ra'] == true,
      modelo2dUrl: json['modelo_2d_url'],
      modelo3dUrl: json['modelo_3d_url'] ?? json['modelo_ar_url'],
      tipoPrendaRa: json['tipo_prenda_ra'],
    );
  }
}

class DisponibilidadSucursalModel {
  final int idSucursal;
  final String nombre;
  final String direccion;
  final String? telefono;
  final String horario;
  final String? ciudad;
  final int stockDisponible;
  final bool disponible;
  final bool permiteReserva;
  final bool permiteCompra;

  DisponibilidadSucursalModel({
    required this.idSucursal,
    required this.nombre,
    required this.direccion,
    this.telefono,
    required this.horario,
    this.ciudad,
    required this.stockDisponible,
    required this.disponible,
    required this.permiteReserva,
    required this.permiteCompra,
  });

  factory DisponibilidadSucursalModel.fromJson(Map<String, dynamic> json) {
    return DisponibilidadSucursalModel(
      idSucursal: json['id_sucursal'] ?? 0,
      nombre: json['nombre'] ?? '',
      direccion: json['direccion'] ?? '',
      telefono: json['telefono']?.toString(),
      horario: json['horario'] ?? '09:00 - 20:00',
      ciudad: json['ciudad'],
      stockDisponible: json['stock_disponible'] ?? 0,
      disponible: json['disponible'] ?? false,
      permiteReserva: json['permite_reserva'] ?? true,
      permiteCompra: json['permite_compra'] ?? true,
    );
  }
}

class SucursalContextModel {
  final int idSucursal;
  final int idEmpresa;
  final String nombre;
  final String direccion;

  const SucursalContextModel({
    required this.idSucursal,
    required this.idEmpresa,
    required this.nombre,
    required this.direccion,
  });
}

class CatalogoService extends ChangeNotifier {
  final Dio _dio = ApiClient.dio;
  final DatabaseHelper _dbHelper = DatabaseHelper();

  List<TenantModel> _tenants = [];
  TenantModel? _tenantSeleccionado;
  SucursalContextModel? _sucursalSeleccionada;
  int? _sucursalPersistidaId;
  FiltrosCatalogoModel? _filtros;

  List<PrendaModel> _productos = [];
  int _totalProductos = 0;
  bool _cargando = false;
  String? _error;

  // Filtros aplicados
  String _busqueda = '';
  int? _categoriaId;
  int? _tallaId;
  int? _colorId;
  double? _precioMin;
  double? _precioMax;
  String? _orden;

  List<TenantModel> get tenants => _tenants;
  TenantModel? get tenantSeleccionado => _tenantSeleccionado;
  SucursalContextModel? get sucursalSeleccionada => _sucursalSeleccionada;
  int? get sucursalPersistidaId => _sucursalPersistidaId;
  FiltrosCatalogoModel? get filtros => _filtros;
  List<PrendaModel> get productos => _productos;
  int get totalProductos => _totalProductos;
  bool get cargando => _cargando;
  String? get error => _error;

  String get busqueda => _busqueda;
  int? get categoriaId => _categoriaId;
  int? get tallaId => _tallaId;
  int? get colorId => _colorId;
  double? get precioMin => _precioMin;
  double? get precioMax => _precioMax;
  String? get orden => _orden;

  CatalogoService() {
    inicializar();
  }

  Future<void> inicializar() async {
    await cargarTenants();
    if (_tenantSeleccionado != null) {
      await cargarFiltros();
      await cargarProductos();
    }
  }

  Future<void> cargarTenants() async {
    try {
      final res = await _dio.get('/api/catalogo/tenants');
      if (res.data['success'] == true && res.data['data'] != null) {
        _tenants = (res.data['data'] as List<dynamic>)
            .map((e) => TenantModel.fromJson(e))
            .toList();
        final savedEmpresaId = await TokenStorage.getEmpresaId();
        _sucursalPersistidaId = await TokenStorage.getSucursalId();
        if (savedEmpresaId != null) {
          for (final tenant in _tenants) {
            if (tenant.idEmpresa == savedEmpresaId) {
              _tenantSeleccionado = tenant;
              break;
            }
          }
        }
        notifyListeners();
      }
    } catch (_) {}
  }

  Future<void> seleccionarTenant(TenantModel tenant) async {
    if (_tenantSeleccionado?.idEmpresa != tenant.idEmpresa) {
      final empresaAnterior = _tenantSeleccionado?.idEmpresa;
      _tenantSeleccionado = tenant;
      _sucursalSeleccionada = null;
      await TokenStorage.saveEmpresaId(tenant.idEmpresa);
      await TokenStorage.clearSucursalContext();
      if (empresaAnterior != null) {
        notifyListeners();
      }
      cargarFiltros();
      cargarProductos();
      notifyListeners();
    }
  }

  Future<void> seleccionarSucursal(SucursalContextModel? sucursal) async {
    if (sucursal != null &&
        sucursal.idEmpresa != _tenantSeleccionado?.idEmpresa) {
      return;
    }
    _sucursalSeleccionada = sucursal;
    _sucursalPersistidaId = sucursal?.idSucursal;
    if (sucursal == null) {
      await TokenStorage.clearSucursalContext();
    } else {
      await TokenStorage.saveSucursalContext(
        idEmpresa: sucursal.idEmpresa,
        idSucursal: sucursal.idSucursal,
      );
    }
    notifyListeners();
  }

  Future<void> cargarFiltros() async {
    try {
      final queryParams = <String, dynamic>{};
      if (_tenantSeleccionado != null) {
        queryParams['id_empresa'] = _tenantSeleccionado!.idEmpresa;
      }

      final res =
          await _dio.get('/api/catalogo/filtros', queryParameters: queryParams);
      if (res.data['success'] == true && res.data['data'] != null) {
        _filtros = FiltrosCatalogoModel.fromJson(res.data['data']);
        notifyListeners();
      }
    } catch (_) {}
  }

  Future<void> cargarProductos() async {
    _cargando = true;
    _error = null;
    notifyListeners();

    try {
      final params = <String, dynamic>{
        'limit': 50,
        'offset': 0,
      };

      if (_tenantSeleccionado != null) {
        params['id_empresa'] = _tenantSeleccionado!.idEmpresa;
      }
      if (_busqueda.trim().isNotEmpty) {
        params['busqueda'] = _busqueda.trim();
      }
      if (_categoriaId != null) {
        params['id_categoria'] = _categoriaId;
      }
      if (_tallaId != null) {
        params['id_talla'] = _tallaId;
      }
      if (_colorId != null) {
        params['id_color'] = _colorId;
      }
      if (_precioMin != null) {
        params['precio_min'] = _precioMin;
      }
      if (_precioMax != null) {
        params['precio_max'] = _precioMax;
      }
      if (_orden != null && _orden!.isNotEmpty) {
        params['orden'] = _orden;
      }

      final res =
          await _dio.get('/api/catalogo/productos', queryParameters: params);
      if (res.data['success'] == true && res.data['data'] != null) {
        final list = (res.data['data'] as List<dynamic>)
            .map((e) => Map<String, dynamic>.from(e as Map))
            .toList();
        _productos = list.map((e) => PrendaModel.fromJson(e)).toList();
        _totalProductos = res.data['total'] ?? _productos.length;

        // Persistir en SQLite para navegación offline
        final activeTenantId = _tenantSeleccionado?.idEmpresa ??
            (list.isNotEmpty ? list.first['id_empresa'] as int? ?? 1 : 1);
        await _dbHelper.saveProducts(activeTenantId, _productos);
      } else {
        _productos = [];
        _totalProductos = 0;
      }
    } on DioException catch (e) {
      // Fallback a caché local SQLite si no hay conexión
      final activeTenantId = _tenantSeleccionado?.idEmpresa ?? 1;
      final cached = await _dbHelper.getProducts(
        activeTenantId,
        categoriaId: _categoriaId,
        busqueda: _busqueda.trim().isNotEmpty ? _busqueda.trim() : null,
      );
      if (cached.isNotEmpty) {
        _productos = cached;
        _totalProductos = _productos.length;
        _error = null;
      } else {
        _error = e.response?.data?['detail'] ??
            'Error al cargar catálogo de productos.';
        _productos = [];
      }
    } catch (e) {
      final activeTenantId = _tenantSeleccionado?.idEmpresa ?? 1;
      final cached = await _dbHelper.getProducts(
        activeTenantId,
        categoriaId: _categoriaId,
        busqueda: _busqueda.trim().isNotEmpty ? _busqueda.trim() : null,
      );
      if (cached.isNotEmpty) {
        _productos = cached;
        _totalProductos = _productos.length;
        _error = null;
      } else {
        _error = 'Error de conexión con el catálogo.';
        _productos = [];
      }
    } finally {
      _cargando = false;
      notifyListeners();
    }
  }

  void aplicarFiltros({
    String? busqueda,
    int? categoriaId,
    int? tallaId,
    int? colorId,
    double? precioMin,
    double? precioMax,
    String? orden,
  }) {
    if (busqueda != null) _busqueda = busqueda;
    _categoriaId = categoriaId;
    _tallaId = tallaId;
    _colorId = colorId;
    _precioMin = precioMin;
    _precioMax = precioMax;
    _orden = orden;
    cargarProductos();
  }

  void limpiarFiltros() {
    _busqueda = '';
    _categoriaId = null;
    _tallaId = null;
    _colorId = null;
    _precioMin = null;
    _precioMax = null;
    _orden = null;
    cargarProductos();
  }

  Future<DetallePrendaModel> obtenerDetalleProducto(int idProducto) async {
    final activeTenantId = _tenantSeleccionado?.idEmpresa ?? 1;
    try {
      final params = <String, dynamic>{};
      if (_tenantSeleccionado != null) {
        params['id_empresa'] = _tenantSeleccionado!.idEmpresa;
      }

      final res = await _dio.get('/api/catalogo/productos/$idProducto',
          queryParameters: params);
      if (res.data['success'] == true && res.data['data'] != null) {
        final dataMap = Map<String, dynamic>.from(res.data['data'] as Map);
        final detail = DetallePrendaModel.fromJson(dataMap);
        await _dbHelper.saveProductDetail(activeTenantId, idProducto, detail);
        return detail;
      }
      throw Exception(res.data['message'] ?? 'No se pudo cargar la prenda.');
    } on DioException catch (e) {
      final cached = await _dbHelper.getProductDetail(activeTenantId, idProducto);
      if (cached != null) {
        return cached;
      }
      final msg = e.response?.data?['detail'] ??
          'Error al consultar detalle de la prenda.';
      throw Exception(msg.toString());
    } catch (e) {
      final cached = await _dbHelper.getProductDetail(activeTenantId, idProducto);
      if (cached != null) {
        return cached;
      }
      rethrow;
    }
  }

  Future<List<DisponibilidadSucursalModel>> consultarDisponibilidadVariante(
      int idVariante) async {
    try {
      final params = <String, dynamic>{};
      if (_tenantSeleccionado != null) {
        params['id_empresa'] = _tenantSeleccionado!.idEmpresa;
      }

      final res = await _dio.get(
        '/api/catalogo/variantes/$idVariante/disponibilidad',
        queryParameters: params,
      );

      if (res.data['success'] == true && res.data['data'] != null) {
        final sucursalesRaw =
            res.data['data']['sucursales'] as List<dynamic>? ?? [];
        return sucursalesRaw
            .map((e) => DisponibilidadSucursalModel.fromJson(
                Map<String, dynamic>.from(e)))
            .toList();
      }
      return [];
    } catch (_) {
      return [];
    }
  }
}
