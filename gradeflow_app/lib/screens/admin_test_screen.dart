import 'dart:convert';
import 'dart:io';
import 'dart:typed_data';

import 'package:flutter/foundation.dart';
import 'package:flutter/material.dart';
import '../services/ad_navigation_observer.dart';
import 'package:google_fonts/google_fonts.dart';
import 'package:image_picker/image_picker.dart';
import 'package:lucide_icons/lucide_icons.dart';
import 'package:provider/provider.dart';

import '../config/theme.dart';
import '../models/grade_result.dart';
import '../services/auth_service.dart';
import '../services/api_service.dart';
import '../services/live_grading_service.dart';
import 'live_camera_screen.dart';

/// Admin-only: Test grading screen.
/// Allows admin to pick/take a photo and grade it without saving a submission.
/// Shows full raw results: SBD, Ma de, Part I/II/III, images, timing.
class AdminTestScreen extends StatefulWidget {
  const AdminTestScreen({super.key});

  @override
  State<AdminTestScreen> createState() => _AdminTestScreenState();
}

class _AdminTestScreenState extends State<AdminTestScreen> {
  bool _grading = false;
  Uint8List? _imageBytes;
  LiveCapture? _liveCapture;
  String _fileName = 'test.jpg';
  GradeResult? _result;
  final _imagePicker = ImagePicker();

  // ─── Image picking ──────────────────────────────────────────────

  Future<void> _scanDocument() async {
    if (!kIsWeb &&
        (defaultTargetPlatform == TargetPlatform.android ||
            defaultTargetPlatform == TargetPlatform.iOS)) {
      final capture = await Navigator.push<LiveCapture>(
        context,
        MaterialPageRoute(
          settings: const RouteSettings(name: AdNavigationObserver.cameraRoute),
          builder: (_) => AutoScanScreen(),
        ),
      );
      if (capture != null && mounted) {
        final ts = DateTime.now().millisecondsSinceEpoch;
        setState(() {
          _imageBytes = capture.bytes;
          _liveCapture = capture;
          _fileName = 'omr_$ts.jpg';
          _result = null;
        });
        return;
      }
    }
    _pickFromGallery();
  }

  Future<void> _pickFromCamera() async {
    final photo = await _imagePicker.pickImage(
      source: ImageSource.camera,
      maxWidth: 2400,
      maxHeight: 3200,
      imageQuality: 92,
    );
    if (photo != null && mounted) {
      final bytes = await photo.readAsBytes();
      setState(() {
        _imageBytes = bytes;
        _fileName = photo.name;
        _result = null;
      });
    }
  }

  Future<void> _pickFromGallery() async {
    final photo = await _imagePicker.pickImage(
      source: ImageSource.gallery,
      maxWidth: 2400,
      maxHeight: 3200,
      imageQuality: 92,
    );
    if (photo != null && mounted) {
      final bytes = await photo.readAsBytes();
      setState(() {
        _imageBytes = bytes;
        _fileName = photo.name;
        _result = null;
      });
    }
  }

  // ─── Grading ────────────────────────────────────────────────────

  Future<void> _grade() async {
    if (_imageBytes == null) return;
    final auth = context.read<AuthService>();
    if (auth.token == null) return;

    setState(() => _grading = true);
    try {
      final api = ApiService(token: auth.token!);
      final live = _liveCapture;
      final result = live != null && identical(live.bytes, _imageBytes)
          ? await gradeLiveCapture(token: auth.token!, capture: live, save: false)
          : await api.gradeImage(
        imageBytes: _imageBytes!,
        fileName: _fileName,
        save: false, // Don't create submission — test only
      );
      if (mounted) {
        setState(() {
          _result = result;
          _grading = false;
        });
      }
    } catch (e) {
      if (mounted) {
        setState(() => _grading = false);
        ScaffoldMessenger.of(context).showSnackBar(
          SnackBar(content: Text('Loi: $e'), backgroundColor: Colors.red),
        );
      }
    }
  }

  void _reset() {
    setState(() {
      _imageBytes = null;
      _result = null;
    });
  }

