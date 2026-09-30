"""Offline audit of saved Live JPEGs. Never calls API or changes source images."""
import importlib.util
import json
import logging
from pathlib import Path
import re
import sys

import cv2
import numpy as np

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / 'grading' / 'engine'))
spec = importlib.util.spec_from_file_location('live_audit_engine', ROOT / 'grading/engine/hi.py')
engine = importlib.util.module_from_spec(spec)
spec.loader.exec_module(engine)
sys.path.insert(0, str(ROOT))
from grading.engine import live_bubble_reader as live
engine.HYBRID_CNN_ENABLE = False  # Offline worker only; do not load any model.
logging.disable(logging.WARNING)
engine.load_template(str(ROOT / 'grading/engine/templates/template_default.json'))
log = json.loads((ROOT / 'tests/ketqua/live_v3_device/20260911_212322_617709.json').read_text(encoding='utf-8'))
captures = []
for line in log['lines']:
    match = re.search(r'bytes=(\d+) corners=(\[.*\])', line)
    if match:
        captures.append((int(match[1]), json.loads(match[2])))
out = ROOT / 'tests/ketqua/live_bubble_audit_20260912'
out.mkdir(parents=True, exist_ok=True)
rows = []
for path in sorted((ROOT / 'media/submissions/2026/09').glob('live*.jpg')):
    matching = [points for size, points in captures if size == path.stat().st_size]
    if len(matching) != 1:
        continue
    warped = engine._warp_to_rect(cv2.imread(str(path)), np.float32(matching[0]))
    raw = cv2.cvtColor(warped, cv2.COLOR_BGR2GRAY)
    processed, _, _ = engine.preprocess(warped, mode='fast')
    answers, scores = engine.extract_part2(processed, fast_mode=True)
    new_answers, new_details = live.read_part2(raw, engine.PART2_BLOCKS,
        engine.PART2_STEP_X, engine.PART2_STEP_Y, engine.PART2_ROWS)
    new_p3, new_p3_details = live.read_part3(raw, engine.PART3_BLOCKS,
        engine.PART3_SIGN_Y, engine.PART3_COMMA_Y, engine.PART3_DIGIT_START_Y,
        engine.PART3_DIGIT_STEP_Y)
    probes = []
    for block in engine.PART2_BLOCKS:
        for row_index, label in enumerate(engine.PART2_ROWS):
            for choice_index, choice in enumerate(['Dung', 'Sai']):
                cx = block['start_x'] + choice_index * engine.PART2_STEP_X
                cy = block['start_y'] + row_index * engine.PART2_STEP_Y
                yy, xx = np.ogrid[:raw.shape[0], :raw.shape[1]]
                d2 = (xx - cx) ** 2 + (yy - cy) ** 2
                core = raw[d2 <= 6 ** 2]
                ring = raw[(d2 >= 16 ** 2) & (d2 <= 20 ** 2)]
                background = float(np.percentile(ring, 75))
                core_ratio = max(0.0, 1 - float(np.mean(core)) / max(1, background))
                probes.append({'q': block['q'], 'row': label, 'choice': choice,
                               'xy': [cx, cy], 'old': scores[block['q']][label][choice],
                               'raw_core_ratio': round(core_ratio, 3),
                               'raw_core_mean': round(float(np.mean(core)), 1),
                               'local_white': round(background, 1)})
    target = out / path.stem
    target.mkdir(exist_ok=True)
    cv2.imwrite(str(target / 'raw_warp.jpg'), warped)
    cv2.imwrite(str(target / 'part2_raw.png'), warped[1100:1330])
    cv2.imwrite(str(target / 'part2_processed.png'), processed[1100:1330])
    # Diagnostic overlays show detected marks only, not exam correctness/score.
    for label, picked in [('before', answers), ('after', new_answers)]:
        canvas = warped.copy()
        for block in engine.PART2_BLOCKS:
            for ri, row_label in enumerate(engine.PART2_ROWS):
                answer = picked[block['q']][row_label]
                if answer in ('Dung', 'Sai'):
                    x = block['start_x'] + (answer == 'Sai') * engine.PART2_STEP_X
                    y = block['start_y'] + ri * engine.PART2_STEP_Y
                    cv2.circle(canvas, (int(x), int(y)), 16, (0, 0, 240), 3)
        cv2.imwrite(str(target / ('part2_' + label + '.png')), canvas[1100:1330])
    row = {'source': str(path), 'corners': matching[0], 'old_part2': answers,
           'new_part2': new_answers, 'new_part3': new_p3,
           'new_part2_evidence': new_details, 'new_part3_evidence': new_p3_details,
           'probes': probes}
    (target / 'audit.json').write_text(json.dumps(row, indent=2), encoding='utf-8')
    rows.append(row)
    print(json.dumps({'source': path.name, 'old_part2': answers,
                      'selected': [p for p in probes if p['old'] >= .25]}, ensure_ascii=True))
(out / 'summary.json').write_text(json.dumps(rows, indent=2), encoding='utf-8')
