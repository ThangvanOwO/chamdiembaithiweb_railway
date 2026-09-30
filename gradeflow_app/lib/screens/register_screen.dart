import 'package:flutter/material.dart';
import 'package:flutter/services.dart';
import 'package:google_fonts/google_fonts.dart';
import 'package:lucide_icons/lucide_icons.dart';
import 'package:provider/provider.dart';

import '../config/theme.dart';
import '../services/auth_service.dart';

class RegisterScreen extends StatefulWidget {
  const RegisterScreen({super.key});

  @override
  State<RegisterScreen> createState() => _RegisterScreenState();
}

class _RegisterScreenState extends State<RegisterScreen> {
  final _formKey = GlobalKey<FormState>();
  final _emailCtrl = TextEditingController();
  final _passwordCtrl = TextEditingController();
  final _confirmCtrl = TextEditingController();
  final _firstNameCtrl = TextEditingController();
  final _lastNameCtrl = TextEditingController();
  bool _obscure = true;
  String? _error;

  Future<void> _handleRegister() async {
    if (!_formKey.currentState!.validate()) return;
    if (_passwordCtrl.text != _confirmCtrl.text) {
      setState(() => _error = 'Mật khẩu xác nhận không khớp');
      return;
    }

    setState(() => _error = null);
    final error = await context.read<AuthService>().register(
          _emailCtrl.text.trim(),
          _passwordCtrl.text,
          _firstNameCtrl.text.trim(),
          _lastNameCtrl.text.trim(),
        );
    if (!mounted) return;
    if (error != null) {
      setState(() => _error = error);
    } else {
      Navigator.of(context).popUntil((route) => route.isFirst);
    }
  }

