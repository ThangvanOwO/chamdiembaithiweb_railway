import 'dart:convert';
import 'dart:typed_data';
import 'package:flutter/material.dart';
import 'package:flutter/services.dart';
import 'package:google_fonts/google_fonts.dart';
import 'package:lucide_icons/lucide_icons.dart';

import '../config/theme.dart';
import '../models/grade_result.dart';
import '../widgets/academic_ui.dart';
import 'training_correction_screen.dart';

class GradeResultScreen extends StatefulWidget {
  final GradeResult result;
  final Uint8List imageBytes;
  final String? examTitle;
  final bool isAdmin;
  final String templateCode;
  final List<List<double>>? trainingCorners;

  const GradeResultScreen({
    super.key,
    required this.result,
    required this.imageBytes,
    this.examTitle,
    this.isAdmin = false,
    this.templateCode = '40-08-06',
    this.trainingCorners,
  });

  @override
  State<GradeResultScreen> createState() => _GradeResultScreenState();
}

class _GradeResultScreenState extends State<GradeResultScreen> {
  bool _debugExpanded = false;

  GradeResult get result => widget.result;
  Uint8List get imageBytes => widget.imageBytes;
  String? get examTitle => widget.examTitle;
  bool get isAdmin => widget.isAdmin;

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      backgroundColor: AcademicStyle.paper,
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
    return ListView(
      padding: const EdgeInsets.all(20),
      children: [
        AcademicScoreSummary(result: result, examTitle: examTitle),
        const SizedBox(height: 16),
        if (result.qualityWarning.isNotEmpty || result.validationWarnings.isNotEmpty) ...[
          AcademicNotice(title: 'Một số thông tin cần đối chiếu',
            message: result.qualityWarning.isNotEmpty ? result.qualityWarning :
              '${result.validationWarnings.length} cảnh báo nhận diện. Kiểm tra phiếu và các đáp án bên dưới.',
            warning: true),
          if (result.validationWarnings.isNotEmpty)
            ExpansionTile(title: const Text('Xem cảnh báo'),
              children: [Padding(padding: const EdgeInsets.all(16),
                child: Text(result.validationWarnings.join('\n')))]),
          const SizedBox(height: 16),
        ],

        // ── Name crop image (cropped from scanned sheet) ──
        if (result.nameImageBase64.isNotEmpty)
          _buildNameCrop(),
        const SizedBox(height: 12),

        // ── Part Scores ──
        if (result.weighted != null) _buildPartScores(),
        const SizedBox(height: 16),

        // ── Result Image or Visual Answer Overlay ──
        if (result.resultImageBase64.isNotEmpty)
          _buildResultImage(),
        if (result.resultImageBase64.isEmpty && result.part1.isNotEmpty)
          _buildAnswerBubbleOverlay(),
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
        const SizedBox(height: 12),

        // ── Debug Diagnostics (collapsible, admin only) ──
        if (isAdmin) _buildDebugPanel(),
        const SizedBox(height: 20),

        // ── Actions ──
        if (isAdmin) ...[
          OutlinedButton.icon(
            onPressed: () => Navigator.push(context, MaterialPageRoute(builder: (_) =>
              TrainingCorrectionScreen(imageBytes: imageBytes, result: result,
                templateCode: widget.templateCode, corners: widget.trainingCorners))),
            icon: const Icon(Icons.psychology_outlined, size: 18),
            label: const Text('Training AI · Lấy phiếu / sửa dấu tô'),
          ),
          const SizedBox(height: 12),
        ],
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

  // ── Name Crop Image ──
  Widget _buildNameCrop() {
    final bytes = base64Decode(result.nameImageBase64);
    return Card(
      child: Padding(
        padding: const EdgeInsets.all(14),
        child: Row(
          children: [
            Icon(LucideIcons.user, size: 16, color: GradeFlowTheme.primary),
            const SizedBox(width: 8),
            Text('Họ tên học sinh',
                style: GoogleFonts.dmSans(
                    fontSize: 13, fontWeight: FontWeight.w600)),
            const SizedBox(width: 12),
            Expanded(
              child: ClipRRect(
                borderRadius: BorderRadius.circular(6),
                child: Image.memory(bytes,
                    height: 36, fit: BoxFit.contain,
                    alignment: Alignment.centerLeft),
              ),
            ),
          ],
        ),
      ),
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

  /// Visual answer bubble overlay — shows ABCD bubbles with
  /// green circle = correct, red circle = wrong, arrow to correct answer
  Widget _buildAnswerBubbleOverlay() {
    const choices = ['A', 'B', 'C', 'D'];
    final entries = result.part1.entries.toList();
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
                Icon(LucideIcons.checkCircle,
                    size: 16, color: GradeFlowTheme.primary),
                const SizedBox(width: 8),
                Text('Kết quả đánh dấu',
                    style: GoogleFonts.dmSans(
                        fontSize: 15, fontWeight: FontWeight.w600)),
              ],
            ),
            const SizedBox(height: 6),
            Row(
              children: [
                _legendDot(const Color(0xFF4CAF50), 'Đúng'),
                const SizedBox(width: 12),
                _legendDot(const Color(0xFFE53935), 'Sai'),
                const SizedBox(width: 12),
                _legendDot(const Color(0xFF2196F3), 'Đáp án đúng'),
              ],
            ),
            const SizedBox(height: 12),
            // Bubble grid
            ...entries.map((e) {
              final qNum = e.key;
              final detected = '${e.value}'.toUpperCase();
              final correctRaw = result.correctAnswers[qNum];
              final correct = correctRaw != null ? '$correctRaw'.toUpperCase() : '';
              final hasCorrect = correct.isNotEmpty;
              final isCorrect = hasCorrect && detected == correct;

              return Padding(
                padding: const EdgeInsets.only(bottom: 4),
                child: Row(
                  children: [
                    SizedBox(
                      width: 36,
                      child: Text('C$qNum',
                          style: GoogleFonts.dmSans(
                              fontSize: 12,
                              fontWeight: FontWeight.w600,
                              color: GradeFlowTheme.onSurfaceVariant)),
                    ),
                    ...choices.map((ch) {
                      final isDetected = detected == ch;
                      final isCorrectChoice = correct == ch;

                      Color bgColor;
                      Color borderColor;
                      Color textColor;
                      double borderWidth = 1.5;

                      if (isDetected && isCorrect) {
                        // Student chose this and it's correct
                        bgColor = const Color(0xFFE8F5E9);
                        borderColor = const Color(0xFF4CAF50);
                        textColor = const Color(0xFF2E7D32);
                        borderWidth = 2.5;
                      } else if (isDetected && !isCorrect && hasCorrect) {
                        // Student chose this but it's wrong
                        bgColor = const Color(0xFFFFEBEE);
                        borderColor = const Color(0xFFE53935);
                        textColor = const Color(0xFFC62828);
                        borderWidth = 2.5;
                      } else if (!isDetected && isCorrectChoice && hasCorrect && !isCorrect) {
                        // This is the correct answer (student got it wrong)
                        bgColor = const Color(0xFFE3F2FD);
                        borderColor = const Color(0xFF2196F3);
                        textColor = const Color(0xFF1565C0);
                        borderWidth = 2.0;
                      } else if (isDetected && !hasCorrect) {
                        // Detected but no answer key
                        bgColor = GradeFlowTheme.primary.withOpacity(0.08);
                        borderColor = GradeFlowTheme.primary.withOpacity(0.4);
                        textColor = GradeFlowTheme.primary;
                        borderWidth = 2.0;
                      } else {
                        // Empty bubble
                        bgColor = GradeFlowTheme.surfaceContainerLow;
                        borderColor = GradeFlowTheme.outlineVariant;
                        textColor = GradeFlowTheme.onSurfaceVariant.withOpacity(0.5);
                        borderWidth = 1.0;
                      }

                      return Expanded(
                        child: Container(
                          margin: const EdgeInsets.symmetric(horizontal: 3),
                          padding: const EdgeInsets.symmetric(vertical: 8),
                          decoration: BoxDecoration(
                            color: bgColor,
                            borderRadius: BorderRadius.circular(20),
                            border: Border.all(
                                color: borderColor, width: borderWidth),
                          ),
                          child: Center(
                            child: Text(ch,
                                style: GoogleFonts.manrope(
                                    fontSize: 13,
                                    fontWeight: FontWeight.w700,
                                    color: textColor)),
                          ),
                        ),
                      );
                    }),
                    // Result icon
                    SizedBox(
                      width: 28,
                      child: hasCorrect
                          ? Icon(
                              isCorrect
                                  ? LucideIcons.checkCircle2
                                  : LucideIcons.xCircle,
                              size: 16,
                              color: isCorrect
                                  ? const Color(0xFF4CAF50)
                                  : const Color(0xFFE53935),
                            )
                          : const SizedBox.shrink(),
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

  Widget _legendDot(Color color, String text) {
    return Row(
      mainAxisSize: MainAxisSize.min,
      children: [
        Container(
          width: 10,
          height: 10,
          decoration: BoxDecoration(
            color: color.withOpacity(0.2),
            shape: BoxShape.circle,
            border: Border.all(color: color, width: 2),
          ),
        ),
        const SizedBox(width: 4),
        Text(text,
            style: GoogleFonts.dmSans(
                fontSize: 10, color: GradeFlowTheme.onSurfaceVariant)),
      ],
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

  Widget _buildDebugPanel() {
    final summary = StringBuffer();
    summary.writeln('=== Scan Diagnostics ===');
    summary.writeln('Method: ${result.detectMethod}');
    summary.writeln('Preprocess: ${result.preprocessMode}');
    summary.writeln('Avg Confidence: ${result.avgConfidence.toStringAsFixed(3)}');
    summary.writeln('Quality: ${result.scanQuality}');
    summary.writeln('Time: ${result.processingTime}s');
    if (result.offsets.isNotEmpty) {
      summary.writeln('Offsets: ${result.offsets}');
    }
    if (result.qualityWarning.isNotEmpty) {
      summary.writeln('Warning: ${result.qualityWarning}');
    }
    for (final w in result.validationWarnings) {
      summary.writeln('  ! $w');
    }
    if (result.debugLog.isNotEmpty) {
      summary.writeln('\n--- Engine Log ---');
      summary.writeln(result.debugLog);
    }
    final fullText = summary.toString();

    return Card(
      child: Column(
        children: [
          InkWell(
            onTap: () => setState(() => _debugExpanded = !_debugExpanded),
            borderRadius: BorderRadius.circular(12),
            child: Padding(
              padding: const EdgeInsets.symmetric(horizontal: 16, vertical: 12),
              child: Row(
                children: [
                  Icon(LucideIcons.bug, size: 16, color: GradeFlowTheme.onSurfaceVariant),
                  const SizedBox(width: 8),
                  Expanded(
                    child: Text('Thông số chẩn đoán',
                        style: GoogleFonts.dmSans(
                            fontSize: 13, fontWeight: FontWeight.w600)),
                  ),
                  // Quick stats
                  Container(
                    padding: const EdgeInsets.symmetric(horizontal: 6, vertical: 2),
                    decoration: BoxDecoration(
                      color: result.scanQuality == 'OK'
                          ? const Color(0xFFE8F5E9)
                          : const Color(0xFFFFF3E0),
                      borderRadius: BorderRadius.circular(4),
                    ),
                    child: Text(
                      '${result.detectMethod} | conf=${result.avgConfidence.toStringAsFixed(2)}',
                      style: GoogleFonts.dmSans(fontSize: 10, fontWeight: FontWeight.w600),
                    ),
                  ),
                  const SizedBox(width: 8),
                  Icon(
                    _debugExpanded ? LucideIcons.chevronUp : LucideIcons.chevronDown,
                    size: 16,
                    color: GradeFlowTheme.onSurfaceVariant,
                  ),
                ],
              ),
            ),
          ),
          if (_debugExpanded) ...[
            const Divider(height: 1),
            Padding(
              padding: const EdgeInsets.all(12),
              child: Column(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  _debugRow('Method', result.detectMethod),
                  _debugRow('Preprocess', result.preprocessMode),
                  _debugRow('Avg Confidence', result.avgConfidence.toStringAsFixed(3)),
                  _debugRow('Scan Quality', result.scanQuality),
                  _debugRow('Time', '${result.processingTime}s'),
                  if (result.offsets.isNotEmpty)
                    _debugRow('Offsets', result.offsets.entries.map((e) => '${e.key}=${e.value}').join(', ')),
                  if (result.qualityWarning.isNotEmpty)
                    _debugRow('Warning', result.qualityWarning),
                  for (final w in result.validationWarnings)
                    Padding(
                      padding: const EdgeInsets.only(top: 2),
                      child: Text('⚠ $w',
                          style: GoogleFonts.dmSans(fontSize: 11, color: const Color(0xFFE65100))),
                    ),
                  const SizedBox(height: 8),
                  if (result.debugLog.isNotEmpty) ...[
                    Text('Engine Log:',
                        style: GoogleFonts.dmSans(fontSize: 11, fontWeight: FontWeight.w700)),
                    const SizedBox(height: 4),
                    Container(
                      width: double.infinity,
                      padding: const EdgeInsets.all(8),
                      decoration: BoxDecoration(
                        color: const Color(0xFFF5F5F5),
                        borderRadius: BorderRadius.circular(6),
                      ),
                      constraints: const BoxConstraints(maxHeight: 200),
                      child: SingleChildScrollView(
                        child: Text(result.debugLog,
                            style: GoogleFonts.dmSans(fontSize: 10, height: 1.4)),
                      ),
                    ),
                  ],
                  const SizedBox(height: 8),
                  SizedBox(
                    width: double.infinity,
                    child: OutlinedButton.icon(
                      onPressed: () {
                        Clipboard.setData(ClipboardData(text: fullText));
                        ScaffoldMessenger.of(context).showSnackBar(
                          const SnackBar(
                            content: Text('Đã copy thông số chẩn đoán'),
                            duration: Duration(seconds: 2),
                          ),
                        );
                      },
                      icon: const Icon(LucideIcons.copy, size: 14),
                      label: const Text('Copy toàn bộ'),
                      style: OutlinedButton.styleFrom(
                        textStyle: GoogleFonts.dmSans(fontSize: 12),
                        padding: const EdgeInsets.symmetric(vertical: 8),
                      ),
                    ),
                  ),
                ],
              ),
            ),
          ],
        ],
      ),
    );
  }

  Widget _debugRow(String label, String value) {
    return Padding(
      padding: const EdgeInsets.only(bottom: 3),
      child: Row(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          SizedBox(
            width: 110,
            child: Text(label,
                style: GoogleFonts.dmSans(
                    fontSize: 11, color: GradeFlowTheme.onSurfaceVariant)),
          ),
          Expanded(
            child: Text(value,
                style: GoogleFonts.dmSans(fontSize: 11, fontWeight: FontWeight.w600)),
          ),
        ],
      ),
    );
  }

}
