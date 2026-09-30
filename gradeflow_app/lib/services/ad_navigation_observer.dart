import 'package:flutter/material.dart';

/// Counts actual page/tab changes, excluding dialogs, sheets and initial home.
class AdNavigationObserver extends NavigatorObserver {
  AdNavigationObserver({
    required this.onScreenChanged,
    required this.onSafeTransition,
  });

  static const cameraRoute = '/camera';
  static const batchScanRoute = '/batch-scan';

  final VoidCallback onScreenChanged;
  final VoidCallback onSafeTransition;
  Route<dynamic>? _top;
  int _revision = 0;

  bool _isProtected(Route<dynamic>? route) =>
      route?.settings.name == cameraRoute ||
      route?.settings.name == batchScanRoute;

  void _changed(Route<dynamic> destination, Animation<double>? animation,
      {bool protected = false}) {
    onScreenChanged();
    final revision = _revision;
    void maybeShow() {
      WidgetsBinding.instance.addPostFrameCallback((_) {
        if (revision == _revision &&
            destination.isCurrent &&
            !protected &&
            !_isProtected(destination)) {
          onSafeTransition();
        }
      });
    }

    if (animation == null || !animation.isAnimating) {
      maybeShow();
    } else {
      void listener(AnimationStatus status) {
        if (status == AnimationStatus.completed ||
            status == AnimationStatus.dismissed) {
          animation.removeStatusListener(listener);
          maybeShow();
        }
      }

      animation.addStatusListener(listener);
    }
  }

  void didChangeTab() {
    final route = _top;
    if (route is! PageRoute || !route.isCurrent) return;
    _revision++;
    _changed(route, null);
  }

  @override
  void didPush(Route<dynamic> route, Route<dynamic>? previousRoute) {
    _top = route;
    _revision++;
    if (route is PageRoute && previousRoute is PageRoute) {
      _changed(route, route.animation);
    }
  }

  @override
  void didPop(Route<dynamic> route, Route<dynamic>? previousRoute) {
    _top = previousRoute;
    _revision++;
    if (route is PageRoute && previousRoute is PageRoute) {
      // Returning a camera capture often starts grading immediately.
      _changed(previousRoute, route.animation, protected: _isProtected(route));
    }
  }

  @override
  void didReplace({Route<dynamic>? newRoute, Route<dynamic>? oldRoute}) {
    if (_top != oldRoute) return;
    _top = newRoute;
    _revision++;
    if (newRoute is PageRoute && oldRoute is PageRoute) {
      _changed(newRoute, newRoute.animation);
    }
  }

  @override
  void didRemove(Route<dynamic> route, Route<dynamic>? previousRoute) {
    if (_top == route) {
      _top = previousRoute;
      _revision++;
    }
  }
}
