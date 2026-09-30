import 'dart:math' as math;
import 'dart:typed_data';
import 'dart:ui' as ui;

/// The live camera detector is deliberately independent from the upload and
/// grading pipeline. It only answers one question: do the four printed corner
/// markers belong to the expected sheet geometry in this frame?
const double liveMarkerRoiRatio = 0.12;

const Map<String, List<double>> liveMarkerCornerRatios = {
  'TL': [0.015, 0.015],
  'TR': [0.845, 0.015],
  'BL': [0.015, 0.845],
  'BR': [0.845, 0.845],
};

const List<String> liveMarkerKeys = ['TL', 'TR', 'BL', 'BR'];

/// Top-level isolate entry point used by Flutter's [compute].
Map<String, dynamic> detectLiveMarkers(Map<String, dynamic> params) {
  final yBytes = params['yBytes'];
  final rowStride = params['rowStride'];
  final sensorW = params['sensorW'];
  final sensorH = params['sensorH'];
  final sqRatio =
      (params['sqSizeRatio'] as num?)?.toDouble() ?? liveMarkerRoiRatio;
  final rawCorners = params['corners'] as Map? ?? liveMarkerCornerRatios;
  final rotation = params['rotationDegrees'] as int? ?? 0;
  final pixelStride = params['pixelStride'] as int? ?? 1;
  final corners = <String, List<double>>{};
  for (final key in liveMarkerKeys) {
    final value = rawCorners[key];
    if (value is List && value.length >= 2) {
      corners[key] = [
        (value[0] as num).toDouble(),
        (value[1] as num).toDouble(),
      ];
    }
  }

  if (yBytes is! Uint8List ||
      rowStride is! int ||
      sensorW is! int ||
      sensorH is! int ||
      corners.length != 4 ||
      sensorW <= 0 ||
      sensorH <= 0 ||
      pixelStride < 1 ||
      rowStride < (sensorW - 1) * pixelStride + 1 ||
      yBytes.length <
          (sensorH - 1) * rowStride + (sensorW - 1) * pixelStride + 1 ||
      ![0, 90, 180, 270].contains(rotation)) {
    return _emptyDetection(corners);
  }

  // Rotation is supplied by camera metadata, not inferred from dimensions.
  final rotated = rotation == 90 || rotation == 270;
  final logicalW = rotated ? sensorH : sensorW;
  final logicalH = rotated ? sensorW : sensorH;
  final crop = params['fullImage'] == true
      ? ui.Rect.fromLTWH(0, 0, logicalW.toDouble(), logicalH.toDouble())
      : _portraitCrop(logicalW, logicalH);
  final roiSize = (crop.width * sqRatio).round();
  if (roiSize < 12) return _emptyDetection(corners);

  final candidates = <String, _MarkerCandidate?>{};
  for (final key in liveMarkerKeys) {
    final ratio = corners[key]!;
    var roiX = (crop.left + crop.width * ratio[0]).round();
    var roiY = (crop.top + crop.height * ratio[1]).round();
    roiX = roiX.clamp(0, logicalW - 1).toInt();
    roiY = roiY.clamp(0, logicalH - 1).toInt();
    final int roiW = roiSize.clamp(1, logicalW - roiX).toInt();
    final int roiH = roiSize.clamp(1, logicalH - roiY).toInt();

    candidates[key] = _findMarker(
      yBytes,
      rowStride,
      sensorW,
      sensorH,
      rotation,
      roiX,
      roiY,
      roiW,
      roiH,
      pixelStride,
    );
  }

  if (candidates.values.any((candidate) => candidate == null)) {
    return _detectionResult(candidates, roiSize: roiSize, matched: false);
  }

  final concrete = <String, _MarkerCandidate>{
    for (final key in liveMarkerKeys) key: candidates[key]!,
  };

  final geometry = _validateGeometry(concrete, crop, roiSize);
  if (!geometry.valid) {
    return _detectionResult(candidates,
        roiSize: roiSize, matched: false, rejectReason: geometry.reason);
  }

  return _detectionResult(
    candidates,
    roiSize: roiSize,
    matched: true,
    quality: geometry.quality,
  );
}

Map<String, dynamic> _emptyDetection(Map<String, List<double>> corners) {
  return {
    'match': false,
    'matchedCorners': {for (final key in liveMarkerKeys) key: false},
    'markers': <double>[],
    'markerCentersLogical': <double>[-1, -1, -1, -1, -1, -1, -1, -1],
    'quality': 0.0,
    'rejectReason': 'preflight',
  };
}

