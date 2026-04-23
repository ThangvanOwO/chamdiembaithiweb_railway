import 'package:flutter/material.dart';
import 'package:google_fonts/google_fonts.dart';
import 'package:lucide_icons/lucide_icons.dart';
import 'package:provider/provider.dart';

import '../config/api_config.dart';
import '../config/theme.dart';
import '../services/auth_service.dart';
import 'settings_screen.dart';
import 'admin_training_screen.dart';
import 'admin_users_screen.dart';

class ProfileScreen extends StatelessWidget {
  const ProfileScreen({super.key});

  @override
  Widget build(BuildContext context) {
    final auth = context.watch<AuthService>();

    return Scaffold(
      appBar: AppBar(title: const Text('Tài khoản')),
      body: ListView(
        padding: const EdgeInsets.all(16),
        children: [
          // User info card
          Card(
            child: Padding(
              padding: const EdgeInsets.all(20),
              child: Row(
                children: [
                  // Avatar
                  Container(
                    width: 56,
                    height: 56,
                    decoration: BoxDecoration(
                      color: GradeFlowTheme.primaryFixed,
                      borderRadius: BorderRadius.circular(16),
                    ),
                    child: Center(
                      child: Text(
                        auth.userInitial,
                        style: GoogleFonts.manrope(
                          fontSize: 22,
                          fontWeight: FontWeight.w700,
                          color: GradeFlowTheme.primary,
                        ),
                      ),
                    ),
                  ),
                  const SizedBox(width: 16),
                  Expanded(
                    child: Column(
                      crossAxisAlignment: CrossAxisAlignment.start,
                      children: [
                        Text(
                          auth.userName,
                          style: GoogleFonts.dmSans(
                              fontSize: 17, fontWeight: FontWeight.w600),
                        ),
                        const SizedBox(height: 2),
                        Text(
                          auth.userEmail,
                          style: GoogleFonts.dmSans(
                              fontSize: 13,
                              color: GradeFlowTheme.onSurfaceVariant),
                        ),
                        const SizedBox(height: 4),
                        Container(
                          padding: const EdgeInsets.symmetric(
                              horizontal: 8, vertical: 2),
                          decoration: BoxDecoration(
                            color: GradeFlowTheme.primaryFixed,
                            borderRadius: BorderRadius.circular(6),
                          ),
                          child: Text(
                            'Giáo viên',
                            style: GoogleFonts.dmSans(
                              fontSize: 11,
                              fontWeight: FontWeight.w600,
                              color: GradeFlowTheme.primary,
                            ),
                          ),
                        ),
                      ],
                    ),
                  ),
                ],
              ),
            ),
          ),
          const SizedBox(height: 16),

          // Server info
          Card(
            child: Padding(
              padding: const EdgeInsets.all(16),
              child: Column(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  Text('Cấu hình kết nối',
                      style: GoogleFonts.dmSans(
                          fontSize: 14, fontWeight: FontWeight.w600)),
                  const SizedBox(height: 8),
                  _infoRow(LucideIcons.server, 'Server', ApiConfig.baseUrl),
                  const SizedBox(height: 6),
                  _infoRow(LucideIcons.key, 'Token',
                      '${auth.token?.substring(0, 8)}...'),
                ],
              ),
            ),
          ),
          const SizedBox(height: 16),

          // App info
          Card(
            child: Padding(
              padding: const EdgeInsets.all(16),
              child: Column(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  Text('Thông tin ứng dụng',
                      style: GoogleFonts.dmSans(
                          fontSize: 14, fontWeight: FontWeight.w600)),
                  const SizedBox(height: 8),
                  _infoRow(LucideIcons.smartphone, 'Ứng dụng', 'GradeFlow Mobile'),
                  const SizedBox(height: 6),
                  _infoRow(LucideIcons.tag, 'Phiên bản', '1.0.0'),
                  const SizedBox(height: 6),
                  _infoRow(LucideIcons.scan, 'Document Scanner',
                      'Google ML Kit'),
                ],
              ),
            ),
          ),
          const SizedBox(height: 16),

          // Admin-only: Training data manager
          if (auth.isAdmin) ...[
            Card(
              color: GradeFlowTheme.primaryFixed,
              child: ListTile(
                leading: Container(
                  padding: const EdgeInsets.all(8),
                  decoration: BoxDecoration(
                    color: GradeFlowTheme.primary,
                    borderRadius: BorderRadius.circular(10),
                  ),
                  child: const Icon(LucideIcons.shieldCheck,
                      color: Colors.white, size: 20),
                ),
                title: Text('Quản trị training data',
                    style: GoogleFonts.dmSans(
                        fontSize: 15,
                        fontWeight: FontWeight.w700,
                        color: GradeFlowTheme.primary)),
                subtitle: Text('Xem thống kê và tải gói ảnh training (.zip)',
                    style: GoogleFonts.dmSans(
                        fontSize: 12,
                        color: GradeFlowTheme.primary.withOpacity(0.8))),
                trailing: Icon(LucideIcons.chevronRight,
                    size: 18, color: GradeFlowTheme.primary),
                onTap: () => Navigator.push(
                  context,
                  MaterialPageRoute(
                    builder: (_) => const AdminTrainingScreen(),
                  ),
                ),
              ),
            ),
            const SizedBox(height: 12),
            Card(
              color: GradeFlowTheme.primaryFixed,
              child: ListTile(
                leading: Container(
                  padding: const EdgeInsets.all(8),
                  decoration: BoxDecoration(
                    color: GradeFlowTheme.primary,
                    borderRadius: BorderRadius.circular(10),
                  ),
                  child: const Icon(LucideIcons.users,
                      color: Colors.white, size: 20),
                ),
                title: Text('Quản lý người dùng',
                    style: GoogleFonts.dmSans(
                        fontSize: 15,
                        fontWeight: FontWeight.w700,
                        color: GradeFlowTheme.primary)),
                subtitle: Text('Xem danh sách tài khoản và số đề thi mỗi user',
                    style: GoogleFonts.dmSans(
                        fontSize: 12,
                        color: GradeFlowTheme.primary.withOpacity(0.8))),
                trailing: Icon(LucideIcons.chevronRight,
                    size: 18, color: GradeFlowTheme.primary),
                onTap: () => Navigator.push(
                  context,
                  MaterialPageRoute(
                    builder: (_) => const AdminUsersScreen(),
                  ),
                ),
              ),
            ),
            const SizedBox(height: 12),
          ],

          // Settings entry
          Card(
            child: ListTile(
              leading: Icon(LucideIcons.settings,
                  color: GradeFlowTheme.primary),
              title: Text('Cài đặt',
                  style: GoogleFonts.dmSans(
                      fontSize: 15, fontWeight: FontWeight.w600)),
              subtitle: Text('Tự động xóa ảnh cũ, xem lại hướng dẫn',
                  style: GoogleFonts.dmSans(
                      fontSize: 12,
                      color: GradeFlowTheme.onSurfaceVariant)),
              trailing: const Icon(LucideIcons.chevronRight, size: 18),
              onTap: () => Navigator.push(
                context,
                MaterialPageRoute(
                    builder: (_) => const SettingsScreen()),
              ),
            ),
          ),
          const SizedBox(height: 24),

          // Logout button
          SizedBox(
            height: 48,
            child: OutlinedButton.icon(
              onPressed: () => _confirmLogout(context, auth),
              icon: const Icon(LucideIcons.logOut, size: 18),
              label: const Text('Đăng xuất'),
              style: OutlinedButton.styleFrom(
                foregroundColor: GradeFlowTheme.error,
                side: const BorderSide(color: GradeFlowTheme.error),
              ),
            ),
          ),
        ],
      ),
    );
  }

  Widget _infoRow(IconData icon, String label, String value) {
    return Row(
      children: [
        Icon(icon, size: 14, color: GradeFlowTheme.onSurfaceVariant),
        const SizedBox(width: 8),
        Text(
          '$label: ',
          style: GoogleFonts.dmSans(
              fontSize: 13, color: GradeFlowTheme.onSurfaceVariant),
        ),
        Expanded(
          child: Text(
            value,
            style: GoogleFonts.dmSans(fontSize: 13, fontWeight: FontWeight.w500),
            overflow: TextOverflow.ellipsis,
          ),
        ),
      ],
    );
  }

  void _confirmLogout(BuildContext context, AuthService auth) {
    showDialog(
      context: context,
      builder: (ctx) => AlertDialog(
        title: Text('Đăng xuất?',
            style: GoogleFonts.manrope(fontWeight: FontWeight.w600)),
        content: Text('Bạn sẽ cần đăng nhập lại để tiếp tục sử dụng.',
            style: GoogleFonts.dmSans()),
        actions: [
          TextButton(
            onPressed: () => Navigator.pop(ctx),
            child: const Text('Hủy'),
          ),
          ElevatedButton(
            onPressed: () {
              Navigator.pop(ctx);
              auth.logout();
            },
            style: ElevatedButton.styleFrom(
              backgroundColor: GradeFlowTheme.error,
            ),
            child: const Text('Đăng xuất'),
          ),
        ],
      ),
    );
  }
}
