import 'dart:typed_data';
import 'package:image/image.dart' as img;
import 'live_still_detector.dart';

/// Immutable image/geometry pair. Coordinates refer to the encoded JPEG,
/// after orientation and resize, in TL, TR, BR, BL order.
class LiveCapture {
  final Uint8List bytes;
  final List<List<double>> corners;
  final int width;
  final int height;

  LiveCapture(
      Uint8List image, List<List<double>> points, this.width, this.height)
      : bytes = image.asUnmodifiableView(),
        corners =
            List.unmodifiable(points.map((p) => List<double>.unmodifiable(p)));
}

/// Runs in a worker isolate for both automatic and manual capture. No warp:
/// the server warps once, using these measured corners instead of re-detection.
LiveCapture prepareLiveCapture(Uint8List raw) {
  img.Image? decoded;
  try {
    decoded = img.decodeImage(raw);
  } catch (_) {
    throw const FormatException('Ảnh chụp không đọc được.');
  }
  if (decoded == null) throw const FormatException('Ảnh chụp không đọc được.');
  var upright = img.bakeOrientation(decoded);
  // Discard orientation and private camera metadata after baking it once.
  upright.exif = img.ExifData();
  if (upright.width > 2000) upright = img.copyResize(upright, width: 2000);
  final sample =
      upright.width > 1000 ? img.copyResize(upright, width: 1000) : upright;
  final y = Uint8List(sample.width * sample.height);
  for (final p in sample) {
    y[p.y * sample.width + p.x] = img.getLuminance(p).round();
  }
  final result = detectStillMarkers(y, sample.width, sample.height);
  if (!result.valid) {
    throw LiveCaptureException(
        'Ảnh vừa chụp chưa rõ đủ 4 góc. Hãy để toàn bộ '
            'phiếu trong camera và chụp lại.',
        '${result.reason}: ${result.candidateCount} candidates');
  }
  // Four squares on a blank background are not enough evidence of a sheet.
  final body = <int>[];
  for (var sy = sample.height ~/ 4; sy < sample.height * 3 ~/ 4; sy += 3) {
    for (var sx = sample.width ~/ 4; sx < sample.width * 3 ~/ 4; sx += 3) {
      final index = sy * sample.width + sx;
      body.add(y[index]);
    }
  }
  body.sort();
  final background = body.isEmpty ? 0 : body[body.length * 3 ~/ 4];
  final ink = body.where((value) => value < background - 40).length;
  if (body.isEmpty || ink / body.length < 0.005 || ink / body.length > 0.65) {
    throw const FormatException(
        'Vùng nội dung phiếu không rõ. Kiểm tra ánh sáng và lấy nét.');
  }
  final sx = upright.width / sample.width;
  final sy = upright.height / sample.height;
  final points = [
    for (final p in result.corners) [p.dx * sx, p.dy * sy]
  ];
  return LiveCapture(Uint8List.fromList(img.encodeJpg(upright, quality: 95)),
      points, upright.width, upright.height);
}

class LiveCaptureException extends FormatException {
  final String diagnostic;
  const LiveCaptureException(super.message, this.diagnostic);
}

/// Bounds automatic retries, not manual shutter latency or preview readiness.
class LiveCaptureRetryPolicy {
  static const cooldownMs = 750;
  static const maxAutomaticFailures = 3;
  int _failures = 0;
  int _retryAtMs = 0;
  bool get paused => _failures >= maxAutomaticFailures;
  bool canAttempt({required bool manual, required int nowMs}) =>
      manual || (!paused && nowMs >= _retryAtMs);

  void failed({required bool manual, required int nowMs}) {
    // A failed manual attempt must not immediately trigger an automatic one.
    _failures = manual ? maxAutomaticFailures : _failures + 1;
    _retryAtMs = nowMs + cooldownMs;
  }

  void reset() {
    _failures = 0;
    _retryAtMs = 0;
  }
}
