import 'dart:convert';
import 'dart:io';
import 'dart:math' as math;
import 'dart:typed_data';
import 'package:flutter/foundation.dart' show compute;
import 'package:flutter_test/flutter_test.dart';
import 'package:http/http.dart' as http;
import 'package:http/testing.dart';
import 'package:image/image.dart' as img;
import 'package:gradeflow_app/services/live_capture.dart';
import 'package:gradeflow_app/services/live_grading_service.dart';
import 'package:gradeflow_app/services/live_marker_detector.dart';
import 'package:gradeflow_app/services/live_still_detector.dart';

void main() {
  test('bounded auto retry never blocks the manual shutter', () {
    final policy = LiveCaptureRetryPolicy();
    policy.failed(manual: false, nowMs: 100);
    expect(policy.canAttempt(manual: false, nowMs: 849), isFalse);
    expect(policy.canAttempt(manual: false, nowMs: 850), isTrue);
    expect(policy.canAttempt(manual: true, nowMs: 101), isTrue);
    policy.failed(manual: false, nowMs: 900);
    policy.failed(manual: false, nowMs: 1800);
    expect(policy.paused, isTrue);
    expect(policy.canAttempt(manual: false, nowMs: 10000), isFalse);
    expect(policy.canAttempt(manual: true, nowMs: 1801), isTrue);
    policy.reset();
    expect(policy.canAttempt(manual: false, nowMs: 1801), isTrue);
    policy.failed(manual: true, nowMs: 2000);
    expect(policy.paused, isTrue);
  });

  test('four squares without sheet content cannot be submitted', () {
    final frame = img.Image(width: 600, height: 800);
    img.fill(frame, color: img.ColorRgb8(230, 230, 230));
    for (final p in [
      [50, 40],
      [540, 40],
      [540, 730],
      [50, 730]
    ]) {
      img.fillRect(frame,
          x1: p[0],
          y1: p[1],
          x2: p[0] + 15,
          y2: p[1] + 15,
          color: img.ColorRgb8(50, 50, 50));
    }
    expect(() => prepareLiveCapture(Uint8List.fromList(img.encodeJpg(frame))),
        throwsFormatException);
  });

  test('still detector rejects blank, malformed and ambiguous quartets', () {
    expect(detectStillMarkers(Uint8List(1), 600, 800).valid, isFalse);
    final gray = Uint8List(600 * 800)..fillRange(0, 600 * 800, 230);
    expect(detectStillMarkers(gray, 600, 800).valid, isFalse);
    // Two equally plausible TL markers. Do not pick one just by iteration order.
    for (final p in [
      [50, 40],
      [75, 40],
      [540, 40],
      [540, 730],
      [50, 730]
    ]) {
      for (var y = p[1]; y < p[1] + 16; y++) {
        gray.fillRange(y * 600 + p[0], y * 600 + p[0] + 16, 50);
      }
    }
    expect(detectStillMarkers(gray, 600, 800).reason, 'ambiguous_quad');
  });

  test('multi-threshold still detection rejects round bubbles even with blur',
      () {
    for (final radius in [5, 7, 10, 14]) {
      for (final blur in [0, 1, 2]) {
        final frame = img.Image(width: 600, height: 800);
        img.fill(frame, color: img.ColorRgb8(230, 230, 230));
        for (final p in [
          [50, 40],
          [540, 40],
          [540, 730],
          [50, 730]
        ]) {
          img.fillCircle(frame,
              x: p[0],
              y: p[1],
              radius: radius,
              color: img.ColorRgb8(70, 70, 70));
        }
        if (blur > 0) img.gaussianBlur(frame, radius: blur);
        final gray = Uint8List(frame.width * frame.height);
        for (final p in frame) {
          gray[p.y * frame.width + p.x] = img.getLuminance(p).round();
        }
        expect(
            detectStillMarkers(gray, frame.width, frame.height).valid, isFalse,
            reason: 'radius=$radius blur=$blur');
      }
    }
  });
  test('Live multipart preserves the JPEG and its pixel coordinate system',
      () async {
    final bytes = Uint8List(900 * 1024)..fillRange(0, 900 * 1024, 83);
    final capture = LiveCapture(
        bytes,
        [
          [60, 50],
          [650, 50],
          [640, 880],
          [60, 880]
        ],
        709,
        949);
    final client = MockClient((request) async {
      final body = latin1.decode(request.bodyBytes);
      expect(body, contains(jsonEncode(capture.corners)));
      expect(body, contains(latin1.decode(bytes)));
      expect(body, contains('name="corners"'));
      expect(body, contains('name="capture_pipeline"'));
      expect(body, contains('live_capture_v3'));
      expect(request.headers['Authorization'], 'Token test-token');
      return http.Response('{"success":false,"error":"fixture"}', 200);
    });
    await gradeLiveCapture(
        token: 'test-token', capture: capture, client: client);
    client.close();
  });

  test('invalid JPEG is rejected before upload', () {
    expect(() => prepareLiveCapture(Uint8List(0)), throwsFormatException);
  });

  test('EXIF rotation is applied once in the capture worker isolate', () async {
    final raw = img.Image(width: 600, height: 800);
    img.fill(raw, color: img.ColorRgb8(230, 230, 230));
    for (final p in [
      [50, 40],
      [540, 40],
      [50, 730],
      [540, 730]
    ]) {
      img.fillRect(raw,
          x1: p[0],
          y1: p[1],
          x2: p[0] + 15,
          y2: p[1] + 15,
          color: img.ColorRgb8(90, 90, 90));
    }
    for (var y = 260; y < 500; y += 18) {
      img.fillRect(raw,
          x1: 170, y1: y, x2: 400, y2: y + 2, color: img.ColorRgb8(90, 90, 90));
    }
    final landscape = img.copyRotate(raw, angle: -90);
    landscape.exif.imageIfd.orientation = 6;
    final capture = await compute(prepareLiveCapture,
        Uint8List.fromList(img.encodeJpg(landscape, quality: 95)));
    expect(capture.width, 600);
    expect(capture.height, 800);
    final decoded = img.decodeJpg(capture.bytes)!;
    expect(decoded.width, 600);
    expect(decoded.exif.imageIfd.hasOrientation, isFalse);
    img.fillRect(raw,
        x1: 535, y1: 35, x2: 570, y2: 65, color: img.ColorRgb8(230, 230, 230));
    expect(() => prepareLiveCapture(Uint8List.fromList(img.encodeJpg(raw))),
        throwsFormatException,
        reason: 'Manual capture must not upload with a missing marker');
  });

  const screenshotPath = String.fromEnvironment('LIVE_SCREENSHOT');
  test(
      'real screenshot: grey markers survive preview and captured-JPEG validation',
      () {
    final screenshot = img.decodeImage(File(screenshotPath).readAsBytesSync())!;
    // Camera viewport bounds measured on the supplied 1220x2712 screenshot.
    final frame =
        img.copyCrop(screenshot, x: 0, y: 449, width: 1220, height: 1627);
    final y = Uint8List(frame.width * frame.height);
    for (final pixel in frame) {
      y[pixel.y * frame.width + pixel.x] = img.getLuminance(pixel).round();
    }
    final detection = detectLiveMarkers({
      'yBytes': y,
      'rowStride': frame.width,
      'sensorW': frame.width,
      'sensorH': frame.height,
      'rotationDegrees': 0
    });
    expect(detection['match'], isTrue, reason: '$detection');
    final capture = prepareLiveCapture(
        Uint8List.fromList(img.encodeJpg(frame, quality: 95)));
    expect(capture.corners.length, 4);
    expect(capture.corners[1][1], closeTo(capture.corners[0][1], 15));
  },
      skip: screenshotPath.isEmpty
          ? 'Supply --dart-define=LIVE_SCREENSHOT=<path>'
          : false);

  const overlayPath = String.fromEnvironment('LIVE_OVERLAY');
  test(
      'real sheet: each missing outer marker must reject, not use inner squares',
      () {
    for (final p in [
      [60, 52],
      [656, 54],
      [644, 881],
      [64, 881]
    ]) {
      final frame = img.decodeImage(File(overlayPath).readAsBytesSync())!;
      img.fillRect(frame,
          x1: p[0] - 15,
          y1: p[1] - 15,
          x2: p[0] + 15,
          y2: p[1] + 15,
          color: img.ColorRgb8(225, 225, 225));
      expect(() => prepareLiveCapture(Uint8List.fromList(img.encodeJpg(frame))),
          throwsFormatException,
          reason: 'missing corner $p');
    }
  }, skip: overlayPath.isEmpty ? 'Supply LIVE_OVERLAY fixture' : false);
  for (final spec in [
    (scale: 0.8, dx: 35, dy: 40, angle: 0.0, blur: 0),
    (scale: 0.9, dx: 55, dy: 50, angle: 0.0, blur: 1),
    (scale: 1.0, dx: 0, dy: 0, angle: 6.0, blur: 1),
    (scale: 1.0, dx: 0, dy: 0, angle: -6.0, blur: 1),
  ]) {
    test('real sheet framing/rotation regression: $spec', () {
      final source = img.decodeImage(File(overlayPath).readAsBytesSync())!;
      final resized =
          img.copyResize(source, width: (source.width * spec.scale).round());
      var frame = img.Image(width: source.width, height: source.height);
      img.fill(frame, color: img.ColorRgb8(230, 230, 230));
      img.compositeImage(frame, resized, dstX: spec.dx, dstY: spec.dy);
      final rad = spec.angle * math.pi / 180;
      final cos = math.cos(rad), sin = math.sin(rad);
      final dw = (source.width * cos).abs() + (source.height * sin).abs();
      final dh = (source.width * sin).abs() + (source.height * cos).abs();
      frame.backgroundColor = img.ColorRgb8(230, 230, 230);
      frame = img.copyRotate(frame,
          angle: spec.angle, interpolation: img.Interpolation.linear);
      if (spec.blur > 0) img.gaussianBlur(frame, radius: spec.blur);
      final bytes = Uint8List.fromList(img.encodeJpg(frame, quality: 90));
      late LiveCapture capture;
      try {
        capture = prepareLiveCapture(bytes);
      } on LiveCaptureException catch (e) {
        final decoded = img.decodeJpg(bytes)!;
        final gray = Uint8List(decoded.width * decoded.height);
        for (final p in decoded) {
          gray[p.y * decoded.width + p.x] = img.getLuminance(p).round();
        }
        detectStillMarkers(gray, decoded.width, decoded.height,
            trace: (message) => print(message));
        fail(e.diagnostic);
      }
      const original = [
        [60, 52],
        [656, 54],
        [644, 881],
        [64, 881]
      ];
      for (var i = 0; i < 4; i++) {
        final x = original[i][0] * resized.width / source.width + spec.dx;
        final y = original[i][1] * resized.height / source.height + spec.dy;
        final ex = (x - source.width / 2) * cos -
            (y - source.height / 2) * sin +
            dw / 2;
        final ey = (x - source.width / 2) * sin +
            (y - source.height / 2) * cos +
            dh / 2;
        expect(capture.corners[i][0], closeTo(ex, 5), reason: 'corner $i x');
        expect(capture.corners[i][1], closeTo(ey, 5), reason: 'corner $i y');
      }
      if (spec.scale == 0.8) {
        final gray = Uint8List(frame.width * frame.height);
        for (final p in frame) {
          gray[p.y * frame.width + p.x] = img.getLuminance(p).round();
        }
        final old = detectLiveMarkers({
          'yBytes': gray,
          'rowStride': frame.width,
          'sensorW': frame.width,
          'sensorH': frame.height,
          'fullImage': true,
          'sqSizeRatio': 0.25,
          'corners': {
            'TL': [0.0, 0.0],
            'TR': [0.75, 0.0],
            'BL': [0.0, 0.8],
            'BR': [0.75, 0.8]
          },
        });
        expect(old['match'], isFalse,
            reason: 'Fixture must reproduce the retired fixed-ROI failure');
      }
    }, skip: overlayPath.isEmpty ? 'Supply LIVE_OVERLAY fixture' : false);
  }

  test('real failed scan: outer marker coordinates exclude the old skewed quad',
      () {
    final capture = prepareLiveCapture(File(overlayPath).readAsBytesSync());
    const expected = [
      [60, 52],
      [656, 54],
      [644, 881],
      [64, 881]
    ];
    expect(capture.width, 709);
    expect(capture.height, 949);
    const output = String.fromEnvironment('LIVE_REPLAY_OUTPUT');
    if (output.isNotEmpty) {
      Directory(output).createSync(recursive: true);
      File('$output/capture.jpg').writeAsBytesSync(capture.bytes);
      File('$output/capture.json').writeAsStringSync(jsonEncode({
        'width': capture.width,
        'height': capture.height,
        'corners': capture.corners,
        'source': overlayPath,
        'note': 'Annotated historical overlay, geometry replay only',
      }));
    }
    for (var i = 0; i < 4; i++) {
      for (var j = 0; j < 2; j++) {
        expect(capture.corners[i][j], closeTo(expected[i][j], 5));
      }
    }
  },
      skip: overlayPath.isEmpty
          ? 'Supply --dart-define=LIVE_OVERLAY=<path>'
          : false);
}
