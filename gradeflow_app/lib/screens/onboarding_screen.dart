import 'package:flutter/material.dart';
import 'package:google_fonts/google_fonts.dart';
import 'package:introduction_screen/introduction_screen.dart';
import 'package:lucide_icons/lucide_icons.dart';
import 'package:shared_preferences/shared_preferences.dart';

import '../config/theme.dart';
import '../services/tutorial_flow.dart';

/// Onboarding screens shown on first launch.
/// After completion, stores `has_seen_onboarding = true` in SharedPreferences.
class OnboardingScreen extends StatelessWidget {
  final VoidCallback onDone;
  const OnboardingScreen({super.key, required this.onDone});

  static const _prefsKey = 'has_seen_onboarding';

  /// Returns true if user has already completed onboarding.
  static Future<bool> hasSeenOnboarding() async {
    final prefs = await SharedPreferences.getInstance();
    return prefs.getBool(_prefsKey) ?? false;
  }

  /// Reset flag so onboarding shows again (used from Profile screen).
  static Future<void> reset() async {
    final prefs = await SharedPreferences.getInstance();
    await prefs.setBool(_prefsKey, false);
  }

  Future<void> _complete() async {
    final prefs = await SharedPreferences.getInstance();
    await prefs.setBool(_prefsKey, true);
    await TutorialFlow.instance.restart();
    onDone();
  }

  PageViewModel _buildPage({
    required IconData icon,
    required Color iconColor,
    required Color bgColor,
    required String title,
    required String body,
  }) {
    return PageViewModel(
      titleWidget: Padding(
        padding: const EdgeInsets.only(bottom: 8),
        child: Text(title,
            style: GoogleFonts.manrope(
                fontSize: 26, fontWeight: FontWeight.w800),
            textAlign: TextAlign.center),
      ),
      bodyWidget: Padding(
        padding: const EdgeInsets.symmetric(horizontal: 16),
        child: Text(body,
            style: GoogleFonts.dmSans(
                fontSize: 15,
                height: 1.5,
                color: GradeFlowTheme.onSurfaceVariant),
            textAlign: TextAlign.center),
      ),
      image: Container(
        width: 200,
        height: 200,
        decoration: BoxDecoration(
          color: bgColor,
          shape: BoxShape.circle,
        ),
        child: Center(
          child: Icon(icon, size: 96, color: iconColor),
        ),
      ),
      decoration: const PageDecoration(
        imagePadding: EdgeInsets.only(top: 60, bottom: 24),
        titlePadding: EdgeInsets.symmetric(horizontal: 24, vertical: 8),
        bodyPadding: EdgeInsets.symmetric(horizontal: 24, vertical: 8),
        pageColor: Colors.white,
      ),
    );
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      body: IntroductionScreen(
        globalBackgroundColor: Colors.white,
        pages: [
          _buildPage(
            icon: LucideIcons.graduationCap,
            iconColor: GradeFlowTheme.primary,
            bgColor: GradeFlowTheme.primaryFixed,
            title: 'Chào mừng đến GradeFlow',
            body:
                'Chấm điểm phiếu trắc nghiệm tự động chỉ với 1 chiếc camera. Nhanh, chính xác và tiết kiệm hàng giờ mỗi tuần.',
          ),
          _buildPage(
            icon: LucideIcons.scan,
            iconColor: const Color(0xFF4A4458),
            bgColor: const Color(0xFFE8DEF8),
            title: 'Quét phiếu bằng ML Kit',
            body:
                'Dùng camera điện thoại để quét phiếu đáp án. Hệ thống Google ML Kit tự động căn chỉnh giấy và nhận diện các ô đã tô.',
          ),
          _buildPage(
            icon: LucideIcons.barChart3,
            iconColor: GradeFlowTheme.tertiary,
            bgColor: GradeFlowTheme.tertiaryContainer,
            title: 'Thống kê & Báo cáo',
            body:
                'Xem điểm trung bình lớp, tỉ lệ đạt và phân tích chi tiết từng câu. Mọi dữ liệu được đồng bộ với hệ thống web.',
          ),
          _buildPage(
            icon: LucideIcons.sparkles,
            iconColor: const Color(0xFF2E7D32),
            bgColor: const Color(0xFFE8F5E9),
            title: 'Sẵn sàng bắt đầu!',
            body:
                'Tạo đề thi đầu tiên hoặc nhập từ file Excel, rồi quét phiếu và xem kết quả tức thì. Chúc bạn giảng dạy hiệu quả!',
          ),
        ],
        onDone: _complete,
        onSkip: _complete,
        showSkipButton: true,
        skip: Text('Bỏ qua',
            style: GoogleFonts.dmSans(
                fontSize: 14,
                fontWeight: FontWeight.w600,
                color: GradeFlowTheme.onSurfaceVariant)),
        next: Icon(LucideIcons.arrowRight, color: GradeFlowTheme.primary),
        done: Text('Bắt đầu',
            style: GoogleFonts.dmSans(
                fontSize: 15,
                fontWeight: FontWeight.w700,
                color: GradeFlowTheme.primary)),
        dotsDecorator: DotsDecorator(
          size: const Size(10, 10),
          color: GradeFlowTheme.outlineVariant,
          activeSize: const Size(24, 10),
          activeColor: GradeFlowTheme.primary,
          activeShape: RoundedRectangleBorder(
            borderRadius: BorderRadius.circular(25),
          ),
          spacing: const EdgeInsets.symmetric(horizontal: 3),
        ),
        controlsPadding:
            const EdgeInsets.symmetric(horizontal: 16, vertical: 12),
      ),
    );
  }
}
