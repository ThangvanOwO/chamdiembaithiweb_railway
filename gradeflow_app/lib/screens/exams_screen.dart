import 'package:flutter/material.dart';
import 'package:google_fonts/google_fonts.dart';
import 'package:lucide_icons/lucide_icons.dart';
import 'package:provider/provider.dart';

import '../config/theme.dart';
import '../models/exam.dart';
import '../services/auth_service.dart';
import '../services/api_service.dart';
import 'scan_screen.dart';
import 'results_screen.dart';
import 'exam_create_screen.dart';

class ExamsScreen extends StatefulWidget {
  const ExamsScreen({super.key});

  @override
  State<ExamsScreen> createState() => _ExamsScreenState();
}

class _ExamsScreenState extends State<ExamsScreen> {
  List<Exam> _exams = [];
  bool _loading = true;
  String? _error;

  @override
  void initState() {
    super.initState();
    _loadExams();
  }

  Future<void> _loadExams() async {
    final auth = context.read<AuthService>();
    if (auth.token == null) return;

    setState(() {
      _loading = true;
      _error = null;
    });

    try {
      final api = ApiService(token: auth.token!);
      final exams = await api.getExams();
      if (mounted) setState(() => _exams = exams);
    } catch (e) {
      if (mounted) setState(() => _error = e.toString());
    } finally {
      if (mounted) setState(() => _loading = false);
    }
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      appBar: AppBar(
        title: const Text('Quản lý bài thi'),
        actions: [
          IconButton(
            icon: const Icon(LucideIcons.refreshCw, size: 20),
            onPressed: _loadExams,
          ),
        ],
      ),
      floatingActionButton: FloatingActionButton.extended(
        onPressed: _createExam,
        icon: const Icon(LucideIcons.plus, size: 20),
        label: Text('Tạo đề thi',
            style: GoogleFonts.dmSans(fontWeight: FontWeight.w600)),
        backgroundColor: GradeFlowTheme.primary,
        foregroundColor: Colors.white,
      ),
      body: _loading
          ? const Center(child: CircularProgressIndicator())
          : _error != null
              ? _buildError()
              : RefreshIndicator(
                  onRefresh: _loadExams,
                  child: _buildList(),
                ),
    );
  }

  Widget _buildError() {
    return Center(
      child: Column(
        mainAxisAlignment: MainAxisAlignment.center,
        children: [
          Icon(LucideIcons.alertTriangle,
              size: 48, color: GradeFlowTheme.onSurfaceVariant),
          const SizedBox(height: 16),
          Text('Không thể tải dữ liệu',
              style: GoogleFonts.dmSans(fontSize: 16)),
          const SizedBox(height: 24),
          ElevatedButton.icon(
            onPressed: _loadExams,
            icon: const Icon(LucideIcons.refreshCw, size: 16),
            label: const Text('Thử lại'),
          ),
        ],
      ),
    );
  }

  Widget _buildList() {
    if (_exams.isEmpty) {
      return Center(
        child: Column(
          mainAxisAlignment: MainAxisAlignment.center,
          children: [
            Icon(LucideIcons.fileText,
                size: 56, color: GradeFlowTheme.onSurfaceVariant.withOpacity(0.4)),
            const SizedBox(height: 16),
            Text('Chưa có bài thi nào',
                style: GoogleFonts.manrope(
                    fontSize: 18, fontWeight: FontWeight.w600)),
            const SizedBox(height: 8),
            Text('Tạo bài thi để bắt đầu chấm điểm.',
                style: GoogleFonts.dmSans(
                    fontSize: 14, color: GradeFlowTheme.onSurfaceVariant)),
            const SizedBox(height: 24),
            ElevatedButton.icon(
              onPressed: _createExam,
              icon: const Icon(LucideIcons.plus, size: 18),
              label: const Text('Tạo đề thi'),
            ),
          ],
        ),
      );
    }

    return ListView.builder(
      padding: const EdgeInsets.all(16),
      itemCount: _exams.length,
      itemBuilder: (context, index) => _ExamCard(
        exam: _exams[index],
        onGrade: () => _navigateToScan(_exams[index]),
        onResults: () => _navigateToResults(_exams[index]),
      ),
    );
  }

  void _navigateToScan(Exam exam) {
    Navigator.push(
      context,
      MaterialPageRoute(
        builder: (_) => ScanScreen(preselectedExam: exam),
      ),
    );
  }

  void _createExam() async {
    final created = await Navigator.push<bool>(
      context,
      MaterialPageRoute(builder: (_) => const ExamCreateScreen()),
    );
    if (created == true) _loadExams();
  }

  void _navigateToResults(Exam exam) {
    Navigator.push(
      context,
      MaterialPageRoute(
        builder: (_) => ResultsScreen(exam: exam),
      ),
    );
  }
}

