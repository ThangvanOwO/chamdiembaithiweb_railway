import 'dart:io';
import 'dart:typed_data';
import 'package:flutter/foundation.dart';
import 'package:flutter/material.dart';
import 'package:google_fonts/google_fonts.dart';
import 'package:google_mlkit_document_scanner/google_mlkit_document_scanner.dart';
import 'package:image_picker/image_picker.dart';
import 'package:lucide_icons/lucide_icons.dart';
import 'package:provider/provider.dart';

import '../config/theme.dart';
import '../models/exam.dart';
import '../models/grade_result.dart';
import '../services/auth_service.dart';
import '../services/api_service.dart';
import '../services/coach_mark_service.dart';
import '../services/tutorial_flow.dart';
import '../services/training_uploader.dart';
import 'grade_result_screen.dart';
import 'batch_scan_screen.dart';

class ScanScreen extends StatefulWidget {
  final Exam? preselectedExam;
  const ScanScreen({super.key, this.preselectedExam});

  @override
  State<ScanScreen> createState() => _ScanScreenState();
}

class _ScanScreenState extends State<ScanScreen> {
  List<Exam> _exams = [];
  Exam? _selectedExam;
  bool _loadingExams = true;
  bool _grading = false;
  XFile? _scannedFile;
  Uint8List? _scannedBytes;
  GradeResult? _lastResult;

  final _imagePicker = ImagePicker();

  // ML Kit Document Scanner (Android/iOS only)
  DocumentScanner? _documentScanner;

  // Coach mark targets
  final GlobalKey _examKey = GlobalKey();
  final GlobalKey _scanKey = GlobalKey();
  final GlobalKey _pickersKey = GlobalKey();

  VoidCallback? _flowListener;

  @override
  void initState() {
    super.initState();
    _selectedExam = widget.preselectedExam;
    _loadExams();
    _flowListener = _onFlowStepChanged;
    TutorialFlow.instance.step.addListener(_flowListener!);
    WidgetsBinding.instance.addPostFrameCallback((_) => _onFlowStepChanged());
  }

  void _onFlowStepChanged() {
    if (!mounted) return;
    if (TutorialFlow.instance.step.value == TutorialFlow.stepScanScreen) {
      _maybeShowCoachMarks();
    }
  }

  Future<void> _maybeShowCoachMarks() async {
    await Future.delayed(const Duration(milliseconds: 500));
    if (!mounted) return;
    if (TutorialFlow.instance.step.value != TutorialFlow.stepScanScreen) return;
    await CoachMarkService.show(
      context: context,
      screenKey: 'flow_step5_scan_screen',
      force: true,
      onFinish: () => TutorialFlow.instance.finish(),
      targets: [
        CoachMarkService.buildTarget(
          identify: 'exam',
          key: _examKey,
          title: 'Bước 5a: Chọn đề thi',
          description:
              'Chọn đề thi tương ứng với phiếu bạn sắp quét. Nếu chưa chọn, hệ thống chỉ quét không chấm.',
          align: ContentAlign.bottom,
        ),
        CoachMarkService.buildTarget(
          identify: 'scan',
          key: _scanKey,
          title: 'Bước 5b: Quét phiếu',
          description:
              'Nhấn để mở Google ML Kit Scanner. Đưa camera vào phiếu, hệ thống tự cắt viền và nắn thẳng.',
          align: ContentAlign.bottom,
        ),
        CoachMarkService.buildTarget(
          identify: 'pickers',
          key: _pickersKey,
          title: 'Tuỳ chọn khác',
          description:
              'Bạn cũng có thể chụp Camera bình thường hoặc chọn ảnh có sẵn từ Thư viện nếu cần.',
          align: ContentAlign.top,
        ),
      ],
    );
  }

