"""Live-only OMR evidence from the unmodified, geometrically rectified JPEG.

Never measure ink against an artificial white text-erasure mask. No CNN/argmax
rescue can turn a blank raw bubble into a selected answer. Upload is not routed
here; the caller must explicitly request live_capture_v3.
"""
from dataclasses import asdict, dataclass

import cv2
import numpy as np


def align_grid(gray, columns, rows, radius=13, diagnostics=None):
    """Fit printed circle centers, not darkest pixels, to the expected grid.

    Independent row/column medians tolerate template printing scale and the
    nonuniform legacy identifier row coordinates. Require broad grid support;
    sparse marks/text cannot translate the grid. No global template mutation.
    """
    xs, ys = np.asarray(columns, float), np.asarray(rows, float)
    spacing = min(np.min(np.diff(xs)) if len(xs) > 1 else 30, np.min(np.diff(ys)))
    tolerance = min(12.0, spacing * .43)
    pad = int(radius * 2)
    x0, y0 = max(0, int(xs.min()) - pad), max(0, int(ys.min()) - pad)
    x1, y1 = min(gray.shape[1], int(xs.max()) + pad + 1), min(gray.shape[0], int(ys.max()) + pad + 1)
    roi = gray[y0:y1, x0:x1]
    if roi.size == 0:
        return xs.tolist(), ys.tolist(), False
    circles = cv2.HoughCircles(cv2.GaussianBlur(roi, (3, 3), 0), cv2.HOUGH_GRADIENT,
        dp=1, minDist=max(10, spacing * .65), param1=60, param2=15,
        minRadius=max(5, int(radius * .60)), maxRadius=int(radius * 1.2))
    if circles is None:
        return xs.tolist(), ys.tolist(), False
    matched = {}
    for x, y, _ in circles[0]:
        x, y = float(x + x0), float(y + y0)
        col, row = int(np.argmin(abs(xs-x))), int(np.argmin(abs(ys-y)))
        distance = float(np.hypot(xs[col]-x, ys[row]-y))
        if max(abs(xs[col]-x), abs(ys[row]-y)) <= tolerance and (
                (col, row) not in matched or distance < matched[col, row][2]):
            matched[col, row] = (x, y, distance)
    if diagnostics is not None:
        diagnostics.update(circles=len(circles[0]), matched=len(matched),
                           cells={str(k): v for k, v in matched.items()})
    if len(matched) < len(xs) * len(ys) * .55:
        return xs.tolist(), ys.tolist(), False
    x_groups = [[p[0] for (c, r), p in matched.items() if c == col] for col in range(len(xs))]
    y_groups = [[p[1] for (c, r), p in matched.items() if r == row] for row in range(len(ys))]
    supported = [i for i, g in enumerate(y_groups) if len(g) >= max(2, len(xs) * .4)]
    if any(len(g) < len(ys) * .4 for g in x_groups) or len(supported) < len(ys) * .8:
        return xs.tolist(), ys.tolist(), False
    new_x = [float(np.median(g)) for g in x_groups]
    observed = np.array([np.median(y_groups[i]) for i in supported])
    # Filled circles sometimes lack a detectable rim. Infer at most 20% rows
    # only when the remaining printed rows prove a regular grid, not from ink.
    line = np.polyfit(supported, observed, 1)
    if len(supported) < len(ys) and np.max(abs(np.polyval(line, supported) - observed)) > 2.5:
        return xs.tolist(), ys.tolist(), False
    new_y = [float(np.median(y_groups[i])) if i in supported else float(np.polyval(line, i))
             for i in range(len(ys))]
    if np.max(abs(np.asarray(new_y) - ys)) > tolerance:
        return xs.tolist(), ys.tolist(), False
    if min(np.diff(new_x)) < spacing * .65 or min(np.diff(new_y)) < spacing * .65:
        return xs.tolist(), ys.tolist(), False
    return new_x, new_y, True


def read_identifiers(gray, sbd_columns, made_columns, rows):
    """Live SBD/mã đề: raw ink evidence with locally aligned smaller circles."""
    output, details = [], {}
    for name, columns in [('sbd', sbd_columns), ('made', made_columns)]:
        xs, ys, aligned = align_grid(gray, columns, rows, radius=10)
        digits, scores, evidence = [], [], []
        for x in xs:
            ev = [measure_ink(gray, x, y, radius=10) for y in ys]
            picked, _ = _select(ev)
            digits.append(str(picked) if picked >= 0 else '?')
            scores.append({d: e.score for d, e in enumerate(ev)})
            evidence.append([asdict(e) for e in ev])
        output.append(''.join(digits))
        details[name] = scores
        details[name + '_live'] = {'aligned': aligned, 'columns': xs, 'rows': ys, 'evidence': evidence}
    return output[0], output[1], details


