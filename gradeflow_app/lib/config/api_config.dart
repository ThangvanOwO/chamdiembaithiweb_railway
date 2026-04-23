/// API configuration — change baseUrl to your server address.
class ApiConfig {
  // Development: use your local IP (not localhost) so the phone can reach it.
  // Example: 'http://192.168.1.100:8000'
  // Production: 'https://your-railway-domain.up.railway.app'
  static const String baseUrl = 'https://web-production-4b96b.up.railway.app';

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
