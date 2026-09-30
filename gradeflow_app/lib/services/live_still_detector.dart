import 'dart:math' as math;
import 'dart:typed_data';
import 'dart:ui';
import 'live_marker_detector.dart' show hasFourStraightSides;

/// Full-image JPEG detector. Unlike preview ROIs, these candidates are not
/// tied to the guide overlay, image margins, or preview sensor crop.
/// Independently implements local threshold -> components -> quadrilateral
/// approximation -> joint four-marker geometry (no reference APK code/assets).
class LiveStillDetection {
  final List<Offset> corners; // TL, TR, BR, BL in this image's pixels.
  final int candidateCount;
  final String? reason;
  const LiveStillDetection(this.corners, this.candidateCount, [this.reason]);
  bool get valid => corners.length == 4;
}

class _Candidate {
  final Offset center;
  final double size;
  const _Candidate(this.center, this.size);
}

LiveStillDetection detectStillMarkers(Uint8List gray, int width, int height,
    {void Function(String)? trace}) {
  if (width < 40 || height < 40 || gray.length != width * height) {
    return const LiveStillDetection([], 0, 'invalid_image');
  }
  final stride = width + 1;
  final integral = Int32List(stride * (height + 1));
  for (var y = 0; y < height; y++) {
    var row = 0;
    for (var x = 0; x < width; x++) {
      row += gray[y * width + x];
      integral[(y + 1) * stride + x + 1] = integral[y * stride + x + 1] + row;
    }
  }
  final candidates = <_Candidate>[];
  // Two local scales cope with exposure, soft edges and varied marker sizes.
  for (final radius in [(width * 0.025).round(), (width * 0.05).round()]) {
    // A low-contrast edge can round off a printed square after JPEG/shake.
    // Also inspect its darker core; never relax the square-vs-circle shape gate.
    for (final contrastFraction in [0.0, 0.3, 0.5]) {
      final binary = Uint8List(width * height);
      for (var y = 0; y < height; y++) {
        final top = math.max(0, y - radius),
            bottom = math.min(height, y + radius + 1);
        for (var x = 0; x < width; x++) {
          final left = math.max(0, x - radius),
              right = math.min(width, x + radius + 1);
          final sum = integral[bottom * stride + right] -
              integral[top * stride + right] -
              integral[bottom * stride + left] +
              integral[top * stride + left];
          final mean = sum / ((bottom - top) * (right - left));
          if (gray[y * width + x] <
              mean - math.max(12, mean * contrastFraction)) {
            binary[y * width + x] = 1;
          }
        }
      }
      final minSide = math.max(6, (width * 0.006).round());
      final maxSide = (width * 0.07).round();
      for (var start = 0; start < binary.length; start++) {
        if (binary[start] != 1) continue;
        final queue = <int>[start];
        binary[start] = 2;
        var head = 0;
        var minX = start % width,
            maxX = minX,
            minY = start ~/ width,
            maxY = minY;
        while (head < queue.length) {
          final index = queue[head++], x = index % width, y = index ~/ width;
          minX = math.min(minX, x);
          maxX = math.max(maxX, x);
          minY = math.min(minY, y);
          maxY = math.max(maxY, y);
          for (var dy = -1; dy <= 1; dy++) {
            for (var dx = -1; dx <= 1; dx++) {
              final nx = x + dx, ny = y + dy;
              if (nx < 0 || nx >= width || ny < 0 || ny >= height) continue;
              final next = ny * width + nx;
              if (binary[next] == 1) {
                binary[next] = 2;
                queue.add(next);
              }
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
        if (candidates.any(
            (c) => (c.center - center).distance < math.min(c.size, size) * 0.5)) {
          continue;
        }
        candidates.add(_Candidate(center, size));
        trace?.call('candidate center=$center size=$size');
      }
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
  if (best == null) {
    return LiveStillDetection([], candidates.length, 'no_coherent_quad');
  }
  if (runnerScore > bestScore * 0.94) {
    return LiveStillDetection([], candidates.length, 'ambiguous_quad');
  }
  return LiveStillDetection(best, candidates.length);
}