@dataclass(frozen=True)
class InkEvidence:
    state: str
    contrast: float
    coverage: float
    dark_quarters: int

    @property
    def score(self):
        return round(self.contrast, 3) if self.state == 'marked' else 0.0


def measure_ink(gray, cx, cy, radius=13, *, row_background=False):
    """Use the inner half-radius and nearby real paper; exclude printed rim.

    An absolute local contrast, filled area and spatial support must agree.
    Border/erasure/small speck evidence is not rescued by relative ranking.
    """
    cx, cy = int(round(cx)), int(round(cy))
    pad = int(np.ceil(radius * 1.6))
    h, w = gray.shape[:2]
    if gray.ndim != 2 or cx - pad < 0 or cy - pad < 0 or cx + pad >= w or cy + pad >= h:
        return InkEvidence('invalid', 0.0, 0.0, 0)
    roi = gray[cy-pad:cy+pad+1, cx-pad:cx+pad+1].astype(np.float32)
    yy, xx = np.mgrid[-pad:pad+1, -pad:pad+1]
    r2 = xx * xx + yy * yy
    core = r2 <= max(3, radius * .5) ** 2
    ring = (r2 >= (radius * 1.25) ** 2) & (r2 <= (radius * 1.55) ** 2)
    background = float(np.percentile(roi[ring], 75))
    if background < 45:
        return InkEvidence('invalid', 0.0, 0.0, 0)
    if row_background:
        # A curled bottom edge casts a horizontal shadow through digit rows.
        # The annulus sees brighter paper above/below it. Measure paper on both
        # sides at the same scanline, outside the printed rim. The brighter side
        # prevents a neighboring rim from hiding faint ink; keep all thresholds.
        side = (abs(xx[0]) >= radius * 1.25) & (abs(xx[0]) <= radius * 1.55)
        left = np.percentile(roi[:, side & (xx[0] < 0)], 75, axis=1)
        right = np.percentile(roi[:, side & (xx[0] > 0)], 75, axis=1)
        core_rows = np.any(core, axis=1)
        if min(left[core_rows].min(), right[core_rows].min()) < 45:
            return InkEvidence('invalid', 0.0, 0.0, 0)
        paper = np.broadcast_to(np.maximum(left, right)[:, None], roi.shape)
        contrast = float(np.clip(1 - np.mean(roi[core] / paper[core]), 0, 1))
        dark = roi < paper - np.maximum(12, paper * .12)
    else:
        contrast = float(np.clip(1 - roi[core].mean() / background, 0, 1))
        dark = roi < background - max(12, background * .12)
    coverage = float(dark[core].mean())
    quarters = [(xx < 0) & (yy < 0), (xx >= 0) & (yy < 0),
                (xx < 0) & (yy >= 0), (xx >= 0) & (yy >= 0)]
    dark_quarters = sum(float(dark[core & q].mean()) >= .5 for q in quarters)
    if contrast >= .16 and coverage >= .60 and dark_quarters >= 3:
        state = 'marked'
    elif contrast < .07 and coverage < .20:
        state = 'blank'
    else:
        state = 'uncertain'
    return InkEvidence(state, round(contrast, 4), round(coverage, 4), dark_quarters)


def _select(evidence):
    marked = [i for i, e in enumerate(evidence) if e.state == 'marked']
    uncertain = any(e.state in ('uncertain', 'invalid') for e in evidence)
    if len(marked) == 1 and not uncertain:
        return marked[0], False
    return -1, uncertain or len(marked) > 1


def read_part1(gray, blocks, choices, radius=13, y_offset=0, limit=None):
    """Absolute raw-paper evidence; double marks never become a winning argmax."""
    answers, scores, details = {}, {}, {}
    for index, block in enumerate(blocks):
        xs, ys, aligned = align_grid(gray,
            [block['start_x'] + i * block['step_x'] for i in range(len(choices))],
            [block['start_y'] + i * block['step_y'] + y_offset for i in range(10)], radius)
        for row, y in enumerate(ys):
            q = index * 10 + row + 1
            if limit is not None and q > limit:
                continue
            evidence = [measure_ink(gray, x, y, radius) for x in xs]
            picked, review = _select(evidence)
            marked = sum(e.state == 'marked' for e in evidence)
            answers[q] = 'X' if marked > 1 else choices[picked] if picked >= 0 else ''
            scores[q] = {choice: e.score for choice, e in zip(choices, evidence)}
            details[q] = {'evidence': [asdict(e) for e in evidence], 'needs_review': review,
                          'points': list(zip(xs, [y] * len(xs))), 'aligned': aligned}
    return answers, scores, details


