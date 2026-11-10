import 'package:dio/dio.dart';
import 'api_client.dart';

class PerfilModel {
  final int idUsuario;
  final String username;
  final String nombre;
  final String apellido;
  final String nombreCompleto;
  final String correo;
  final String? telefono;
  final String? ci;
  final String? direccion;
  final String? ciudad;
  final String? estado;
  final String? fechaRegistro;
  final int? idRol;
  final String? nombreRol;
  final int? idEmpresa;
  final String? nombreEmpresa;

  PerfilModel({
    required this.idUsuario,
    required this.username,
    required this.nombre,
    required this.apellido,
    required this.nombreCompleto,
    required this.correo,
    this.telefono,
    this.ci,
    this.direccion,
    this.ciudad,
    this.estado,
    this.fechaRegistro,
    this.idRol,
    this.nombreRol,
    this.idEmpresa,
    this.nombreEmpresa,
  });

  factory PerfilModel.fromJson(Map<String, dynamic> json) {
    return PerfilModel(
      idUsuario: json['id_usuario'] ?? json['nro_usuario'] ?? 0,
      username: json['username'] ?? json['nombre_usuario'] ?? '',
      nombre: json['nombre'] ?? '',
      apellido: json['apellido'] ?? '',
      nombreCompleto: json['nombre_completo'] ?? '${json['nombre'] ?? ''} ${json['apellido'] ?? ''}'.trim(),
      correo: json['correo'] ?? '',
      telefono: json['telefono']?.toString(),
      ci: json['ci']?.toString(),
      direccion: json['direccion']?.toString(),
      ciudad: json['ciudad']?.toString(),
      estado: json['estado']?.toString(),
      fechaRegistro: json['fecha_registro']?.toString(),
      idRol: json['id_rol'],
      nombreRol: json['nombre_rol'],
      idEmpresa: json['id_empresa'],
      nombreEmpresa: json['nombre_empresa'],
    );
  }
}

class ProfileService {
  final Dio _dio = ApiClient.dio;

  Future<PerfilModel> obtenerPerfil() async {
    try {
      final response = await _dio.get('/api/perfil/');
      final data = response.data;
      if (data['success'] == true && data['data'] != null) {
        return PerfilModel.fromJson(data['data']);
      }
      throw Exception(data['message'] ?? 'No se pudo obtener el perfil.');
    } on DioException catch (e) {
      final msg = e.response?.data?['detail'] ?? e.response?.data?['message'] ?? 'Error de conexión.';
      throw Exception(msg.toString());
    }
  }

  Future<PerfilModel> actualizarPerfil({
    required String nombre,
    required String apellido,
    String? telefono,
    String? ci,
    String? direccion,
    String? ciudad,
  }) async {
    try {
      final body = {
        'nombre': nombre.trim(),
        'apellido': apellido.trim(),
        'telefono': telefono?.trim(),
        'ci': ci?.trim(),
        'direccion': direccion?.trim(),
        'ciudad': ciudad?.trim(),
      };

      final response = await _dio.put('/api/perfil/', data: body);
      final data = response.data;
      if (data['success'] == true && data['data'] != null) {
        return PerfilModel.fromJson(data['data']);
      }
      throw Exception(data['message'] ?? 'No se pudo actualizar el perfil.');
    } on DioException catch (e) {
      final msg = e.response?.data?['detail'] ?? e.response?.data?['message'] ?? 'Error al actualizar perfil.';
      throw Exception(msg.toString());
    }
  }

  Future<void> cambiarPassword(String nuevaPassword) async {
    try {
      final response = await _dio.put(
        '/api/perfil/cambiar-password',
        data: {'password': nuevaPassword},
      );
      final data = response.data;
      if (data['success'] != true) {
        throw Exception(data['message'] ?? 'Error al cambiar contraseña.');
      }
    } on DioException catch (e) {
      final msg = e.response?.data?['detail'] ?? e.response?.data?['message'] ?? 'Error al cambiar contraseña.';
      throw Exception(msg.toString());
    }
  }
}