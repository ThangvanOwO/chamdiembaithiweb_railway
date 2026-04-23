import 'package:flutter/material.dart';
import 'package:google_fonts/google_fonts.dart';
import 'package:lucide_icons/lucide_icons.dart';
import 'package:provider/provider.dart';

import '../config/theme.dart';
import '../services/auth_service.dart';
import '../services/api_service.dart';

class AdminUsersScreen extends StatefulWidget {
  const AdminUsersScreen({super.key});

  @override
  State<AdminUsersScreen> createState() => _AdminUsersScreenState();
}

class _AdminUsersScreenState extends State<AdminUsersScreen> {
  bool _loading = true;
  String? _error;
  List<Map<String, dynamic>> _users = [];
  int _totalUsers = 0;

  @override
  void initState() {
    super.initState();
    _loadUsers();
  }

  Future<void> _loadUsers() async {
    final auth = context.read<AuthService>();
    if (auth.token == null) return;

    setState(() {
      _loading = true;
      _error = null;
    });

    try {
      final api = ApiService(token: auth.token!);
      final data = await api.getAdminUsers();
      if (mounted) {
        setState(() {
          _totalUsers = data['total'] ?? 0;
          _users = List<Map<String, dynamic>>.from(data['users'] ?? []);
          _loading = false;
        });
      }
    } catch (e) {
      if (mounted) {
        setState(() {
          _error = e.toString();
          _loading = false;
        });
      }
    }
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      appBar: AppBar(
        title: const Text('Quản lý người dùng'),
        actions: [
          IconButton(
            icon: const Icon(LucideIcons.refreshCw, size: 20),
            onPressed: _loadUsers,
          ),
        ],
      ),
      body: _loading
          ? const Center(child: CircularProgressIndicator())
          : _error != null
              ? _buildError()
              : _buildUserList(),
    );
  }

  Widget _buildError() {
    return Center(
      child: Padding(
        padding: const EdgeInsets.all(32),
        child: Column(
          mainAxisSize: MainAxisSize.min,
          children: [
            Icon(LucideIcons.alertCircle,
                size: 48, color: GradeFlowTheme.error),
            const SizedBox(height: 12),
            Text(_error!,
                style: GoogleFonts.dmSans(color: GradeFlowTheme.error),
                textAlign: TextAlign.center),
            const SizedBox(height: 16),
            ElevatedButton.icon(
              onPressed: _loadUsers,
              icon: const Icon(LucideIcons.refreshCw, size: 16),
              label: const Text('Thử lại'),
            ),
          ],
        ),
      ),
    );
  }

  Widget _buildUserList() {
    return RefreshIndicator(
      onRefresh: _loadUsers,
      child: ListView(
        padding: const EdgeInsets.all(16),
        children: [
          // Summary card
          Card(
            color: GradeFlowTheme.primaryFixed,
            child: Padding(
              padding: const EdgeInsets.all(16),
              child: Row(
                children: [
                  Container(
                    padding: const EdgeInsets.all(10),
                    decoration: BoxDecoration(
                      color: GradeFlowTheme.primary,
                      borderRadius: BorderRadius.circular(12),
                    ),
                    child: const Icon(LucideIcons.users,
                        color: Colors.white, size: 24),
                  ),
                  const SizedBox(width: 16),
                  Column(
                    crossAxisAlignment: CrossAxisAlignment.start,
                    children: [
                      Text(
                        '$_totalUsers người dùng',
                        style: GoogleFonts.manrope(
                          fontSize: 20,
                          fontWeight: FontWeight.w700,
                          color: GradeFlowTheme.primary,
                        ),
                      ),
                      Text(
                        'Tổng số tài khoản đã đăng ký',
                        style: GoogleFonts.dmSans(
                          fontSize: 13,
                          color: GradeFlowTheme.primary.withOpacity(0.7),
                        ),
                      ),
                    ],
                  ),
                ],
              ),
            ),
          ),
          const SizedBox(height: 16),

          // User list
          ..._users.map((u) => _buildUserCard(u)),
        ],
      ),
    );
  }

  Widget _buildUserCard(Map<String, dynamic> user) {
    final fullName = user['full_name'] ?? user['username'] ?? '—';
    final email = user['email'] ?? '';
    final isAdmin = user['is_admin'] == true;
    final isActive = user['is_active'] == true;
    final examCount = user['exam_count'] ?? 0;
    final submissionCount = user['submission_count'] ?? 0;
    final dateJoined = user['date_joined'] ?? '';
    final lastLogin = user['last_login'];

    // Parse date
    String joinedStr = '';
    try {
      final dt = DateTime.parse(dateJoined);
      joinedStr = '${dt.day}/${dt.month}/${dt.year}';
    } catch (_) {}

    String lastLoginStr = 'Chưa đăng nhập';
    if (lastLogin != null) {
      try {
        final dt = DateTime.parse(lastLogin);
        final diff = DateTime.now().difference(dt);
        if (diff.inMinutes < 60) {
          lastLoginStr = '${diff.inMinutes} phút trước';
        } else if (diff.inHours < 24) {
          lastLoginStr = '${diff.inHours} giờ trước';
        } else {
          lastLoginStr = '${diff.inDays} ngày trước';
        }
      } catch (_) {}
    }

    final initial = (fullName.isNotEmpty ? fullName[0] : '?').toUpperCase();

    return Card(
      margin: const EdgeInsets.only(bottom: 10),
      child: Padding(
        padding: const EdgeInsets.all(14),
        child: Row(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            // Avatar
            Container(
              width: 44,
              height: 44,
              decoration: BoxDecoration(
                color: isAdmin
                    ? GradeFlowTheme.primary
                    : GradeFlowTheme.primaryFixed,
                borderRadius: BorderRadius.circular(12),
              ),
              child: Center(
                child: Text(
                  initial,
                  style: GoogleFonts.manrope(
                    fontSize: 18,
                    fontWeight: FontWeight.w700,
                    color: isAdmin ? Colors.white : GradeFlowTheme.primary,
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
                  Row(
                    children: [
                      Flexible(
                        child: Text(
                          fullName,
                          style: GoogleFonts.dmSans(
                            fontSize: 15,
                            fontWeight: FontWeight.w600,
                          ),
                          overflow: TextOverflow.ellipsis,
                        ),
                      ),
                      const SizedBox(width: 6),
                      if (isAdmin)
                        Container(
                          padding: const EdgeInsets.symmetric(
                              horizontal: 6, vertical: 1),
                          decoration: BoxDecoration(
                            color: GradeFlowTheme.primary,
                            borderRadius: BorderRadius.circular(4),
                          ),
                          child: Text('Admin',
                              style: GoogleFonts.dmSans(
                                  fontSize: 10,
                                  fontWeight: FontWeight.w600,
                                  color: Colors.white)),
                        ),
                      if (!isActive)
                        Container(
                          margin: const EdgeInsets.only(left: 4),
                          padding: const EdgeInsets.symmetric(
                              horizontal: 6, vertical: 1),
                          decoration: BoxDecoration(
                            color: GradeFlowTheme.error,
                            borderRadius: BorderRadius.circular(4),
                          ),
                          child: Text('Vô hiệu',
                              style: GoogleFonts.dmSans(
                                  fontSize: 10,
                                  fontWeight: FontWeight.w600,
                                  color: Colors.white)),
                        ),
                    ],
                  ),
                  const SizedBox(height: 2),
                  Text(
                    email,
                    style: GoogleFonts.dmSans(
                      fontSize: 12,
                      color: GradeFlowTheme.onSurfaceVariant,
                    ),
                  ),
                  const SizedBox(height: 8),

                  // Stats row
                  Row(
                    children: [
                      _statChip(LucideIcons.fileText, '$examCount đề thi'),
                      const SizedBox(width: 10),
                      _statChip(
                          LucideIcons.checkSquare, '$submissionCount bài chấm'),
                    ],
                  ),
                  const SizedBox(height: 6),

                  // Date info
                  Row(
                    children: [
                      Icon(LucideIcons.calendar,
                          size: 11, color: GradeFlowTheme.onSurfaceVariant),
                      const SizedBox(width: 4),
                      Text(
                        'Tham gia: $joinedStr',
                        style: GoogleFonts.dmSans(
                          fontSize: 11,
                          color: GradeFlowTheme.onSurfaceVariant,
                        ),
                      ),
                      const SizedBox(width: 12),
                      Icon(LucideIcons.clock,
                          size: 11, color: GradeFlowTheme.onSurfaceVariant),
                      const SizedBox(width: 4),
                      Text(
                        lastLoginStr,
                        style: GoogleFonts.dmSans(
                          fontSize: 11,
                          color: GradeFlowTheme.onSurfaceVariant,
                        ),
                      ),
                    ],
                  ),
                ],
              ),
            ),
          ],
        ),
      ),
    );
  }

  Widget _statChip(IconData icon, String label) {
    return Container(
      padding: const EdgeInsets.symmetric(horizontal: 8, vertical: 3),
      decoration: BoxDecoration(
        color: GradeFlowTheme.surfaceContainerLow,
        borderRadius: BorderRadius.circular(6),
      ),
      child: Row(
        mainAxisSize: MainAxisSize.min,
        children: [
          Icon(icon, size: 12, color: GradeFlowTheme.primary),
          const SizedBox(width: 4),
          Text(label,
              style: GoogleFonts.dmSans(
                  fontSize: 11, fontWeight: FontWeight.w500)),
        ],
      ),
    );
  }
}
