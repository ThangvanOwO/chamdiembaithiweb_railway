import 'package:flutter/material.dart';
import 'package:google_fonts/google_fonts.dart';
import 'package:lucide_icons/lucide_icons.dart';
import 'package:provider/provider.dart';

import '../config/theme.dart';
import '../models/submission.dart';
import '../services/auth_service.dart';
import '../services/api_service.dart';
import 'submission_detail_screen.dart';

class HistoryScreen extends StatefulWidget {
  const HistoryScreen({super.key});

  @override
  State<HistoryScreen> createState() => _HistoryScreenState();
}

class _HistoryScreenState extends State<HistoryScreen> {
  List<Submission> _submissions = [];
  bool _loading = true;

  @override
  void initState() {
    super.initState();
    _loadHistory();
  }

  Future<void> _loadHistory() async {
    final auth = context.read<AuthService>();
    if (auth.token == null) return;

    setState(() => _loading = true);

    try {
      final api = ApiService(token: auth.token!);
      final subs = await api.getSubmissions(limit: 50);
      if (mounted) setState(() => _submissions = subs);
    } catch (_) {}

    if (mounted) setState(() => _loading = false);
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      appBar: AppBar(
        title: const Text('Lịch sử chấm'),
        actions: [
          IconButton(
            icon: const Icon(LucideIcons.refreshCw, size: 20),
            onPressed: _loadHistory,
          ),
        ],
      ),
      body: _loading
          ? const Center(child: CircularProgressIndicator())
          : RefreshIndicator(
              onRefresh: _loadHistory,
              child: _submissions.isEmpty
                  ? _buildEmpty()
                  : _buildList(),
            ),
    );
  }

  Widget _buildEmpty() {
    return Center(
      child: Column(
        mainAxisAlignment: MainAxisAlignment.center,
        children: [
          Icon(LucideIcons.clock,
              size: 48,
              color: GradeFlowTheme.onSurfaceVariant.withOpacity(0.4)),
          const SizedBox(height: 16),
          Text('Chưa có lịch sử',
              style: GoogleFonts.manrope(
                  fontSize: 18, fontWeight: FontWeight.w600)),
          const SizedBox(height: 8),
          Text('Bắt đầu chấm điểm để xem lịch sử tại đây.',
              style: GoogleFonts.dmSans(
                  fontSize: 14, color: GradeFlowTheme.onSurfaceVariant)),
        ],
      ),
    );
  }

  Widget _buildList() {
    return ListView.builder(
      padding: const EdgeInsets.all(16),
      itemCount: _submissions.length,
      itemBuilder: (context, index) {
        final sub = _submissions[index];
        final gradeColor = GradeFlowTheme.gradeColor(sub.gradeLabel);
        final gradeBg = GradeFlowTheme.gradeBackground(sub.gradeLabel);

        return Card(
          margin: const EdgeInsets.only(bottom: 8),
          child: InkWell(
            onTap: () => Navigator.push(
              context,
              MaterialPageRoute(
                builder: (_) => SubmissionDetailScreen(submissionId: sub.id),
              ),
            ),
            borderRadius: BorderRadius.circular(12),
            child: Padding(
              padding: const EdgeInsets.all(12),
              child: Row(
              children: [
                // Score
                Container(
                  width: 48,
                  height: 48,
                  decoration: BoxDecoration(
                    color: gradeBg,
                    borderRadius: BorderRadius.circular(10),
                  ),
                  child: Center(
                    child: Text(
                      sub.score != null ? '${sub.score}' : '—',
                      style: GoogleFonts.manrope(
                        fontSize: 16,
                        fontWeight: FontWeight.w800,
                        color: gradeColor,
                      ),
                    ),
                  ),
                ),
                const SizedBox(width: 12),

                // Details
                Expanded(
                  child: Column(
                    crossAxisAlignment: CrossAxisAlignment.start,
                    children: [
                      Text(
                        sub.studentId.isNotEmpty
                            ? 'SBD ${sub.studentId}'
                            : 'Bài #${sub.id}',
                        style: GoogleFonts.dmSans(
                            fontSize: 14, fontWeight: FontWeight.w600),
                      ),
                      Text(
                        sub.examTitle,
                        style: GoogleFonts.dmSans(
                          fontSize: 12,
                          color: GradeFlowTheme.onSurfaceVariant,
                        ),
                        maxLines: 1,
                        overflow: TextOverflow.ellipsis,
                      ),
                    ],
                  ),
                ),

                // Grade chip
                if (sub.gradeText.isNotEmpty && sub.status == 'completed')
                  Container(
                    padding:
                        const EdgeInsets.symmetric(horizontal: 10, vertical: 4),
                    decoration: BoxDecoration(
                      color: gradeBg,
                      borderRadius: BorderRadius.circular(8),
                    ),
                    child: Text(
                      sub.gradeText,
                      style: GoogleFonts.dmSans(
                        fontSize: 11,
                        fontWeight: FontWeight.w600,
                        color: gradeColor,
                      ),
                    ),
                  ),
              ],
            ),
            ),
          ),
        );
      },
    );
  }
}
