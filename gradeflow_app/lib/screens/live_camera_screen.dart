import 'dart:async';
import 'package:camera/camera.dart';
import 'package:flutter/foundation.dart';
import 'package:flutter/material.dart';
import 'package:flutter/services.dart';
import '../services/live_marker_detector.dart';
import '../services/live_capture.dart';
import '../services/live_speed/capture_engine.dart';
import '../services/live_speed/engine_preference.dart';
export '../services/live_capture.dart' show LiveCapture;

// ----------------------------------------------------------------------
// 1. CẤU HÌNH TỌA ĐỘ VÀ TỈ LỆ 3:4
// Giảm sqSizeRatio 0.14→0.12: ROI nhỏ hơn = ít bắt nhầm vật thể xung quanh
// ----------------------------------------------------------------------
const double sqSizeRatio = liveMarkerRoiRatio;
const Map<String, Offset> cornerRatios = {
  'TL': Offset(0.015, 0.015),
  'TR': Offset(0.845, 0.015),
  'BL': Offset(0.015, 0.845),
  'BR': Offset(0.845, 0.845),
};

// ──────────────────────────────────────────────────────────────────────
// DETECTION THRESHOLDS — tất cả tham số nhạy cảm tập trung ở đây
// để dễ audit và chỉnh về sau.
// ──────────────────────────────────────────────────────────────────────

/// Throttle: chỉ xử lý 1 frame mỗi N milliseconds.
/// Observe up to 10 fps; readiness uses 500 ms, not a required frame count.
const int _kFrameThrottleMs = 100;

/// Geometry must remain comfortably inside the accepted range before it can
/// enter the temporal gate. This prevents marginal one-frame matches from
/// starting the capture sequence.
const double _kMinDetectionQuality = 0.62;

class AutoScanScreen extends StatefulWidget {
  // Import, batch and admin callers retain the stable engine by default.
  final bool allowSpeedTrial;
  const AutoScanScreen({super.key, this.allowSpeedTrial = false});

  @override
  State<AutoScanScreen> createState() => _AutoScanScreenState();
}

