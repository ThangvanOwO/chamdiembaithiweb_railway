import 'dart:convert';
import 'dart:typed_data';
import 'package:flutter/material.dart';
import '../models/grade_result.dart';
import '../services/api_service.dart';
import '../widgets/academic_ui.dart';
import '../widgets/training_label_editor.dart';

class TrainingSheetScreen extends StatefulWidget {
  final Uint8List imageBytes;
  final GradeResult result;
  final String templateCode;
  final List<List<double>>? corners;
  final ApiService api;
  const TrainingSheetScreen(
      {super.key,
      required this.imageBytes,
      required this.result,
      required this.templateCode,
      required this.api,
      this.corners});
  @override
  State<TrainingSheetScreen> createState() => _TrainingSheetScreenState();
}

class _TrainingSheetScreenState extends State<TrainingSheetScreen> {
  List<Map<String, dynamic>> _samples = [];
  final Set<int> _selected = {}, _reviewed = {};
  bool _busy = true, _confirmed = false, _onlyReview = false;
  String? _error;
  @override
  void initState() {
    super.initState();
    _load();
  }

  Future<void> _load() async {
    setState(() {
      _busy = true;
      _error = null;
    });
    try {
      final data = await widget.api.previewTrainingSheet(
          imageBytes: widget.imageBytes,
          templateCode: widget.templateCode,
          result: widget.result,
          corners: widget.corners);
      if (!mounted) return;
      setState(() {
        _samples = [
          for (final raw in data['samples'])
            {
              ...Map<String, dynamic>.from(raw),
              'labels': Map<String, String>.from(raw['candidate_labels'])
            }
        ];
        _selected.clear();
        _reviewed.clear();
        _confirmed = false;
        for (var i = 0; i < _samples.length; i++) {
          if (_samples[i]['geometry']['aligned'] == true) _selected.add(i);
        }
      });
    } catch (e) {
      if (mounted) setState(() => _error = '$e');
    } finally {
      if (mounted) setState(() => _busy = false);
    }
  }

  int get _remaining => _selected
      .where(
          (i) => _samples[i]['needs_review'] == true && !_reviewed.contains(i))
      .length;
  String _title(Map<String, dynamic> s) =>
      'Phần ${s['part']} · Câu ${s['question']}${s['subquestion']}';

  Future<void> _edit(int i) async {
    final s = _samples[i];
    final labels = await editTrainingLabels(context,
        title: _title(s),
        image: base64Decode(s['image_base64']),
        cells: s['cells'],
        geometry: Map<String, dynamic>.from(s['geometry']),
        labels: Map<String, String>.from(s['labels']));
    if (labels != null && mounted) {
      setState(() {
        s['labels'] = labels;
        _reviewed.add(i);
        _confirmed = false;
      });
    }
  }

  Future<void> _save() async {
    setState(() {
      _busy = true;
      _error = null;
    });
    try {
      final response = await widget.api.saveTrainingSheet(widget.imageBytes, [
        for (final i in _selected)
          {
            'preview_token': _samples[i]['preview_token'],
            'labels': _samples[i]['labels'],
            'review_confirmed': _reviewed.contains(i)
          }
      ]);
      if (!mounted) return;
      ScaffoldMessenger.of(context).showSnackBar(SnackBar(
          content: Text(
              'Đã lấy ${response['count']} vùng câu đã duyệt; ${response['duplicates']} mẫu trùng.')));
      Navigator.pop(context, true);
    } catch (e) {
      if (mounted) setState(() => _error = '$e');
    } finally {
      if (mounted) setState(() => _busy = false);
    }
  }

