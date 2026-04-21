import 'package:flutter/material.dart';
import 'package:google_fonts/google_fonts.dart';
import 'package:lucide_icons/lucide_icons.dart';
import 'package:provider/provider.dart';

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
  final _templateCtrl = TextEditingController();

  int _p1Count = 24;
  int _p2Count = 4;
  int _p3Count = 0;

  // Variants: list of {code, p1, p2, p3}
  List<_VariantData> _variants = [_VariantData()];
  bool _saving = false;
  int _currentStep = 0;

  @override
  void dispose() {
    _titleCtrl.dispose();
    _subjectCtrl.dispose();
    _templateCtrl.dispose();
    super.dispose();
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
        templateCode: _templateCtrl.text.trim(),
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
        title: const Text('Tạo đề thi'),
        leading: IconButton(
          icon: const Icon(LucideIcons.arrowLeft),
          onPressed: () => Navigator.pop(context),
        ),
        actions: [
          TextButton.icon(
            onPressed: _saving ? null : _saveExam,
            icon: _saving
                ? const SizedBox(
                    width: 16,
                    height: 16,
                    child:
                        CircularProgressIndicator(strokeWidth: 2, color: Colors.white))
                : const Icon(LucideIcons.save, size: 18),
            label: Text(_saving ? 'Đang lưu...' : 'Lưu',
                style: GoogleFonts.dmSans(fontWeight: FontWeight.w600)),
          ),
        ],
      ),
      body: Form(
        key: _formKey,
        child: Stepper(
          currentStep: _currentStep,
          onStepContinue: () {
            if (_currentStep < 2) {
              setState(() => _currentStep++);
            } else {
              _saveExam();
            }
          },
          onStepCancel: () {
            if (_currentStep > 0) setState(() => _currentStep--);
          },
          controlsBuilder: (context, details) {
            return Padding(
              padding: const EdgeInsets.only(top: 12),
              child: Row(
                children: [
                  ElevatedButton(
                    onPressed: details.onStepContinue,
                    child: Text(_currentStep == 2 ? 'Lưu đề thi' : 'Tiếp tục'),
                  ),
                  if (_currentStep > 0) ...[
                    const SizedBox(width: 8),
                    OutlinedButton(
                      onPressed: details.onStepCancel,
                      child: const Text('Quay lại'),
                    ),
                  ],
                ],
              ),
            );
          },
          steps: [
            Step(
              title: const Text('Thông tin đề thi'),
              isActive: _currentStep >= 0,
              state: _currentStep > 0
                  ? StepState.complete
                  : StepState.indexed,
              content: _buildStep1(),
            ),
            Step(
              title: const Text('Cấu hình câu hỏi'),
              isActive: _currentStep >= 1,
              state: _currentStep > 1
                  ? StepState.complete
                  : StepState.indexed,
              content: _buildStep2(),
            ),
            Step(
              title: const Text('Đáp án mã đề'),
              isActive: _currentStep >= 2,
              content: _buildStep3(),
            ),
          ],
        ),
      ),
    );
  }

  // ── Step 1: Basic info ──
  Widget _buildStep1() {
    return Column(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        TextFormField(
          controller: _titleCtrl,
          decoration: const InputDecoration(
            labelText: 'Tên đề thi *',
            hintText: 'VD: Kiểm tra giữa kỳ Toán 12',
            prefixIcon: Icon(LucideIcons.fileText, size: 18),
          ),
          validator: (v) =>
              (v == null || v.trim().isEmpty) ? 'Vui lòng nhập tên đề thi' : null,
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
        const SizedBox(height: 16),
        TextFormField(
          controller: _templateCtrl,
          decoration: const InputDecoration(
            labelText: 'Template code',
            hintText: 'VD: template_default',
            prefixIcon: Icon(LucideIcons.layout, size: 18),
          ),
        ),
      ],
    );
  }

  // ── Step 2: Question config ──
  Widget _buildStep2() {
    return Column(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        _partCounter('Phần I — Trắc nghiệm (ABCD)', _p1Count, (v) {
          setState(() => _p1Count = v);
        }),
        const SizedBox(height: 12),
        _partCounter('Phần II — Đúng/Sai (câu x 4 ý)', _p2Count, (v) {
          setState(() => _p2Count = v);
        }),
        const SizedBox(height: 12),
        _partCounter('Phần III — Trả lời ngắn', _p3Count, (v) {
          setState(() => _p3Count = v);
        }),
        const SizedBox(height: 12),
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
              Text('Tổng: $_totalQuestions câu',
                  style: GoogleFonts.dmSans(
                      fontSize: 14, fontWeight: FontWeight.w600)),
            ],
          ),
        ),
      ],
    );
  }

  Widget _partCounter(String label, int value, ValueChanged<int> onChanged) {
    return Row(
      children: [
        Expanded(
          child: Text(label,
              style: GoogleFonts.dmSans(fontSize: 13, fontWeight: FontWeight.w500)),
        ),
        IconButton(
          icon: const Icon(LucideIcons.minus, size: 18),
          onPressed: value > 0 ? () => onChanged(value - 1) : null,
          visualDensity: VisualDensity.compact,
        ),
        Container(
          width: 40,
          alignment: Alignment.center,
          child: Text('$value',
              style: GoogleFonts.manrope(
                  fontSize: 16, fontWeight: FontWeight.w700)),
        ),
        IconButton(
          icon: const Icon(LucideIcons.plus, size: 18),
          onPressed: () => onChanged(value + 1),
          visualDensity: VisualDensity.compact,
        ),
      ],
    );
  }

  // ── Step 3: Variants ──
  Widget _buildStep3() {
    return Column(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        Text('Thêm mã đề và nhập đáp án',
            style: GoogleFonts.dmSans(
                fontSize: 13, color: GradeFlowTheme.onSurfaceVariant)),
        const SizedBox(height: 12),
        ..._variants.asMap().entries.map((entry) {
          final idx = entry.key;
          final v = entry.value;
          return Card(
            margin: const EdgeInsets.only(bottom: 12),
            child: Padding(
              padding: const EdgeInsets.all(12),
              child: Column(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  Row(
                    children: [
                      Expanded(
                        child: TextFormField(
                          controller: v.codeCtrl,
                          decoration: InputDecoration(
                            labelText: 'Mã đề ${idx + 1}',
                            hintText: 'VD: 101',
                            isDense: true,
                          ),
                        ),
                      ),
                      if (_variants.length > 1)
                        IconButton(
                          icon: const Icon(LucideIcons.trash2,
                              size: 18, color: Colors.red),
                          onPressed: () =>
                              setState(() => _variants.removeAt(idx)),
                        ),
                    ],
                  ),
                  const SizedBox(height: 8),
                  if (_p1Count > 0) ...[
                    Text('Phần I — Đáp án ABCD (${_p1Count} câu)',
                        style: GoogleFonts.dmSans(
                            fontSize: 12, fontWeight: FontWeight.w600)),
                    const SizedBox(height: 4),
                    _buildP1AnswerInputs(v),
                  ],
                  if (_p2Count > 0) ...[
                    const SizedBox(height: 8),
                    Text('Phần II — Đúng/Sai (${_p2Count} câu x 4 ý)',
                        style: GoogleFonts.dmSans(
                            fontSize: 12, fontWeight: FontWeight.w600)),
                    const SizedBox(height: 4),
                    _buildP2AnswerInputs(v),
                  ],
                  if (_p3Count > 0) ...[
                    const SizedBox(height: 8),
                    Text('Phần III — Trả lời ngắn (${_p3Count} câu)',
                        style: GoogleFonts.dmSans(
                            fontSize: 12, fontWeight: FontWeight.w600)),
                    const SizedBox(height: 4),
                    _buildP3AnswerInputs(v),
                  ],
                ],
              ),
            ),
          );
        }),
        Center(
          child: OutlinedButton.icon(
            onPressed: () => setState(() => _variants.add(_VariantData())),
            icon: const Icon(LucideIcons.plus, size: 16),
            label: const Text('Thêm mã đề'),
          ),
        ),
      ],
    );
  }

  Widget _buildP1AnswerInputs(_VariantData v) {
    while (v.p1Answers.length < _p1Count) {
      v.p1Answers.add('');
    }
    return Wrap(
      spacing: 4,
      runSpacing: 4,
      children: List.generate(_p1Count, (i) {
        final qNum = i + 1;
        return SizedBox(
          width: 55,
          child: DropdownButtonFormField<String>(
            value: v.p1Answers[i].isNotEmpty ? v.p1Answers[i] : null,
            decoration: InputDecoration(
              labelText: '$qNum',
              isDense: true,
              contentPadding:
                  const EdgeInsets.symmetric(horizontal: 6, vertical: 6),
            ),
            items: ['A', 'B', 'C', 'D']
                .map((c) =>
                    DropdownMenuItem(value: c, child: Text(c, style: const TextStyle(fontSize: 13))))
                .toList(),
            onChanged: (val) {
              v.p1Answers[i] = val ?? '';
            },
            style: GoogleFonts.manrope(fontSize: 13, fontWeight: FontWeight.w700, color: Colors.black),
          ),
        );
      }),
    );
  }

  Widget _buildP2AnswerInputs(_VariantData v) {
    while (v.p2Answers.length < _p2Count) {
      v.p2Answers.add({'a': '', 'b': '', 'c': '', 'd': ''});
    }
    return Column(
      children: List.generate(_p2Count, (i) {
        final qNum = _p1Count + i + 1;
        return Padding(
          padding: const EdgeInsets.only(bottom: 6),
          child: Row(
            children: [
              SizedBox(
                width: 32,
                child: Text('$qNum',
                    style: GoogleFonts.dmSans(
                        fontSize: 12, fontWeight: FontWeight.w600)),
              ),
              ...['a', 'b', 'c', 'd'].map((sub) => Expanded(
                    child: Padding(
                      padding: const EdgeInsets.symmetric(horizontal: 2),
                      child: DropdownButtonFormField<String>(
                        value: v.p2Answers[i][sub]!.isNotEmpty
                            ? v.p2Answers[i][sub]
                            : null,
                        decoration: InputDecoration(
                          labelText: sub.toUpperCase(),
                          isDense: true,
                          contentPadding: const EdgeInsets.symmetric(
                              horizontal: 4, vertical: 4),
                        ),
                        items: ['Đ', 'S']
                            .map((c) => DropdownMenuItem(
                                value: c,
                                child: Text(c,
                                    style: const TextStyle(fontSize: 11))))
                            .toList(),
                        onChanged: (val) {
                          v.p2Answers[i][sub] = val ?? '';
                        },
                        style: GoogleFonts.dmSans(fontSize: 11, color: Colors.black),
                      ),
                    ),
                  )),
            ],
          ),
        );
      }),
    );
  }

  Widget _buildP3AnswerInputs(_VariantData v) {
    while (v.p3Ctrls.length < _p3Count) {
      v.p3Ctrls.add(TextEditingController());
    }
    return Wrap(
      spacing: 6,
      runSpacing: 6,
      children: List.generate(_p3Count, (i) {
        final qNum = _p1Count + _p2Count + i + 1;
        return SizedBox(
          width: 80,
          child: TextFormField(
            controller: v.p3Ctrls[i],
            decoration: InputDecoration(
              labelText: 'C$qNum',
              isDense: true,
              contentPadding:
                  const EdgeInsets.symmetric(horizontal: 8, vertical: 8),
            ),
            style: GoogleFonts.manrope(fontSize: 13, fontWeight: FontWeight.w600),
          ),
        );
      }),
    );
  }
}

class _VariantData {
  final codeCtrl = TextEditingController();
  List<String> p1Answers = [];
  List<Map<String, String>> p2Answers = [];
  List<TextEditingController> p3Ctrls = [];

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
