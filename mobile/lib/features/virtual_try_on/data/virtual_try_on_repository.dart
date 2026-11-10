import 'package:dio/dio.dart';
import 'package:flutter/foundation.dart';
import '../../../core/tenant/tenant_context_manager.dart';
import '../../../services/api_client.dart';
import '../models/garment_model.dart';

class VirtualTryOnRepository {
  final Dio _dio;

  VirtualTryOnRepository({Dio? dio}) : _dio = dio ?? ApiClient.dio;

  /// Obtiene la lista de prendas compatibles con el vestidor virtual RA
  Future<List<GarmentModel>> getPrendasCompatibles({GarmentType? tipo}) async {
    try {
      final Map<String, dynamic> queryParams = {};
      final tenantId = TenantContextManager().idEmpresaActiva;
      if (tenantId != null) {
        queryParams['id_empresa'] = tenantId;
      }
      if (tipo != null) {
        queryParams['tipo_prenda'] = tipo.name.toUpperCase();
      }

      final response = await _dio.get(
        '/api/catalogo/vestidor/prendas',
        queryParameters: queryParams,
      );

      if (response.statusCode == 200) {
        dynamic rawList;
        if (response.data is List) {
          rawList = response.data;
        } else if (response.data is Map && response.data['data'] is List) {
          rawList = response.data['data'];
        }

        if (rawList is List) {
          return rawList
              .map((item) => GarmentModel.fromJson(Map<String, dynamic>.from(item as Map)))
              .toList();
        }
      }
      return [];
    } catch (e) {
      debugPrint('[VirtualTryOnRepository] Error al obtener prendas: $e');
      return [];
    }
  }

  /// Obtiene la configuración de vestidor de un producto específico
  Future<GarmentModel?> getProductoVestidor(int idProducto) async {
    try {
      final response = await _dio.get('/api/catalogo/productos/$idProducto/vestidor');
      if (response.statusCode == 200) {
        dynamic rawMap;
        if (response.data is Map && response.data['data'] is Map) {
          rawMap = response.data['data'];
        } else if (response.data is Map) {
          rawMap = response.data;
        }

        if (rawMap is Map) {
          return GarmentModel.fromJson(Map<String, dynamic>.from(rawMap));
        }
      }
      return null;
    } catch (e) {
      debugPrint('[VirtualTryOnRepository] Error al obtener producto $idProducto: $e');
      return null;
    }
  }
}
