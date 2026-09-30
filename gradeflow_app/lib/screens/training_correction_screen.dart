import 'dart:convert';
import 'dart:typed_data';
import 'package:flutter/material.dart';
import 'package:provider/provider.dart';

import '../models/grade_result.dart';
import '../services/api_service.dart';
import '../services/auth_service.dart';
import '../widgets/academic_ui.dart';

/// Explicit labels of the marks on paper, independent of the exam answer key.
class TrainingCorrectionScreen extends StatefulWidget {
  final Uint8List imageBytes;
  final GradeResult result;
  final String templateCode;
  final List<List<double>>? corners;
  final ApiService? api;
  const TrainingCorrectionScreen(
      {super.key,
      required this.imageBytes,
      required this.result,
      required this.templateCode,
      this.corners,
      this.api});

  @override
  State<TrainingCorrectionScreen> createState() =>
      _TrainingCorrectionScreenState();
}

class _TrainingCorrectionScreenState extends State<TrainingCorrectionScreen> {
  int _part = 1;
  int _question = 1;
  String _sub = 'a';
  Map<String, dynamic>? _preview;
  Map<String, String> _labels = {};
  bool _busy = false;
  bool _confirmed = false;
  String? _error;
  String? _choice;
  String? _sign;
  String? _comma;
  final Map<int, String> _digits = {};
  int _saved = 0;

  Map<String, dynamic> _answers(int part) => part == 1
      ? widget.result.part1
      : part == 2
          ? widget.result.part2
          : widget.result.part3;
  List<int> _questions(int part) =>
      _answers(part).keys.map(int.tryParse).whereType<int>().toList()..sort();
  ApiService get _api =>
      widget.api ?? ApiService(token: context.read<AuthService>().token!);

  @override
  void initState() {
    super.initState();
    _part =
        [1, 2, 3].firstWhere((p) => _questions(p).isNotEmpty, orElse: () => 1);
    _question = _questions(_part).firstOrNull ?? 1;
    // Bring unresolved Part II marks to attention, without suggesting a label.
    for (final q in _questions(2)) {
      final answers = widget.result.part2['$q'];
      if (answers is Map) {
        for (final s in ['a', 'b', 'c', 'd']) {
          if ((answers[s]?.toString() ?? '').isEmpty) {
            _part = 2;
            _question = q;
            _sub = s;
            return;
          }
        }
      }
    }
  }

  void _reset() {
    _preview = null;
    _labels = {};
    _confirmed = false;
    _error = null;
    _choice = null;
    _sign = null;
    _comma = null;
    _digits.clear();
  }

  Future<void> _loadPreview() async {
    setState(() {
      _busy = true;
      _reset();
    });
    try {
      final data = await _api.previewTrainingQuestion(
          imageBytes: widget.imageBytes,
          templateCode: widget.templateCode,
          part: _part,
          question: _question,
          subquestion: _part == 2 ? _sub : '',
          corners: widget.corners);
      if (mounted) setState(() => _preview = data);
    } catch (e) {
      if (mounted) setState(() => _error = '$e');
    } finally {
      if (mounted) setState(() => _busy = false);
    }
  }

  void _labelChoice(String value) {
    setState(() {
      _choice = value;
      _confirmed = false;
      _labels = {
        for (final c in _preview!['cells'] as List)
          c['id'] as String: value == '?'
              ? 'skip'
              : value == 'X' || value == c['id']
                  ? 'filled'
                  : 'empty'
      };
    });
  }

  void _setDigit(int col, String value) {
    setState(() {
      _digits[col] = value;
      _confirmed = false;
      for (var digit = 0; digit < 10; digit++) {
        _labels['digit_${col}_$digit'] = value == '?'
            ? 'skip'
            : value == '$digit'
                ? 'filled'
                : 'empty';
      }
    });
  }

  Future<void> _save() async {
    setState(() {
      _busy = true;
      _error = null;
    });
    try {
      final saved =
          await _api.saveTrainingQuestion(_preview!['preview_token'], _labels);
      if (!mounted) return;
      setState(() {
        _saved++;
        _reset();
      });
      ScaffoldMessenger.of(context).showSnackBar(SnackBar(
          content: Text(saved['duplicate'] == true
              ? 'Mẫu này đã được lưu; không tạo bản trùng.'
              : 'Đã lưu câu được chọn vào hàng chờ duyệt.')));
    } catch (e) {
      if (mounted) setState(() => _error = '$e');
    } finally {
      if (mounted) setState(() => _busy = false);
    }
  }

