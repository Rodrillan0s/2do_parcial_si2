import 'package:dio/dio.dart';
import 'package:flutter/material.dart';
import '../../services/api_client.dart';
import '../../services/catalogo_service.dart';
import '../../services/token_storage.dart';
import '../database/database_helper.dart';

class TenantContextManager extends ChangeNotifier {
  static final TenantContextManager _instance = TenantContextManager._internal();
  factory TenantContextManager() => _instance;
  TenantContextManager._internal();

  final Dio _dio = ApiClient.dio;
  final DatabaseHelper _dbHelper = DatabaseHelper();

  TenantModel? _tenantActual;
  SucursalContextModel? _sucursalActual;
  List<TenantModel> _tenantsDisponibles = [];
  List<SucursalContextModel> _sucursalesDisponibles = [];
  bool _cargando = false;
  String? _error;
  DateTime? _ultimaActualizacion;

  TenantModel? get tenantActual => _tenantActual;
  SucursalContextModel? get sucursalActual => _sucursalActual;
  List<TenantModel> get tenantsDisponibles => _tenantsDisponibles;
  List<SucursalContextModel> get sucursalesDisponibles => _sucursalesDisponibles;
  bool get cargando => _cargando;
  String? get error => _error;
  DateTime? get ultimaActualizacion => _ultimaActualizacion;

  bool get tieneTiendaSeleccionada => _tenantActual != null;
  int? get idEmpresaActiva => _tenantActual?.idEmpresa;
  String get nombreTiendaActiva => _tenantActual?.nombreEmpresa ?? 'Aurora Store';
  String? get logoTiendaActiva => _tenantActual?.logo;
  String? get ciudadTiendaActiva => _tenantActual?.ciudad;

  Future<void> inicializar() async {
    _cargando = true;
    _error = null;
    notifyListeners();

    try {
      // 1. Cargar caché local inmediato desde SQLite (para modo offline instantáneo)
      final tenantsLocales = await _dbHelper.getTenants();
      if (tenantsLocales.isNotEmpty) {
        _tenantsDisponibles = tenantsLocales;
        final savedEmpresaId = await TokenStorage.getEmpresaId();
        if (savedEmpresaId != null) {
          _tenantActual = _tenantsDisponibles.firstWhere(
            (t) => t.idEmpresa == savedEmpresaId,
            orElse: () => _tenantsDisponibles.first,
          );
        } else {
          _tenantActual = _tenantsDisponibles.first;
        }
        notifyListeners();
      }

      // 2. Intentar actualizar desde el servidor remoto
      await recargarTenantsRemotos();
    } catch (e) {
      // Si falla la red, el estado local de SQLite ya quedó cargado
      _error = 'Modo sin conexión activo';
    } finally {
      _cargando = false;
      notifyListeners();
    }
  }

  Future<void> recargarTenantsRemotos() async {
    try {
      final res = await _dio.get('/api/catalogo/tenants');
      if (res.data['success'] == true && res.data['data'] != null) {
        final list = (res.data['data'] as List<dynamic>)
            .map((e) => TenantModel.fromJson(Map<String, dynamic>.from(e)))
            .toList();

        _tenantsDisponibles = list;
        _ultimaActualizacion = DateTime.now();

        // Persistir en SQLite para futuras sesiones offline
        await _dbHelper.saveTenants(list);

        final savedEmpresaId = await TokenStorage.getEmpresaId();
        if (savedEmpresaId != null) {
          _tenantActual = _tenantsDisponibles.firstWhere(
            (t) => t.idEmpresa == savedEmpresaId,
            orElse: () => _tenantsDisponibles.isNotEmpty ? _tenantsDisponibles.first : list.first,
          );
        } else if (_tenantsDisponibles.isNotEmpty && _tenantActual == null) {
          _tenantActual = _tenantsDisponibles.first;
          await TokenStorage.saveEmpresaId(_tenantActual!.idEmpresa);
        }

        // Cargar sucursales del tenant seleccionado
        if (_tenantActual != null) {
          await cargarSucursalesTenant(_tenantActual!.idEmpresa);
        }

        _error = null;
        notifyListeners();
      }
    } catch (e) {
      // Continúa con la copia de SQLite
    }
  }

  Future<void> cargarSucursalesTenant(int idEmpresa) async {
    try {
      final res = await _dio.get('/api/pedidos/sucursales', queryParameters: {'id_empresa': idEmpresa});
      if (res.data['success'] == true && res.data['data'] != null) {
        final raw = res.data['data'] as List<dynamic>;
        _sucursalesDisponibles = raw.map((s) => SucursalContextModel(
          idSucursal: s['id_sucursal'] ?? 0,
          idEmpresa: idEmpresa,
          nombre: s['nombre'] ?? '',
          direccion: s['direccion'] ?? '',
        )).toList();

        final savedSucId = await TokenStorage.getSucursalId();
        if (savedSucId != null) {
          _sucursalActual = _sucursalesDisponibles.firstWhere(
            (s) => s.idSucursal == savedSucId,
            orElse: () => _sucursalesDisponibles.first,
          );
        } else if (_sucursalesDisponibles.isNotEmpty) {
          _sucursalActual = _sucursalesDisponibles.first;
        }
        notifyListeners();
      }
    } catch (_) {
      // Ignorar si está offline
    }
  }

  Future<void> seleccionarTienda(TenantModel tenant) async {
    if (_tenantActual?.idEmpresa == tenant.idEmpresa) return;

    _tenantActual = tenant;
    _sucursalActual = null;
    _sucursalesDisponibles = [];

    await TokenStorage.saveEmpresaId(tenant.idEmpresa);
    await TokenStorage.clearSucursalContext();

    notifyListeners();

    // Cargar sucursales de la nueva tienda
    await cargarSucursalesTenant(tenant.idEmpresa);
    notifyListeners();
  }

  Future<void> seleccionarTenant(TenantModel tenant) => seleccionarTienda(tenant);

  Future<void> seleccionarSucursal(SucursalContextModel? sucursal) async {
    if (sucursal != null && sucursal.idEmpresa != _tenantActual?.idEmpresa) {
      return;
    }
    _sucursalActual = sucursal;
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
}
