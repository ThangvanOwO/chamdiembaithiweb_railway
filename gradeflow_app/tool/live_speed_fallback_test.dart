// Run explicitly with DARTCV_LIB_PATH pointing to a nonexistent test DLL.
// Kept outside test/ so normal native tests never silently skip this case.
import 'dart:io';
import 'dart:typed_data';
import 'package:flutter/foundation.dart' show compute;
import 'package:image/image.dart' as img;
import 'package:flutter_test/flutter_test.dart';
import 'package:gradeflow_app/services/live_capture.dart';
import 'package:gradeflow_app/services/live_speed/capture_engine.dart';

void main() {
  test('missing native library falls back to identical stable capture', () {
    final dll = Platform.environment['DARTCV_LIB_PATH'];
    expect(dll, isNotNull);
    expect(File(dll!).existsSync(), isFalse,
        reason: 'This test must exercise a real native loader failure');
    final bytes = File('../tests/fixtures/exam_import_capture_20260912.jpg')
        .readAsBytesSync();
    final stable = prepareLiveCapture(bytes);
    final result = prepareLiveCaptureSelected(
        LivePreparationRequest(bytes, LiveCaptureEngine.nativeMarkers));
    expect(result.engine, 'legacy_fallback');
    expect(result.fallbackReason, isNotEmpty);
    expect(result.capture.bytes, orderedEquals(stable.bytes));
    expect(result.capture.corners, stable.corners);
    expect(result.timingsUs['nativeFailed'], greaterThan(0));
  });
  test('fallback cannot turn corrupt input into a successful capture', () {
    expect(
        () => prepareLiveCaptureSelected(LivePreparationRequest(
            Uint8List(0), LiveCaptureEngine.nativeMarkers)),
        throwsFormatException);
  });
  test('native failure survives legacy rejection across worker isolate',
      () async {
    final blank = img.Image(width: 600, height: 800);
    img.fill(blank, color: img.ColorRgb8(230, 230, 230));
    final raw = Uint8List.fromList(img.encodeJpg(blank));
    await expectLater(
        compute(prepareLiveCaptureSelected,
            LivePreparationRequest(raw, LiveCaptureEngine.nativeMarkers)),
        throwsA(isA<LivePreparationFailure>()
            .having(
                (e) => e.disableTrial, 'disables broken native engine', isTrue)
            .having(
                (e) => e.nativeReason, 'native failure retained', isNotEmpty)
            .having((e) => e.stableReason, 'legacy rejection retained',
                isNotEmpty)));
  });
}
