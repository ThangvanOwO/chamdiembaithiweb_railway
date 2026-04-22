import 'package:flutter/material.dart';
import 'package:google_fonts/google_fonts.dart';
import 'package:lucide_icons/lucide_icons.dart';
import 'package:provider/provider.dart';

import '../config/theme.dart';
import '../models/exam.dart';
import '../services/auth_service.dart';
import '../services/api_service.dart';
import '../services/coach_mark_service.dart';
import '../services/tutorial_flow.dart';
import 'scan_screen.dart';
import 'results_screen.dart';
import 'exam_create_screen.dart';
import 'exam_import_screen.dart';

class ExamsScreen extends StatefulWidget {
  const ExamsScreen({super.key});

  @override
  State<ExamsScreen> createState() => _ExamsScreenState();
}

class _ExamsScreenState extends State<ExamsScreen> {
  List<Exam> _exams = [];
  bool _loading = true;
  String? _error;

  final GlobalKey _importBtnKey = GlobalKey();
  final GlobalKey _manualBtnKey = GlobalKey();

  VoidCallback? _flowListener;

  @override
  void initState() {
    super.initState();
    _loadExams();
    _flowListener = _onFlowStepChanged;
    TutorialFlow.instance.step.addListener(_flowListener!);
    // Initial check (in case we are built after step was set).
    WidgetsBinding.instance.addPostFrameCallback((_) => _onFlowStepChanged());
  }

  @override
  void dispose() {
    if (_flowListener != null) {
      TutorialFlow.instance.step.removeListener(_flowListener!);
    }
    super.dispose();
  }

  void _onFlowStepChanged() {
    if (!mounted) return;
    if (TutorialFlow.instance.step.value == TutorialFlow.stepClickImport) {
      _showStep2CoachMark();
    }
  }

  Future<void> _showStep2CoachMark() async {
    await Future.delayed(const Duration(milliseconds: 400));
    if (!mounted) return;
    // Still on right step?
    if (TutorialFlow.instance.step.value != TutorialFlow.stepClickImport) {
      return;
    }
    await CoachMarkService.show(
      context: context,
      screenKey: 'flow_step2_import_btn',
      force: true,
      targets: [
        CoachMarkService.buildTarget(
          identify: 'import',
          key: _importBtnKey,
          title: 'Bước 2: Tạo đề từ file',
          description:
              'Nhấn vào đây để tạo đề thi nhanh từ file Excel đáp án hoặc ảnh phiếu mẫu.',
          align: ContentAlign.bottom,
        ),
      ],
    );
  }