  @override
  Widget build(BuildContext context) => Scaffold(
        appBar: AppBar(title: const Text('Training AI · Toàn bộ phiếu')),
        body: ListView(padding: const EdgeInsets.all(20), children: [
          const AcademicNotice(
              title: 'Đối chiếu rồi lấy toàn bộ',
              message:
                  'Nhãn điền sẵn là gợi ý từ dấu tô. Anh kiểm tra từng vùng ảnh; vùng vàng cần xác nhận riêng. '
                  'Mẫu được duyệt sẽ sẵn sàng xuất dữ liệu, chưa thay mô hình đang chấm.'),
          const SizedBox(height: 12),
          if (_busy) const Center(child: CircularProgressIndicator()),
          if (_error != null)
            Text(_error!, style: const TextStyle(color: Colors.red)),
          if (!_busy && _samples.isEmpty)
            FilledButton(onPressed: _load, child: const Text('Tải lại phiếu')),
          if (_samples.isNotEmpty) ...[
            Text(
                '${_selected.length}/${_samples.length} vùng được chọn · $_remaining vùng cần kiểm tra',
                style: Theme.of(context).textTheme.titleMedium),
            if (_samples.length != _selected.length)
              const Text(
                  'Vùng bỏ chọn sẽ không được lấy. Vùng chưa khớp lưới cần quét lại.'),
            SwitchListTile(
                title: const Text('Chỉ xem vùng cần kiểm tra'),
                value: _onlyReview,
                onChanged:
                    _busy ? null : (v) => setState(() => _onlyReview = v)),
            for (var i = 0; i < _samples.length; i++)
              if (!_onlyReview ||
                  (_samples[i]['needs_review'] == true &&
                      !_reviewed.contains(i)))
                _card(i),
            CheckboxListTile(
                value: _confirmed,
                onChanged: !_busy && _remaining == 0 && _selected.isNotEmpty
                    ? (v) => setState(() => _confirmed = v!)
                    : null,
                title: const Text(
                    'Tôi đã xem các vùng được chọn và xác nhận toàn bộ dấu tô đúng với ảnh.')),
            FilledButton.icon(
                onPressed: !_busy &&
                        _confirmed &&
                        _remaining == 0 &&
                        _selected.isNotEmpty
                    ? _save
                    : null,
                icon: const Icon(Icons.library_add_check),
                label: Text('Xác nhận & lấy ${_selected.length} vùng câu')),
          ],
        ]),
      );

  Widget _card(int i) {
    final s = _samples[i];
    final review = s['needs_review'] == true && !_reviewed.contains(i);
    return Card(
        color: review ? Colors.orange.shade50 : null,
        child: Padding(
          padding: const EdgeInsets.all(12),
          child:
              Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
            CheckboxListTile(
                contentPadding: EdgeInsets.zero,
                title: Text(_title(s)),
                subtitle: Text(_reviewed.contains(i)
                    ? 'Đã kiểm tra thủ công'
                    : review
                        ? 'Cần kiểm tra dấu tô'
                        : 'Nhãn điền sẵn · cần đối chiếu'),
                value: _selected.contains(i),
                onChanged: _busy || s['geometry']['aligned'] != true
                    ? null
                    : (v) => setState(() {
                          v! ? _selected.add(i) : _selected.remove(i);
                          _confirmed = false;
                        })),
            SizedBox(
                height: s['part'] == 3 ? 260 : 95,
                width: double.infinity,
                child: InteractiveViewer(
                    maxScale: 5,
                    child: Image.memory(base64Decode(s['image_base64']),
                        fit: BoxFit.contain))),
            const SizedBox(height: 8),
            Text(
                'Máy đọc: ${s['detected'] == '' ? 'Trống / chưa rõ' : s['detected']}'),
            Wrap(spacing: 4, children: [
              for (final e in (s['labels'] as Map<String, String>).entries)
                if (e.value != 'empty')
                  Chip(
                      label: Text(
                          '${TrainingLabelEditor.cellTitle(e.key)}${e.value == 'skip' ? ' · ?' : ''}'))
            ]),
            TextButton.icon(
                onPressed: _busy ? null : () => _edit(i),
                icon: const Icon(Icons.edit_outlined),
                label: const Text('Chọn vòng tròn thực tế / xác nhận')),
          ]),
        ));
  }
}
