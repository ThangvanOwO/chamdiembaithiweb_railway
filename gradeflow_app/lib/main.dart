import 'package:flutter/material.dart';
import 'package:flutter/services.dart';
import 'package:provider/provider.dart';

import 'config/api_config.dart';
import 'config/theme.dart';
import 'services/auth_service.dart';
import 'services/ad_service.dart';
import 'services/idle_detector.dart';
import 'screens/login_screen.dart';
import 'screens/main_shell.dart';
import 'screens/onboarding_screen.dart';

void main() async {
  WidgetsFlutterBinding.ensureInitialized();

  SystemChrome.setSystemUIOverlayStyle(const SystemUiOverlayStyle(
    statusBarColor: Colors.transparent,
    statusBarIconBrightness: Brightness.dark,
  ));

  await SystemChrome.setPreferredOrientations([
    DeviceOrientation.portraitUp,
    DeviceOrientation.portraitDown,
  ]);

  await ApiConfig.loadCustomBaseUrl();

  final authService = AuthService();
  await authService.loadToken();
  final seenOnboarding = await OnboardingScreen.hasSeenOnboarding();

  runApp(
    ChangeNotifierProvider<AuthService>.value(
      value: authService,
      child: GradeFlowApp(showOnboarding: !seenOnboarding),
    ),
  );
}

class GradeFlowApp extends StatefulWidget {
  final bool showOnboarding;
  const GradeFlowApp({super.key, required this.showOnboarding});

  @override
  State<GradeFlowApp> createState() => _GradeFlowAppState();
}

class _GradeFlowAppState extends State<GradeFlowApp> {
  late bool _showOnboarding;

  @override
  void initState() {
    super.initState();
    _showOnboarding = widget.showOnboarding;
    WidgetsBinding.instance.addPostFrameCallback((_) {
      if (mounted) AdService.instance.initializeConsent();
    });
  }

  void _finishOnboarding() {
    setState(() => _showOnboarding = false);
  }

  @override
  Widget build(BuildContext context) {
    return MaterialApp(
      title: 'GradeFlow',
      debugShowCheckedModeBanner: false,
      theme: GradeFlowTheme.lightTheme,
      navigatorObservers: [AdService.instance.navigationObserver],
      home: _showOnboarding
          ? OnboardingScreen(onDone: _finishOnboarding)
          : Consumer<AuthService>(
              builder: (context, auth, _) {
                if (auth.isAuthenticated) {
                  return IdleDetector(
                    tokenProvider: () => auth.token ?? '',
                    child: const MainShell(),
                  );
                }
                return const LoginScreen();
              },
            ),
    );
  }
}