  // ─── Build ──────────────────────────────────────────────────────

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      appBar: AppBar(
        title: const Text('Test cham diem'),
        actions: [
          if (_imageBytes != null)
            IconButton(
              icon: const Icon(LucideIcons.trash2, size: 20),
              onPressed: _reset,
              tooltip: 'Xoa',
            ),
        ],
      ),
      body: ListView(
        padding: const EdgeInsets.all(16),
        children: [
          // Banner
          Container(
            padding: const EdgeInsets.all(14),
            decoration: BoxDecoration(
              gradient: LinearGradient(
                colors: [GradeFlowTheme.primary, GradeFlowTheme.tertiary],
                begin: Alignment.topLeft,
                end: Alignment.bottomRight,
              ),
              borderRadius: BorderRadius.circular(14),
            ),
            child: Row(
              children: [
                const Icon(LucideIcons.flaskConical, color: Colors.white, size: 24),
                const SizedBox(width: 12),
                Expanded(
                  child: Column(
                    crossAxisAlignment: CrossAxisAlignment.start,
                    children: [
                      Text('Che do test',
                          style: GoogleFonts.manrope(
                              fontSize: 15,
                              fontWeight: FontWeight.w700,
                              color: Colors.white)),
                      Text('Cham nhanh — khong luu ket qua',
                          style: GoogleFonts.dmSans(
                              fontSize: 12,
                              color: Colors.white.withOpacity(0.9))),
                    ],
                  ),
                ),
              ],
            ),
          ),
          const SizedBox(height: 20),

          // Live Camera button (TNMaker-style)
          if (_imageBytes == null && _result == null) ...[            SizedBox(
              height: 56,
              child: ElevatedButton.icon(
                onPressed: _scanDocument,
                icon: const Icon(LucideIcons.video, size: 22),
                label: Text('Live Camera (TNMaker)',
                    style: GoogleFonts.dmSans(
                        fontSize: 16, fontWeight: FontWeight.w600)),
                style: ElevatedButton.styleFrom(
                  backgroundColor: GradeFlowTheme.tertiary,
                  shape: RoundedRectangleBorder(
                      borderRadius: BorderRadius.circular(14)),
                ),
              ),
            ),
            const SizedBox(height: 12),
          ],

          // Scan buttons
          if (_imageBytes == null) ...[
            SizedBox(
              height: 56,
              child: ElevatedButton.icon(
                onPressed: _scanDocument,
                icon: const Icon(LucideIcons.scan, size: 22),
                label: Text('Quet phieu thi',
                    style: GoogleFonts.dmSans(
                        fontSize: 16, fontWeight: FontWeight.w600)),
                style: ElevatedButton.styleFrom(
                  shape: RoundedRectangleBorder(
                      borderRadius: BorderRadius.circular(14)),
                ),
              ),
            ),
            const SizedBox(height: 10),
            Row(
              children: [
                Expanded(
                  child: OutlinedButton.icon(
                    onPressed: _pickFromCamera,
                    icon: const Icon(LucideIcons.camera, size: 18),
                    label: const Text('Camera'),
                  ),
                ),
                const SizedBox(width: 10),
                Expanded(
                  child: OutlinedButton.icon(
                    onPressed: _pickFromGallery,
                    icon: const Icon(LucideIcons.image, size: 18),
                    label: const Text('Thu vien'),
                  ),
                ),
              ],
            ),
          ],

          // Preview + Grade button
          if (_imageBytes != null && _result == null) ...[
            Card(
              child: Padding(
                padding: const EdgeInsets.all(16),
                child: Column(
                  children: [
                    ClipRRect(
                      borderRadius: BorderRadius.circular(10),
                      child: Image.memory(_imageBytes!, height: 280,
                          fit: BoxFit.contain),
                    ),
                    const SizedBox(height: 14),
                    SizedBox(
                      width: double.infinity,
                      height: 52,
                      child: ElevatedButton.icon(
                        onPressed: _grading ? null : _grade,
                        icon: _grading
                            ? const SizedBox(
                                width: 20,
                                height: 20,
                                child: CircularProgressIndicator(
                                    strokeWidth: 2, color: Colors.white))
                            : const Icon(LucideIcons.play, size: 20),
                        label: Text(
                            _grading ? 'Dang cham...' : 'Bat dau cham diem',
                            style: GoogleFonts.dmSans(
                                fontSize: 16, fontWeight: FontWeight.w600)),
                        style: ElevatedButton.styleFrom(
                          backgroundColor: GradeFlowTheme.success,
                          shape: RoundedRectangleBorder(
                              borderRadius: BorderRadius.circular(14)),
                        ),
                      ),
                    ),
                  ],
                ),
              ),
            ),
          ],

          // Results
          if (_result != null) _buildResults(),
        ],
      ),
    );
  }

  // ─── Results display ────────────────────────────────────────────

  Widget _buildResults() {
    final r = _result!;

    if (!r.success) {
      return Card(
        color: GradeFlowTheme.errorContainer,
        child: Padding(
          padding: const EdgeInsets.all(16),
          child: Column(
            children: [
              const Icon(LucideIcons.alertTriangle,
                  size: 40, color: GradeFlowTheme.error),
              const SizedBox(height: 8),
              Text('Khong nhan dien duoc',
                  style: GoogleFonts.manrope(
                      fontSize: 16, fontWeight: FontWeight.w700)),
              Text(r.error,
                  style: GoogleFonts.dmSans(fontSize: 13),
                  textAlign: TextAlign.center),
              const SizedBox(height: 12),
              OutlinedButton.icon(
                onPressed: _reset,
                icon: const Icon(LucideIcons.refreshCw, size: 16),
                label: const Text('Thu lai'),
              ),
            ],
          ),
        ),
      );
    }

    return Column(
      children: [
        // SBD + Ma de + Timing
        _infoCard(r),
        const SizedBox(height: 12),

        // Result image
        if (r.resultImageBase64.isNotEmpty) ...[
          _imageCard('Anh ket qua', r.resultImageBase64),
          const SizedBox(height: 12),
        ],

        // Overlay image
        if (r.overlayImageBase64.isNotEmpty) ...[
          _imageCard('Anh overlay', r.overlayImageBase64),
          const SizedBox(height: 12),
        ],

        // Part I
        if (r.part1.isNotEmpty) ...[
          _part1Card(r),
          const SizedBox(height: 12),
        ],

        // Part II
        if (r.part2.isNotEmpty) ...[
          _part2Card(r),
          const SizedBox(height: 12),
        ],

        // Part III
        if (r.part3.isNotEmpty) ...[
          _part3Card(r),
          const SizedBox(height: 12),
        ],

        // Try again
        SizedBox(
          width: double.infinity,
          height: 48,
          child: OutlinedButton.icon(
            onPressed: _reset,
            icon: const Icon(LucideIcons.refreshCw, size: 18),
            label: const Text('Test anh khac'),
          ),
        ),
        const SizedBox(height: 24),
      ],
    );
  }

  Widget _infoCard(GradeResult r) {
    return Card(
      child: Padding(
        padding: const EdgeInsets.all(16),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            Text('Ket qua nhan dien',
                style: GoogleFonts.manrope(
                    fontSize: 16, fontWeight: FontWeight.w700)),
            const SizedBox(height: 12),
            _infoRow(LucideIcons.hash, 'SBD', r.sbd.isEmpty ? '(trong)' : r.sbd),
            const SizedBox(height: 6),
            _infoRow(LucideIcons.fileText, 'Ma de',
                r.made.isEmpty ? '(trong)' : r.made),
            const SizedBox(height: 6),
            _infoRow(LucideIcons.award, 'Diem',
                r.score != null ? '${r.score}' : '(chua co de)'),
            const SizedBox(height: 6),
            _infoRow(LucideIcons.cpu, 'Method', r.detectMethod),
            const SizedBox(height: 6),
            _infoRow(LucideIcons.clock, 'Thoi gian',
                '${r.processingTime.toStringAsFixed(1)}s'),
            if (r.scores.isNotEmpty) ...[
              const SizedBox(height: 6),
              _infoRow(LucideIcons.barChart2, 'Scores',
                  'P1=${r.scores['part1'] ?? '-'}  P2=${r.scores['part2'] ?? '-'}  P3=${r.scores['part3'] ?? '-'}'),
            ],
          ],
        ),
      ),
    );
  }

  Widget _infoRow(IconData icon, String label, String value) {
    return Row(
      children: [
        Icon(icon, size: 14, color: GradeFlowTheme.onSurfaceVariant),
        const SizedBox(width: 8),
        Text('$label: ',
            style: GoogleFonts.dmSans(
                fontSize: 13, color: GradeFlowTheme.onSurfaceVariant)),
        Expanded(
          child: Text(value,
              style:
                  GoogleFonts.dmSans(fontSize: 13, fontWeight: FontWeight.w600),
              overflow: TextOverflow.ellipsis),
        ),
      ],
    );
  }

  Widget _imageCard(String title, String base64) {
    Uint8List? bytes;
    try {
      bytes = base64Decode(base64);
    } catch (_) {}
    if (bytes == null) return const SizedBox.shrink();

    return Card(
      child: Padding(
        padding: const EdgeInsets.all(12),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            Text(title,
                style: GoogleFonts.dmSans(
                    fontSize: 14, fontWeight: FontWeight.w600)),
            const SizedBox(height: 8),
            ClipRRect(
              borderRadius: BorderRadius.circular(8),
              child: Image.memory(bytes, fit: BoxFit.contain),
            ),
          ],
        ),
      ),
    );
  }

  Widget _part1Card(GradeResult r) {
    // Part I: questions 1-40, each has a letter answer (A/B/C/D or empty)
    final entries = r.part1.entries.toList()
      ..sort((a, b) {
        final ai = int.tryParse(a.key) ?? 0;
        final bi = int.tryParse(b.key) ?? 0;
        return ai.compareTo(bi);
      });

    return Card(
      child: Padding(
        padding: const EdgeInsets.all(16),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            Text('Phan I — Trac nghiem (${entries.length} cau)',
                style: GoogleFonts.manrope(
                    fontSize: 14, fontWeight: FontWeight.w700)),
            const SizedBox(height: 10),
            Wrap(
              spacing: 6,
              runSpacing: 6,
              children: entries.map((e) {
                final q = e.key;
                final ans = e.value?.toString() ?? '';
                final hasAnswer = ans.isNotEmpty && ans != 'X';
                return Container(
                  width: 68,
                  padding:
                      const EdgeInsets.symmetric(horizontal: 6, vertical: 4),
                  decoration: BoxDecoration(
                    color: hasAnswer
                        ? GradeFlowTheme.primaryFixed
                        : GradeFlowTheme.surfaceContainerLow,
                    borderRadius: BorderRadius.circular(6),
                    border: Border.all(
                      color: hasAnswer
                          ? GradeFlowTheme.primary.withOpacity(0.3)
                          : GradeFlowTheme.outlineVariant,
                    ),
                  ),
                  child: Text(
                    'Q$q: ${hasAnswer ? ans : '-'}',
                    style: GoogleFonts.dmSans(
                      fontSize: 12,
                      fontWeight: FontWeight.w600,
                      color: hasAnswer
                          ? GradeFlowTheme.primary
                          : GradeFlowTheme.onSurfaceVariant,
                    ),
                    textAlign: TextAlign.center,
                  ),
                );
              }).toList(),
            ),
          ],
        ),
      ),
    );
  }

  Widget _part2Card(GradeResult r) {
    // Part II: questions with sub-answers (a/b/c/d → Dung/Sai)
    final entries = r.part2.entries.toList()
      ..sort((a, b) {
        final ai = int.tryParse(a.key) ?? 0;
        final bi = int.tryParse(b.key) ?? 0;
        return ai.compareTo(bi);
      });

    return Card(
      child: Padding(
        padding: const EdgeInsets.all(16),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            Text('Phan II — Dung/Sai (${entries.length} cau)',
                style: GoogleFonts.manrope(
                    fontSize: 14, fontWeight: FontWeight.w700)),
            const SizedBox(height: 10),
            ...entries.map((e) {
              final q = e.key;
              final subs = e.value is Map
                  ? Map<String, dynamic>.from(e.value)
                  : <String, dynamic>{};
              return Padding(
                padding: const EdgeInsets.only(bottom: 6),
                child: Row(
                  children: [
                    SizedBox(
                      width: 36,
                      child: Text('Q$q',
                          style: GoogleFonts.dmSans(
                              fontSize: 13, fontWeight: FontWeight.w600)),
                    ),
                    ...['a', 'b', 'c', 'd'].map((sub) {
                      final val = subs[sub]?.toString() ?? '';
                      final isDung = val.toLowerCase().contains('dung') ||
                          val.toLowerCase() == 'd';
                      final isSai = val.toLowerCase().contains('sai') ||
                          val.toLowerCase() == 's';
                      Color bg = GradeFlowTheme.surfaceContainerLow;
                      Color fg = GradeFlowTheme.onSurfaceVariant;
                      if (isDung) {
                        bg = GradeFlowTheme.successContainer;
                        fg = GradeFlowTheme.success;
                      } else if (isSai) {
                        bg = GradeFlowTheme.errorContainer;
                        fg = GradeFlowTheme.error;
                      }
                      return Expanded(
                        child: Container(
                          margin: const EdgeInsets.only(left: 4),
                          padding: const EdgeInsets.symmetric(vertical: 4),
                          decoration: BoxDecoration(
                            color: bg,
                            borderRadius: BorderRadius.circular(4),
                          ),
                          child: Text(
                            '$sub=${val.isEmpty ? '-' : val}',
                            style: GoogleFonts.dmSans(
                                fontSize: 11,
                                fontWeight: FontWeight.w600,
                                color: fg),
                            textAlign: TextAlign.center,
                          ),
                        ),
                      );
                    }),
                  ],
                ),
              );
            }),
          ],
        ),
      ),
    );
  }

  Widget _part3Card(GradeResult r) {
    // Part III: numeric fill-in answers
    final entries = r.part3.entries.toList()
      ..sort((a, b) {
        final ai = int.tryParse(a.key) ?? 0;
        final bi = int.tryParse(b.key) ?? 0;
        return ai.compareTo(bi);
      });

    return Card(
      child: Padding(
        padding: const EdgeInsets.all(16),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            Text('Phan III — Dien so (${entries.length} cau)',
                style: GoogleFonts.manrope(
                    fontSize: 14, fontWeight: FontWeight.w700)),
            const SizedBox(height: 10),
            ...entries.map((e) {
              final q = e.key;
              final val = e.value?.toString() ?? '';
              return Padding(
                padding: const EdgeInsets.only(bottom: 6),
                child: Row(
                  children: [
                    SizedBox(
                      width: 40,
                      child: Text('Q$q:',
                          style: GoogleFonts.dmSans(
                              fontSize: 13, fontWeight: FontWeight.w600)),
                    ),
                    Container(
                      padding: const EdgeInsets.symmetric(
                          horizontal: 12, vertical: 4),
                      decoration: BoxDecoration(
                        color: val.isNotEmpty
                            ? GradeFlowTheme.primaryFixed
                            : GradeFlowTheme.surfaceContainerLow,
                        borderRadius: BorderRadius.circular(6),
                      ),
                      child: Text(
                        val.isEmpty ? '(trong)' : val,
                        style: GoogleFonts.dmSans(
                          fontSize: 14,
                          fontWeight: FontWeight.w700,
                          color: val.isNotEmpty
                              ? GradeFlowTheme.primary
                              : GradeFlowTheme.onSurfaceVariant,
                        ),
                      ),
                    ),
                  ],
                ),
              );
            }),
          ],
        ),
      ),
    );
  }
}