class _AutoScanScreenState extends State<AutoScanScreen>
    with WidgetsBindingObserver, SingleTickerProviderStateMixin {
  CameraController? _controller;
  bool _isDetecting = false;
  bool _isAligned = false;
  bool _isCapturing = false;
  bool _flashOn = false;
  double _stableProgress = 0;
  String? _errorMessage;
  String? _tiltWarning;
  String? _captureHint;
  final _captureRetry = LiveCaptureRetryPolicy();
  LiveCaptureEngine _captureEngine = LiveCaptureEngine.legacy;
  bool _engineChanging = false;
  bool _engineMenuOpen = false;

  Offset? _tapFocusOffset;
  bool _showFocusRing = false;

  late AnimationController _laserController;
  Uint8List? _freezeFrameBytes;

  Map<String, bool> _cornerMatched = {
    'TL': false,
    'TR': false,
    'BL': false,
    'BR': false,
  };
  List<Rect> _markerRectsInCorner = [];

  // ── Temporal Stability State ──────────────────────────────────────
  // Lưu vị trí marker từ frame trước để so sánh drift
  final _stability = LiveStabilityGate();
  final _streamClock = Stopwatch()..start();

  // ── Frame Throttle ────────────────────────────────────────────────
  int _lastProcessedMs = 0;
  bool _cameraInitializing = false;
  int _cameraGeneration = 0;
  bool _cameraPaused = false;
  int _lastDiagnosticMs = 0;
  int? _lastRotation;

  @override
  void initState() {
    super.initState();
    WidgetsBinding.instance.addObserver(this);
    _laserController = AnimationController(
      vsync: this,
      duration: const Duration(milliseconds: 400),
    );
    _initializeCaptureEngine();
  }

  Future<void> _initializeCaptureEngine() async {
    if (widget.allowSpeedTrial && !LiveEnginePreference.disabled) {
      try {
        _captureEngine = await LiveEnginePreference.read();
      } catch (error) {
        debugPrint('[LiveSpeed preference] read failed; using legacy: $error');
      }
    }
    if (mounted) _initCamera();
  }

  Future<void> _changeCaptureEngine(LiveCaptureEngine engine) async {
    if (_isCapturing || _engineChanging || !widget.allowSpeedTrial) return;
    setState(() {
      _engineMenuOpen = false;
      _engineChanging = true;
      _resetDetectionState();
    });
    try {
      await LiveEnginePreference.write(engine);
      if (mounted) {
        setState(() {
          _captureEngine = engine;
          _captureRetry.reset();
          _captureHint = engine == LiveCaptureEngine.legacy
              ? 'Đang dùng bộ xử lý ổn định.'
              : 'Đang thử tăng tốc marker. Cách chấm điểm không đổi.';
        });
      }
    } catch (error) {
      if (mounted) {
        setState(() =>
            _captureHint = 'Không đổi được bộ xử lý. Đang giữ lựa chọn cũ.');
      }
    } finally {
      if (mounted) setState(() => _engineChanging = false);
    }
  }

  Future<void> _useStableAfterNativeFailure() async {
    _captureEngine = LiveCaptureEngine.legacy;
    try {
      await LiveEnginePreference.write(LiveCaptureEngine.legacy);
    } catch (error) {
      debugPrint('[LiveSpeed fallback] using stable for this session; '
          'could not persist preference: $error');
    }
  }

  @override
  void didChangeAppLifecycleState(AppLifecycleState state) {
    if (state == AppLifecycleState.inactive ||
        state == AppLifecycleState.paused) {
      _pauseCamera();
    } else if (state == AppLifecycleState.resumed) {
      _cameraPaused = false;
      _initCamera();
    }
  }

  Future<void> _initCamera() async {
    if (_cameraInitializing || _isCapturing || _cameraPaused || !mounted) {
      return;
    }
    _cameraInitializing = true;
    final generation = ++_cameraGeneration;
    try {
      await _stopImageStream();
      final previous = _controller;
      _controller = null;
      await previous?.dispose();
      if (!mounted || _cameraPaused || generation != _cameraGeneration) return;
      setState(() {});
      final cameras = await availableCameras();
      if (cameras.isEmpty) {
        if (mounted) setState(() => _errorMessage = "Không tìm thấy camera!");
        return;
      }

      final camera = cameras.firstWhere(
        (item) => item.lensDirection == CameraLensDirection.back,
        orElse: () => cameras.first,
      );
      final controller = CameraController(
        camera,
        ResolutionPreset.veryHigh,
        enableAudio: false,
        imageFormatGroup: ImageFormatGroup.yuv420,
      );

      await controller.initialize();
      if (!mounted || _cameraPaused || generation != _cameraGeneration) {
        await controller.dispose();
        return;
      }
      _controller = controller;
      _resetDetectionState();
      setState(() => _errorMessage = null);
      await _startImageStream();
    } catch (e) {
      if (!mounted) return;
      setState(() => _errorMessage = "Lỗi Camera: $e");
    } finally {
      _cameraInitializing = false;
      if (mounted && !_cameraPaused && generation != _cameraGeneration) {
        unawaited(_initCamera());
      }
    }
  }

  Future<void> _pauseCamera() async {
    _cameraPaused = true;
    _cameraGeneration++;
    _resetDetectionState();
    await _stopImageStream();
  }

  Future<void> _startImageStream() async {
    final controller = _controller;
    if (controller == null ||
        !controller.value.isInitialized ||
        controller.value.isStreamingImages ||
        _isCapturing ||
        _cameraPaused) {
      return;
    }
    _isDetecting = false;
    _lastProcessedMs = 0;
    final generation = _cameraGeneration;
    await controller.startImageStream((CameraImage image) {
      final nowMs = _streamClock.elapsedMilliseconds;
      if (nowMs - _lastProcessedMs < _kFrameThrottleMs ||
          _isDetecting ||
          _isCapturing ||
          _engineChanging ||
          _engineMenuOpen ||
          _cameraPaused ||
          generation != _cameraGeneration) {
        return;
      }
      _lastProcessedMs = nowMs;
      _isDetecting = true;
      _processCameraImage(image, generation);
    });
  }

  Future<void> _stopImageStream() async {
    final controller = _controller;
    if (controller == null || !controller.value.isStreamingImages) return;
    try {
      await controller.stopImageStream();
    } catch (_) {}
  }

  void _resetDetectionState() {
    _isAligned = false;
    _stableProgress = 0;
    _stability.reset();
    _cornerMatched = {for (final key in liveMarkerKeys) key: false};
    _markerRectsInCorner = [];
  }

  Future<void> _processCameraImage(CameraImage image, int generation) async {
    try {
      if (image.format.group != ImageFormatGroup.yuv420 &&
          image.format.group != ImageFormatGroup.nv21) {
        throw StateError(
            'Unsupported live image format: ${image.format.group}');
      }
      final Plane yPlane = image.planes[0];
      // Camera plugins may reuse the platform buffer after the callback.
      // Copy before handing it to an isolate so a frame cannot mutate mid-read.
      final Uint8List yBytes = Uint8List.fromList(yPlane.bytes);
      final int rowStride = yPlane.bytesPerRow;
      final int sensorW = image.width;
      final int sensorH = image.height;
      final controller = _controller!;
      final deviceDegrees = switch (controller.value.deviceOrientation) {
        DeviceOrientation.portraitUp => 0,
        DeviceOrientation.landscapeLeft => 90,
        DeviceOrientation.portraitDown => 180,
        DeviceOrientation.landscapeRight => 270,
      };
      final rotation =
          (controller.description.sensorOrientation - deviceDegrees + 360) %
              360;
      if (_lastRotation != rotation) {
        _resetDetectionState();
        _lastRotation = rotation;
      }

      final Map<String, dynamic> result = await compute(detectLiveMarkers, {
        'yBytes': yBytes,
        'rowStride': rowStride,
        'sensorW': sensorW,
        'sensorH': sensorH,
        'rotationDegrees': rotation,
        'pixelStride': yPlane.bytesPerPixel ?? 1,
        'sqSizeRatio': sqSizeRatio,
        'corners': liveMarkerCornerRatios,
      });

      if (!mounted ||
          _isCapturing ||
          _engineChanging ||
          _engineMenuOpen ||
          generation != _cameraGeneration) {
        return;
      }
      final now = DateTime.now().millisecondsSinceEpoch;
      if (now - _lastDiagnosticMs >= 2000) {
        _lastDiagnosticMs = now;
        debugPrint('[LiveCamera v2] ${sensorW}x$sensorH rotation=$rotation '
            'stride=$rowStride match=${result['match']} reason=${result['rejectReason']}');
      }

      final bool isMatch = result['match'] == true &&
          ((result['quality'] as num?)?.toDouble() ?? 0.0) >=
              _kMinDetectionQuality;
      final String? tilt = result['tilt'] as String?;
      final Map<String, dynamic> rawMatched =
          result['matchedCorners'] as Map<String, dynamic>;
      final Map<String, bool> cornerMatched = rawMatched.map(
        (k, v) => MapEntry(k, v as bool),
      );

      // ── Giải mã marker rects ──────────────────────────────────────
      final List<dynamic> rawMarkers = result['markers'] as List<dynamic>;
      List<Rect> cornerMarkers = [];
      for (int i = 0; i < rawMarkers.length; i += 4) {
        if (i + 3 < rawMarkers.length) {
          cornerMarkers.add(Rect.fromLTWH(
            (rawMarkers[i] as num).toDouble(),
            (rawMarkers[i + 1] as num).toDouble(),
            (rawMarkers[i + 2] as num).toDouble(),
            (rawMarkers[i + 3] as num).toDouble(),
          ));
        }
      }

      // ── Giải mã vị trí tâm marker (để kiểm tra temporal drift) ──
      final List<dynamic>? rawCenters =
          result['markerCentersLogical'] as List<dynamic>?;
      Map<String, Offset>? currentCenters;
      if (rawCenters != null &&
          rawCenters.length == 8 &&
          rawCenters.every((value) => (value as num).toDouble() >= 0)) {
        currentCenters = {};
        for (int i = 0; i < 4; i++) {
          currentCenters[liveMarkerKeys[i]] = Offset(
            (rawCenters[i * 2] as num).toDouble(),
            (rawCenters[i * 2 + 1] as num).toDouble(),
          );
        }
      }

      setState(() {
        _cornerMatched = cornerMatched;
        _markerRectsInCorner = cornerMarkers;
        _tiltWarning = tilt;
      });

      final logicalWidth =
          rotation == 90 || rotation == 270 ? sensorH : sensorW;
      final normalized = isMatch && currentCenters != null
          ? [
              for (final key in liveMarkerKeys) ...[
                currentCenters[key]!.dx / logicalWidth,
                currentCenters[key]!.dy / logicalWidth
              ]
            ]
          : null;
      final ready =
          _stability.observe(normalized, _streamClock.elapsedMilliseconds);
      setState(() {
        _stableProgress = _stability.progress;
        _isAligned = _stability.aligned;
      });
      if (ready &&
          !_isCapturing &&
          _captureRetry.canAttempt(
              manual: false, nowMs: _streamClock.elapsedMilliseconds)) {
        await _capturePhoto(manual: false);
      }
    } catch (e, stack) {
      if (generation == _cameraGeneration && mounted) {
        setState(_resetDetectionState);
        final now = DateTime.now().millisecondsSinceEpoch;
        if (now - _lastDiagnosticMs >= 2000) {
          _lastDiagnosticMs = now;
          debugPrint('[LiveCamera v2] $e\n$stack');
        }
      }
    } finally {
      if (generation == _cameraGeneration) _isDetecting = false;
    }
  }

  Future<void> _onTapToFocus(
      TapDownDetails details, BoxConstraints constraints) async {
    if (_controller == null || !_controller!.value.isInitialized) return;
    final double dx =
        (details.localPosition.dx / constraints.maxWidth).clamp(0.0, 1.0);
    final double dy =
        (details.localPosition.dy / constraints.maxHeight).clamp(0.0, 1.0);

    setState(() {
      _tapFocusOffset = details.localPosition;
      _showFocusRing = true;
    });
    Future.delayed(const Duration(milliseconds: 800), () {
      if (mounted) setState(() => _showFocusRing = false);
    });

    try {
      await _controller!.setFocusPoint(Offset(dx, dy));
      await _controller!.setExposurePoint(Offset(dx, dy));
      await _controller!.setFocusMode(FocusMode.auto);
      await _controller!.setExposureMode(ExposureMode.auto);
    } catch (_) {}
  }

  Future<void> _capturePhoto({bool manual = true}) async {
    if (_isCapturing ||
        _cameraPaused ||
        _controller == null ||
        !_controller!.value.isInitialized) {
      return;
    }
    if (_engineChanging ||
        _engineMenuOpen ||
        !_stability.canCapture(manual: manual)) {
      return;
    }
    if (!_captureRetry.canAttempt(
        manual: manual, nowMs: _streamClock.elapsedMilliseconds)) {
      return;
    }
    final captureClock = Stopwatch()..start();
    final generation = ++_cameraGeneration;
    final controller = _controller!;
    setState(() {
      _isCapturing = true;
      _captureHint = null;
    });
    _laserController.repeat(reverse: true);

    // Phản hồi xúc giác rung và âm thanh chụp
    try {
      SystemSound.play(SystemSoundType.click);
    } catch (_) {}

    try {
      if (_controller != null && _controller!.value.isStreamingImages) {
        await _controller!.stopImageStream();
      }
      if (!mounted || _cameraPaused || generation != _cameraGeneration) return;

      final file = await controller.takePicture();
      final shutterMs = captureClock.elapsedMilliseconds;
      print("📸 Đã chụp: ${file.path}");

      final rawBytes = await file.readAsBytes();
      if (mounted) {
        setState(() {
          _freezeFrameBytes = rawBytes;
        });
      }

      // The legacy call stays exactly as before for all non-trial callers.
      final LiveCapture capture;
      if (_captureEngine == LiveCaptureEngine.legacy) {
        capture = await compute(prepareLiveCapture, rawBytes);
      } else {
        final preparation = await compute(prepareLiveCaptureSelected,
            LivePreparationRequest(rawBytes, _captureEngine));
        capture = preparation.capture;
        debugPrint('[LiveSpeed timing] engine=${preparation.engine} '
            'us=${preparation.timingsUs} fallback=${preparation.fallbackReason}');
        if (preparation.fallbackReason != null && mounted) {
          await _useStableAfterNativeFailure();
        }
      }
      debugPrint('[LiveCamera timing] manual=$manual shutterMs=$shutterMs '
          'postCaptureMs=${captureClock.elapsedMilliseconds - shutterMs}');
      if (mounted && !_cameraPaused && generation == _cameraGeneration) {
        debugPrint('[LiveCamera v2] capture=${capture.width}x${capture.height} '
            'bytes=${capture.bytes.length} corners=${capture.corners}');
        Navigator.pop(context, capture);
      }
    } catch (e) {
      if (e is LivePreparationFailure) {
        debugPrint('[LiveSpeed failed] native=${e.nativeReason} '
            'stable=${e.stableReason} disableTrial=${e.disableTrial}');
        if (e.disableTrial) await _useStableAfterNativeFailure();
      }
      debugPrint('[LiveCamera capture rejected] manual=$manual '
          'elapsedMs=${captureClock.elapsedMilliseconds} '
          'reason=${e is LiveCaptureException ? e.diagnostic : e}');
      if (mounted && !_cameraPaused && generation == _cameraGeneration) {
        _captureRetry.failed(
            manual: manual, nowMs: _streamClock.elapsedMilliseconds);
        setState(() {
          _isCapturing = false;
          _freezeFrameBytes = null;
          _captureHint = e is FormatException
              ? e.message
              : 'Không chụp được ảnh. Chạm để lấy nét rồi chụp lại.';
          _resetDetectionState();
        });
        await _startImageStream();
      }
    } finally {
      if (mounted) {
        _laserController.stop();
        setState(() {
          _isCapturing = false;
          _freezeFrameBytes = null;
        });
        if (!_cameraPaused && generation != _cameraGeneration) {
          unawaited(_initCamera());
        }
      }
    }
  }

  Future<void> _toggleFlash() async {
    if (_controller == null || !_controller!.value.isInitialized) return;
    try {
      final newMode = _flashOn ? FlashMode.off : FlashMode.torch;
      await _controller!.setFlashMode(newMode);
      setState(() => _flashOn = !_flashOn);
    } catch (e) {
      print("Lỗi bật đèn flash: $e");
    }
  }

  @override
  void dispose() {
    WidgetsBinding.instance.removeObserver(this);
    _cameraGeneration++;
    _stopImageStream();
    _laserController.dispose();
    _controller?.dispose();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) {
    if (_errorMessage != null) {
      return Scaffold(
        backgroundColor: Colors.black,
        body: Center(
          child:
              Text(_errorMessage!, style: const TextStyle(color: Colors.red)),
        ),
      );
    }
    if (_controller == null || !_controller!.value.isInitialized) {
      return const Scaffold(
        backgroundColor: Colors.black,
        body: Center(child: CircularProgressIndicator(color: Colors.white)),
      );
    }

    final cameraSize = _controller!.value.previewSize!;

    return Scaffold(
      backgroundColor: Colors.black,
      body: SafeArea(
        child: Column(
          children: [
            // Top Bar: Thoát & Bật đèn Flash
            Padding(
              padding: const EdgeInsets.symmetric(horizontal: 16, vertical: 8),
              child: Row(
                mainAxisAlignment: MainAxisAlignment.spaceBetween,
                children: [
                  IconButton(
                    icon:
                        const Icon(Icons.close, color: Colors.white, size: 28),
                    onPressed: () => Navigator.pop(context),
                  ),
                  const Text(
                    "Quét phiếu thi",
                    style: TextStyle(
                      color: Colors.white,
                      fontSize: 18,
                      fontWeight: FontWeight.bold,
                    ),
                  ),
                  IconButton(
                    icon: Icon(
                      _flashOn ? Icons.flash_on : Icons.flash_off,
                      color: _flashOn ? Colors.amber : Colors.white,
                      size: 28,
                    ),
                    onPressed: _toggleFlash,
                  ),
                ],
              ),
            ),

            if (widget.allowSpeedTrial && !LiveEnginePreference.disabled)
              Padding(
                padding: const EdgeInsets.symmetric(horizontal: 16),
                child: PopupMenuButton<LiveCaptureEngine>(
                  enabled: !_isCapturing && !_engineChanging,
                  initialValue: _captureEngine,
                  onOpened: () => setState(() {
                    _engineMenuOpen = true;
                    _resetDetectionState();
                  }),
                  onCanceled: () => setState(() {
                    _engineMenuOpen = false;
                    _resetDetectionState();
                  }),
                  onSelected: _changeCaptureEngine,
                  itemBuilder: (_) => const [
                    PopupMenuItem(
                        value: LiveCaptureEngine.legacy,
                        child: Text('Ổn định — bộ xử lý cũ')),
                    PopupMenuItem(
                        value: LiveCaptureEngine.nativeMarkers,
                        child: Text('Thử nghiệm — tăng tốc marker')),
                  ],
                  child: Padding(
                    padding: const EdgeInsets.symmetric(vertical: 10),
                    child: Row(mainAxisSize: MainAxisSize.min, children: [
                      Icon(
                          _captureEngine == LiveCaptureEngine.legacy
                              ? Icons.verified_user_outlined
                              : Icons.speed,
                          size: 18,
                          color: Colors.white70),
                      const SizedBox(width: 8),
                      Flexible(
                          child: Text(
                              _captureEngine == LiveCaptureEngine.legacy
                                  ? 'Bộ xử lý: Ổn định'
                                  : 'Bộ xử lý: Tăng tốc thử nghiệm',
                              style: const TextStyle(
                                  color: Colors.white70, fontSize: 13))),
                      const Icon(Icons.expand_more, color: Colors.white70),
                    ]),
                  ),
                ),
              ),

            // Camera Preview (Tỉ lệ chuẩn 3:4)
            Expanded(
              child: Center(
                child: AspectRatio(
                  aspectRatio: 3 / 4,
                  child: Stack(
                    fit: StackFit.expand,
                    children: [
                      ClipRect(
                        child: FittedBox(
                          fit: BoxFit.cover,
                          child: SizedBox(
                            width: cameraSize.height,
                            height: cameraSize.width,
                            child: CameraPreview(_controller!),
                          ),
                        ),
                      ),

                      // Ảnh đóng băng ngay khi chụp (Freeze Frame không chớp màn hình)
                      if (_freezeFrameBytes != null)
                        Positioned.fill(
                          child: Image.memory(
                            _freezeFrameBytes!,
                            fit: BoxFit.cover,
                          ),
                        ),

                      LayoutBuilder(builder: (context, constraints) {
                        return GestureDetector(
                          behavior: HitTestBehavior.opaque,
                          onTapDown: (details) =>
                              _onTapToFocus(details, constraints),
                          child: CustomPaint(
                            size: Size(
                                constraints.maxWidth, constraints.maxHeight),
                            painter: _AzotaOverlayPainter(
                              screenW: constraints.maxWidth,
                              screenH: constraints.maxHeight,
                              isAligned: _isAligned,
                              cornerMatched: _cornerMatched,
                              markerRectsInCorner: _markerRectsInCorner,
                              stableProgress: _stableProgress,
                            ),
                          ),
                        );
                      }),

                      // Hiệu ứng tia Laser quét dọc (Scanner Animation) khi đang chụp và chấm
                      if (_isCapturing)
                        Positioned.fill(
                          child: LayoutBuilder(
                            builder: (context, constraints) {
                              return AnimatedBuilder(
                                animation: _laserController,
                                builder: (context, child) {
                                  return Stack(
                                    children: [
                                      // Dải quét laser sáng
                                      Positioned(
                                        top: (constraints.maxHeight - 40) *
                                            _laserController.value,
                                        left: 0,
                                        right: 0,
                                        child: Container(
                                          height: 40,
                                          decoration: BoxDecoration(
                                            gradient: LinearGradient(
                                              begin: Alignment.topCenter,
                                              end: Alignment.bottomCenter,
                                              colors: [
                                                Colors.transparent,
                                                Colors.cyanAccent
                                                    .withValues(alpha: 0.3),
                                                Colors.cyanAccent,
                                                Colors.cyanAccent
                                                    .withValues(alpha: 0.3),
                                                Colors.transparent,
                                              ],
                                              stops: const [
                                                0.0,
                                                0.35,
                                                0.5,
                                                0.65,
                                                1.0
                                              ],
                                            ),
                                          ),
                                        ),
                                      ),
                                      // Khung viền sáng neon
                                      Positioned.fill(
                                        child: Container(
                                          decoration: BoxDecoration(
                                            border: Border.all(
                                              color: Colors.cyanAccent
                                                  .withValues(alpha: 0.6),
                                              width: 3,
                                            ),
                                          ),
                                        ),
                                      ),
                                      // Badge HUD trạng thái "Đang quét..."
                                      Positioned(
                                        bottom: 24,
                                        left: 24,
                                        right: 24,
                                        child: Center(
                                          child: Container(
                                            padding: const EdgeInsets.symmetric(
                                                horizontal: 20, vertical: 10),
                                            decoration: BoxDecoration(
                                              color: Colors.black
                                                  .withValues(alpha: 0.85),
                                              borderRadius:
                                                  BorderRadius.circular(30),
                                              border: Border.all(
                                                  color: Colors.cyanAccent
                                                      .withValues(alpha: 0.8),
                                                  width: 1.5),
                                              boxShadow: [
                                                BoxShadow(
                                                  color: Colors.cyanAccent
                                                      .withValues(alpha: 0.35),
                                                  blurRadius: 14,
                                                  spreadRadius: 2,
                                                ),
                                              ],
                                            ),
                                            child: Row(
                                              mainAxisSize: MainAxisSize.min,
                                              children: [
                                                SizedBox(
                                                  width: 18,
                                                  height: 18,
                                                  child:
                                                      CircularProgressIndicator(
                                                    strokeWidth: 2.5,
                                                    valueColor:
                                                        AlwaysStoppedAnimation<
                                                                Color>(
                                                            Colors.cyanAccent),
                                                  ),
                                                ),
                                                SizedBox(width: 12),
                                                Text(
                                                  _freezeFrameBytes == null
                                                      ? "Đang chụp..."
                                                      : "Đã chụp — đang kiểm tra ảnh...",
                                                  style: TextStyle(
                                                    color: Colors.white,
                                                    fontSize: 15,
                                                    fontWeight: FontWeight.bold,
                                                    letterSpacing: 0.5,
                                                  ),
                                                ),
                                              ],
                                            ),
                                          ),
                                        ),
                                      ),
                                    ],
                                  );
                                },
                              );
                            },
                          ),
                        ),

                      // Hiệu ứng vòng tròn chạm để lấy nét (Tap to focus)
                      if (_showFocusRing && _tapFocusOffset != null)
                        Positioned(
                          left: _tapFocusOffset!.dx - 28,
                          top: _tapFocusOffset!.dy - 28,
                          child: IgnorePointer(
                            child: Container(
                              width: 56,
                              height: 56,
                              decoration: BoxDecoration(
                                shape: BoxShape.circle,
                                border: Border.all(
                                    color: Colors.amberAccent, width: 2.5),
                                boxShadow: [
                                  BoxShadow(
                                    color: Colors.amberAccent
                                        .withValues(alpha: 0.5),
                                    blurRadius: 8,
                                  ),
                                ],
                              ),
                            ),
                          ),
                        ),

                      // Cảnh báo nghiêng
                      if (_tiltWarning != null)
                        Positioned(
                          top: 16,
                          left: 8,
                          right: 8,
                          child: Text(
                            _tiltWarning!,
                            style: const TextStyle(
                              color: Colors.orange,
                              fontSize: 13,
                              fontWeight: FontWeight.bold,
                              shadows: [
                                Shadow(color: Colors.black, blurRadius: 4)
                              ],
                            ),
                            textAlign: TextAlign.center,
                          ),
                        ),

                      // Trạng thái giữ yên — hiển thị progress bar ổn định
                      Positioned(
                        bottom: 8,
                        left: 0,
                        right: 0,
                        child: !_isCapturing && _stableProgress > 0
                            ? _StabilityProgressBar(
                                progress: _stableProgress,
                              )
                            : const SizedBox.shrink(),
                      ),
                    ],
                  ),
                ),
              ),
            ),

            // Bottom Bar: Hướng dẫn + Nút Chụp Ảnh Thủ Công (Shutter Button)
            Padding(
              padding: const EdgeInsets.only(bottom: 24, top: 12),
              child: Column(
                mainAxisSize: MainAxisSize.min,
                children: [
                  Text(
                    _captureRetry.paused
                        ? 'Tạm dừng tự chụp — bạn vẫn có thể bấm chụp'
                        : _captureHint != null
                            ? 'Đang tìm lại góc để tự chụp'
                            : _isAligned
                                ? "🟢 Sẵn sàng — Đang tự động chụp"
                                : (_cornerMatched.values.any((m) => m)
                                    ? "🟡 Đang căn chỉnh (${_cornerMatched.values.where((m) => m).length}/4 góc)..."
                                    : "🔴 Đặt 4 góc phiếu thi vào khung hoặc chạm để chụp"),
                    style: TextStyle(
                      color: _isAligned
                          ? Colors.greenAccent
                          : (_cornerMatched.values.any((m) => m)
                              ? Colors.amberAccent
                              : Colors.white70),
                      fontSize: 14,
                      fontWeight: FontWeight.w600,
                    ),
                  ),
                  if (_captureHint != null)
                    Padding(
                      padding: const EdgeInsets.fromLTRB(16, 6, 16, 0),
                      child: Text(_captureHint!,
                          textAlign: TextAlign.center,
                          style: const TextStyle(
                              color: Colors.white70, fontSize: 12)),
                    ),
                  if (_captureRetry.paused)
                    TextButton(
                      onPressed: _isCapturing
                          ? null
                          : () {
                              setState(() {
                                _captureRetry.reset();
                                _captureHint = null;
                                _resetDetectionState();
                              });
                            },
                      child: const Text('Thử tự chụp lại'),
                    ),
                  const SizedBox(height: 14),

                  // Nút Chụp tròn to phong cách Azota / iOS Camera
                  GestureDetector(
                    onTap:
                        _isCapturing ? null : () => _capturePhoto(manual: true),
                    child: Container(
                      width: 76,
                      height: 76,
                      decoration: BoxDecoration(
                        shape: BoxShape.circle,
                        border: Border.all(color: Colors.white, width: 4),
                        color: Colors.white.withValues(alpha: 0.15),
                      ),
                      child: Center(
                        child: Container(
                          width: 60,
                          height: 60,
                          decoration: const BoxDecoration(
                            shape: BoxShape.circle,
                            color: Colors.white,
                          ),
                          child: _isCapturing
                              ? const Padding(
                                  padding: EdgeInsets.all(14),
                                  child: CircularProgressIndicator(
                                    strokeWidth: 3,
                                    valueColor: AlwaysStoppedAnimation<Color>(
                                        Colors.blueAccent),
                                  ),
                                )
                              : null,
                        ),
                      ),
                    ),
                  ),
                ],
              ),
            ),
          ],
        ),
      ),
    );
  }
}

