import 'package:flutter/material.dart';
import 'package:flutter/services.dart';
import 'package:google_fonts/google_fonts.dart';
import 'package:http/http.dart' as http;
import 'package:lucide_icons/lucide_icons.dart';
import 'package:provider/provider.dart';

import '../config/api_config.dart';
import '../config/theme.dart';
import '../services/auth_service.dart';
import 'register_screen.dart';

class LoginScreen extends StatefulWidget {
  const LoginScreen({super.key});

  @override
  State<LoginScreen> createState() => _LoginScreenState();
}

class _LoginScreenState extends State<LoginScreen> {
  final _emailController = TextEditingController();
  final _passwordController = TextEditingController();
  final _formKey = GlobalKey<FormState>();
  bool _obscurePassword = true;
  bool _rememberMe = true;
  String? _errorMessage;

  Future<void> _handleLogin() async {
    if (!_formKey.currentState!.validate()) return;
    setState(() => _errorMessage = null);
    final error = await context.read<AuthService>().login(
          _emailController.text.trim(),
          _passwordController.text,
        );
    if (error != null && mounted) setState(() => _errorMessage = error);
  }

  @override
  void dispose() {
    _emailController.dispose();
    _passwordController.dispose();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) {
    final auth = context.watch<AuthService>();
    return AnnotatedRegion<SystemUiOverlayStyle>(
      value: SystemUiOverlayStyle.light,
      child: Scaffold(
        resizeToAvoidBottomInset: true,
        backgroundColor: GradeFlowTheme.primary,
        body: Container(
          decoration: const BoxDecoration(
            gradient: LinearGradient(
              begin: Alignment.topLeft,
              end: Alignment.bottomRight,
              colors: [Color(0xFF064E4A), GradeFlowTheme.primary],
            ),
          ),
          child: SafeArea(
            bottom: false,
            child: Column(
              children: [
                SizedBox(height: 230, child: _buildHero()),
                Expanded(
                  child: Container(
                    width: double.infinity,
                    decoration: const BoxDecoration(
                      color: Colors.white,
                      borderRadius:
                          BorderRadius.vertical(top: Radius.circular(36)),
                    ),
                    child: SingleChildScrollView(
                      keyboardDismissBehavior:
                          ScrollViewKeyboardDismissBehavior.onDrag,
                      padding: const EdgeInsets.fromLTRB(28, 30, 28, 28),
                      child: Center(
                        child: ConstrainedBox(
                          constraints: const BoxConstraints(maxWidth: 520),
                          child: Form(
                            key: _formKey,
                            child: Column(
                              crossAxisAlignment: CrossAxisAlignment.stretch,
                              children: [
                                Row(
                                  children: [
                                    Expanded(
                                      child: Text(
                                        'Đăng nhập',
                                        style: GoogleFonts.manrope(
                                          fontSize: 30,
                                          height: 1.1,
                                          fontWeight: FontWeight.w800,
                                          color: const Color(0xFF10233D),
                                        ),
                                      ),
                                    ),
                                    _buildBadge('v2.4 Pro'),
                                  ],
                                ),
                                const SizedBox(height: 8),
                                Text(
                                  'Nhập thông tin tài khoản giáo viên hoặc nhà trường',
                                  style: GoogleFonts.dmSans(
                                    fontSize: 15,
                                    color: const Color(0xFF64748B),
                                  ),
                                ),
                                const SizedBox(height: 24),
                                if (_errorMessage != null) ...[
                                  _buildError(_errorMessage!),
                                  const SizedBox(height: 16),
                                ],
                                _fieldLabel('EMAIL / TÊN ĐĂNG NHẬP'),
                                const SizedBox(height: 9),
                                TextFormField(
                                  controller: _emailController,
                                  keyboardType: TextInputType.emailAddress,
                                  textInputAction: TextInputAction.next,
                                  decoration: _fieldDecoration(
                                    hintText: 'email@truonghoc.edu.vn',
                                    icon: LucideIcons.mail,
                                  ),
                                  validator: (value) =>
                                      value == null || value.trim().isEmpty
                                          ? 'Vui lòng nhập email'
                                          : null,
                                ),
                                const SizedBox(height: 18),
                                _fieldLabel('MẬT KHẨU'),
                                const SizedBox(height: 9),
                                TextFormField(
                                  controller: _passwordController,
                                  obscureText: _obscurePassword,
                                  textInputAction: TextInputAction.done,
                                  onFieldSubmitted: (_) => _handleLogin(),
                                  decoration: _fieldDecoration(
                                    hintText: 'Nhập mật khẩu',
                                    icon: LucideIcons.lock,
                                    suffix: IconButton(
                                      tooltip: _obscurePassword
                                          ? 'Hiện mật khẩu'
                                          : 'Ẩn mật khẩu',
                                      onPressed: () => setState(() =>
                                          _obscurePassword =
                                              !_obscurePassword),
                                      icon: Icon(
                                        _obscurePassword
                                            ? LucideIcons.eyeOff
                                            : LucideIcons.eye,
                                        color: const Color(0xFF94A3B8),
                                      ),
                                    ),
                                  ),
                                  validator: (value) => value == null ||
                                          value.isEmpty
                                      ? 'Vui lòng nhập mật khẩu'
                                      : null,
                                ),
                                const SizedBox(height: 8),
                                Row(
                                  children: [
                                    Checkbox(
                                      value: _rememberMe,
                                      activeColor: GradeFlowTheme.primary,
                                      onChanged: (value) => setState(
                                        () => _rememberMe = value ?? false,
                                      ),
                                    ),
                                    Text(
                                      'Ghi nhớ đăng nhập',
                                      style: GoogleFonts.dmSans(
                                        fontSize: 14,
                                        color: const Color(0xFF475569),
                                      ),
                                    ),
                                    const Spacer(),
                                    TextButton(
                                      onPressed: () => ScaffoldMessenger.of(context)
                                          .showSnackBar(const SnackBar(
                                        content: Text(
                                          'Hãy liên hệ quản trị viên để đặt lại mật khẩu.',
                                        ),
                                      )),
                                      child: Text(
                                        'Quên mật khẩu?',
                                        style: GoogleFonts.dmSans(
                                          fontWeight: FontWeight.w700,
                                          color: GradeFlowTheme.primary,
                                        ),
                                      ),
                                    ),
                                  ],
                                ),
                                const SizedBox(height: 16),
                                SizedBox(
                                  height: 58,
                                  child: ElevatedButton(
                                    onPressed: auth.isLoading
                                        ? null
                                        : _handleLogin,
                                    style: ElevatedButton.styleFrom(
                                      elevation: 8,
                                      shadowColor: GradeFlowTheme.primary
                                          .withValues(alpha: 0.30),
                                      shape: RoundedRectangleBorder(
                                        borderRadius: BorderRadius.circular(18),
                                      ),
                                    ),
                                    child: auth.isLoading
                                        ? const SizedBox(
                                            width: 24,
                                            height: 24,
                                            child: CircularProgressIndicator(
                                              strokeWidth: 2.4,
                                              color: Colors.white,
                                            ),
                                          )
                                        : Row(
                                            mainAxisAlignment:
                                                MainAxisAlignment.center,
                                            children: [
                                              Text(
                                                'Đăng nhập ngay',
                                                style: GoogleFonts.manrope(
                                                  fontSize: 17,
                                                  fontWeight: FontWeight.w800,
                                                ),
                                              ),
                                              const SizedBox(width: 12),
                                              const Icon(LucideIcons.arrowRight,
                                                  size: 24),
                                            ],
                                          ),
                                  ),
                                ),
                                const SizedBox(height: 26),
                                _buildDivider(),
                                const SizedBox(height: 20),
                                SizedBox(
                                  height: 54,
                                  child: OutlinedButton.icon(
                                    onPressed: () => ScaffoldMessenger.of(context)
                                        .showSnackBar(const SnackBar(
                                      content: Text(
                                        'Đăng nhập Google sẽ sớm khả dụng.',
                                      ),
                                    )),
                                    icon: const Icon(LucideIcons.chrome,
                                        color: Color(0xFF4285F4)),
                                    label: Text(
                                      'Tài khoản Google Giáo dục',
                                      style: GoogleFonts.dmSans(
                                        fontSize: 15,
                                        fontWeight: FontWeight.w700,
                                        color: const Color(0xFF243B5A),
                                      ),
                                    ),
                                    style: OutlinedButton.styleFrom(
                                      side: const BorderSide(
                                        color: Color(0xFFD8E1EE),
                                      ),
                                      shape: RoundedRectangleBorder(
                                        borderRadius: BorderRadius.circular(16),
                                      ),
                                    ),
                                  ),
                                ),
                                const SizedBox(height: 34),
                                const Divider(color: Color(0xFFE7EDF4)),
                                const SizedBox(height: 20),
                                Row(
                                  mainAxisAlignment: MainAxisAlignment.center,
                                  children: [
                                    Text(
                                      'Chưa có tài khoản? ',
                                      style: GoogleFonts.dmSans(
                                        fontSize: 14,
                                        color: const Color(0xFF475569),
                                      ),
                                    ),
                                    TextButton(
                                      onPressed: () => Navigator.push(
                                        context,
                                        MaterialPageRoute(
                                          builder: (_) => const RegisterScreen(),
                                        ),
                                      ),
                                      child: Text(
                                        'Đăng ký miễn phí',
                                        style: GoogleFonts.dmSans(
                                          fontSize: 14,
                                          fontWeight: FontWeight.w800,
                                          color: GradeFlowTheme.primary,
                                        ),
                                      ),
                                    ),
                                  ],
                                ),
                              ],
                            ),
                          ),
                        ),
                      ),
                    ),
                  ),
                ),
              ],
            ),
          ),
        ),
      ),
    );
  }

