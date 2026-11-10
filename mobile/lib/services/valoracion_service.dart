import 'package:flutter/foundation.dart';
import 'api_client.dart';

class OpinionClienteModel {
  final int idValoracion;
  final int puntuacion;
  final String? comentario;
  final String fechaCreacion;
  final String nombreCliente;
  final bool compraVerificada;

  OpinionClienteModel({
    required this.idValoracion,
    required this.puntuacion,
    this.comentario,
    required this.fechaCreacion,
    required this.nombreCliente,
    this.compraVerificada = true,
  });

  factory OpinionClienteModel.fromJson(Map<String, dynamic> json) {
    return OpinionClienteModel(
      idValoracion: json['id_valoracion'] ?? 0,
      puntuacion: json['puntuacion'] ?? 5,
      comentario: json['comentario'],
      fechaCreacion: json['fecha_creacion'] ?? '',
      nombreCliente: json['nombre_cliente'] ?? 'Cliente',
      compraVerificada: json['compra_verificada'] ?? true,
    );
  }
}

class ResumenValoracionesProductoModel {
  final int idProducto;
  final double promedio;
  final int total;
  final Map<int, int> distribucion;
  final List<OpinionClienteModel> ultimasOpiniones;

  ResumenValoracionesProductoModel({
    required this.idProducto,
    required this.promedio,
    required this.total,
    required this.distribucion,
    required this.ultimasOpiniones,
  });

  factory ResumenValoracionesProductoModel.fromJson(Map<String, dynamic> json) {
    final distMap = <int, int>{};
    if (json['distribucion'] is Map) {
      (json['distribucion'] as Map).forEach((k, v) {
        final parsedKey = int.tryParse(k.toString()) ?? 0;
        distMap[parsedKey] = (v is num) ? v.toInt() : 0;
      });
    }
    final rawOpiniones = json['ultimas_opiniones'] as List? ?? [];
    return ResumenValoracionesProductoModel(
      idProducto: json['id_producto'] ?? 0,
      promedio: (json['promedio'] is num) ? (json['promedio'] as num).toDouble() : 0.0,
      total: json['total'] ?? 0,
      distribucion: distMap,
      ultimasOpiniones: rawOpiniones
          .map((e) => OpinionClienteModel.fromJson(Map<String, dynamic>.from(e)))
          .toList(),
    );
  }
}

class ValoracionService {
  Future<Map<String, dynamic>> crearValoracion({
    int? idProducto,
    int? idPedido,
    int? idVenta,
    int? idReserva,
    required int puntuacion,
    String? comentario,
    String? motivoNegativo,
  }) async {
    final body = <String, dynamic>{
      'puntuacion': puntuacion,
      if (idProducto != null) 'id_producto': idProducto,
      if (idPedido != null) 'id_pedido': idPedido,
      if (idVenta != null) 'id_venta': idVenta,
      if (idReserva != null) 'id_reserva': idReserva,
      if (comentario != null && comentario.isNotEmpty) 'comentario': comentario,
      if (motivoNegativo != null && motivoNegativo.isNotEmpty) 'motivo_negativo': motivoNegativo,
    };

    final resp = await ApiClient.dio.post('/api/valoraciones', data: body);
    return resp.data as Map<String, dynamic>;
  }

  Future<ResumenValoracionesProductoModel?> obtenerResumenProducto(int idProducto) async {
    try {
      final resp = await ApiClient.dio.get('/api/valoraciones/producto/$idProducto');
      if (resp.data != null && resp.data['data'] != null) {
        return ResumenValoracionesProductoModel.fromJson(
            Map<String, dynamic>.from(resp.data['data']));
      }
      return null;
    } catch (e) {
      debugPrint('Error al obtener resumen de valoraciones: $e');
      return null;
    }
  }

  Future<List<Map<String, dynamic>>> obtenerPendientes() async {
    try {
      final resp = await ApiClient.dio.get('/api/valoraciones/pendientes');
      if (resp.data != null && resp.data['data'] is List) {
        return (resp.data['data'] as List)
            .map((e) => Map<String, dynamic>.from(e))
            .toList();
      }
      return [];
    } catch (e) {
      debugPrint('Error al obtener pendientes de valoracion: $e');
      return [];
    }
  }
}
