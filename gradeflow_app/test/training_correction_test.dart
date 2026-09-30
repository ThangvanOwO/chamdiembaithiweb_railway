import 'dart:convert';
import 'dart:typed_data';
import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:image/image.dart' as img;
import 'package:gradeflow_app/models/grade_result.dart';
import 'package:gradeflow_app/screens/training_correction_screen.dart';
import 'package:gradeflow_app/services/api_service.dart';

class FakeTrainingApi extends ApiService {
  FakeTrainingApi() : super(token: 'test-only');
  Map<String, String>? savedLabels;
  String? savedToken;
  int? question;
  String? subquestion;
  bool aligned = true;

  @override
  Future<Map<String, dynamic>> previewTrainingQuestion(
      {required Uint8List imageBytes,
      required String templateCode,
      required int part,
      required int question,
      String subquestion = '',
      List<List<double>>? corners}) async {
    this.question = question;
    this.subquestion = subquestion;
    return {
      'preview_token': 'signed-preview-test',
      'detected': '',
      'image_base64':
          base64Encode(img.encodePng(img.Image(width: 82, height: 42))),
      'geometry': {'aligned': aligned},
      'cells': [
        {'id': 'Dung'},
        {'id': 'Sai'}
      ]
    };
  }

  @override
  Future<Map<String, dynamic>> saveTrainingQuestion(
      String previewToken, Map<String, String> labels) async {
    savedLabels = Map.of(labels);
    savedToken = previewToken;
    return {'success': true};
  }
}

void main() {
  Future<FakeTrainingApi> mount(WidgetTester tester) async {
    tester.view.physicalSize = const Size(420, 1200);
    tester.view.devicePixelRatio = 1;
    addTearDown(tester.view.resetPhysicalSize);
    addTearDown(tester.view.resetDevicePixelRatio);
    final api = FakeTrainingApi();
    await tester.pumpWidget(MaterialApp(
        home: TrainingCorrectionScreen(
            api: api,
            imageBytes: Uint8List.fromList([1]),
            templateCode: '40-08-06',
            result: GradeResult(success: true, part1: {
              '1': 'C'
            }, part2: {
              '6': {'a': 'Dung', 'b': 'Dung', 'c': '', 'd': 'Sai'}
            }))));
    return api;
  }

  testWidgets('unread 6c is selected and no label is invented', (tester) async {
    final api = await mount(tester);
    await tester.tap(find.text('Xem ảnh câu đã chọn'));
    await tester.pumpAndSettle();
    expect(api.question, 6);
    expect(api.subquestion, 'c');
    expect(
        tester
            .widget<FilledButton>(
                find.widgetWithText(FilledButton, 'Lưu mẫu câu này'))
            .onPressed,
        isNull);
    expect(tester.widget<CheckboxListTile>(find.byType(CheckboxListTile)).value,
        isFalse);
    expect(api.savedLabels, isNull);
  });

  testWidgets('save requires selected mark and explicit crop confirmation',
      (tester) async {
    final api = await mount(tester);
    await tester.tap(find.text('Xem ảnh câu đã chọn'));
    await tester.pumpAndSettle();
    await tester.tap(find.widgetWithText(ChoiceChip, 'Đúng'));
    await tester.pump();
    expect(
        tester
            .widget<FilledButton>(
                find.widgetWithText(FilledButton, 'Lưu mẫu câu này'))
            .onPressed,
        isNull);
    await tester.ensureVisible(find.byType(CheckboxListTile));
    await tester.tap(find.byType(CheckboxListTile));
    await tester.pump();
    await tester
        .ensureVisible(find.widgetWithText(FilledButton, 'Lưu mẫu câu này'));
    await tester.tap(find.widgetWithText(FilledButton, 'Lưu mẫu câu này'));
    await tester.pumpAndSettle();
    expect(api.savedLabels, {'Dung': 'filled', 'Sai': 'empty'});
    expect(api.savedToken, 'signed-preview-test');
    expect(
        find.text('Đã lưu câu được chọn vào hàng chờ duyệt.'), findsOneWidget);
  });

  testWidgets('changing subquestion invalidates preview and confirmed label',
      (tester) async {
    await mount(tester);
    await tester.tap(find.text('Xem ảnh câu đã chọn'));
    await tester.pumpAndSettle();
    await tester.tap(find.widgetWithText(ChoiceChip, 'Đúng'));
    await tester.pump();
    await tester.tap(find.text('Ý b'));
    await tester.pumpAndSettle();
    expect(find.text('Lưu mẫu câu này'), findsNothing);
    expect(find.byType(CheckboxListTile), findsNothing);
  });

  testWidgets('misaligned crop cannot be confirmed even with complete labels',
      (tester) async {
    final api = await mount(tester);
    api.aligned = false;
    await tester.tap(find.text('Xem ảnh câu đã chọn'));
    await tester.pumpAndSettle();
    await tester.tap(find.widgetWithText(ChoiceChip, 'Đúng'));
    await tester.pump();
    expect(
        tester
            .widget<CheckboxListTile>(find.byType(CheckboxListTile))
            .onChanged,
        isNull);
    expect(
        tester
            .widget<FilledButton>(
                find.widgetWithText(FilledButton, 'Lưu mẫu câu này'))
            .onPressed,
        isNull);
  });
}