  @override
  void dispose() {
    if (_flowListener != null) {
      TutorialFlow.instance.step.removeListener(_flowListener!);
    }
    _documentScanner?.close();
    super.dispose();
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

  /// Launch document scanner (ML Kit on mobile, fallback on web/desktop)
  Future<void> _scanDocument() async {
    if (!kIsWeb &&
        (defaultTargetPlatform == TargetPlatform.android ||
         defaultTargetPlatform == TargetPlatform.iOS)) {
      try {
        _documentScanner ??= DocumentScanner(
          options: DocumentScannerOptions(
            documentFormat: DocumentFormat.jpeg,
            mode: ScannerMode.full,
            pageLimit: 1,
            isGalleryImport: true,
          ),
        );
        final result = await _documentScanner!.scanDocument();
        final images = result.images;
        if (images.isNotEmpty && mounted) {
          final file = File(images.first);
          final bytes = await file.readAsBytes();
          setState(() {
            _scannedFile = XFile(images.first);
            _scannedBytes = bytes;
          });
          return;
        }
      } catch (e) {
        debugPrint('Document scanner error: $e');
      }
    }
    // Fallback: use gallery picker
    _pickFromGallery();
  }

  /// Set scanned file and read bytes for preview + upload
  Future<void> _setScannedFile(XFile file) async {
    final bytes = await file.readAsBytes();
    if (mounted) {
      setState(() {
        _scannedFile = file;
        _scannedBytes = bytes;
      });
    }
  }

  /// Fallback: pick image from camera
  Future<void> _pickFromCamera() async {
    final XFile? photo = await _imagePicker.pickImage(
      source: ImageSource.camera,
      maxWidth: 2400,
      maxHeight: 3200,
      imageQuality: 92,
    );
    if (photo != null && mounted) {
      await _setScannedFile(photo);
    }
  }

  /// Pick from gallery
  Future<void> _pickFromGallery() async {
    final XFile? photo = await _imagePicker.pickImage(
      source: ImageSource.gallery,
      maxWidth: 2400,
      maxHeight: 3200,
      imageQuality: 92,
    );
    if (photo != null && mounted) {
      await _setScannedFile(photo);
    }
  }

  /// Send image to API for grading
  Future<void> _gradeImage() async {
    if (_scannedBytes == null || _scannedFile == null) return;

    final auth = context.read<AuthService>();
    if (auth.token == null) return;

    setState(() => _grading = true);

    try {
      final api = ApiService(token: auth.token!);
      final result = await api.gradeImage(
        imageBytes: _scannedBytes!,
        fileName: _scannedFile!.name,
        examId: _selectedExam?.id,
        templateCode: _selectedExam?.templateCode,
      );

      if (mounted) {
        setState(() {
          _lastResult = result;
          _grading = false;
        });

        // Active learning: queue clean samples for upload (fire-and-forget).
        if (result.isCleanForTraining && auth.token != null) {
          TrainingUploader.instance.enqueue(
            token: auth.token!,
            imageBytes: _scannedBytes!,
            metadata: result.toTrainingMetadata(),
            fileName: _scannedFile!.name,
          );
        }

        // Navigate to result screen
        Navigator.push(
          context,
          MaterialPageRoute(
            builder: (_) => GradeResultScreen(
              result: result,
              imageBytes: _scannedBytes!,
              examTitle: _selectedExam?.title,
            ),
          ),
        ).then((_) {
          // Reset for next scan
          if (mounted) {
            setState(() {
              _scannedFile = null;
              _scannedBytes = null;
              _lastResult = null;
            });
          }
        });
      }
    } catch (e) {
      if (mounted) {
        setState(() => _grading = false);
        ScaffoldMessenger.of(context).showSnackBar(
          SnackBar(content: Text('Lỗi: $e')),
        );
      }
    }
  }

  @override
  Widget build(BuildContext context) {
    final isFromExam = widget.preselectedExam != null;

    return Scaffold(
      appBar: AppBar(
        title: const Text('Chấm điểm'),
        leading: isFromExam
            ? IconButton(
                icon: const Icon(LucideIcons.arrowLeft),
                onPressed: () => Navigator.pop(context),
              )
            : null,
        actions: [
          IconButton(
            tooltip: 'Chấm hàng loạt',
            icon: const Icon(LucideIcons.layers),
            onPressed: () => Navigator.push(
              context,
              MaterialPageRoute(
                builder: (_) =>
                    BatchScanScreen(preselectedExam: _selectedExam),
              ),
            ),
          ),
        ],
      ),
      body: SingleChildScrollView(
        padding: const EdgeInsets.all(16),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.stretch,
          children: [
            // Section header
            Text(
              'Chấm điểm',
              style: GoogleFonts.manrope(
                fontSize: 22,
                fontWeight: FontWeight.w700,
              ),
            ),
            const SizedBox(height: 4),
            Text(
              'Chọn đề thi → Quét phiếu → Chấm điểm tự động',
              style: GoogleFonts.dmSans(
                fontSize: 14,
                color: GradeFlowTheme.onSurfaceVariant,
              ),
            ),
            const SizedBox(height: 24),

            // Step 1: Exam selector
            Container(key: _examKey, child: _buildExamSelector()),
            const SizedBox(height: 20),

            // Step 2: Scan buttons
            _buildScanActions(),
            const SizedBox(height: 20),

            // Preview + Grade
            if (_scannedBytes != null) _buildPreview(),
          ],
        ),
      ),
    );
  }

