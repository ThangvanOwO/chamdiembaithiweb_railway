import 'dart:async';

import 'package:flutter/foundation.dart';
import 'package:flutter/material.dart';
import 'package:flutter/services.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:google_mobile_ads/google_mobile_ads.dart';
// The real plugin codecs let these tests exercise native callbacks without ads.
import 'package:google_mobile_ads/src/ad_instance_manager.dart';
import 'package:google_mobile_ads/src/ump/user_messaging_codec.dart';
import 'package:gradeflow_app/config/admob_config.dart';
import 'package:gradeflow_app/services/ad_navigation_observer.dart';
import 'package:gradeflow_app/services/ad_service.dart';
import 'package:gradeflow_app/services/tutorial_flow.dart';
import 'package:gradeflow_app/widgets/ad_banner.dart';

void main() {
  final binding = TestWidgetsFlutterBinding.ensureInitialized();
  late AdService service;
  late GlobalKey<NavigatorState> navigator;
  late List<MethodCall> calls;
  bool consentAllowed = true;
  bool privacyRequired = false;
  bool updateFails = false;
  bool privacyFormFails = false;
  Completer<Object?>? consentFormPending;
  Completer<Object?>? privacyFormPending;
  final ump = MethodChannel('plugins.flutter.io/google_mobile_ads/ump',
      StandardMethodCodec(UserMessagingCodec()));

  Future<void> event(int id, String name,
      [Map<String, Object?> extra = const {}]) async {
    final channel = instanceManager.channel;
    await binding.defaultBinaryMessenger.handlePlatformMessage(
      channel.name,
      channel.codec.encodeMethodCall(MethodCall('onAdEvent', {
        'adId': id,
        'eventName': name,
        ...extra,
      })),
      (_) {},
    );
  }

  int getLoadedId() =>
      calls.lastWhere((c) => c.method == 'loadInterstitialAd').arguments['adId']
          as int;
  int shows() => calls.where((c) => c.method == 'showAdWithoutView').length;

  setUp(() {
    binding.handleAppLifecycleStateChanged(AppLifecycleState.resumed);
    TutorialFlow.instance.step.value = TutorialFlow.stepDone;
    consentAllowed = true;
    privacyRequired = false;
    updateFails = false;
    privacyFormFails = false;
    consentFormPending = null;
    privacyFormPending = null;
    calls = [];
    navigator = GlobalKey<NavigatorState>();
    instanceManager = AdInstanceManager('plugins.flutter.io/google_mobile_ads');
    binding.defaultBinaryMessenger.setMockMethodCallHandler(ump, (call) async {
      calls.add(call);
      switch (call.method) {
        case 'ConsentInformation#requestConsentInfoUpdate':
          if (updateFails) {
            throw PlatformException(code: '3', message: 'Offline');
          }
          return null;
        case 'UserMessagingPlatform#loadAndShowConsentFormIfRequired':
          return consentFormPending?.future;
        case 'UserMessagingPlatform#showPrivacyOptionsForm':
          if (privacyFormFails) {
            throw PlatformException(code: '3', message: 'Offline');
          }
          return privacyFormPending?.future;
        case 'ConsentInformation#canRequestAds':
          return consentAllowed;
        case 'ConsentInformation#getPrivacyOptionsRequirementStatus':
          return privacyRequired ? 1 : 0;
        default:
          return null;
      }
    });
    binding.defaultBinaryMessenger.setMockMethodCallHandler(
      instanceManager.channel,
      (call) async {
        calls.add(call);
        if (call.method == 'MobileAds#initialize') {
          return InitializationStatus({});
        }
        if (call.method == 'getAdSize') {
          final load = calls.lastWhere((c) => c.method == 'loadBannerAd');
          final requested = load.arguments['size'] as AdSize;
          return AdSize(width: requested.width, height: 60);
        }
        return null;
      },
    );
    service = AdService();
    binding.defaultBinaryMessenger.setMockMethodCallHandler(
      SystemChannels.platform_views,
      (call) async => null,
    );
  });

  tearDown(() {
    service.dispose();
    debugDefaultTargetPlatformOverride = null;
    binding.defaultBinaryMessenger.setMockMethodCallHandler(ump, null);
    binding.defaultBinaryMessenger
        .setMockMethodCallHandler(instanceManager.channel, null);
    binding.defaultBinaryMessenger.setMockMethodCallHandler(
      SystemChannels.platform_views,
      null,
    );
  });

  Future<void> launch(WidgetTester tester, {bool loaded = true}) async {
    await tester.pumpWidget(MaterialApp(
      navigatorKey: navigator,
      navigatorObservers: [service.navigationObserver],
      home: const Scaffold(body: Text('Home')),
    ));
    service.startSession();
    await tester.pumpAndSettle();
    if (loaded && consentAllowed) await event(getLoadedId(), 'onAdLoaded');
    await tester.pump();
  }

  Future<void> tab(WidgetTester tester) async {
    service.navigationObserver.didChangeTab();
    // MainShell calls setState when selecting a different tab.
    tester.binding.scheduleFrame();
    await tester.pump();
  }

  testWidgets('shows on fifth and tenth changes, then reloads after dismissal',
      (tester) async {
    await launch(tester);
    expect(shows(), 0);
    for (var i = 0; i < 4; i++) {
      await tab(tester);
    }
    expect(shows(), 0);
    await tab(tester);
    expect(shows(), 1);
    final first = getLoadedId();
    await event(first, 'onAdShowedFullScreenContent');
    await event(first, 'onAdDismissedFullScreenContent');
    await tester.pump();
    expect(getLoadedId(), isNot(first));
    await event(getLoadedId(), 'onAdLoaded');
    for (var i = 0; i < 4; i++) {
      await tab(tester);
    }
    expect(shows(), 1);
    await tab(tester);
    expect(shows(), 2);
  });

  testWidgets('UMP updates at app launch before login without requesting ads',
      (tester) async {
    await service.initializeConsent();
    expect(calls.where((c) => c.method == 'ConsentInformation#reset').length,
        AdMobConfig.resetTestConsent ? 1 : 0);
    expect(
        calls
            .where((c) =>
                c.method == 'ConsentInformation#requestConsentInfoUpdate')
            .length,
        1);
    expect(calls.where((c) => c.method == 'MobileAds#initialize'), isEmpty);
    expect(calls.where((c) => c.method == 'loadInterstitialAd'), isEmpty);
    service.startSession();
    await tester.pumpAndSettle();
    expect(
        calls
            .where((c) =>
                c.method == 'ConsentInformation#requestConsentInfoUpdate')
            .length,
        1);
    expect(calls.where((c) => c.method == 'loadInterstitialAd').length, 1);
    final parameters = calls
        .firstWhere(
            (c) => c.method == 'ConsentInformation#requestConsentInfoUpdate')
        .arguments['params'] as ConsentRequestParameters;
    expect(parameters.consentDebugSettings?.testIdentifiers,
        AdMobConfig.testDeviceIds);
    expect(
        parameters.consentDebugSettings?.debugGeography,
        AdMobConfig.umpDebugGeography == 'eea'
            ? DebugGeography.debugGeographyEea
            : DebugGeography.debugGeographyDisabled);
  });

  testWidgets('ads wait until required UMP form is dismissed', (tester) async {
    consentAllowed = false;
    consentFormPending = Completer<Object?>();
    service.startSession();
    service.initializeConsent();
    await tester.pumpAndSettle();
    expect(service.canLoadAds, isFalse);
    expect(calls.where((c) => c.method == 'MobileAds#initialize'), isEmpty);
    expect(calls.where((c) => c.method == 'loadInterstitialAd'), isEmpty);
    consentAllowed = true;
    consentFormPending!.complete(null);
    await tester.pumpAndSettle();
    expect(service.canLoadAds, isTrue);
    expect(calls.where((c) => c.method == 'MobileAds#initialize').length, 1);
    expect(calls.where((c) => c.method == 'loadInterstitialAd').length, 1);
  });

  for (final cachedConsent in [false, true]) {
    testWidgets(
        'UMP update failure respects cached permission ($cachedConsent)',
        (tester) async {
      updateFails = true;
      consentAllowed = cachedConsent;
      await launch(tester, loaded: false);
      expect(service.canLoadAds, cachedConsent);
      expect(
          calls.where((c) =>
              c.method ==
              'UserMessagingPlatform#loadAndShowConsentFormIfRequired'),
          isEmpty);
      expect(calls.where((c) => c.method == 'loadInterstitialAd').length,
          cachedConsent ? 1 : 0);
    });
  }

  testWidgets('privacy options suspend ads and apply the updated permission',
      (tester) async {
    privacyRequired = true;
    await launch(tester);
    expect(service.privacyOptionsRequired, isTrue);
    privacyFormPending = Completer<Object?>();
    final form = service.showPrivacyOptions();
    await tester.pumpAndSettle();
    expect(service.privacyOptionsOpen, isTrue);
    expect(service.canLoadAds, isFalse);
    await service.showPrivacyOptions();
    expect(
        calls
            .where((c) =>
                c.method == 'UserMessagingPlatform#showPrivacyOptionsForm')
            .length,
        1);
    consentAllowed = false;
    privacyFormPending!.complete(null);
    expect(await form, isNull);
    expect(service.privacyOptionsOpen, isFalse);
    expect(service.canLoadAds, isFalse);
    expect(calls.where((c) => c.method == 'loadInterstitialAd').length, 1);
  });

  testWidgets('privacy form errors return feedback and preserve UMP permission',
      (tester) async {
    privacyRequired = true;
    await launch(tester);
    privacyFormFails = true;
    expect(await service.showPrivacyOptions(), contains('Không thể mở'));
    expect(service.privacyOptionsOpen, isFalse);
    expect(service.canLoadAds, isTrue);
  });

  testWidgets(
      'registers test devices before SDK initialization and ad requests',
      (tester) async {
    await launch(tester);
    final configIndex = calls.indexWhere(
        (call) => call.method == 'MobileAds#updateRequestConfiguration');
    final initIndex =
        calls.indexWhere((call) => call.method == 'MobileAds#initialize');
    final loadIndex =
        calls.indexWhere((call) => call.method == 'loadInterstitialAd');
    expect(configIndex, greaterThanOrEqualTo(0));
    expect(configIndex, lessThan(initIndex));
    expect(initIndex, lessThan(loadIndex));
    expect(calls[configIndex].arguments['testDeviceIds'],
        AdMobConfig.testDeviceIds);
    if (const bool.fromEnvironment('ADMOB_VERIFY_TEST_DEVICES')) {
      expect(AdMobConfig.testDeviceIds, ['QA_DEVICE_A', 'QA_DEVICE_B']);
    }
  });

  testWidgets('counts push and back but ignores dialog and sheet navigation',
      (tester) async {
    await launch(tester);
    for (var i = 0; i < 3; i++) {
      await tab(tester);
    }
    showDialog<void>(
        context: navigator.currentContext!,
        builder: (_) => const AlertDialog(title: Text('Dialog')));
    await tester.pumpAndSettle();
    navigator.currentState!.pop();
    await tester.pumpAndSettle();
    showModalBottomSheet<void>(
        context: navigator.currentContext!,
        builder: (_) => const Text('Sheet'));
    await tester.pumpAndSettle();
    navigator.currentState!.pop();
    await tester.pumpAndSettle();
    navigator.currentState!.push(MaterialPageRoute<void>(
        builder: (_) => const Scaffold(body: Text('Detail'))));
    await tester.pumpAndSettle();
    expect(shows(), 0);
    navigator.currentState!.pop();
    await tester.pumpAndSettle();
    expect(shows(), 1);
  });

  testWidgets(
      'camera entry and capture return defer an ad to the next safe change',
      (tester) async {
    await launch(tester);
    for (var i = 0; i < 4; i++) {
      await tab(tester);
    }
    navigator.currentState!.push(MaterialPageRoute<void>(
      settings: const RouteSettings(name: AdNavigationObserver.cameraRoute),
      builder: (_) => const Scaffold(body: Text('Camera')),
    ));
    await tester.pumpAndSettle();
    expect(shows(), 0);
    navigator.currentState!.pop();
    await tester.pumpAndSettle();
    expect(shows(), 0);
    await tab(tester);
    expect(shows(), 1);
  });

  testWidgets('late load never shows an ad until another screen change',
      (tester) async {
    await launch(tester, loaded: false);
    for (var i = 0; i < 5; i++) {
      await tab(tester);
    }
    expect(shows(), 0);
    await event(getLoadedId(), 'onAdLoaded');
    await tester.pump();
    expect(shows(), 0);
    await tab(tester);
    expect(shows(), 1);
  });

  testWidgets('no-fill retries with delay and keeps the fifth change due',
      (tester) async {
    await launch(tester, loaded: false);
    await event(getLoadedId(), 'onAdFailedToLoad', {
      'loadAdError': LoadAdError(3, 'test', 'No fill', null),
    });
    for (var i = 0; i < 5; i++) {
      await tab(tester);
    }
    expect(calls.where((c) => c.method == 'loadInterstitialAd').length, 1);
    await tester.pump(const Duration(seconds: 60));
    expect(calls.where((c) => c.method == 'loadInterstitialAd').length, 2);
    await event(getLoadedId(), 'onAdLoaded');
    await tester.pump();
    expect(shows(), 0);
    await tab(tester);
    expect(shows(), 1);
  });

  testWidgets('does not request ads without consent', (tester) async {
    consentAllowed = false;
    await launch(tester);
    for (var i = 0; i < 6; i++) {
      await tab(tester);
    }
    expect(service.canLoadAds, isFalse);
    expect(calls.where((c) => c.method == 'loadInterstitialAd'), isEmpty);
    expect(shows(), 0);
  });

  testWidgets('logout discards a pending ad and resets the count',
      (tester) async {
    await launch(tester, loaded: false);
    final stale = getLoadedId();
    for (var i = 0; i < 4; i++) {
      await tab(tester);
    }
    service.endSession();
    await event(stale, 'onAdLoaded');
    await tester.pump();
    expect(service.canLoadAds, isFalse);
    service.startSession();
    await tester.pumpAndSettle();
    await event(getLoadedId(), 'onAdLoaded');
    await tab(tester);
    expect(shows(), 0);
  });

  testWidgets(
      'background and tutorial defer interstitial until safe navigation',
      (tester) async {
    await launch(tester);
    TutorialFlow.instance.step.value = TutorialFlow.stepClickImport;
    for (var i = 0; i < 5; i++) {
      await tab(tester);
    }
    expect(shows(), 0);
    TutorialFlow.instance.step.value = TutorialFlow.stepDone;
    binding.handleAppLifecycleStateChanged(AppLifecycleState.inactive);
    await tab(tester);
    expect(shows(), 0);
    binding.handleAppLifecycleStateChanged(AppLifecycleState.resumed);
    await tester.pump();
    expect(shows(), 0);
    await tab(tester);
    expect(shows(), 1);
  });

  testWidgets(
      'inline banner fits padded content, scrolls and hides for keyboard',
      (tester) async {
    tester.view.physicalSize = const Size(360, 640);
    tester.view.devicePixelRatio = 1;
    addTearDown(tester.view.resetPhysicalSize);
    addTearDown(tester.view.resetDevicePixelRatio);
    addTearDown(tester.view.resetViewInsets);
    await tester.pumpWidget(MaterialApp(
      home: Builder(
          builder: (context) => AdBannerScope(
                isActive: true,
                keyboardVisible: MediaQuery.viewInsetsOf(context).bottom > 0,
                child: Scaffold(
                  body: ListView(
                    padding: const EdgeInsets.all(16),
                    children: const [
                      SizedBox(height: 400, key: Key('content')),
                      AdBanner(),
                      SizedBox(height: 400, key: Key('following')),
                    ],
                  ),
                  bottomNavigationBar: BottomNavigationBar(items: const [
                    BottomNavigationBarItem(
                        icon: Icon(Icons.home), label: 'Home'),
                    BottomNavigationBarItem(
                        icon: Icon(Icons.person), label: 'Profile'),
                  ]),
                ),
              )),
    ));
    await tester.pumpAndSettle();
    final load = calls.lastWhere((c) => c.method == 'loadBannerAd');
    await event(load.arguments['adId'] as int, 'onAdLoaded');
    await tester.pumpAndSettle();
    final content = tester.getRect(find.byKey(const Key('content')));
    final banner = tester.getRect(find.byType(AdWidget));
    final following = tester.getRect(find.byKey(const Key('following')));
    final nav = tester.getRect(find.byType(BottomNavigationBar));
    expect(banner.height, 60);
    expect(banner.width, 328);
    expect(banner.left, 16);
    expect(banner.top - content.bottom, 24);
    expect(following.top - banner.bottom, 24);
    expect(banner.bottom, lessThan(nav.top));
    expect(nav.bottom, lessThanOrEqualTo(640));
    await tester.drag(find.byType(ListView), const Offset(0, -180));
    await tester.pumpAndSettle();
    expect(tester.getRect(find.byType(AdWidget)).top, lessThan(banner.top));
    tester.view.viewInsets = const FakeViewPadding(bottom: 260);
    await tester.pumpAndSettle();
    expect(find.byType(AdWidget), findsNothing);
    tester.view.resetViewInsets();
    await tester.pumpAndSettle();
    expect(find.byType(AdWidget), findsOneWidget);
    expect(tester.takeException(), isNull);
    await tester.pumpWidget(const SizedBox());
    await tester.pump();
  });

  testWidgets('inactive retained tabs do not request or retain a banner',
      (tester) async {
    final sharedService = AdService.instance;
    addTearDown(sharedService.endSession);
    sharedService.startSession();
    Future<void> showTab(bool active) async {
      await tester.pumpWidget(MaterialApp(
          home: AdBannerScope(
        isActive: active,
        child: const Scaffold(body: InlineAdBanner()),
      )));
      await tester.pumpAndSettle();
    }

    await showTab(false);
    expect(sharedService.canLoadAds, isTrue);
    expect(calls.where((c) => c.method == 'loadBannerAd'), isEmpty);
    await showTab(true);
    final load = calls.lastWhere((c) => c.method == 'loadBannerAd');
    await event(load.arguments['adId'] as int, 'onAdLoaded');
    await tester.pumpAndSettle();
    expect(find.byType(AdWidget), findsOneWidget);
    await showTab(false);
    expect(find.byType(AdWidget), findsNothing);
    expect(calls.where((c) => c.method == 'loadBannerAd').length, 1);
    expect(tester.takeException(), isNull);
  });

  for (final earned in [false, true]) {
    testWidgets('rewarded opt-in completion=$earned and SSV before show',
        (tester) async {
      await launch(tester);
      final pending = service.showRewarded(ticket: 'signed-test-ticket');
      await tester.pump();
      final load = calls.lastWhere((c) => c.method == 'loadRewardedAd');
      expect(
          load.arguments['adUnitId'], 'ca-app-pub-3940256099942544/5224354917');
      final id = load.arguments['adId'] as int;
      for (var i = 0; i < 5; i++) {
        await tab(tester);
      }
      expect(shows(), 0);
      await event(id, 'onAdLoaded');
      await tester.pump();
      final ssvIndex = calls
          .indexWhere((c) => c.method == 'setServerSideVerificationOptions');
      final showIndex =
          calls.indexWhere((c) => c.method == 'showAdWithoutView');
      expect(ssvIndex, greaterThan(-1));
      expect(showIndex, greaterThan(ssvIndex));
      if (earned) {
        await event(id, 'onRewardedAdUserEarnedReward',
            {'rewardItem': RewardItem(5, 'credits')});
      }
      await event(id, 'onAdDismissedFullScreenContent');
      await tester.pump();
      expect(await pending, earned);
      expect(
          calls.where(
              (c) => c.method == 'disposeAd' && c.arguments['adId'] == id),
          isNotEmpty);
    });
  }

  testWidgets('rewarded requires UMP permission and active session',
      (tester) async {
    consentAllowed = false;
    await launch(tester, loaded: false);
    await expectLater(service.showRewarded(), throwsException);
    expect(calls.where((c) => c.method == 'loadRewardedAd'), isEmpty);
  });

  testWidgets('logout while rewarded loads prevents display', (tester) async {
    await launch(tester);
    final pending = service.showRewarded();
    final expected = expectLater(pending, throwsException);
    await tester.pump();
    final id = calls
        .lastWhere((c) => c.method == 'loadRewardedAd')
        .arguments['adId'] as int;
    service.endSession();
    await event(id, 'onAdLoaded');
    await tester.pump();
    await expected;
    expect(shows(), 0);
  });

  test('debug uses Google test IDs and unsupported platforms are disabled', () {
    expect(
        AdMobConfig.bannerUnitId, startsWith('ca-app-pub-3940256099942544/'));
    expect(AdMobConfig.interstitialUnitId,
        startsWith('ca-app-pub-3940256099942544/'));
    expect(
        AdMobConfig.rewardedUnitId, startsWith('ca-app-pub-3940256099942544/'));
    debugDefaultTargetPlatformOverride = TargetPlatform.iOS;
    expect(AdMobConfig.isSupported, isFalse);
    debugDefaultTargetPlatformOverride = TargetPlatform.windows;
    expect(AdMobConfig.isSupported, isFalse);
    debugDefaultTargetPlatformOverride = null;
  });
}
