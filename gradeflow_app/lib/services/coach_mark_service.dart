import 'package:flutter/material.dart';
import 'package:google_fonts/google_fonts.dart';
import 'package:shared_preferences/shared_preferences.dart';
import 'package:tutorial_coach_mark/tutorial_coach_mark.dart';

// Re-export commonly used types for convenience
export 'package:tutorial_coach_mark/tutorial_coach_mark.dart'
    show TargetFocus, ContentAlign, ShapeLightFocus;

/// Helper to show TutorialCoachMark once per screen, tracking
/// completion via SharedPreferences.
class CoachMarkService {
  CoachMarkService._();

  static TutorialCoachMark? _active;
  static String? _activeScreenKey;

  static void dismissActive() => _active?.finish();

  static Future<bool> hasSeen(String key) async {
    final prefs = await SharedPreferences.getInstance();
    return prefs.getBool('coach_$key') ?? false;
  }

  static Future<void> markSeen(String key) async {
    final prefs = await SharedPreferences.getInstance();
    await prefs.setBool('coach_$key', true);
  }

  /// Reset all coach marks (used when user replays tutorial).
  static Future<void> resetAll() async {
    final prefs = await SharedPreferences.getInstance();
    final keys = prefs.getKeys().where((k) => k.startsWith('coach_')).toList();
    for (final k in keys) {
      await prefs.remove(k);
    }
  }

  /// Build a standard target focus.
  static TargetFocus buildTarget({
    required String identify,
    required GlobalKey key,
    required String title,
    required String description,
    ContentAlign align = ContentAlign.bottom,
    ShapeLightFocus shape = ShapeLightFocus.RRect,
    double? contentTop,
  }) {
    return TargetFocus(
      identify: identify,
      keyTarget: key,
      shape: shape,
      radius: 12,
      borderSide: const BorderSide(color: Color(0xFF59DCC7), width: 2),
      contents: [
        TargetContent(
          align: contentTop == null ? align : ContentAlign.custom,
          customPosition: contentTop == null
              ? null
              : CustomTargetContentPosition(top: contentTop),
          builder: (context, controller) {
            return TweenAnimationBuilder<double>(
              tween: Tween(begin: 0.88, end: 1),
              duration: const Duration(milliseconds: 420),
              curve: Curves.easeOutCubic,
              builder: (context, value, child) => Opacity(
                opacity: ((value - 0.88) / 0.12).clamp(0.0, 1.0),
                child: Transform.translate(
                  offset: Offset(0, (1 - value) * 90),
                  child: child,
                ),
              ),
              child: Center(
                child: ConstrainedBox(
                  constraints: const BoxConstraints(maxWidth: 440),
                  child: DecoratedBox(
                    decoration: BoxDecoration(
                      gradient: const LinearGradient(
                        begin: Alignment.topLeft,
                        end: Alignment.bottomRight,
                        colors: [Colors.white, Color(0xFFE7F7F3)],
                      ),
                      borderRadius: BorderRadius.circular(22),
                      border: Border.all(color: const Color(0xFF9DDDD1)),
                      boxShadow: const [BoxShadow(
                        color: Color(0x33071E2B),
                        blurRadius: 28,
                        offset: Offset(0, 12),
                      )],
                    ),
                    child: Padding(
                      padding: const EdgeInsets.all(20),
                      child: Column(
                        mainAxisSize: MainAxisSize.min,
                        crossAxisAlignment: CrossAxisAlignment.start,
                        children: [
                          Row(children: [
                            const Icon(Icons.auto_awesome_rounded,
                                color: Color(0xFF0F766E), size: 18),
                            const SizedBox(width: 8),
                            Text('HƯỚNG DẪN GRADEFLOW',
                                style: GoogleFonts.dmSans(
                                    color: const Color(0xFF0F766E),
                                    fontSize: 11,
                                    letterSpacing: 1.2,
                                    fontWeight: FontWeight.w800)),
                          ]),
                          const SizedBox(height: 12),
                          Text(title,
                              style: GoogleFonts.manrope(
                                  fontSize: 20,
                                  height: 1.2,
                                  fontWeight: FontWeight.w800,
                                  color: const Color(0xFF16343F))),
                          const SizedBox(height: 8),
                          Text(description,
                              style: GoogleFonts.dmSans(
                                  fontSize: 14,
                                  height: 1.45,
                                  color: const Color(0xFF405969))),
                          const SizedBox(height: 14),
                          Row(children: [
                            const Icon(Icons.touch_app_rounded,
                                color: Color(0xFF0F766E), size: 17),
                            const SizedBox(width: 6),
                            Flexible(child: Text('Chạm vào vùng sáng để tiếp tục',
                                style: GoogleFonts.dmSans(
                                    fontSize: 12,
                                    fontWeight: FontWeight.w700,
                                    color: const Color(0xFF0F766E)))),
                          ]),
                        ],
                      ),
                    ),
                  ),
                ),
              ),
            );
          },
        ),
      ],
    );
  }

  /// Show coach marks on a screen.
  /// Only shows once unless [force] is true.
  static Future<void> show({
    required BuildContext context,
    required String screenKey,
    required List<TargetFocus> targets,
    bool force = false,
    VoidCallback? onFinish,
    ValueChanged<TargetFocus>? onTargetTap,
  }) async {
    if (!force && await hasSeen(screenKey)) {
      onFinish?.call();
      return;
    }

    if (!context.mounted) return;

    if (_activeScreenKey == screenKey) return;
    dismissActive();

    late final TutorialCoachMark coach;
    TargetFocus? tappedTarget;
    void clearActive() {
      if (identical(_active, coach)) {
        _active = null;
        _activeScreenKey = null;
      }
    }

    coach = TutorialCoachMark(
      targets: targets,
      colorShadow: const Color(0xFF102F3A),
      opacityShadow: 0.63,
      focusAnimationDuration: const Duration(milliseconds: 380),
      unFocusAnimationDuration: const Duration(milliseconds: 260),
      pulseAnimationDuration: const Duration(milliseconds: 1000),
      onClickTarget: (target) => tappedTarget = target,
      textSkip: 'Bỏ qua',
      textStyleSkip: GoogleFonts.dmSans(
        color: Colors.white,
        fontSize: 14,
        fontWeight: FontWeight.w600,
      ),
      paddingFocus: 8,
      onFinish: () async {
        clearActive();
        await markSeen(screenKey);
        onFinish?.call();
        if (tappedTarget != null && onTargetTap != null) {
          final target = tappedTarget!;
          WidgetsBinding.instance.addPostFrameCallback((_) => onTargetTap(target));
        }
      },
      onSkip: () {
        clearActive();
        markSeen(screenKey);
        onFinish?.call();
        return true;
      },
    );
    _active = coach;
    _activeScreenKey = screenKey;
    coach.show(context: context);
  }
}