Map<String, dynamic> _detectionResult(
  Map<String, _MarkerCandidate?> candidates, {
  required int roiSize,
  required bool matched,
  double quality = 0.0,
  String? rejectReason,
}) {
  final matchedCorners = <String, bool>{
    for (final key in liveMarkerKeys) key: candidates[key] != null,
  };
  final markers = <double>[];
  final centers = <double>[];
  for (final key in liveMarkerKeys) {
    final candidate = candidates[key];
    if (candidate == null) {
      markers.addAll([-1, -1, 0, 0]);
      centers.addAll([-1, -1]);
      continue;
    }
    markers.addAll([
      candidate.rect.left / roiSize,
      candidate.rect.top / roiSize,
      candidate.rect.width / roiSize,
      candidate.rect.height / roiSize,
    ]);
    centers.add(candidate.center.dx);
    centers.add(candidate.center.dy);
  }
  while (centers.length < 8) {
    centers.add(-1);
  }

  return {
    'match': matched,
    'matchedCorners': matchedCorners,
    'markers': markers,
    'markerCentersLogical': centers,
    'tilt': _tiltWarning(candidates),
    'quality': quality,
    'rejectReason':
        rejectReason ?? (matched ? null : 'marker_candidate_missing'),
  };
}

String? _tiltWarning(Map<String, _MarkerCandidate?> candidates) {
  final tl = candidates['TL'];
  final tr = candidates['TR'];
  if (tl == null || tr == null) return null;
  final dx = (tr.center.dx - tl.center.dx).abs();
  if (dx <= 0) return null;
  final dy = (tr.center.dy - tl.center.dy).abs();
  final angle = math.atan(dy / dx) * 180 / math.pi;
  if (angle <= 10) return null;
  return '⚠️ Giấy nghiêng ~${angle.toStringAsFixed(0)}°';
}

ui.Rect _portraitCrop(int width, int height) {
  const targetRatio = 3.0 / 4.0;
  final ratio = width / height;
  if (ratio > targetRatio) {
    final cropWidth = (height * targetRatio).round();
    return ui.Rect.fromLTWH(
      ((width - cropWidth) / 2).roundToDouble(),
      0,
      cropWidth.toDouble(),
      height.toDouble(),
    );
  }
  if (ratio < targetRatio) {
    final cropHeight = (width / targetRatio).round();
    return ui.Rect.fromLTWH(
      0,
      ((height - cropHeight) / 2).roundToDouble(),
      width.toDouble(),
      cropHeight.toDouble(),
    );
  }
  return ui.Rect.fromLTWH(0, 0, width.toDouble(), height.toDouble());
}