  Widget _buildHero() {
    final server = ApiConfig.baseUrl.replaceFirst(RegExp(r'^https?://'), '');
    return Stack(
      children: [
        Positioned(
          top: 8,
          right: 20,
          child: Material(
            color: Colors.transparent,
            child: InkWell(
              onTap: _showServerConfigDialog,
              borderRadius: BorderRadius.circular(28),
              child: Container(
                padding: const EdgeInsets.symmetric(horizontal: 14, vertical: 9),
                decoration: BoxDecoration(
                  color: Colors.white.withValues(alpha: 0.13),
                  borderRadius: BorderRadius.circular(28),
                  border: Border.all(color: Colors.white.withValues(alpha: 0.26)),
                ),
                child: Row(
                  mainAxisSize: MainAxisSize.min,
                  children: [
                    const Icon(LucideIcons.server,
                        size: 16, color: Colors.white),
                    const SizedBox(width: 8),
                    ConstrainedBox(
                      constraints: const BoxConstraints(maxWidth: 190),
                      child: Text(
                        server,
                        overflow: TextOverflow.ellipsis,
                        style: GoogleFonts.dmSans(
                          fontSize: 14,
                          fontWeight: FontWeight.w600,
                          color: Colors.white,
                        ),
                      ),
                    ),
                    const SizedBox(width: 8),
                    const Icon(LucideIcons.pencil,
                        size: 15, color: Color(0xFFBDF7E9)),
                  ],
                ),
              ),
            ),
          ),
        ),
        Align(
          alignment: Alignment.bottomCenter,
          child: Column(
            mainAxisSize: MainAxisSize.min,
            children: [
              Container(
                width: 72,
                height: 72,
                decoration: BoxDecoration(
                  color: Colors.white.withValues(alpha: 0.16),
                  borderRadius: BorderRadius.circular(24),
                  border: Border.all(color: Colors.white.withValues(alpha: 0.30)),
                ),
                child: const Icon(
                  LucideIcons.graduationCap,
                  color: Color(0xFF9FF5E4),
                  size: 39,
                ),
              ),
              const SizedBox(height: 12),
              Text(
                'GradeFlow',
                style: GoogleFonts.manrope(
                  fontSize: 29,
                  fontWeight: FontWeight.w800,
                  color: Colors.white,
                ),
              ),
              const SizedBox(height: 3),
              Text(
                'Giải pháp chấm thi & quản lý đề thi thông minh',
                textAlign: TextAlign.center,
                style: GoogleFonts.dmSans(
                  fontSize: 13,
                  color: const Color(0xFFBDF7E9),
                ),
              ),
              const SizedBox(height: 18),
            ],
          ),
        ),
      ],
    );
  }

