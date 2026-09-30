import 'dart:typed_data';
import 'package:flutter/foundation.dart';
import 'package:flutter/material.dart';
import '../services/ad_navigation_observer.dart';
import 'package:google_fonts/google_fonts.dart';
import 'package:lucide_icons/lucide_icons.dart';
import 'package:provider/provider.dart';

import '../config/theme.dart';
import '../models/exam.dart';
import '../models/grade_result.dart';
import '../services/auth_service.dart';
import '../services/api_service.dart';
import '../services/live_grading_service.dart';
import '../services/training_uploader.dart';
import 'grade_result_screen.dart';
import 'live_camera_screen.dart';

/// Batch scanning: scan multiple papers in one session, grade each automatically,
/// and display all results in a list.
class BatchScanScreen extends StatefulWidget {
  final Exam? preselectedExam;
  const BatchScanScreen({super.key, this.preselectedExam});

  @override
  State<BatchScanScreen> createState() => _BatchScanScreenState();
}

class _BatchResult {
  final GradeResult result;
  final Uint8List imageBytes;
  final String fileName;
  _BatchResult(
      {required this.result, required this.imageBytes, required this.fileName});
}

class _BatchScanScreenState extends State<BatchScanScreen> {
  List<Exam> _exams = [];
  Exam? _selectedExam;
  bool _loadingExams = true;
  bool _scanning = false;
  int _gradingCount = 0;
  int _gradingDone = 0;

  final List<_BatchResult> _results = [];

  @override
  void initState() {
    super.initState();
    _selectedExam = widget.preselectedExam;
    _loadExams();
  }


  Future<void> _loadExams() async {
    final auth = context.read<AuthService>();
    if (auth.token == null) return;
    try {
      final api = ApiService(token: auth.token!);
      final exams = await api.getExams();
      if (mounted) {
        setState(() {
          _exams = exams;
          _loadingExams = false;
        });
      }
    } catch (_) {
      if (mounted) setState(() => _loadingExams = false);
    }
  }

  Future<void> _scanBatch() async {
    if (kIsWeb ||
        !(defaultTargetPlatform == TargetPlatform.android ||
            defaultTargetPlatform == TargetPlatform.iOS)) {
      ScaffoldMessenger.of(context).showSnackBar(
        const SnackBar(
            content:
                Text('Batch scan chỉ hỗ trợ Android/iOS. Dùng Chấm điểm đơn.')),
      );
      return;
    }

    setState(() => _scanning = true);
    int scanned = 0;

    try {
      bool keepScanning = true;
      while (keepScanning && mounted) {
        // Open live camera for each paper
        final capture = await Navigator.push<LiveCapture>(
          context,
          MaterialPageRoute(
            settings: const RouteSettings(name: AdNavigationObserver.cameraRoute),
            builder: (_) => AutoScanScreen(),
          ),
        );

        if (capture == null || !mounted) break; // User cancelled
        final bytes = capture.bytes;
        scanned++;

        // Grade this scan
        final fileName = 'batch_${DateTime.now().millisecondsSinceEpoch}.jpg';
        setState(() {
          _gradingCount = scanned;
          _gradingDone = scanned - 1;
        });

        final auth = context.read<AuthService>();
        try {
          final result = await gradeLiveCapture(
            token: auth.token!,
            capture: capture,
            examId: _selectedExam?.id,
            templateCode: _selectedExam?.templateCode,
          );
          if (mounted) {
            setState(() {
              _results.insert(
                  0,
                  _BatchResult(
                      result: result,
                      imageBytes: bytes,
                      fileName: fileName));
              _gradingDone = scanned;
            });
            if (result.isCleanForTraining && auth.token != null) {
              TrainingUploader.instance.enqueue(
                token: auth.token!,
                imageBytes: bytes,
                metadata: result.toTrainingMetadata(),
                fileName: fileName,
              );
            }
          }
        } catch (e) {
          if (mounted) {
            setState(() => _gradingDone = scanned);
            ScaffoldMessenger.of(context).showSnackBar(
              SnackBar(content: Text('Lỗi chấm phiếu $scanned: $e')),
            );
          }
        }

        // Ask to continue or finish
        if (!mounted) break;
        final more = await showDialog<bool>(
          context: context,
          barrierDismissible: false,
          builder: (ctx) => AlertDialog(
            title: Text('Đã quét $scanned phiếu'),
            content: const Text('Quét tiếp hay hoàn tất?'),
            actions: [
              TextButton(
                onPressed: () => Navigator.pop(ctx, false),
                child: const Text('Hoàn tất'),
              ),
              ElevatedButton(
                onPressed: () => Navigator.pop(ctx, true),
                child: const Text('Quét tiếp'),
              ),
            ],
          ),
        );
        keepScanning = more == true;
      }
    } catch (e) {
      if (mounted) {
        ScaffoldMessenger.of(context).showSnackBar(
          SnackBar(content: Text('Lỗi quét: $e')),
        );
      }
    }

    if (mounted) {
      setState(() {
        _scanning = false;
        _gradingCount = 0;
        _gradingDone = 0;
      });
      if (scanned > 0) {
        ScaffoldMessenger.of(context).showSnackBar(
          SnackBar(
              content: Text('Đã chấm xong $scanned phiếu'),
              backgroundColor: GradeFlowTheme.success),
        );
      }
    }
  }

