import 'dart:convert';
import 'package:http/http.dart' as http;
import 'package:http_parser/http_parser.dart';
import '../config/api_config.dart';
import '../models/grade_result.dart';
import 'live_capture.dart';

/// Live-only transport: never resize/re-encode after corners have been measured.
/// Static Upload continues to use ApiService.gradeImage unchanged.
Future<GradeResult> gradeLiveCapture({
  required String token,
  required LiveCapture capture,
  int? examId,
  String? templateCode,
  bool save = true,
  http.Client? client,
}) async {
  final request = http.MultipartRequest(
      'POST', Uri.parse('${ApiConfig.baseUrl}${ApiConfig.grade}'));
  request.headers['Authorization'] = 'Token $token';
  if (const bool.fromEnvironment('LIVE_BACKGROUND_TRIAL')) {
    request.headers['X-GradeFlow-Background-Trial'] = 'box5';
  }
  request.fields.addAll({
    'corners': jsonEncode(capture.corners),
    'capture_pipeline': 'live_capture_v3',
    'save': save ? 'true' : 'false',
    // The corners are verified on capture; skip the legacy alternative-quad
    // search so the server cannot replace them with a different detection.
    'fast': '1',
  });
  if (examId != null) request.fields['exam_id'] = '$examId';
  if (templateCode != null && templateCode.isNotEmpty) {
    request.fields['template_code'] = templateCode;
  }
  request.files.add(http.MultipartFile.fromBytes('image', capture.bytes,
      filename: 'live.jpg', contentType: MediaType('image', 'jpeg')));
  final connection = client ?? http.Client();
  try {
    final streamed =
        await connection.send(request).timeout(const Duration(seconds: 90));
    final response = await http.Response.fromStream(streamed)
        .timeout(const Duration(seconds: 90));
    if (response.statusCode != 200) {
      return GradeResult(
          success: false, error: 'Lỗi chấm Live (${response.statusCode}).');
    }
    return GradeResult.fromJson(jsonDecode(response.body));
  } finally {
    if (client == null) connection.close();
  }
}
