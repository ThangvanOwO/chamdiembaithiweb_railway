import 'package:flutter/material.dart';
import 'package:shared_preferences/shared_preferences.dart';

/// Orchestrates the cross-screen onboarding tutorial.
///
///   step 1 = Dashboard: highlight "Bài thi" bottom-nav tab.
///   step 2 = Exams screen: highlight "Tạo từ file đáp án" button.
///   step 3 = Import screen: highlight drop zone + "Quét phiếu thi" button.
///   step 4 = Exams screen (after pop back): note "tạo đề thi thủ công" +
///            highlight "Chấm điểm" bottom-nav tab.
///   step 5 = Scan screen: highlight exam selector → scan button → pickers.
///   step 0 = Done / skipped.
class TutorialFlow {
  TutorialFlow._();
  static final TutorialFlow instance = TutorialFlow._();

  static const _prefKey = 'tutorial_flow_step_v2';

  static const int stepClickBaiThi = 1;
  static const int stepClickImport = 2;
  static const int stepImportScreen = 3;
  static const int stepClickChamDiem = 4;
  static const int stepScanScreen = 5;
  static const int stepDone = 0;

  final ValueNotifier<int> step = ValueNotifier<int>(-1);

  Future<void> load() async {
    final prefs = await SharedPreferences.getInstance();
    step.value = prefs.getInt(_prefKey) ?? stepDone;
  }

  Future<void> setStep(int value) async {
    step.value = value;
    final prefs = await SharedPreferences.getInstance();
    await prefs.setInt(_prefKey, value);
  }

  /// Advance to [next] only if currently on [expectedCurrent].
  /// Prevents regressions when user taps tabs out of order.
  Future<void> advanceIf(int expectedCurrent, int next) async {
    if (step.value == expectedCurrent) await setStep(next);
  }

  Future<void> restart() => setStep(stepClickBaiThi);
  Future<void> finish() => setStep(stepDone);

  bool get isActive => step.value != stepDone && step.value != -1;
}

/// Shared global keys attached to widgets in `MainShell`'s bottom nav so that
/// any screen can target them in its coach marks.
class TutorialKeys {
  static final GlobalKey baiThiTabKey = GlobalKey(debugLabel: 'tab_bai_thi');
  static final GlobalKey chamDiemTabKey =
      GlobalKey(debugLabel: 'tab_cham_diem');
}
