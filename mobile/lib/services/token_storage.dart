import 'dart:convert';
import 'package:flutter_secure_storage/flutter_secure_storage.dart';

class TokenStorage {
  static const FlutterSecureStorage _storage = FlutterSecureStorage();

  static const String _keyToken = 'auth_token';
  static const String _keyUserJson = 'auth_user_json';
  static const String _keyEmpresaId = 'selected_empresa_id';
  static const String _keySucursalId = 'selected_sucursal_id';

  static Future<void> saveToken(String token) async {
    await _storage.write(key: _keyToken, value: token);
  }

  static Future<String?> getToken() async {
    return _storage.read(key: _keyToken);
  }

  static Future<void> clearToken() async {
    await _storage.delete(key: _keyToken);
    await _storage.delete(key: _keyUserJson);
  }

  static Future<void> saveUserJson(String jsonStr) async {
    await _storage.write(key: _keyUserJson, value: jsonStr);
  }

  static Future<String?> getUserJson() async {
    return _storage.read(key: _keyUserJson);
  }

  static Future<Map<String, dynamic>?> getUsuario() async {
    final str = await getUserJson();
    if (str != null && str.isNotEmpty) {
      try {
        return jsonDecode(str) as Map<String, dynamic>;
      } catch (_) {
        return null;
      }
    }
    return null;
  }

  static Future<void> saveEmpresaId(int idEmpresa) async {
    await _storage.write(key: _keyEmpresaId, value: idEmpresa.toString());
  }

  static Future<int?> getEmpresaId() async {
    final str = await _storage.read(key: _keyEmpresaId);
    return str != null ? int.tryParse(str) : null;
  }

  static Future<void> saveSucursalContext(
      {required int idEmpresa, required int idSucursal}) async {
    await _storage.write(key: _keyEmpresaId, value: idEmpresa.toString());
    await _storage.write(key: _keySucursalId, value: idSucursal.toString());
  }

  static Future<int?> getSucursalId() async {
    final str = await _storage.read(key: _keySucursalId);
    return str != null ? int.tryParse(str) : null;
  }

  static Future<void> clearSucursalContext() async {
    await _storage.delete(key: _keySucursalId);
  }

  static Future<void> clearAll() async {
    await _storage.deleteAll();
  }
}
