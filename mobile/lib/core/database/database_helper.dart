import 'dart:convert';
import 'package:flutter/foundation.dart';
import 'package:path/path.dart' as p;
import 'package:sqflite/sqflite.dart';
import '../../services/catalogo_service.dart';
import '../../services/carrito_service.dart';
import '../../services/reserva_service.dart';

class DatabaseHelper {
  static final DatabaseHelper _instance = DatabaseHelper._internal();
  factory DatabaseHelper() => _instance;
  DatabaseHelper._internal();

  static Database? _database;

  Future<Database> get database async {
    if (_database != null) return _database!;
    _database = await _initDatabase();
    return _database!;
  }

  /// Permite inyectar una base de datos en pruebas (ej: ffi / in-memory).
  @visibleForTesting
  static void setMockDatabase(Database? db) {
    _database = db;
  }

  Future<Database> _initDatabase() async {
    final dbPath = await getDatabasesPath();
    final path = p.join(dbPath, 'aurora_store_mobile.db');

    return await openDatabase(
      path,
      version: 1,
      onCreate: _onCreate,
    );
  }

  Future<void> _onCreate(Database db, int version) async {
    // 1. Tiendas / Tenants almacenados localmente
    await db.execute('''
      CREATE TABLE local_tenants (
        id_empresa INTEGER PRIMARY KEY,
        nombre_empresa TEXT NOT NULL,
        slug TEXT,
        razon_social TEXT,
        logo TEXT,
        ciudad TEXT,
        direccion_fiscal TEXT,
        updated_at TEXT NOT NULL
      );
    ''');

    // 2. Catálogo de productos particionado por id_empresa
    await db.execute('''
      CREATE TABLE local_products (
        id_producto INTEGER NOT NULL,
        id_empresa INTEGER NOT NULL,
        id_categoria INTEGER,
        categoria_nombre TEXT,
        codigo_producto TEXT,
        nombre TEXT NOT NULL,
        descripcion TEXT,
        marca TEXT,
        genero TEXT,
        precio REAL NOT NULL,
        estado_stock TEXT,
        stock_disponible_catalogo INTEGER,
        imagen_principal TEXT,
        tiene_ra INTEGER DEFAULT 0,
        raw_json TEXT NOT NULL,
        updated_at TEXT NOT NULL,
        PRIMARY KEY (id_producto, id_empresa)
      );
    ''');
    await db.execute('CREATE INDEX idx_products_empresa ON local_products (id_empresa);');
    await db.execute('CREATE INDEX idx_products_categoria ON local_products (id_empresa, id_categoria);');

    // 3. Detalles de productos en caché offline particionado por id_empresa
    await db.execute('''
      CREATE TABLE local_product_details (
        id_producto INTEGER NOT NULL,
        id_empresa INTEGER NOT NULL,
        raw_json TEXT NOT NULL,
        updated_at TEXT NOT NULL,
        PRIMARY KEY (id_producto, id_empresa)
      );
    ''');

    // 4. Borrador local de carrito particionado por id_empresa e id_usuario
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

    // 5. Cola de operaciones pendientes de sincronización con UUID estable (POST /api/sync/lote)
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
    await db.execute('CREATE INDEX idx_sync_status ON local_sync_operations (status);');
    await db.execute('CREATE INDEX idx_sync_user_empresa ON local_sync_operations (id_usuario, id_empresa);');

    // 6. Recibos durables de confirmación de sincronización
    await db.execute('''
      CREATE TABLE local_sync_receipts (
        operation_id TEXT PRIMARY KEY,
        id_empresa INTEGER NOT NULL,
        id_usuario INTEGER NOT NULL,
        response_json TEXT NOT NULL,
        created_at TEXT NOT NULL
      );
    ''');

    // 7. Reservas locales (incluyendo borradores offline)
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

    // 8. Devoluciones del cliente en caché local
    await db.execute('''
      CREATE TABLE local_devoluciones (
        id_devolucion INTEGER NOT NULL,
        id_empresa INTEGER NOT NULL,
        id_usuario INTEGER NOT NULL,
        id_venta INTEGER NOT NULL,
        codigo_venta TEXT,
        motivo TEXT NOT NULL,
        tipo_resolucion TEXT,
        estado TEXT NOT NULL,
        monto_reembolso REAL DEFAULT 0,
        items_json TEXT,
        created_at TEXT NOT NULL,
        PRIMARY KEY (id_devolucion, id_empresa)
      );
    ''');
  }

