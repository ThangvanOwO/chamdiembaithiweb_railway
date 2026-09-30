import 'dart:io';
import 'package:flutter/material.dart';
import 'package:path_provider/path_provider.dart';
import 'package:provider/provider.dart';
import '../config/api_config.dart';
import '../services/api_service.dart';
import '../services/auth_service.dart';
import '../widgets/academic_ui.dart';

class AdminTrainingScreen extends StatefulWidget {
  const AdminTrainingScreen({super.key});
  @override
  State<AdminTrainingScreen> createState() => _AdminTrainingScreenState();
}

class _AdminTrainingScreenState extends State<AdminTrainingScreen> {
  Map<String, dynamic>? _data;
  String _status = 'pending';
  int _page = 1;
  bool _busy = false;
  String? _error;
  final Set<int> _loadedImages = {};
  ApiService get _api => ApiService(token: context.read<AuthService>().token!);
  static const _titles = {
    'pending': 'Chờ duyệt',
    'approved': 'Đã duyệt',
    'rejected': 'Đã loại'
  };

  @override
  void initState() {
    super.initState();
    _load();
  }

  Future<void> _load() async {
    if (context.read<AuthService>().token == null) return;
    setState(() {
      _busy = true;
      _error = null;
    });
    try {
      final data =
          await _api.getTrainingCorrections(status: _status, page: _page);
      if (mounted) {
        setState(() {
          _data = data;
          _loadedImages.clear();
        });
      }
    } catch (e) {
      if (mounted) setState(() => _error = '$e');
    } finally {
      if (mounted) setState(() => _busy = false);
    }
  }

  Future<void> _review(Map<String, dynamic> sample, String status) async {
    final agree = await showDialog<bool>(
        context: context,
        builder: (ctx) => AlertDialog(
                title: Text(status == 'approved'
                    ? 'Xác nhận nhãn đã kiểm tra'
                    : 'Loại mẫu này'),
                content: const Text(
                    'Anh đã đối chiếu ảnh và từng nhãn vòng tròn? Ảnh cắt lệch hoặc nhãn sai cần được loại.'),
                actions: [
                  TextButton(
                      onPressed: () => Navigator.pop(ctx, false),
                      child: const Text('Quay lại')),
                  FilledButton(
                      onPressed: () => Navigator.pop(ctx, true),
                      child: const Text('Xác nhận'))
                ]));
    if (agree != true || !mounted) return;
    setState(() => _busy = true);
    try {
      await _api.reviewTrainingQuestion(
          sample['id'], status, sample['revision']);
      if (mounted) await _load();
    } catch (e) {
      if (mounted) {
        setState(() {
          _error = '$e';
          _busy = false;
        });
      }
    }
  }

  Future<void> _download({bool unverified = false}) async {
    setState(() {
      _busy = true;
      _error = null;
    });
    try {
      final bytes = unverified
          ? await _api.downloadTrainingZip()
          : await _api.downloadReviewedTraining();
      final directory =
          Platform.isAndroid ? await getExternalStorageDirectory() : null;
      final base = directory ?? await getApplicationDocumentsDirectory();
      final file = File(
          '${base.path}/training_${unverified ? "unverified" : "reviewed"}_${DateTime.now().millisecondsSinceEpoch}.zip');
      await file.writeAsBytes(bytes, flush: true);
      if (mounted) {
        ScaffoldMessenger.of(context)
            .showSnackBar(SnackBar(content: Text('Đã lưu: ${file.path}')));
      }
    } catch (e) {
      if (mounted) setState(() => _error = '$e');
    } finally {
      if (mounted) setState(() => _busy = false);
    }
  }

