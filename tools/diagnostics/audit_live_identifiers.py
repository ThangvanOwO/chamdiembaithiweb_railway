"""Register original camera JPEGs to the supplied result for OFFLINE diagnosis.

SIFT/RANSAC is only used to recover this run's warp from an annotated result.
Detection measurements use the original pixels, never the red overlay.
"""
import json
from pathlib import Path
import sys

import cv2
import numpy as np

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
from grading.engine import hi as engine
from grading.engine import live_bubble_reader as reader

engine.load_template(str(ROOT / 'grading/engine/templates/template_default.json'))
OUT = ROOT / 'tests/ketqua/live_identifiers_20260912'
OUT.mkdir(parents=True, exist_ok=True)
PAIRS = [
    ('live_O2ZBpeK.jpg', '20260912_051201_live_sbd_011_3__md___1_result.jpg'),
    ('live_F6lMUpt.jpg', '20260912_121135_tmpdnbev9i2_sbd_011_3__md_0_1_result.jpg'),
    ('live_Mq6I2UX.jpg', '20260912_051225_live_sbd_011_3__md_0_1_result.jpg'),
]
summary = []
for original_name, result_name in PAIRS:
    original = cv2.imread(str(ROOT / 'media/submissions/2026/09' / original_name))
    result = cv2.imread(str(ROOT / 'tests/ketqua' / result_name))
    sift = cv2.SIFT_create(nfeatures=6000)
    k1, d1 = sift.detectAndCompute(cv2.cvtColor(original, cv2.COLOR_BGR2GRAY), None)
    k2, d2 = sift.detectAndCompute(cv2.cvtColor(result, cv2.COLOR_BGR2GRAY), None)
    matches = cv2.BFMatcher().knnMatch(d1, d2, k=2)
    good = [a for a, b in matches if a.distance < .7 * b.distance]
    src = np.float32([k1[m.queryIdx].pt for m in good])
    dst = np.float32([k2[m.trainIdx].pt for m in good])
    h, mask = cv2.findHomography(src, dst, cv2.RANSAC, 2.0)
    assert h is not None and int(mask.sum()) > 100, 'Registration unreliable'
    predicted = cv2.perspectiveTransform(src.reshape(-1, 1, 2), h).reshape(-1, 2)
    error = float(np.median(np.linalg.norm(predicted - dst, axis=1)[mask.ravel() > 0]))
    assert error < 1.0
    warped = cv2.warpPerspective(original, h, (1400, 1920))
    gray = cv2.cvtColor(warped, cv2.COLOR_BGR2GRAY)
    p3, details = reader.read_part3(gray, engine.PART3_BLOCKS, engine.PART3_SIGN_Y,
        engine.PART3_COMMA_Y, engine.PART3_DIGIT_START_Y, engine.PART3_DIGIT_STEP_Y)
    row = {'source': original_name, 'reference': result_name,
           'inliers': int(mask.sum()), 'median_error_px': error, 'homography': h.tolist(),
           'p3': p3, 'q5': details[5], 'identifiers': {}}
    row['read_identifiers'] = reader.read_identifiers(gray, engine.SBD_COLS_X, engine.MADE_COLS_X, engine.SBD_MADE_DIGIT_Y)
    note = {}
    reader.align_grid(gray, engine.MADE_COLS_X, engine.SBD_MADE_DIGIT_Y, 10, note)
    row['made_alignment_debug'] = note
    if row['read_identifiers'][1] != '001':
        print(json.dumps(note))
    for name, columns in [('sbd', engine.SBD_COLS_X), ('made', engine.MADE_COLS_X)]:
        row['identifiers'][name] = [
            [reader.measure_ink(gray, x, y).__dict__ for y in engine.SBD_MADE_DIGIT_Y]
            for x in columns]
    folder = OUT / Path(original_name).stem
    folder.mkdir(exist_ok=True)
    cv2.imwrite(str(folder / 'raw_warp.png'), warped)
    cv2.imwrite(str(folder / 'identifiers.png'), warped[90:570, 1000:1390])
    cv2.imwrite(str(folder / 'q5.png'), warped[1400:1900, 960:1150])
    # Diagnostic selections, not correctness/score; no answer key is supplied.
    overlay = warped.copy()
    reader.draw_part3(overlay, {q: {'student': answer, 'is_correct': False} for q, answer in p3.items()},
        details, engine.PART3_BLOCKS, engine.PART3_SIGN_Y, engine.PART3_COMMA_Y,
        engine.PART3_DIGIT_START_Y, engine.PART3_DIGIT_STEP_Y, 13, 2, (0,180,255), (0,180,255))
    sbd, made, id_details = row['read_identifiers']
    for name, value in [('sbd', sbd), ('made', made)]:
        grid = id_details[name + '_live']
        for col, digit in enumerate(value):
            if digit.isdigit():
                cv2.circle(overlay, (round(grid['columns'][col]), round(grid['rows'][int(digit)])),
                           11, (0,180,255), 2)
    cv2.putText(overlay, f'DIAGNOSTIC ONLY | SBD {sbd} | MD {made} | P3 Q5 {p3[5]}',
                (25, 65), cv2.FONT_HERSHEY_SIMPLEX, .8, (180,30,10), 2)
    cv2.imwrite(str(folder / 'verified_live.png'), overlay)
    (folder / 'audit.json').write_text(json.dumps(row, indent=2), encoding='utf-8')
    summary.append(row)
    print(json.dumps({'source': original_name, 'inliers': row['inliers'], 'p3': p3,
        'ids': row['read_identifiers'][:2], 'q5_grid': details[5].get('live_grid'),
        'q5_nonblank': [(col, d, e) for col, values in enumerate(details[5]['live_evidence']['digits'])
            for d, e in enumerate(values) if e['state'] != 'blank'],
        'q5_other': {k: v for k, v in details[5]['live_evidence'].items() if k != 'digits'}}, ensure_ascii=True))
(OUT / 'summary.json').write_text(json.dumps(summary, indent=2), encoding='utf-8')
