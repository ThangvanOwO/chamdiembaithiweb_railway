import 'dart:convert';
import 'dart:typed_data';
import 'package:http/http.dart' as http;
import 'package:http_parser/http_parser.dart';
import 'package:image/image.dart' as img;

import '../config/api_config.dart';
import '../models/exam.dart';
import '../models/submission.dart';
import '../models/grade_result.dart';

class ApiService {
  final String token;

  ApiService({required this.token});

  static const _corrections = '/api/v1/training/corrections/';

  Map<String, dynamic> _trainingResponse(http.Response response) {
    final data =
        jsonDecode(utf8.decode(response.bodyBytes)) as Map<String, dynamic>;
    if (response.statusCode >= 200 && response.statusCode < 300) return data;
    throw Exception(
        data['error'] ?? data['detail'] ?? 'Không tải được dữ liệu training.');
  }

  Future<Map<String, dynamic>> previewTrainingQuestion(
      {required Uint8List imageBytes,
      required String templateCode,
      required int part,
      required int question,
      String subquestion = '',
      List<List<double>>? corners}) async {
    final request = http.MultipartRequest(
        'POST', Uri.parse('${ApiConfig.baseUrl}${_corrections}preview/'));
    request.headers['Authorization'] = 'Token $token';
    request.fields.addAll({
      'template_code': templateCode,
      'part': '$part',
      'question': '$question',
      'subquestion': subquestion,
      if (corners != null) 'corners': jsonEncode(corners)
    });
    // Keep exact bytes: the corner coordinates belong to this image.
    request.files.add(http.MultipartFile.fromBytes('image', imageBytes,
        filename: 'source.jpg'));
    return _trainingResponse(await http.Response.fromStream(
        await request.send().timeout(const Duration(seconds: 90))));
  }

  Future<Map<String, dynamic>> saveTrainingQuestion(
          String previewToken, Map<String, String> labels) async =>
      _trainingResponse(await http.post(
          Uri.parse('${ApiConfig.baseUrl}${_corrections}save/'),
          headers: _headers,
          body: jsonEncode({
            'preview_token': previewToken,
            'labels': labels,
            'confirmed': true
          })));

  Future<Map<String, dynamic>> previewTrainingSheet(
      {required Uint8List imageBytes,
      required String templateCode,
      required GradeResult result,
      List<List<double>>? corners}) async {
    final request = http.MultipartRequest(
        'POST', Uri.parse('${ApiConfig.baseUrl}${_corrections}sheet/preview/'));
    request.headers['Authorization'] = 'Token $token';
    request.fields.addAll({
      'template_code': templateCode,
      'scan_answers': jsonEncode({
        'part1': result.part1,
        'part2': result.part2,
        'part3': result.part3
      }),
      if (corners != null) 'corners': jsonEncode(corners)
    });
    request.files.add(http.MultipartFile.fromBytes('image', imageBytes,
        filename: 'source.jpg'));
    return _trainingResponse(await http.Response.fromStream(
        await request.send().timeout(const Duration(seconds: 90))));
  }

  Future<Map<String, dynamic>> saveTrainingSheet(
      Uint8List imageBytes, List<Map<String, dynamic>> items) async {
    final request = http.MultipartRequest(
        'POST', Uri.parse('${ApiConfig.baseUrl}${_corrections}sheet/save/'));
    request.headers['Authorization'] = 'Token $token';
    request.fields.addAll(
        {'items': jsonEncode(items), 'confirmed': 'true', 'approve': 'true'});
    request.files.add(http.MultipartFile.fromBytes('image', imageBytes,
        filename: 'source.jpg'));
    return _trainingResponse(await http.Response.fromStream(
        await request.send().timeout(const Duration(seconds: 90))));
  }

  Future<void> correctTrainingQuestion(
      int id, String revision, Map<String, String> labels) async {
    _trainingResponse(await http.post(
        Uri.parse('${ApiConfig.baseUrl}$_corrections$id/correct/'),
        headers: _headers,
        body: jsonEncode(
            {'revision': revision, 'labels': labels, 'confirmed': true})));
  }

  Future<Uint8List> getTrainingImage(String path) async {
    final response = await http.get(Uri.parse('${ApiConfig.baseUrl}$path'),
        headers: _headers);
    if (response.statusCode != 200) throw Exception('Không tải được ảnh câu.');
    return response.bodyBytes;
  }

  Future<Map<String, dynamic>> getTrainingCorrections(
          {String status = 'pending', int page = 1}) async =>
      _trainingResponse(await http.get(
          Uri.parse(
              '${ApiConfig.baseUrl}$_corrections?status=$status&page=$page'),
          headers: _headers));

