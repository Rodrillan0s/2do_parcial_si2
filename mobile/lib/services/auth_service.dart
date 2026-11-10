import 'dart:convert';
import 'package:dio/dio.dart';
import 'api_client.dart';
import 'token_storage.dart';

class UsuarioModel {
  final int nroUsuario;
  final String correo;
  final String nombreUsuario;
  final String nombre;
  final String apellido;
  final String? telefono;
  final int? idRol;
  final String? nombreRol;
  final int? idEmpresa;
  final String? nombreEmpresa;
  final List<String> roles;
  final List<String> permisos;
  final List<dynamic> sucursales;

  UsuarioModel({
    required this.nroUsuario,
    required this.correo,
    required this.nombreUsuario,
    required this.nombre,
    required this.apellido,
    this.telefono,
    this.idRol,
    this.nombreRol,
    this.idEmpresa,
    this.nombreEmpresa,
    this.roles = const [],
    this.permisos = const [],
    this.sucursales = const [],
  });

  String get nombreCompleto => '$nombre $apellido'.trim();

  factory UsuarioModel.fromJson(Map<String, dynamic> json) {
    return UsuarioModel(
      nroUsuario: json['nro_usuario'] ?? json['id_usuario'] ?? 0,
      correo: json['correo'] ?? '',
      nombreUsuario: json['nombre_usuario'] ?? json['username'] ?? '',
      nombre: json['nombre'] ?? '',
      apellido: json['apellido'] ?? '',
      telefono: json['telefono']?.toString(),
      idRol: json['id_rol'],
      nombreRol: json['nombre_rol'],
      idEmpresa: json['id_empresa'],
      nombreEmpresa: json['nombre_empresa'],
      roles: (json['roles'] as List<dynamic>?)
              ?.map((e) => e.toString())
              .toList() ??
          [],
      permisos: (json['permisos'] as List<dynamic>?)
              ?.map((e) => e.toString())
              .toList() ??
          [],
      sucursales: json['sucursales'] as List<dynamic>? ?? [],
    );
  }

  Map<String, dynamic> toJson() {
    return {
      'nro_usuario': nroUsuario,
      'correo': correo,
      'nombre_usuario': nombreUsuario,
      'nombre': nombre,
      'apellido': apellido,
      'telefono': telefono,
      'id_rol': idRol,
      'nombre_rol': nombreRol,
      'id_empresa': idEmpresa,
      'nombre_empresa': nombreEmpresa,
      'roles': roles,
      'permisos': permisos,
      'sucursales': sucursales,
    };
  }
}

class AuthService {
  final Dio _dio = ApiClient.dio;

  /// Inicia sesión consumiendo POST /api/auth/login
  Future<Map<String, dynamic>> login({
    required String loginIdentifier,
    required String password,
    String? deviceFingerprint,
    String? nombreDispositivo,
  }) async {
    try {
      final response = await _dio.post(
        '/api/auth/login',
        data: {
          'login_identifier': loginIdentifier.trim(),
          'password': password,
          'device_fingerprint': deviceFingerprint ?? 'mobile_android_client',
          'nombre_dispositivo': nombreDispositivo ?? 'Aurora Mobile App',
        },
      );

      final data = response.data;
      if (data['success'] == true) {
        if (data['requires_verification'] == true) {
          return {
            'success': true,
            'requires_verification': true,
            'nro_usuario': data['nro_usuario'],
            'codigo_simulado': data['codigo_simulado'],
            'message': data['message'],
          };
        }

        final token = data['token'];
        final usuarioMap = data['usuario'];
        final usuario = UsuarioModel.fromJson(usuarioMap);

        await TokenStorage.saveToken(token);
        await TokenStorage.saveUserJson(jsonEncode(usuario.toJson()));
        if (usuario.idEmpresa != null) {
          await TokenStorage.saveEmpresaId(usuario.idEmpresa!);
        }

        return {
          'success': true,
          'requires_verification': false,
          'usuario': usuario,
          'token': token,
        };
      }

      return {
        'success': false,
        'message': data['message'] ?? 'Error desconocido al iniciar sesión',
      };
    } on DioException catch (e) {
      final errorMsg = e.response?.data?['detail'] ??
          e.response?.data?['message'] ??
          (e.type == DioExceptionType.connectionError ||
                  e.type == DioExceptionType.connectionTimeout
              ? 'No se pudo conectar a ${ApiClient.dio.options.baseUrl}. En un teléfono físico usa la IP LAN del PC, por ejemplo http://192.168.0.9:5000.'
              : 'Error de conexión con el servidor.');
      return {
        'success': false,
        'message': errorMsg.toString(),
      };
    } catch (e) {
      return {
        'success': false,
        'message': 'Error inesperado: $e',
      };
    }
  }

  /// Registra un nuevo cliente consumiendo POST /api/auth/register
  Future<Map<String, dynamic>> register({
    required String correo,
    required String password,
    required String confirmPassword,
    required String nombre,
    required String apellido,
    String? telefono,
    String? nombreUsuario,
    int? idEmpresa,
  }) async {
    try {
      final response = await _dio.post(
        '/api/auth/register',
        data: {
          'correo': correo.trim(),
          'password': password,
          'confirm_password': confirmPassword,
          'nombre': nombre.trim(),
          'apellido': apellido.trim(),
          'telefono': telefono?.trim(),
          'nombre_usuario': (nombreUsuario != null && nombreUsuario.isNotEmpty)
              ? nombreUsuario.trim()
              : correo.trim().split('@')[0],
          'aceptar_terminos': true,
          'device_fingerprint': 'mobile_android_client',
          'nombre_dispositivo': 'Aurora Mobile App',
          if (idEmpresa != null) 'id_empresa': idEmpresa,
        },
      );

      final data = response.data;
      if (data['success'] == true) {
        final token = data['token'];
        final usuarioMap = data['usuario'];
        final usuario = UsuarioModel.fromJson(usuarioMap);

        await TokenStorage.saveToken(token);
        await TokenStorage.saveUserJson(jsonEncode(usuario.toJson()));

        return {
          'success': true,
          'message': data['message'] ?? 'Registro completado exitosamente.',
          'usuario': usuario,
          'token': token,
        };
      }

      return {
        'success': false,
        'message': data['message'] ?? 'Error al registrar usuario.',
      };
    } on DioException catch (e) {
      final errorMsg = e.response?.data?['detail'] ??
          e.response?.data?['message'] ??
          'Error de validación en el registro.';
      return {
        'success': false,
        'message': errorMsg.toString(),
      };
    } catch (e) {
      return {
        'success': false,
        'message': 'Error inesperado: $e',
      };
    }
  }

  /// Verifica código de nuevo dispositivo
  Future<Map<String, dynamic>> verifyDevice({
    required int nroUsuario,
    required String codigo,
  }) async {
    try {
      final response = await _dio.post(
        '/api/auth/verify-device',
        data: {
          'id_usuario': nroUsuario,
          'codigo_verificacion': codigo.trim(),
          'device_fingerprint': 'mobile_android_client',
          'nombre_dispositivo': 'Aurora Mobile App',
        },
      );

      final data = response.data;
      return {
        'success': data['success'] ?? true,
        'message': data['message'] ?? 'Dispositivo verificado.',
      };
    } on DioException catch (e) {
      final errorMsg = e.response?.data?['detail'] ??
          e.response?.data?['message'] ??
          'Código incorrecto o expirado.';
      return {
        'success': false,
        'message': errorMsg.toString(),
      };
    }
  }

  /// Cierra sesión
  Future<void> logout() async {
    await TokenStorage.clearToken();
  }
}
