/// Slots that must be confirmed before an imported answer key can be saved.
List<String> missingImportedAnswers(Map<String, dynamic> data) {
  final number = RegExp(r'^-?\d+(?:\.\d+)?$');
  final p1Count = (data['part1Count'] as num?)?.toInt() ?? 0;
  final p2Count = (data['part2Count'] as num?)?.toInt() ?? 0;
  final p3Count = (data['part3Count'] as num?)?.toInt() ?? 0;
  final variants = data['variants'] as List? ?? [];
  final missing = <String>[];
  if (variants.isEmpty) return ['Mã đề'];

  for (final entry in variants) {
    final variant = entry as Map;
    final prefix = variants.length > 1 ? 'Mã ${variant['code']}: ' : '';
    final p1 = variant['p1'] as Map? ?? {};
    final p2 = variant['p2'] as Map? ?? {};
    final p3 = variant['p3'] as Map? ?? {};
    for (var q = 1; q <= p1Count; q++) {
      if (!const ['A', 'B', 'C', 'D'].contains('${p1['$q']}'.toUpperCase())) {
        missing.add('${prefix}Phần I câu $q');
      }
    }
    for (var q = 1; q <= p2Count; q++) {
      final options = p2['$q'] as Map? ?? {};
      for (final option in const ['a', 'b', 'c', 'd']) {
        if (!const ['Đ', 'S'].contains('${options[option]}')) {
          missing.add('${prefix}Phần II câu $q$option');
        }
      }
    }
    for (var q = 1; q <= p3Count; q++) {
      final value = '${p3['$q'] ?? ''}'.trim();
      if (!number.hasMatch(value)) {
        missing.add('${prefix}Phần III câu $q');
      }
    }
  }
  return missing;
}