  // ===========================================================================
  // MÉTODOS DE ACCESO MULTITENANT
  // ===========================================================================

  // --- TIENDAS / TENANTS ---
  Future<void> saveTenants(List<TenantModel> tenants) async {
    final db = await database;
    final batch = db.batch();
    final now = DateTime.now().toIso8601String();

    for (final t in tenants) {
      batch.insert(
        'local_tenants',
        {
          'id_empresa': t.idEmpresa,
          'nombre_empresa': t.nombreEmpresa,
          'slug': null,
          'razon_social': t.razonSocial,
          'logo': t.logo,
          'ciudad': t.ciudad,
          'direccion_fiscal': t.direccionFiscal,
          'updated_at': now,
        },
        conflictAlgorithm: ConflictAlgorithm.replace,
      );
    }
    await batch.commit(noResult: true);
  }

  Future<List<TenantModel>> getTenants() async {
    final db = await database;
    final rows = await db.query('local_tenants', orderBy: 'id_empresa ASC');
    return rows.map((r) => TenantModel.fromJson(r)).toList();
  }

  // --- CATÁLOGO DE PRODUCTOS (PARTICIONADO POR TENANT) ---
  Future<void> saveProducts(int idEmpresa, List<PrendaModel> products) async {
    final db = await database;
    final batch = db.batch();
    final now = DateTime.now().toIso8601String();

    // Reemplaza o actualiza productos de este tenant
    for (final p in products) {
      final rawMap = {
        'id_producto': p.idProducto,
        'id_empresa': idEmpresa,
        'id_categoria': p.idCategoria,
        'categoria_nombre': p.categoriaNombre,
        'codigo_producto': p.codigoProducto,
        'nombre': p.nombre,
        'descripcion': p.descripcion,
        'marca': p.marca,
        'genero': p.genero,
        'precio': p.precio,
        'promocion': p.promocion,
        'estado_stock': p.estadoStock,
        'stock_disponible_catalogo': p.stockDisponibleCatalogo,
        'imagen_principal': p.imagenPrincipal,
        'total_imagenes': p.totalImagenes,
        'total_variantes': p.totalVariantes,
        'tallas_disponibles': p.tallasDisponibles,
        'colores_disponibles': p.coloresDisponibles,
        'tiene_ra': p.tieneRa,
        'modelo_2d_url': p.modelo2dUrl,
        'tipo_prenda_ra': p.tipoPrendaRa,
      };

      batch.insert(
        'local_products',
        {
          'id_producto': p.idProducto,
          'id_empresa': idEmpresa,
          'id_categoria': p.idCategoria,
          'categoria_nombre': p.categoriaNombre,
          'codigo_producto': p.codigoProducto,
          'nombre': p.nombre,
          'descripcion': p.descripcion,
          'marca': p.marca,
          'genero': p.genero,
          'precio': p.precio,
          'estado_stock': p.estadoStock,
          'stock_disponible_catalogo': p.stockDisponibleCatalogo,
          'imagen_principal': p.imagenPrincipal,
          'tiene_ra': p.tieneRa ? 1 : 0,
          'raw_json': jsonEncode(rawMap),
          'updated_at': now,
        },
        conflictAlgorithm: ConflictAlgorithm.replace,
      );
    }
    await batch.commit(noResult: true);
  }

