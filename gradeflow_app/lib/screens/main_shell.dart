import 'package:flutter/material.dart';
import 'package:google_fonts/google_fonts.dart';
import 'package:lucide_icons/lucide_icons.dart';
import 'package:provider/provider.dart';

import '../services/auth_service.dart';
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

  @override
  void initState() {
    super.initState();
    WidgetsBinding.instance.addPostFrameCallback((_) async {
      context.read<AuthService>().refreshMe();
      await TutorialFlow.instance.load();
      _maybeShowStep1();
    });
  }

  void _maybeShowStep1() async {
    if (!mounted) return;
    if (TutorialFlow.instance.step.value != TutorialFlow.stepClickBaiThi) return;
    await Future.delayed(const Duration(milliseconds: 500));
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
        ),
      ],
    );
  }

  void _maybeShowStep4() async {
    if (!mounted) return;
    if (TutorialFlow.instance.step.value != TutorialFlow.stepClickChamDiem) {
      return;
    }
    await Future.delayed(const Duration(milliseconds: 500));
    if (!mounted) return;
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
    if (!mounted) return;
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
        ),
      ],
    );
  }

  void _onTabTap(int index) {
    final flow = TutorialFlow.instance;
    // Advance flow steps based on tab taps
    if (index == 1 && flow.step.value == TutorialFlow.stepClickBaiThi) {
      flow.setStep(TutorialFlow.stepClickImport);
    } else if (index == 2 && flow.step.value == TutorialFlow.stepClickChamDiem) {
      flow.setStep(TutorialFlow.stepScanScreen);
    }
    setState(() => _currentIndex = index);

    // When user returns to Exams tab after visiting Import screen
    if (index == 1 && flow.step.value == TutorialFlow.stepClickChamDiem) {
      WidgetsBinding.instance.addPostFrameCallback((_) => _maybeShowStep4());
    }
  }

  final List<Widget> _screens = const [
    DashboardScreen(),
    ExamsScreen(),
    ScanScreen(),
    HistoryScreen(),
    ProfileScreen(),
  ];

  @override
  Widget build(BuildContext context) {
    return ValueListenableBuilder<int>(
      valueListenable: TutorialFlow.instance.step,
      builder: (context, step, _) {
        // React to external changes (e.g., import screen popped)
        if (step == TutorialFlow.stepClickChamDiem && _currentIndex == 1) {
          WidgetsBinding.instance
              .addPostFrameCallback((_) => _maybeShowStep4());
        }
        return Scaffold(
          body: IndexedStack(
            index: _currentIndex,
            children: _screens,
          ),
          bottomNavigationBar: Container(
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
                  label: 'Dashboard',
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
        );
      },
    );
  }
}
