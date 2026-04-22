import 'package:flutter/material.dart';
import 'package:google_fonts/google_fonts.dart';
import 'package:lucide_icons/lucide_icons.dart';
import 'package:provider/provider.dart';

import '../config/theme.dart';
import '../services/api_service.dart';
import '../services/auth_service.dart';
import '../services/coach_mark_service.dart';
import '../services/tutorial_flow.dart';
import 'onboarding_screen.dart';

class SettingsScreen extends StatefulWidget {
  const SettingsScreen({super.key});

  @override
  State<SettingsScreen> createState() => _SettingsScreenState();
}

class _SettingsScreenState extends State<SettingsScreen> {
  bool _loading = true;
  String? _error;
  int _retentionDays = 30;
  bool _contributeTraining = false;
  List<Map<String, dynamic>> _choices = [];
  bool _saving = false;
  bool _cleaning = false;

  @override
  void initState() {
    super.initState();
    _loadSettings();
  }

  Future<void> _loadSettings() async {
    final auth = context.read<AuthService>();
    if (auth.token == null) return;

    setState(() {
      _loading = true;
      _error = null;
    });
    try {
      final api = ApiService(token: auth.token!);
      final data = await api.getSettings();
      if (!mounted) return;
      setState(() {
        _retentionDays = data['temp_retention_days'] ?? 30;
        _contributeTraining = data['contribute_training_data'] == true;
        _choices = List<Map<String, dynamic>>.from(data['retention_choices'] ?? []);
        _loading = false;
      });
    } catch (e) {
      if (mounted) setState(() { _error = e.toString(); _loading = false; });
    }
  }

  Future<void> _saveRetention(int days) async {
    final auth = context.read<AuthService>();
    setState(() => _saving = true);
    try {
      final api = ApiService(token: auth.token!);
      await api.updateSettings(retentionDays: days);
      if (!mounted) return;
      setState(() {
        _retentionDays = days;
        _saving = false;
      });
      ScaffoldMessenger.of(context).showSnackBar(
        SnackBar(
            content: const Text('Đã lưu cài đặt'),
            backgroundColor: GradeFlowTheme.success),
      );
    } catch (e) {
      if (mounted) {
        setState(() => _saving = false);
        ScaffoldMessenger.of(context).showSnackBar(
          SnackBar(content: Text('Lỗi: $e'), backgroundColor: Colors.red),
        );
      }
    }
  }

  Future<void> _saveContribute(bool value) async {
    final auth = context.read<AuthService>();
    final prev = _contributeTraining;
    setState(() => _contributeTraining = value);
    try {
      final api = ApiService(token: auth.token!);
      await api.updateSettings(contributeTraining: value);
      if (!mounted) return;
      ScaffoldMessenger.of(context).showSnackBar(
        SnackBar(
          content: Text(value
              ? 'Đã bật đóng góp ảnh training'
              : 'Đã tắt đóng góp ảnh training'),
          backgroundColor: GradeFlowTheme.success,
        ),
      );
    } catch (e) {
      if (mounted) {
        setState(() => _contributeTraining = prev);
        ScaffoldMessenger.of(context).showSnackBar(
          SnackBar(content: Text('Lỗi: $e'), backgroundColor: Colors.red),
        );
      }
    }
  }