def read_part2(gray, blocks, step_x, step_y, labels, radius=13, y_offset=0, limit=None, align=False):
    answers, details = {}, {}
    paired_grids = {}
    if align:
        # Adjacent question pairs provide four printed columns: enough support
        # to fit a row even when filled circles hide some rims. Same tolerances.
        for start in range(0, len(blocks) - 1, 2):
            pair = blocks[start:start + 2]
            if abs(pair[0]['start_y'] - pair[1]['start_y']) > 1:
                continue
            columns = [b['start_x'] + c * step_x for b in pair for c in range(2)]
            rows = [pair[0]['start_y'] + r * step_y + y_offset for r in range(len(labels))]
            px, py, ok = align_grid(gray, columns, rows, radius)
            if ok:
                for i, b in enumerate(pair):
                    paired_grids[b['q']] = (px[i * 2:i * 2 + 2], py, True)
    for block in blocks:
        q = block['q']
        if limit is not None and q > limit:
            continue
        answers[q], details[q] = {}, {}
        xs = [block['start_x'] + col * step_x for col in range(2)]
        ys = [block['start_y'] + row * step_y + y_offset for row in range(len(labels))]
        aligned = False
        if align:
            xs, ys, aligned = paired_grids[q] if q in paired_grids else align_grid(gray, xs, ys, radius)
        for row, label in enumerate(labels):
            cy = ys[row]
            ev = [measure_ink(gray, xs[col], cy, radius)
                  for col in range(2)]
            picked, _ = _select(ev)
            answers[q][label] = ('Dung', 'Sai')[picked] if picked >= 0 else ''
            if all(e.state == 'marked' for e in ev):
                answers[q][label] = 'X'
            details[q][label] = {'Dung': ev[0].score, 'Sai': ev[1].score,
                                  'live_evidence': [asdict(e) for e in ev]}
            if align:
                details[q][label].update(points=list(zip(xs, [cy, cy])), aligned=aligned)
    return answers, details


def read_part3(gray, blocks, sign_y, comma_y, digit_y, digit_step,
               radius=13, y_offset=0, limit=None, local_symbols=False):
    answers, details = {}, {}
    for block in blocks:
        q = block['q']
        if limit is not None and q > limit:
            continue
        xs, ys, aligned = align_grid(gray, block['cols_x'],
            [digit_y + d * digit_step + y_offset for d in range(10)], radius)
        shift_x = float(np.median(np.asarray(xs) - block['cols_x']))
        shift_y = float(np.median(np.asarray(ys) -
            [digit_y + d * digit_step + y_offset for d in range(10)]))
        sign_point = [block['sign_x'] + shift_x, sign_y + y_offset + shift_y]
        comma_points = [[x, comma_y + y_offset + shift_y] for x in xs]
        if local_symbols and aligned:
            # Extrapolate the nearby printed top digit rows, not the median
            # shift of all ten rows (which drifts on vertically scaled sheets).
            step = float(np.median(np.diff(ys[:4])))
            if .8 * digit_step <= step <= 1.2 * digit_step:
                symbol_y = lambda y: ys[0] + (y - digit_y) * step / digit_step
                sign_point = [xs[0] + block['sign_x'] - block['cols_x'][0], symbol_y(sign_y)]
                comma_points = [[x, symbol_y(comma_y)] for x in xs]
        sign = measure_ink(gray, *sign_point, radius)
        commas = [measure_ink(gray, *point, radius) for point in comma_points]
        comma_col, uncertain = _select(commas)
        uncertain |= sign.state in ('uncertain', 'invalid')
        digits, digit_scores, evidence = [], [], []
        for x in xs:
            ev = [measure_ink(gray, x, y, radius,
                             row_background=local_symbols and aligned) for y in ys]
            picked, ambiguous = _select(ev)
            uncertain |= ambiguous
            digits.append(picked)
            digit_scores.append({d: e.score for d, e in enumerate(ev)})
            evidence.append([asdict(e) for e in ev])
        if local_symbols:
            if comma_col >= 0 and not (any(d >= 0 for d in digits[:comma_col]) and
                                      any(d >= 0 for d in digits[comma_col:])):
                uncertain = True  # Never silently drop a trailing decimal mark.
            occupied = [i for i, d in enumerate(digits) if d >= 0 or i == comma_col]
            if occupied and occupied != list(range(occupied[0], occupied[-1] + 1)):
                uncertain = True  # Missing middle digit is not concatenated away.
            if sign.state == 'marked' and not any(d >= 0 for d in digits):
                uncertain = True
        # Do not silently concatenate a partial answer around an ambiguous digit.
        answer = ''
        if not uncertain:
            for i, digit in enumerate(digits):
                if i == comma_col and answer and any(d >= 0 for d in digits[i:]):
                    answer += '.'
                if digit >= 0:
                    answer += str(digit)
            if sign.state == 'marked' and answer:
                answer = '-' + answer
        answers[q] = answer
        details[q] = {
            'sign': sign.score, 'comma': [e.score for e in commas],
            'digits': digit_scores, 'digits_score': digit_scores,
            'picked': {'sign': sign.state == 'marked', 'comma_col': comma_col, 'digits': digits},
            'ocr_digits': [], 'ocr_boxes': [], 'ocr_ink': [],
            'live_grid': {'aligned': aligned, 'columns': xs, 'rows': ys,
                          'sign': sign_point, 'commas': comma_points},
            'live_evidence': {'sign': asdict(sign), 'comma': [asdict(e) for e in commas],
                              'digits': evidence, 'needs_review': bool(uncertain)},
        }
    return answers, details