  Widget _buildExamSelector() {
    return Card(
      child: Padding(
        padding: const EdgeInsets.all(16),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            Row(
              children: [
                Icon(LucideIcons.fileText,
                    size: 18, color: GradeFlowTheme.primary),
                const SizedBox(width: 8),
                Text('Chọn đề thi',
                    style: GoogleFonts.dmSans(
                        fontSize: 15, fontWeight: FontWeight.w600)),
              ],
            ),
            const SizedBox(height: 12),
            if (_loadingExams)
              const Center(
                  child: Padding(
                      padding: EdgeInsets.all(8),
                      child: CircularProgressIndicator(strokeWidth: 2)))
            else
              DropdownButtonFormField<Exam>(
                value: _selectedExam,
                decoration: const InputDecoration(
                  hintText: 'Chọn đề thi (không bắt buộc)',
                  contentPadding:
                      EdgeInsets.symmetric(horizontal: 16, vertical: 12),
                ),
                items: [
                  const DropdownMenuItem<Exam>(
                    value: null,
                    child: Text('Không chọn đề — chỉ quét'),
                  ),
                  ..._exams.map((e) => DropdownMenuItem(
                        value: e,
                        child: Text(
                          '${e.title} (${e.numQuestions} câu)',
                          overflow: TextOverflow.ellipsis,
                        ),
                      )),
                ],
                onChanged: (exam) => setState(() => _selectedExam = exam),
                isExpanded: true,
              ),
          ],
        ),
      ),
    );
  }

  Widget _buildScanActions() {
    return Column(
      crossAxisAlignment: CrossAxisAlignment.stretch,
      children: [
        // Primary: Document Scanner
        SizedBox(
          key: _scanKey,
          height: 56,
          child: ElevatedButton.icon(
            onPressed: _grading ? null : _scanDocument,
            icon: const Icon(LucideIcons.scan, size: 22),
            label: Text('Quét phiếu thi',
                style: GoogleFonts.dmSans(
                    fontSize: 16, fontWeight: FontWeight.w600)),
            style: ElevatedButton.styleFrom(
              shape: RoundedRectangleBorder(
                  borderRadius: BorderRadius.circular(14)),
            ),
          ),
        ),
        const SizedBox(height: 10),

        // Secondary actions
        Row(
          key: _pickersKey,
          children: [
            Expanded(
              child: OutlinedButton.icon(
                onPressed: _grading ? null : _pickFromCamera,
                icon: const Icon(LucideIcons.camera, size: 18),
                label: const Text('Camera'),
              ),
            ),
            const SizedBox(width: 10),
            Expanded(
              child: OutlinedButton.icon(
                onPressed: _grading ? null : _pickFromGallery,
                icon: const Icon(LucideIcons.image, size: 18),
                label: const Text('Thư viện'),
              ),
            ),
          ],
        ),
        const SizedBox(height: 8),
        Text(
          'Quét phiếu sử dụng Google Document Scanner — tự động cắt, nắn thẳng và làm nét.',
          style: GoogleFonts.dmSans(
            fontSize: 12,
            color: GradeFlowTheme.onSurfaceVariant,
          ),
          textAlign: TextAlign.center,
        ),
      ],
    );
  }

  Widget _buildPreview() {
    return Card(
      child: Padding(
        padding: const EdgeInsets.all(16),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.stretch,
          children: [
            Row(
              children: [
                Icon(LucideIcons.image,
                    size: 18, color: GradeFlowTheme.primary),
                const SizedBox(width: 8),
                Text('Ảnh đã quét',
                    style: GoogleFonts.dmSans(
                        fontSize: 15, fontWeight: FontWeight.w600)),
                const Spacer(),
                TextButton.icon(
                  onPressed: () =>
                      setState(() { _scannedFile = null; _scannedBytes = null; }),
                  icon: const Icon(LucideIcons.x, size: 14),
                  label: const Text('Xóa'),
                  style: TextButton.styleFrom(
                    foregroundColor: GradeFlowTheme.error,
                    padding: EdgeInsets.zero,
                    visualDensity: VisualDensity.compact,
                  ),
                ),
              ],
            ),
            const SizedBox(height: 12),

            // Image preview
            ClipRRect(
              borderRadius: BorderRadius.circular(12),
              child: _buildImagePreview(),
            ),
            const SizedBox(height: 16),

            // Grade button
            SizedBox(
              height: 52,
              child: ElevatedButton.icon(
                onPressed: _grading ? null : _gradeImage,
                icon: _grading
                    ? const SizedBox(
                        width: 20,
                        height: 20,
                        child: CircularProgressIndicator(
                            strokeWidth: 2, color: Colors.white),
                      )
                    : const Icon(LucideIcons.checkCircle, size: 20),
                label: Text(
                  _grading ? 'Đang chấm...' : 'Bắt đầu chấm điểm',
                  style: GoogleFonts.dmSans(
                      fontSize: 16, fontWeight: FontWeight.w600),
                ),
                style: ElevatedButton.styleFrom(
                  backgroundColor: GradeFlowTheme.success,
                  shape: RoundedRectangleBorder(
                      borderRadius: BorderRadius.circular(14)),
                ),
              ),
            ),
          ],
        ),
      ),
    );
  }

  Widget _buildImagePreview() {
    // Use Image.memory — works on all platforms
    return Image.memory(
      _scannedBytes!,
      height: 300,
      fit: BoxFit.contain,
    );
  }
}
