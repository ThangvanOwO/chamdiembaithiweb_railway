"""Replay a manifest offline and compare CPU/time/answers with the legacy path.

No HTTP requests, account mutations, billing, or database writes. Input images
are copied to a new output folder; engine artifacts stay beside those copies.
Manifest: [{"name": "...", "image": "relative/or/absolute.jpg", "corners": [...],
            "pre_warped": false, "template": "template_default.json"}].
"""
import argparse
import contextlib
import hashlib
import io
import json
import logging
from pathlib import Path
import shutil
import statistics
import sys
import time
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
import cv2
from grading.engine import hi as engine

FIELDS = ('sbd', 'made', 'part1', 'part2', 'part3', 'score', 'max_score',
          'scores', 'scan_quality', 'validation_warnings', 'avg_confidence')
# A deterministic synthetic key tests scoring parity, not student accuracy.
KEY = {'part1': {q: 'ABCD'[(q - 1) % 4] for q in range(1, 41)},
       'part2': {q: {s: ('Dung' if i % 2 == 0 else 'Sai') for i, s in enumerate('abcd')}
                 for q in range(1, 9)},
       'part3': {1: '-0.2', 2: '1599', 3: '-0.8', 4: '1.25', 5: '22', 6: '7420'}}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--manifest', required=True, type=Path)
    parser.add_argument('--output', required=True, type=Path)
    parser.add_argument('--rounds', type=int, default=3)
    parser.add_argument('--threads', type=int, default=2)
    args = parser.parse_args()
    if args.rounds < 1 or args.threads < 1:
        parser.error('rounds and threads must be positive')
    args.output.mkdir(parents=True, exist_ok=False)
    cv2.setNumThreads(args.threads)
    logging.disable(logging.WARNING)
    records = []
    original_copy = shutil.copy2
    for fixture in json.loads(args.manifest.read_text(encoding='utf-8-sig')):
        name = fixture['name']
        if Path(name).name != name:
            raise ValueError('Fixture name must be a single path component')
        source = Path(fixture['image'])
        if not source.is_absolute():
            source = args.manifest.parent / source
        source_hash = hashlib.sha256(source.read_bytes()).hexdigest()
        engine.load_template(str(ROOT / 'grading/engine/templates' / fixture.get('template', 'template_default.json')))
        reference = None
        for mode, enabled, rounds in [('legacy', False, 1), ('optimized', True, args.rounds)]:
            for number in range(rounds):
                folder = args.output / name / f'{mode}_{number}'
                folder.mkdir(parents=True)
                image = folder / 'input.jpg'
                original_copy(source, image)

                def copy(src, dst, *a, **kw):
                    if Path(dst).parent.name == 'ketqua':
                        dst = folder / ('auto_' + Path(dst).name)
                    return original_copy(src, dst, *a, **kw)

                started, cpu = time.perf_counter(), time.process_time()
                with contextlib.redirect_stdout(io.StringIO()), patch.object(shutil, 'copy2', copy):
                    result = engine.process_sheet(
                        str(image), correct_answers=KEY, debug=False,
                        provided_corners=fixture.get('corners'),
                        pre_warped=fixture.get('pre_warped', False),
                        fast_mode=True, live_bubble_mode=True, live_validation=True,
                        live_cpu_fast=enabled,
                    )
                wall_s, cpu_s = time.perf_counter() - started, time.process_time() - cpu
                if not result:
                    raise RuntimeError(f'No result: {name}/{mode}')
                comparable = {k: result.get(k) for k in FIELDS}
                if reference is None:
                    reference = comparable
                differences = [k for k in FIELDS if reference[k] != comparable[k]]
                row = {'fixture': name, 'source_sha256': source_hash, 'mode': mode,
                       'round': number, 'wall_s': round(wall_s, 4), 'cpu_s': round(cpu_s, 4),
                       'preprocess_mode': result['preprocess_mode'], 'offsets': result['offsets'],
                       'differences': differences}
                if differences:
                    row['different_values'] = {k: {'legacy': reference[k], 'optimized': comparable[k]} for k in differences}
                records.append(row)
                (folder / 'recognition.json').write_text(json.dumps(comparable, indent=2, ensure_ascii=False), encoding='utf-8')
                (args.output / 'progress.json').write_text(json.dumps(records, indent=2, ensure_ascii=False), encoding='utf-8')
                print(json.dumps(row, ensure_ascii=False), flush=True)
    optimized = [r for r in records if r['mode'] == 'optimized']
    times = sorted(r['wall_s'] for r in optimized)
    p95 = times[max(0, int(len(times) * .95 + .999999) - 1)]
    summary = {'scope': 'Offline backend processing; excludes camera/network/DB/API encoding. Synthetic scoring key.',
               'threads': args.threads, 'fixtures': len({r['fixture'] for r in records}),
               'legacy_mean_s': statistics.mean(r['wall_s'] for r in records if r['mode'] == 'legacy'),
               'optimized_mean_s': statistics.mean(times), 'optimized_median_s': statistics.median(times),
               'optimized_sample_p95_s': p95, 'optimized_max_s': max(times),
               'fallbacks': sum(r['preprocess_mode'] != 'live_raw' for r in optimized),
               'parity_failures': sum(bool(r['differences']) for r in optimized), 'records': records}
    (args.output / 'report.json').write_text(json.dumps(summary, indent=2, ensure_ascii=False), encoding='utf-8')
    print(json.dumps({k: v for k, v in summary.items() if k != 'records'}), flush=True)
    if summary['parity_failures']:
        raise SystemExit(1)


if __name__ == '__main__':
    main()
