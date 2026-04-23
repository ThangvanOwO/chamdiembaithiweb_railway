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

  // ─── Exam Delete ───────────────────────────────────────────────────

  Future<void> deleteExam(int examId) async {
    final response = await http.delete(
      Uri.parse('${ApiConfig.baseUrl}${ApiConfig.examDelete(examId)}'),
      headers: _headers,
    );
    if (response.statusCode != 200) {
      final data = json.decode(response.body);
      throw Exception(data['error'] ?? 'Xóa đề thi thất bại');
    }
  }

  // ─── Templates ────────────────────────────────────────────────────

  Future<List<Map<String, dynamic>>> getTemplates() async {
    final response = await http.get(
      Uri.parse('${ApiConfig.baseUrl}${ApiConfig.templates}'),
      headers: _headers,
    );
    if (response.statusCode == 200) {
      final data = json.decode(response.body);
      return List<Map<String, dynamic>>.from(data['templates'] ?? []);
    }
    throw Exception('Failed to load templates: ${response.statusCode}');
  }

  // ─── User Settings ────────────────────────────────────────────────

  Future<Map<String, dynamic>> getSettings() async {
    final response = await http.get(
      Uri.parse('${ApiConfig.baseUrl}${ApiConfig.userSettings}'),
      headers: _headers,
    );
    if (response.statusCode == 200) {
      return Map<String, dynamic>.from(json.decode(response.body));
    }
    throw Exception('Failed to load settings: ${response.statusCode}');
  }

  Future<Map<String, dynamic>> updateSettings({
    int? retentionDays,
    bool? contributeTraining,
  }) async {
    final body = <String, dynamic>{};
    if (retentionDays != null) body['temp_retention_days'] = retentionDays;
    if (contributeTraining != null) {
      body['contribute_training_data'] = contributeTraining;
    }
    final response = await http.put(
      Uri.parse('${ApiConfig.baseUrl}${ApiConfig.userSettings}'),
      headers: _headers,
      body: json.encode(body),
    );
    if (response.statusCode == 200) {
      return Map<String, dynamic>.from(json.decode(response.body));
    }
    throw Exception('Failed to update settings: ${response.statusCode} ${response.body}');
  }

  // ─── Training data (Active Learning) ──────────────────────────────

  /// Upload one clean sample. Returns true on success.
  Future<bool> uploadTrainingSample({
    required Uint8List imageBytes,
    required String fileName,
    required Map<String, String> metadata,
  }) async {
    final uri = Uri.parse('${ApiConfig.baseUrl}${ApiConfig.trainingUpload}');
    final request = http.MultipartRequest('POST', uri);
    request.headers['Authorization'] = 'Token $token';
    request.files.add(
      http.MultipartFile.fromBytes('image', imageBytes, filename: fileName),
    );
    metadata.forEach((k, v) => request.fields[k] = v);
    final streamed = await request.send();
    return streamed.statusCode == 201 || streamed.statusCode == 200;
  }

  Future<Map<String, dynamic>> getTrainingStats() async {
    final response = await http.get(
      Uri.parse('${ApiConfig.baseUrl}${ApiConfig.trainingStats}'),
      headers: _headers,
    );
    if (response.statusCode == 200) {
      return Map<String, dynamic>.from(json.decode(response.body));
    }
    if (response.statusCode == 403) {
      throw Exception('Chỉ admin mới xem được.');
    }
    throw Exception('Failed to fetch stats: ${response.statusCode}');
  }

  /// Download training ZIP to a file path. Returns file bytes.
  Future<Uint8List> downloadTrainingZip() async {
    final response = await http.get(
      Uri.parse('${ApiConfig.baseUrl}${ApiConfig.trainingDownload}'),
      headers: {'Authorization': 'Token $token'},
    );
    if (response.statusCode == 200) return response.bodyBytes;
    if (response.statusCode == 403) {
      throw Exception('Chỉ admin mới tải được.');
    }
    throw Exception('Download failed: ${response.statusCode}');
  }

  Future<Map<String, dynamic>> cleanupNow() async {
    final response = await http.post(
      Uri.parse('${ApiConfig.baseUrl}${ApiConfig.cleanupNow}'),
      headers: _headers,
    );
    if (response.statusCode == 200) {
      return Map<String, dynamic>.from(json.decode(response.body));
    }
    throw Exception('Cleanup failed: ${response.statusCode}');
  }

  // ─── Parse Excel / Image ──────────────────────────────────────────

  Future<Map<String, dynamic>> parseExcelFile(Uint8List bytes, String fileName) async {
    final uri = Uri.parse('${ApiConfig.baseUrl}${ApiConfig.parseExcel}');
    final request = http.MultipartRequest('POST', uri);
    request.headers['Authorization'] = 'Token $token';
    request.files.add(http.MultipartFile.fromBytes('file', bytes, filename: fileName));
    final streamed = await request.send();
    final body = await streamed.stream.bytesToString();
    final data = json.decode(body);
    if (streamed.statusCode == 200 && data['success'] == true) {
      return data['data'];
    }
    throw Exception(data['error'] ?? 'Lỗi phân tích file');
  }

  Future<Map<String, dynamic>> parseImageFile(Uint8List bytes, String fileName) async {
    final uri = Uri.parse('${ApiConfig.baseUrl}${ApiConfig.parseImage}');
    final request = http.MultipartRequest('POST', uri);
    request.headers['Authorization'] = 'Token $token';
    request.files.add(http.MultipartFile.fromBytes('file', bytes, filename: fileName));
    final streamed = await request.send();
    final body = await streamed.stream.bytesToString();
    final data = json.decode(body);
    if (streamed.statusCode == 200 && data['success'] == true) {
      return data['data'];
    }
    throw Exception(data['error'] ?? 'Lỗi phân tích ảnh');
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

  // ─── Admin ──────────────────────────────────────────────────────────

  Future<Map<String, dynamic>> getAdminUsers() async {
    final response = await http.get(
      Uri.parse('${ApiConfig.baseUrl}${ApiConfig.adminUsers}'),
      headers: _headers,
    );
    if (response.statusCode == 200) {
      return Map<String, dynamic>.from(json.decode(response.body));
    }
    if (response.statusCode == 403) {
      throw Exception('Chỉ admin mới xem được.');
    }
    throw Exception('Failed to load users: ${response.statusCode}');
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
