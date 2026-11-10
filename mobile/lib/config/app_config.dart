import 'package:flutter/foundation.dart';
import 'package:shared_preferences/shared_preferences.dart';

class AppConfig {
  // Version nueva para descartar overrides localhost guardados por builds anteriores.
  static const String _keyCustomUrl = 'aurora_custom_api_url_v2';
  static String _overrideBaseUrl = '';

  static const String defaultDeployedUrl =
      'https://aurora-store-be.onrender.com';
  static const String defaultLocalUrl = 'http://127.0.0.1:5000';
  static const String defaultLanUrl = 'http://192.168.0.9:5000';
  static const String defaultEmulatorUrl = 'http://10.0.2.2:5000';

  static Future<void> init() async {
    try {
      final prefs = await SharedPreferences.getInstance();
      final saved = prefs.getString(_keyCustomUrl);
      if (saved != null && saved.isNotEmpty) {
        final normalized = saved.trim().replaceFirst(RegExp(r'/+$'), '');
        _overrideBaseUrl = normalized;
      }
    } catch (_) {}
  }

  static Future<void> setBaseUrl(String url) async {
    _overrideBaseUrl = url.trim().replaceFirst(RegExp(r'/+$'), '');
    try {
      final prefs = await SharedPreferences.getInstance();
      await prefs.setString(_keyCustomUrl, _overrideBaseUrl);
    } catch (_) {}
  }

  static Future<void> resetBaseUrl() async {
    _overrideBaseUrl = '';
    try {
      final prefs = await SharedPreferences.getInstance();
      await prefs.remove(_keyCustomUrl);
    } catch (_) {}
  }

  static String get apiBaseUrl {
    const envUrl = String.fromEnvironment('API_BASE_URL', defaultValue: '');
    if (envUrl.isNotEmpty) {
      return envUrl;
    }

    if (kReleaseMode) {
      return defaultDeployedUrl;
    }

    if (_overrideBaseUrl.isNotEmpty) {
      return _overrideBaseUrl;
    }

    // El fallback de producción permite que la build publicada funcione sin configuración manual.
    return defaultDeployedUrl;
  }
}
