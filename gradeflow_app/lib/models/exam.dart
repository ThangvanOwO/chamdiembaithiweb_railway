class Exam {
  final int id;
  final String title;
  final String subject;
  final int numQuestions;
  final String templateCode;
  final List<String> variantCodes;
  final int submissionCount;
  final int gradedCount;
  final double? averageScore;
  final List<int> partsConfig;
  final String createdAt;

  Exam({
    required this.id,
    required this.title,
    this.subject = '',
    this.numQuestions = 0,
    this.templateCode = '',
    this.variantCodes = const [],
    this.submissionCount = 0,
    this.gradedCount = 0,
    this.averageScore,
    this.partsConfig = const [],
    this.createdAt = '',
  });

  factory Exam.fromJson(Map<String, dynamic> json) {
    return Exam(
      id: json['id'] ?? 0,
      title: json['title'] ?? '',
      subject: json['subject'] ?? '',
      numQuestions: json['num_questions'] ?? 0,
      templateCode: json['template_code'] ?? '',
      variantCodes: List<String>.from(json['variant_codes'] ?? []),
      submissionCount: json['submission_count'] ?? 0,
      gradedCount: json['graded_count'] ?? 0,
      averageScore: json['average_score']?.toDouble(),
      partsConfig: List<int>.from(json['parts_config'] ?? []),
      createdAt: json['created_at'] ?? '',
    );
  }

  @override
  bool operator ==(Object other) =>
      identical(this, other) ||
      other is Exam && runtimeType == other.runtimeType && id == other.id;

  @override
  int get hashCode => id.hashCode;
}
