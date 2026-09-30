import 'package:flutter_test/flutter_test.dart';
import 'package:gradeflow_app/services/answer_key_completeness.dart';

void main() {
  test('camera import reports every missing answer slot', () {
    final data = <String, dynamic>{
      'part1Count': 2, 'part2Count': 1, 'part3Count': 3,
      'variants': [
        {'code': '676', 'p1': {'1': 'A'},
         'p2': {'1': {'a': 'Đ', 'b': 'S', 'd': 'Đ'}},
         'p3': {'1': '', '2': '1599', '3': '-0'}}
      ],
    };
    expect(missingImportedAnswers(data), [
      'Phần I câu 2', 'Phần II câu 1c', 'Phần III câu 1',
    ]);
  });

  test('complete imported answer key can proceed', () {
    final data = <String, dynamic>{
      'part1Count': 1, 'part2Count': 1, 'part3Count': 1,
      'variants': [
        {'code': '676', 'p1': {'1': 'C'},
         'p2': {'1': {'a': 'Đ', 'b': 'S', 'c': 'S', 'd': 'Đ'}},
         'p3': {'1': '-0.5'}}
      ],
    };
    expect(missingImportedAnswers(data), isEmpty);
  });

  test('manual Part III correction must be a confirmed number', () {
    final data = <String, dynamic>{
      'part1Count': 0, 'part2Count': 0, 'part3Count': 1,
      'variants': [{'code': '676', 'p1': {}, 'p2': {}, 'p3': {'1': ''}}],
    };
    expect(missingImportedAnswers(data), ['Phần III câu 1']);
    (data['variants'] as List).first['p3']['1'] = '-0.2';
    expect(missingImportedAnswers(data), isEmpty);
    (data['variants'] as List).first['p3']['1'] = '-';
    expect(missingImportedAnswers(data), ['Phần III câu 1']);
  });
}