// ----------------------------------------------------------------------
// Progress bar hiển thị tiến trình ổn định frame
// ----------------------------------------------------------------------
class _StabilityProgressBar extends StatelessWidget {
  final double progress; // 0.0 → 1.0

  const _StabilityProgressBar({required this.progress});

  @override
  Widget build(BuildContext context) {
    final clamped = progress.clamp(0.0, 1.0);
    return Padding(
      padding: const EdgeInsets.symmetric(horizontal: 24),
      child: Column(
        mainAxisSize: MainAxisSize.min,
        children: [
          Text(
            "Đang xác nhận 4 góc — ${(clamped * 0.5).toStringAsFixed(1)}/0.5 giây",
            style: const TextStyle(
              color: Colors.greenAccent,
              fontSize: 13,
              fontWeight: FontWeight.bold,
              shadows: [Shadow(color: Colors.black, blurRadius: 4)],
            ),
            textAlign: TextAlign.center,
          ),
          const SizedBox(height: 4),
          ClipRRect(
            borderRadius: BorderRadius.circular(4),
            child: LinearProgressIndicator(
              value: clamped,
              minHeight: 5,
              backgroundColor: Colors.white24,
              valueColor:
                  const AlwaysStoppedAnimation<Color>(Colors.greenAccent),
            ),
          ),
        ],
      ),
    );
  }
}