  Future<void> _confirmCleanup() async {
    final confirm = await showDialog<bool>(
      context: context,
      builder: (_) => AlertDialog(
        title: Text('Xóa tất cả ảnh đã chấm?',
            style: GoogleFonts.manrope(fontWeight: FontWeight.w700)),
        content: Text(
            'Tất cả ảnh phiếu đã chấm sẽ bị xóa khỏi server. '
            'Điểm số và lịch sử vẫn được giữ lại. Không thể khôi phục.',
            style: GoogleFonts.dmSans(fontSize: 14)),
        actions: [
          TextButton(
              onPressed: () => Navigator.pop(context, false),
              child: const Text('Hủy')),
          ElevatedButton(
            onPressed: () => Navigator.pop(context, true),
            style: ElevatedButton.styleFrom(
                backgroundColor: GradeFlowTheme.error,
                foregroundColor: Colors.white),
            child: const Text('Xóa ngay'),
          ),
        ],
      ),
    );
    if (confirm != true) return;

    setState(() => _cleaning = true);
    try {
      final auth = context.read<AuthService>();
      final api = ApiService(token: auth.token!);
      final result = await api.cleanupNow();
      if (!mounted) return;
      final files = result['files_deleted'] ?? 0;
      final mb = result['mb_freed'] ?? 0;
      ScaffoldMessenger.of(context).showSnackBar(
        SnackBar(
            content: Text('Đã xóa $files file, giải phóng $mb MB'),
            backgroundColor: GradeFlowTheme.success),
      );
    } catch (e) {
      if (mounted) {
        ScaffoldMessenger.of(context).showSnackBar(
          SnackBar(content: Text('Lỗi: $e'), backgroundColor: Colors.red),
        );
      }
    } finally {
      if (mounted) setState(() => _cleaning = false);
    }
  }