  Future<List<PrendaModel>> getProducts(
    int idEmpresa, {
    String? busqueda,
    int? categoriaId,
    double? precioMin,
    double? precioMax,
    String? orden,
  }) async {
    final db = await database;
    final whereClauses = <String>['id_empresa = ?'];
    final whereArgs = <dynamic>[idEmpresa];

    if (busqueda != null && busqueda.trim().isNotEmpty) {
      whereClauses.add('(nombre LIKE ? OR descripcion LIKE ? OR codigo_producto LIKE ?)');
      final term = '%${busqueda.trim()}%';
      whereArgs.addAll([term, term, term]);
    }

    if (categoriaId != null) {
      whereClauses.add('id_categoria = ?');
      whereArgs.add(categoriaId);
    }

    if (precioMin != null) {
      whereClauses.add('precio >= ?');
      whereArgs.add(precioMin);
    }

    if (precioMax != null) {
      whereClauses.add('precio <= ?');
      whereArgs.add(precioMax);
    }

    String orderBy = 'id_producto DESC';
    if (orden == 'precio_asc') {
      orderBy = 'precio ASC';
    } else if (orden == 'precio_desc') {
      orderBy = 'precio DESC';
    }

    final rows = await db.query(
      'local_products',
      where: whereClauses.join(' AND '),
      whereArgs: whereArgs,
      orderBy: orderBy,
      limit: 100,
    );

    return rows.map((r) {
      try {
        final map = jsonDecode(r['raw_json'] as String) as Map<String, dynamic>;
        return PrendaModel.fromJson(map);
      } catch (_) {
        return PrendaModel(
          idProducto: r['id_producto'] as int,
          idEmpresa: r['id_empresa'] as int,
          idCategoria: r['id_categoria'] as int? ?? 0,
          categoriaNombre: r['categoria_nombre'] as String? ?? '',
          codigoProducto: r['codigo_producto'] as String?,
          nombre: r['nombre'] as String? ?? '',
          descripcion: r['descripcion'] as String? ?? '',
          marca: r['marca'] as String? ?? '',
          genero: r['genero'] as String? ?? '',
          precio: (r['precio'] as num?)?.toDouble() ?? 0.0,
          imagenPrincipal: r['imagen_principal'] as String?,
          estadoStock: r['estado_stock'] as String? ?? 'DISPONIBLE',
          stockDisponibleCatalogo: r['stock_disponible_catalogo'] as int? ?? 0,
          tieneRa: (r['tiene_ra'] as int?) == 1,
        );
      }
    }).toList();
  }

  // --- DETALLES DE PRODUCTO ---
  Future<void> saveProductDetail(int idEmpresa, int idProducto, DetallePrendaModel detail) async {
    final db = await database;
    final now = DateTime.now().toIso8601String();

    final rawMap = {
      'id_producto': detail.idProducto,
      'id_empresa': idEmpresa,
      'empresa_nombre': detail.empresaNombre,
      'id_categoria': detail.idCategoria,
      'categoria_nombre': detail.categoriaNombre,
      'codigo_producto': detail.codigoProducto,
      'nombre': detail.nombre,
      'descripcion': detail.descripcion,
      'marca': detail.marca,
      'genero': detail.genero,
      'precio': detail.precio,
      'imagen_principal': detail.imagenPrincipal,
      'imagenes': detail.imagenes,
      'variantes': detail.variantes.map((v) => {
        'id_variante': v.idVariante,
        'id_talla': v.idTalla,
        'talla_nombre': v.tallaNombre,
        'id_color': v.idColor,
        'color_nombre': v.colorNombre,
        'codigo_hex': v.codigoHex,
        'sku': v.sku,
        'precio': v.precio,
      }).toList(),
      'tallas': detail.tallas,
      'colores': detail.colores,
      'stock_total_general': detail.stockTotalGeneral,
      'hay_stock_disponible': detail.hayStockDisponible,
      'permite_reserva': detail.permiteReserva,
      'permite_compra': detail.permiteCompra,
      'tiene_ra': detail.tieneRa,
      'modelo_2d_url': detail.modelo2dUrl,
      'tipo_prenda_ra': detail.tipoPrendaRa,
    };

    await db.insert(
      'local_product_details',
      {
        'id_producto': idProducto,
        'id_empresa': idEmpresa,
        'raw_json': jsonEncode(rawMap),
        'updated_at': now,
      },
      conflictAlgorithm: ConflictAlgorithm.replace,
    );
  }

