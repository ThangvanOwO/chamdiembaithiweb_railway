import 'package:flutter/material.dart';
import 'academic_ui.dart';

/// Read-only view of the API answer key; never guesses or mutates answers.
class AnswerKeyReview extends StatelessWidget {
  final Map<String, dynamic> variant;
  final int part1Count, part2Count, part3Count;
  const AnswerKeyReview({super.key, required this.variant, required this.part1Count,
    required this.part2Count, required this.part3Count});
  String answer(dynamic value) => value == null || '$value'.trim().isEmpty ? '—' : '$value';
  @override
  Widget build(BuildContext context) {
    final p1 = Map<String, dynamic>.from(variant['p1'] ?? {});
    final p2 = Map<String, dynamic>.from(variant['p2'] ?? {});
    final p3 = Map<String, dynamic>.from(variant['p3'] ?? {});
    return Column(crossAxisAlignment: CrossAxisAlignment.stretch, children: [
      if (part1Count > 0) ...[
        AcademicHeading(eyebrow: 'Phần I · $part1Count câu', title: 'Trắc nghiệm'),
        const SizedBox(height: 14), _grid(context, p1, part1Count), const SizedBox(height: 28),
      ],
      if (part2Count > 0) ...[
        AcademicHeading(eyebrow: 'Phần II · $part2Count câu', title: 'Đúng / Sai'),
        const SizedBox(height: 14),
        for (var i = 1; i <= part2Count; i++) Padding(padding: const EdgeInsets.only(bottom: 10),
          child: AcademicCard(padding: const EdgeInsets.all(16), child: Column(
            crossAxisAlignment: CrossAxisAlignment.start, children: [
            Text('Câu $i', style: const TextStyle(fontWeight: FontWeight.w700, color: AcademicStyle.ink)),
            const SizedBox(height: 12), Wrap(spacing: 8, runSpacing: 8, children: [
              for (final key in ['a','b','c','d']) _cell(context, key,
                answer(p2['$i'] is Map ? p2['$i'][key] : null), compact: true),
            ]),
          ]))),
        const SizedBox(height: 18),
      ],
      if (part3Count > 0) ...[
        AcademicHeading(eyebrow: 'Phần III · $part3Count câu', title: 'Trả lời ngắn'),
        const SizedBox(height: 14), _grid(context, p3, part3Count, wide: true),
      ],
    ]);
  }
  Widget _grid(BuildContext context, Map<String, dynamic> values, int count, {bool wide = false}) =>
    LayoutBuilder(builder: (context, box) {
      final target = (wide ? 105 : 62) * MediaQuery.textScalerOf(context).scale(1).clamp(1, 2);
      final columns = ((box.maxWidth + 8) / (target + 8)).floor().clamp(1, 6);
      final width = (box.maxWidth - (columns-1)*8) / columns;
      return Wrap(spacing: 8, runSpacing: 8, children: [for (var i=1; i<=count; i++)
        SizedBox(width: width, child: _cell(context, 'Câu $i', answer(values['$i'])))]);
    });
  Widget _cell(BuildContext context, String label, String value, {bool compact = false}) {
    final uncertain = value == '—' || value == 'X' || value.contains('?');
    final status = value == '—' ? 'Chưa có đáp án xác nhận' : uncertain ? 'Cần kiểm tra' : value;
    return Semantics(label: '$label: $status', excludeSemantics: true,
      child: Container(padding: EdgeInsets.symmetric(horizontal: compact ? 14 : 8, vertical: 12),
        decoration: BoxDecoration(color: uncertain ? AcademicStyle.paper : AcademicStyle.mint,
          borderRadius: BorderRadius.circular(12), border: Border.all(color: AcademicStyle.line)),
        child: compact ? Text('$label) $value', style: const TextStyle(fontSize: 15,
          fontWeight: FontWeight.w600, color: AcademicStyle.ink)) : Column(children: [
          Text(label, style: const TextStyle(fontSize: 12, color: AcademicStyle.muted)),
          const SizedBox(height: 7), Text(value, style: TextStyle(fontSize: 19,
            fontWeight: FontWeight.w800, color: uncertain ? AcademicStyle.muted : AcademicStyle.teal)),
        ])));
  }
}
