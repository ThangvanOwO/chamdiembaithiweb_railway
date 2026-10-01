import 'dart:convert';
import 'dart:typed_data';
import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:image/image.dart' as img;
import 'package:gradeflow_app/models/grade_result.dart';
import 'package:gradeflow_app/screens/training_sheet_screen.dart';
import 'package:gradeflow_app/services/api_service.dart';
import 'package:gradeflow_app/widgets/training_label_editor.dart';

class SheetApi extends ApiService {
  SheetApi() : super(token: 'fixture');
  bool aligned = true, review = true;
  List<Map<String, dynamic>>? saved;
  Uint8List? original;
  @override
  Future<Map<String, dynamic>> previewTrainingSheet(
          {required Uint8List imageBytes,
          required String templateCode,
          required GradeResult result,
          List<List<double>>? corners}) async =>
      {
        'samples': [
          {
            'part': 2,
            'question': 6,
            'subquestion': 'c',
            'preview_token': 'signed',
            'detected': '',
            'needs_review': review,
            'candidate_labels': {'Dung': 'skip', 'Sai': 'empty'},
            'geometry': {
              'aligned': aligned,
              'width': 82,
              'height': 42,
              'radius': 10
            },
            'cells': [
              {'id': 'Dung', 'x': 20, 'y': 20},
              {'id': 'Sai', 'x': 60, 'y': 20}
            ],
            'image_base64':
                base64Encode(img.encodePng(img.Image(width: 82, height: 42))),
          }
        ],
      };
  @override
  Future<Map<String, dynamic>> saveTrainingSheet(
      Uint8List imageBytes, List<Map<String, dynamic>> items) async {
    original = imageBytes;
    saved = items;
    return {'count': items.length, 'duplicates': 0};
  }
}

void main() {
  Future<void> mount(WidgetTester tester, SheetApi api) async {
    tester.view.physicalSize = const Size(480, 1600);
    tester.view.devicePixelRatio = 1;
    addTearDown(tester.view.resetPhysicalSize);
    addTearDown(tester.view.resetDevicePixelRatio);
    await tester.pumpWidget(MaterialApp(
        home: TrainingSheetScreen(
            api: api,
            imageBytes: Uint8List.fromList([1, 2, 3]),
            result: GradeResult(success: true),
            templateCode: '40-08-06')));
    await tester.pumpAndSettle();
  }

  testWidgets(
      'yellow cannot be taken until labels and whole sheet are confirmed',
      (tester) async {
    final api = SheetApi();
    await mount(tester, api);
    expect(
        tester
            .widget<FilledButton>(
                find.widgetWithText(FilledButton, 'Xác nhận & lấy 1 vùng câu'))
            .onPressed,
        isNull);
    await tester.tap(find.text('Chọn vòng tròn thực tế / xác nhận'));
    await tester.pumpAndSettle();
    await tester.tap(find.widgetWithText(FilterChip, 'Đúng'));
    await tester.pumpAndSettle();
    await tester.tap(find.descendant(
        of: find.byType(AlertDialog), matching: find.byType(CheckboxListTile)));
    await tester.pumpAndSettle();
    await tester.tap(find.text('Xác nhận nhãn'));
    await tester.pumpAndSettle();
    expect(find.text('Đã kiểm tra thủ công'), findsOneWidget);
    final checkbox = find.widgetWithText(CheckboxListTile,
        'Tôi đã xem các vùng được chọn và xác nhận toàn bộ dấu tô đúng với ảnh.');
    await tester.ensureVisible(checkbox);
    await tester.tap(checkbox);
    await tester.pump();
    final save = find.widgetWithText(FilledButton, 'Xác nhận & lấy 1 vùng câu');
    await tester.ensureVisible(save);
    await tester.tap(save);
    await tester.pumpAndSettle();
    expect(api.saved!.single['labels'], {'Dung': 'filled', 'Sai': 'empty'});
    expect(api.saved!.single['review_confirmed'], true);
    expect(api.original, Uint8List.fromList([1, 2, 3]));
  });

  testWidgets('misaligned question is excluded and cannot be approved',
      (tester) async {
    final api = SheetApi()..aligned = false;
    await mount(tester, api);
    expect(
        find.text('0/1 vùng được chọn · 0 vùng cần kiểm tra'), findsOneWidget);
    expect(
        tester
            .widget<FilledButton>(
                find.widgetWithText(FilledButton, 'Xác nhận & lấy 0 vùng câu'))
            .onPressed,
        isNull);
    expect(api.saved, isNull);
  });

  testWidgets('independent circle labels retain multiple marks',
      (tester) async {
    Map<String, String> labels = {'A': 'empty', 'C': 'empty'};
    await tester.pumpWidget(MaterialApp(
        home: Scaffold(
            body: StatefulBuilder(
                builder: (ctx, setState) => TrainingLabelEditor(
                    image: img.encodePng(img.Image(width: 82, height: 42)),
                    geometry: const {'width': 82, 'height': 42, 'radius': 10},
                    cells: const [
                      {'id': 'A', 'x': 20, 'y': 20},
                      {'id': 'C', 'x': 60, 'y': 20}
                    ],
                    labels: labels,
                    onChanged: (v) => setState(() => labels = v))))));
    await tester.tap(find.widgetWithText(FilterChip, 'A'));
    await tester.pump();
    await tester.tap(find.widgetWithText(FilterChip, 'C'));
    await tester.pump();
    expect(labels, {'A': 'filled', 'C': 'filled'});
  });
}