  @override
  Widget build(BuildContext context) {
    final counts = (_data?['counts'] as Map?) ?? {};
    final total = counts.values.fold<int>(0, (sum, v) => sum + (v as int));
    final samples = (_data?['samples'] as List?) ?? [];
    return Scaffold(
      appBar: AppBar(title: const Text('Dữ liệu huấn luyện'), actions: [
        IconButton(
            onPressed: _busy ? null : _load, icon: const Icon(Icons.refresh))
      ]),
      body: ListView(padding: const EdgeInsets.all(20), children: [
        const AcademicNotice(
            title: 'Nhãn do admin xác nhận',
            message:
                'Training AI lưu ảnh câu và dấu tô thực tế. Mẫu đã duyệt mới được xuất cho huấn luyện/kiểm thử; '
                'không tự thay mô hình đang chấm bài.'),
        const SizedBox(height: 18),
        Row(children: [
          for (final status in _titles.keys)
            Expanded(
                child: Card(
                    child: Padding(
                        padding: const EdgeInsets.all(12),
                        child: Column(children: [
                          Text('${counts[status] ?? 0}',
                              style: Theme.of(context).textTheme.headlineSmall),
                          Text(_titles[status]!,
                              style: Theme.of(context).textTheme.bodySmall),
                          const SizedBox(height: 8),
                          LinearProgressIndicator(
                              value: total == 0
                                  ? 0
                                  : (counts[status] ?? 0) / total,
                              color: status == 'approved'
                                  ? Colors.teal
                                  : status == 'rejected'
                                      ? Colors.redAccent
                                      : Colors.orange),
                        ]))))
        ]),
        const SizedBox(height: 18),
        FilledButton.icon(
            onPressed: _busy || (counts['approved'] ?? 0) == 0
                ? null
                : () => _download(),
            icon: const Icon(Icons.download),
            label: const Text('Tải mẫu đã duyệt (.zip)')),
        const Padding(
            padding: EdgeInsets.symmetric(vertical: 10),
            child: Text(
                'Trên máy Windows, chạy scripts/sync_training.ps1 để đồng bộ về thư mục Traing.',
                style: TextStyle(fontSize: 12))),
        Wrap(spacing: 8, children: [
          for (final s in _titles.keys)
            ChoiceChip(
                label: Text(_titles[s]!),
                selected: _status == s,
                onSelected: _busy
                    ? null
                    : (_) {
                        setState(() {
                          _status = s;
                          _page = 1;
                        });
                        _load();
                      })
        ]),
        if (_busy)
          const Padding(
              padding: EdgeInsets.all(16),
              child: Center(child: CircularProgressIndicator())),
        if (_error != null)
          Padding(
              padding: const EdgeInsets.all(12),
              child: Text(_error!, style: const TextStyle(color: Colors.red))),
        if (!_busy && samples.isEmpty)
          const Padding(
              padding: EdgeInsets.all(24),
              child: Text(
                  'Chưa có mẫu ở nhóm này. Sau khi quét, chọn “Training AI” trên màn hình kết quả.')),
        for (final raw in samples) _sampleCard(Map<String, dynamic>.from(raw)),
        Row(mainAxisAlignment: MainAxisAlignment.spaceBetween, children: [
          TextButton(
              onPressed: _busy || _page == 1
                  ? null
                  : () {
                      setState(() => _page--);
                      _load();
                    },
              child: const Text('Trang trước')),
          Text('Trang $_page'),
          TextButton(
              onPressed: _busy || _page * 20 >= (_data?['count'] ?? 0)
                  ? null
                  : () {
                      setState(() => _page++);
                      _load();
                    },
              child: const Text('Trang sau'))
        ]),
        const Divider(height: 28),
        Text(
            'Ảnh tự động cũ: ${_data?["unverified"] ?? 0} mẫu chưa được xác minh'),
        const Text(
            'Nhãn cũ là kết quả máy tự đọc; không sử dụng như đáp án chuẩn.',
            style: TextStyle(fontSize: 12)),
        TextButton.icon(
            onPressed: _busy ? null : () => _download(unverified: true),
            icon: const Icon(Icons.archive_outlined),
            label: const Text('Tải kho ảnh cũ để kiểm tra')),
      ]),
    );
  }

  Widget _sampleCard(Map<String, dynamic> sample) {
    final labels = (sample['labels'] as Map)
        .entries
        .map((e) =>
            '${e.key}: ${e.value == "filled" ? "Tô" : e.value == "empty" ? "Trống" : "Bỏ qua"}')
        .join(' · ');
    final token = context.read<AuthService>().token!;
    return Card(
        margin: const EdgeInsets.symmetric(vertical: 8),
        child: Padding(
            padding: const EdgeInsets.all(16),
            child:
                Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
              Text(
                  'Phần ${sample["part"]} · Câu ${sample["question"]}${sample["subquestion"]} · #${sample["id"]}',
                  style: Theme.of(context).textTheme.titleMedium),
              Text('Phiếu ${sample["template_code"]}'),
              const SizedBox(height: 12),
              SizedBox(
                  height: sample['part'] == 3 ? 260 : 120,
                  width: double.infinity,
                  child: InteractiveViewer(
                      maxScale: 5,
                      child: Image.network(
                          '${ApiConfig.baseUrl}${sample["image_url"]}',
                          headers: {'Authorization': 'Token $token'},
                          fit: BoxFit.contain,
                          frameBuilder: (context, child, frame, synchronous) {
                            if (frame != null &&
                                !_loadedImages.contains(sample['id'])) {
                              WidgetsBinding.instance.addPostFrameCallback((_) {
                                if (mounted) {
                                  setState(
                                      () => _loadedImages.add(sample['id']));
                                }
                              });
                            }
                            return child;
                          },
                          errorBuilder: (_, error, stack) => const Center(
                              child: Text(
                                  'Không tải được ảnh; chưa thể duyệt.'))))),
              const SizedBox(height: 12),
              Text(
                  'Máy đọc: ${sample["detected"] == "" ? "Trống" : sample["detected"]} → '
                  'Nhãn xác nhận: ${sample["answer"] == "" ? "Trống" : sample["answer"]}'),
              ExpansionTile(
                  tilePadding: EdgeInsets.zero,
                  title: const Text('Đối chiếu từng vòng tròn'),
                  children: [Text(labels)]),
              Row(children: [
                TextButton.icon(
                    onPressed: _busy ? null : () => _review(sample, 'rejected'),
                    icon: const Icon(Icons.close),
                    label: const Text('Loại')),
                const Spacer(),
                FilledButton.icon(
                    onPressed: _busy ||
                            !_loadedImages.contains(sample['id']) ||
                            sample['status'] == 'approved'
                        ? null
                        : () => _review(sample, 'approved'),
                    icon: const Icon(Icons.check),
                    label: const Text('Duyệt nhãn')),
              ]),
            ])));
  }
}