_MarkerCandidate? _findMarker(
  Uint8List yBytes,
  int rowStride,
  int sensorW,
  int sensorH,
  int rotation,
  int roiX,
  int roiY,
  int roiW,
  int roiH,
  int pixelStride,
) {
  int luminance(int x, int y) {
    final (px, py) = switch (rotation) {
      90 => (y, sensorH - 1 - x),
      180 => (sensorW - 1 - x, sensorH - 1 - y),
      270 => (sensorW - 1 - y, x),
      _ => (x, y),
    };
    if (px < 0 || px >= sensorW || py < 0 || py >= sensorH) return 255;
    final index = py * rowStride + px * pixelStride;
    if (index < 0 || index >= yBytes.length) return 255;
    return yBytes[index];
  }

  final samples = <int>[];
  for (var y = roiY; y < roiY + roiH; y += 2) {
    for (var x = roiX; x < roiX + roiW; x += 2) {
      samples.add(luminance(x, y));
    }
  }
  if (samples.isEmpty) return null;
  samples.sort();
  // Relative contrast survives exposure changes; absolute black levels do not.
  final ink = samples[(samples.length * 0.01).floor()];
  final paper = samples[(samples.length * 0.75).floor()];
  if (paper - ink < 35) return null;
  final darkThreshold = (ink + (paper - ink) * 0.42).round();
  const step = 2;
  final gridW = (roiW + step - 1) ~/ step;
  final gridH = (roiH + step - 1) ~/ step;
  final grid = Uint8List(gridW * gridH);

  for (var gy = 0; gy < gridH; gy++) {
    for (var gx = 0; gx < gridW; gx++) {
      final lum = luminance(roiX + gx * step, roiY + gy * step);
      if (lum < darkThreshold) grid[gy * gridW + gx] = 1;
    }
  }

  final queue = <int>[];
  _MarkerCandidate? best;
  var accepted = 0;
  var bestScore = double.infinity;
  for (var gy = 0; gy < gridH; gy++) {
    for (var gx = 0; gx < gridW; gx++) {
      final start = gy * gridW + gx;
      if (grid[start] != 1) continue;
      grid[start] = 2;
      queue
        ..clear()
        ..add(start);
      var head = 0;
      var minX = gx, maxX = gx, minY = gy, maxY = gy, points = 0;

      while (head < queue.length) {
        final current = queue[head++];
        final cy = current ~/ gridW;
        final cx = current % gridW;
        points++;
        minX = math.min(minX, cx);
        maxX = math.max(maxX, cx);
        minY = math.min(minY, cy);
        maxY = math.max(maxY, cy);
        for (var dy = -1; dy <= 1; dy++) {
          final ny = cy + dy;
          if (ny < 0 || ny >= gridH) continue;
          for (var dx = -1; dx <= 1; dx++) {
            if (dx == 0 && dy == 0) continue;
            final nx = cx + dx;
            if (nx < 0 || nx >= gridW) continue;
            final next = ny * gridW + nx;
            if (grid[next] == 1) {
              grid[next] = 2;
              queue.add(next);
            }
          }
        }
      }

      final bw = (maxX - minX + 1) * step;
      final bh = (maxY - minY + 1) * step;
      final minBlob = roiW * 0.07;
      final maxBlob = roiW * 0.55;
      if (bw < minBlob || bh < minBlob || bw > maxBlob || bh > maxBlob) {
        continue;
      }
      final aspect = math.max(bw / bh, bh / bw);
      if (aspect > 1.35) continue;
      final boxPoints = (maxX - minX + 1) * (maxY - minY + 1);
      final solidity = points / boxPoints;
      if (solidity < 0.65 || !hasFourStraightSides(queue, gridW)) continue;

      // A printed marker has a dark interior, unlike a bubble or text outline.
      var filled = 0, interior = 0;
      for (var iy = minY + (maxY - minY) ~/ 4;
          iy <= maxY - (maxY - minY) ~/ 4;
          iy++) {
        for (var ix = minX + (maxX - minX) ~/ 4;
            ix <= maxX - (maxX - minX) ~/ 4;
            ix++) {
          interior++;
          if (grid[iy * gridW + ix] != 0) filled++;
        }
      }
      if (interior == 0 || filled / interior < 0.85) continue;

      final relCenterX = ((minX + maxX + 1) * 0.5 * step) / roiW;
      final relCenterY = ((minY + maxY + 1) * 0.5 * step) / roiH;
      if (relCenterX < 0.08 ||
          relCenterX > 0.92 ||
          relCenterY < 0.08 ||
          relCenterY > 0.92) {
        continue;
      }
      accepted++;

      final score = (aspect - 1.0) + (1.0 - solidity) * 0.75;
      if (score < bestScore) {
        bestScore = score;
        best = _MarkerCandidate(
          rect: ui.Rect.fromLTWH(
            minX * step.toDouble(),
            minY * step.toDouble(),
            bw.toDouble(),
            bh.toDouble(),
          ),
          center: ui.Offset(
            roiX + (minX + maxX + 1) * 0.5 * step,
            roiY + (minY + maxY + 1) * 0.5 * step,
          ),
          size: (bw + bh) / 2,
        );
      }
    }
  }
  // Do not arbitrarily choose between two plausible markers in the same ROI.
  return accepted == 1 ? best : null;
}