  Widget _buildBadge(String label) => Container(
        padding: const EdgeInsets.symmetric(horizontal: 13, vertical: 7),
        decoration: BoxDecoration(
          color: const Color(0xFFECFDF5),
          borderRadius: BorderRadius.circular(24),
          border: Border.all(color: const Color(0xFF99F6D0)),
        ),
        child: Text(
          label,
          style: GoogleFonts.dmSans(
            color: const Color(0xFF047857),
            fontWeight: FontWeight.w800,
          ),
        ),
      );

  Widget _buildError(String message) => Container(
        padding: const EdgeInsets.all(14),
        decoration: BoxDecoration(
          color: const Color(0xFFFFF1F0),
          borderRadius: BorderRadius.circular(14),
          border: Border.all(color: const Color(0xFFFFD1CC)),
        ),
        child: Row(
          children: [
            const Icon(LucideIcons.alertCircle,
                size: 19, color: GradeFlowTheme.error),
            const SizedBox(width: 10),
            Expanded(
              child: Text(message,
                  style: GoogleFonts.dmSans(
                      fontSize: 13, color: GradeFlowTheme.error)),
            ),
          ],
        ),
      );

  Widget _fieldLabel(String label) => Text(
        label,
        style: GoogleFonts.manrope(
          fontSize: 13,
          fontWeight: FontWeight.w800,
          color: const Color(0xFF22344D),
          letterSpacing: 0.2,
        ),
      );

