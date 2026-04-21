import 'dart:typed_data';
import 'package:flutter/material.dart';
import 'package:google_fonts/google_fonts.dart';
import 'package:lucide_icons/lucide_icons.dart';
import 'package:provider/provider.dart';
import 'package:file_picker/file_picker.dart';
import 'package:image_picker/image_picker.dart';

import '../config/theme.dart';
import '../services/auth_service.dart';
import '../services/api_service.dart';
import 'scan_screen.dart';

class ExamImportScreen extends StatefulWidget {
  const ExamImportScreen({super.key});

  @override
  State<ExamImportScreen> createState() => _ExamImportScreenState();
}

class _ExamImportScreenState extends State<ExamImportScreen> {
  int _step = 1; // 1=upload, 2=review, 3=template+save
  bool _uploading = false;
  String? _uploadError;
  String _fileName = '';

  // Parsed data from server
  Map<String, dynamic>? _parsedData;
  int _activeVariantIdx = 0;

  // Exam info
  final _titleCtrl = TextEditingController();
  final _subjectCtrl = TextEditingController();

  // Template selection
  String? _selectedTemplate;
  bool _saving = false;

  @override
  void dispose() {
    _titleCtrl.dispose();
    _subjectCtrl.dispose();
    super.dispose();
  }

  // ── Step 1: Pick & Upload file ──

  Future<void> _pickExcelFile() async {
    final result = await FilePicker.platform.pickFiles(
      type: FileType.custom,
      allowedExtensions: ['xlsx', 'xls'],
      withData: true,
    );
    if (result == null || result.files.isEmpty) return;
    final file = result.files.first;
    if (file.bytes == null) return;
    _uploadFile(file.bytes!, file.name, isImage: false);
  }

  Future<void> _pickImage() async {
    final picker = ImagePicker();
    final xfile = await picker.pickImage(source: ImageSource.gallery);
    if (xfile == null) return;
    final bytes = await xfile.readAsBytes();
    _uploadFile(bytes, xfile.name, isImage: true);
  }

  Future<void> _uploadFile(Uint8List bytes, String name,
      {required bool isImage}) async {
    final auth = context.read<AuthService>();
    if (auth.token == null) return;

    setState(() {
      _uploading = true;
      _uploadError = null;
      _fileName = name;
    });

    try {
      final api = ApiService(token: auth.token!);
      Map<String, dynamic> data;
      if (isImage) {
        data = await api.parseImageFile(bytes, name);
      } else {
        data = await api.parseExcelFile(bytes, name);
      }
      setState(() {
        _parsedData = data;
        _uploading = false;
        _step = 2;
        _activeVariantIdx = 0;
      });
    } catch (e) {
      setState(() {
        _uploading = false;
        _uploadError = e.toString().replaceFirst('Exception: ', '');
      });
    }
  }

  // ── Step 3: Save exam ──