class _ExamCard extends StatelessWidget {
  final Exam exam;
  final VoidCallback onGrade;
  final VoidCallback onResults;

  const _ExamCard({
    required this.exam,
    required this.onGrade,
    required this.onResults,
  });

  @override
  Widget build(BuildContext context) {
    return Card(
      margin: const EdgeInsets.only(bottom: 12),
      child: Padding(
        padding: const EdgeInsets.all(16),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            // Header
            Row(
              children: [
                // Avatar
                Container(
                  width: 40,
                  height: 40,
                  decoration: BoxDecoration(
                    color: GradeFlowTheme.primaryFixed,
                    borderRadius: BorderRadius.circular(10),
                  ),
                  child: Center(
                    child: Text(
                      (exam.subject.isNotEmpty
                              ? exam.subject
                              : exam.title)
                          .substring(0, exam.subject.isNotEmpty
                              ? (exam.subject.length >= 2 ? 2 : exam.subject.length)
                              : (exam.title.length >= 2 ? 2 : exam.title.length))
                          .toUpperCase(),
                      style: GoogleFonts.manrope(
                        fontSize: 13,
                        fontWeight: FontWeight.w700,
                        color: GradeFlowTheme.primary,
                      ),
                    ),
                  ),
                ),
                const SizedBox(width: 12),
                Expanded(
                  child: Column(
                    crossAxisAlignment: CrossAxisAlignment.start,
                    children: [
                      Text(
                        exam.title,
                        style: GoogleFonts.dmSans(
                            fontSize: 15, fontWeight: FontWeight.w600),
                        maxLines: 1,
                        overflow: TextOverflow.ellipsis,
                      ),
                      if (exam.subject.isNotEmpty)
                        Text(
                          exam.subject,
                          style: GoogleFonts.dmSans(
                            fontSize: 12,
                            color: GradeFlowTheme.onSurfaceVariant,
                          ),
                        ),
                    ],
                  ),
                ),
              ],
            ),
            const SizedBox(height: 12),

            // Stats row
            Wrap(
              spacing: 12,
              runSpacing: 4,
              children: [
                _statChip(LucideIcons.list, '${exam.numQuestions} câu'),
                if (exam.variantCodes.isNotEmpty)
                  _statChip(LucideIcons.copy,
                      '${exam.variantCodes.length} mã đề'),
                _statChip(LucideIcons.upload, '${exam.submissionCount} bài nộp'),
                if (exam.averageScore != null)
                  _statChip(LucideIcons.star, 'TB ${exam.averageScore}đ',
                      accent: true),
              ],
            ),

            // Variant chips
            if (exam.variantCodes.isNotEmpty) ...[
              const SizedBox(height: 8),
              Wrap(
                spacing: 6,
                children: exam.variantCodes
                    .map((code) => Chip(
                          label: Text(code),
                          materialTapTargetSize:
                              MaterialTapTargetSize.shrinkWrap,
                          visualDensity: VisualDensity.compact,
                        ))
                    .toList(),
              ),
            ],

            const SizedBox(height: 14),

            // Action buttons
            Row(
              children: [
                Expanded(
                  child: ElevatedButton.icon(
                    onPressed: onGrade,
                    icon: const Icon(LucideIcons.scan, size: 16),
                    label: const Text('Chấm điểm'),
                    style: ElevatedButton.styleFrom(
                      padding: const EdgeInsets.symmetric(vertical: 12),
                    ),
                  ),
                ),
                if (exam.gradedCount > 0) ...[
                  const SizedBox(width: 8),
                  Expanded(
                    child: OutlinedButton.icon(
                      onPressed: onResults,
                      icon: const Icon(LucideIcons.barChart3, size: 16),
                      label: const Text('Kết quả'),
                      style: OutlinedButton.styleFrom(
                        padding: const EdgeInsets.symmetric(vertical: 12),
                      ),
                    ),
                  ),
                ],
              ],
            ),
          ],
        ),
      ),
    );
  }

  Widget _statChip(IconData icon, String text, {bool accent = false}) {
    return Row(
      mainAxisSize: MainAxisSize.min,
      children: [
        Icon(icon,
            size: 13,
            color: accent
                ? GradeFlowTheme.primary
                : GradeFlowTheme.onSurfaceVariant),
        const SizedBox(width: 4),
        Text(
          text,
          style: GoogleFonts.dmSans(
            fontSize: 12,
            color: accent
                ? GradeFlowTheme.primary
                : GradeFlowTheme.onSurfaceVariant,
            fontWeight: accent ? FontWeight.w600 : FontWeight.w400,
          ),
        ),
      ],
    );
  }
}