  InputDecoration _fieldDecoration({
    required String hintText,
    required IconData icon,
    Widget? suffix,
  }) =>
      InputDecoration(
        hintText: hintText,
        prefixIcon: Icon(icon, size: 21, color: const Color(0xFF94A3B8)),
        suffixIcon: suffix,
        filled: true,
        fillColor: const Color(0xFFF8FAFC),
        contentPadding: const EdgeInsets.symmetric(horizontal: 18, vertical: 18),
        enabledBorder: OutlineInputBorder(
          borderRadius: BorderRadius.circular(17),
          borderSide: const BorderSide(color: Color(0xFFD9E2EF)),
        ),
        focusedBorder: OutlineInputBorder(
          borderRadius: BorderRadius.circular(17),
          borderSide: const BorderSide(color: GradeFlowTheme.primary, width: 2),
        ),
        errorBorder: OutlineInputBorder(
          borderRadius: BorderRadius.circular(17),
          borderSide: const BorderSide(color: GradeFlowTheme.error),
        ),
      );

  Widget _buildDivider() => Row(
        children: [
          const Expanded(child: Divider(color: Color(0xFFD9E2EF))),
          Padding(
            padding: const EdgeInsets.symmetric(horizontal: 14),
            child: Text(
              'HOẶC TIẾP TỤC VỚI',
              style: GoogleFonts.dmSans(
                fontSize: 11,
                letterSpacing: 0.8,
                color: const Color(0xFF94A3B8),
              ),
            ),
          ),
          const Expanded(child: Divider(color: Color(0xFFD9E2EF))),
        ],
      );