def draw_part3(image, results, details, blocks, sign_y, comma_y, digit_y,
               digit_step, radius, thickness, correct_color, wrong_color, y_offset=0, warn_ambiguous=False):
    """Draw only selected cells; never loop over all above-threshold ratios.

    Separate Live renderer avoids the legacy for/else fallback drawing extra
    circles after the OCR loop. Scores, picked cells and overlay stay consistent.
    """
    by_q = {block['q']: block for block in blocks}
    for q, result in results.items():
        evidence = details[q].get('live_evidence', {})
        grid = details[q].get('live_grid')
        if warn_ambiguous and evidence.get('needs_review') and grid:
            pairs = [(grid['sign'], evidence['sign'])]
            pairs.extend(zip(grid['commas'], evidence['comma']))
            pairs.extend(((grid['columns'][col], grid['rows'][digit]), item)
                         for col, column in enumerate(evidence['digits']) for digit, item in enumerate(column))
            for point, item in pairs:
                if item['state'] in ('marked', 'uncertain'):
                    cv2.circle(image, tuple(int(round(v)) for v in point), radius + 3, (0, 200, 255), thickness)
            continue
        if not result.get('student') or result['student'] in ('X', '-'):
            continue
        block, picked = by_q[q], details[q]['picked']
        grid = details[q].get('live_grid')
        color = correct_color if result['is_correct'] else wrong_color
        points = []
        if picked['sign']:
            points.append(grid['sign'] if grid else (block['sign_x'], sign_y + y_offset))
        comma = picked['comma_col']
        if 0 <= comma < len(block['cols_x']):
            points.append(grid['commas'][comma] if grid else (block['cols_x'][comma], comma_y + y_offset))
        for col, digit in enumerate(picked['digits']):
            if 0 <= digit <= 9:
                points.append((grid['columns'][col], grid['rows'][digit]) if grid else
                              (block['cols_x'][col], digit_y + digit * digit_step + y_offset))
        for x, y in points:
            cv2.circle(image, (int(round(x)), int(round(y))), radius + 3, color, thickness)


def draw_choice_result(image, result, evidence, points, choices, radius, thickness):
    """Live legend: selected correct=green, wrong=red, unresolved=yellow.

    Do not draw the answer key on an empty circle as if the student marked it.
    """
    review = result['student'] in ('X', '') and any(e['state'] != 'blank' for e in evidence)
    for choice, item, point in zip(choices, evidence, points):
        color = None
        if review and item['state'] in ('marked', 'uncertain'):
            color = (0, 200, 255)
        elif choice == result['student']:
            color = (0, 180, 0) if result['is_correct'] else (0, 0, 220)
        if color:
            cv2.circle(image, tuple(int(round(v)) for v in point), radius + 3, color, thickness)
