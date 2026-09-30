import 'dart:typed_data';

import 'package:flutter_test/flutter_test.dart';

import 'package:gradeflow_app/services/live_marker_detector.dart';

void main() {
  group('500 ms capture readiness', () {
    final centers = <double>[0.1, 0.1, 0.9, 0.1, 0.1, 1.2, 0.9, 1.2];

    test('becomes ready at 500 ms, not before, independent of FPS', () {
      for (final interval in [50, 100, 250, 500]) {
        final gate = LiveStabilityGate();
        for (var ms = 0; ms < 500; ms += interval) {
          expect(gate.observe(centers, ms), isFalse);
          expect(gate.phase, LiveScanPhase.stabilizing);
        }
        expect(gate.observe(centers, 500), isTrue);
        expect(gate.phase, LiveScanPhase.ready);
        expect(gate.progress, 1);
      }
    });

    test('2 percent hand jitter preserves progress and reaches ready', () {
      final gate = LiveStabilityGate();
      expect(gate.observe(centers, 0), isFalse);
      for (var ms = 100; ms <= 500; ms += 100) {
        final offset = ms % 200 == 0 ? -0.02 : 0.02;
        final jitter = List<double>.of(centers);
        for (var i = 0; i < 8; i += 2) {
          jitter[i] += offset;
        }
        expect(gate.observe(jitter, ms), ms == 500);
        expect(gate.progress, closeTo(ms / 500, 0.001));
      }
    });

    test('brief missing observation pauses instead of zeroing progress', () {
      final gate = LiveStabilityGate();
      gate.observe(centers, 0);
      gate.observe(centers, 100);
      expect(gate.observe(null, 200), isFalse);
      expect(gate.progress, 0.2);
      expect(gate.canCapture(manual: false), isFalse);
      expect(gate.observe(centers, 300), isFalse);
      expect(gate.progress, 0.2); // Missing interval is not counted.
      for (var ms = 400; ms <= 700; ms += 100) {
        expect(gate.observe(centers, ms), ms == 700);
      }
    });

    test('missing current frame never triggers automatic capture', () {
      final gate = LiveStabilityGate();
      for (var ms = 0; ms <= 500; ms += 100) {
        gate.observe(centers, ms);
      }
      expect(gate.canCapture(manual: false), isTrue);
      expect(gate.observe(null, 600), isFalse);
      expect(gate.canCapture(manual: false), isFalse);
      expect(gate.progress, 1);
    });

    test('long gap and large movement invalidate old progress', () {
      final gate = LiveStabilityGate();
      gate.observe(centers, 0);
      gate.observe(centers, 100);
      expect(gate.observe(null, 501), isFalse);
      expect(gate.phase, LiveScanPhase.searching);
      expect(gate.progress, 0);
      gate.observe(centers, 600);
      gate.observe(centers, 700);
      expect(gate.observe(centers.map((v) => v + 0.1).toList(), 800), isFalse);
      expect(gate.progress, 0);
      expect(gate.observe(centers, 2000), isFalse);
      expect(gate.progress, 0);
    });

    test('manual shutter does not wait for readiness or marker detection', () {
      final gate = LiveStabilityGate();
      expect(gate.canCapture(manual: true), isTrue);
      expect(gate.canCapture(manual: false), isFalse);
      gate.observe(centers, 0);
      gate.observe(centers, 100);
      expect(gate.canCapture(manual: true), isTrue);
      expect(gate.canCapture(manual: false), isFalse);
      gate.observe(null, 500);
      expect(gate.canCapture(manual: true), isTrue);
    });
  });
  const width = 600;
  const height = 800;
  const rowStride = width;

  Uint8List frame({List<_Square> squares = const []}) {
    final bytes = Uint8List(width * height)..fillRange(0, width * height, 255);
    for (final square in squares) {
      for (var y = square.y; y < square.y + square.size; y++) {
        for (var x = square.x; x < square.x + square.size; x++) {
          if (x >= 0 && x < width && y >= 0 && y < height) {
            bytes[y * rowStride + x] = 0;
          }
        }
      }
    }
    return bytes;
  }

  List<_Square> validMarkers() => const [
        _Square(29, 32, 24),
        _Square(527, 32, 24),
        _Square(29, 696, 24),
        _Square(527, 696, 24),
      ];

  Map<String, dynamic> detect(Uint8List bytes) => detectLiveMarkers({
        'yBytes': bytes,
        'rowStride': rowStride,
        'sensorW': width,
        'sensorH': height,
        'sqSizeRatio': liveMarkerRoiRatio,
        'corners': liveMarkerCornerRatios,
      });

  test('accepts four solid markers with expected page geometry', () {
    final result = detect(frame(squares: validMarkers()));

    expect(result['match'], isTrue);
    expect((result['matchedCorners'] as Map).values, everyElement(isTrue));
    expect((result['markerCentersLogical'] as List).length, 8);
  });

  test('rejects an empty frame', () {
    final result = detect(frame());

    expect(result['match'], isFalse);
    expect(result['rejectReason'], 'marker_candidate_missing');
  });

  test('rejects sparse dark noise in the corner ROIs', () {
    final result = detect(frame(
      squares: const [
        _Square(35, 38, 4),
        _Square(533, 38, 4),
        _Square(35, 702, 4),
        _Square(533, 702, 4),
      ],
    ));

    expect(result['match'], isFalse);
  });

  test('recognizes grey markers under exposure changes', () {
    final bytes = frame(squares: validMarkers());
    for (var i = 0; i < bytes.length; i++) {
      bytes[i] = bytes[i] == 0 ? 94 : 210;
    }
    expect(detect(bytes)['match'], isTrue);
  });

  test('four round filled bubbles are not square markers', () {
    final bytes = frame();
    for (final square in validMarkers()) {
      for (var dy = 0; dy < square.size; dy++) {
        for (var dx = 0; dx < square.size; dx++) {
          final cx = dx - square.size / 2;
          final cy = dy - square.size / 2;
          if (cx * cx + cy * cy < square.size * square.size / 4) {
            bytes[(square.y + dy) * width + square.x + dx] = 40;
          }
        }
      }
    }
    expect(detect(bytes)['match'], isFalse);
  });

  test('uniform dark ROI rejects without throwing clamp exception', () {
    expect(detect(Uint8List(width * height))['match'], isFalse);
  });

  test('truncated frame and invalid row stride reject safely', () {
    expect(detect(Uint8List(5))['match'], isFalse);
    expect(
        detectLiveMarkers({
          'yBytes': frame(),
          'sensorW': width,
          'sensorH': height,
          'rowStride': 1
        })['match'],
        isFalse);
  });

  test('rotated buffers and padded rows map to the same asymmetric centers',
      () {
    final upright = frame(squares: validMarkers());
    final expected = detect(upright)['markerCentersLogical'];
    for (final rotation in [90, 270]) {
      const sw = height, sh = width, stride = height + 16;
      final bytes = Uint8List(stride * sh)..fillRange(0, stride * sh, 255);
      for (var y = 0; y < height; y++) {
        for (var x = 0; x < width; x++) {
          final px = rotation == 90 ? y : sw - 1 - y;
          final py = rotation == 90 ? sh - 1 - x : x;
          bytes[py * stride + px] = upright[y * width + x];
        }
      }
      final result = detectLiveMarkers({
        'yBytes': bytes,
        'rowStride': stride,
        'sensorW': sw,
        'sensorH': sh,
        'rotationDegrees': rotation
      });
      expect(result['match'], isTrue);
      expect(result['markerCentersLogical'], expected);
    }
  });

  test(
      'rejects one oversized object even when all four ROIs contain dark pixels',
      () {
    final markers = validMarkers()
        .map((square) =>
            square == validMarkers().first ? const _Square(20, 23, 48) : square)
        .toList();
    final result = detect(frame(squares: markers));

    expect(result['match'], isFalse);
    expect(result['rejectReason'], isNotNull);
  });

  test('rejects marker-size mismatch instead of selecting a false positive',
      () {
    final markers = validMarkers()
        .map((square) =>
            square == validMarkers()[1] ? const _Square(535, 40, 10) : square)
        .toList();
    final result = detect(frame(squares: markers));

    expect(result['match'], isFalse);
  });
}

class _Square {
  final int x;
  final int y;
  final int size;

  const _Square(this.x, this.y, this.size);

  @override
  bool operator ==(Object other) =>
      other is _Square && x == other.x && y == other.y && size == other.size;

  @override
  int get hashCode => Object.hash(x, y, size);
}
