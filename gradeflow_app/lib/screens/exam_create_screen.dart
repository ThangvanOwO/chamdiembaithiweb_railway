import 'package:flutter/material.dart';
import 'package:google_fonts/google_fonts.dart';
import 'package:lucide_icons/lucide_icons.dart';
import 'package:provider/provider.dart';
import 'package:cached_network_image/cached_network_image.dart';

import '../config/theme.dart';
import '../services/auth_service.dart';
import '../services/api_service.dart';

class ExamCreateScreen extends StatefulWidget {
  const ExamCreateScreen({super.key});

  @override
  State<ExamCreateScreen> createState() => _ExamCreateScreenState();
}

class _ExamCreateScreenState extends State<ExamCreateScreen> {
  final _formKey = GlobalKey<FormState>();
  final _titleCtrl = TextEditingController();
  final _subjectCtrl = TextEditingController();

  // Template selection (from API)
  List<Map<String, dynamic>> _templates = [];
  bool _loadingTemplates = true;
  Map<String, dynamic>? _selectedTemplate;
  int _previewPageIdx = 0;

  // Derived from selected template
  int _p1Count = 24;
  int _p2Count = 4;
  int _p3Count = 0;

  // Variants: list of {code, p1, p2, p3}
  final List<_VariantData> _variants = [_VariantData()];
  bool _saving = false;
  int _currentStep = 0;
  int _activeVariantIndex = 0;

  @override
  void initState() {
    super.initState();
    _loadTemplates();
  }

  @override
  void dispose() {
    _titleCtrl.dispose();
    _subjectCtrl.dispose();
    for (final variant in _variants) {
      variant.dispose();
    }
    super.dispose();
  }

  Future<void> _loadTemplates() async {
    final auth = context.read<AuthService>();
    if (auth.token == null) return;
    try {
      final api = ApiService(token: auth.token!);
      final templates = await api.getTemplates();
      if (mounted) {
        setState(() {
          _templates = templates;
          _loadingTemplates = false;
        });
      }
    } catch (_) {
      if (mounted) setState(() => _loadingTemplates = false);
    }
  }

  int get _totalQuestions => _p1Count + _p2Count + _p3Count;