  @override
  void dispose() {
    _emailCtrl.dispose();
    _passwordCtrl.dispose();
    _confirmCtrl.dispose();
    _firstNameCtrl.dispose();
    _lastNameCtrl.dispose();
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
                SizedBox(height: 206, child: _buildHero()),
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
                                        'Tạo tài khoản',
                                        style: GoogleFonts.manrope(
                                          fontSize: 29,
                                          height: 1.1,
                                          fontWeight: FontWeight.w800,
                                          color: const Color(0xFF10233D),
                                        ),
                                      ),
                                    ),
                                    _badge('Miễn phí'),
                                  ],
                                ),
                                const SizedBox(height: 8),
                                Text(
                                  'Tạo tài khoản giáo viên để bắt đầu quản lý bài thi.',
                                  style: GoogleFonts.dmSans(
                                    fontSize: 15,
                                    color: const Color(0xFF64748B),
                                  ),
                                ),
                                const SizedBox(height: 22),
                                if (_error != null) ...[
                                  _errorBox(_error!),
                                  const SizedBox(height: 16),
                                ],
                                _label('HỌ VÀ TÊN'),
                                const SizedBox(height: 9),
                                Row(
                                  children: [
                                    Expanded(
                                      child: TextFormField(
                                        controller: _lastNameCtrl,
                                        textInputAction: TextInputAction.next,
                                        decoration: _fieldDecoration(
                                          hintText: 'Họ',
                                          icon: LucideIcons.user,
                                        ),
                                      ),
                                    ),
                                    const SizedBox(width: 12),
                                    Expanded(
                                      child: TextFormField(
                                        controller: _firstNameCtrl,
                                        textInputAction: TextInputAction.next,
                                        decoration: _fieldDecoration(
                                          hintText: 'Tên',
                                          icon: LucideIcons.user,
                                        ),
                                      ),
                                    ),
                                  ],
                                ),
                                const SizedBox(height: 18),
                                _label('EMAIL / TÊN ĐĂNG NHẬP'),
                                const SizedBox(height: 9),
                                TextFormField(
                                  controller: _emailCtrl,
                                  keyboardType: TextInputType.emailAddress,
                                  textInputAction: TextInputAction.next,
                                  decoration: _fieldDecoration(
                                    hintText: 'email@truonghoc.edu.vn',
                                    icon: LucideIcons.mail,
                                  ),
                                  validator: (value) {
                                    if (value == null || value.trim().isEmpty) {
                                      return 'Vui lòng nhập email';
                                    }
                                    return value.contains('@')
                                        ? null
                                        : 'Email không hợp lệ';
                                  },
                                ),
                                const SizedBox(height: 18),
                                _label('MẬT KHẨU'),
                                const SizedBox(height: 9),
                                TextFormField(
                                  controller: _passwordCtrl,
                                  obscureText: _obscure,
                                  textInputAction: TextInputAction.next,
                                  decoration: _fieldDecoration(
                                    hintText: 'Ít nhất 6 ký tự',
                                    icon: LucideIcons.lock,
                                    suffix: _visibilityButton(),
                                  ),
                                  validator: (value) => value == null ||
                                          value.length < 6
                                      ? 'Mật khẩu ít nhất 6 ký tự'
                                      : null,
                                ),
                                const SizedBox(height: 18),
                                _label('XÁC NHẬN MẬT KHẨU'),
                                const SizedBox(height: 9),
                                TextFormField(
                                  controller: _confirmCtrl,
                                  obscureText: _obscure,
                                  textInputAction: TextInputAction.done,
                                  onFieldSubmitted: (_) => _handleRegister(),
                                  decoration: _fieldDecoration(
                                    hintText: 'Nhập lại mật khẩu',
                                    icon: LucideIcons.shieldCheck,
                                    suffix: _visibilityButton(),
                                  ),
                                  validator: (value) => value != _passwordCtrl.text
                                      ? 'Mật khẩu không khớp'
                                      : null,
                                ),
                                const SizedBox(height: 24),
                                SizedBox(
                                  height: 58,
                                  child: ElevatedButton(
                                    onPressed: auth.isLoading
                                        ? null
                                        : _handleRegister,
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
                                                'Tạo tài khoản',
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
                                const Divider(color: Color(0xFFE7EDF4)),
                                const SizedBox(height: 14),
                                Row(
                                  mainAxisAlignment: MainAxisAlignment.center,
                                  children: [
                                    Text(
                                      'Đã có tài khoản? ',
                                      style: GoogleFonts.dmSans(
                                        fontSize: 14,
                                        color: const Color(0xFF475569),
                                      ),
                                    ),
                                    TextButton(
                                      onPressed: () => Navigator.pop(context),
                                      child: Text(
                                        'Đăng nhập ngay',
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

  Widget _buildHero() => Stack(
        children: [
          Positioned(
            left: 10,
            top: 4,
            child: IconButton(
              tooltip: 'Quay lại đăng nhập',
              onPressed: () => Navigator.pop(context),
              icon: const Icon(LucideIcons.arrowLeft, color: Colors.white),
            ),
          ),
          Align(
            alignment: Alignment.bottomCenter,
            child: Column(
              mainAxisSize: MainAxisSize.min,
              children: [
                Container(
                  width: 68,
                  height: 68,
                  decoration: BoxDecoration(
                    color: Colors.white.withValues(alpha: 0.16),
                    borderRadius: BorderRadius.circular(23),
                    border:
                        Border.all(color: Colors.white.withValues(alpha: 0.30)),
                  ),
                  child: const Icon(
                    LucideIcons.graduationCap,
                    color: Color(0xFF9FF5E4),
                    size: 36,
                  ),
                ),
                const SizedBox(height: 10),
                Text(
                  'GradeFlow',
                  style: GoogleFonts.manrope(
                    fontSize: 27,
                    fontWeight: FontWeight.w800,
                    color: Colors.white,
                  ),
                ),
                const SizedBox(height: 17),
              ],
            ),
          ),
        ],
      );

  Widget _badge(String text) => Container(
        padding: const EdgeInsets.symmetric(horizontal: 12, vertical: 7),
        decoration: BoxDecoration(
          color: const Color(0xFFECFDF5),
          borderRadius: BorderRadius.circular(24),
          border: Border.all(color: const Color(0xFF99F6D0)),
        ),
        child: Text(
          text,
          style: GoogleFonts.dmSans(
            color: const Color(0xFF047857),
            fontWeight: FontWeight.w800,
          ),
        ),
      );

  Widget _label(String text) => Text(
        text,
        style: GoogleFonts.manrope(
          fontSize: 13,
          fontWeight: FontWeight.w800,
          color: const Color(0xFF22344D),
          letterSpacing: 0.2,
        ),
      );

  Widget _errorBox(String message) => Container(
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

  Widget _visibilityButton() => IconButton(
        tooltip: _obscure ? 'Hiện mật khẩu' : 'Ẩn mật khẩu',
        onPressed: () => setState(() => _obscure = !_obscure),
        icon: Icon(
          _obscure ? LucideIcons.eyeOff : LucideIcons.eye,
          color: const Color(0xFF94A3B8),
        ),
      );

  InputDecoration _fieldDecoration({
    required String hintText,
    required IconData icon,
    Widget? suffix,
  }) =>
      InputDecoration(
        hintText: hintText,
        prefixIcon: Icon(icon, size: 20, color: const Color(0xFF94A3B8)),
        suffixIcon: suffix,
        filled: true,
        fillColor: const Color(0xFFF8FAFC),
        contentPadding: const EdgeInsets.symmetric(horizontal: 17, vertical: 17),
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
}
