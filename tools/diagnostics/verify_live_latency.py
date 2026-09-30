"""Compare against byte-for-byte pre-edit engine; isolated outputs, no DB.

Exit failure on stable/single-pass/Upload parity regressions. The optional
background experiment records differences, NEVER relaxes parity assertions.
"""
import argparse
import hashlib
import json
import os
from pathlib import Path
import shutil
import sys
import time
import types
from contextlib import ExitStack
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'chamdiemtudong.settings')
import django
django.setup()
import cv2
import numpy as np
from grading import grader
from grading.live_latency import LiveAnswerKeySelection
from experimental_live_background import global_background


def comparable(result):
    excluded = {'processing_time', 'debug_log', 'result_image_path', 'name_image_path'}
    return {k: v for k, v in result.items() if k not in excluded}


def main():
    parser = argparse.ArgumentParser(__doc__)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    output = args.output.resolve()
    if output.exists() or not output.is_relative_to(ROOT):
        parser.error('Use a NEW output directory inside the workspace')
    output.mkdir(parents=True)
    current = grader.engine
    before = ROOT / 'scratch/restore_points/before_live_latency_20260914/before/grading/engine/hi.py'
    baseline = types.ModuleType('latency_baseline_engine')
    baseline.__file__ = current.__file__  # Same models/calibration/resource paths.
    sys.modules[baseline.__name__] = baseline
    exec(compile(before.read_bytes(), str(before), 'exec'), baseline.__dict__)
    source = ROOT / 'tests/fixtures/exam_import_v1.jpg'
    corners = json.loads(json.loads(source.with_suffix('.json').read_text())['corners'])
    rows = []
    copier = shutil.copy2

    def run(name, engine, key='', image=source, live=True, background_trial=False, **options):
        folder = output / name
        folder.mkdir()
        local = folder / 'input.jpg'
        copier(image, local)
        def relocate(src, dst, *a, **kw):
            if Path(dst).parent.resolve() == (ROOT / 'tests/ketqua').resolve():
                dst = folder / ('auto_' + Path(dst).name)
            return copier(src, dst, *a, **kw)
        started = time.perf_counter()
        with ExitStack() as stack:
            stack.enter_context(patch.object(grader, 'engine', engine))
            stack.enter_context(patch.object(shutil, 'copy2', relocate))
            if background_trial:
                original_blur = cv2.GaussianBlur
                def experimental_blur(src, ksize, sigmaX=0, *a, **kw):
                    if sigmaX == 120 and ksize == (0, 0):
                        # Avoid recursion: the reduced-size Gaussian is sigma=30.
                        return global_background(src)
                    return original_blur(src, ksize, sigmaX, *a, **kw)
                stack.enter_context(patch.object(cv2, 'GaussianBlur', experimental_blur))
            result = grader.grade_image(str(local), key, '40-08-06', corners=corners,
                                       fast_mode=True, live_bubble_mode=live, **options)
        elapsed = time.perf_counter() - started
        (folder / 'engine.log').write_text(result.get('debug_log', ''), encoding='utf-8')
        if not result.get('success'):
            raise RuntimeError(result)
        artifacts = {suffix: hashlib.sha256(local.with_name('input_' + suffix + '.jpg').read_bytes()).hexdigest()
                     for suffix in ('result', 'overlay', 'name', 'gray', 'thresh', 'cleaned', 'calibration')}
        row = {'name': name, 'seconds': elapsed, 'result': comparable(result), 'artifacts': artifacts}
        rows.append(row)
        print(f'{name}: {elapsed:.3f}s', flush=True)
        (output / 'progress.json').write_text(json.dumps(rows, indent=2, ensure_ascii=False), encoding='utf-8')
        return result, row

    old, old_row = run('baseline_no_key', baseline)
    assert (old['sbd'], old['made'], old['part3'][5]) == ('011232', '001', '22')
    same, same_row = run('switches_off', current)
    assert comparable(old) == comparable(same)
    assert old_row['artifacts'] == same_row['artifacts']
    correct = {k: old[k] for k in ('part1', 'part2', 'part3')}
    key_final = json.dumps(correct)
    first = json.loads(key_final)
    first['part1']['1'] = 'D' if first['part1']['1'] != 'D' else 'A'
    first['part2']['1']['a'] = 'Sai' if first['part2']['1'].get('a') == 'Dung' else 'Dung'
    first['part3']['5'] = '999'
    key_first = json.dumps(first)
    _, first_row = run('old_first_wrong_key', baseline, key_first)
    expected, expected_row = run('old_second_final_key', baseline, key_final)
    selection = LiveAnswerKeySelection(key_first, [('999', key_first), ('001', key_final)], grader.parse_answer_key)
    selected, selected_row = run('new_single_pass', current, key_first,
                                 live_answer_key_resolver=selection.resolve)
    assert selection.used_key == key_final
    assert comparable(expected) == comparable(selected), 'Single-pass changed result/evidence'
    assert expected_row['artifacts'] == selected_row['artifacts'], 'Final-key image pixels differ'
    assert expected_row['artifacts']['result'] != first_row['artifacts']['result']
    for config in (None, {'p1': .25, 'p2_mode': 'moet', 'p3': .5},
                   {'p1': 1., 'p2_mode': 'raw', 'p3': 2., 'max': 10}):
        assert grader.compute_weighted_score(expected, config, grader.parse_answer_key(key_final)) == \
               grader.compute_weighted_score(selected, config, grader.parse_answer_key(key_final))
    old_upload, upload_row = run('old_upload', baseline, key_final, live=False)
    def forbidden(_):
        raise AssertionError('Upload must ignore Live resolver')
    new_upload, new_upload_row = run('new_upload_flags_ignored', current, key_final, live=False,
                                    live_answer_key_resolver=forbidden)
    assert comparable(old_upload) == comparable(new_upload)
    assert upload_row['artifacts'] == new_upload_row['artifacts']

    # Controlled perturbations are NOT additional independent real captures.
    pixels = cv2.imread(str(source))
    h, w = pixels.shape[:2]
    gradient = np.linspace(.60, 1.0, w)[None, :, None]
    variants = [('original', None),
                ('dim', np.clip(pixels.astype(float) * .75, 0, 255).astype(np.uint8)),
                ('bright', np.clip(pixels.astype(float) * 1.12, 0, 255).astype(np.uint8)),
                ('soft_blur', cv2.GaussianBlur(pixels, (3, 3), .7)),
                ('shadow', np.clip(pixels.astype(float) * gradient, 0, 255).astype(np.uint8)),
                ('faint_contrast', np.clip(235 + .65 * (pixels.astype(float) - 235), 0, 255).astype(np.uint8))]
    trial_rows = []
    for name, transformed in variants:
        image = source
        if transformed is not None:
            image = output / (name + '.jpg')
            assert cv2.imwrite(str(image), transformed, [cv2.IMWRITE_JPEG_QUALITY, 95])
        stable, stable_row = (expected, expected_row) if name == 'original' else run(name + '_stable', current, key_final, image)
        trial, trial_row = run(name + '_background_trial', current, key_final, image, background_trial=True)
        answer_fields = ('sbd', 'made', 'part1', 'part2', 'part3', 'scores', 'score', 'max_score')
        differences = [key for key in answer_fields if stable[key] != trial[key]]
        evidence_differences = [key for key in comparable(stable) if comparable(stable)[key] != comparable(trial)[key]]
        trial_rows.append({'case': name, 'answer_differences': differences,
                           'all_field_differences': evidence_differences,
                           'stable_seconds': stable_row['seconds'], 'trial_seconds': trial_row['seconds']})
        print(f'  trial parity: {name}: {differences}', flush=True)
    report = {'baseline_sha256': hashlib.sha256(before.read_bytes()).hexdigest(),
              'fixture_sha256': hashlib.sha256(source.read_bytes()).hexdigest(),
              'single_pass_exact_result_and_artifact_parity': True, 'weighted_score_parity': True,
              'upload_exact_parity': True,
              'old_two_pass_seconds': first_row['seconds'] + expected_row['seconds'],
              'new_single_pass_seconds': selected_row['seconds'],
              'background_trial_in_production': False, 'trial_cases': trial_rows, 'runs': rows}
    (output / 'report.json').write_text(json.dumps(report, indent=2, ensure_ascii=False), encoding='utf-8')
    print('PASS: single-pass + rollback + Upload parity. Background stays experimental.', flush=True)


if __name__ == '__main__':
    main()