  Future<DetallePrendaModel?> getProductDetail(int idEmpresa, int idProducto) async {
    final db = await database;
    final rows = await db.query(
      'local_product_details',
      where: 'id_empresa = ? AND id_producto = ?',
      whereArgs: [idEmpresa, idProducto],
      limit: 1,
    );

    if (rows.isEmpty) return null;
    try {
      final map = jsonDecode(rows.first['raw_json'] as String) as Map<String, dynamic>;
      return DetallePrendaModel.fromJson(map);
    } catch (_) {
      return null;
    }
  }

  // --- BORRADOR DE CARRITO (AISLADO POR TENANT Y USUARIO) ---
  Future<void> saveCartDraft(int idEmpresa, int idUsuario, List<ItemCarritoModel> items) async {
    final db = await database;
    await db.transaction((txn) async {
      // Elimina los ítems anteriores de este usuario en esta empresa
      await txn.delete(
        'local_cart_drafts',
        where: 'id_empresa = ? AND id_usuario = ?',
        whereArgs: [idEmpresa, idUsuario],
      );

      final now = DateTime.now().toIso8601String();
      for (final it in items) {
        await txn.insert(
          'local_cart_drafts',
          {
            'id_empresa': idEmpresa,
            'id_usuario': idUsuario,
            'id_variante': it.idVariante,
            'id_producto': it.idProducto,
            'producto_nombre': it.productoNombre,
            'talla_nombre': it.tallaNombre,
            'color_nombre': it.colorNombre,
            'codigo_hex': it.codigoHex,
            'precio_unitario': it.precioUnitario,
            'cantidad': it.cantidad,
            'imagen_url': it.imagenUrl,
            'updated_at': now,
          },
          conflictAlgorithm: ConflictAlgorithm.replace,
        );
      }
    });
  }

  Future<List<ItemCarritoModel>> getCartDraft(int idEmpresa, int idUsuario) async {
    final db = await database;
    final rows = await db.query(
      'local_cart_drafts',
      where: 'id_empresa = ? AND id_usuario = ?',
      whereArgs: [idEmpresa, idUsuario],
      orderBy: 'id_variante ASC',
    );

    return rows.map((r) {
      final cant = r['cantidad'] as int? ?? 1;
      final prec = (r['precio_unitario'] as num?)?.toDouble() ?? 0.0;
      return ItemCarritoModel(
        idDetalleCarrito: 0, // id temporal en borrador offline
        idVariante: r['id_variante'] as int,
        idProducto: r['id_producto'] as int,
        productoNombre: r['producto_nombre'] as String? ?? 'Prenda',
        tallaNombre: r['talla_nombre'] as String? ?? '',
        colorNombre: r['color_nombre'] as String? ?? '',
        codigoHex: r['codigo_hex'] as String? ?? '#000000',
        precioUnitario: prec,
        cantidad: cant,
        subtotal: cant * prec,
        stockDisponible: 99, // Stock offline no confirmado
        disponible: true,
        imagenUrl: r['imagen_url'] as String?,
        advertenciaStock: 'Precio y stock sujetos a confirmación con la tienda.',
      );
    }).toList();
  }

  Future<void> clearCartDraft(int idEmpresa, int idUsuario) async {
    final db = await database;
    await db.delete(
      'local_cart_drafts',
      where: 'id_empresa = ? AND id_usuario = ?',
      whereArgs: [idEmpresa, idUsuario],
    );
  }

