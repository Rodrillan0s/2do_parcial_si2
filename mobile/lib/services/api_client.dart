import 'package:dio/dio.dart';
import '../config/app_config.dart';
import '../core/tenant/tenant_context_manager.dart';
import 'token_storage.dart';

class ApiClient {
  static Dio? _dioInstance;

  static Dio get dio {
    _dioInstance ??= _createDio();
    // Actualizar baseUrl si AppConfig cambió
    _dioInstance!.options.baseUrl = AppConfig.apiBaseUrl;
    return _dioInstance!;
  }

  static Dio _createDio() {
    final dio = Dio(
      BaseOptions(
        baseUrl: AppConfig.apiBaseUrl,
        connectTimeout: const Duration(seconds: 20),
        receiveTimeout: const Duration(seconds: 20),
        headers: {
          'Content-Type': 'application/json',
          'Accept': 'application/json',
        },
      ),
    );

    dio.interceptors.add(
      InterceptorsWrapper(
        onRequest: (options, handler) async {
          // Los servicios conservan una instancia Dio; sincronizar la URL aquí
          // permite cambiar entre local y producción desde la app sin reiniciarla.
          options.baseUrl = AppConfig.apiBaseUrl;
          final token = await TokenStorage.getToken();
          if (token != null && token.isNotEmpty) {
            options.headers['Authorization'] = 'Bearer $token';
          }
          final tenantId = TenantContextManager().idEmpresaActiva;
          if (tenantId != null) {
            options.headers['X-Tenant-Id'] = tenantId.toString();
          }
          return handler.next(options);
        },
        onError: (DioException e, handler) async {
          if (e.response?.statusCode == 401) {
            await TokenStorage.clearToken();
          }
          return handler.next(e);
        },
      ),
    );

    return dio;
  }
}
