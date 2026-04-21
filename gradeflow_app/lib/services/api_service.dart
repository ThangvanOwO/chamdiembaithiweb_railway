import 'dart:convert';
import 'dart:typed_data';
import 'package:http/http.dart' as http;
import 'package:http_parser/http_parser.dart';

import '../config/api_config.dart';
import '../models/exam.dart';
import '../models/submission.dart';
import '../models/grade_result.dart';

class ApiService {
  final String token;

  ApiService({required this.token});

  Map<String, String> get _headers => {
        'Authorization': 'Token $token',
        'Content-Type': 'application/json',
      };

  // ─── Dashboard ───────────────────────────────────────────────────────

  Future<Map<String, dynamic>> getDashboard() async {
    final response = await http.get(
      Uri.parse('${ApiConfig.baseUrl}${ApiConfig.dashboard}'),
      headers: _headers,
    );
    if (response.statusCode == 200) {
      return json.decode(response.body);
    }
    throw Exception('Failed to load dashboard: ${response.statusCode}');
  }

  // ─── Exams ───────────────────────────────────────────────────────────

  Future<List<Exam>> getExams() async {
    final response = await http.get(
      Uri.parse('${ApiConfig.baseUrl}${ApiConfig.exams}'),
      headers: _headers,
    );
    if (response.statusCode == 200) {
      final data = json.decode(response.body);
      return (data['exams'] as List).map((e) => Exam.fromJson(e)).toList();
    }
    throw Exception('Failed to load exams: ${response.statusCode}');
  }

  Future<Map<String, dynamic>> getExamDetail(int examId) async {
    final response = await http.get(
      Uri.parse('${ApiConfig.baseUrl}${ApiConfig.examDetail(examId)}'),
      headers: _headers,
    );
    if (response.statusCode == 200) {
      return json.decode(response.body);
    }
    throw Exception('Failed to load exam detail: ${response.statusCode}');
  }

  // ─── Exam Create ───────────────────────────────────────────────────

  Future<Map<String, dynamic>> createExam({
    required String title,
    String subject = '',
    String templateCode = '',
    List<int> parts = const [24, 4, 0],
    List<Map<String, dynamic>> variants = const [],
  }) async {
    final response = await http.post(
      Uri.parse('${ApiConfig.baseUrl}${ApiConfig.exams}'),
      headers: _headers,
      body: json.encode({
        'title': title,
        'subject': subject,
        'template_code': templateCode,
        'parts': parts,
        'variants': variants,
      }),
    );
    if (response.statusCode == 201 || response.statusCode == 200) {
      return json.decode(response.body);
    }
    final data = json.decode(response.body);
    throw Exception(data['error'] ?? 'Tạo đề thi thất bại: ${response.statusCode}');
  }

  // ─── Grading (Core) ─────────────────────────────────────────────────

  /// Send image to API for grading.
  /// [imageBytes] — image data as bytes (works on all platforms).
  /// [fileName] — original filename for MIME type detection.
  /// [examId] — optional exam ID.
  /// [templateCode] — optional template code.
  Future<GradeResult> gradeImage({
    required Uint8List imageBytes,
    String fileName = 'scan.jpg',
    int? examId,
    String? templateCode,
    bool save = true,
  }) async {
    final uri = Uri.parse('${ApiConfig.baseUrl}${ApiConfig.grade}');
    final request = http.MultipartRequest('POST', uri);

    request.headers['Authorization'] = 'Token $token';

    // Attach image as bytes (works on web + mobile)
    final ext = fileName.split('.').last.toLowerCase();
    final mimeType = ext == 'png' ? 'image/png' : 'image/jpeg';
    request.files.add(http.MultipartFile.fromBytes(
      'image',
      imageBytes,
      filename: fileName,
      contentType: MediaType.parse(mimeType),
    ));

    if (examId != null) {
      request.fields['exam_id'] = examId.toString();
    }
    if (templateCode != null && templateCode.isNotEmpty) {
      request.fields['template_code'] = templateCode;
    }
    request.fields['save'] = save ? 'true' : 'false';

    final streamedResponse = await request.send();
    final response = await http.Response.fromStream(streamedResponse);

    if (response.statusCode == 200) {
      final data = json.decode(response.body);
      return GradeResult.fromJson(data);
    }

    // Try to parse error message
    try {
      final data = json.decode(response.body);
      return GradeResult(
        success: false,
        error: data['error'] ?? 'Lỗi server: ${response.statusCode}',
      );
    } catch (_) {
      return GradeResult(
        success: false,
        error: 'Lỗi server: ${response.statusCode}',
      );
    }
  }

  // ─── Submissions ─────────────────────────────────────────────────────

  Future<List<Submission>> getSubmissions({int? examId, int limit = 20}) async {
    var url = '${ApiConfig.baseUrl}${ApiConfig.submissions}?limit=$limit';
    if (examId != null) url += '&exam_id=$examId';

    final response = await http.get(Uri.parse(url), headers: _headers);
    if (response.statusCode == 200) {
      final data = json.decode(response.body);
      return (data['submissions'] as List)
          .map((s) => Submission.fromJson(s))
          .toList();
    }
    throw Exception('Failed to load submissions: ${response.statusCode}');
  }

  Future<Map<String, dynamic>> getSubmissionDetail(int id) async {
    final response = await http.get(
      Uri.parse('${ApiConfig.baseUrl}${ApiConfig.submissionDetail(id)}'),
      headers: _headers,
    );
    if (response.statusCode == 200) {
      return json.decode(response.body);
    }
    throw Exception('Failed to load submission: ${response.statusCode}');
  }
}