  // --- COLA DE SINCRONIZACIÓN (/api/sync/lote) ---
  Future<void> enqueueSyncOperation({
    required String operationId,
    required int idEmpresa,
    required int idUsuario,
    int? idSucursal,
    required String kind,
    required Map<String, dynamic> payload,
  }) async {
    final db = await database;
    final now = DateTime.now().toUtc().toIso8601String();

    await db.insert(
      'local_sync_operations',
      {
        'operation_id': operationId,
        'id_empresa': idEmpresa,
        'id_usuario': idUsuario,
        'id_sucursal': idSucursal,
        'kind': kind,
        'payload_json': jsonEncode(payload),
        'status': 'pending',
        'retry_count': 0,
        'created_at': now,
        'updated_at': now,
      },
      conflictAlgorithm: ConflictAlgorithm.ignore,
    );
  }

  Future<List<Map<String, dynamic>>> getPendingSyncOperations({int? idEmpresa, int? idUsuario}) async {
    final db = await database;
    final where = <String>["status IN ('pending', 'failed_retryable')"];
    final args = <dynamic>[];

    if (idEmpresa != null) {
      where.add('id_empresa = ?');
      args.add(idEmpresa);
    }
    if (idUsuario != null) {
      where.add('id_usuario = ?');
      args.add(idUsuario);
    }

    final rows = await db.query(
      'local_sync_operations',
      where: where.join(' AND '),
      whereArgs: args,
      orderBy: 'created_at ASC',
    );
    return rows;
  }

  Future<void> markSyncOperationResult({
    required String operationId,
    required String status,
    String? conflictCode,
    String? message,
    Map<String, dynamic>? responseData,
  }) async {
    final db = await database;
    final now = DateTime.now().toUtc().toIso8601String();

    await db.update(
      'local_sync_operations',
      {
        'status': status,
        'conflict_code': conflictCode,
        'message': message,
        'updated_at': now,
      },
      where: 'operation_id = ?',
      whereArgs: [operationId],
    );

    if (status == 'synced' && responseData != null) {
      await db.insert(
        'local_sync_receipts',
        {
          'operation_id': operationId,
          'id_empresa': responseData['id_empresa'] ?? 0,
          'id_usuario': responseData['id_usuario'] ?? 0,
          'response_json': jsonEncode(responseData),
          'created_at': now,
        },
        conflictAlgorithm: ConflictAlgorithm.replace,
      );
    }
  }

  // --- RESERVAS LOCALES ---
  Future<void> saveLocalReservations(int idEmpresa, int idUsuario, List<ReservaModel> reservas) async {
    final db = await database;
    final batch = db.batch();
    final now = DateTime.now().toIso8601String();

    // Eliminar las que no sean borradores locales
    await db.delete(
      'local_reservations',
      where: 'id_empresa = ? AND id_usuario = ? AND is_offline_draft = 0',
      whereArgs: [idEmpresa, idUsuario],
    );

    for (final r in reservas) {
      batch.insert(
        'local_reservations',
        {
          'id_reserva_local': 'res_${r.idReserva}',
          'codigo_reserva': r.codigoReserva,
          'id_empresa': idEmpresa,
          'id_usuario': idUsuario,
          'id_sucursal': r.sucursal?.idSucursal,
          'sucursal_nombre': r.sucursal?.nombre,
          'fecha_hora_visita': r.fechaHoraVisita,
          'items_json': jsonEncode(r.items.map((i) => {
            'id_detalle_reserva': i.idDetalleReserva,
            'id_variante': i.idVariante,
            'cantidad': i.cantidad,
            'producto_nombre': i.productoNombre,
            'precio': i.precio,
            'talla': i.talla,
            'color': i.color,
            'codigo_hex': i.codigoHex,
            'imagen_url': i.imagenUrl,
          }).toList()),
          'observaciones': r.observaciones,
          'estado': r.estado,
          'is_offline_draft': 0,
          'created_at': now,
        },
        conflictAlgorithm: ConflictAlgorithm.replace,
      );
    }
    await batch.commit(noResult: true);
  }

