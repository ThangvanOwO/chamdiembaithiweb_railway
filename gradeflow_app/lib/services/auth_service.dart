import 'dart:convert';
import 'package:flutter/foundation.dart';
import 'package:http/http.dart' as http;
import 'package:shared_preferences/shared_preferences.dart';

import '../config/api_config.dart';

class AuthService extends ChangeNotifier {
  String? _token;
  Map<String, dynamic>? _user;
  bool _isLoading = false;

  String? get token => _token;
  Map<String, dynamic>? get user => _user;
  bool get isAuthenticated => _token != null;
  bool get isLoading => _isLoading;

  String get userName =>
      _user?['full_name'] ?? _user?['email'] ?? 'Giáo viên';
  String get userEmail => _user?['email'] ?? '';
  String get userInitial =>
      (userName.isNotEmpty ? userName[0] : 'G').toUpperCase();
  bool get isAdmin => _user?['is_admin'] == true;

  /// Re-fetch /auth/me/ to pick up latest flags (is_admin, etc).
  Future<void> refreshMe() async {
    if (_token == null) return;
    try {
      final response = await http.get(
        Uri.parse('${ApiConfig.baseUrl}${ApiConfig.me}'),
        headers: authHeaders,
      );
      if (response.statusCode == 200) {
        _user = json.decode(response.body);
        final prefs = await SharedPreferences.getInstance();
        await prefs.setString('auth_user', json.encode(_user));
        notifyListeners();
      } else if (response.statusCode == 401 || response.statusCode == 403) {
        await logout();
      }
    } catch (_) {}
  }

  /// Load token from SharedPreferences on app start.
  Future<void> loadToken() async {
    final prefs = await SharedPreferences.getInstance();
    _token = prefs.getString('auth_token');
    final userJson = prefs.getString('auth_user');
    if (userJson != null) {
      try {
        _user = json.decode(userJson);
      } catch (_) {}
    }
    notifyListeners();
  }

  /// Register new account.
  Future<String?> register(String email, String password, String firstName, String lastName) async {
    _isLoading = true;
    notifyListeners();

    try {
      final response = await http.post(
        Uri.parse('${ApiConfig.baseUrl}${ApiConfig.register}'),
        headers: {'Content-Type': 'application/json'},
        body: json.encode({
          'email': email,
          'password': password,
          'first_name': firstName,
          'last_name': lastName,
        }),
      );

      final data = json.decode(response.body);

      if ((response.statusCode == 200 || response.statusCode == 201) && data['token'] != null) {
        _token = data['token'];
        _user = data['user'];

        final prefs = await SharedPreferences.getInstance();
        await prefs.setString('auth_token', _token!);
        await prefs.setString('auth_user', json.encode(_user));

        _isLoading = false;
        notifyListeners();
        return null; // success
      } else {
        _isLoading = false;
        notifyListeners();
        return data['message'] ?? data['error'] ?? 'Đăng ký thất bại';
      }
    } catch (e) {
      _isLoading = false;
      notifyListeners();
      return 'Không thể kết nối server.';
    }
  }

  /// Login with email + password.
  Future<String?> login(String email, String password) async {
    _isLoading = true;
    notifyListeners();

    try {
      final response = await http.post(
        Uri.parse('${ApiConfig.baseUrl}${ApiConfig.login}'),
        headers: {'Content-Type': 'application/json'},
        body: json.encode({'email': email, 'password': password}),
      );

      final data = json.decode(response.body);

      if (response.statusCode == 200 && data['token'] != null) {
        _token = data['token'];
        _user = data['user'];

        final prefs = await SharedPreferences.getInstance();
        await prefs.setString('auth_token', _token!);
        await prefs.setString('auth_user', json.encode(_user));

        _isLoading = false;
        notifyListeners();
        return null; // success
      } else {
        _isLoading = false;
        notifyListeners();
        return data['error'] ?? 'Đăng nhập thất bại';
      }
    } catch (e) {
      _isLoading = false;
      notifyListeners();
      return 'Không thể kết nối server. Kiểm tra lại địa chỉ API.';
    }
  }

  /// End the local session without waiting for an unavailable server.
  Future<void> logout() async {
    final token = _token;
    final logoutUrl = '${ApiConfig.baseUrl}${ApiConfig.logout}';
    _token = null;
    _user = null;
    _isLoading = false;

    final prefs = await SharedPreferences.getInstance();
    await prefs.remove('auth_token');
    await prefs.remove('auth_user');

    notifyListeners();

    // Best effort: the UI and persisted session are already signed out.
    // Use the captured token so a later login cannot change this request.
    if (token == null) return;
    final client = http.Client();
    try {
      await client.post(
        Uri.parse(logoutUrl),
        headers: {
          'Authorization': 'Token $token',
          'Content-Type': 'application/json',
        },
      ).timeout(const Duration(seconds: 4));
    } catch (_) {
      // Offline logout still succeeds locally.
    } finally {
      client.close();
    }
  }

  /// Auth headers for API calls.
  Map<String, String> get authHeaders => {
        'Authorization': 'Token $_token',
        'Content-Type': 'application/json',
      };
}
