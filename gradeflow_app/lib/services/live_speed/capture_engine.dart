import 'dart:typed_data';
import 'package:image/image.dart' as img;
import '../live_capture.dart';
import '../live_still_detector.dart';
import 'native_still_detector_stub.dart'
    if (dart.library.io) 'native_still_detector.dart';

enum LiveCaptureEngine { legacy, nativeMarkers }

class LivePreparationRequest {
  final Uint8List bytes;
  final LiveCaptureEngine engine;
  const LivePreparationRequest(this.bytes, this.engine);
}

/// Only Dart-owned buffers cross the worker isolate boundary.
class LivePreparationResult {
  final LiveCapture capture;
  final String engine;
  final Map<String, int> timingsUs;
  final String? fallbackReason;
  const LivePreparationResult(this.capture, this.engine, this.timingsUs,
      {this.fallbackReason});
}

/// Preserve both failures across compute() so a native loader/runtime failure
/// can disable the trial even when the stable engine also rejects the photo.
class LivePreparationFailure extends FormatException {
  final String nativeReason;
  final String stableReason;
  final bool disableTrial;
  const LivePreparationFailure(
      super.message, this.nativeReason, this.stableReason,
      {required this.disableTrial});
}

/// Called inside compute(), never on the UI isolate. Native load/processing
/// failure retries the SAME input once with the unchanged stable engine.
LivePreparationResult prepareLiveCaptureSelected(
    LivePreparationRequest request) {
  final total = Stopwatch()..start();
  if (request.engine == LiveCaptureEngine.legacy) {
    final capture = prepareLiveCapture(request.bytes);
    return LivePreparationResult(
        capture, 'legacy', {'total': total.elapsedMicroseconds});
  }
  try {
    return profileCapturePreparation(request.bytes, nativeMarkers: true);
  } catch (error) {
    final failedUs = total.elapsedMicroseconds;
    // Do not submit stale corners or weaken validation on failure.
    final LiveCapture capture;
    try {
      capture = prepareLiveCapture(request.bytes);
    } catch (stableError) {
      throw LivePreparationFailure(
          stableError is FormatException
              ? stableError.message
              : 'Không xử lý được ảnh. Vui lòng chụp lại.',
          '${error.runtimeType}: $error',
          '$stableError',
          disableTrial: error is! FormatException);
    }
    return LivePreparationResult(
        capture,
        'legacy_fallback',
        {
          'nativeFailed': failedUs,
          'total': total.elapsedMicroseconds,
        },
        fallbackReason: '${error.runtimeType}: $error');
  }
}

/// Byte-preserving optimization stage: decode, EXIF, nearest-neighbor resize,
/// luminance, body validation and JPEG encoding intentionally match the legacy
/// function. Only marker component extraction is accelerated. Do not replace
/// codecs here without full OMR equivalence tests on unannotated source images.
LivePreparationResult profileCapturePreparation(Uint8List raw,
    {required bool nativeMarkers}) {
  final total = Stopwatch()..start();
  final stage = Stopwatch()..start();
  final timings = <String, int>{};
  void lap(String name) {
    timings[name] = stage.elapsedMicroseconds;
    stage.reset();
  }

  img.Image? decoded;
  try {
    decoded = img.decodeImage(raw);
  } catch (_) {
    throw const FormatException('Ảnh chụp không đọc được.');
  }
  if (decoded == null) throw const FormatException('Ảnh chụp không đọc được.');
  lap('decode');
  var upright = img.bakeOrientation(decoded);
  upright.exif = img.ExifData();
  if (upright.width > 2000) upright = img.copyResize(upright, width: 2000);
  final sample =
      upright.width > 1000 ? img.copyResize(upright, width: 1000) : upright;
  final gray = Uint8List(sample.width * sample.height);
  for (final pixel in sample) {
    gray[pixel.y * sample.width + pixel.x] = img.getLuminance(pixel).round();
  }
  lap('orientResizeGray');
  final detection = nativeMarkers
      ? detectStillMarkersNative(gray, sample.width, sample.height,
          onStage: (name, us) => timings[name] = (timings[name] ?? 0) + us)
      : detectStillMarkers(gray, sample.width, sample.height);
  lap('markers');
  if (!detection.valid) {
    throw LiveCaptureException(
        'Ảnh vừa chụp chưa rõ đủ 4 góc. Hãy để toàn bộ phiếu trong camera và chụp lại.',
        '${detection.reason}: ${detection.candidateCount} candidates');
  }
  final body = <int>[];
  for (var y = sample.height ~/ 4; y < sample.height * 3 ~/ 4; y += 3) {
    for (var x = sample.width ~/ 4; x < sample.width * 3 ~/ 4; x += 3) {
      body.add(gray[y * sample.width + x]);
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
  final corners = [
    for (final p in detection.corners) [p.dx * sx, p.dy * sy]
  ];
  lap('validate');
  final jpeg = Uint8List.fromList(img.encodeJpg(upright, quality: 95));
  lap('encode');
  timings['total'] = total.elapsedMicroseconds;
  return LivePreparationResult(
      LiveCapture(jpeg, corners, upright.width, upright.height),
      nativeMarkers ? 'native_markers_v1' : 'legacy_profile',
      timings);
}
