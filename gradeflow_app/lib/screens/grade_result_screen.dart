import 'dart:convert';
import 'dart:typed_data';
import 'package:flutter/material.dart';
import 'package:google_fonts/google_fonts.dart';
import 'package:lucide_icons/lucide_icons.dart';

import '../config/theme.dart';
import '../models/grade_result.dart';

class GradeResultScreen extends StatelessWidget {
  final GradeResult result;
  final Uint8List imageBytes;
  final String? examTitle;

  const GradeResultScreen({
    super.key,
    required this.result,
    required this.imageBytes,
    this.examTitle,
  });

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      appBar: AppBar(
        title: const Text('Kết quả chấm'),
        leading: IconButton(
          icon: const Icon(LucideIcons.arrowLeft),
          onPressed: () => Navigator.pop(context),
        ),
      ),
      body: result.success ? _buildSuccess(context) : _buildError(context),
    );
  }

  Widget _buildError(BuildContext context) {
    return Center(
      child: Padding(
        padding: const EdgeInsets.all(24),
        child: Column(
          mainAxisAlignment: MainAxisAlignment.center,
          children: [
            Container(
              width: 72,
              height: 72,
              decoration: BoxDecoration(
                color: GradeFlowTheme.errorContainer,
                borderRadius: BorderRadius.circular(20),
              ),
              child: const Icon(LucideIcons.alertTriangle,
                  size: 36, color: GradeFlowTheme.error),
            ),
            const SizedBox(height: 20),
            Text('Không nhận diện được',
                style: GoogleFonts.manrope(
                    fontSize: 20, fontWeight: FontWeight.w700)),
            const SizedBox(height: 8),
            Text(result.error,
                style: GoogleFonts.dmSans(
                    fontSize: 14, color: GradeFlowTheme.onSurfaceVariant),
                textAlign: TextAlign.center),
            const SizedBox(height: 32),
            ElevatedButton.icon(
              onPressed: () => Navigator.pop(context),
              icon: const Icon(LucideIcons.scan, size: 18),
              label: const Text('Quét lại'),
            ),
          ],
        ),
      ),
    );
  }

  Widget _buildSuccess(BuildContext context) {
    final gradeColor = GradeFlowTheme.gradeColor(result.gradeLabel);
    final gradeBg = GradeFlowTheme.gradeBackground(result.gradeLabel);

    return ListView(
      padding: const EdgeInsets.all(16),
      children: [
        // ── Score Hero Card ──
        Card(
          child: Padding(
            padding: const EdgeInsets.all(20),
            child: Column(
              children: [
                Container(
                  width: 110,
                  height: 110,
                  decoration: BoxDecoration(
                    color: gradeBg,
                    shape: BoxShape.circle,
                    border: Border.all(
                        color: gradeColor.withOpacity(0.3), width: 3),
                  ),
                  child: Center(
                    child: Column(
                      mainAxisAlignment: MainAxisAlignment.center,
                      children: [
                        Text(
                          result.score != null
                              ? result.score!.toStringAsFixed(2)
                              : '—',
                          style: GoogleFonts.manrope(
                              fontSize: 32,
                              fontWeight: FontWeight.w800,
                              color: gradeColor),
                        ),
                        Text(result.gradeText,
                            style: GoogleFonts.dmSans(
                                fontSize: 12,
                                fontWeight: FontWeight.w600,
                                color: gradeColor)),
                      ],
                    ),
                  ),
                ),
                const SizedBox(height: 16),
                if (examTitle != null)
                  Text(examTitle!,
                      style: GoogleFonts.dmSans(
                          fontSize: 15, fontWeight: FontWeight.w600),
                      textAlign: TextAlign.center),
                const SizedBox(height: 12),
                Wrap(
                  spacing: 8,
                  runSpacing: 8,
                  alignment: WrapAlignment.center,
                  children: [
                    if (result.sbd.isNotEmpty)
                      _infoChip(LucideIcons.hash, 'SBD: ${result.sbd}'),
                    if (result.made.isNotEmpty)
                      _infoChip(
                          LucideIcons.fileText, 'Mã đề: ${result.made}'),
                    if (result.correctCount != null &&
                        result.totalQuestions != null)
                      _infoChip(LucideIcons.checkSquare,
                          '${result.correctCount}/${result.totalQuestions} câu'),
                    _infoChip(LucideIcons.timer,
                        '${result.processingTime.toStringAsFixed(1)}s'),
                  ],
                ),
              ],
            ),
          ),
        ),
        const SizedBox(height: 16),

        // ── Part Scores ──
        if (result.weighted != null) _buildPartScores(),
        const SizedBox(height: 16),

        // ── Result Image (annotated overlay from engine) ──
        if (result.resultImageBase64.isNotEmpty)
          _buildResultImage(),
        if (result.resultImageBase64.isEmpty)
          _buildScannedImage(),
        const SizedBox(height: 16),

        // ── Part I: Trắc nghiệm ABCD ──
        if (result.part1.isNotEmpty)
          _buildAnswerGrid('Phần I — Trắc nghiệm', result.part1, 1),
        const SizedBox(height: 12),

        // ── Part II: Đúng/Sai ──
        if (result.part2.isNotEmpty)
          _buildPart2Answers(),
        const SizedBox(height: 12),

        // ── Part III: Trả lời ngắn ──
        if (result.part3.isNotEmpty)
          _buildPart3Answers(),
        const SizedBox(height: 20),

        // ── Actions ──
        Row(
          children: [
            Expanded(
              child: ElevatedButton.icon(
                onPressed: () => Navigator.pop(context),
                icon: const Icon(LucideIcons.scan, size: 18),
                label: const Text('Quét tiếp'),
              ),
            ),
          ],
        ),
        const SizedBox(height: 32),
      ],
    );
  }

  // ── Part Scores Card ──
  Widget _buildPartScores() {
    final w = result.weighted!;
    return Card(
      child: Padding(
        padding: const EdgeInsets.all(16),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            Row(
              children: [
                Icon(LucideIcons.barChart3,
                    size: 16, color: GradeFlowTheme.primary),
                const SizedBox(width: 8),
                Text('Chi tiết điểm',
                    style: GoogleFonts.dmSans(
                        fontSize: 15, fontWeight: FontWeight.w600)),
              ],
            ),
            const SizedBox(height: 12),
            _partScoreRow('Phần I (Trắc nghiệm)',
                '${w['p1_correct']} câu đúng', '${w['p1_score']} đ'),
            const Divider(height: 16),
            _partScoreRow('Phần II (Đúng/Sai)',
                '${w['p2_correct']} ý đúng', '${w['p2_score']} đ'),
            const Divider(height: 16),
            _partScoreRow('Phần III (Trả lời ngắn)',
                '${w['p3_correct']} câu đúng', '${w['p3_score']} đ'),
          ],
        ),
      ),
    );
  }

  Widget _partScoreRow(String label, String detail, String score) {
    return Row(
      children: [
        Expanded(
          child: Column(
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              Text(label,
                  style: GoogleFonts.dmSans(
                      fontSize: 13, fontWeight: FontWeight.w600)),
              Text(detail,
                  style: GoogleFonts.dmSans(
                      fontSize: 12, color: GradeFlowTheme.onSurfaceVariant)),
            ],
          ),
        ),
        Text(score,
            style: GoogleFonts.manrope(
                fontSize: 16,
                fontWeight: FontWeight.w700,
                color: GradeFlowTheme.primary)),
      ],
    );
  }

  // ── Result Image (annotated by engine) ──
  Widget _buildResultImage() {
    final bytes = base64Decode(result.resultImageBase64);
    return Card(
      child: Padding(
        padding: const EdgeInsets.all(16),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            Row(
              children: [
                Icon(LucideIcons.scanLine,
                    size: 16, color: GradeFlowTheme.primary),
                const SizedBox(width: 8),
                Text('Ảnh kết quả (đánh dấu đúng/sai)',
                    style: GoogleFonts.dmSans(
                        fontSize: 14, fontWeight: FontWeight.w600)),
              ],
            ),
            const SizedBox(height: 12),
            ClipRRect(
              borderRadius: BorderRadius.circular(10),
              child: InteractiveViewer(
                minScale: 1.0,
                maxScale: 4.0,
                child: Image.memory(bytes,
                    width: double.infinity, fit: BoxFit.contain),
              ),
            ),
            const SizedBox(height: 6),
            Text('Pinch để phóng to xem chi tiết',
                style: GoogleFonts.dmSans(
                    fontSize: 11, color: GradeFlowTheme.onSurfaceVariant),
                textAlign: TextAlign.center),
          ],
        ),
      ),
    );
  }

  Widget _buildScannedImage() {
    return Card(
      child: Padding(
        padding: const EdgeInsets.all(16),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            Row(
              children: [
                Icon(LucideIcons.image,
                    size: 16, color: GradeFlowTheme.primary),
                const SizedBox(width: 8),
                Text('Ảnh đã quét',
                    style: GoogleFonts.dmSans(
                        fontSize: 14, fontWeight: FontWeight.w600)),
              ],
            ),
            const SizedBox(height: 12),
            ClipRRect(
              borderRadius: BorderRadius.circular(10),
              child: InteractiveViewer(
                minScale: 1.0,
                maxScale: 4.0,
                child: Image.memory(imageBytes,
                    width: double.infinity, fit: BoxFit.contain),
              ),
            ),
          ],
        ),
      ),
    );
  }

  // ── Part I: Trắc nghiệm grid with correct/wrong ──
  Widget _buildAnswerGrid(
      String title, Map<String, dynamic> answers, int partStart) {
    final entries = answers.entries.toList();
    entries.sort((a, b) {
      final ai = int.tryParse(a.key) ?? 0;
      final bi = int.tryParse(b.key) ?? 0;
      return ai.compareTo(bi);
    });

    return Card(
      child: Padding(
        padding: const EdgeInsets.all(16),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            Row(
              children: [
                Icon(LucideIcons.listChecks,
                    size: 16, color: GradeFlowTheme.primary),
                const SizedBox(width: 8),
                Text(title,
                    style: GoogleFonts.dmSans(
                        fontSize: 15, fontWeight: FontWeight.w600)),
              ],
            ),
            const SizedBox(height: 12),
            Wrap(
              spacing: 6,
              runSpacing: 6,
              children: entries.map((e) {
                final detected = '${e.value}';
                final correct = result.correctAnswers[e.key];
                final isCorrect =
                    correct != null && '$correct' == detected;
                final hasCorrect = correct != null;

                return Container(
                  width: 52,
                  padding: const EdgeInsets.symmetric(
                      horizontal: 4, vertical: 6),
                  decoration: BoxDecoration(
                    color: hasCorrect
                        ? (isCorrect
                            ? const Color(0xFFE8F5E9)
                            : const Color(0xFFFFEBEE))
                        : GradeFlowTheme.surfaceContainerLow,
                    borderRadius: BorderRadius.circular(8),
                    border: Border.all(
                      color: hasCorrect
                          ? (isCorrect
                              ? const Color(0xFF4CAF50)
                              : const Color(0xFFE53935))
                          : GradeFlowTheme.outlineVariant,
                      width: 1,
                    ),
                  ),
                  child: Column(
                    children: [
                      Text('C${e.key}',
                          style: GoogleFonts.dmSans(
                              fontSize: 9,
                              color: GradeFlowTheme.onSurfaceVariant)),
                      Text(detected,
                          style: GoogleFonts.manrope(
                              fontSize: 14,
                              fontWeight: FontWeight.w700,
                              color: hasCorrect
                                  ? (isCorrect
                                      ? const Color(0xFF2E7D32)
                                      : const Color(0xFFC62828))
                                  : GradeFlowTheme.primary)),
                      if (hasCorrect && !isCorrect)
                        Text('→$correct',
                            style: GoogleFonts.dmSans(
                                fontSize: 9,
                                fontWeight: FontWeight.w600,
                                color: const Color(0xFF2E7D32))),
                    ],
                  ),
                );
              }).toList(),
            ),
          ],
        ),
      ),
    );
  }

  // ── Part II: Đúng/Sai ──
  Widget _buildPart2Answers() {
    final entries = result.part2.entries.toList();
    entries.sort((a, b) {
      final ai = int.tryParse(a.key) ?? 0;
      final bi = int.tryParse(b.key) ?? 0;
      return ai.compareTo(bi);
    });

    return Card(
      child: Padding(
        padding: const EdgeInsets.all(16),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            Row(
              children: [
                Icon(LucideIcons.toggleRight,
                    size: 16, color: GradeFlowTheme.primary),
                const SizedBox(width: 8),
                Text('Phần II — Đúng/Sai',
                    style: GoogleFonts.dmSans(
                        fontSize: 15, fontWeight: FontWeight.w600)),
              ],
            ),
            const SizedBox(height: 12),
            ...entries.map((e) {
              final qNum = e.key;
              final detected = e.value;
              // detected is typically a map: {a: "Đúng", b: "Sai", c: "Đúng", d: "Sai"}
              if (detected is Map) {
                return _buildPart2Question(qNum, Map<String, dynamic>.from(detected));
              }
              // Fallback: show raw
              return Padding(
                padding: const EdgeInsets.only(bottom: 8),
                child: Text('Câu $qNum: $detected',
                    style: GoogleFonts.dmSans(fontSize: 13)),
              );
            }),
          ],
        ),
      ),
    );
  }

  Widget _buildPart2Question(String qNum, Map<String, dynamic> detected) {
    // Get correct answers for this question
    final correctRaw = result.correctAnswers[qNum];
    Map<String, dynamic>? correct;
    if (correctRaw is Map) {
      correct = Map<String, dynamic>.from(correctRaw);
    }

    return Padding(
      padding: const EdgeInsets.only(bottom: 10),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Text('Câu $qNum',
              style: GoogleFonts.dmSans(
                  fontSize: 13, fontWeight: FontWeight.w600)),
          const SizedBox(height: 4),
          Wrap(
            spacing: 6,
            runSpacing: 4,
            children: detected.entries.map((sub) {
              final subKey = sub.key;
              final subVal = '${sub.value}';
              final correctVal =
                  correct != null ? '${correct[subKey] ?? ''}' : '';
              final isMatch =
                  correctVal.isNotEmpty && subVal == correctVal;
              final hasCorrect = correctVal.isNotEmpty;

              return Container(
                padding: const EdgeInsets.symmetric(
                    horizontal: 8, vertical: 4),
                decoration: BoxDecoration(
                  color: hasCorrect
                      ? (isMatch
                          ? const Color(0xFFE8F5E9)
                          : const Color(0xFFFFEBEE))
                      : GradeFlowTheme.surfaceContainerLow,
                  borderRadius: BorderRadius.circular(6),
                  border: Border.all(
                    color: hasCorrect
                        ? (isMatch
                            ? const Color(0xFF4CAF50)
                            : const Color(0xFFE53935))
                        : GradeFlowTheme.outlineVariant,
                    width: 0.8,
                  ),
                ),
                child: Text('$subKey: $subVal',
                    style: GoogleFonts.dmSans(
                        fontSize: 12,
                        fontWeight: FontWeight.w600,
                        color: hasCorrect
                            ? (isMatch
                                ? const Color(0xFF2E7D32)
                                : const Color(0xFFC62828))
                            : GradeFlowTheme.onSurface)),
              );
            }).toList(),
          ),
        ],
      ),
    );
  }

  // ── Part III: Trả lời ngắn ──
  Widget _buildPart3Answers() {
    final entries = result.part3.entries.toList();
    entries.sort((a, b) {
      final ai = int.tryParse(a.key) ?? 0;
      final bi = int.tryParse(b.key) ?? 0;
      return ai.compareTo(bi);
    });

    return Card(
      child: Padding(
        padding: const EdgeInsets.all(16),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            Row(
              children: [
                Icon(LucideIcons.pencil,
                    size: 16, color: GradeFlowTheme.primary),
                const SizedBox(width: 8),
                Text('Phần III — Trả lời ngắn',
                    style: GoogleFonts.dmSans(
                        fontSize: 15, fontWeight: FontWeight.w600)),
              ],
            ),
            const SizedBox(height: 12),
            ...entries.map((e) {
              final detected = '${e.value}';
              final correct = result.correctAnswers[e.key];
              final correctStr = correct != null ? '$correct' : '';
              final isCorrect =
                  correctStr.isNotEmpty && detected == correctStr;
              final hasCorrect = correctStr.isNotEmpty;

              return Padding(
                padding: const EdgeInsets.only(bottom: 8),
                child: Row(
                  children: [
                    SizedBox(
                      width: 50,
                      child: Text('C${e.key}',
                          style: GoogleFonts.dmSans(
                              fontSize: 13,
                              fontWeight: FontWeight.w600,
                              color: GradeFlowTheme.onSurfaceVariant)),
                    ),
                    Expanded(
                      child: Container(
                        padding: const EdgeInsets.symmetric(
                            horizontal: 12, vertical: 6),
                        decoration: BoxDecoration(
                          color: hasCorrect
                              ? (isCorrect
                                  ? const Color(0xFFE8F5E9)
                                  : const Color(0xFFFFEBEE))
                              : GradeFlowTheme.surfaceContainerLow,
                          borderRadius: BorderRadius.circular(8),
                          border: Border.all(
                            color: hasCorrect
                                ? (isCorrect
                                    ? const Color(0xFF4CAF50)
                                    : const Color(0xFFE53935))
                                : GradeFlowTheme.outlineVariant,
                            width: 0.8,
                          ),
                        ),
                        child: Row(
                          children: [
                            Icon(
                              hasCorrect
                                  ? (isCorrect
                                      ? LucideIcons.checkCircle
                                      : LucideIcons.xCircle)
                                  : LucideIcons.minus,
                              size: 14,
                              color: hasCorrect
                                  ? (isCorrect
                                      ? const Color(0xFF2E7D32)
                                      : const Color(0xFFC62828))
                                  : GradeFlowTheme.onSurfaceVariant,
                            ),
                            const SizedBox(width: 8),
                            Text(detected,
                                style: GoogleFonts.manrope(
                                    fontSize: 14,
                                    fontWeight: FontWeight.w700)),
                            if (hasCorrect && !isCorrect) ...[
                              const SizedBox(width: 8),
                              Text('→ $correctStr',
                                  style: GoogleFonts.dmSans(
                                      fontSize: 12,
                                      fontWeight: FontWeight.w600,
                                      color: const Color(0xFF2E7D32))),
                            ],
                          ],
                        ),
                      ),
                    ),
                  ],
                ),
              );
            }),
          ],
        ),
      ),
    );
  }

  Widget _infoChip(IconData icon, String text) {
    return Container(
      padding: const EdgeInsets.symmetric(horizontal: 10, vertical: 5),
      decoration: BoxDecoration(
        color: GradeFlowTheme.surfaceContainer,
        borderRadius: BorderRadius.circular(8),
      ),
      child: Row(
        mainAxisSize: MainAxisSize.min,
        children: [
          Icon(icon, size: 13, color: GradeFlowTheme.onSurfaceVariant),
          const SizedBox(width: 5),
          Text(text,
              style: GoogleFonts.dmSans(
                  fontSize: 12, color: GradeFlowTheme.onSurfaceVariant)),
        ],
      ),
    );
  }
}