// ----------------------------------------------------------------------
// 4. LỚP VẼ UI
// ----------------------------------------------------------------------
class _AzotaOverlayPainter extends CustomPainter {
  final double screenW;
  final double screenH;
  final bool isAligned;
  final Map<String, bool> cornerMatched;
  final List<Rect> markerRectsInCorner;
  final double stableProgress; // 0.0→1.0 để vẽ viền dày dần

  _AzotaOverlayPainter({
    required this.screenW,
    required this.screenH,
    required this.isAligned,
    this.cornerMatched = const {},
    this.markerRectsInCorner = const [],
    this.stableProgress = 0.0,
  });

  @override
  void paint(Canvas canvas, Size size) {
    final int matchedCount =
        isAligned ? 4 : cornerMatched.values.where((m) => m).length;
    final Color guideColor = isAligned
        ? Colors.greenAccent
        : (matchedCount > 0
            ? Colors.amberAccent
            : Colors.redAccent.withValues(alpha: 0.75));

    // 1. Khung Smart Guide A4 với 4 góc L-shaped
    final double guideW = screenW * 0.96;
    final double guideH = (guideW * 1.414).clamp(0.0, screenH * 0.96);
    final double guideLeft = (screenW - guideW) / 2;
    final double guideTop = (screenH - guideH) / 2;
    final double guideRight = guideLeft + guideW;
    final double guideBottom = guideTop + guideH;
    final guideRect = Rect.fromLTWH(guideLeft, guideTop, guideW, guideH);

    final a4Paint = Paint()
      ..color = guideColor.withValues(alpha: 0.35)
      ..style = PaintingStyle.stroke
      ..strokeWidth = 1.5;
    canvas.drawRect(guideRect, a4Paint);

    // Độ dày bracket tăng dần theo stability progress
    final double bracketWidth =
        isAligned ? (2.5 + stableProgress * 2.0).clamp(2.5, 4.5) : 3.5;

    final bracketPaint = Paint()
      ..color = guideColor
      ..style = PaintingStyle.stroke
      ..strokeWidth = bracketWidth
      ..strokeCap = StrokeCap.round;

    const double arm = 24.0;
    // TL
    canvas.drawLine(Offset(guideLeft, guideTop + arm),
        Offset(guideLeft, guideTop), bracketPaint);
    canvas.drawLine(Offset(guideLeft, guideTop),
        Offset(guideLeft + arm, guideTop), bracketPaint);
    // TR
    canvas.drawLine(Offset(guideRight - arm, guideTop),
        Offset(guideRight, guideTop), bracketPaint);
    canvas.drawLine(Offset(guideRight, guideTop),
        Offset(guideRight, guideTop + arm), bracketPaint);
    // BR
    canvas.drawLine(Offset(guideRight, guideBottom - arm),
        Offset(guideRight, guideBottom), bracketPaint);
    canvas.drawLine(Offset(guideRight, guideBottom),
        Offset(guideRight - arm, guideBottom), bracketPaint);
    // BL
    canvas.drawLine(Offset(guideLeft + arm, guideBottom),
        Offset(guideLeft, guideBottom), bracketPaint);
    canvas.drawLine(Offset(guideLeft, guideBottom),
        Offset(guideLeft, guideBottom - arm), bracketPaint);

    // 2. 4 ô vuông mục tiêu góc
    final sqSize = screenW * sqSizeRatio;

    final cornerKeys = ['TL', 'TR', 'BL', 'BR'];
    final corners = [
      Rect.fromLTWH(screenW * cornerRatios['TL']!.dx,
          screenH * cornerRatios['TL']!.dy, sqSize, sqSize),
      Rect.fromLTWH(screenW * cornerRatios['TR']!.dx,
          screenH * cornerRatios['TR']!.dy, sqSize, sqSize),
      Rect.fromLTWH(screenW * cornerRatios['BL']!.dx,
          screenH * cornerRatios['BL']!.dy, sqSize, sqSize),
      Rect.fromLTWH(screenW * cornerRatios['BR']!.dx,
          screenH * cornerRatios['BR']!.dy, sqSize, sqSize),
    ];

    for (int i = 0; i < 4; i++) {
      final key = cornerKeys[i];
      final bool matched = isAligned || (cornerMatched[key] ?? false);

      final borderPaint = Paint()
        ..color =
            matched ? Colors.greenAccent : guideColor.withValues(alpha: 0.85)
        ..style = PaintingStyle.stroke
        ..strokeWidth = matched ? 3.0 : 2.0;

      canvas.drawRect(corners[i], borderPaint);
    }

    // Vẽ bounding box xanh lục bên trong overlay nếu có
    if (markerRectsInCorner.length >= 4) {
      final markerPaint = Paint()
        ..color = Colors.greenAccent
        ..style = PaintingStyle.stroke
        ..strokeWidth = 3.0;

      for (int i = 0; i < 4 && i < markerRectsInCorner.length; i++) {
        final corner = corners[i];
        final relMarker = markerRectsInCorner[i];

        double clampedLeft = relMarker.left.clamp(0.0, 1.0);
        double clampedTop = relMarker.top.clamp(0.0, 1.0);
        double clampedRight =
            (relMarker.left + relMarker.width).clamp(0.0, 1.0);
        double clampedBottom =
            (relMarker.top + relMarker.height).clamp(0.0, 1.0);
        double clampedW = clampedRight - clampedLeft;
        double clampedH = clampedBottom - clampedTop;

        if (clampedW <= 0 || clampedH <= 0) continue;

        final markerScreenRect = Rect.fromLTWH(
          corner.left + clampedLeft * corner.width,
          corner.top + clampedTop * corner.height,
          clampedW * corner.width,
          clampedH * corner.height,
        );

        canvas.save();
        canvas.clipRect(corner);
        canvas.drawRect(markerScreenRect, markerPaint);
        canvas.restore();
      }
    }
  }

  @override
  bool shouldRepaint(covariant _AzotaOverlayPainter oldDelegate) =>
      oldDelegate.isAligned != isAligned ||
      oldDelegate.screenW != screenW ||
      oldDelegate.screenH != screenH ||
      oldDelegate.cornerMatched != cornerMatched ||
      oldDelegate.markerRectsInCorner.length != markerRectsInCorner.length ||
      oldDelegate.stableProgress != stableProgress;
}