  Future<void> _replayTutorial() async {
    await OnboardingScreen.reset();
    await CoachMarkService.resetAll();
    await TutorialFlow.instance.restart();
    if (!mounted) return;
    ScaffoldMessenger.of(context).showSnackBar(
      SnackBar(
          content: const Text('Hướng dẫn sẽ hiện lại khi mở app lần sau'),
          backgroundColor: GradeFlowTheme.primary),
    );
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      appBar: AppBar(title: const Text('Cài đặt')),
      body: _loading
          ? const Center(child: CircularProgressIndicator())
          : _error != null
              ? _buildError()
              : ListView(
                  padding: const EdgeInsets.all(16),
                  children: [
                    _sectionTitle('Quản lý bộ nhớ', LucideIcons.hardDrive),
                    Card(
                      child: Padding(
                        padding: const EdgeInsets.all(16),
                        child: Column(
                          crossAxisAlignment: CrossAxisAlignment.start,
                          children: [
                            Text('Tự động xóa ảnh đã chấm',
                                style: GoogleFonts.dmSans(
                                    fontSize: 15,
                                    fontWeight: FontWeight.w600)),
                            const SizedBox(height: 4),
                            Text(
                                'Ảnh phiếu sẽ bị xóa tự động sau khoảng thời gian '
                                'này. Điểm số và dữ liệu chấm vẫn được giữ nguyên.',
                                style: GoogleFonts.dmSans(
                                    fontSize: 12,
                                    color: GradeFlowTheme.onSurfaceVariant)),
                            const SizedBox(height: 12),
                            ..._choices.map((c) {
                              final v = c['value'] as int;
                              return RadioListTile<int>(
                                value: v,
                                groupValue: _retentionDays,
                                onChanged: _saving
                                    ? null
                                    : (val) {
                                        if (val != null) _saveRetention(val);
                                      },
                                title: Text(c['label'] ?? '',
                                    style: GoogleFonts.dmSans(fontSize: 14)),
                                contentPadding: EdgeInsets.zero,
                                dense: true,
                                visualDensity: VisualDensity.compact,
                              );
                            }),
                          ],
                        ),
                      ),
                    ),
                    const SizedBox(height: 12),
                    SizedBox(
                      width: double.infinity,
                      height: 48,
                      child: OutlinedButton.icon(
                        onPressed: _cleaning ? null : _confirmCleanup,
                        icon: _cleaning
                            ? const SizedBox(
                                width: 16,
                                height: 16,
                                child: CircularProgressIndicator(strokeWidth: 2))
                            : const Icon(LucideIcons.trash2, size: 18),
                        label: Text(_cleaning
                            ? 'Đang xóa...'
                            : 'Xóa tất cả ảnh đã chấm ngay'),
                        style: OutlinedButton.styleFrom(
                          foregroundColor: GradeFlowTheme.error,
                          side: const BorderSide(color: GradeFlowTheme.error),
                          shape: RoundedRectangleBorder(
                              borderRadius: BorderRadius.circular(12)),
                        ),
                      ),
                    ),

                    const SizedBox(height: 28),
                    _sectionTitle('Đóng góp', LucideIcons.heartHandshake),
                    Card(
                      child: Padding(
                        padding: const EdgeInsets.all(16),
                        child: Column(
                          crossAxisAlignment: CrossAxisAlignment.start,
                          children: [
                            Row(
                              children: [
                                Expanded(
                                  child: Column(
                                    crossAxisAlignment:
                                        CrossAxisAlignment.start,
                                    children: [
                                      Text('Góp ảnh để cải thiện AI',
                                          style: GoogleFonts.dmSans(
                                              fontSize: 15,
                                              fontWeight: FontWeight.w600)),
                                      const SizedBox(height: 4),
                                      Text(
                                        'Chỉ những ảnh phiếu có mã đề, SBD và câu '
                                        'trả lời nhận diện 100% (không dấu "?") '
                                        'mới được gửi. Ảnh có thể chứa thông tin '
                                        'học sinh — cân nhắc trước khi bật.',
                                        style: GoogleFonts.dmSans(
                                            fontSize: 12,
                                            height: 1.4,
                                            color: GradeFlowTheme
                                                .onSurfaceVariant),
                                      ),
                                    ],
                                  ),
                                ),
                                Switch(
                                  value: _contributeTraining,
                                  onChanged: _saving ? null : _saveContribute,
                                ),
                              ],
                            ),
                            if (_contributeTraining) ...[
                              const SizedBox(height: 8),
                              Container(
                                padding: const EdgeInsets.symmetric(
                                    horizontal: 10, vertical: 6),
                                decoration: BoxDecoration(
                                  color: GradeFlowTheme.primaryFixed,
                                  borderRadius: BorderRadius.circular(6),
                                ),
                                child: Row(
                                  mainAxisSize: MainAxisSize.min,
                                  children: [
                                    Icon(LucideIcons.checkCircle,
                                        size: 14,
                                        color: GradeFlowTheme.primary),
                                    const SizedBox(width: 6),
                                    Text('Đã bật đóng góp',
                                        style: GoogleFonts.dmSans(
                                            fontSize: 11,
                                            fontWeight: FontWeight.w600,
                                            color: GradeFlowTheme.primary)),
                                  ],
                                ),
                              ),
                            ],
                          ],
                        ),
                      ),
                    ),

                    const SizedBox(height: 28),
                    _sectionTitle('Hướng dẫn', LucideIcons.helpCircle),
                    Card(
                      child: ListTile(
                        leading: Icon(LucideIcons.bookOpen,
                            color: GradeFlowTheme.primary),
                        title: Text('Xem lại hướng dẫn',
                            style: GoogleFonts.dmSans(
                                fontSize: 14, fontWeight: FontWeight.w600)),
                        subtitle: Text(
                            'Hiện lại màn hình giới thiệu và các coach marks',
                            style: GoogleFonts.dmSans(
                                fontSize: 12,
                                color: GradeFlowTheme.onSurfaceVariant)),
                        trailing: const Icon(LucideIcons.chevronRight, size: 18),
                        onTap: _replayTutorial,
                      ),
                    ),
                  ],
                ),
    );
  }

  Widget _sectionTitle(String text, IconData icon) {
    return Padding(
      padding: const EdgeInsets.only(bottom: 10, top: 4),
      child: Row(
        children: [
          Icon(icon, size: 16, color: GradeFlowTheme.onSurfaceVariant),
          const SizedBox(width: 8),
          Text(text,
              style: GoogleFonts.manrope(
                  fontSize: 13,
                  fontWeight: FontWeight.w700,
                  color: GradeFlowTheme.onSurfaceVariant,
                  letterSpacing: 0.5)),
        ],
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
            Icon(LucideIcons.alertTriangle,
                size: 48, color: GradeFlowTheme.onSurfaceVariant),
            const SizedBox(height: 12),
            Text(_error ?? '',
                style: GoogleFonts.dmSans(fontSize: 13),
                textAlign: TextAlign.center),
            const SizedBox(height: 16),
            ElevatedButton.icon(
              onPressed: _loadSettings,
              icon: const Icon(LucideIcons.refreshCw, size: 16),
              label: const Text('Thử lại'),
            ),
          ],
        ),
      ),
    );
  }
}
