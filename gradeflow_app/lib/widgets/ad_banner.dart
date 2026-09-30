import 'dart:async';

import 'package:flutter/material.dart';
import 'package:google_mobile_ads/google_mobile_ads.dart';

import '../config/admob_config.dart';
import '../services/ad_service.dart';

/// Prevents retained, inactive tabs from requesting or displaying banners.
class AdBannerScope extends InheritedWidget {
  const AdBannerScope(
      {super.key,
      required this.isActive,
      this.keyboardVisible = false,
      required super.child});

  final bool isActive;
  final bool keyboardVisible;

  @override
  bool updateShouldNotify(AdBannerScope oldWidget) =>
      isActive != oldWidget.isActive ||
      keyboardVisible != oldWidget.keyboardVisible;
}

class InlineAdBanner extends StatelessWidget {
  const InlineAdBanner({super.key});

  @override
  Widget build(BuildContext context) {
    final active =
        context.dependOnInheritedWidgetOfExactType<AdBannerScope>()?.isActive ??
            false;
    return AnimatedBuilder(
      animation: AdService.instance,
      builder: (context, _) => active && AdService.instance.canLoadAds
          ? const AdBanner()
          : const SizedBox.shrink(),
    );
  }
}

/// An adaptive banner in the scrolling layout, sized to its actual parent.
class AdBanner extends StatelessWidget {
  const AdBanner({super.key});

  @override
  Widget build(BuildContext context) => SafeArea(
        top: false,
        bottom: false,
        child: LayoutBuilder(
          builder: (context, constraints) => _AdaptiveBanner(
            width: constraints.maxWidth.floor(),
          ),
        ),
      );
}

class _AdaptiveBanner extends StatefulWidget {
  const _AdaptiveBanner({required this.width});

  final int width;

  @override
  State<_AdaptiveBanner> createState() => _AdaptiveBannerState();
}

class _AdaptiveBannerState extends State<_AdaptiveBanner> {
  BannerAd? _ad;
  AdSize? _size;
  bool _loaded = false;
  int _generation = 0;
  Timer? _retry;

  @override
  void initState() {
    super.initState();
    unawaited(_load(++_generation));
  }

  @override
  void didUpdateWidget(_AdaptiveBanner oldWidget) {
    super.didUpdateWidget(oldWidget);
    if (oldWidget.width == widget.width) return;
    _retry?.cancel();
    _ad?.dispose();
    _ad = null;
    _size = null;
    _loaded = false;
    unawaited(_load(++_generation));
  }

  Future<void> _load(int generation) async {
    if (!AdMobConfig.isSupported || widget.width <= 0) return;
    try {
      final size = AdSize.getInlineAdaptiveBannerAdSize(widget.width, 120);
      if (!mounted || generation != _generation) return;
      final ad = BannerAd(
        adUnitId: AdMobConfig.bannerUnitId,
        size: size,
        request: const AdRequest(),
        listener: BannerAdListener(
          onAdLoaded: (ad) async {
            if (!mounted || generation != _generation) return;
            final platformSize = await (ad as BannerAd).getPlatformAdSize();
            if (!mounted || generation != _generation) return;
            if (platformSize == null) {
              ad.dispose();
              _ad = null;
              _scheduleRetry(generation);
              return;
            }
            setState(() {
              _size = platformSize;
              _loaded = true;
            });
          },
          onAdFailedToLoad: (ad, error) {
            if (!mounted || generation != _generation) return;
            ad.dispose();
            _ad = null;
            setState(() => _loaded = false);
            debugPrint('AdMob banner load: $error');
            _scheduleRetry(generation);
          },
        ),
      );
      _ad = ad;
      await ad.load();
    } catch (error) {
      if (!mounted || generation != _generation) return;
      _ad?.dispose();
      _ad = null;
      setState(() => _loaded = false);
      debugPrint('AdMob banner load: $error');
      _scheduleRetry(generation);
    }
  }

  void _scheduleRetry(int generation) {
    _retry?.cancel();
    _retry = Timer(const Duration(seconds: 60), () => _load(generation));
  }

  @override
  void dispose() {
    _generation++;
    _retry?.cancel();
    _ad?.dispose();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) {
    final ad = _ad;
    final size = _size;
    final keyboardVisible = context
            .dependOnInheritedWidgetOfExactType<AdBannerScope>()
            ?.keyboardVisible ??
        false;
    if (!_loaded ||
        ad == null ||
        size == null ||
        keyboardVisible ||
        MediaQuery.viewInsetsOf(context).bottom > 0) {
      return const SizedBox.shrink();
    }
    return Padding(
      padding: const EdgeInsets.symmetric(vertical: 24),
      child: Center(
        child: SizedBox(
          width: size.width.toDouble(),
          height: size.height.toDouble(),
          child: AdWidget(ad: ad),
        ),
      ),
    );
  }
}