  @override
  Widget build(BuildContext context) {
    final ready = _preview != null &&
        _preview!['geometry']['aligned'] == true &&
        _labels.length == (_preview!['cells'] as List).length;
    return Scaffold(
      appBar: AppBar(title: const Text('Training AI · Chọn câu')),
      body: ListView(padding: const EdgeInsets.all(20), children: [
        const AcademicNotice(
            title: 'Dạy từ dấu tô thực tế',
            message:
                'Chỉ chọn câu cần sửa. Nhãn là vòng tròn được tô trên phiếu, không phải đáp án đúng của đề. '
                'Lưu mẫu không thay đổi điểm hoặc huấn luyện mô hình ngay.'),
        const SizedBox(height: 18),
        Row(children: [
          Expanded(
              child: DropdownButtonFormField<int>(
                  initialValue: _part,
                  decoration: const InputDecoration(labelText: 'Phần'),
                  items: [
                    for (final p in [1, 2, 3])
                      if (_questions(p).isNotEmpty)
                        DropdownMenuItem(value: p, child: Text('Phần $p'))
                  ],
                  onChanged: _busy
                      ? null
                      : (p) => setState(() {
                            _part = p!;
                            _question = _questions(_part).first;
                            _reset();
                          }))),
          const SizedBox(width: 12),
          Expanded(
              child: DropdownButtonFormField<int>(
                  key: ValueKey('$_part:$_question'),
                  initialValue: _question,
                  decoration: const InputDecoration(labelText: 'Câu'),
                  items: [
                    for (final q in _questions(_part))
                      DropdownMenuItem(value: q, child: Text('Câu $q'))
                  ],
                  onChanged: _busy
                      ? null
                      : (q) => setState(() {
                            _question = q!;
                            _reset();
                          }))),
        ]),
        if (_part == 2) ...[
          const SizedBox(height: 12),
          SegmentedButton<String>(
              segments: [
                for (final s in ['a', 'b', 'c', 'd'])
                  ButtonSegment(value: s, label: Text('Ý $s'))
              ],
              selected: {
                _sub
              },
              onSelectionChanged: _busy
                  ? null
                  : (s) => setState(() {
                        _sub = s.first;
                        _reset();
                      })),
        ],
        const SizedBox(height: 14),
        OutlinedButton.icon(
            onPressed: _busy ? null : _loadPreview,
            icon: const Icon(Icons.crop),
            label: const Text('Xem ảnh câu đã chọn')),
        if (_busy)
          const Padding(
              padding: EdgeInsets.all(18),
              child: Center(child: CircularProgressIndicator())),
        if (_error != null)
          Padding(
              padding: const EdgeInsets.symmetric(vertical: 12),
              child: Text(_error!, style: const TextStyle(color: Colors.red))),
        if (_preview != null) ...[
          const SizedBox(height: 12),
          Text('Ảnh gốc · Phần $_part, câu $_question${_part == 2 ? _sub : ""}',
              style: Theme.of(context).textTheme.titleMedium),
          const SizedBox(height: 10),
          Container(
              height: _part == 3 ? 340 : 150,
              padding: const EdgeInsets.all(12),
              decoration: BoxDecoration(
                  color: Colors.white,
                  borderRadius: BorderRadius.circular(16),
                  border: Border.all(
                      color: Theme.of(context).colorScheme.outlineVariant)),
              child: InteractiveViewer(
                  minScale: 1,
                  maxScale: 5,
                  child: Image.memory(base64Decode(_preview!['image_base64']),
                      fit: BoxFit.contain))),
          const SizedBox(height: 8),
          Text(
              'Máy đang đọc: ${(_preview!["detected"] as String).isEmpty ? "Bỏ trống" : _preview!["detected"]}'),
          if (_preview!['geometry']['aligned'] != true)
            const Padding(
                padding: EdgeInsets.only(top: 8),
                child: Text(
                    'Lưới vòng tròn chưa khớp ảnh; chưa thể lưu mẫu. Hãy quét Live lại đủ bốn góc.',
                    style: TextStyle(color: Colors.orange))),
          const SizedBox(height: 18),
          Text('Trên phiếu thực tế tô:',
              style: Theme.of(context).textTheme.titleMedium),
          const SizedBox(height: 8),
          if (_part != 3)
            Wrap(spacing: 8, runSpacing: 8, children: [
              for (final value in _part == 1
                  ? ['A', 'B', 'C', 'D', '', '?']
                  : ['Dung', 'Sai', 'X', '', '?'])
                ChoiceChip(
                    label: Text(value == 'Dung'
                        ? 'Đúng'
                        : value == 'Sai'
                            ? 'Sai'
                            : value == 'X'
                                ? 'Cả hai ô'
                                : value.isEmpty
                                    ? 'Không tô'
                                    : value == '?'
                                        ? 'Không rõ'
                                        : value),
                    selected: _choice == value,
                    onSelected: _busy ? null : (_) => _labelChoice(value)),
            ]),
          if (_part == 3) ...[
            const Text(
                'Đọc từng cột từ trái sang phải. Bỏ qua chữ viết tay phía trên.'),
            const SizedBox(height: 12),
            DropdownButtonFormField<String>(
                initialValue: _sign,
                decoration: const InputDecoration(labelText: 'Dấu âm'),
                items: const [
                  DropdownMenuItem(
                      value: 'filled', child: Text('Có tô dấu âm')),
                  DropdownMenuItem(
                      value: 'empty', child: Text('Không tô dấu âm')),
                  DropdownMenuItem(value: 'skip', child: Text('Không rõ'))
                ],
                onChanged: _busy
                    ? null
                    : (s) => setState(() {
                          _sign = s;
                          _labels['sign'] = s!;
                          _confirmed = false;
                        })),
            const SizedBox(height: 12),
            DropdownButtonFormField<String>(
                initialValue: _comma,
                decoration: const InputDecoration(labelText: 'Dấu phẩy'),
                items: [
                  const DropdownMenuItem(
                      value: '', child: Text('Không tô dấu phẩy')),
                  for (var c = 0; c < 4; c++)
                    DropdownMenuItem(value: '$c', child: Text('Cột ${c + 1}')),
                  const DropdownMenuItem(value: '?', child: Text('Không rõ'))
                ],
                onChanged: _busy
                    ? null
                    : (s) => setState(() {
                          _comma = s;
                          _confirmed = false;
                          for (var c = 0; c < 4; c++) {
                            _labels['comma_$c'] = s == '?'
                                ? 'skip'
                                : s == '$c'
                                    ? 'filled'
                                    : 'empty';
                          }
                        })),
            const SizedBox(height: 12),
            for (var c = 0; c < 4; c++)
              Padding(
                  padding: const EdgeInsets.only(bottom: 12),
                  child: DropdownButtonFormField<String>(
                      initialValue: _digits[c],
                      decoration: InputDecoration(labelText: 'Cột số ${c + 1}'),
                      items: [
                        const DropdownMenuItem(
                            value: '', child: Text('Không tô số')),
                        for (var d = 0; d < 10; d++)
                          DropdownMenuItem(value: '$d', child: Text('$d')),
                        const DropdownMenuItem(
                            value: '?', child: Text('Nhiều ô / không rõ'))
                      ],
                      onChanged: _busy ? null : (s) => _setDigit(c, s!))),
          ],
          CheckboxListTile(
              contentPadding: EdgeInsets.zero,
              value: _confirmed,
              onChanged: ready && !_busy
                  ? (v) => setState(() => _confirmed = v!)
                  : null,
              title: const Text(
                  'Ảnh đúng câu, các vòng tròn không bị cắt; tôi đã đối chiếu từng nhãn.')),
          FilledButton.icon(
              onPressed: ready && _confirmed && !_busy ? _save : null,
              icon: const Icon(Icons.save_outlined),
              label: const Text('Lưu mẫu câu này')),
        ],
        if (_saved > 0)
          Padding(
              padding: const EdgeInsets.only(top: 18),
              child: Text(
                  'Đã lưu $_saved lượt. Anh có thể chọn câu khác hoặc quay lại.')),
        const SizedBox(height: 24),
      ]),
    );
  }
}