  Future<void> _saveExam() async {
    final auth = context.read<AuthService>();
    if (auth.token == null) return;
    if (_titleCtrl.text.trim().isEmpty) {
      ScaffoldMessenger.of(context).showSnackBar(
        const SnackBar(
            content: Text('Vui lòng nhập tên đề thi'),
            backgroundColor: Colors.red),
      );
      return;
    }

    setState(() => _saving = true);
    try {
      final api = ApiService(token: auth.token!);
      final p1 = _parsedData?['part1Count'] ?? 0;
      final p2 = _parsedData?['part2Count'] ?? 0;
      final p3 = _parsedData?['part3Count'] ?? 0;

      final variants = (_parsedData?['variants'] as List? ?? [])
          .map((v) => <String, dynamic>{
                'code': v['code'] ?? '',
                'p1': v['p1'] ?? {},
                'p2': v['p2'] ?? {},
                'p3': v['p3'] ?? {},
              })
          .toList();

      final result = await api.createExam(
        title: _titleCtrl.text.trim(),
        subject: _subjectCtrl.text.trim(),
        templateCode: _selectedTemplate ?? '',
        parts: [p1 as int, p2 as int, p3 as int],
        variants: variants,
      );

      if (mounted) {
        ScaffoldMessenger.of(context).showSnackBar(
          const SnackBar(
              content: Text('Đã tạo đề thi thành công!'),
              backgroundColor: Color(0xFF2E7D32)),
        );
        // Navigate to scan screen with the new exam
        Navigator.pop(context, true);
      }
    } catch (e) {
      setState(() => _saving = false);
      if (mounted) {
        ScaffoldMessenger.of(context).showSnackBar(
          SnackBar(content: Text('Lỗi: $e'), backgroundColor: Colors.red),
        );
      }
    }
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      appBar: AppBar(
        title: Text(_step == 1
            ? 'Tạo đề thi từ file'
            : _step == 2
                ? 'Xác nhận đáp án'
                : 'Chọn phiếu & Lưu'),
        leading: IconButton(
          icon: const Icon(LucideIcons.arrowLeft),
          onPressed: () {
            if (_step > 1) {
              setState(() => _step--);
            } else {
              Navigator.pop(context);
            }
          },
        ),
      ),
      body: _step == 1
          ? _buildStep1()
          : _step == 2
              ? _buildStep2()
              : _buildStep3(),
    );
  }

  // ═══════════════════════════════════════════════════════════════════
  // STEP 1: Upload file
  // ═══════════════════════════════════════════════════════════════════

  Widget _buildStep1() {
    return ListView(
      padding: const EdgeInsets.all(20),
      children: [
        // Step indicator
        _buildStepIndicator(),
        const SizedBox(height: 24),

        Text('Tạo đề thi từ file đáp án',
            style: GoogleFonts.manrope(
                fontSize: 20, fontWeight: FontWeight.w700)),
        const SizedBox(height: 6),
        Text('Chọn file Excel hoặc ảnh phiếu đáp án đã tô',
            style: GoogleFonts.dmSans(
                fontSize: 14, color: GradeFlowTheme.onSurfaceVariant)),
        const SizedBox(height: 24),

        // Drop zone
        GestureDetector(
          onTap: _uploading ? null : _pickExcelFile,
          child: Container(
            padding: const EdgeInsets.symmetric(vertical: 40, horizontal: 24),
            decoration: BoxDecoration(
              color: _uploadError != null
                  ? const Color(0xFFFFF0F0)
                  : GradeFlowTheme.surfaceContainerLow,
              borderRadius: BorderRadius.circular(16),
              border: Border.all(
                color: _uploadError != null
                    ? GradeFlowTheme.error.withOpacity(0.4)
                    : GradeFlowTheme.outlineVariant,
                width: 2,
                style: BorderStyle.solid,
              ),
            ),
            child: _uploading
                ? Column(
                    children: [
                      const SizedBox(
                          width: 36,
                          height: 36,
                          child: CircularProgressIndicator(strokeWidth: 3)),
                      const SizedBox(height: 16),
                      Text('Đang phân tích file...',
                          style: GoogleFonts.dmSans(
                              fontSize: 15, fontWeight: FontWeight.w600)),
                      const SizedBox(height: 4),
                      Text(_fileName,
                          style: GoogleFonts.dmSans(
                              fontSize: 13,
                              color: GradeFlowTheme.onSurfaceVariant)),
                    ],
                  )
                : _uploadError != null
                    ? Column(
                        children: [
                          Icon(LucideIcons.alertCircle,
                              size: 40, color: GradeFlowTheme.error),
                          const SizedBox(height: 12),
                          Text(_uploadError!,
                              style: GoogleFonts.dmSans(
                                  fontSize: 14, color: GradeFlowTheme.error),
                              textAlign: TextAlign.center),
                          const SizedBox(height: 8),
                          Text('Nhấn để thử lại',
                              style: GoogleFonts.dmSans(
                                  fontSize: 13,
                                  color: GradeFlowTheme.onSurfaceVariant)),
                        ],
                      )
                    : Column(
                        children: [
                          Icon(LucideIcons.fileUp,
                              size: 44,
                              color: GradeFlowTheme.primary.withOpacity(0.6)),
                          const SizedBox(height: 14),
                          Text('Nhấn để chọn file Excel',
                              style: GoogleFonts.dmSans(
                                  fontSize: 16, fontWeight: FontWeight.w600)),
                          const SizedBox(height: 6),
                          Row(
                            mainAxisAlignment: MainAxisAlignment.center,
                            children: [
                              _formatBadge('.xlsx', GradeFlowTheme.primary),
                              const SizedBox(width: 6),
                              _formatBadge('.xls', GradeFlowTheme.primary),
                            ],
                          ),
                        ],
                      ),
          ),
        ),

        const SizedBox(height: 20),

        // OR divider
        Row(
          children: [
            const Expanded(child: Divider()),
            Padding(
              padding: const EdgeInsets.symmetric(horizontal: 16),
              child: Text('HOẶC',
                  style: GoogleFonts.dmSans(
                      fontSize: 12,
                      fontWeight: FontWeight.w700,
                      color: GradeFlowTheme.onSurfaceVariant,
                      letterSpacing: 1)),
            ),
            const Expanded(child: Divider()),
          ],
        ),
        const SizedBox(height: 20),

        // Image pick button
        Center(
          child: ElevatedButton.icon(
            onPressed: _uploading ? null : _pickImage,
            icon: const Icon(LucideIcons.camera, size: 20),
            label: Text('Chọn ảnh phiếu đáp án',
                style: GoogleFonts.dmSans(
                    fontSize: 15, fontWeight: FontWeight.w600)),
            style: ElevatedButton.styleFrom(
              backgroundColor: const Color(0xFFE8DEF8),
              foregroundColor: const Color(0xFF4A4458),
              padding: const EdgeInsets.symmetric(horizontal: 24, vertical: 14),
              shape: RoundedRectangleBorder(
                  borderRadius: BorderRadius.circular(14)),
            ),
          ),
        ),
        const SizedBox(height: 8),
        Text('Chọn ảnh phiếu đáp án đã tô từ thư viện',
            textAlign: TextAlign.center,
            style: GoogleFonts.dmSans(
                fontSize: 13, color: GradeFlowTheme.onSurfaceVariant)),
        const SizedBox(height: 24),

        // Hint
        Container(
          padding: const EdgeInsets.all(14),
          decoration: BoxDecoration(
            color: GradeFlowTheme.surfaceContainer,
            borderRadius: BorderRadius.circular(12),
          ),
          child: Row(
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              Icon(LucideIcons.info,
                  size: 16, color: GradeFlowTheme.onSurfaceVariant),
              const SizedBox(width: 10),
              Expanded(
                child: Text.rich(
                  TextSpan(children: [
                    TextSpan(
                        text: 'Excel: ',
                        style: GoogleFonts.dmSans(fontWeight: FontWeight.w700)),
                    TextSpan(
                        text:
                            'Dòng 1 là header. Mỗi dòng tiếp theo là 1 mã đề.\n'),
                    TextSpan(
                        text: 'Ảnh: ',
                        style: GoogleFonts.dmSans(fontWeight: FontWeight.w700)),
                    const TextSpan(
                        text:
                            'Chụp phiếu đáp án đã tô. Hệ thống tự nhận diện.'),
                  ]),
                  style: GoogleFonts.dmSans(
                      fontSize: 13, color: GradeFlowTheme.onSurfaceVariant),
                ),
              ),
            ],
          ),
        ),
      ],
    );
  }

  Widget _formatBadge(String text, Color color) {
    return Container(
      padding: const EdgeInsets.symmetric(horizontal: 10, vertical: 4),
      decoration: BoxDecoration(
        color: color.withOpacity(0.12),
        borderRadius: BorderRadius.circular(8),
      ),
      child: Text(text,
          style: GoogleFonts.manrope(
              fontSize: 12, fontWeight: FontWeight.w700, color: color)),
    );
  }

  // ═══════════════════════════════════════════════════════════════════
  // STEP 2: Review parsed answers
  // ═══════════════════════════════════════════════════════════════════

  Widget _buildStep2() {
    if (_parsedData == null) return const SizedBox.shrink();
    final data = _parsedData!;
    final variants = List<Map<String, dynamic>>.from(data['variants'] ?? []);
    final p1Count = data['part1Count'] ?? 0;
    final p2Count = data['part2Count'] ?? 0;
    final p3Count = data['part3Count'] ?? 0;
    final totalQ = data['totalQuestions'] ?? 0;

    return ListView(
      padding: const EdgeInsets.all(20),
      children: [
        _buildStepIndicator(),
        const SizedBox(height: 24),

        Text('Xác nhận đáp án',
            style: GoogleFonts.manrope(
                fontSize: 20, fontWeight: FontWeight.w700)),
        const SizedBox(height: 4),
        Text.rich(TextSpan(children: [
          const TextSpan(text: 'Kiểm tra lại đáp án từ file '),
          TextSpan(
              text: _fileName,
              style: GoogleFonts.dmSans(fontWeight: FontWeight.w700)),
        ]), style: GoogleFonts.dmSans(fontSize: 14, color: GradeFlowTheme.onSurfaceVariant)),
        const SizedBox(height: 20),

        // Exam info fields
        Card(
          child: Padding(
            padding: const EdgeInsets.all(16),
            child: Column(
              children: [
                TextFormField(
                  controller: _titleCtrl,
                  decoration: const InputDecoration(
                    labelText: 'Tên đề thi *',
                    hintText: 'VD: Đề kiểm tra Toán HK1',
                    isDense: true,
                  ),
                ),
                const SizedBox(height: 12),
                TextFormField(
                  controller: _subjectCtrl,
                  decoration: const InputDecoration(
                    labelText: 'Môn học',
                    hintText: 'VD: Toán, Lý, Hóa...',
                    isDense: true,
                  ),
                ),
              ],
            ),
          ),
        ),
        const SizedBox(height: 16),

        // Summary stats
        Row(
          children: [
            _summaryChip('${variants.length}', 'Mã đề'),
            _summaryChip('$p1Count', 'TN (P1)'),
            _summaryChip('$p2Count', 'Đ/S (P2)'),
            _summaryChip('$p3Count', 'Số (P3)'),
            _summaryChip('$totalQ', 'Tổng',
                accent: true),
          ],
        ),
        const SizedBox(height: 16),

        // Variant tabs
        if (variants.length > 1)
          SizedBox(
            height: 40,
            child: ListView.builder(
              scrollDirection: Axis.horizontal,
              itemCount: variants.length,
              itemBuilder: (_, idx) {
                final v = variants[idx];
                final active = idx == _activeVariantIdx;
                return Padding(
                  padding: const EdgeInsets.only(right: 8),
                  child: ChoiceChip(
                    label: Text('Mã ${v['code']}'),
                    selected: active,
                    onSelected: (_) =>
                        setState(() => _activeVariantIdx = idx),
                    selectedColor: GradeFlowTheme.primary,
                    labelStyle: TextStyle(
                        color: active ? Colors.white : GradeFlowTheme.onSurface,
                        fontWeight: FontWeight.w600),
                  ),
                );
              },
            ),
          ),
        const SizedBox(height: 16),

        // Answer display for active variant
        if (variants.isNotEmpty) ...[
          _buildAnswerReview(variants[_activeVariantIdx], p1Count, p2Count, p3Count),
        ],

        const SizedBox(height: 24),
        SizedBox(
          width: double.infinity,
          height: 48,
          child: ElevatedButton.icon(
            onPressed: _titleCtrl.text.trim().isEmpty
                ? null
                : () => setState(() => _step = 3),
            icon: const Icon(LucideIcons.arrowRight, size: 18),
            label: Text('Xác nhận đáp án & Tiếp tục',
                style: GoogleFonts.dmSans(
                    fontSize: 15, fontWeight: FontWeight.w600)),
          ),
        ),
      ],
    );
  }

  Widget _summaryChip(String value, String label, {bool accent = false}) {
    return Expanded(
      child: Container(
        margin: const EdgeInsets.symmetric(horizontal: 3),
        padding: const EdgeInsets.symmetric(vertical: 10),
        decoration: BoxDecoration(
          color: accent
              ? GradeFlowTheme.primary.withOpacity(0.1)
              : GradeFlowTheme.surfaceContainer,
          borderRadius: BorderRadius.circular(10),
        ),
        child: Column(
          children: [
            Text(value,
                style: GoogleFonts.manrope(
                    fontSize: 18,
                    fontWeight: FontWeight.w800,
                    color: accent
                        ? GradeFlowTheme.primary
                        : GradeFlowTheme.onSurface)),
            Text(label,
                style: GoogleFonts.dmSans(
                    fontSize: 10, color: GradeFlowTheme.onSurfaceVariant)),
          ],
        ),
      ),
    );
  }

  Widget _buildAnswerReview(
      Map<String, dynamic> variant, int p1Count, int p2Count, int p3Count) {
    final p1 = Map<String, dynamic>.from(variant['p1'] ?? {});
    final p2 = Map<String, dynamic>.from(variant['p2'] ?? {});
    final p3 = Map<String, dynamic>.from(variant['p3'] ?? {});

    return Column(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        // P1
        if (p1Count > 0) ...[
          _sectionTitle('Phần I — Trắc nghiệm', '$p1Count câu'),
          const SizedBox(height: 8),
          Wrap(
            spacing: 5,
            runSpacing: 5,
            children: List.generate(p1Count, (i) {
              final q = '${i + 1}';
              final ans = p1[q] ?? '—';
              final empty = ans == '—';
              return Container(
                width: 44,
                padding: const EdgeInsets.symmetric(vertical: 6),
                decoration: BoxDecoration(
                  color: empty
                      ? GradeFlowTheme.surfaceContainer
                      : GradeFlowTheme.primary.withOpacity(0.08),
                  borderRadius: BorderRadius.circular(8),
                  border: Border.all(
                      color: empty
                          ? GradeFlowTheme.outlineVariant
                          : GradeFlowTheme.primary.withOpacity(0.3),
                      width: 0.5),
                ),
                child: Column(
                  children: [
                    Text('C$q',
                        style: GoogleFonts.dmSans(
                            fontSize: 9,
                            color: GradeFlowTheme.onSurfaceVariant)),
                    Text('$ans',
                        style: GoogleFonts.manrope(
                            fontSize: 14,
                            fontWeight: FontWeight.w700,
                            color: empty
                                ? GradeFlowTheme.onSurfaceVariant
                                : GradeFlowTheme.primary)),
                  ],
                ),
              );
            }),
          ),
          const SizedBox(height: 16),
        ],

        // P2
        if (p2Count > 0) ...[
          _sectionTitle('Phần II — Đúng/Sai', '$p2Count câu'),
          const SizedBox(height: 8),
          ...List.generate(p2Count, (i) {
            final q = '${i + 1}';
            final opts =
                p2[q] is Map ? Map<String, dynamic>.from(p2[q]) : null;
            return Container(
              margin: const EdgeInsets.only(bottom: 6),
              padding: const EdgeInsets.symmetric(horizontal: 12, vertical: 8),
              decoration: BoxDecoration(
                color: GradeFlowTheme.surfaceContainerLow,
                borderRadius: BorderRadius.circular(10),
              ),
              child: Row(
                children: [
                  Text('Câu $q',
                      style: GoogleFonts.dmSans(
                          fontSize: 13, fontWeight: FontWeight.w600)),
                  const SizedBox(width: 12),
                  ...['a', 'b', 'c', 'd'].map((k) {
                    final val = opts?[k] ?? '—';
                    final isDung = val == 'Đ';
                    final isSai = val == 'S';
                    return Container(
                      margin: const EdgeInsets.only(right: 4),
                      padding: const EdgeInsets.symmetric(
                          horizontal: 8, vertical: 3),
                      decoration: BoxDecoration(
                        color: isDung
                            ? const Color(0xFFE8F5E9)
                            : isSai
                                ? const Color(0xFFFFF3E0)
                                : GradeFlowTheme.surfaceContainer,
                        borderRadius: BorderRadius.circular(6),
                      ),
                      child: Text('${k}) $val',
                          style: GoogleFonts.dmSans(
                              fontSize: 12,
                              fontWeight: FontWeight.w600,
                              color: isDung
                                  ? const Color(0xFF2E7D32)
                                  : isSai
                                      ? const Color(0xFFE65100)
                                      : GradeFlowTheme.onSurfaceVariant)),
                    );
                  }),
                ],
              ),
            );
          }),
          const SizedBox(height: 16),
        ],

        // P3
        if (p3Count > 0) ...[
          _sectionTitle('Phần III — Điền số', '$p3Count câu'),
          const SizedBox(height: 8),
          Wrap(
            spacing: 6,
            runSpacing: 6,
            children: List.generate(p3Count, (i) {
              final q = '${i + 1}';
              final ans = p3[q] ?? '—';
              return Container(
                width: 70,
                padding: const EdgeInsets.symmetric(vertical: 6),
                decoration: BoxDecoration(
                  color: GradeFlowTheme.surfaceContainer,
                  borderRadius: BorderRadius.circular(8),
                ),
                child: Column(
                  children: [
                    Text('C$q',
                        style: GoogleFonts.dmSans(
                            fontSize: 9,
                            color: GradeFlowTheme.onSurfaceVariant)),
                    Text('$ans',
                        style: GoogleFonts.manrope(
                            fontSize: 14, fontWeight: FontWeight.w700)),
                  ],
                ),
              );
            }),
          ),
        ],
      ],
    );
  }

  Widget _sectionTitle(String title, String badge) {
    return Row(
      children: [
        Text(title,
            style: GoogleFonts.dmSans(
                fontSize: 14, fontWeight: FontWeight.w600)),
        const SizedBox(width: 8),
        Container(
          padding: const EdgeInsets.symmetric(horizontal: 8, vertical: 2),
          decoration: BoxDecoration(
            color: GradeFlowTheme.surfaceContainer,
            borderRadius: BorderRadius.circular(8),
          ),
          child: Text(badge,
              style: GoogleFonts.dmSans(
                  fontSize: 11,
                  fontWeight: FontWeight.w600,
                  color: GradeFlowTheme.onSurfaceVariant)),
        ),
      ],
    );
  }

  // ═══════════════════════════════════════════════════════════════════
  // STEP 3: Choose template & Save
  // ═══════════════════════════════════════════════════════════════════

  Widget _buildStep3() {
    final templates = [
      {
        'code': 'template_default',
        'label': 'Mặc định (24 TN + 4 ĐS + 6 Số)',
        'parts': [24, 4, 6]
      },
      {
        'code': 'template_40mc',
        'label': '40 câu trắc nghiệm',
        'parts': [40, 0, 0]
      },
      {
        'code': 'template_toan',
        'label': 'Đề Toán (24 TN + 4 ĐS + 6 Số)',
        'parts': [24, 4, 6]
      },
    ];

    return ListView(
      padding: const EdgeInsets.all(20),
      children: [
        _buildStepIndicator(),
        const SizedBox(height: 24),

        Text('Chọn phiếu trả lời',
            style: GoogleFonts.manrope(
                fontSize: 20, fontWeight: FontWeight.w700)),
        const SizedBox(height: 4),
        Text('Chọn mẫu phiếu phù hợp với cấu trúc đề thi',
            style: GoogleFonts.dmSans(
                fontSize: 14, color: GradeFlowTheme.onSurfaceVariant)),
        const SizedBox(height: 20),

        ...templates.map((t) {
          final code = t['code'] as String;
          final selected = _selectedTemplate == code;
          return GestureDetector(
            onTap: () => setState(() => _selectedTemplate = code),
            child: Container(
              margin: const EdgeInsets.only(bottom: 10),
              padding: const EdgeInsets.all(16),
              decoration: BoxDecoration(
                color: selected
                    ? GradeFlowTheme.primary.withOpacity(0.06)
                    : GradeFlowTheme.surfaceContainerLow,
                borderRadius: BorderRadius.circular(14),
                border: Border.all(
                    color: selected
                        ? GradeFlowTheme.primary
                        : GradeFlowTheme.outlineVariant,
                    width: selected ? 2 : 1),
              ),
              child: Column(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  Row(
                    children: [
                      if (selected)
                        Icon(LucideIcons.checkCircle2,
                            size: 18, color: GradeFlowTheme.primary),
                      if (selected) const SizedBox(width: 8),
                      Text(code,
                          style: GoogleFonts.manrope(
                              fontSize: 14, fontWeight: FontWeight.w700)),
                    ],
                  ),
                  const SizedBox(height: 4),
                  Text(t['label'] as String,
                      style: GoogleFonts.dmSans(
                          fontSize: 13,
                          color: GradeFlowTheme.onSurfaceVariant)),
                  const SizedBox(height: 8),
                  Row(
                    children: (t['parts'] as List<int>)
                        .asMap()
                        .entries
                        .map((e) => _formatBadge(
                            'P${e.key + 1}: ${e.value}',
                            GradeFlowTheme.onSurfaceVariant))
                        .toList(),
                  ),
                ],
              ),
            ),
          );
        }),

        const SizedBox(height: 24),
        Row(
          children: [
            Expanded(
              child: OutlinedButton(
                onPressed: () {
                  setState(() => _selectedTemplate = null);
                  _saveExam();
                },
                child: Text('Bỏ qua',
                    style: GoogleFonts.dmSans(fontWeight: FontWeight.w600)),
              ),
            ),
            const SizedBox(width: 12),
            Expanded(
              flex: 2,
              child: SizedBox(
                height: 48,
                child: ElevatedButton.icon(
                  onPressed: _saving ? null : _saveExam,
                  icon: _saving
                      ? const SizedBox(
                          width: 18,
                          height: 18,
                          child: CircularProgressIndicator(
                              strokeWidth: 2, color: Colors.white))
                      : const Icon(LucideIcons.check, size: 18),
                  label: Text(_saving ? 'Đang lưu...' : 'Lưu đề thi & Chấm bài',
                      style: GoogleFonts.dmSans(
                          fontSize: 14, fontWeight: FontWeight.w600)),
                ),
              ),
            ),
          ],
        ),
      ],
    );
  }

  // ── Step indicator ──
  Widget _buildStepIndicator() {
    return Row(
      children: [
        _stepDot(1, 'Tải file'),
        _stepLine(1),
        _stepDot(2, 'Xác nhận'),
        _stepLine(2),
        _stepDot(3, 'Lưu'),
      ],
    );
  }

  Widget _stepDot(int num, String label) {
    final done = _step > num;
    final active = _step == num;
    return Column(
      children: [
        Container(
          width: 30,
          height: 30,
          decoration: BoxDecoration(
            shape: BoxShape.circle,
            color: done
                ? GradeFlowTheme.primary
                : active
                    ? GradeFlowTheme.primary
                    : GradeFlowTheme.surfaceContainer,
            border: Border.all(
                color: done || active
                    ? GradeFlowTheme.primary
                    : GradeFlowTheme.outlineVariant),
          ),
          child: Center(
            child: done
                ? const Icon(LucideIcons.check, size: 16, color: Colors.white)
                : Text('$num',
                    style: GoogleFonts.manrope(
                        fontSize: 13,
                        fontWeight: FontWeight.w700,
                        color: active
                            ? Colors.white
                            : GradeFlowTheme.onSurfaceVariant)),
          ),
        ),
        const SizedBox(height: 4),
        Text(label,
            style: GoogleFonts.dmSans(
                fontSize: 10,
                color: active || done
                    ? GradeFlowTheme.primary
                    : GradeFlowTheme.onSurfaceVariant)),
      ],
    );
  }

  Widget _stepLine(int afterStep) {
    final done = _step > afterStep;
    return Expanded(
      child: Container(
        height: 2,
        margin: const EdgeInsets.only(bottom: 18, left: 4, right: 4),
        color: done
            ? GradeFlowTheme.primary
            : GradeFlowTheme.outlineVariant.withOpacity(0.5),
      ),
    );
  }
}
