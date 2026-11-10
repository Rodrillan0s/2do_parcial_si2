import 'dart:convert';
import 'package:flutter/material.dart';
import 'auth_service.dart';
import 'token_storage.dart';

class AuthProvider extends ChangeNotifier {
  final AuthService _authService = AuthService();

  bool _estaAutenticado = false;
  UsuarioModel? _usuario;
  bool _cargando = true;

  bool get estaAutenticado => _estaAutenticado;
  UsuarioModel? get usuario => _usuario;
  bool get cargando => _cargando;
  int? get idEmpresa => _usuario?.idEmpresa;

  Future<void> verificarSesion() async {
    _cargando = true;
    notifyListeners();

    try {
      final token = await TokenStorage.getToken();
      if (token != null && token.isNotEmpty) {
        final userJson = await TokenStorage.getUserJson();
        if (userJson != null) {
          _usuario = UsuarioModel.fromJson(jsonDecode(userJson));
          _estaAutenticado = true;
        } else {
          _estaAutenticado = true;
        }
      } else {
        _estaAutenticado = false;
        _usuario = null;
      }
    } catch (_) {
      _estaAutenticado = false;
      _usuario = null;
    } finally {
      _cargando = false;
      notifyListeners();
    }
  }

  Future<Map<String, dynamic>> login(String identifier, String password) async {
    final result = await _authService.login(
      loginIdentifier: identifier,
      password: password,
    );

    if (result['success'] == true && result['requires_verification'] != true) {
      _usuario = result['usuario'] as UsuarioModel;
      _estaAutenticado = true;
      notifyListeners();
    }

    return result;
  }

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
    final result = await _authService.register(
      correo: correo,
      password: password,
      confirmPassword: confirmPassword,
      nombre: nombre,
      apellido: apellido,
      telefono: telefono,
      nombreUsuario: nombreUsuario,
      idEmpresa: idEmpresa,
    );

    if (result['success'] == true) {
      _usuario = result['usuario'] as UsuarioModel;
      _estaAutenticado = true;
      notifyListeners();
    }

    return result;
  }

  Future<void> logout() async {
    _estaAutenticado = false;
    _usuario = null;
    await _authService.logout();
    notifyListeners();
  }

  void actualizarUsuario(UsuarioModel usuarioActualizado) {
    _usuario = usuarioActualizado;
    TokenStorage.saveUserJson(jsonEncode(usuarioActualizado.toJson()));
    notifyListeners();
  }
}