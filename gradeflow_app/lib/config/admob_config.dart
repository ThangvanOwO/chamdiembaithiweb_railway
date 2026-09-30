import 'package:flutter/foundation.dart';

abstract final class AdMobConfig {
  // These IDs belong to the Android app. Other platforms stay ad-free until
  // they have their own platform-specific AdMob configuration.
  static bool get isSupported =>
      !kIsWeb && defaultTargetPlatform == TargetPlatform.android;

  static const useTestAds = !kReleaseMode ||
      bool.fromEnvironment('ADMOB_TEST_ADS', defaultValue: false);

  // Optional UMP scenarios; ignored by releases using real advertising.
  static const umpDebugGeography = useTestAds
      ? String.fromEnvironment('UMP_DEBUG_GEOGRAPHY', defaultValue: 'disabled')
      : 'disabled';
  static const resetTestConsent = useTestAds &&
      bool.fromEnvironment('UMP_RESET_CONSENT', defaultValue: false);

  // Copy the hashed IDs printed by the Ads SDK in logcat, not adb serials.
  // Release builds with real ads never register development devices.
  static List<String> get testDeviceIds => useTestAds
      ? const String.fromEnvironment(
          'ADMOB_TEST_DEVICE_IDS',
          // Verified Ads SDK test ID for the connected 2412DPC0AG phone.
          defaultValue: '40BFB923AB20AB89042D82271ED4BD11',
        )
          .split(',')
          .map((id) => id.trim())
          .where((id) => id.isNotEmpty)
          .toSet()
          .toList(growable: false)
      : const <String>[];

  static const bannerUnitId = useTestAds
      ? 'ca-app-pub-3940256099942544/9214589741'
      : 'ca-app-pub-6695808615282253/5100942496';
  static const interstitialUnitId = useTestAds
      ? 'ca-app-pub-3940256099942544/1033173712'
      : 'ca-app-pub-6695808615282253/2060021199';
  static const rewardedUnitId = useTestAds
      ? 'ca-app-pub-3940256099942544/5224354917'
      : 'ca-app-pub-6695808615282253/6070051413';
}
