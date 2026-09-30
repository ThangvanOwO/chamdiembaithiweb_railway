import 'dart:convert';
import 'package:http/http.dart' as http;
import 'package:http_parser/http_parser.dart';
import '../config/api_config.dart';
import 'live_capture.dart';

/// Answer-key import only. Preserve the measured JPEG/corners as one unit.
Future<Map<String, dynamic>> importExamCapture({
  required String token,
  required LiveCapture capture,
  http.Client? client,
}) async {
  final request = http.MultipartRequest(
      'POST', Uri.parse('${ApiConfig.baseUrl}${ApiConfig.parseImage}'));
  request.headers['Authorization'] = 'Token $token';
  request.fields.addAll({
    'capture_pipeline': 'exam_import_capture_v1',
    'corners': jsonEncode(capture.corners),
    'capture_width': '${capture.width}',
    'capture_height': '${capture.height}',
  });
  request.files.add(http.MultipartFile.fromBytes('file', capture.bytes,
      filename: 'answer_sheet.jpg', contentType: MediaType('image', 'jpeg')));
  final connection = client ?? http.Client();
  try {
    final streamed = await connection.send(request).timeout(const Duration(seconds: 150));
    final response = await http.Response.fromStream(streamed).timeout(const Duration(seconds: 150));
    final data = jsonDecode(utf8.decode(response.bodyBytes)) as Map<String, dynamic>;
    if (response.statusCode != 200 || data['success'] != true) {
      throw Exception(data['error'] ?? 'Không thể đọc phiếu đáp án.');
    }
    return Map<String, dynamic>.from(data['data']);
  } finally {
    if (client == null) connection.close();
  }
}
