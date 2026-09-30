"""Exact Upload/import parity with pre-change engine AND reader; reject pre-score."""
import contextlib
import hashlib
import json
import os
from pathlib import Path
import shutil
import sys
import types
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'chamdiemtudong.settings')
import django
django.setup()
from grading import grader
from grading import engine as package
from grading.engine import live_bubble_reader
from grading.live_latency import LiveAnswerKeySelection


def main():
    out = ROOT / 'scratch/live_validation_isolation_20260915'
    out.mkdir(exist_ok=False)
    backup = ROOT / 'scratch/restore_points/before_live_validation_20260915/before'
    def load(name, relative, filename):
        module = types.ModuleType(name)
        module.__file__ = filename
        sys.modules[name] = module
        exec(compile((backup / relative).read_bytes(), str(backup / relative), 'exec'), module.__dict__)
        return module
    old_engine = load('validation_old_engine', 'grading/engine/hi.py', grader.engine.__file__)
    old_reader = load('validation_old_reader', 'grading/engine/live_bubble_reader.py', live_bubble_reader.__file__)
    source = ROOT / 'tests/fixtures/exam_import_v1.jpg'
    corners = json.loads(json.loads(source.with_suffix('.json').read_text())['corners'])
    copier = shutil.copy2
    records = []
    def run(name, engine, reader, live=False, **kwargs):
        folder = out / name
        folder.mkdir()
        image = folder / 'input.jpg'
        copier(source, image)
        def relocate(src, dst, *a, **kw):
            if Path(dst).parent.resolve() == (ROOT / 'tests/ketqua').resolve():
                dst = folder / ('auto_' + Path(dst).name)
            return copier(src, dst, *a, **kw)
        with patch.object(grader, 'engine', engine), patch.object(package, 'live_bubble_reader', reader), \
             patch.object(shutil, 'copy2', relocate):
            result = grader.grade_image(str(image), '{}', '40-08-06', corners=corners,
                fast_mode=True, live_bubble_mode=live, **kwargs)
        (folder / 'engine.log').write_text(result.pop('debug_log', ''), encoding='utf-8')
        for key in ('processing_time', 'result_image_path', 'name_image_path'):
            result.pop(key, None)
        hashes = {p.name: hashlib.sha256(p.read_bytes()).hexdigest() for p in folder.glob('input_*.jpg')}
        records.append({'name': name, 'result': result, 'hashes': hashes})
        print(name, result.get('success'), flush=True)
        return result, hashes
    for live in (False, True):
        old = run(f'old_live{int(live)}', old_engine, old_reader, live)
        new = run(f'new_live{int(live)}', grader.engine, live_bubble_reader, live)
        assert old == new, 'Default Upload/import result or image changed'
    selector = LiveAnswerKeySelection('{}', [('002', '{}')], grader.parse_answer_key, strict=True)
    # Original has code 001, which is deliberately not registered here.
    with patch.object(grader.engine, 'grade_part1', side_effect=AssertionError('Must reject BEFORE scoring')):
        result, hashes = run('unregistered_rejected', grader.engine, live_bubble_reader, True,
                            live_validation=True, live_answer_key_resolver=selector.resolve)
    assert not result['success'] and '001' in result['error']
    assert 'input_result.jpg' not in hashes and 'input_overlay.jpg' not in hashes
    (out / 'report.json').write_text(json.dumps(records, indent=2, ensure_ascii=False), encoding='utf-8')
    print('PASS: exact Upload/import parity; unknown variant rejected before grading/result images.', flush=True)


if __name__ == '__main__':
    main()
