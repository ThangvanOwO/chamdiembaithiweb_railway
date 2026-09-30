import 'dart:async';
import 'dart:convert';

import 'package:flutter_test/flutter_test.dart';
import 'package:gradeflow_app/services/auth_service.dart';
import 'package:http/http.dart' as http;
import 'package:http/testing.dart';
import 'package:shared_preferences/shared_preferences.dart';

void main() {
  TestWidgetsFlutterBinding.ensureInitialized();

  Future<AuthService> signedIn() async {
    SharedPreferences.setMockInitialValues({
      'auth_token': 'test-session',
      'auth_user': jsonEncode({'email': 'qa@example.com'}),
      'custom_server_url': 'http://10.0.2.2:8000',
      'has_seen_onboarding': true,
    });
    final auth = AuthService();
    await auth.loadToken();
    return auth;
  }

  test('logout clears and persists the session before server responds', () async {
    final auth = await signedIn();
    final requestSeen = Completer<http.Request>();
    final response = Completer<http.Response>();
    var notifiedSignedOut = false;
    auth.addListener(() => notifiedSignedOut = !auth.isAuthenticated);

    await http.runWithClient(() async {
      final logout = auth.logout();
      final request = await requestSeen.future;
      expect(request.headers['Authorization'], 'Token test-session');
      expect(notifiedSignedOut, isTrue);
      expect(auth.user, isNull);
      final prefs = await SharedPreferences.getInstance();
      expect(prefs.containsKey('auth_token'), isFalse);
      expect(prefs.containsKey('auth_user'), isFalse);
      expect(prefs.getBool('has_seen_onboarding'), isTrue);
      expect(prefs.getString('custom_server_url'), 'http://10.0.2.2:8000');
      final restarted = AuthService();
      await restarted.loadToken();
      expect(restarted.isAuthenticated, isFalse);
      response.complete(http.Response('{}', 200));
      await logout;
    }, () => MockClient((request) {
      requestSeen.complete(request);
      return response.future;
    }));
  });

  test('server connection failure does not prevent logout', () async {
    final auth = await signedIn();
    await http.runWithClient(() => auth.logout(), () => MockClient((_) async {
      throw http.ClientException('Server is offline');
    }));
    expect(auth.isAuthenticated, isFalse);
    expect(auth.user, isNull);
  });

  test('unresponsive logout request has a bounded wait', () async {
    final auth = await signedIn();
    await http.runWithClient(
      () => auth.logout().timeout(const Duration(seconds: 6)),
      () => MockClient((_) => Completer<http.Response>().future),
    );
    expect(auth.isAuthenticated, isFalse);
  });
}