_GeometryResult _validateGeometry(
  Map<String, _MarkerCandidate> markers,
  ui.Rect crop,
  int roiSize,
) {
  final tl = markers['TL']!;
  final tr = markers['TR']!;
  final bl = markers['BL']!;
  final br = markers['BR']!;
  final sizes = markers.values.map((marker) => marker.size).toList()..sort();
  final medianSize = (sizes[1] + sizes[2]) / 2;
  for (final size in sizes) {
    final ratio = size / medianSize;
    if (ratio < 0.68 || ratio > 1.47) {
      return const _GeometryResult(false, 'marker_size_mismatch', 0.0);
    }
  }

  // A printed marker has a bounded physical size. Tiny noise and large dark
  // objects are both rejected even when their local blob looks square.
  final markerRatio = medianSize / crop.width;
  if (markerRatio < 0.008 || markerRatio > 0.075) {
    return const _GeometryResult(false, 'marker_scale_invalid', 0.0);
  }
  if (medianSize < roiSize * 0.07 || medianSize > roiSize * 0.55) {
    return const _GeometryResult(false, 'marker_roi_scale_invalid', 0.0);
  }

  final leftX = (tl.center.dx + bl.center.dx) / 2;
  final rightX = (tr.center.dx + br.center.dx) / 2;
  final topY = (tl.center.dy + tr.center.dy) / 2;
  final bottomY = (bl.center.dy + br.center.dy) / 2;
  final xSpan = rightX - leftX;
  final ySpan = bottomY - topY;
  final expectedX = crop.width *
      (liveMarkerCornerRatios['TR']![0] - liveMarkerCornerRatios['TL']![0]);
  final expectedY = crop.height *
      (liveMarkerCornerRatios['BL']![1] - liveMarkerCornerRatios['TL']![1]);

  if (xSpan < expectedX * 0.70 || xSpan > expectedX * 1.12) {
    return const _GeometryResult(false, 'horizontal_geometry_invalid', 0.0);
  }
  if (ySpan < expectedY * 0.70 || ySpan > expectedY * 1.12) {
    return const _GeometryResult(false, 'vertical_geometry_invalid', 0.0);
  }
  if (leftX >= rightX || topY >= bottomY) {
    return const _GeometryResult(false, 'marker_order_invalid', 0.0);
  }

  final topSpan = (tr.center - tl.center).distance;
  final bottomSpan = (br.center - bl.center).distance;
  final leftSpan = (bl.center - tl.center).distance;
  final rightSpan = (br.center - tr.center).distance;
  if (topSpan <= 0 || bottomSpan <= 0 || leftSpan <= 0 || rightSpan <= 0) {
    return const _GeometryResult(false, 'degenerate_geometry', 0.0);
  }
  if (topSpan / bottomSpan < 0.62 || topSpan / bottomSpan > 1.38) {
    return const _GeometryResult(false, 'horizontal_perspective_invalid', 0.0);
  }
  if (leftSpan / rightSpan < 0.62 || leftSpan / rightSpan > 1.38) {
    return const _GeometryResult(false, 'vertical_perspective_invalid', 0.0);
  }

  final qualityParts = <double>[
    1.0 - (medianSize / roiSize - 0.22).abs(),
    1.0 - ((xSpan / expectedX) - 0.91).abs(),
    1.0 - ((ySpan / expectedY) - 0.91).abs(),
  ].map((value) => value.clamp(0.0, 1.0).toDouble()).toList();
  final quality = qualityParts.reduce((a, b) => a + b) / qualityParts.length;
  return _GeometryResult(true, null, quality);
}

// A filled circle can have high bounding-box solidity at low resolution.
// Its convex hull cannot be approximated by four straight sides without losing
// substantial area. A perspective-distorted square can.
bool hasFourStraightSides(List<int> component, int gridWidth) {
  final points = component
      .map((i) =>
          ui.Offset((i % gridWidth).toDouble(), (i ~/ gridWidth).toDouble()))
      .toList()
    ..sort(
        (a, b) => a.dx == b.dx ? a.dy.compareTo(b.dy) : a.dx.compareTo(b.dx));
  double cross(ui.Offset a, ui.Offset b, ui.Offset c) =>
      (b.dx - a.dx) * (c.dy - a.dy) - (b.dy - a.dy) * (c.dx - a.dx);
  List<ui.Offset> chain(Iterable<ui.Offset> input) {
    final result = <ui.Offset>[];
    for (final p in input) {
      while (result.length >= 2 &&
          cross(result[result.length - 2], result.last, p) <= 0) {
        result.removeLast();
      }
      result.add(p);
    }
    return result;
  }

  final lower = chain(points), upper = chain(points.reversed);
  final hull = [
    ...lower.take(lower.length - 1),
    ...upper.take(upper.length - 1)
  ];
  double area(List<ui.Offset> polygon) {
    var sum = 0.0;
    for (var i = 0; i < polygon.length; i++) {
      final a = polygon[i], b = polygon[(i + 1) % polygon.length];
      sum += a.dx * b.dy - a.dy * b.dx;
    }
    return sum.abs() / 2;
  }

  if (hull.length < 4) return false;
  final originalArea = area(hull);
  while (hull.length > 4) {
    var bestIndex = 0, bestLoss = double.infinity;
    for (var i = 0; i < hull.length; i++) {
      final loss = cross(hull[(i + hull.length - 1) % hull.length], hull[i],
              hull[(i + 1) % hull.length])
          .abs();
      if (loss < bestLoss) {
        bestIndex = i;
        bestLoss = loss;
      }
    }
    hull.removeAt(bestIndex);
  }
  return originalArea > 0 && area(hull) / originalArea >= 0.88;
}

