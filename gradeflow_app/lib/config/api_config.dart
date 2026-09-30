import 'package:shared_preferences/shared_preferences.dart';

/// API configuration — dynamic baseUrl for local LAN or production server.
class ApiConfig {
  static const String defaultBaseUrl = 'https://gradeflow.io.vn';
  static String _customBaseUrl = '';

  static String get baseUrl =>
      _customBaseUrl.isNotEmpty ? _customBaseUrl : defaultBaseUrl;

  static Future<void> loadCustomBaseUrl() async {
    try {
      final prefs = await SharedPreferences.getInstance();
      final saved = prefs.getString('custom_server_url');
      if (saved != null && saved.trim().isNotEmpty) {
        final trimmed = saved.trim();
        if (trimmed.contains('192.168.1.5') || trimmed.contains('172.20.142.5')) {
          await prefs.remove('custom_server_url');
          _customBaseUrl = '';
        } else {
          _customBaseUrl = trimmed;
        }
      }
    } catch (_) {}
  }

  static Future<void> setCustomBaseUrl(String url) async {
    var trimmed = url.trim();
    if (trimmed.endsWith('/')) {
      trimmed = trimmed.substring(0, trimmed.length - 1);
    }
    _customBaseUrl = trimmed;
    try {
      final prefs = await SharedPreferences.getInstance();
      if (trimmed.isEmpty) {
        await prefs.remove('custom_server_url');
      } else {
        await prefs.setString('custom_server_url', trimmed);
      }
    } catch (_) {}
  }

  // API v1 prefix
  static const String apiPrefix = '/api/v1';

  // Endpoints
  static const String register = '$apiPrefix/auth/register/';
  static const String login = '$apiPrefix/auth/login/';
  static const String logout = '$apiPrefix/auth/logout/';
  static const String me = '$apiPrefix/auth/me/';
  static const String dashboard = '$apiPrefix/dashboard/';
  static const String exams = '$apiPrefix/exams/';
  static const String parseExcel = '$apiPrefix/parse-excel/';
  static const String parseImage = '$apiPrefix/parse-image/';
  static const String grade = '$apiPrefix/grade/';
  static const String templates = '$apiPrefix/templates/';
  static const String submissions = '$apiPrefix/submissions/';
  static const String userSettings = '$apiPrefix/settings/';
  static const String cleanupNow = '$apiPrefix/settings/cleanup-now/';
  static const String trainingUpload = '$apiPrefix/training/upload/';
  static const String trainingStats = '$apiPrefix/training/stats/';
  static const String trainingDownload = '$apiPrefix/training/download/';

  // Admin
  static const String adminUsers = '$apiPrefix/admin/users/';

  static String examDetail(int id) => '$apiPrefix/exams/$id/';
  static String examDelete(int id) => '$apiPrefix/exams/$id/delete/';
  static String submissionDetail(int id) => '$apiPrefix/submissions/$id/';
}
