class GradeResult {
  final bool success;
  final int? submissionId;
  final String sbd;
  final String made;
  final double? score;
  final int? correctCount;
  final int? totalQuestions;
  final String gradeLabel;
  final String gradeText;
  final Map<String, dynamic> scores;
  final Map<String, dynamic> part1;
  final Map<String, dynamic> part2;
  final Map<String, dynamic> part3;
  final Map<String, dynamic> correctAnswers;
  final Map<String, dynamic>? weighted;
  final String detectMethod;
  final double processingTime;
  final String error;
  final String resultImageBase64;
  final String overlayImageBase64;

  GradeResult({
    required this.success,
    this.submissionId,
    this.sbd = '',
    this.made = '',
    this.score,
    this.correctCount,
    this.totalQuestions,
    this.gradeLabel = 'pending',
    this.gradeText = 'Chờ chấm',
    this.scores = const {},
    this.part1 = const {},
    this.part2 = const {},
    this.part3 = const {},
    this.correctAnswers = const {},
    this.weighted,
    this.detectMethod = '',
    this.processingTime = 0,
    this.error = '',
    this.resultImageBase64 = '',
    this.overlayImageBase64 = '',
  });

  factory GradeResult.fromJson(Map<String, dynamic> json) {
    return GradeResult(
      success: json['success'] ?? false,
      submissionId: json['submission_id'],
      sbd: json['sbd'] ?? '',
      made: json['made'] ?? '',
      score: json['score']?.toDouble(),
      correctCount: json['correct_count'],
      totalQuestions: json['total_questions'],
      gradeLabel: json['grade_label'] ?? 'pending',
      gradeText: json['grade_text'] ?? 'Chờ chấm',
      scores: Map<String, dynamic>.from(json['scores'] ?? {}),
      part1: Map<String, dynamic>.from(json['part1'] ?? {}),
      part2: Map<String, dynamic>.from(json['part2'] ?? {}),
      part3: Map<String, dynamic>.from(json['part3'] ?? {}),
      correctAnswers: Map<String, dynamic>.from(json['correct_answers'] ?? {}),
      weighted: json['weighted'] != null
          ? Map<String, dynamic>.from(json['weighted'])
          : null,
      detectMethod: json['detect_method'] ?? '',
      processingTime: (json['processing_time'] ?? 0).toDouble(),
      error: json['error'] ?? '',
      resultImageBase64: json['result_image'] ?? '',
      overlayImageBase64: json['overlay_image'] ?? '',
    );
  }
}
