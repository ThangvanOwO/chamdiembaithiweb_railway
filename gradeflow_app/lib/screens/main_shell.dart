import 'package:flutter/material.dart';
import 'package:google_fonts/google_fonts.dart';
import 'package:lucide_icons/lucide_icons.dart';
import 'package:provider/provider.dart';

import '../services/auth_service.dart';
import '../services/ad_service.dart';
import '../widgets/ad_banner.dart';
import '../services/coach_mark_service.dart';
import '../services/tutorial_flow.dart';
import 'dashboard_screen.dart';
import 'exams_screen.dart';
import 'scan_screen.dart';
import 'history_screen.dart';
import 'profile_screen.dart';

class MainShell extends StatefulWidget {
  const MainShell({super.key});

  @override
  State<MainShell> createState() => _MainShellState();
}

class _MainShellState extends State<MainShell> {
  int _currentIndex = 0;
  bool _step4Queued = false;

  @override
  void initState() {
    super.initState();
    _screens = [
      DashboardScreen(onNavigate: _onTabTap),
      const ExamsScreen(),
      const ScanScreen(),
      const HistoryScreen(),
      const ProfileScreen()
    ];
    TutorialFlow.instance.activeTabIndex.value = _currentIndex;
    WidgetsBinding.instance.addPostFrameCallback((_) async {
      if (!mounted) return;
      AdService.instance.startSession();
      context.read<AuthService>().refreshMe();
      await TutorialFlow.instance.load();
      _maybeShowStep1();
    });
  }

  void _maybeShowStep1() async {
    if (!mounted) return;
    if (TutorialFlow.instance.step.value != TutorialFlow.stepClickBaiThi) return;
    if (_currentIndex != 0) return; // Only when Dashboard is active
    await Future.delayed(const Duration(milliseconds: 500));
    if (!mounted) return;
    // Mark as started so this never auto-shows again on future launches.
    await TutorialFlow.instance.markStartedOnce();
    if (!mounted) return;
    await CoachMarkService.show(
      context: context,
      screenKey: 'flow_step1_bai_thi',
      force: true,
      targets: [
        CoachMarkService.buildTarget(
          identify: 'bai_thi_tab',
          key: TutorialKeys.baiThiTabKey,
          title: 'Bước 1: Tạo đề thi',
          description:
              'Nhấn vào mục "Bài thi" ở thanh dưới để bắt đầu tạo đề thi đầu tiên.',
          align: ContentAlign.top,
          shape: ShapeLightFocus.Circle,
          contentTop: MediaQuery.sizeOf(context).height * 0.40,
        ),
      ],
      onTargetTap: (_) {
        if (mounted) _onTabTap(1);
      },
    );
  }

  void _maybeShowStep4() async {
    if (!mounted) return;
    if (_step4Queued || _currentIndex != 1) return;
    if (TutorialFlow.instance.step.value != TutorialFlow.stepClickChamDiem) {
      return;
    }
    _step4Queued = true;
    await Future.delayed(const Duration(milliseconds: 500));
    if (!mounted || _currentIndex != 1 ||
        TutorialFlow.instance.step.value != TutorialFlow.stepClickChamDiem) {
      _step4Queued = false;
      return;
    }
    // Show note first
    ScaffoldMessenger.of(context).showSnackBar(
      SnackBar(
        content: Text(
          'Gợi ý: bạn cũng có thể tạo đề thi thủ công bằng nút "Tạo thủ công".',
          style: GoogleFonts.dmSans(fontSize: 13),
        ),
        duration: const Duration(seconds: 4),
      ),
    );
    await Future.delayed(const Duration(milliseconds: 400));
    if (!mounted || _currentIndex != 1 ||
        TutorialFlow.instance.step.value != TutorialFlow.stepClickChamDiem) {
      _step4Queued = false;
      return;
    }
    await CoachMarkService.show(
      context: context,
      screenKey: 'flow_step4_cham_diem',
      force: true,
      targets: [
        CoachMarkService.buildTarget(
          identify: 'cham_diem_tab',
          key: TutorialKeys.chamDiemTabKey,
          title: 'Bước tiếp theo: Chấm điểm',
          description:
              'Sau khi có đề thi, nhấn "Chấm điểm" để quét phiếu học sinh.',
          align: ContentAlign.top,
          shape: ShapeLightFocus.Circle,
          contentTop: MediaQuery.sizeOf(context).height * 0.40,
        ),
      ],
      onTargetTap: (_) {
        if (mounted) _onTabTap(2);
      },
    );
  }

