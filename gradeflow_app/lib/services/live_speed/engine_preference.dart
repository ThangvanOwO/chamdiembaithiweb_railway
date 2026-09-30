import 'package:shared_preferences/shared_preferences.dart';
import 'capture_engine.dart' show LiveCaptureEngine;

/// Normal builds stay on the stable engine. An explicitly marked trial APK may
/// opt in by default; the user's runtime choice always wins on supported builds.
class LiveEnginePreference {
  static const key = 'live_capture_native_markers_v1';
  static const trialDefault =
      bool.fromEnvironment('LIVE_SPEED_TRIAL', defaultValue: false);
  static const disabled =
      bool.fromEnvironment('LIVE_SPEED_DISABLED', defaultValue: false);

  static Future<LiveCaptureEngine> read() async {
    if (disabled) return LiveCaptureEngine.legacy;
    final prefs = await SharedPreferences.getInstance();
    return (prefs.getBool(key) ?? trialDefault)
        ? LiveCaptureEngine.nativeMarkers
        : LiveCaptureEngine.legacy;
  }

  static Future<void> write(LiveCaptureEngine engine) async {
    final prefs = await SharedPreferences.getInstance();
    if (!await prefs.setBool(key, engine == LiveCaptureEngine.nativeMarkers)) {
      throw StateError('Không lưu được lựa chọn bộ xử lý.');
    }
  }
}
