import 'dart:math' as math;
import 'dart:typed_data';
import 'dart:ffi' as ffi;
import 'package:opencv_dart/opencv.dart' as cv;
import '../live_still_detector.dart' show LiveStillDetection;
import 'dart:ui';
import '../live_marker_detector.dart' show hasFourStraightSides;

/// Opt-in speed engine. The legacy file is deliberately left untouched.
/// Native labeling replaces the flood-fill only; all acceptance thresholds,
/// shape checks and quartet ranking remain the legacy algorithm.
class _Candidate {
  final Offset center;
  final double size;
  const _Candidate(this.center, this.size);
}

LiveStillDetection detectStillMarkersNative(
    Uint8List gray, int width, int height,
    {void Function(String)? trace, void Function(String, int)? onStage}) {
  if (width < 40 || height < 40 || gray.length != width * height) {
    return const LiveStillDetection([], 0, 'invalid_image');
  }
  final nativeGray = cv.Mat.zeros(height, width, cv.MatType.CV_8UC1);
  cv.Mat? gray64, floor12;
  final timer = Stopwatch()..start();
  void lap(String stage) {
    onStage?.call(stage, timer.elapsedMicroseconds);
    timer.reset();
  }

  try {
    nativeGray.data.setAll(0, gray);
    gray64 = nativeGray.convertTo(cv.MatType.CV_64FC1);
    floor12 = cv.Mat.ones(height, width, cv.MatType.CV_64FC1);
    floor12.multiplyF64(12, inplace: true);
    final candidates = <_Candidate>[];
    // Two local scales cope with exposure, soft edges and varied marker sizes.
    for (final radius in [(width * 0.025).round(), (width * 0.05).round()]) {
      final means = _localMeans(nativeGray, width, height, radius);
      final meanMat = cv.Mat.zeros(height, width, cv.MatType.CV_64FC1);
      try {
        meanMat.dataPtr
            .cast<ffi.Double>()
            .asTypedList(width * height)
            .setAll(0, means);
        lap('nativeMeans');
        // A low-contrast edge can round off a printed square after JPEG/shake.
        // Also inspect its darker core; never relax the square-vs-circle shape gate.
        for (final contrastFraction in [0.0, 0.3, 0.5]) {
          final components = _nativeComponents(
              gray64, meanMat, floor12, width, height, contrastFraction);
          lap('nativeComponents');
          final binary = components.binary;
          final minSide = math.max(6, (width * 0.006).round());
          final maxSide = (width * 0.07).round();
          for (final component in components.items) {
            final minX = component.x, minY = component.y;
            final maxX = minX + component.width - 1;
            final maxY = minY + component.height - 1;
            // Avoid allocating every pixel of large text/background components.
            if (component.width < minSide ||
                component.height < minSide ||
                component.width > maxSide ||
                component.height > maxSide) {
              continue;
            }
            final queue = <int>[];
            for (var y = minY; y <= maxY; y++) {
              for (var x = minX; x <= maxX; x++) {
                final index = y * width + x;
                if (components.labels[index] == component.label) {
                  queue.add(index);
                }
              }
            }
            final bw = maxX - minX + 1, bh = maxY - minY + 1;
            // Edge-touching components are incomplete; do not invent their centers.
            if (minX == 0 ||
                minY == 0 ||
                maxX == width - 1 ||
                maxY == height - 1 ||
                bw < minSide ||
                bh < minSide ||
                bw > maxSide ||
                bh > maxSide ||
                math.max(bw / bh, bh / bw) > 1.65 ||
                queue.length / (bw * bh) < 0.6) {
              continue;
            }
            if (!hasFourStraightSides(queue, width)) {
              trace?.call('reject shape bbox=[$minX,$minY,$bw,$bh]');
              continue;
            }
            var ink = 0, total = 0;
            for (var y = minY + bh ~/ 4; y <= maxY - bh ~/ 4; y++) {
              for (var x = minX + bw ~/ 4; x <= maxX - bw ~/ 4; x++) {
                total++;
                if (binary[y * width + x] != 0) ink++;
              }
            }
            if (total == 0 || ink / total < 0.85) continue;
            final center = Offset((minX + maxX) / 2, (minY + maxY) / 2);
            final size = (bw + bh) / 2;
            // A component found at both threshold scales is one physical marker.
            if (candidates.any((c) =>
                (c.center - center).distance < math.min(c.size, size) * 0.5)) {
              continue;
            }
            candidates.add(_Candidate(center, size));
            trace?.call('candidate center=$center size=$size');
          }
          lap('nativeShapes');
        }
      } finally {
        meanMat.dispose();
      }
    }
    // Search globally for a coherent outer quartet. Local extra squares no longer
    // invalidate a whole corner ROI; size/shape and sheet geometry resolve them.
    final buckets = List.generate(4, (_) => <_Candidate>[]);
    for (final c in candidates) {
      final right = c.center.dx >= width / 2;
      final bottom = c.center.dy >= height / 2;
      buckets[bottom ? (right ? 2 : 3) : (right ? 1 : 0)].add(c);
    }
    for (final bucket in buckets) {
      bucket.sort((a, b) => b.size.compareTo(a.size));
      if (bucket.length > 12) bucket.removeRange(12, bucket.length);
    }
    List<Offset>? best;
    var bestScore = 0.0, runnerScore = 0.0;
    for (final tl in buckets[0]) {
      for (final tr in buckets[1]) {
        for (final br in buckets[2]) {
          for (final bl in buckets[3]) {
            final group = [tl, tr, br, bl];
            final sizes = group.map((c) => c.size).toList()..sort();
            if (sizes.first / sizes.last < 0.65) continue;
            final p = group.map((c) => c.center).toList();
            final top = (p[1] - p[0]).distance, bottom = (p[2] - p[3]).distance;
            final left = (p[3] - p[0]).distance, right = (p[2] - p[1]).distance;
            if (math.min(top, bottom) < width * 0.35 ||
                math.min(left, right) < height * 0.4 ||
                math.min(top, bottom) / math.max(top, bottom) < 0.70 ||
                math.min(left, right) / math.max(left, right) < 0.70) {
              continue;
            }
            final ratio = (left + right) / (top + bottom);
            if (ratio < 1.15 || ratio > 1.8) continue;
            if ((p[1].dy - p[0].dy).abs() > (left + right) * 0.12 ||
                (p[2].dy - p[3].dy).abs() > (left + right) * 0.12 ||
                (p[3].dx - p[0].dx).abs() > (top + bottom) * 0.12 ||
                (p[2].dx - p[1].dx).abs() > (top + bottom) * 0.12) {
              continue;
            }
            var area = 0.0;
            for (var i = 0; i < 4; i++) {
              final a = p[i], b = p[(i + 1) % 4];
              area += a.dx * b.dy - a.dy * b.dx;
            }
            area /= 2;
            if (area < width * height * 0.22) continue;
            final score = area * math.pow(sizes.first / sizes.last, 2);
            if (score > bestScore) {
              runnerScore = bestScore;
              bestScore = score;
              best = p;
            } else if (score > runnerScore) {
              runnerScore = score;
            }
          }
        }
      }
    }
    trace?.call('quartet best=$best score=$bestScore runner=$runnerScore');
    lap('nativeQuartet');
    if (best == null) {
      return LiveStillDetection([], candidates.length, 'no_coherent_quad');
    }
    if (runnerScore > bestScore * 0.94) {
      return LiveStillDetection([], candidates.length, 'ambiguous_quad');
    }
    return LiveStillDetection(best, candidates.length);
  } finally {
    floor12?.dispose();
    gray64?.dispose();
    nativeGray.dispose();
  }
}

