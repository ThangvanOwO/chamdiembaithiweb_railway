"""Run the real API/engine/encoding offline with billing and ORM isolated.

Uses a synthetic answer key and mocked ownership lookup; no account creation,
database writes or real charges. Includes response rendering and image payloads,
but excludes the camera, transport and production database latency.
"""
import argparse
import json
import logging
import os
from pathlib import Path
import statistics
import sys
import time
from types import SimpleNamespace
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'chamdiemtudong.settings')
import django
django.setup()
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import override_settings
from rest_framework.test import APIRequestFactory, force_authenticate
from api import views
from tools.diagnostics.benchmark_live_cpu import KEY


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--manifest', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--rounds', type=int, default=3)
    args = parser.parse_args()
    args.output.mkdir(parents=True, exist_ok=False)
    logging.disable(logging.WARNING)
    key = json.dumps(KEY)
    variants = [SimpleNamespace(variant_code=code, answer_key_str=key) for code in ('001', '676', '122')]
    exam = SimpleNamespace(template_code='40-08-06', answer_key=key,
                           variants=SimpleNamespace(all=lambda: variants))
    records = []
    for fixture in json.loads(args.manifest.read_text(encoding='utf-8-sig')):
        if not fixture.get('corners'):
            continue
        source = Path(fixture['image'])
        if not source.is_absolute():
            source = args.manifest.parent / source
        reference = None
        for mode, enabled, rounds in [('legacy', False, 1), ('optimized', True, args.rounds)]:
            for index in range(rounds):
                fields = {'image': SimpleUploadedFile('live.jpg', source.read_bytes(), content_type='image/jpeg'),
                          'exam_id': '1', 'save': 'false', 'fast': '1', 'capture_pipeline': 'live_capture_v3',
                          'corners': json.dumps(fixture['corners'])}
                request = APIRequestFactory().post('/api/v1/grade/', fields, format='multipart')
                force_authenticate(request, user=SimpleNamespace(is_authenticated=True, is_active=True, is_staff=False))
                started, cpu = time.perf_counter(), time.process_time()
                with override_settings(LIVE_SINGLE_PASS_GRADING=True), \
                     patch.dict(os.environ, {'LIVE_CPU_FAST': '1' if enabled else '0'}), \
                     patch.object(views.Exam.objects, 'get', return_value=exam), \
                     patch.object(views.Submission.objects, 'create', side_effect=AssertionError('No DB writes')), \
                     patch('accounts.scan_billing._request_identity', return_value=('offline-benchmark', 'fingerprint')), \
                     patch('accounts.scan_billing.reserve_scan', return_value=(SimpleNamespace(), True)), \
                     patch('accounts.scan_billing.finish_scan'), patch('shutil.copy2'):
                    response = views.grade_api(request)
                    response.render()
                result = response.data
                if response.status_code != 200 or not result.get('success'):
                    raise RuntimeError(f"API rejected {fixture['name']}/{mode}: {result.get('error')}")
                comparable = {k: result[k] for k in ('sbd', 'made', 'part1', 'part2', 'part3',
                                  'score', 'scores', 'weighted', 'scan_quality', 'validation_warnings')}
                if reference is None:
                    reference = comparable
                row = {'fixture': fixture['name'], 'mode': mode, 'round': index,
                       'wall_s': round(time.perf_counter() - started, 4),
                       'cpu_s': round(time.process_time() - cpu, 4),
                       'engine_s': result['processing_time'], 'response_bytes': len(response.content),
                       'preprocess_mode': result['preprocess_mode'],
                       'differences': [k for k in comparable if reference[k] != comparable[k]]}
                records.append(row)
                (args.output / 'progress.json').write_text(json.dumps(records, indent=2), encoding='utf-8')
                print(json.dumps(row), flush=True)
    fast = [r for r in records if r['mode'] == 'optimized']
    summary = {'scope': __doc__, 'legacy_mean_s': statistics.mean(r['wall_s'] for r in records if r['mode'] == 'legacy'),
               'optimized_mean_s': statistics.mean(r['wall_s'] for r in fast),
               'optimized_max_s': max(r['wall_s'] for r in fast),
               'legacy_mean_bytes': statistics.mean(r['response_bytes'] for r in records if r['mode'] == 'legacy'),
               'optimized_mean_bytes': statistics.mean(r['response_bytes'] for r in fast),
               'parity_failures': sum(bool(r['differences']) for r in fast), 'records': records}
    (args.output / 'report.json').write_text(json.dumps(summary, indent=2), encoding='utf-8')
    print(json.dumps({k: v for k, v in summary.items() if k != 'records'}), flush=True)
    if summary['parity_failures']:
        raise SystemExit(1)


if __name__ == '__main__':
    main()