  Future<void> _saveExam() async {
    if (!_formKey.currentState!.validate()) return;

    final auth = context.read<AuthService>();
    if (auth.token == null) return;

    setState(() => _saving = true);
    try {
      final api = ApiService(token: auth.token!);
      final variantsList = _variants
          .where((v) => v.codeCtrl.text.trim().isNotEmpty)
          .map((v) => {
                'code': v.codeCtrl.text.trim(),
                'p1': v.buildP1Answers(_p1Count),
                'p2': v.buildP2Answers(_p2Count),
                'p3': v.buildP3Answers(_p3Count),
              })
          .toList();

      await api.createExam(
        title: _titleCtrl.text.trim(),
        subject: _subjectCtrl.text.trim(),
        templateCode: _selectedTemplate?['code'] ?? '',
        parts: [_p1Count, _p2Count, _p3Count],
        variants: variantsList,
      );

      if (mounted) {
        ScaffoldMessenger.of(context).showSnackBar(
          const SnackBar(
              content: Text('Đã tạo đề thi thành công!'),
              backgroundColor: Color(0xFF2E7D32)),
        );
        Navigator.pop(context, true);
      }
    } catch (e) {
      if (mounted) {
        setState(() => _saving = false);
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
        toolbarHeight: 80,
        leading: IconButton(
          icon: const Icon(LucideIcons.arrowLeft),
          onPressed: () {
            if (_currentStep > 0) {
              setState(() => _currentStep--);
            } else {
              Navigator.pop(context);
            }
          },
        ),
        title: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            const Text('Tạo đề thi'),
            Text(
              'Bước ${_currentStep + 1}/3 · ${_stepLabels[_currentStep]}',
              style: GoogleFonts.dmSans(
                fontSize: 12,
                color: GradeFlowTheme.onSurfaceVariant,
              ),
            ),
          ],
        ),
        actions: [
          if (_currentStep == 2)
            IconButton(
              tooltip: 'Lưu đề thi',
              onPressed: _saving ? null : _saveExam,
              icon: _saving
                  ? const SizedBox(
                      width: 18,
                      height: 18,
                      child: CircularProgressIndicator(strokeWidth: 2),
                    )
                  : const Icon(LucideIcons.save, size: 20),
            ),
        ],
      ),
      body: Form(
        key: _formKey,
        child: Column(
          children: [
            _buildProgress(),
            Expanded(
              child: SingleChildScrollView(
                padding: const EdgeInsets.fromLTRB(20, 28, 20, 32),
                child: _buildCurrentStep(),
              ),
            ),
          ],
        ),
      ),
      bottomNavigationBar: _buildBottomAction(),
    );
  }

  static const _stepLabels = ['Thông tin', 'Mẫu giấy thi', 'Đáp án'];

  Widget _buildProgress() {
    return Container(
      color: GradeFlowTheme.surfaceContainerLowest,
      padding: const EdgeInsets.fromLTRB(28, 15, 28, 18),
      child: Column(
        children: [
          SizedBox(
            height: 42,
            child: Stack(
              alignment: Alignment.center,
              children: [
                Positioned(
                  left: 23,
                  right: 23,
                  top: 20,
                  child: Row(
                    children: List.generate(
                      2,
                      (index) => Expanded(
                        child: Container(
                          height: 3,
                          margin: const EdgeInsets.symmetric(horizontal: 12),
                          color: index < _currentStep
                              ? GradeFlowTheme.primary
                              : GradeFlowTheme.surfaceContainerHigh,
                        ),
                      ),
                    ),
                  ),
                ),
                Row(
                  mainAxisAlignment: MainAxisAlignment.spaceBetween,
                  children: List.generate(3, _buildProgressCircle),
                ),
              ],
            ),
          ),
          const SizedBox(height: 7),
          Row(
            children: List.generate(
              3,
              (index) => Expanded(
                child: Text(
                  _stepLabels[index],
                  textAlign: TextAlign.center,
                  style: GoogleFonts.dmSans(
                    fontSize: 11,
                    fontWeight: index == _currentStep
                        ? FontWeight.w800
                        : FontWeight.w600,
                    color: index == _currentStep
                        ? GradeFlowTheme.primary
                        : GradeFlowTheme.onSurfaceVariant,
                  ),
                ),
              ),
            ),
          ),
        ],
      ),
    );
  }

  Widget _buildProgressCircle(int index) {
    final completed = index < _currentStep;
    final active = index == _currentStep;
    final filled = completed || active;
    return Container(
      width: 40,
      height: 40,
      decoration: BoxDecoration(
        color: filled ? GradeFlowTheme.primary : GradeFlowTheme.surfaceContainer,
        shape: BoxShape.circle,
        boxShadow: active
            ? [
                BoxShadow(
                  color: GradeFlowTheme.primary.withValues(alpha: 0.20),
                  blurRadius: 10,
                  offset: const Offset(0, 3),
                ),
              ]
            : null,
      ),
      child: Center(
        child: completed
            ? const Icon(LucideIcons.check, size: 19, color: Colors.white)
            : Text(
                '${index + 1}',
                style: GoogleFonts.manrope(
                  fontSize: 16,
                  fontWeight: FontWeight.w800,
                  color: filled ? Colors.white : GradeFlowTheme.onSurfaceVariant,
                ),
              ),
      ),
    );
  }

  Widget _buildCurrentStep() {
    final titles = [
      'Thông tin đề thi',
      'Chọn mẫu giấy thi',
      'Mã đề và đáp án',
    ];
    final subtitles = [
      'Đặt tên để bạn dễ tìm và quản lý bài thi.',
      'Mẫu quyết định số câu và cấu trúc phiếu chấm.',
      'Chọn đáp án chạm một lần cho từng mã đề.',
    ];
    final content = switch (_currentStep) {
      0 => _buildStep1(),
      1 => _buildStep2(),
      _ => _buildStep3(),
    };
    return Column(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        Text(titles[_currentStep],
            style:
                GoogleFonts.manrope(fontSize: 29, fontWeight: FontWeight.w800)),
        const SizedBox(height: 7),
        Text(subtitles[_currentStep],
            style: GoogleFonts.dmSans(
                fontSize: 16,
                height: 1.4,
                color: GradeFlowTheme.onSurfaceVariant)),
        const SizedBox(height: 24),
        content,
      ],
    );
  }

  Widget _buildBottomAction() {
    final onLastStep = _currentStep == 2;
    return SafeArea(
      top: false,
      child: Container(
        color: GradeFlowTheme.surfaceContainerLowest,
        padding: const EdgeInsets.fromLTRB(18, 14, 18, 14),
        child: Row(
          children: [
            if (_currentStep > 0) ...[
              SizedBox(
                height: 56,
                child: OutlinedButton(
                  onPressed: () => setState(() => _currentStep--),
                  child: const Text('Quay lại'),
                ),
              ),
              const SizedBox(width: 10),
            ],
            Expanded(
              child: SizedBox(
                height: 56,
                child: ElevatedButton.icon(
                  onPressed:
                      _saving ? null : (onLastStep ? _saveExam : _nextStep),
                  icon: _saving
                      ? const SizedBox(
                          width: 18,
                          height: 18,
                          child: CircularProgressIndicator(
                              strokeWidth: 2, color: Colors.white),
                        )
                      : Icon(
                          onLastStep ? LucideIcons.save : LucideIcons.arrowRight,
                          size: 21),
                  label: Text(
                    _saving
                        ? 'Đang lưu...'
                        : onLastStep
                            ? 'Lưu đề thi'
                            : _currentStep == 0
                                ? 'Tiếp tục'
                                : 'Tiếp tục: nhập đáp án',
                    style: GoogleFonts.manrope(
                        fontSize: 16, fontWeight: FontWeight.w800),
                  ),
                ),
              ),
            ),
          ],
        ),
      ),
    );
  }

  void _nextStep() {
    if (_currentStep == 0 && !(_formKey.currentState?.validate() ?? false)) {
      return;
    }
    if (_currentStep == 1 && _selectedTemplate == null) {
      ScaffoldMessenger.of(context).showSnackBar(
        const SnackBar(content: Text('Hãy chọn một mẫu giấy thi trước.')),
      );
      return;
    }
    setState(() => _currentStep++);
  }

  // ── Step 1: Basic info ──
  Widget _buildStep1() {
    return Card(
      child: Padding(
        padding: const EdgeInsets.all(20),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            Row(
              children: [
                Container(
                  padding: const EdgeInsets.all(12),
                  decoration: BoxDecoration(
                    color: GradeFlowTheme.primaryFixed,
                    borderRadius: BorderRadius.circular(14),
                  ),
                  child: const Icon(LucideIcons.filePlus2,
                      color: GradeFlowTheme.primary, size: 24),
                ),
                const SizedBox(width: 14),
                Expanded(
                  child: Text('Bắt đầu với thông tin cơ bản',
                      style: GoogleFonts.dmSans(
                          fontSize: 18, fontWeight: FontWeight.w800)),
                ),
              ],
            ),
            const SizedBox(height: 22),
            TextFormField(
              controller: _titleCtrl,
              decoration: const InputDecoration(
                labelText: 'Tên đề thi *',
                hintText: 'VD: Kiểm tra giữa kỳ Toán 12',
                prefixIcon: Icon(LucideIcons.fileText, size: 18),
              ),
              validator: (v) => (v == null || v.trim().isEmpty)
                  ? 'Vui lòng nhập tên đề thi'
                  : null,
            ),
            const SizedBox(height: 16),
            TextFormField(
              controller: _subjectCtrl,
              decoration: const InputDecoration(
                labelText: 'Môn học',
                hintText: 'VD: Toán',
                prefixIcon: Icon(LucideIcons.bookOpen, size: 18),
              ),
            ),
            const SizedBox(height: 18),
            Container(
              padding: const EdgeInsets.all(14),
              decoration: BoxDecoration(
                color: GradeFlowTheme.surfaceContainerLow,
                borderRadius: BorderRadius.circular(14),
              ),
              child: Row(
                children: [
                  const Icon(LucideIcons.info,
                      size: 16, color: GradeFlowTheme.primary),
                  const SizedBox(width: 8),
                  Expanded(
                    child: Text(
                      'Bạn có thể thêm nhiều mã đề ở bước cuối.',
                      style: GoogleFonts.dmSans(
                          fontSize: 13, color: GradeFlowTheme.onSurfaceVariant),
                    ),
                  ),
                ],
              ),
            ),
          ],
        ),
      ),
    );
  }

  // ── Step 2: Choose template with preview images ──
  Widget _buildStep2() {
    if (_loadingTemplates) {
      return const Center(
        child: Padding(
          padding: EdgeInsets.all(24),
          child: CircularProgressIndicator(strokeWidth: 2),
        ),
      );
    }

    if (_templates.isEmpty) {
      return Center(
        child: Padding(
          padding: const EdgeInsets.all(16),
          child: Text('Không có mẫu giấy thi nào',
              style: GoogleFonts.dmSans(
                  fontSize: 14, color: GradeFlowTheme.onSurfaceVariant)),
        ),
      );
    }

    return Column(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        Text('Chọn mẫu phiếu thi phù hợp',
            style: GoogleFonts.dmSans(
                fontSize: 13, color: GradeFlowTheme.onSurfaceVariant)),
        const SizedBox(height: 12),
        ..._templates.map((t) {
          final code = t['code'] as String;
          final parts = List<int>.from(t['parts'] ?? [0, 0, 0]);
          final desc = t['desc'] as String? ?? '';
          final total = t['total'] ?? 0;
          final images = List<String>.from(t['images'] ?? []);
          final pages = t['pages'] ?? 1;
          final selected = _selectedTemplate?['code'] == code;

          return GestureDetector(
            onTap: () {
              setState(() {
                _selectedTemplate = t;
                _p1Count = parts[0];
                _p2Count = parts.length > 1 ? parts[1] : 0;
                _p3Count = parts.length > 2 ? parts[2] : 0;
                _previewPageIdx = 0;
              });
            },
            child: AnimatedContainer(
              duration: const Duration(milliseconds: 200),
              margin: const EdgeInsets.only(bottom: 12),
              decoration: BoxDecoration(
                color: selected
                    ? GradeFlowTheme.primary.withValues(alpha: 0.06)
                    : GradeFlowTheme.surfaceContainerLow,
                borderRadius: BorderRadius.circular(14),
                border: Border.all(
                  color: selected
                      ? GradeFlowTheme.primary
                      : GradeFlowTheme.outlineVariant,
                  width: selected ? 2 : 1,
                ),
              ),
              child: Column(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  Padding(
                    padding: const EdgeInsets.fromLTRB(14, 14, 14, 0),
                    child: Row(
                      children: [
                        if (selected)
                          Icon(LucideIcons.checkCircle2,
                              size: 18, color: GradeFlowTheme.primary),
                        if (selected) const SizedBox(width: 8),
                        Expanded(
                          child: Column(
                            crossAxisAlignment: CrossAxisAlignment.start,
                            children: [
                              Text(code,
                                  style: GoogleFonts.manrope(
                                      fontSize: 14,
                                      fontWeight: FontWeight.w700)),
                              const SizedBox(height: 2),
                              Text(desc,
                                  style: GoogleFonts.dmSans(
                                      fontSize: 12,
                                      color: GradeFlowTheme.onSurfaceVariant)),
                            ],
                          ),
                        ),
                        Container(
                          padding: const EdgeInsets.symmetric(
                              horizontal: 8, vertical: 3),
                          decoration: BoxDecoration(
                            color:
                                GradeFlowTheme.primary.withValues(alpha: 0.1),
                            borderRadius: BorderRadius.circular(8),
                          ),
                          child: Text('$total câu',
                              style: GoogleFonts.manrope(
                                  fontSize: 11,
                                  fontWeight: FontWeight.w700,
                                  color: GradeFlowTheme.primary)),
                        ),
                      ],
                    ),
                  ),
                  const SizedBox(height: 8),
                  Padding(
                    padding: const EdgeInsets.symmetric(horizontal: 14),
                    child: Row(
                      children: [
                        _partBadge('P1: ${parts[0]}', GradeFlowTheme.primary),
                        const SizedBox(width: 4),
                        if (parts.length > 1 && parts[1] > 0) ...[
                          _partBadge(
                              'P2: ${parts[1]}', const Color(0xFFE65100)),
                          const SizedBox(width: 4),
                        ],
                        if (parts.length > 2 && parts[2] > 0)
                          _partBadge(
                              'P3: ${parts[2]}', const Color(0xFF6A1B9A)),
                        const Spacer(),
                        Text('$pages trang',
                            style: GoogleFonts.dmSans(
                                fontSize: 11,
                                color: GradeFlowTheme.onSurfaceVariant)),
                      ],
                    ),
                  ),

                  // Preview images — show when selected
                  if (selected && images.isNotEmpty) ...[
                    const SizedBox(height: 12),
                    const Divider(height: 1),
                    Padding(
                      padding: const EdgeInsets.all(12),
                      child: Column(
                        crossAxisAlignment: CrossAxisAlignment.start,
                        children: [
                          Row(
                            children: [
                              Icon(LucideIcons.eye,
                                  size: 14, color: GradeFlowTheme.primary),
                              const SizedBox(width: 6),
                              Text('Xem trước mẫu phiếu',
                                  style: GoogleFonts.dmSans(
                                      fontSize: 12,
                                      fontWeight: FontWeight.w600)),
                              const Spacer(),
                              if (images.length > 1)
                                Text(
                                    'Trang ${_previewPageIdx + 1}/${images.length}',
                                    style: GoogleFonts.dmSans(
                                        fontSize: 11,
                                        color:
                                            GradeFlowTheme.onSurfaceVariant)),
                            ],
                          ),
                          const SizedBox(height: 8),
                          ClipRRect(
                            borderRadius: BorderRadius.circular(10),
                            child: CachedNetworkImage(
                              imageUrl: images[_previewPageIdx],
                              httpHeaders: _getAuthHeaders(),
                              width: double.infinity,
                              fit: BoxFit.contain,
                              placeholder: (_, __) => Container(
                                height: 200,
                                color: GradeFlowTheme.surfaceContainer,
                                child: const Center(
                                    child: CircularProgressIndicator(
                                        strokeWidth: 2)),
                              ),
                              errorWidget: (_, __, ___) => Container(
                                height: 120,
                                color: GradeFlowTheme.surfaceContainer,
                                child: Center(
                                  child: Column(
                                    mainAxisAlignment: MainAxisAlignment.center,
                                    children: [
                                      Icon(LucideIcons.imageOff,
                                          size: 28,
                                          color:
                                              GradeFlowTheme.onSurfaceVariant),
                                      const SizedBox(height: 4),
                                      Text('Không tải được ảnh',
                                          style: GoogleFonts.dmSans(
                                              fontSize: 11,
                                              color: GradeFlowTheme
                                                  .onSurfaceVariant)),
                                    ],
                                  ),
                                ),
                              ),
                            ),
                          ),
                          if (images.length > 1) ...[
                            const SizedBox(height: 8),
                            Row(
                              mainAxisAlignment: MainAxisAlignment.center,
                              children: List.generate(images.length, (i) {
                                return GestureDetector(
                                  onTap: () =>
                                      setState(() => _previewPageIdx = i),
                                  child: Container(
                                    width: 60,
                                    margin: const EdgeInsets.symmetric(
                                        horizontal: 4),
                                    padding:
                                        const EdgeInsets.symmetric(vertical: 6),
                                    decoration: BoxDecoration(
                                      color: _previewPageIdx == i
                                          ? GradeFlowTheme.primary
                                          : GradeFlowTheme.surfaceContainer,
                                      borderRadius: BorderRadius.circular(8),
                                    ),
                                    child: Text(
                                      'Trang ${i + 1}',
                                      textAlign: TextAlign.center,
                                      style: GoogleFonts.dmSans(
                                        fontSize: 11,
                                        fontWeight: FontWeight.w600,
                                        color: _previewPageIdx == i
                                            ? Colors.white
                                            : GradeFlowTheme.onSurfaceVariant,
                                      ),
                                    ),
                                  ),
                                );
                              }),
                            ),
                          ],
                        ],
                      ),
                    ),
                  ],
                  if (!selected) const SizedBox(height: 14),
                ],
              ),
            ),
          );
        }),
        if (_selectedTemplate != null)
          Container(
            padding: const EdgeInsets.all(12),
            decoration: BoxDecoration(
              color: GradeFlowTheme.surfaceContainer,
              borderRadius: BorderRadius.circular(10),
            ),
            child: Row(
              mainAxisAlignment: MainAxisAlignment.center,
              children: [
                Icon(LucideIcons.info, size: 16, color: GradeFlowTheme.primary),
                const SizedBox(width: 8),
                Text(
                    'Cấu trúc: P1=$_p1Count · P2=$_p2Count · P3=$_p3Count · Tổng=$_totalQuestions câu',
                    style: GoogleFonts.dmSans(
                        fontSize: 12, fontWeight: FontWeight.w600)),
              ],
            ),
          ),
      ],
    );
  }

  Map<String, String> _getAuthHeaders() {
    final auth = context.read<AuthService>();
    return {
      'Authorization': 'Token ${auth.token ?? ''}',
    };
  }

  Widget _partBadge(String text, Color color) {
    return Container(
      padding: const EdgeInsets.symmetric(horizontal: 8, vertical: 3),
      decoration: BoxDecoration(
        color: color.withValues(alpha: 0.12),
        borderRadius: BorderRadius.circular(6),
      ),
      child: Text(text,
          style: GoogleFonts.manrope(
              fontSize: 10, fontWeight: FontWeight.w700, color: color)),
    );
  }

  // ── Step 3: Mã đề & Đáp án ──
  Widget _buildStep3() {
    final variant = _variants[_activeVariantIndex];
    _ensureAnswerSlots(variant);
    final answered = _answeredCount(variant);
    return Column(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        _buildTemplateSummary(),
        const SizedBox(height: 16),
        Text('Danh sách mã đề',
            style:
                GoogleFonts.dmSans(fontSize: 13, fontWeight: FontWeight.w700)),
        const SizedBox(height: 8),
        SingleChildScrollView(
          scrollDirection: Axis.horizontal,
          child: Row(
            children: [
              ...List.generate(_variants.length, (index) {
                final item = _variants[index];
                final active = index == _activeVariantIndex;
                final label = item.codeCtrl.text.trim().isEmpty
                    ? 'Mã ${index + 1}'
                    : 'Mã ${item.codeCtrl.text.trim()}';
                return Padding(
                  padding: const EdgeInsets.only(right: 8),
                  child: ChoiceChip(
                    label: Text(label),
                    selected: active,
                    avatar: active
                        ? const Icon(LucideIcons.pencil, size: 13)
                        : null,
                    onSelected: (_) =>
                        setState(() => _activeVariantIndex = index),
                  ),
                );
              }),
              ActionChip(
                avatar: const Icon(LucideIcons.plus, size: 16),
                label: const Text('Thêm mã'),
                onPressed: () => setState(() {
                  _variants.add(_VariantData());
                  _activeVariantIndex = _variants.length - 1;
                }),
              ),
            ],
          ),
        ),
        const SizedBox(height: 14),
        Card(
          child: Padding(
            padding: const EdgeInsets.all(14),
            child: Column(
              children: [
                Row(
                  children: [
                    Expanded(
                      child: TextFormField(
                        controller: variant.codeCtrl,
                        onChanged: (_) => setState(() {}),
                        decoration: InputDecoration(
                          labelText: 'Mã đề ${_activeVariantIndex + 1}',
                          hintText: 'VD: 101',
                          prefixIcon: const Icon(LucideIcons.hash, size: 18),
                          isDense: true,
                        ),
                      ),
                    ),
                    if (_variants.length > 1) ...[
                      const SizedBox(width: 4),
                      IconButton(
                        tooltip: 'Xóa mã đề',
                        icon: const Icon(LucideIcons.trash2,
                            size: 19, color: GradeFlowTheme.error),
                        onPressed: () => setState(() {
                          final removed =
                              _variants.removeAt(_activeVariantIndex);
                          removed.dispose();
                          _activeVariantIndex = _activeVariantIndex.clamp(
                              0, _variants.length - 1);
                        }),
                      ),
                    ],
                  ],
                ),
                const SizedBox(height: 12),
                _completionRow(answered),
              ],
            ),
          ),
        ),
        if (_p1Count > 0) ...[
          const SizedBox(height: 20),
          _sectionHeader(
              'Phần I: Trắc nghiệm ABCD', '$_p1Count câu · Chạm để chọn'),
          const SizedBox(height: 8),
          _buildP1AnswerEditor(variant),
        ],
        if (_p2Count > 0) ...[
          const SizedBox(height: 22),
          _sectionHeader('Phần II: Đúng / Sai', '$_p2Count câu · 4 ý mỗi câu'),
          const SizedBox(height: 8),
          _buildP2AnswerEditor(variant),
        ],
        if (_p3Count > 0) ...[
          const SizedBox(height: 22),
          _sectionHeader('Phần III: Trả lời ngắn', '$_p3Count câu'),
          const SizedBox(height: 8),
          _buildP3AnswerEditor(variant),
        ],
      ],
    );
  }

  Widget _buildTemplateSummary() {
    final label = _selectedTemplate?['label'] as String? ??
        _selectedTemplate?['code'] as String? ??
        'Mẫu giấy thi';
    return Container(
      padding: const EdgeInsets.all(14),
      decoration: BoxDecoration(
        color: GradeFlowTheme.primaryFixed,
        borderRadius: BorderRadius.circular(14),
      ),
      child: Row(
        children: [
          Container(
            padding: const EdgeInsets.all(9),
            decoration: const BoxDecoration(
              color: GradeFlowTheme.primary,
              shape: BoxShape.circle,
            ),
            child: const Icon(LucideIcons.clipboardCheck,
                size: 18, color: Colors.white),
          ),
          const SizedBox(width: 10),
          Expanded(
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                Text(label,
                    style: GoogleFonts.dmSans(
                        fontSize: 14, fontWeight: FontWeight.w800)),
                const SizedBox(height: 2),
                Text(
                    '$_totalQuestions câu · P1 $_p1Count · P2 $_p2Count · P3 $_p3Count',
                    style: GoogleFonts.dmSans(
                        fontSize: 11, color: GradeFlowTheme.onSurfaceVariant)),
              ],
            ),
          ),
          Container(
            padding: const EdgeInsets.symmetric(horizontal: 8, vertical: 5),
            decoration: BoxDecoration(
              color: Colors.white.withValues(alpha: 0.72),
              borderRadius: BorderRadius.circular(8),
            ),
            child: Text('Sẵn sàng',
                style: GoogleFonts.dmSans(
                    fontSize: 11,
                    fontWeight: FontWeight.w700,
                    color: GradeFlowTheme.primary)),
          ),
        ],
      ),
    );
  }

  Widget _completionRow(int answered) {
    final total = _totalQuestions + (_p2Count * 3);
    final complete = total == 0 ? 0 : (answered / total * 100).round();
    return Row(
      children: [
        Icon(
            answered == total
                ? LucideIcons.checkCircle2
                : LucideIcons.circleDot,
            size: 16,
            color: answered == total
                ? GradeFlowTheme.success
                : GradeFlowTheme.primary),
        const SizedBox(width: 7),
        Expanded(
          child: Text('$answered/$total lựa chọn đã nhập',
              style: GoogleFonts.dmSans(
                  fontSize: 12, fontWeight: FontWeight.w700)),
        ),
        Text('$complete%',
            style: GoogleFonts.manrope(
                fontSize: 12,
                fontWeight: FontWeight.w800,
                color: GradeFlowTheme.primary)),
      ],
    );
  }

  Widget _sectionHeader(String title, String subtitle) {
    return Row(
      children: [
        Expanded(
          child: Column(
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              Text(title,
                  style: GoogleFonts.manrope(
                      fontSize: 16, fontWeight: FontWeight.w800)),
              const SizedBox(height: 2),
              Text(subtitle,
                  style: GoogleFonts.dmSans(
                      fontSize: 12, color: GradeFlowTheme.onSurfaceVariant)),
            ],
          ),
        ),
        const Icon(LucideIcons.mousePointerClick,
            size: 17, color: GradeFlowTheme.primary),
      ],
    );
  }

  void _ensureAnswerSlots(_VariantData variant) {
    while (variant.p1Answers.length < _p1Count) {
      variant.p1Answers.add('');
    }
    while (variant.p2Answers.length < _p2Count) {
      variant.p2Answers.add({'a': '', 'b': '', 'c': '', 'd': ''});
    }
    while (variant.p3Ctrls.length < _p3Count) {
      variant.p3Ctrls.add(TextEditingController());
    }
  }

  int _answeredCount(_VariantData variant) {
    final p1 = variant.p1Answers.where((answer) => answer.isNotEmpty).length;
    final p2 = variant.p2Answers.fold<int>(
        0,
        (sum, answer) =>
            sum + answer.values.where((value) => value.isNotEmpty).length);
    final p3 =
        variant.p3Ctrls.where((ctrl) => ctrl.text.trim().isNotEmpty).length;
    return p1 + p2 + p3;
  }

  Widget _buildP1AnswerEditor(_VariantData variant) {
    return Card(
      child: Padding(
        padding: const EdgeInsets.all(10),
        child: Column(
          children: List.generate(_p1Count, (index) {
            final answer = variant.p1Answers[index];
            return Container(
              margin: EdgeInsets.only(bottom: index == _p1Count - 1 ? 0 : 7),
              padding: const EdgeInsets.symmetric(horizontal: 10, vertical: 7),
              decoration: BoxDecoration(
                color: answer.isEmpty
                    ? GradeFlowTheme.surfaceContainerLow
                    : GradeFlowTheme.primaryFixed.withValues(alpha: 0.52),
                borderRadius: BorderRadius.circular(10),
              ),
              child: Row(
                children: [
                  Container(
                    width: 30,
                    height: 30,
                    alignment: Alignment.center,
                    decoration: BoxDecoration(
                      color: answer.isEmpty
                          ? GradeFlowTheme.surfaceContainerHigh
                          : GradeFlowTheme.primary,
                      borderRadius: BorderRadius.circular(8),
                    ),
                    child: Text('${index + 1}'.padLeft(2, '0'),
                        style: GoogleFonts.manrope(
                            fontSize: 11,
                            fontWeight: FontWeight.w800,
                            color: answer.isEmpty
                                ? GradeFlowTheme.onSurfaceVariant
                                : Colors.white)),
                  ),
                  const SizedBox(width: 10),
                  ...['A', 'B', 'C', 'D'].map(
                    (letter) => Expanded(
                      child: Padding(
                        padding: const EdgeInsets.symmetric(horizontal: 2),
                        child: _answerButton(
                          label: letter,
                          selected: answer == letter,
                          onTap: () =>
                              setState(() => variant.p1Answers[index] = letter),
                        ),
                      ),
                    ),
                  ),
                ],
              ),
            );
          }),
        ),
      ),
    );
  }

  Widget _answerButton({
    required String label,
    required bool selected,
    required VoidCallback onTap,
  }) {
    return Material(
      color: selected ? GradeFlowTheme.primary : Colors.white,
      borderRadius: BorderRadius.circular(18),
      child: InkWell(
        onTap: onTap,
        borderRadius: BorderRadius.circular(18),
        child: Container(
          height: 34,
          alignment: Alignment.center,
          decoration: BoxDecoration(
            border: selected
                ? null
                : Border.all(color: GradeFlowTheme.outlineVariant),
            borderRadius: BorderRadius.circular(18),
          ),
          child: Text(label,
              style: GoogleFonts.manrope(
                  fontSize: 12,
                  fontWeight: FontWeight.w800,
                  color: selected
                      ? Colors.white
                      : GradeFlowTheme.onSurfaceVariant)),
        ),
      ),
    );
  }

  Widget _buildP2AnswerEditor(_VariantData variant) {
    return Column(
      children: List.generate(_p2Count, (index) {
        final answer = variant.p2Answers[index];
        final question = _p1Count + index + 1;
        final done = answer.values.where((value) => value.isNotEmpty).length;
        return Card(
          margin: EdgeInsets.only(bottom: index == _p2Count - 1 ? 0 : 10),
          child: Padding(
            padding: const EdgeInsets.all(12),
            child: Column(
              children: [
                Row(
                  children: [
                    Container(
                      padding: const EdgeInsets.symmetric(
                          horizontal: 9, vertical: 5),
                      decoration: BoxDecoration(
                        color: GradeFlowTheme.primary,
                        borderRadius: BorderRadius.circular(8),
                      ),
                      child: Text('Câu $question',
                          style: GoogleFonts.dmSans(
                              fontSize: 12,
                              fontWeight: FontWeight.w800,
                              color: Colors.white)),
                    ),
                    const Spacer(),
                    Text('$done/4 ý đã chọn',
                        style: GoogleFonts.dmSans(
                            fontSize: 11,
                            color: done == 4
                                ? GradeFlowTheme.success
                                : GradeFlowTheme.onSurfaceVariant)),
                  ],
                ),
                const SizedBox(height: 10),
                Row(
                  children: ['a', 'b', 'c', 'd'].map((part) {
                    final selected = answer[part] ?? '';
                    return Expanded(
                      child: Padding(
                        padding: const EdgeInsets.symmetric(horizontal: 2),
                        child: Column(
                          children: [
                            Text('Ý ${part.toUpperCase()}',
                                style: GoogleFonts.dmSans(
                                    fontSize: 10,
                                    fontWeight: FontWeight.w700,
                                    color: GradeFlowTheme.onSurfaceVariant)),
                            const SizedBox(height: 5),
                            Row(
                              children: [
                                Expanded(
                                  child: _answerButton(
                                    label: 'Đ',
                                    selected: selected == 'Đ',
                                    onTap: () =>
                                        setState(() => answer[part] = 'Đ'),
                                  ),
                                ),
                                const SizedBox(width: 3),
                                Expanded(
                                  child: _answerButton(
                                    label: 'S',
                                    selected: selected == 'S',
                                    onTap: () =>
                                        setState(() => answer[part] = 'S'),
                                  ),
                                ),
                              ],
                            ),
                          ],
                        ),
                      ),
                    );
                  }).toList(),
                ),
              ],
            ),
          ),
        );
      }),
    );
  }

  Widget _buildP3AnswerEditor(_VariantData variant) {
    return Card(
      child: Padding(
        padding: const EdgeInsets.all(12),
        child: Wrap(
          spacing: 8,
          runSpacing: 8,
          children: List.generate(_p3Count, (index) {
            final question = _p1Count + _p2Count + index + 1;
            return SizedBox(
              width: 100,
              child: TextFormField(
                controller: variant.p3Ctrls[index],
                onChanged: (_) => setState(() {}),
                decoration: InputDecoration(
                  labelText: 'Câu $question',
                  hintText: 'Đáp án',
                  isDense: true,
                ),
                style: GoogleFonts.manrope(
                    fontSize: 13, fontWeight: FontWeight.w700),
              ),
            );
          }),
        ),
      ),
    );
  }
}

