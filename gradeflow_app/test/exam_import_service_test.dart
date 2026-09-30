import 'dart:convert';
import 'dart:io';
import 'dart:typed_data';
import 'package:flutter_test/flutter_test.dart';
import 'package:http/http.dart' as http;
import 'package:gradeflow_app/services/exam_import_service.dart';
import 'package:gradeflow_app/services/live_capture.dart';

class InspectClient extends http.BaseClient {
  final Future<http.StreamedResponse> Function(http.BaseRequest) inspect;
  InspectClient(this.inspect);
  @override
  Future<http.StreamedResponse> send(http.BaseRequest request) => inspect(request);
}

void main() {
  test('import transports exact bytes, dimensions, and corners to parse-image', () async {
    final capture = LiveCapture(Uint8List.fromList([0, 1, 255, 4]),
        [[10, 10], [190, 10], [190, 290], [10, 290]], 200, 300);
    final client = InspectClient((base) async {
      final request = base as http.MultipartRequest;
      expect(request.url.path, '/api/v1/parse-image/');
      expect(request.fields['capture_pipeline'], 'exam_import_capture_v1');
      expect(jsonDecode(request.fields['corners']!), capture.corners);
      expect(request.fields['capture_width'], '200');
      expect(request.fields['capture_height'], '300');
      expect(request.fields.containsKey('save'), isFalse);
      expect(request.files.single.field, 'file');
      expect(await request.files.single.finalize().toBytes(), capture.bytes);
      return http.StreamedResponse(Stream.value(utf8.encode(jsonEncode({
        'success': true, 'data': {'source': 'image', 'note': 'Đáp án'}
      }))), 200);
    });
    final result = await importExamCapture(token: 'test', capture: capture, client: client);
    expect(result['note'], 'Đáp án');
  });

  test('import propagates server validation failure', () async {
    final capture = LiveCapture(Uint8List(1), [[0,0],[1,0],[1,1],[0,1]], 2, 2);
    final client = InspectClient((_) async => http.StreamedResponse(
        Stream.value(utf8.encode('{"error":"Quét lại phiếu"}')), 400));
    await expectLater(importExamCapture(token: 'test', capture: capture, client: client),
        throwsA(predicate((e) => '$e'.contains('Quét lại phiếu'))));
  });

  test('real import capture uses existing unmodified camera preparation', () async {
    final original = File('../tests/fixtures/exam_import_capture_20260912.jpg');
    final capture = prepareLiveCapture(await original.readAsBytes());
    expect(capture.corners.length, 4);
    expect(capture.width, greaterThan(500));
    if (Platform.environment['EXPORT_IMPORT_FIXTURE'] == '1') {
      // Reproducible cross-language fixture from the same code as the phone.
      await File('../tests/fixtures/exam_import_v1.jpg').writeAsBytes(capture.bytes);
      await File('../tests/fixtures/exam_import_v1.json').writeAsString(jsonEncode({
        'capture_pipeline': 'exam_import_capture_v1',
        'corners': jsonEncode(capture.corners),
        'capture_width': '${capture.width}', 'capture_height': '${capture.height}'
      }));
    }
  });
}
