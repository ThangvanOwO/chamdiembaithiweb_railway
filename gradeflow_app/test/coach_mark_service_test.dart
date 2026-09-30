import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:shared_preferences/shared_preferences.dart';
import 'package:gradeflow_app/services/coach_mark_service.dart';

void main() {
  setUp(() => SharedPreferences.setMockInitialValues({}));
  tearDown(CoachMarkService.dismissActive);

  Future<(BuildContext, GlobalKey)> mountTarget(WidgetTester tester) async {
    final key = GlobalKey();
    await tester.pumpWidget(MaterialApp(
      home: Scaffold(
        body: const Center(child: Text('Trang Bài thi')),
        bottomNavigationBar: BottomAppBar(
          child: SizedBox(key: key, height: 50, child: const Center(child: Text('Chấm điểm'))),
        ),
      ),
    ));
    return (key.currentContext!, key);
  }

  testWidgets('guide remains single, readable, and skip dismisses it', (tester) async {
    final (context, key) = await mountTarget(tester);
    final target = CoachMarkService.buildTarget(
      identify: 'scan', key: key, title: 'Bước tiếp theo: Chấm điểm',
      description: 'Quét phiếu học sinh.', contentTop: 220,
      shape: ShapeLightFocus.Circle,
    );
    await CoachMarkService.show(context: context, screenKey: 'guide_test',
        targets: [target], force: true);
    await CoachMarkService.show(context: context, screenKey: 'guide_test',
        targets: [target], force: true);
    await tester.pump();
    await tester.pump(const Duration(milliseconds: 650));
    await tester.pump(const Duration(milliseconds: 650));
    await tester.pump(const Duration(milliseconds: 650));
    expect(find.text('Bước tiếp theo: Chấm điểm'), findsOneWidget);
    expect(find.text('HƯỚNG DẪN GRADEFLOW'), findsOneWidget);
    expect(find.text('Chạm vào vùng sáng để tiếp tục'), findsOneWidget);
    await tester.tap(find.text('Bỏ qua'));
    await tester.pump();
    expect(find.text('Bước tiếp theo: Chấm điểm'), findsNothing);
  });

  testWidgets('focused target navigates once after overlay closes', (tester) async {
    final (context, key) = await mountTarget(tester);
    var visits = 0;
    await CoachMarkService.show(
      context: context, screenKey: 'target_test', force: true,
      onTargetTap: (_) => visits++,
      targets: [CoachMarkService.buildTarget(
        identify: 'scan', key: key, title: 'Chấm điểm',
        description: 'Quét phiếu học sinh.', contentTop: 220,
        shape: ShapeLightFocus.Circle,
      )],
    );
    await tester.pump();
    await tester.pump(const Duration(milliseconds: 650));
    await tester.pump(const Duration(milliseconds: 650));
    await tester.pump(const Duration(milliseconds: 650));
    await tester.tapAt(tester.getCenter(find.byKey(key)));
    await tester.pump();
    await tester.pump(const Duration(milliseconds: 700));
    await tester.pump(const Duration(milliseconds: 700));
    await tester.pump();
    expect(visits, 1);
    expect(find.text('HƯỚNG DẪN GRADEFLOW'), findsNothing);
  });
}
