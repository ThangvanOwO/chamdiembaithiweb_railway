import 'dart:async';

import 'package:flutter/material.dart';
import 'package:google_mobile_ads/google_mobile_ads.dart';

import '../config/admob_config.dart';
import 'ad_navigation_observer.dart';
import 'tutorial_flow.dart';

class AdService extends ChangeNotifier {
  AdService() {
    navigationObserver = AdNavigationObserver(
      onScreenChanged: _recordScreenChange,
      onSafeTransition: _tryShowInterstitial,
    );
  }

  static final instance = AdService();
  late final AdNavigationObserver navigationObserver;
  bool _sessionActive = false;
  bool _ready = false;
  Future<void>? _consentInitialization;
  bool _sdkInitialized = false;
  bool _loading = false;
  bool _showing = false;
  bool _privacyRequired = false;
  bool _privacyOpen = false;
  bool _disposed = false;
  int _screenChanges = 0;
  int _generation = 0;
  InterstitialAd? _interstitial;
  DateTime? _loadedAt;
  Timer? _retry;

  bool get canLoadAds => _sessionActive && _ready && !_privacyOpen;
  bool get privacyOptionsRequired => _privacyRequired;
  bool get privacyOptionsOpen => _privacyOpen;

  /// Explicit opt-in only; completion is informational, never a credit award.
  Future<bool> showRewarded({String? ticket}) async {
    if (!canLoadAds || _showing) {
      throw Exception('Quảng cáo chưa sẵn sàng. Vui lòng thử lại sau.');
    }
    _showing = true;
    final generation = _generation;
    RewardedAd? loaded;
    var abandoned = false;
    try {
      final loading = Completer<RewardedAd>();
      await RewardedAd.load(
        adUnitId: AdMobConfig.rewardedUnitId,
        request: const AdRequest(),
        rewardedAdLoadCallback: RewardedAdLoadCallback(
          onAdLoaded: (ad) {
            if (abandoned) {
              ad.dispose();
              return;
            }
            loading.complete(ad);
          },
          onAdFailedToLoad: (_) {
            if (!abandoned) {
              loading.completeError(
                  Exception('Hiện chưa có quảng cáo. Vui lòng thử lại sau.'));
            }
          },
        ),
      );
      loaded = await loading.future.timeout(const Duration(seconds: 25));
      if (generation != _generation || !canLoadAds) {
        throw Exception('Phiên quảng cáo đã kết thúc.');
      }
      if (ticket != null) {
        await loaded.setServerSideOptions(
            ServerSideVerificationOptions(customData: ticket));
      }
      final done = Completer<bool>();
      var earned = false;
      loaded.fullScreenContentCallback = FullScreenContentCallback(
        onAdDismissedFullScreenContent: (_) {
          if (!done.isCompleted) done.complete(earned);
        },
        onAdFailedToShowFullScreenContent: (_, error) {
          if (!done.isCompleted) {
            done.completeError(Exception('Không mở được quảng cáo.'));
          }
        },
      );
      if (generation != _generation || !canLoadAds) {
        throw Exception('Phiên quảng cáo đã kết thúc.');
      }
      await loaded.show(onUserEarnedReward: (ad, reward) => earned = true);
      return await done.future;
    } finally {
      abandoned = true;
      loaded?.dispose();
      _showing = false;
      unawaited(_loadInterstitial());
    }
  }

  /// Refresh UMP once per app launch, even before the teacher logs in.
  Future<void> initializeConsent() {
    if (_disposed || !AdMobConfig.isSupported) return Future<void>.value();
    return _consentInitialization ??= _initialize();
  }

  void startSession() {
    if (_disposed || !AdMobConfig.isSupported || _sessionActive) return;
    _sessionActive = true;
    _ready = false;
    unawaited(_startAdvertisingSession());
  }

  Future<void> _startAdvertisingSession() async {
    await initializeConsent();
    if (_disposed || !_sessionActive || _ready) return;
    try {
      await _refreshConsent();
    } catch (error) {
      debugPrint('AdMob consent refresh: $error');
    }
  }

  void endSession() {
    _sessionActive = false;
    _ready = false;
    _screenChanges = 0;
    _clearInterstitial();
    if (!_disposed) notifyListeners();
  }

  Future<void> _initialize() async {
    try {
      if (AdMobConfig.resetTestConsent) {
        await ConsentInformation.instance.reset();
      }
      if (_disposed) return;
      final consent = Completer<bool>();
      ConsentInformation.instance.requestConsentInfoUpdate(
        ConsentRequestParameters(
          consentDebugSettings: AdMobConfig.useTestAds
              ? ConsentDebugSettings(
                  testIdentifiers: AdMobConfig.testDeviceIds,
                  debugGeography: switch (AdMobConfig.umpDebugGeography) {
                    'eea' => DebugGeography.debugGeographyEea,
                    'us' => DebugGeography.debugGeographyRegulatedUsState,
                    'other' => DebugGeography.debugGeographyOther,
                    _ => DebugGeography.debugGeographyDisabled,
                  },
                )
              : null,
        ),
        () => consent.complete(true),
        (error) {
          debugPrint('AdMob consent update: ${error.message}');
          consent.complete(false);
        },
      );
      final updated = await consent.future;
      if (_disposed) return;
      if (updated) {
        await ConsentForm.loadAndShowConsentFormIfRequired((error) {
          if (error != null) debugPrint('AdMob consent: ${error.message}');
        });
      }
      // On update/form failure UMP may still permit ads from prior consent.
      await _refreshConsent();
    } catch (error) {
      debugPrint('AdMob initialization: $error');
    }
  }

