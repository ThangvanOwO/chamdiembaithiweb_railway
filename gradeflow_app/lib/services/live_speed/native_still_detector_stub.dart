import 'dart:typed_data';
import '../live_still_detector.dart' show LiveStillDetection;

/// Do not pull dart:ffi/OpenCV into the existing Flutter web/gallery build.
LiveStillDetection detectStillMarkersNative(
    Uint8List gray, int width, int height,
    {void Function(String)? trace, void Function(String, int)? onStage}) {
  throw UnsupportedError('Native Live acceleration is unavailable on web.');
}
