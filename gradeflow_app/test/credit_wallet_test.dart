import 'dart:convert';
import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:http/http.dart' as http;
import 'package:http/testing.dart';
import 'package:gradeflow_app/services/credit_service.dart';
import 'package:gradeflow_app/widgets/ad_banner.dart';
import 'package:gradeflow_app/widgets/credit_wallet_card.dart';

void main() {
  Widget screen(CreditService service, {bool active = true}) => MaterialApp(
        home: Scaffold(
            body: SingleChildScrollView(
                child: AdBannerScope(
          isActive: active,
          child: CreditWalletCard(token: 'test-token', service: service),
        ))),
      );

  testWidgets(
      'reads authenticated balance and ledger; pending actions are disabled',
      (tester) async {
    final service = CreditService(client: MockClient((request) async {
      expect(request.headers['authorization'], 'Token test-token');
      expect(request.url.path, '/api/v1/credits/');
      return http.Response(
          jsonEncode({
            'balance': 73,
            'entries': [
              {
                'amount': -1,
                'balance_after': 73,
                'reason': 'Chấm bài',
                'created_at': '2026-09-29T01:00:00Z'
              },
            ]
          }),
          200,
          headers: {'content-type': 'application/json; charset=utf-8'});
    }));
    await tester.pumpWidget(screen(service));
    await tester.pumpAndSettle();
    expect(find.text('73 điểm'), findsOneWidget);
    expect(find.text('Chưa mở'), findsOneWidget);
    expect(find.text('Quảng cáo thử · không cộng điểm'), findsOneWidget);
    final reward = tester.widget<ListTile>(
        find.widgetWithText(ListTile, 'Xem quảng cáo nhận thưởng'));
    expect(reward.enabled, isFalse);
    expect(reward.onTap, isNull);
    await tester.tap(find.text('Lịch sử tín dụng'));
    await tester.pumpAndSettle();
    expect(find.text('Chấm bài'), findsOneWidget);
    expect(find.text('-1'), findsOneWidget);
    expect(tester.takeException(), isNull);
  });

  testWidgets('does not show zero balance when API fails; refresh recovers',
      (tester) async {
    var calls = 0;
    final service = CreditService(client: MockClient((_) async {
      calls++;
      return calls == 1
          ? http.Response('', 500)
          : http.Response('{"balance": 98, "entries": []}', 200);
    }));
    await tester.pumpWidget(screen(service));
    await tester.pumpAndSettle();
    expect(find.textContaining('Không tải được số dư'), findsOneWidget);
    expect(find.text('0 điểm'), findsNothing);
    await tester.tap(find.byTooltip('Cập nhật số dư'));
    await tester.pumpAndSettle();
    expect(find.text('98 điểm'), findsOneWidget);
    expect(find.textContaining('Không tải được số dư'), findsNothing);
  });

  testWidgets('refreshes when retained account tab becomes active again',
      (tester) async {
    var calls = 0;
    final service = CreditService(client: MockClient((_) async {
      calls++;
      return http.Response('{"balance": ${100 - calls}, "entries": []}', 200);
    }));
    await tester.pumpWidget(screen(service, active: false));
    await tester.pumpAndSettle();
    expect(calls, 0);
    await tester.pumpWidget(screen(service));
    await tester.pumpAndSettle();
    expect(find.text('99 điểm'), findsOneWidget);
    await tester.pumpWidget(screen(service, active: false));
    await tester.pumpWidget(screen(service));
    await tester.pumpAndSettle();
    expect(find.text('98 điểm'), findsOneWidget);
  });
}