class _VariantData {
  final codeCtrl = TextEditingController();
  List<String> p1Answers = [];
  List<Map<String, String>> p2Answers = [];
  List<TextEditingController> p3Ctrls = [];

  void dispose() {
    codeCtrl.dispose();
    for (final controller in p3Ctrls) {
      controller.dispose();
    }
  }

  Map<String, dynamic> buildP1Answers(int count) {
    final map = <String, dynamic>{};
    for (int i = 0; i < count && i < p1Answers.length; i++) {
      if (p1Answers[i].isNotEmpty) {
        map['${i + 1}'] = p1Answers[i];
      }
    }
    return map;
  }

  Map<String, dynamic> buildP2Answers(int count) {
    final map = <String, dynamic>{};
    for (int i = 0; i < count && i < p2Answers.length; i++) {
      final sub = <String, String>{};
      p2Answers[i].forEach((k, v) {
        if (v.isNotEmpty) sub[k] = v;
      });
      if (sub.isNotEmpty) map['${i + 1}'] = sub;
    }
    return map;
  }

  Map<String, dynamic> buildP3Answers(int count) {
    final map = <String, dynamic>{};
    for (int i = 0; i < count && i < p3Ctrls.length; i++) {
      final v = p3Ctrls[i].text.trim();
      if (v.isNotEmpty) map['${i + 1}'] = v;
    }
    return map;
  }
}