  Future<void> _refreshConsent() async {
    _ready = false;
    _privacyRequired = await ConsentInformation.instance
            .getPrivacyOptionsRequirementStatus() ==
        PrivacyOptionsRequirementStatus.required;
    if (_disposed) return;
    if (!_sessionActive) {
      notifyListeners();
      return;
    }
    final allowed = await ConsentInformation.instance.canRequestAds();
    if (_disposed || !_sessionActive) return;
    if (allowed) {
      if (!_sdkInitialized) {
        if (AdMobConfig.useTestAds) {
          // Flutter equivalent of addTestDevice / setTestDeviceIds. Await this
          // before initialization and before either banner or interstitial load.
          await MobileAds.instance.updateRequestConfiguration(
            RequestConfiguration(testDeviceIds: AdMobConfig.testDeviceIds),
          );
        }
        await MobileAds.instance.initialize();
        _sdkInitialized = true;
      }
      if (_disposed || !_sessionActive) return;
      _ready = true;
    }
    notifyListeners();
    if (canLoadAds) unawaited(_loadInterstitial());
  }

  Future<String?> showPrivacyOptions() async {
    if (!_privacyRequired || _showing || _privacyOpen || !_sessionActive) {
      return null;
    }
    _privacyOpen = true;
    _ready = false;
    _clearInterstitial();
    notifyListeners();
    String? message;
    try {
      await ConsentForm.showPrivacyOptionsForm((error) {
        if (error != null) {
          debugPrint('AdMob privacy options: ${error.message}');
          message =
              'Không thể mở lựa chọn quyền riêng tư. Vui lòng thử lại sau.';
        }
      });
    } catch (error) {
      debugPrint('AdMob privacy options: $error');
      message = 'Không thể mở lựa chọn quyền riêng tư. Vui lòng thử lại sau.';
    } finally {
      try {
        await _refreshConsent();
      } catch (error) {
        debugPrint('AdMob privacy refresh: $error');
      }
      _privacyOpen = false;
      if (!_disposed) {
        notifyListeners();
        if (canLoadAds) unawaited(_loadInterstitial());
      }
    }
    return message;
  }

  void _recordScreenChange() {
    if (_sessionActive && !_showing) {
      // Keep an ad due if there is no fill; never accumulate multiple ads.
      if (_screenChanges < 5) _screenChanges++;
      unawaited(_loadInterstitial());
    }
  }

  Future<void> _loadInterstitial() async {
    if (!canLoadAds || _loading || _showing || _retry != null) return;
    if (_interstitial != null) {
      if (DateTime.now().difference(_loadedAt!) < const Duration(minutes: 55)) {
        return;
      }
      _interstitial!.dispose();
      _interstitial = null;
    }
    _loading = true;
    final generation = _generation;
    try {
      await InterstitialAd.load(
        adUnitId: AdMobConfig.interstitialUnitId,
        request: const AdRequest(),
        adLoadCallback: InterstitialAdLoadCallback(
          onAdLoaded: (ad) {
            if (generation != _generation || !canLoadAds) {
              ad.dispose();
              return;
            }
            _loading = false;
            _interstitial = ad;
            _loadedAt = DateTime.now();
            // Only navigation may show an ad, never a delayed load callback.
          },
          onAdFailedToLoad: (error) {
            if (generation != _generation) return;
            _loading = false;
            debugPrint('AdMob interstitial load: $error');
            _scheduleRetry();
          },
        ),
      );
    } catch (error) {
      if (generation != _generation) return;
      _loading = false;
      debugPrint('AdMob interstitial load: $error');
      _scheduleRetry();
    }
  }

  void _scheduleRetry() {
    if (!canLoadAds || _retry != null) return;
    _retry = Timer(const Duration(seconds: 60), () {
      _retry = null;
      unawaited(_loadInterstitial());
    });
  }

  void _tryShowInterstitial() {
    if (!canLoadAds ||
        _screenChanges < 5 ||
        _showing ||
        TutorialFlow.instance.isActive ||
        WidgetsBinding.instance.lifecycleState != AppLifecycleState.resumed) {
      return;
    }
    final ad = _interstitial;
    if (ad == null) return;
    _interstitial = null;
    _showing = true;
    ad.fullScreenContentCallback = FullScreenContentCallback(
      onAdShowedFullScreenContent: (_) => _screenChanges = 0,
      onAdDismissedFullScreenContent: (_) => _finishAd(ad),
      onAdFailedToShowFullScreenContent: (_, error) {
        debugPrint('AdMob interstitial show: $error');
        _finishAd(ad);
      },
    );
    unawaited(ad.show().catchError((Object error) {
      debugPrint('AdMob interstitial show: $error');
      _finishAd(ad);
    }));
  }

  void _finishAd(InterstitialAd ad) {
    ad.dispose();
    _showing = false;
    unawaited(_loadInterstitial());
  }

  void _clearInterstitial() {
    _generation++;
    _retry?.cancel();
    _retry = null;
    _interstitial?.dispose();
    _interstitial = null;
    _loading = false;
  }

  @override
  void dispose() {
    _disposed = true;
    endSession();
    super.dispose();
  }
}
