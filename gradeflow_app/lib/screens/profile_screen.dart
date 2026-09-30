import 'package:flutter/material.dart';
import 'package:lucide_icons/lucide_icons.dart';
import 'package:provider/provider.dart';
import '../config/api_config.dart';
import '../services/ad_service.dart';
import '../services/auth_service.dart';
import '../widgets/ad_banner.dart';
import '../widgets/credit_wallet_card.dart';
import 'settings_screen.dart';
import 'admin_test_screen.dart';
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
          Card(
              child: ListTile(
            contentPadding: const EdgeInsets.all(16),
            leading: CircleAvatar(child: Text(auth.userInitial)),
            title: Text(auth.userName,
                style: const TextStyle(fontWeight: FontWeight.w600)),
            subtitle: Text(auth.userEmail),
          )),
          const SizedBox(height: 12),
          if (auth.token != null) CreditWalletCard(token: auth.token!),
          const InlineAdBanner(),
          Card(
              child: Column(children: [
            ListTile(
              leading: const Icon(LucideIcons.settings),
              title: const Text('Cài đặt'),
              trailing: const Icon(Icons.chevron_right),
              onTap: () => Navigator.push(context,
                  MaterialPageRoute(builder: (_) => const SettingsScreen())),
            ),
            AnimatedBuilder(
              animation: AdService.instance,
              builder: (context, _) => AdService.instance.privacyOptionsRequired
                  ? ListTile(
                      leading: const Icon(Icons.privacy_tip_outlined),
                      title: const Text('Quyền riêng tư quảng cáo'),
                      trailing: AdService.instance.privacyOptionsOpen
                          ? const SizedBox(
                              width: 18,
                              height: 18,
                              child: CircularProgressIndicator(strokeWidth: 2))
                          : const Icon(Icons.chevron_right),
                      onTap: AdService.instance.privacyOptionsOpen
                          ? null
                          : () async {
                              final error =
                                  await AdService.instance.showPrivacyOptions();
                              if (!context.mounted || error == null) return;
                              ScaffoldMessenger.of(context)
                                  .showSnackBar(SnackBar(content: Text(error)));
                            },
                    )
                  : const SizedBox.shrink(),
            ),
            ExpansionTile(
              leading: const Icon(Icons.info_outline),
              title: const Text('Thông tin ứng dụng'),
              childrenPadding: const EdgeInsets.fromLTRB(16, 0, 16, 16),
              children: [
                const ListTile(
                    contentPadding: EdgeInsets.zero,
                    title: Text('GradeFlow Mobile'),
                    subtitle: Text('Chấm điểm trắc nghiệm')),
                ListTile(
                    contentPadding: EdgeInsets.zero,
                    title: const Text('Máy chủ'),
                    subtitle: Text(ApiConfig.baseUrl)),
              ],
            ),
          ])),
          if (auth.isAdmin) ...[
            const SizedBox(height: 12),
            Card(
                child: ExpansionTile(
              leading: const Icon(LucideIcons.shieldCheck),
              title: const Text('Quản trị'),
              children: [
                _adminEntry(context, LucideIcons.flaskConical,
                    'Kiểm tra chấm điểm', const AdminTestScreen()),
                _adminEntry(context, LucideIcons.database, 'Dữ liệu huấn luyện',
                    const AdminTrainingScreen()),
                _adminEntry(context, LucideIcons.users, 'Quản lý người dùng',
                    const AdminUsersScreen()),
              ],
            )),
          ],
          const SizedBox(height: 20),
          OutlinedButton.icon(
            onPressed: () => _confirmLogout(context, auth),
            icon: const Icon(LucideIcons.logOut, size: 18),
            label: const Text('Đăng xuất'),
            style: OutlinedButton.styleFrom(
                foregroundColor: Theme.of(context).colorScheme.error,
                minimumSize: const Size.fromHeight(48)),
          ),
        ],
      ),
    );
  }

  Widget _adminEntry(
          BuildContext context, IconData icon, String title, Widget screen) =>
      ListTile(
        leading: Icon(icon),
        title: Text(title),
        trailing: const Icon(Icons.chevron_right),
        onTap: () =>
            Navigator.push(context, MaterialPageRoute(builder: (_) => screen)),
      );

  void _confirmLogout(BuildContext context, AuthService auth) {
    showDialog<void>(
        context: context,
        builder: (ctx) => AlertDialog(
              title: const Text('Đăng xuất?'),
              content:
                  const Text('Bạn sẽ cần đăng nhập lại để tiếp tục sử dụng.'),
              actions: [
                TextButton(
                    onPressed: () => Navigator.pop(ctx),
                    child: const Text('Hủy')),
                TextButton(
                    onPressed: () {
                      Navigator.pop(ctx);
                      auth.logout();
                    },
                    child: const Text('Đăng xuất')),
              ],
            ));
  }
}
