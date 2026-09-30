"""Isolated UTF-8 engine runner for importing an answer sheet (not grading).

The legacy engine prints Vietnamese diagnostics. Never redirect/reconfigure
the Django process's global stdout: concurrent Live grading owns that stream
too. A child process also isolates the engine's mutable template globals.
"""
import contextlib
import json
import logging
import math
import os
from pathlib import Path
import subprocess
import sys
import tempfile

logger = logging.getLogger(__name__)
ROOT = Path(__file__).resolve().parents[1]
TIMEOUT_SECONDS = 120


def capture_options(data):
    """Import-camera coordinates are bound to the exact JPEG dimensions."""
    protocol = data.get('capture_pipeline', '')
    if not protocol and not data.get('corners'):
        return {}
    if protocol != 'exam_import_capture_v1':
        raise ValueError('Phiên bản quét tạo đề không hợp lệ. Vui lòng cập nhật app.')
    try:
        points = json.loads(data.get('corners', ''))
        width, height = int(data['capture_width']), int(data['capture_height'])
        if not (0 < width <= 12000 and 0 < height <= 12000):
            raise ValueError()
        if not isinstance(points, list) or len(points) != 4:
            raise ValueError()
        for p in points:
            if not isinstance(p, list) or len(p) != 2:
                raise ValueError()
            if any(type(v) not in (int, float) or not math.isfinite(v) for v in p):
                raise ValueError()
            if not (0 <= p[0] < width and 0 <= p[1] < height):
                raise ValueError()
        crosses = []
        for i in range(4):
            a, b, c = points[i], points[(i+1) % 4], points[(i+2) % 4]
            crosses.append((b[0]-a[0])*(c[1]-b[1]) - (b[1]-a[1])*(c[0]-b[0]))
        area = sum(points[i][0]*points[(i+1)%4][1] - points[(i+1)%4][0]*points[i][1]
                   for i in range(4)) / 2
        if min(crosses) <= 0 or area < width * height * .1:
            raise ValueError()
    except (KeyError, TypeError, ValueError):
        raise ValueError('Tọa độ 4 góc không hợp lệ. Vui lòng quét lại.') from None
    return {'corners': points, 'width': width, 'height': height}


def parse_answer_image(upload, options=None):
    suffix = Path(upload.name).suffix.lower()
    with tempfile.TemporaryDirectory(prefix='gradeflow-answer-import-') as folder:
        path = Path(folder) / ('sheet' + suffix)
        with path.open('wb') as target:
            for chunk in upload.chunks():
                target.write(chunk)
        env = os.environ.copy()
        env['PYTHONIOENCODING'] = 'utf-8'
        try:
            completed = subprocess.run(
                [sys.executable, '-X', 'utf8', '-m', 'api.answer_image_import', str(path)],
                cwd=str(ROOT), env=env, capture_output=True, encoding='utf-8',
                input=json.dumps(options or {}),
                errors='replace', timeout=TIMEOUT_SECONDS, check=True,
                creationflags=subprocess.CREATE_NO_WINDOW if os.name == 'nt' else 0,
            )
        except subprocess.TimeoutExpired as exc:
            raise RuntimeError('Đọc phiếu quá thời gian. Vui lòng thử lại với ảnh rõ hơn.') from exc
        except subprocess.CalledProcessError as exc:
            logger.error('Answer-image worker failed: %s', ascii((exc.stderr or '')[-6000:]))
            raise RuntimeError('Không thể xử lý phiếu đáp án. Vui lòng thử lại.') from exc
        # ASCII escaping keeps even an old Windows log sink safe. JSON response
        # below is decoded as UTF-8 independently of the console's code page.
        logger.debug('Answer-image diagnostics: %s', ascii(completed.stderr[-12000:]))
        payload = json.loads(completed.stdout)
        if isinstance(payload, dict) and payload.get('error'):
            raise ValueError(payload['error'])
        return payload


def main():
    options = json.loads(sys.stdin.read() or '{}')
    # Redirect only INSIDE the child, so stdout is a clean JSON protocol.
    with contextlib.redirect_stdout(sys.stderr):
        from grading.engine import hi as engine
        engine.load_template(str(ROOT / 'grading/engine/templates/template_default.json'))
        if options:
            from PIL import Image
            with Image.open(sys.argv[1]) as image:
                if image.size != (options['width'], options['height']) or image.getexif().get(274, 1) != 1:
                    print(json.dumps({'error': 'Ảnh không khớp tọa độ camera. Vui lòng quét lại.'}),
                          file=sys.__stdout__)
                    return
        result = engine.process_sheet(sys.argv[1], correct_answers=None, debug=False,
            provided_corners=options.get('corners'), fast_mode=bool(options), live_bubble_mode=True)
        # Parent only needs recognition data, not renderer/NumPy internals.
        payload = None if not result else {
            key: result.get(key) for key in ('part1', 'part2', 'part3', 'made',
                'detect_method', 'scan_quality', 'validation_warnings')
        }
    print(json.dumps(payload, ensure_ascii=False))


if __name__ == '__main__':
    main()
