import 'dart:convert';
import 'package:flutter/material.dart';
import 'package:google_fonts/google_fonts.dart';
import 'package:lucide_icons/lucide_icons.dart';
import 'package:provider/provider.dart';

import '../config/api_config.dart';
import '../config/theme.dart';
import '../services/auth_service.dart';
import '../services/api_service.dart';

class SubmissionDetailScreen extends StatefulWidget {
  final int submissionId;
  const SubmissionDetailScreen({super.key, required this.submissionId});

  @override
  State<SubmissionDetailScreen> createState() => _SubmissionDetailScreenState();
}

class _SubmissionDetailScreenState extends State<SubmissionDetailScreen> {
  Map<String, dynamic>? _data;
  bool _loading = true;
  String? _error;

  @override
  void initState() {
    super.initState();
    _load();
  }

  Future<void> _load() async {
    final auth = context.read<AuthService>();
    if (auth.token == null) return;
    try {
      final api = ApiService(token: auth.token!);
      final data = await api.getSubmissionDetail(widget.submissionId);
      if (mounted) setState(() { _data = data; _loading = false; });
    } catch (e) {
      if (mounted) setState(() { _error = e.toString(); _loading = false; });
    }
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      appBar: AppBar(
        title: const Text('Chi tiết bài chấm'),
        leading: IconButton(
          icon: const Icon(LucideIcons.arrowLeft),
          onPressed: () => Navigator.pop(context),
        ),
      ),
      body: _loading
          ? const Center(child: CircularProgressIndicator())
          : _error != null
              ? Center(child: Text(_error!))
              : _data != null
                  ? _buildContent()
                  : const Center(child: Text('Không có dữ liệu')),
    );
  }

  Widget _buildContent() {
    final d = _data!;
    final score = d['score'];
    final gradeLabel = d['grade_label'] ?? 'pending';
    final gradeText = d['grade_text'] ?? '';
    final gradeColor = GradeFlowTheme.gradeColor(gradeLabel);
    final gradeBg = GradeFlowTheme.gradeBackground(gradeLabel);

    final answers = d['answers_detected'] is Map
        ? Map<String, dynamic>.from(d['answers_detected'])
        : <String, dynamic>{};
    final part1 = answers['part1'] is Map
        ? Map<String, dynamic>.from(answers['part1'])
        : <String, dynamic>{};
    final part2 = answers['part2'] is Map
        ? Map<String, dynamic>.from(answers['part2'])
        : <String, dynamic>{};
    final part3 = answers['part3'] is Map
        ? Map<String, dynamic>.from(answers['part3'])
        : <String, dynamic>{};

    return ListView(
      padding: const EdgeInsets.all(16),
      children: [
        // Score card
        Card(
          child: Padding(
            padding: const EdgeInsets.all(20),
            child: Column(
              children: [
                Container(
                  width: 90,
                  height: 90,
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
                          score != null ? '$score' : '—',
                          style: GoogleFonts.manrope(
                              fontSize: 28,
                              fontWeight: FontWeight.w800,
                              color: gradeColor),
                        ),
                        Text(gradeText,
                            style: GoogleFonts.dmSans(
                                fontSize: 11,
                                fontWeight: FontWeight.w600,
                                color: gradeColor)),
                      ],
                    ),
                  ),
                ),
                const SizedBox(height: 12),
                if (d['exam_title'] != null && d['exam_title'].toString().isNotEmpty)
                  Text(d['exam_title'],
                      style: GoogleFonts.dmSans(
                          fontSize: 15, fontWeight: FontWeight.w600)),
                const SizedBox(height: 8),
                Wrap(
                  spacing: 8,
                  runSpacing: 8,
                  alignment: WrapAlignment.center,
                  children: [
                    if (d['student_id'] != null &&
                        d['student_id'].toString().isNotEmpty)
                      _chip(LucideIcons.hash, 'SBD: ${d['student_id']}'),
                    if (d['variant_code'] != null &&
                        d['variant_code'].toString().isNotEmpty)
                      _chip(LucideIcons.fileText,
                          'Mã đề: ${d['variant_code']}'),
                    if (d['correct_count'] != null)
                      _chip(LucideIcons.checkSquare,
                          '${d['correct_count']}/${d['total_questions']} câu'),
                    if (d['processing_time'] != null)
                      _chip(LucideIcons.timer,
                          '${(d['processing_time'] as num).toStringAsFixed(1)}s'),
                  ],
                ),
              ],
            ),
          ),
        ),
        const SizedBox(height: 16),

        // Image (if available from media URL)
        if (d['id'] != null) _buildImageCard(d['id']),
        const SizedBox(height: 16),

        // Part I
        if (part1.isNotEmpty) _buildAnswerSection('Phần I — Trắc nghiệm', part1),
        if (part2.isNotEmpty) ...[
          const SizedBox(height: 12),
          _buildP2Section(part2),
        ],
        if (part3.isNotEmpty) ...[
          const SizedBox(height: 12),
          _buildP3Section(part3),
        ],

        const SizedBox(height: 32),
      ],
    );
  }

  Widget _buildImageCard(int submissionId) {
    // Try to load image from the submission's media URL
    final auth = context.read<AuthService>();
    final imageUrl =
        '${ApiConfig.baseUrl}/media/submissions/$submissionId.jpg';
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
                Text('Ảnh phiếu thi',
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
                child: Image.network(
                  imageUrl,
                  headers: {'Authorization': 'Token ${auth.token}'},
                  width: double.infinity,
                  fit: BoxFit.contain,
                  errorBuilder: (_, __, ___) => Container(
                    height: 100,
                    alignment: Alignment.center,
                    child: Text('Ảnh không khả dụng',
                        style: GoogleFonts.dmSans(
                            color: GradeFlowTheme.onSurfaceVariant)),
                  ),
                ),
              ),
            ),
          ],
        ),
      ),
    );
  }

  Widget _buildAnswerSection(String title, Map<String, dynamic> answers) {
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
            Text(title,
                style: GoogleFonts.dmSans(
                    fontSize: 15, fontWeight: FontWeight.w600)),
            const SizedBox(height: 12),
            Wrap(
              spacing: 6,
              runSpacing: 6,
              children: entries.map((e) {
                return Container(
                  width: 48,
                  padding: const EdgeInsets.symmetric(
                      horizontal: 4, vertical: 6),
                  decoration: BoxDecoration(
                    color: GradeFlowTheme.surfaceContainerLow,
                    borderRadius: BorderRadius.circular(8),
                    border: Border.all(
                        color: GradeFlowTheme.outlineVariant, width: 0.5),
                  ),
                  child: Column(
                    children: [
                      Text('C${e.key}',
                          style: GoogleFonts.dmSans(
                              fontSize: 9,
                              color: GradeFlowTheme.onSurfaceVariant)),
                      Text('${e.value}',
                          style: GoogleFonts.manrope(
                              fontSize: 14,
                              fontWeight: FontWeight.w700,
                              color: GradeFlowTheme.primary)),
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

  Widget _buildP2Section(Map<String, dynamic> part2) {
    final entries = part2.entries.toList();
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
            Text('Phần II — Đúng/Sai',
                style: GoogleFonts.dmSans(
                    fontSize: 15, fontWeight: FontWeight.w600)),
            const SizedBox(height: 12),
            ...entries.map((e) {
              if (e.value is Map) {
                final m = Map<String, dynamic>.from(e.value);
                return Padding(
                  padding: const EdgeInsets.only(bottom: 8),
                  child: Row(
                    children: [
                      Text('C${e.key}: ',
                          style: GoogleFonts.dmSans(
                              fontSize: 13, fontWeight: FontWeight.w600)),
                      ...m.entries.map((sub) => Container(
                            margin: const EdgeInsets.only(right: 4),
                            padding: const EdgeInsets.symmetric(
                                horizontal: 6, vertical: 2),
                            decoration: BoxDecoration(
                              color: GradeFlowTheme.surfaceContainerLow,
                              borderRadius: BorderRadius.circular(4),
                            ),
                            child: Text('${sub.key}: ${sub.value}',
                                style: GoogleFonts.dmSans(fontSize: 11)),
                          )),
                    ],
                  ),
                );
              }
              return Text('C${e.key}: ${e.value}');
            }),
          ],
        ),
      ),
    );
  }

  Widget _buildP3Section(Map<String, dynamic> part3) {
    final entries = part3.entries.toList();
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
            Text('Phần III — Trả lời ngắn',
                style: GoogleFonts.dmSans(
                    fontSize: 15, fontWeight: FontWeight.w600)),
            const SizedBox(height: 12),
            ...entries.map((e) => Padding(
                  padding: const EdgeInsets.only(bottom: 6),
                  child: Row(
                    children: [
                      SizedBox(
                        width: 50,
                        child: Text('C${e.key}',
                            style: GoogleFonts.dmSans(
                                fontSize: 13, fontWeight: FontWeight.w600)),
                      ),
                      Container(
                        padding: const EdgeInsets.symmetric(
                            horizontal: 10, vertical: 4),
                        decoration: BoxDecoration(
                          color: GradeFlowTheme.surfaceContainerLow,
                          borderRadius: BorderRadius.circular(6),
                        ),
                        child: Text('${e.value}',
                            style: GoogleFonts.manrope(
                                fontSize: 14, fontWeight: FontWeight.w700)),
                      ),
                    ],
                  ),
                )),
          ],
        ),
      ),
    );
  }

  Widget _chip(IconData icon, String text) {
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
