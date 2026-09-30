import 'dart:convert';
import 'dart:io';
import 'dart:math' as math;
import 'dart:typed_data';
import 'package:flutter/foundation.dart' show compute;
import 'package:flutter_test/flutter_test.dart';
import 'package:image/image.dart' as img;
import 'package:shared_preferences/shared_preferences.dart';
import 'package:gradeflow_app/screens/live_camera_screen.dart';
import 'package:gradeflow_app/services/live_capture.dart';
import 'package:gradeflow_app/services/live_still_detector.dart';
import 'package:gradeflow_app/services/live_speed/capture_engine.dart';
import 'package:gradeflow_app/services/live_speed/engine_preference.dart';
import 'package:gradeflow_app/services/live_speed/native_still_detector.dart';

img.Image sheet(
    {int width = 600,
    int height = 800,
    int? missing,
    bool round = false,
    bool content = true,
    bool ambiguous = false}) {
  final frame = img.Image(width: width, height: height);
  img.fill(frame, color: img.ColorRgb8(230, 230, 230));
  final points = [
    [50, 40],
    [540, 40],
    [540, 730],
    [50, 730]
  ];
  if (ambiguous) points.add([75, 40]);
  for (var i = 0; i < points.length; i++) {
    if (i == missing) continue;
    final x = (points[i][0] * width / 600).round();
    final y = (points[i][1] * height / 800).round();
    final size = (15 * width / 600).round();
    if (round) {
      img.fillCircle(frame,
          x: x + size ~/ 2,
          y: y + size ~/ 2,
          radius: size ~/ 2,
          color: img.ColorRgb8(70, 70, 70));
    } else {
      img.fillRect(frame,
          x1: x,
          y1: y,
          x2: x + size,
          y2: y + size,
          color: img.ColorRgb8(70, 70, 70));
    }
  }
  if (content) {
    for (var y = height ~/ 3; y < height * 2 ~/ 3; y += 18) {
      img.fillRect(frame,
          x1: width ~/ 3,
          y1: y,
          x2: width * 2 ~/ 3,
          y2: y + 2,
          color: img.ColorRgb8(90, 90, 90));
    }
  }
  return frame;
}

Uint8List grayOf(img.Image frame) {
  final gray = Uint8List(frame.width * frame.height);
  for (final p in frame) {
    gray[p.y * frame.width + p.x] = img.getLuminance(p).round();
  }
  return gray;
}

void compareDetection(img.Image frame, {bool? valid}) {
  final gray = grayOf(frame);
  final old = detectStillMarkers(gray, frame.width, frame.height);
  final fast = detectStillMarkersNative(gray, frame.width, frame.height);
  expect(fast.valid, old.valid);
  expect(fast.reason, old.reason);
  expect(fast.candidateCount, old.candidateCount);
  expect(fast.corners, old.corners,
      reason: 'Every marker center must be identical');
  if (valid != null) expect(fast.valid, valid);
}

void expectCaptureEqual(LiveCapture fast, LiveCapture old) {
  expect(fast.width, old.width);
  expect(fast.height, old.height);
  expect(fast.corners, old.corners);
  expect(fast.bytes, orderedEquals(old.bytes),
      reason: 'The server must receive byte-identical JPEG + corners');
}