  Future<void> saveReservationDraft({
    required String draftId,
    required int idEmpresa,
    required int idUsuario,
    required int idSucursal,
    required String sucursalNombre,
    required String fechaHoraVisita,
    required List<Map<String, dynamic>> items,
    String? observaciones,
  }) async {
    final db = await database;
    final now = DateTime.now().toUtc().toIso8601String();

    await db.insert(
      'local_reservations',
      {
        'id_reserva_local': draftId,
        'codigo_reserva': 'BORRADOR-LOCAL',
        'id_empresa': idEmpresa,
        'id_usuario': idUsuario,
        'id_sucursal': idSucursal,
        'sucursal_nombre': sucursalNombre,
        'fecha_hora_visita': fechaHoraVisita,
        'items_json': jsonEncode(items),
        'observaciones': observaciones,
        'estado': 'PENDIENTE_SYNC',
        'is_offline_draft': 1,
        'created_at': now,
      },
      conflictAlgorithm: ConflictAlgorithm.replace,
    );
  }

  Future<void> confirmReservationDraft({
    required String operationId,
    String? codigoReserva,
    int? idReserva,
  }) async {
    final db = await database;
    await db.update(
      'local_reservations',
      {
        if (codigoReserva != null && codigoReserva.isNotEmpty) 'codigo_reserva': codigoReserva,
        'estado': 'CONFIRMADA',
        'is_offline_draft': 0,
      },
      where: 'id_reserva_local = ? OR id_reserva_local = ?',
      whereArgs: [operationId, 'draft_$operationId'],
    );
  }

  Future<void> rejectReservationDraft({
    required String operationId,
    String? motivo,
  }) async {
    final db = await database;
    await db.update(
      'local_reservations',
      {
        'estado': 'CONFLICTO',
        if (motivo != null) 'observaciones': motivo,
      },
      where: 'id_reserva_local = ? OR id_reserva_local = ?',
      whereArgs: [operationId, 'draft_$operationId'],
    );
  }

  Future<List<ReservaModel>> getLocalReservations(int idEmpresa, int idUsuario) async {
    final db = await database;
    final rows = await db.query(
      'local_reservations',
      where: 'id_empresa = ? AND id_usuario = ?',
      whereArgs: [idEmpresa, idUsuario],
      orderBy: 'created_at DESC',
    );

    return rows.map((r) {
      final itemsRaw = jsonDecode(r['items_json'] as String? ?? '[]') as List<dynamic>;
      final items = itemsRaw.map((e) => ItemReservaModel.fromJson(Map<String, dynamic>.from(e))).toList();
      final isDraft = (r['is_offline_draft'] as int? ?? 0) == 1;

      return ReservaModel(
        idReserva: int.tryParse(r['id_reserva_local'].toString().replaceAll('res_', '')) ?? 0,
        codigoReserva: r['codigo_reserva'] as String? ?? (isDraft ? 'BORRADOR' : ''),
        fechaReserva: r['created_at'] as String? ?? '',
        fechaHoraVisita: r['fecha_hora_visita'] as String? ?? '',
        estado: r['estado'] as String? ?? 'PENDIENTE',
        observaciones: r['observaciones'] as String?,
        sucursal: SucursalReservaModel(
          idSucursal: r['id_sucursal'] as int? ?? 0,
          nombre: r['sucursal_nombre'] as String? ?? 'Sucursal Tienda',
          direccion: '',
          ciudad: '',
        ),
        items: items,
        totalPrendas: items.length,
        conPago: false, // Citas 100% gratuitas
        estadoPago: 'GRATUITA',
        montoPagado: 0.0,
      );
    }).toList();
  }

  Future<List<ReservaModel>> getReservationDrafts(int idEmpresa, int idUsuario) => getLocalReservations(idEmpresa, idUsuario);

  // --- LIMPIEZA TOTAL EN LOGOUT ---
  Future<void> clearUserCache(int idUsuario) async {
    final db = await database;
    await db.delete('local_cart_drafts', where: 'id_usuario = ?', whereArgs: [idUsuario]);
    await db.delete('local_reservations', where: 'id_usuario = ?', whereArgs: [idUsuario]);
    await db.delete('local_devoluciones', where: 'id_usuario = ?', whereArgs: [idUsuario]);
  }
}
