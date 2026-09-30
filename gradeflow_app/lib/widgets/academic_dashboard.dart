import 'package:flutter/material.dart';
import 'academic_ui.dart';
import 'ad_banner.dart';

class AcademicDashboard extends StatelessWidget {
  final String name;
  final Map<String, dynamic> stats;
  final List<Widget> recent;
  final ValueChanged<int>? onNavigate;
  const AcademicDashboard({super.key, required this.name, required this.stats,
    required this.recent, this.onNavigate});
  @override
  Widget build(BuildContext context) => ListView(
    padding: const EdgeInsets.fromLTRB(20, 12, 20, 32),
    physics: const AlwaysScrollableScrollPhysics(),
    children: [
      AcademicReveal(child: Container(
        padding: const EdgeInsets.all(24),
        decoration: BoxDecoration(borderRadius: BorderRadius.circular(24),
          gradient: const LinearGradient(begin: Alignment.topLeft, end: Alignment.bottomRight,
            colors: [AcademicStyle.ink, Color(0xFF155F5A)])),
        child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
          const Row(children: [Icon(Icons.auto_stories_outlined, color: Color(0xFFF2DCA0), size: 24),
            SizedBox(width: 10), Expanded(child: Text('KHÔNG GIAN GIÁO DỤC',
              style: TextStyle(fontSize: 11, letterSpacing: 1.5, color: Color(0xFFF2DCA0))))]),
          const SizedBox(height: 24),
          Text('Xin chào, $name', style: Theme.of(context).textTheme.headlineMedium?.copyWith(
            color: Colors.white, fontWeight: FontWeight.w800)),
          const SizedBox(height: 10),
          const Text('Nhẹ việc chấm bài.\nThêm thời gian cho lớp học.',
            style: TextStyle(color: Color(0xFFDEEEE8), fontSize: 16, height: 1.5)),
        ]))),
      const SizedBox(height: 20),
      LayoutBuilder(builder: (context, box) {
        final stacked = box.maxWidth < 340 || MediaQuery.textScalerOf(context).scale(1) > 1.3;
        final scan = FilledButton.icon(onPressed: onNavigate == null ? null : () => onNavigate!(2),
          icon: const Icon(Icons.document_scanner_outlined), label: const Text('Chấm bài'),
          style: FilledButton.styleFrom(minimumSize: const Size(0, 52), backgroundColor: AcademicStyle.teal));
        final exams = OutlinedButton.icon(onPressed: onNavigate == null ? null : () => onNavigate!(1),
          icon: const Icon(Icons.library_books_outlined), label: const Text('Đề thi'),
          style: OutlinedButton.styleFrom(minimumSize: const Size(0, 52)));
        return stacked ? Column(crossAxisAlignment: CrossAxisAlignment.stretch,
          children: [scan, const SizedBox(height: 10), exams]) : Row(children: [
          Expanded(child: scan), const SizedBox(width: 12), Expanded(child: exams)]);
      }),
      const SizedBox(height: 28),
      const AcademicHeading(eyebrow: 'Sổ công tác', title: 'Hoạt động của bạn'),
      const SizedBox(height: 16),
      LayoutBuilder(builder: (context, box) {
        final columns = MediaQuery.textScalerOf(context).scale(1) > 1.5 ? 1 : 2;
        final width = (box.maxWidth - 12 * (columns - 1)) / columns;
        final items = [
          ('${stats['total_exams'] ?? 0}', 'Đề thi', Icons.library_books_outlined),
          ('${stats['total_graded'] ?? 0}', 'Bài đã chấm', Icons.task_alt_outlined),
          ('${stats['avg_score'] ?? '—'}', 'Điểm trung bình', Icons.insights_outlined),
          (stats['pass_rate'] == null ? '—' : '${stats['pass_rate']}%', 'Tỉ lệ đạt', Icons.bar_chart_rounded),
        ];
        return Wrap(spacing: 12, runSpacing: 12, children: [for (final item in items)
          SizedBox(width: width, child: AcademicCard(child: Column(
            crossAxisAlignment: CrossAxisAlignment.start, children: [
            Icon(item.$3, color: AcademicStyle.teal, size: 23), const SizedBox(height: 18),
            AcademicMetric(value: item.$1, label: item.$2),
          ])))]);
      }),
      const SizedBox(height: 28),
      const InlineAdBanner(),
      const AcademicHeading(eyebrow: 'Tiếp nối công việc', title: 'Bài chấm gần đây'),
      const SizedBox(height: 16),
      if (recent.isEmpty) const AcademicNotice(title: 'Sẵn sàng cho bài chấm đầu tiên',
        message: 'Tạo đề và kiểm tra đáp án mẫu, sau đó quét phiếu học sinh. Kết quả sẽ xuất hiện ở đây.')
      else ...recent,
    ],
  );
}