void main() {
  TestWidgetsFlutterBinding.ensureInitialized();
  test('all existing camera callers default to the stable engine', () {
    expect(const AutoScanScreen().allowSpeedTrial, isFalse);
    expect(LiveEnginePreference.trialDefault, isFalse);
  });
  test('runtime switch persists and can always return to stable', () async {
    SharedPreferences.setMockInitialValues({});
    expect(await LiveEnginePreference.read(), LiveCaptureEngine.legacy);
    await LiveEnginePreference.write(LiveCaptureEngine.nativeMarkers);
    expect(await LiveEnginePreference.read(), LiveCaptureEngine.nativeMarkers);
    await LiveEnginePreference.write(LiveCaptureEngine.legacy);
    expect(await LiveEnginePreference.read(), LiveCaptureEngine.legacy);
  });
  test('legacy selector delegates to unchanged capture implementation',
      () async {
    final raw = Uint8List.fromList(img.encodeJpg(sheet(), quality: 95));
    final result = await compute(prepareLiveCaptureSelected,
        LivePreparationRequest(raw, LiveCaptureEngine.legacy));
    expectCaptureEqual(result.capture, prepareLiveCapture(raw));
    expect(result.engine, 'legacy');
    expect(result.fallbackReason, isNull);
  });
  test('profiling copy stays byte-identical to stable implementation', () {
    final raw = Uint8List.fromList(img.encodeJpg(sheet(), quality: 95));
    final result = profileCapturePreparation(raw, nativeMarkers: false);
    expectCaptureEqual(result.capture, prepareLiveCapture(raw));
    expect(result.timingsUs.keys,
        containsAll(['decode', 'markers', 'encode', 'total']));
  });

  // These tests require REAL OpenCV, not a mocked detector. Do not skip silently
  // when the DLL is missing; use the documented native test environment.
  group('native OpenCV equivalence', () {
    test('valid markers, content and ambiguous quartet', () {
      compareDetection(sheet(), valid: true);
      compareDetection(sheet(ambiguous: true), valid: false);
    });
    for (var missing = 0; missing < 4; missing++) {
      test('missing corner $missing is rejected', () {
        compareDetection(sheet(missing: missing), valid: false);
      });
    }
    for (final blur in [0, 1, 2]) {
      test('round bubbles stay rejected under blur $blur', () {
        final frame = sheet(round: true);
        if (blur > 0) img.gaussianBlur(frame, radius: blur);
        compareDetection(frame, valid: false);
      });
    }
    test('blank, invalid and edge-clipped images', () {
      expect(detectStillMarkersNative(Uint8List(1), 600, 800).valid, isFalse);
      final blank = img.Image(width: 600, height: 800);
      img.fill(blank, color: img.ColorRgb8(230, 230, 230));
      compareDetection(blank, valid: false);
      compareDetection(
          img.copyCrop(sheet(), x: 57, y: 0, width: 543, height: 800),
          valid: false);
    });
    test('content validation is never bypassed by native detection', () {
      final raw = Uint8List.fromList(img.encodeJpg(sheet(content: false)));
      expect(() => profileCapturePreparation(raw, nativeMarkers: true),
          throwsFormatException);
      expect(
          () => prepareLiveCaptureSelected(
              LivePreparationRequest(raw, LiveCaptureEngine.nativeMarkers)),
          throwsFormatException);
    });
    test('exposure gradient, JPEG, blur, rotation preserve decisions', () {
      for (final angle in [-6, 0, 6]) {
        var frame = sheet();
        for (final p in frame) {
          final factor = 0.55 + p.x / frame.width * 0.4;
          p.r = (p.r * factor).round();
          p.g = (p.g * factor).round();
          p.b = (p.b * factor).round();
        }
        frame.backgroundColor = img.ColorRgb8(210, 210, 210);
        frame = img.copyRotate(frame,
            angle: angle, interpolation: img.Interpolation.linear);
        img.gaussianBlur(frame, radius: 1);
        frame = img.decodeJpg(img.encodeJpg(frame, quality: 85))!;
        compareDetection(frame);
      }
    });
    test('seeded noise and threshold boundary images match exactly', () {
      final random = math.Random(42);
      for (var trial = 0; trial < 8; trial++) {
        final frame = sheet(width: 360, height: 480);
        for (final p in frame) {
          final value = (p.r - random.nextInt(45)).clamp(0, 255);
          p.r = value;
          p.g = value;
          p.b = value;
        }
        compareDetection(frame);
      }
    });
    test('EXIF orientations 1-8 preserve image/corners and JPEG bytes',
        () async {
      for (var orientation = 1; orientation <= 8; orientation++) {
        var frame = sheet();
        if (orientation >= 5) frame = img.copyRotate(frame, angle: -90);
        frame.exif.imageIfd.orientation = orientation;
        final raw = Uint8List.fromList(img.encodeJpg(frame, quality: 95));
        final old = prepareLiveCapture(raw);
        final result = await compute(prepareLiveCaptureSelected,
            LivePreparationRequest(raw, LiveCaptureEngine.nativeMarkers));
        expect(result.engine, 'native_markers_v1',
            reason: result.fallbackReason);
        expectCaptureEqual(result.capture, old);
      }
    });
    test('real unannotated fixtures: parity, timings, repeated calls', () {
      final records = <Map<String, Object?>>[];
      for (final name in [
        'exam_import_capture_20260912.jpg',
        'exam_import_v1.jpg'
      ]) {
        final file = File('../tests/fixtures/$name');
        expect(file.existsSync(), isTrue,
            reason: 'Required real source fixture missing');
        final raw = file.readAsBytesSync();
        final old = prepareLiveCapture(raw);
        for (var iteration = 0; iteration < 3; iteration++) {
          final baseline = profileCapturePreparation(raw, nativeMarkers: false);
          final fast = profileCapturePreparation(raw, nativeMarkers: true);
          expectCaptureEqual(baseline.capture, old);
          expectCaptureEqual(fast.capture, old);
          records.add({
            'fixture': name,
            'iteration': iteration,
            'legacyUs': baseline.timingsUs,
            'nativeUs': fast.timingsUs,
            'identicalJpegAndCorners': true
          });
        }
      }
      const output = String.fromEnvironment('LIVE_SPEED_REPORT');
      if (output.isNotEmpty) {
        File(output).parent.createSync(recursive: true);
        File(output)
            .writeAsStringSync(const JsonEncoder.withIndent('  ').convert({
          'platform': Platform.operatingSystem,
          'runtime': 'Flutter desktop test/JIT, NOT Android release',
          'records': records,
        }));
      }
      // Timing is reported, not asserted on noisy CI/desktop hardware.
      print('LIVE_SPEED_BENCHMARK ${jsonEncode(records)}');
    });
  });
}