  void _openDetail(_BatchResult batch) {
    Navigator.push(
      context,
      MaterialPageRoute(
        builder: (_) => GradeResultScreen(
          result: batch.result,
          imageBytes: batch.imageBytes,
          examTitle: _selectedExam?.title,
          isAdmin: context.read<AuthService>().isAdmin,
        ),
      ),
    );
  }

  @override
  Widget build(BuildContext context) {
    final grading = _gradingCount > 0;

    return Scaffold(
      appBar: AppBar(
        title: const Text('Chấm hàng loạt'),
        actions: [
          if (_results.isNotEmpty)
            TextButton.icon(
              onPressed: () => setState(() => _results.clear()),
              icon: const Icon(LucideIcons.trash2, size: 16),
              label: const Text('Xóa'),
            ),
        ],
      ),
      body: Column(
        children: [
          // Header with selector + scan button
          Container(
            padding: const EdgeInsets.all(16),
            decoration: BoxDecoration(
              color: GradeFlowTheme.surfaceContainerLow,
              border: Border(
                bottom: BorderSide(
                    color: GradeFlowTheme.outlineVariant, width: 0.5),
              ),
            ),
            child: Column(
              children: [
                _buildExamSelector(),
                const SizedBox(height: 12),
                SizedBox(
                  width: double.infinity,
                  height: 52,
                  child: ElevatedButton.icon(
                    onPressed: (_scanning || grading) ? null : _scanBatch,
                    icon: _scanning || grading
                        ? const SizedBox(
                            width: 18,
                            height: 18,
                            child: CircularProgressIndicator(
                                strokeWidth: 2, color: Colors.white),
                          )
                        : const Icon(LucideIcons.scan, size: 20),
                    label: Text(
                      _scanning
                          ? 'Đang quét...'
                          : grading
                              ? 'Đang chấm $_gradingDone/$_gradingCount...'
                              : 'Quét liên tục nhiều phiếu',
                      style: GoogleFonts.dmSans(
                          fontSize: 15, fontWeight: FontWeight.w600),
                    ),
                    style: ElevatedButton.styleFrom(
                      backgroundColor: GradeFlowTheme.primary,
                      foregroundColor: Colors.white,
                      shape: RoundedRectangleBorder(
                          borderRadius: BorderRadius.circular(12)),
                    ),
                  ),
                ),
                const SizedBox(height: 6),
                Text(
                  'Mẹo: Chụp từng phiếu, bấm "+" để chụp tiếp, "Lưu" khi xong. '
                  'Tối đa 30 phiếu/phiên.',
                  style: GoogleFonts.dmSans(
                      fontSize: 11, color: GradeFlowTheme.onSurfaceVariant),
                  textAlign: TextAlign.center,
                ),
              ],
            ),
          ),

          // Results list
          Expanded(
            child: _results.isEmpty
                ? _buildEmptyState(grading)
                : ListView.separated(
                    padding: const EdgeInsets.all(12),
                    itemCount: _results.length,
                    separatorBuilder: (_, __) => const SizedBox(height: 6),
                    itemBuilder: (_, i) => _buildResultTile(_results[i], i),
                  ),
          ),
        ],
      ),
    );
  }

