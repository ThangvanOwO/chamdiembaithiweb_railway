import 'dart:async';

import 'package:flutter/material.dart';
import 'package:flutter/services.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:google_fonts/google_fonts.dart';
import 'package:http/http.dart' as http;
import 'package:http/testing.dart';
import 'package:provider/provider.dart';
import 'package:shared_preferences/shared_preferences.dart';

import 'package:gradeflow_app/config/api_config.dart';
import 'package:gradeflow_app/screens/login_screen.dart';
import 'package:gradeflow_app/services/auth_service.dart';

void main() {
  TestWidgetsFlutterBinding.ensureInitialized();

  setUp(() async {
    SharedPreferences.setMockInitialValues({});
    await ApiConfig.setCustomBaseUrl('http://127.0.0.1:8000');
    GoogleFonts.config.allowRuntimeFetching = false;
    // Typography is outside these lifecycle tests; provide font assets locally.
    TestDefaultBinaryMessengerBinding.instance.defaultBinaryMessenger
        .setMockMessageHandler('flutter/assets', (message) async {
      final asset = String.fromCharCodes(message!.buffer.asUint8List());
      if (asset == 'AssetManifest.bin') {
        final manifest = <String, dynamic>{};
        for (final family in ['Manrope', 'DMSans']) {
          for (final variant in [
            'Thin',
            'ExtraLight',
            'Light',
            'Regular',
            'Medium',
            'SemiBold',
            'Bold',
            'ExtraBold',
            'Black',
          ]) {
            final path = '$family-$variant.ttf';
            manifest[path] = [
              {'asset': path}
            ];
          }
        }
        return const StandardMessageCodec().encodeMessage(manifest);
      }
      return ByteData(0);
    });
  });

  tearDown(() {
    TestDefaultBinaryMessengerBinding.instance.defaultBinaryMessenger
        .setMockMessageHandler('flutter/assets', null);
    GoogleFonts.config.allowRuntimeFetching = true;
  });

  Future<void> openDialog(WidgetTester tester) async {
    await tester.pumpWidget(ChangeNotifierProvider(
      create: (_) => AuthService(),
      child: MaterialApp(
        // The test font is monospaced; keep unrelated login text within bounds.
        builder: (context, child) => MediaQuery(
          data: MediaQuery.of(context)
              .copyWith(textScaler: const TextScaler.linear(0.8)),
          child: child!,
        ),
        home: const LoginScreen(),
      ),
    ));
    await tester.pumpAndSettle();
    await tester.tap(find.text('127.0.0.1:8000'));
    await tester.pumpAndSettle();
  }

  testWidgets('save focused server address and reopen without lifecycle errors',
      (tester) async {
    await openDialog(tester);
    final address = find.descendant(
        of: find.byType(AlertDialog), matching: find.byType(TextField));
    await tester.enterText(address, 'http://192.168.1.20:8000/');
    await tester.tap(find.text('Lưu'));
    await tester.pumpAndSettle();
    expect(tester.takeException(), isNull);
    expect(ApiConfig.baseUrl, 'http://192.168.1.20:8000');
    final prefs = await SharedPreferences.getInstance();
    expect(prefs.getString('custom_server_url'), ApiConfig.baseUrl);
    await tester.tap(find.text('192.168.1.20:8000'));
    await tester.pumpAndSettle();
    expect(find.text('http://192.168.1.20:8000'), findsOneWidget);
  });

  testWidgets('dismiss focused server address without saving', (tester) async {
    await openDialog(tester);
    final address = find.descendant(
        of: find.byType(AlertDialog), matching: find.byType(TextField));
    await tester.enterText(address, 'http://192.168.1.99:8000');
    await tester.tapAt(const Offset(10, 10));
    await tester.pumpAndSettle();
    expect(tester.takeException(), isNull);
    expect(ApiConfig.baseUrl, 'http://127.0.0.1:8000');
  });

  testWidgets(
      'connection check uses mobile API and accepts authentication response',
      (tester) async {
    await http.runWithClient(() async {
      await openDialog(tester);
      await tester.tap(find.text('Thử kết nối'));
      await tester.pumpAndSettle();
      expect(find.text('Kết nối thành công!'), findsOneWidget);
      expect(tester.takeException(), isNull);
    },
        () => MockClient((request) async {
              expect(request.url.toString(),
                  'http://127.0.0.1:8000/api/v1/dashboard/');
              return http.Response('', 401);
            }));
  });

  for (final failed in [false, true]) {
    testWidgets('dismiss while connection check is pending (failed: $failed)',
        (tester) async {
      final pending = Completer<http.Response>();
      await http.runWithClient(() async {
        await openDialog(tester);
        await tester.tap(find.text('Thử kết nối'));
        await tester.pump();
        expect(find.text('Đang kiểm tra kết nối...'), findsOneWidget);
        await tester.tapAt(const Offset(10, 10));
        await tester.pumpAndSettle();
        if (failed) {
          pending.completeError(http.ClientException('Network unavailable'));
        } else {
          pending.complete(http.Response('', 401));
        }
        await tester.pumpAndSettle();
        expect(tester.takeException(), isNull);
        expect(find.byType(AlertDialog), findsNothing);
      }, () => MockClient((_) => pending.future));
    });
  }
}
