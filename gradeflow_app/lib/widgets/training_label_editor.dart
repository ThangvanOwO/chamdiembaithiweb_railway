import 'dart:typed_data';
import 'package:flutter/material.dart';

/// Labels are independent per circle: multiple marks and blanks stay truthful.
class TrainingLabelEditor extends StatelessWidget {
  final Uint8List image;
  final List<dynamic> cells;
  final Map<String, dynamic> geometry;
  final Map<String, String> labels;
  final ValueChanged<Map<String, String>> onChanged;
  const TrainingLabelEditor(
      {super.key,
      required this.image,
      required this.cells,
      required this.geometry,
      required this.labels,
      required this.onChanged});

  static String cellTitle(String id) {
    if (id == 'Dung') return 'Đúng';
    if (id == 'Sai') return 'Sai';
    if (id == 'sign') return 'Dấu âm';
    final parts = id.split('_');
    if (parts.first == 'comma') return 'Phẩy cột ${int.parse(parts[1]) + 1}';
    if (parts.first == 'digit') {
      return 'Cột ${int.parse(parts[1]) + 1} · ${parts[2]}';
    }
    return id;
  }

  @override
  Widget build(BuildContext context) =>
      Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
        const Text(
            'Chạm ô để đổi đã tô/chưa tô. Nhấn giữ để bỏ qua ô không rõ. Có thể chọn nhiều ô.'),
        const SizedBox(height: 12),
        InteractiveViewer(
            maxScale: 5,
            child: LayoutBuilder(builder: (context, constraints) {
              final width = constraints.maxWidth;
              final iw = (geometry['width'] as num).toDouble();
              final ih = (geometry['height'] as num).toDouble();
              final scale = width / iw;
              final size =
                  ((geometry['radius'] as num).toDouble() * 2.3 * scale)
                      .clamp(24.0, 56.0);
              return SizedBox(
                  width: width,
                  height: ih * scale,
                  child: Stack(children: [
                    Positioned.fill(
                        child: Image.memory(image, fit: BoxFit.fill)),
                    for (final cell in cells)
                      Positioned(
                          left:
                              (cell['x'] as num).toDouble() * scale - size / 2,
                          top: (cell['y'] as num).toDouble() * scale - size / 2,
                          width: size,
                          height: size,
                          child: Semantics(
                              button: true,
                              label:
                                  '${cellTitle(cell['id'])}: ${labels[cell['id']] ?? 'skip'}',
                              child: Tooltip(
                                  message: cellTitle(cell['id']),
                                  child: GestureDetector(
                                    onTap: () => onChanged({
                                      ...labels,
                                      cell['id']: labels[cell['id']] == 'filled'
                                          ? 'empty'
                                          : 'filled'
                                    }),
                                    onLongPress: () => onChanged(
                                        {...labels, cell['id']: 'skip'}),
                                    child: Container(
                                        decoration: BoxDecoration(
                                            shape: BoxShape.circle,
                                            border: Border.all(
                                                width: 2.5,
                                                color: labels[cell['id']] ==
                                                        'filled'
                                                    ? Colors.teal
                                                    : labels[cell['id']] ==
                                                            'empty'
                                                        ? Colors.blueGrey
                                                        : Colors.orange),
                                            color:
                                                labels[cell['id']] == 'filled'
                                                    ? Colors.teal
                                                        .withValues(alpha: .22)
                                                    : Colors.transparent)),
                                  )))),
                  ]));
            })),
        const SizedBox(height: 12),
        const Text('Xanh: đã tô · Xám: chưa tô · Vàng: bỏ qua'),
        const SizedBox(height: 8),
        Wrap(spacing: 6, runSpacing: 4, children: [
          for (final cell in cells)
            FilterChip(
                label: Text(cellTitle(cell['id'])),
                selected: labels[cell['id']] == 'filled',
                avatar: labels[cell['id']] == 'skip'
                    ? const Icon(Icons.help_outline, size: 16)
                    : null,
                onSelected: (_) => onChanged({
                      ...labels,
                      cell['id']:
                          labels[cell['id']] == 'filled' ? 'empty' : 'filled'
                    })),
        ]),
      ]);
}

Future<Map<String, String>?> editTrainingLabels(
  BuildContext context, {
  required String title,
  required Uint8List image,
  required List<dynamic> cells,
  required Map<String, dynamic> geometry,
  required Map<String, String> labels,
}) async {
  var edited = Map<String, String>.from(labels);
  var confirmed = false;
  return showDialog<Map<String, String>>(
      context: context,
      builder: (ctx) => StatefulBuilder(
            builder: (ctx, setState) => AlertDialog(
              title: Text(title),
              content: SizedBox(
                  width: 480,
                  child: SingleChildScrollView(
                      child: Column(mainAxisSize: MainAxisSize.min, children: [
                    TrainingLabelEditor(
                        image: image,
                        cells: cells,
                        geometry: geometry,
                        labels: edited,
                        onChanged: (v) => setState(() {
                              edited = v;
                              confirmed = false;
                            })),
                    CheckboxListTile(
                        value: confirmed,
                        onChanged: geometry['aligned'] == true
                            ? (v) => setState(() => confirmed = v!)
                            : null,
                        title: const Text(
                            'Tôi đã đối chiếu ảnh và từng vòng tròn thực tế.')),
                    if (geometry['aligned'] != true)
                      const Text('Ảnh chưa khớp lưới; hãy quét lại.'),
                  ]))),
              actions: [
                TextButton(
                    onPressed: () => Navigator.pop(ctx),
                    child: const Text('Hủy')),
                FilledButton(
                    onPressed:
                        confirmed ? () => Navigator.pop(ctx, edited) : null,
                    child: const Text('Xác nhận nhãn'))
              ],
            ),
          ));
}
