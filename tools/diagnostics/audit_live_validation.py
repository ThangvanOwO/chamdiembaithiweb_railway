"""Original-photo before/after audit. No DB writes or changes to input photos."""
import argparse
import json
import os
from pathlib import Path
import shutil
import sys
import time
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'chamdiemtudong.settings')
import django
django.setup()
from grading import grader


def main():
    parser = argparse.ArgumentParser(__doc__)
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--only', help='Optional source basename from the fixed local corpus')
    args = parser.parse_args()
    out = args.output.resolve()
    if out.exists() or not out.is_relative_to(ROOT):
        parser.error('Use a new output folder inside workspace')
    out.mkdir(parents=True)
    sources = [ROOT / 'media/submissions/2026/09' / name for name in
               ('live_H6cQfZ2.jpg', 'live_iQ7kqOT.jpg', 'live_XbTsC8z.jpg', 'live_t0EDDxm.jpg', 'live_M2fMCpf.jpg')]
    sources.append(ROOT / 'tests/fixtures/exam_import_v1.jpg')
    sources.append(ROOT / 'media/submissions/2026/09/9.jpg')
    if args.only:
        sources = [source for source in sources if source.name == args.only]
        if not sources:
            parser.error('Unknown corpus basename')
    rows = []
    copier = shutil.copy2
    for source in sources:
        fields = source.with_suffix('.json')
        corners = json.loads(json.loads(fields.read_text())['corners']) if fields.exists() else None
        for enabled in (False, True):
            folder = out / f'{source.stem}_{int(enabled)}'
            folder.mkdir()
            image = folder / 'input.jpg'
            copier(source, image)
            def copy(src, dst, *a, **kw):
                if Path(dst).parent.resolve() == (ROOT / 'tests/ketqua').resolve():
                    dst = folder / ('auto_' + Path(dst).name)
                return copier(src, dst, *a, **kw)
            start = time.perf_counter()
            preprocess = grader.engine.preprocess
            def capture(warped, *a, **kw):
                grader.engine.cv2.imwrite(str(folder / 'raw_warp.png'), warped)
                return preprocess(warped, *a, **kw)
            with patch.object(shutil, 'copy2', copy), patch.object(grader.engine, 'preprocess', capture):
                # Empty synthetic answer key: overlays diagnostic only, not real marks.
                result = grader.grade_image(str(image), '{}', '40-08-06', corners=corners,
                    fast_mode=True, live_bubble_mode=True, live_validation=enabled)
            (folder / 'engine.log').write_text(result.pop('debug_log', ''), encoding='utf-8')
            row = {'source': str(source.relative_to(ROOT)), 'enabled': enabled,
                   'seconds': time.perf_counter() - start, 'result': result}
            rows.append(row)
            (out / 'report.json').write_text(json.dumps(rows, indent=2, ensure_ascii=False), encoding='utf-8')
            print(json.dumps({'source': source.name, 'enabled': enabled,
                'sbd': result.get('sbd'), 'made': result.get('made'), 'p1': result.get('part1'),
                'p2': result.get('part2'), 'p3': result.get('part3'), 'error': result.get('error')}, ensure_ascii=True), flush=True)
            assert result['success']


if __name__ == '__main__':
    main()