  Future<void> reviewTrainingQuestion(
      int id, String status, String revision) async {
    _trainingResponse(await http.post(
        Uri.parse('${ApiConfig.baseUrl}$_corrections$id/review/'),
        headers: _headers,
        body: jsonEncode(
            {'status': status, 'revision': revision, 'confirmed': true})));
  }

  Future<Uint8List> downloadReviewedTraining() async {
    final response = await http.get(
        Uri.parse('${ApiConfig.baseUrl}${_corrections}export/'),
        headers: _headers);
    if (response.statusCode != 200) {
      _trainingResponse(response);
    }
    return response.bodyBytes;
  }

  /// Compress image for upload: resize + JPEG encode.
  /// Default: 2000px wide, q90 — balances quality vs upload speed.
  /// For OMR grading, use maxWidth=2400, quality=92 to preserve bubble detail.
  static Uint8List _compressForUpload(Uint8List raw,
      {int maxWidth = 2000, int quality = 90}) {
    try {
      final decoded = img.decodeImage(raw);
      if (decoded == null) return raw;
      // Only downscale if larger than maxWidth
      final src = decoded.width > maxWidth
          ? img.copyResize(decoded, width: maxWidth)
          : decoded;
      final jpeg = img.encodeJpg(src, quality: quality);
      return Uint8List.fromList(jpeg);
    } catch (_) {
      return raw; // Fallback: send original if decode fails
    }
  }

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
    throw Exception(
        'Failed to update settings: ${response.statusCode} ${response.body}');
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

  Future<Map<String, dynamic>> parseExcelFile(
      Uint8List bytes, String fileName) async {
    final uri = Uri.parse('${ApiConfig.baseUrl}${ApiConfig.parseExcel}');
    final request = http.MultipartRequest('POST', uri);
    request.headers['Authorization'] = 'Token $token';
    request.files
        .add(http.MultipartFile.fromBytes('file', bytes, filename: fileName));
    final streamed = await request.send();
    final body = await streamed.stream.bytesToString();
    final data = json.decode(body);
    if (streamed.statusCode == 200 && data['success'] == true) {
      return data['data'];
    }
    throw Exception(data['error'] ?? 'Lỗi phân tích file');
  }

  Future<Map<String, dynamic>> parseImageFile(
      Uint8List bytes, String fileName) async {
    final uri = Uri.parse('${ApiConfig.baseUrl}${ApiConfig.parseImage}');
    final request = http.MultipartRequest('POST', uri);
    request.headers['Authorization'] = 'Token $token';
    request.files
        .add(http.MultipartFile.fromBytes('file', bytes, filename: fileName));
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
    throw Exception(
        data['error'] ?? 'Tạo đề thi thất bại: ${response.statusCode}');
  }

  // ─── Grading (Core) ─────────────────────────────────────────────────

  /// Send image to API for grading.
  /// [imageBytes] — image data as bytes (works on all platforms).
  /// [fileName] — original filename for MIME type detection.
  /// [examId] — optional exam ID.
  /// [templateCode] — optional template code.
  /// [corners] — optional 4 corner coordinates [[x1,y1], [x2,y2], [x3,y3], [x4,y4]]
  /// from live camera detection. Sent to server so it can warp directly without re-detecting.
  Future<GradeResult> gradeImage({
    required Uint8List imageBytes,
    String fileName = 'scan.jpg',
    int? examId,
    String? templateCode,
    bool save = true,
    bool fast = true,
    List<List<double>>? corners,
  }) async {
    final uri = Uri.parse('${ApiConfig.baseUrl}${ApiConfig.grade}');
    final request = http.MultipartRequest('POST', uri);

    request.headers['Authorization'] = 'Token $token';

    // OMR grading: Bỏ qua nén lại nếu ảnh đã được tối ưu sẵn (< 800KB, vd từ Live Camera)
    // Giúp loại bỏ hoàn toàn việc giải mã JPEG trên main thread gây lag UI (~800ms)
    final Uint8List compressed = (imageBytes.lengthInBytes < 800 * 1024)
        ? imageBytes
        : _compressForUpload(imageBytes, maxWidth: 2000, quality: 85);
    request.files.add(http.MultipartFile.fromBytes(
      'image',
      compressed,
      filename: 'scan.jpg',
      contentType: MediaType.parse('image/jpeg'),
    ));

    if (examId != null) {
      request.fields['exam_id'] = examId.toString();
    }
    if (templateCode != null && templateCode.isNotEmpty) {
      request.fields['template_code'] = templateCode;
    }
    request.fields['save'] = save ? 'true' : 'false';
    request.fields['fast'] = fast ? '1' : '0';

    // Send corner coordinates if available (from live camera detection)
    if (corners != null && corners.length == 4) {
      request.fields['corners'] = json.encode(corners);
    }

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