class _Component {
  final int label, x, y, width, height;
  const _Component(this.label, this.x, this.y, this.width, this.height);
}

class _Components {
  final Uint8List binary;
  final Int32List labels;
  final List<_Component> items;
  const _Components(this.binary, this.labels, this.items);
}

/// Native box sums are exact integer-valued doubles. Divide by the clipped
/// population in Dart (same operation as legacy); compute once per radius,
/// not once per threshold. Reflected padding would change edge decisions.
Float64List _localMeans(cv.Mat gray, int width, int height, int radius) {
  final anchor = cv.Point(-1, -1);
  cv.Mat? sums;
  try {
    sums = cv.boxFilter(
        gray, cv.MatType.CV_64F, (radius * 2 + 1, radius * 2 + 1),
        normalize: false, borderType: cv.BORDER_CONSTANT, anchor: anchor);
    final values = sums.dataPtr.cast<ffi.Double>().asTypedList(width * height);
    final means = Float64List(width * height);
    final columnCounts = [
      for (var x = 0; x < width; x++)
        math.min(width, x + radius + 1) - math.max(0, x - radius)
    ];
    for (var y = 0; y < height; y++) {
      final rows = math.min(height, y + radius + 1) - math.max(0, y - radius);
      for (var x = 0; x < width; x++) {
        final i = y * width + x;
        means[i] = values[i] / (rows * columnCounts[x]);
      }
    }
    return means;
  } finally {
    sums?.dispose();
    anchor.dispose();
  }
}

_Components _nativeComponents(cv.Mat pixels, cv.Mat means, cv.Mat floor12,
    int width, int height, double contrastFraction) {
  final owned = <cv.Mat>[];
  cv.Mat own(cv.Mat value) {
    owned.add(value);
    return value;
  }

  try {
    // Keep separate double-precision operations in legacy order. In particular,
    // do NOT round the threshold to uint8 or use adaptiveThreshold's C rounding.
    final scaled = own(means.multiplyF64(contrastFraction));
    final contrast = own(cv.max(scaled, floor12));
    final emptyMask = own(cv.Mat.empty());
    final cutoff = own(cv.subtract(means, contrast, mask: emptyMask));
    final mask = own(cv.compare(pixels, cutoff, cv.CMP_LT));
    final binary = mask.data;
    final labels = own(cv.Mat.empty()), stats = own(cv.Mat.empty());
    final centroids = own(cv.Mat.empty());
    final count = cv.connectedComponentsWithStats(
        mask, labels, stats, centroids, 8, cv.MatType.CV_32S, cv.CCL_WU);
    final statsValues = stats.dataPtr.cast<ffi.Int32>().asTypedList(count * 5);
    final labelValues = Int32List.fromList(
        labels.dataPtr.cast<ffi.Int32>().asTypedList(width * height));
    // SAUF (CCL_WU) labels in row-major discovery order, matching old flood-fill.
    return _Components(Uint8List.fromList(binary), labelValues, [
      for (var label = 1; label < count; label++)
        _Component(label, statsValues[label * 5], statsValues[label * 5 + 1],
            statsValues[label * 5 + 2], statsValues[label * 5 + 3])
    ]);
  } finally {
    for (final mat in owned.reversed) {
      mat.dispose();
    }
  }
}