  Future<void> _showServerConfigDialog() async {
    final controller = TextEditingController(text: ApiConfig.baseUrl);
    bool isTesting = false;
    String? testResult;
    bool? testSuccess;

    final route = DialogRoute<void>(
      context: context,
      builder: (dialogContext) => StatefulBuilder(
        builder: (dialogContext, setDialogState) => AlertDialog(
          shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(22)),
          title: Row(
            children: [
              const Icon(LucideIcons.server,
                  size: 20, color: GradeFlowTheme.primary),
              const SizedBox(width: 9),
              Text('Cấu hình máy chủ',
                  style: GoogleFonts.manrope(
                      fontSize: 18, fontWeight: FontWeight.w800)),
            ],
          ),
          content: Column(
            mainAxisSize: MainAxisSize.min,
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              Text(
                'Nhập địa chỉ IP Wi-Fi hoặc link Cloudflare Tunnel.',
                style: GoogleFonts.dmSans(
                    fontSize: 13, color: GradeFlowTheme.onSurfaceVariant),
              ),
              const SizedBox(height: 14),
              TextField(
                controller: controller,
                keyboardType: TextInputType.url,
                decoration: const InputDecoration(
                  hintText: 'VD: http://10.0.2.2:8000',
                  prefixIcon: Icon(LucideIcons.globe, size: 18),
                ),
              ),
              if (testResult != null) ...[
                const SizedBox(height: 12),
                Container(
                  padding: const EdgeInsets.all(10),
                  decoration: BoxDecoration(
                    color: (testSuccess ?? false)
                        ? GradeFlowTheme.successContainer
                        : GradeFlowTheme.errorContainer,
                    borderRadius: BorderRadius.circular(10),
                  ),
                  child: Row(
                    children: [
                      Icon(
                        (testSuccess ?? false)
                            ? LucideIcons.checkCircle2
                            : LucideIcons.alertCircle,
                        size: 17,
                        color: (testSuccess ?? false)
                            ? GradeFlowTheme.success
                            : GradeFlowTheme.error,
                      ),
                      const SizedBox(width: 8),
                      Expanded(
                        child: Text(testResult!,
                            style: GoogleFonts.dmSans(fontSize: 12)),
                      ),
                    ],
                  ),
                ),
              ],
            ],
          ),
          actions: [
            TextButton(
              onPressed: isTesting
                  ? null
                  : () async {
                      setDialogState(() {
                        isTesting = true;
                        testResult = 'Đang kiểm tra kết nối...';
                        testSuccess = null;
                      });
                      try {
                        var url = controller.text.trim();
                        if (url.endsWith('/')) url = url.substring(0, url.length - 1);
                        final response = await http
                            .get(Uri.parse('$url${ApiConfig.dashboard}'))
                            .timeout(const Duration(seconds: 4));
                        if (!dialogContext.mounted) return;
                        setDialogState(() {
                          isTesting = false;
                          testSuccess = [200, 401, 403]
                              .contains(response.statusCode);
                          testResult = testSuccess!
                              ? 'Kết nối thành công!'
                              : 'Máy chủ phản hồi mã ${response.statusCode}.';
                        });
                      } catch (_) {
                        if (!dialogContext.mounted) return;
                        setDialogState(() {
                          isTesting = false;
                          testSuccess = false;
                          testResult = 'Không thể kết nối. Kiểm tra IP và Wi-Fi.';
                        });
                      }
                    },
              child: isTesting
                  ? const SizedBox(
                      width: 16,
                      height: 16,
                      child: CircularProgressIndicator(strokeWidth: 2),
                    )
                  : const Text('Thử kết nối'),
            ),
            ElevatedButton(
              onPressed: () async {
                await ApiConfig.setCustomBaseUrl(controller.text.trim());
                if (!dialogContext.mounted) return;
                Navigator.pop(dialogContext);
                if (mounted) setState(() {});
              },
              child: const Text('Lưu'),
            ),
          ],
        ),
      ),
    );
    await Navigator.of(context, rootNavigator: true).push(route);
    // A popped dialog still uses its controller during the exit animation.
    await route.completed;
    controller.dispose();
  }
}