class _MarkerCandidate {
  final ui.Rect rect;
  final ui.Offset center;
  final double size;

  const _MarkerCandidate(
      {required this.rect, required this.center, required this.size});
}

class _GeometryResult {
  final bool valid;
  final String? reason;
  final double quality;

  const _GeometryResult(this.valid, this.reason, this.quality);
}

/// Capture readiness is time based, not tied to detector FPS.
enum LiveScanPhase { searching, stabilizing, ready }

class LiveStabilityGate {
  static const requiredStableMs = 500;
  static const dropoutGraceMs = 400;
  static const maxObservationGapMs = 750;
  static const jitterTolerance = 0.035; // 3.5% of image width.
  static const travelTolerance =
      0.065; // Prevent slow panning being called stable.
  static const smoothingAlpha = 0.35;

  List<double>? _smoothed, _anchor;
  int? _lastObservedMs, _lastValidMs;
  int _stableMs = 0;
  bool _previousValid = false;
  int frames = 0;
  LiveScanPhase phase = LiveScanPhase.searching;

  bool get aligned => phase == LiveScanPhase.ready;
  double get progress => (_stableMs / requiredStableMs).clamp(0.0, 1.0);
  // Manual shutter is independent of marker readiness and elapsed time.
  bool canCapture({required bool manual}) => manual || aligned;

  void reset() {
    _smoothed = null;
    _anchor = null;
    _lastObservedMs = null;
    _lastValidMs = null;
    _stableMs = 0;
    _previousValid = false;
    frames = 0;
    phase = LiveScanPhase.searching;
  }

  double _drift(List<double> a, List<double> b) {
    var largest = 0.0;
    for (var i = 0; i < 8; i += 2) {
      final dx = a[i] - b[i], dy = a[i + 1] - b[i + 1];
      largest = math.max(largest, math.sqrt(dx * dx + dy * dy));
    }
    return largest;
  }

  bool observe(List<double>? centers, int nowMs) {
    if (_lastObservedMs != null && nowMs <= _lastObservedMs!) reset();
    _lastObservedMs = nowMs;
    if (centers != null &&
        (centers.length != 8 || centers.any((v) => !v.isFinite || v < 0))) {
      reset();
      return false;
    }
    // A slow detector is not a missing-marker observation. Only explicitly
    // missing frames use the shorter grace period.
    final gapLimit = centers != null && _previousValid
        ? maxObservationGapMs
        : dropoutGraceMs;
    if (_lastValidMs != null && nowMs - _lastValidMs! > gapLimit) reset();
    if (centers == null) {
      // Keep progress through a short dropout, but never auto-capture on a
      // missing observation or count unobserved time toward readiness.
      _previousValid = false;
      if (_smoothed != null) phase = LiveScanPhase.stabilizing;
      return false;
    }
    if (_smoothed != null &&
        (_drift(centers, _smoothed!) > jitterTolerance ||
            _drift(centers, _anchor!) > travelTolerance)) {
      reset();
    }
    if (_smoothed == null) {
      _anchor = List<double>.of(centers);
      _smoothed = List<double>.of(centers);
    } else {
      if (_previousValid) _stableMs += nowMs - _lastValidMs!;
      for (var i = 0; i < 8; i++) {
        _smoothed![i] += smoothingAlpha * (centers[i] - _smoothed![i]);
      }
    }
    frames++;
    _lastObservedMs = nowMs;
    _lastValidMs = nowMs;
    _previousValid = true;
    phase = _stableMs >= requiredStableMs
        ? LiveScanPhase.ready
        : LiveScanPhase.stabilizing;
    return aligned;
  }
}
