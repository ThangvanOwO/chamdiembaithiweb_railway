import 'package:flutter/material.dart';
import 'package:google_fonts/google_fonts.dart';
import 'package:lucide_icons/lucide_icons.dart';
import 'package:provider/provider.dart';

import '../config/theme.dart';
import '../services/auth_service.dart';
import '../services/api_service.dart';
import '../widgets/academic_dashboard.dart';
import '../widgets/academic_ui.dart';

class DashboardScreen extends StatefulWidget {
  final ValueChanged<int>? onNavigate;
  const DashboardScreen({super.key, this.onNavigate});

  @override
  State<DashboardScreen> createState() => _DashboardScreenState();
}

class _DashboardScreenState extends State<DashboardScreen> {
  Map<String, dynamic>? _data;
  bool _loading = true;
  String? _error;

  @override
  void initState() {
    super.initState();
    _loadData();
  }

  Future<void> _loadData() async {
    final auth = context.read<AuthService>();
    if (auth.token == null) return;

    setState(() {
      _loading = true;
      _error = null;
    });

    try {
      final api = ApiService(token: auth.token!);
      final data = await api.getDashboard();
      if (mounted) setState(() => _data = data);
    } catch (e) {
      if (mounted) {
        if (e.toString().contains('401')) {
          auth.logout();
          return;
        }
        setState(() => _error = e.toString());
      }
    } finally {
      if (mounted) setState(() => _loading = false);
    }
  }

  @override
  Widget build(BuildContext context) {
    final auth = context.watch<AuthService>();

    return Scaffold(
      backgroundColor: AcademicStyle.paper,
      appBar: AppBar(
        title: Text('GradeFlow',
            style: GoogleFonts.manrope(fontWeight: FontWeight.w700)),
        actions: [
          IconButton(
            tooltip: 'Làm mới tổng quan',
            icon: const Icon(LucideIcons.refreshCw, size: 20),
            onPressed: _loading ? null : _loadData,
          ),
        ],
      ),
      body: _loading
          ? const Center(child: CircularProgressIndicator())
          : _error != null
              ? _buildError()
              : RefreshIndicator(
                  onRefresh: _loadData,
                  child: _buildContent(auth),
                ),
    );
  }

  Widget _buildError() {
    return Center(
      child: Padding(
        padding: const EdgeInsets.all(24),
        child: Column(
          mainAxisAlignment: MainAxisAlignment.center,
          children: [
            Icon(LucideIcons.wifiOff,
                size: 48, color: GradeFlowTheme.onSurfaceVariant),
            const SizedBox(height: 16),
            Text('Không thể kết nối server',
                style: GoogleFonts.dmSans(fontSize: 16)),
            const SizedBox(height: 8),
            Text('Kiểm tra kết nối mạng rồi thử lại. Dữ liệu của bạn không bị thay đổi.',
                style: GoogleFonts.dmSans(
                    fontSize: 13, color: GradeFlowTheme.onSurfaceVariant),
                textAlign: TextAlign.center),
            const SizedBox(height: 24),
            ElevatedButton.icon(
              onPressed: _loadData,
              icon: const Icon(LucideIcons.refreshCw, size: 16),
              label: const Text('Thử lại'),
            ),
          ],
        ),
      ),
    );
  }

  Widget _buildContent(AuthService auth) {
    final recent = (_data?['recent_submissions'] as List?) ?? [];
    return AcademicDashboard(
      name: auth.userName,
      stats: Map<String, dynamic>.from(_data?['stats'] ?? {}),
      onNavigate: widget.onNavigate,
      recent: [for (final sub in recent) _SubmissionTile(data: sub)],
    );
  }
}

class _SubmissionTile extends StatelessWidget {
  final Map<String, dynamic> data;
  const _SubmissionTile({required this.data});

  @override
  Widget build(BuildContext context) {
    final score = data['score'];
    final gradeLabel = data['grade_label'] ?? 'pending';
    final gradeText = data['grade_text'] ?? '';

    return Card(
      margin: const EdgeInsets.only(bottom: 8),
      child: Padding(
        padding: const EdgeInsets.all(12),
        child: Row(
          children: [
            // Score badge
            Container(
              width: 48,
              height: 48,
              decoration: BoxDecoration(
                color: GradeFlowTheme.gradeBackground(gradeLabel),
                borderRadius: BorderRadius.circular(10),
              ),
              child: Center(
                child: Text(
                  score != null ? '$score' : '—',
                  style: GoogleFonts.manrope(
                    fontSize: 16,
                    fontWeight: FontWeight.w800,
                    color: GradeFlowTheme.gradeColor(gradeLabel),
                  ),
                ),
              ),
            ),
            const SizedBox(width: 12),

            // Info
            Expanded(
              child: Column(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  Text(
                    data['student_name']?.isNotEmpty == true
                        ? data['student_name']
                        : data['student_id']?.isNotEmpty == true
                            ? 'SBD ${data['student_id']}'
                            : data['exam_title'] ?? 'Bài nộp',
                    style: GoogleFonts.dmSans(
                      fontSize: 14,
                      fontWeight: FontWeight.w600,
                    ),
                    maxLines: 1,
                    overflow: TextOverflow.ellipsis,
                  ),
                  const SizedBox(height: 2),
                  Text(
                    data['exam_title'] ?? '',
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
            if (gradeText.isNotEmpty)
              Container(
                padding:
                    const EdgeInsets.symmetric(horizontal: 10, vertical: 4),
                decoration: BoxDecoration(
                  color: GradeFlowTheme.gradeBackground(gradeLabel),
                  borderRadius: BorderRadius.circular(8),
                ),
                child: Text(
                  gradeText,
                  style: GoogleFonts.dmSans(
                    fontSize: 11,
                    fontWeight: FontWeight.w600,
                    color: GradeFlowTheme.gradeColor(gradeLabel),
                  ),
                ),
              ),
          ],
        ),
      ),
    );
  }
}
