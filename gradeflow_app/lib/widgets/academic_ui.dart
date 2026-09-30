import 'package:flutter/material.dart';
import '../models/grade_result.dart';

/// Presentation-only tokens. Camera geometry and grading do not depend on these.
abstract final class AcademicStyle {
  static const ink = Color(0xFF173447);
  static const teal = Color(0xFF0F766E);
  static const paper = Color(0xFFF4F7F5);
  static const line = Color(0xFFDBE6E1);
  static const muted = Color(0xFF52666D);
  static const mint = Color(0xFFE5F2ED);
  static const amber = Color(0xFF795416);
  static const cream = Color(0xFFFFF5DE);
}

class AcademicReveal extends StatelessWidget {
  final Widget child;
  const AcademicReveal({super.key, required this.child});
  @override
  Widget build(BuildContext context) {
    final reduced = MediaQuery.disableAnimationsOf(context);
    return TweenAnimationBuilder<double>(
      tween: Tween(begin: reduced ? 1 : 0, end: 1),
      duration: reduced ? Duration.zero : const Duration(milliseconds: 240),
      curve: Curves.easeOutCubic,
      child: child,
      builder: (_, value, child) => Opacity(opacity: value,
        child: Transform.translate(offset: Offset(0, 10 * (1-value)), child: child)),
    );
  }
}

class AcademicCard extends StatelessWidget {
  final Widget child;
  final Color color;
  final EdgeInsetsGeometry padding;
  const AcademicCard({super.key, required this.child, this.color = Colors.white,
    this.padding = const EdgeInsets.all(20)});
  @override
  Widget build(BuildContext context) => Container(
    padding: padding,
    decoration: BoxDecoration(color: color, borderRadius: BorderRadius.circular(20),
      border: Border.all(color: AcademicStyle.line)),
    child: child,
  );
}

class AcademicHeading extends StatelessWidget {
  final String eyebrow, title, subtitle;
  const AcademicHeading({super.key, required this.eyebrow, required this.title, this.subtitle = ''});
  @override
  Widget build(BuildContext context) => Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
    Text(eyebrow.toUpperCase(), style: const TextStyle(fontSize: 11, letterSpacing: 1.6,
      fontWeight: FontWeight.w700, color: AcademicStyle.teal)),
    const SizedBox(height: 8),
    Text(title, style: Theme.of(context).textTheme.headlineMedium?.copyWith(
      fontWeight: FontWeight.w800, color: AcademicStyle.ink)),
    if (subtitle.isNotEmpty) ...[const SizedBox(height: 6), Text(subtitle,
      style: const TextStyle(fontSize: 14, height: 1.5, color: AcademicStyle.muted))],
  ]);
}

class AcademicNotice extends StatelessWidget {
  final String title, message;
  final bool warning;
  const AcademicNotice({super.key, required this.title, required this.message, this.warning = false});
  @override
  Widget build(BuildContext context) => AcademicCard(
    color: warning ? AcademicStyle.cream : AcademicStyle.mint,
    padding: const EdgeInsets.all(16),
    child: Row(crossAxisAlignment: CrossAxisAlignment.start, children: [
      Icon(warning ? Icons.info_outline_rounded : Icons.school_outlined,
        color: warning ? AcademicStyle.amber : AcademicStyle.teal, size: 22),
      const SizedBox(width: 12),
      Expanded(child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
        Text(title, style: const TextStyle(fontWeight: FontWeight.w700, color: AcademicStyle.ink)),
        const SizedBox(height: 4),
        Text(message, style: const TextStyle(fontSize: 14, height: 1.5, color: AcademicStyle.ink)),
      ])),
    ]),
  );
}

class AcademicMetric extends StatelessWidget {
  final String value, label;
  const AcademicMetric({super.key, required this.value, required this.label});
  @override
  Widget build(BuildContext context) => Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
    Text(value, style: const TextStyle(fontSize: 25, fontWeight: FontWeight.w800, color: AcademicStyle.ink)),
    const SizedBox(height: 4),
    Text(label, style: const TextStyle(fontSize: 13, color: AcademicStyle.muted)),
  ]);
}

class AcademicScoreSummary extends StatelessWidget {
  final GradeResult result;
  final String? examTitle;
  const AcademicScoreSummary({super.key, required this.result, this.examTitle});
  @override
  Widget build(BuildContext context) => AcademicReveal(child: AcademicCard(child: Column(
    crossAxisAlignment: CrossAxisAlignment.start, children: [
      const AcademicHeading(eyebrow: 'Phiếu kết quả', title: 'Kết quả bài làm'),
      if (examTitle?.isNotEmpty == true) ...[const SizedBox(height: 8), Text(examTitle!,
        style: const TextStyle(fontSize: 16, color: AcademicStyle.muted))],
      const SizedBox(height: 24),
      Container(width: double.infinity, padding: const EdgeInsets.all(20),
        decoration: BoxDecoration(color: AcademicStyle.mint, borderRadius: BorderRadius.circular(16)),
        child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
          const Text('ĐIỂM BÀI LÀM', style: TextStyle(fontSize: 12, letterSpacing: 1.2,
            color: AcademicStyle.teal, fontWeight: FontWeight.w700)),
          Text(result.score?.toStringAsFixed(2) ?? '—', style: const TextStyle(
            fontSize: 48, fontWeight: FontWeight.w800, color: AcademicStyle.ink)),
          Text(result.gradeText, style: const TextStyle(fontSize: 15, color: AcademicStyle.ink)),
        ])),
      const SizedBox(height: 20),
      Wrap(spacing: 28, runSpacing: 16, children: [
        AcademicMetric(value: result.sbd.isEmpty ? '—' : result.sbd, label: 'Số báo danh'),
        AcademicMetric(value: result.made.isEmpty ? '—' : result.made, label: 'Mã đề'),
        if (result.correctCount != null && result.totalQuestions != null)
          AcademicMetric(value: '${result.correctCount}/${result.totalQuestions}', label: 'Câu đúng'),
      ]),
      const SizedBox(height: 18),
      Text('${result.processingTime.toStringAsFixed(1)} giây xử lý · '
        '${result.submissionId != null ? 'Đã lưu bài chấm' : 'Chưa có xác nhận lưu bài'}',
        style: const TextStyle(fontSize: 12, color: AcademicStyle.muted)),
    ])));
}