  Future<void> _loadExams() async {
    final auth = context.read<AuthService>();
    if (auth.token == null) return;

    setState(() { _loading = true; _error = null; });

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

  Future<void> _deleteExam(Exam exam) async {
    final confirm = await showDialog<bool>(
      context: context,
      builder: (_) => AlertDialog(
        title: const Text('Xóa bài thi'),
        content: Text('Xóa bài thi «${exam.title}»?'),
        actions: [
          TextButton(onPressed: () => Navigator.pop(context, false), child: const Text('Hủy')),
          TextButton(
            onPressed: () => Navigator.pop(context, true),
            style: TextButton.styleFrom(foregroundColor: GradeFlowTheme.error),
            child: const Text('Xóa'),
          ),
        ],
      ),
    );
    if (confirm != true) return;

    final auth = context.read<AuthService>();
    try {
      final api = ApiService(token: auth.token!);
      await api.deleteExam(exam.id);
      _loadExams();
      if (mounted) {
        ScaffoldMessenger.of(context).showSnackBar(
          SnackBar(content: Text('Đã xóa: ${exam.title}')),
        );
      }
    } catch (e) {
      if (mounted) {
        ScaffoldMessenger.of(context).showSnackBar(
          SnackBar(content: Text('Lỗi: $e'), backgroundColor: Colors.red),
        );
      }
    }
  }

  void _importFromFile() async {
    // Advance tutorial step 2 → 3 on entering import screen
    await TutorialFlow.instance
        .advanceIf(TutorialFlow.stepClickImport, TutorialFlow.stepImportScreen);

    final created = await Navigator.push<bool>(
      context,
      MaterialPageRoute(builder: (_) => const ExamImportScreen()),
    );
    if (created == true) _loadExams();

    // When user returns (regardless of whether exam was created), advance
    // step 3 → 4 so that MainShell shows the "Chấm điểm" hint.
    await TutorialFlow.instance
        .advanceIf(TutorialFlow.stepImportScreen, TutorialFlow.stepClickChamDiem);
  }

  void _createManual() async {
    final created = await Navigator.push<bool>(
      context,
      MaterialPageRoute(builder: (_) => const ExamCreateScreen()),
    );
    if (created == true) _loadExams();
  }

  void _navigateToScan(Exam exam) {
    Navigator.push(context,
        MaterialPageRoute(builder: (_) => ScanScreen(preselectedExam: exam)));
  }

  void _navigateToResults(Exam exam) {
    Navigator.push(context,
        MaterialPageRoute(builder: (_) => ResultsScreen(exam: exam)));
  }

  String _timeAgo(String isoDate) {
    if (isoDate.isEmpty) return '';
    try {
      final dt = DateTime.parse(isoDate);
      final diff = DateTime.now().difference(dt);
      if (diff.inDays > 0) return 'Tạo ${diff.inDays} ngày trước';
      if (diff.inHours > 0) return 'Tạo ${diff.inHours} giờ trước';
      if (diff.inMinutes > 0) return 'Tạo ${diff.inMinutes} phút trước';
      return 'Vừa tạo';
    } catch (_) {
      return '';
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
      body: _loading
          ? const Center(child: CircularProgressIndicator())
          : _error != null
              ? _buildError()
              : RefreshIndicator(
                  onRefresh: _loadExams,
                  child: _buildContent(),
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

  Widget _buildContent() {
    return ListView(
      padding: const EdgeInsets.all(16),
      children: [
        // ── Header ──
        Text('Quản lý bài thi',
            style: GoogleFonts.manrope(
                fontSize: 22, fontWeight: FontWeight.w700)),
        const SizedBox(height: 4),
        Text('Tạo và quản lý các bài kiểm tra trắc nghiệm',
            style: GoogleFonts.dmSans(
                fontSize: 14, color: GradeFlowTheme.onSurfaceVariant)),
        const SizedBox(height: 16),

        // ── Two buttons: Import + Manual ──
        Row(
          children: [
            Expanded(
              key: _importBtnKey,
              child: SizedBox(
                height: 48,
                child: ElevatedButton.icon(
                  onPressed: _importFromFile,
                  icon: const Icon(LucideIcons.fileUp, size: 18),
                  label: Text('Tạo từ file đáp án',
                      style: GoogleFonts.dmSans(
                          fontSize: 14, fontWeight: FontWeight.w600)),
                  style: ElevatedButton.styleFrom(
                    backgroundColor: const Color(0xFF7C3AED),
                    foregroundColor: Colors.white,
                    shape: RoundedRectangleBorder(
                        borderRadius: BorderRadius.circular(12)),
                  ),
                ),
              ),
            ),
            const SizedBox(width: 10),
            Expanded(
              key: _manualBtnKey,
              child: SizedBox(
                height: 48,
                child: OutlinedButton.icon(
                  onPressed: _createManual,
                  icon: const Icon(LucideIcons.plus, size: 18),
                  label: Text('Tạo thủ công',
                      style: GoogleFonts.dmSans(
                          fontSize: 14, fontWeight: FontWeight.w600)),
                  style: OutlinedButton.styleFrom(
                    shape: RoundedRectangleBorder(
                        borderRadius: BorderRadius.circular(12)),
                  ),
                ),
              ),
            ),
          ],
        ),
        const SizedBox(height: 20),

        // ── Exam cards ──
        if (_exams.isEmpty) _buildEmpty(),
        ..._exams.map((exam) => _buildExamCard(exam)),
      ],
    );
  }

  Widget _buildEmpty() {
    return Container(
      padding: const EdgeInsets.symmetric(vertical: 60),
      child: Column(
        children: [
          Icon(LucideIcons.fileText,
              size: 56,
              color: GradeFlowTheme.onSurfaceVariant.withOpacity(0.4)),
          const SizedBox(height: 16),
          Text('Chưa có bài thi nào',
              style: GoogleFonts.manrope(
                  fontSize: 18, fontWeight: FontWeight.w600)),
          const SizedBox(height: 8),
          Text('Tạo bài thi đầu tiên để bắt đầu chấm điểm tự động.',
              style: GoogleFonts.dmSans(
                  fontSize: 14, color: GradeFlowTheme.onSurfaceVariant),
              textAlign: TextAlign.center),
        ],
      ),
    );
  }

  Widget _buildExamCard(Exam exam) {
    final avatarText = (exam.subject.isNotEmpty ? exam.subject : exam.title)
        .substring(
            0,
            (exam.subject.isNotEmpty ? exam.subject : exam.title).length >= 2
                ? 2
                : (exam.subject.isNotEmpty ? exam.subject : exam.title).length)
        .toUpperCase();

    return Card(
      margin: const EdgeInsets.only(bottom: 14),
      child: Padding(
        padding: const EdgeInsets.all(16),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            // ── Header: Avatar + Title + Edit/Delete ──
            Row(
              children: [
                Container(
                  width: 42,
                  height: 42,
                  decoration: BoxDecoration(
                    color: GradeFlowTheme.primaryFixed,
                    borderRadius: BorderRadius.circular(11),
                  ),
                  child: Center(
                    child: Text(avatarText,
                        style: GoogleFonts.manrope(
                            fontSize: 14,
                            fontWeight: FontWeight.w700,
                            color: GradeFlowTheme.primary)),
                  ),
                ),
                const SizedBox(width: 12),
                Expanded(
                  child: Column(
                    crossAxisAlignment: CrossAxisAlignment.start,
                    children: [
                      Text(exam.title,
                          style: GoogleFonts.dmSans(
                              fontSize: 16, fontWeight: FontWeight.w600),
                          maxLines: 1,
                          overflow: TextOverflow.ellipsis),
                      if (exam.subject.isNotEmpty)
                        Text(exam.subject,
                            style: GoogleFonts.dmSans(
                                fontSize: 12,
                                color: GradeFlowTheme.onSurfaceVariant)),
                    ],
                  ),
                ),
                // Edit button (placeholder — opens create with prefill in future)
                IconButton(
                  icon: Icon(LucideIcons.pencil,
                      size: 18, color: GradeFlowTheme.onSurfaceVariant),
                  onPressed: () {}, // TODO: edit
                  visualDensity: VisualDensity.compact,
                  tooltip: 'Sửa đề thi',
                ),
                // Delete button
                IconButton(
                  icon: const Icon(LucideIcons.trash2,
                      size: 18, color: GradeFlowTheme.error),
                  onPressed: () => _deleteExam(exam),
                  visualDensity: VisualDensity.compact,
                  tooltip: 'Xóa',
                ),
              ],
            ),
            const SizedBox(height: 12),

            // ── Stats row ──
            Wrap(
              spacing: 14,
              runSpacing: 6,
              children: [
                _statChip(LucideIcons.list, '${exam.numQuestions} câu'),
                if (exam.variantCodes.isNotEmpty)
                  _statChip(LucideIcons.copy,
                      '${exam.variantCodes.length} mã đề'),
                _statChip(
                    LucideIcons.upload, '${exam.submissionCount} bài nộp'),
                if (exam.averageScore != null)
                  _statChip(LucideIcons.star,
                      'TB ${exam.averageScore!.toStringAsFixed(1)}đ',
                      accent: true),
              ],
            ),

            // ── Variant code chips ──
            if (exam.variantCodes.isNotEmpty) ...[
              const SizedBox(height: 10),
              Wrap(
                spacing: 6,
                runSpacing: 4,
                children: exam.variantCodes
                    .map((code) => Container(
                          padding: const EdgeInsets.symmetric(
                              horizontal: 10, vertical: 4),
                          decoration: BoxDecoration(
                            color: GradeFlowTheme.surfaceContainer,
                            borderRadius: BorderRadius.circular(8),
                          ),
                          child: Text(code,
                              style: GoogleFonts.manrope(
                                  fontSize: 13, fontWeight: FontWeight.w600)),
                        ))
                    .toList(),
              ),
            ],

            // ── Created at ──
            if (exam.createdAt.isNotEmpty) ...[
              const SizedBox(height: 10),
              Row(
                children: [
                  Icon(LucideIcons.clock,
                      size: 12, color: GradeFlowTheme.onSurfaceVariant),
                  const SizedBox(width: 6),
                  Text(_timeAgo(exam.createdAt),
                      style: GoogleFonts.dmSans(
                          fontSize: 12,
                          color: GradeFlowTheme.onSurfaceVariant)),
                ],
              ),
            ],

            const SizedBox(height: 14),

            // ── Action buttons — Chấm điểm + Kết quả ──
            SizedBox(
              width: double.infinity,
              height: 44,
              child: ElevatedButton.icon(
                onPressed: () => _navigateToScan(exam),
                icon: const Icon(LucideIcons.upload, size: 16),
                label: Text('Chấm điểm',
                    style: GoogleFonts.dmSans(
                        fontSize: 15, fontWeight: FontWeight.w600)),
                style: ElevatedButton.styleFrom(
                  shape: RoundedRectangleBorder(
                      borderRadius: BorderRadius.circular(12)),
                ),
              ),
            ),
            if (exam.gradedCount > 0) ...[
              const SizedBox(height: 8),
              SizedBox(
                width: double.infinity,
                height: 42,
                child: OutlinedButton.icon(
                  onPressed: () => _navigateToResults(exam),
                  icon: const Icon(LucideIcons.barChart3, size: 16),
                  label: Text('Kết quả',
                      style: GoogleFonts.dmSans(
                          fontSize: 15, fontWeight: FontWeight.w600)),
                  style: OutlinedButton.styleFrom(
                    shape: RoundedRectangleBorder(
                        borderRadius: BorderRadius.circular(12)),
                  ),
                ),
              ),
            ],
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
        Text(text,
            style: GoogleFonts.dmSans(
                fontSize: 12,
                color: accent
                    ? GradeFlowTheme.primary
                    : GradeFlowTheme.onSurfaceVariant,
                fontWeight: accent ? FontWeight.w600 : FontWeight.w400)),
      ],
    );
  }
}