  Widget _buildExamSelector() {
    if (_loadingExams) {
      return const Padding(
        padding: EdgeInsets.all(8),
        child: CircularProgressIndicator(strokeWidth: 2),
      );
    }
    return DropdownButtonFormField<Exam>(
      value: _selectedExam != null && _exams.contains(_selectedExam)
          ? _selectedExam
          : null,
      decoration: InputDecoration(
        prefixIcon: const Icon(LucideIcons.fileText, size: 18),
        hintText: 'Chọn đề thi',
        isDense: true,
        contentPadding:
            const EdgeInsets.symmetric(horizontal: 12, vertical: 10),
        filled: true,
        fillColor: Colors.white,
        border: OutlineInputBorder(
            borderRadius: BorderRadius.circular(12),
            borderSide: BorderSide(color: GradeFlowTheme.outlineVariant)),
      ),
      items: [
        const DropdownMenuItem<Exam>(
            value: null, child: Text('Không chọn đề')),
        ..._exams.map((e) => DropdownMenuItem(
              value: e,
              child: Text(e.title, overflow: TextOverflow.ellipsis),
            )),
      ],
      onChanged: (e) => setState(() => _selectedExam = e),
      isExpanded: true,
    );
  }

  Widget _buildEmptyState(bool grading) {
    return Center(
      child: Padding(
        padding: const EdgeInsets.all(32),
        child: Column(
          mainAxisAlignment: MainAxisAlignment.center,
          children: [
            Icon(
              grading ? LucideIcons.loader : LucideIcons.layers,
              size: 56,
              color: GradeFlowTheme.onSurfaceVariant.withOpacity(0.4),
            ),
            const SizedBox(height: 16),
            Text(
              grading
                  ? 'Đang chấm bài, vui lòng chờ...'
                  : 'Chưa có bài nào',
              style: GoogleFonts.manrope(
                  fontSize: 16, fontWeight: FontWeight.w600),
            ),
            const SizedBox(height: 6),
            Text(
              grading
                  ? 'Kết quả sẽ xuất hiện tại đây khi chấm xong.'
                  : 'Nhấn "Quét liên tục nhiều phiếu" để bắt đầu.',
              textAlign: TextAlign.center,
              style: GoogleFonts.dmSans(
                  fontSize: 13, color: GradeFlowTheme.onSurfaceVariant),
            ),
          ],
        ),
      ),
    );
  }

  Widget _buildResultTile(_BatchResult batch, int index) {
    final r = batch.result;
    final score = r.score;
    final gradeColor = GradeFlowTheme.gradeColor(r.gradeLabel);
    final gradeBg = GradeFlowTheme.gradeBackground(r.gradeLabel);

    return Card(
      margin: EdgeInsets.zero,
      child: ListTile(
        onTap: () => _openDetail(batch),
        contentPadding:
            const EdgeInsets.symmetric(horizontal: 12, vertical: 4),
        leading: Container(
          width: 48,
          height: 48,
          decoration: BoxDecoration(
            color: gradeBg,
            borderRadius: BorderRadius.circular(10),
          ),
          child: Center(
            child: Text(
              score != null ? score.toStringAsFixed(1) : '—',
              style: GoogleFonts.manrope(
                  fontSize: 15,
                  fontWeight: FontWeight.w800,
                  color: gradeColor),
            ),
          ),
        ),
        title: Text(
          r.sbd.isNotEmpty ? 'SBD ${r.sbd}' : 'Bài #${_results.length - index}',
          style: GoogleFonts.dmSans(
              fontSize: 14, fontWeight: FontWeight.w600),
          maxLines: 1,
          overflow: TextOverflow.ellipsis,
        ),
        subtitle: Row(
          children: [
            if (r.made.isNotEmpty)
              Text('Mã đề ${r.made} • ',
                  style: GoogleFonts.dmSans(
                      fontSize: 12,
                      color: GradeFlowTheme.onSurfaceVariant)),
            if (r.correctCount != null && r.totalQuestions != null)
              Text('${r.correctCount}/${r.totalQuestions} câu',
                  style: GoogleFonts.dmSans(
                      fontSize: 12,
                      color: GradeFlowTheme.onSurfaceVariant)),
          ],
        ),
        trailing: Container(
          padding: const EdgeInsets.symmetric(horizontal: 8, vertical: 3),
          decoration: BoxDecoration(
            color: gradeBg,
            borderRadius: BorderRadius.circular(6),
          ),
          child: Text(
            r.gradeText,
            style: GoogleFonts.dmSans(
                fontSize: 11,
                fontWeight: FontWeight.w700,
                color: gradeColor),
          ),
        ),
      ),
    );
  }
}