  void _onTabTap(int index) {
    if (index == _currentIndex) return;
    final flow = TutorialFlow.instance;
    // Advance flow steps based on tab taps
    if (index == 1 && flow.step.value == TutorialFlow.stepClickBaiThi) {
      flow.setStep(TutorialFlow.stepClickImport);
    } else if (index == 2 &&
        flow.step.value == TutorialFlow.stepClickChamDiem) {
      flow.setStep(TutorialFlow.stepScanScreen);
    }
    setState(() => _currentIndex = index);
    flow.activeTabIndex.value = index;
    AdService.instance.navigationObserver.didChangeTab();

    // When user returns to Exams tab after visiting Import screen
    if (index == 1 && flow.step.value == TutorialFlow.stepClickChamDiem) {
      WidgetsBinding.instance.addPostFrameCallback((_) => _maybeShowStep4());
    }
  }

  late final List<Widget> _screens;

  @override
  void dispose() {
    AdService.instance.endSession();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) {
    return ValueListenableBuilder<int>(
      valueListenable: TutorialFlow.instance.step,
      builder: (context, step, _) {
        if (step != TutorialFlow.stepClickChamDiem) _step4Queued = false;
        // React to external changes (e.g., import screen popped)
        if (step == TutorialFlow.stepClickChamDiem && _currentIndex == 1) {
          WidgetsBinding.instance
              .addPostFrameCallback((_) => _maybeShowStep4());
        }
        return Scaffold(
          body: IndexedStack(
            index: _currentIndex,
            children: [
              for (var index = 0; index < _screens.length; index++)
                AdBannerScope(
                  isActive: index == _currentIndex,
                  keyboardVisible: MediaQuery.viewInsetsOf(context).bottom > 0,
                  child: _screens[index],
                ),
            ],
          ),
          bottomNavigationBar: Column(
            mainAxisSize: MainAxisSize.min,
            children: [
              Container(
                decoration: BoxDecoration(
                  border: Border(
                    top: BorderSide(
                      color: Theme.of(context)
                          .colorScheme
                          .outlineVariant
                          .withOpacity(0.5),
                      width: 1,
                    ),
                  ),
                ),
                child: BottomNavigationBar(
                  currentIndex: _currentIndex,
                  onTap: _onTabTap,
                  items: [
                    const BottomNavigationBarItem(
                      icon: Icon(LucideIcons.layoutDashboard),
                      activeIcon: Icon(LucideIcons.layoutDashboard),
                      label: 'Tổng quan',
                    ),
                    BottomNavigationBarItem(
                      icon: Container(
                        key: TutorialKeys.baiThiTabKey,
                        padding: const EdgeInsets.all(2),
                        child: const Icon(LucideIcons.fileText),
                      ),
                      activeIcon: const Icon(LucideIcons.fileText),
                      label: 'Bài thi',
                    ),
                    BottomNavigationBarItem(
                      icon: Container(
                        key: TutorialKeys.chamDiemTabKey,
                        padding: const EdgeInsets.all(2),
                        child: const Icon(LucideIcons.scan),
                      ),
                      activeIcon: const Icon(LucideIcons.scan),
                      label: 'Chấm điểm',
                    ),
                    const BottomNavigationBarItem(
                      icon: Icon(LucideIcons.clock),
                      activeIcon: Icon(LucideIcons.clock),
                      label: 'Lịch sử',
                    ),
                    const BottomNavigationBarItem(
                      icon: Icon(LucideIcons.user),
                      activeIcon: Icon(LucideIcons.user),
                      label: 'Tài khoản',
                    ),
                  ],
                ),
              ),
            ],
          ),
        );
      },
    );
  }
}
