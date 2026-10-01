"""Question-only raw crops and reviewed datasets. Does not train or change OMR."""
import hashlib
import io
import json
import re
import zipfile
from pathlib import Path

import cv2
import numpy as np
from PIL import Image, ImageOps

from grading.cpu_runtime import serialized_grading


def decode_photo(raw):
    if not raw or len(raw) > 10 * 1024 * 1024:
        raise ValueError('Ảnh phải nhỏ hơn 10 MB.')
    try:
        with Image.open(io.BytesIO(raw)) as image:
            if image.width * image.height > 25_000_000:
                raise ValueError('Ảnh quá lớn (tối đa 25 triệu pixel).')
            image.load()
            return cv2.cvtColor(np.asarray(ImageOps.exif_transpose(image).convert('RGB')), cv2.COLOR_RGB2BGR)
    except (OSError, Image.DecompressionBombError) as exc:
        raise ValueError('Không đọc được ảnh gốc.') from exc


def _prepare_photo(raw, template_code, corners):
    from grading.grader import engine, TEMPLATES_DIR
    if not re.fullmatch(r'[A-Za-z0-9-]{1,30}', template_code):
        raise ValueError('Mã phiếu không hợp lệ.')
    path = TEMPLATES_DIR / ('template_default.json' if template_code == '40-08-06'
                            else f'template_{template_code.replace("-", "_")}.json')
    if not path.is_file():
        raise ValueError('Chọn đúng mẫu phiếu trước khi gán nhãn.')
    engine.load_template(str(path))
    photo = decode_photo(raw)
    if corners is not None:
        points = np.asarray(corners, dtype=np.float32)
        h, w = photo.shape[:2]
        if (points.shape != (4, 2) or not np.isfinite(points).all()
                or (points < 0).any() or (points[:, 0] >= w).any() or (points[:, 1] >= h).any()
                or not cv2.isContourConvex(points.astype(np.int32))
                or abs(cv2.contourArea(points)) < w * h * .05):
            raise ValueError('Tọa độ góc không khớp ảnh gốc.')
        warped = engine.warp_perspective(photo, engine.order_points(points))
        method = 'frontend_corners'
    else:
        detection = engine.detect_paper_and_warp(photo, debug=False)
        if not detection['success']:
            raise ValueError('Không tìm được phiếu; hãy chụp lại đủ bốn góc.')
        warped, method = detection['warped'], detection['method']
    return cv2.cvtColor(warped, cv2.COLOR_BGR2GRAY), engine, method, hashlib.sha256(path.read_bytes()).hexdigest()


def _read_part(gray, engine, part):
    from grading.engine import live_bubble_reader as reader
    if part == 1:
        answers, _, details = reader.read_part1(gray, engine.PART1_COLS, engine.PART1_CHOICES, engine.BUBBLE_RADIUS)
    elif part == 2:
        answers, details = reader.read_part2(gray, engine.PART2_BLOCKS, engine.PART2_STEP_X,
            engine.PART2_STEP_Y, engine.PART2_ROWS, engine.BUBBLE_RADIUS, align=True)
    elif part == 3:
        answers, details = reader.read_part3(gray, engine.PART3_BLOCKS, engine.PART3_SIGN_Y,
            engine.PART3_COMMA_Y, engine.PART3_DIGIT_START_Y, engine.PART3_DIGIT_STEP_Y,
            engine.BUBBLE_RADIUS, local_symbols=True)
    else:
        raise ValueError('Phần không hợp lệ.')
    return answers, details


def _crop_question(gray, engine, part, question, subquestion, answers, details,
                   source_hash, template_code, method, template_hash):
    cells, evidence = [], []
    def cell(key, point, ink):
        cells.append({'id': key, 'x': float(point[0]), 'y': float(point[1])})
        evidence.append(ink)
    radius = engine.BUBBLE_RADIUS
    try:
        if part == 1:
            if subquestion:
                raise ValueError('Phần I chọn cả câu.')
            detail = details[question]
            for choice, point, ink in zip(engine.PART1_CHOICES, detail['points'], detail['evidence']):
                cell(choice, point, ink)
            detected, aligned = answers[question], detail['aligned']
            needs_review = detail['needs_review']
        elif part == 2:
            if subquestion not in ('a', 'b', 'c', 'd'):
                raise ValueError('Chọn ý a, b, c hoặc d.')
            detail = details[question][subquestion]
            for choice, point, ink in zip(('Dung', 'Sai'), detail['points'], detail['live_evidence']):
                cell(choice, point, ink)
            detected, aligned = answers[question][subquestion], detail['aligned']
            needs_review = detected in ('', 'X')
        else:
            if subquestion:
                raise ValueError('Phần III chọn cả câu.')
            detail = details[question]
            grid, ev = detail['live_grid'], detail['live_evidence']
            cell('sign', grid['sign'], ev['sign'])
            for c, (point, ink) in enumerate(zip(grid['commas'], ev['comma'])):
                cell(f'comma_{c}', point, ink)
            for c, x in enumerate(grid['columns']):
                for digit, y in enumerate(grid['rows']):
                    cell(f'digit_{c}_{digit}', (x, y), ev['digits'][c][digit])
            detected, aligned, needs_review = answers[question], grid['aligned'], ev['needs_review']
    except KeyError as exc:
        raise ValueError('Câu không có trên mẫu phiếu này.') from exc
    pad = max(18, radius + 5)
    x0, y0 = max(0, int(min(c['x'] for c in cells)) - pad), max(0, int(min(c['y'] for c in cells)) - pad)
    x1, y1 = min(gray.shape[1], int(max(c['x'] for c in cells)) + pad + 1), min(gray.shape[0], int(max(c['y'] for c in cells)) + pad + 1)
    for c in cells:
        c['x'], c['y'] = c['x'] - x0, c['y'] - y0
    crop = gray[y0:y1, x0:x1]
    if crop.size == 0:
        raise ValueError('Vùng câu bị nằm ngoài phiếu.')
    ok, png = cv2.imencode('.png', crop)
    if not ok:
        raise ValueError('Không tạo được ảnh câu.')
    suggested = {c['id']: {'marked':'filled', 'blank':'empty'}.get(e['state'], 'skip')
                 for c, e in zip(cells, evidence)}
    needs_review = bool(needs_review or not aligned or 'skip' in suggested.values() or detected == 'X')
    return dict(source_hash=source_hash, template_code=template_code, part=part, question=question,
        subquestion=subquestion, detected=str(detected), cells=cells, candidate_labels=suggested,
        needs_review=needs_review,
        geometry={'bbox':[x0,y0,x1,y1], 'width':x1-x0, 'height':y1-y0, 'radius':radius,
                  'aligned':bool(aligned), 'method':method, 'template_hash':template_hash,
                  'machine_labels':suggested, 'needs_review':needs_review}), png.tobytes()


@serialized_grading
def question_preview(raw, template_code, part, question, subquestion='', corners=None):
    gray, engine, method, template_hash = _prepare_photo(raw, template_code, corners)
    answers, details = _read_part(gray, engine, part)
    return _crop_question(gray, engine, part, question, subquestion, answers, details,
                          hashlib.sha256(raw).hexdigest(), template_code, method, template_hash)


@serialized_grading
def sheet_preview(raw, template_code, corners=None):
    """One decode/warp and one read per part; suggestions always require a human."""
    gray, engine, method, template_hash = _prepare_photo(raw, template_code, corners)
    source_hash, crops = hashlib.sha256(raw).hexdigest(), []
    for part in (1, 2, 3):
        answers, details = _read_part(gray, engine, part)
        for question in sorted(answers):
            for sub in ('abcd' if part == 2 else ('',)):
                crops.append(_crop_question(gray, engine, part, question, sub, answers, details,
                                           source_hash, template_code, method, template_hash))
    return crops


def validate_labels(cells, labels):
    if not isinstance(labels, dict) or set(labels) != {c['id'] for c in cells}:
        raise ValueError('Hãy xác nhận nhãn cho tất cả vòng tròn của câu đã chọn.')
    if any(value not in ('filled', 'empty', 'skip') for value in labels.values()):
        raise ValueError('Nhãn không hợp lệ.')


def labelled_answer(part, labels):
    """Summarize human marks; never use the exam answer key or model prediction."""
    if 'skip' in labels.values():
        return '?'
    marked = [k for k, value in labels.items() if value == 'filled']
    if part in (1, 2):
        return marked[0] if len(marked) == 1 else 'X' if marked else ''
    digits = {}
    for key in marked:
        if key.startswith('digit_'):
            _, col, digit = key.split('_')
            if int(col) in digits:
                return 'X'
            digits[int(col)] = digit
    commas = [int(k.split('_')[1]) for k in marked if k.startswith('comma_')]
    if len(commas) > 1 or (not digits and marked):
        return 'X'
    comma = commas[0] if commas else -1
    if comma >= 0 and not (any(c < comma for c in digits) and any(c >= comma for c in digits)):
        return 'X'
    occupied = sorted(set(digits) | set(commas))
    if occupied and occupied != list(range(occupied[0], occupied[-1] + 1)):
        return 'X'
    answer = ''.join(('.' if c == comma else '') + digits.get(c, '') for c in occupied)
    return ('-' if 'sign' in marked else '') + answer


def write_dataset(output, queryset):
    """Stream a versioned ZIP; source hash keeps a photograph in one split."""
    from django.core.files.storage import default_storage
    manifest, exported_sources = [], set()
    with zipfile.ZipFile(output, 'w', zipfile.ZIP_DEFLATED) as archive:
        for sample in queryset.filter(status='approved').order_by('id').iterator():
            validate_labels(sample.cells, sample.labels)
            if sample.geometry.get('aligned') is not True:
                raise ValueError(f'Mẫu #{sample.pk} chưa khớp lưới; không xuất nhãn sai vị trí.')
            with sample.image.open('rb') as file:
                raw = file.read()
            gray = cv2.imdecode(np.frombuffer(raw, np.uint8), cv2.IMREAD_GRAYSCALE)
            if gray is None:
                raise ValueError(f'Ảnh mẫu #{sample.pk} không đọc được.')
            case = f'questions/{sample.pk}.png'
            archive.writestr(case, raw)
            geometry = dict(sample.geometry)
            original = geometry.pop('source_image', None)
            source_file = None
            if original:
                source_file = f'sources/{sample.source_hash}{Path(original).suffix}'
                if source_file not in exported_sources:
                    with default_storage.open(original, 'rb') as source:
                        archive.writestr(source_file, source.read())
                    exported_sources.add(source_file)
            radius = int(sample.geometry['radius'])
            bubble_files = []
            for cell in sample.cells:
                label = sample.labels[cell['id']]
                if label == 'skip':
                    continue
                x, y = int(round(cell['x'])), int(round(cell['y']))
                patch = gray[max(0,y-radius):y+radius+1, max(0,x-radius):x+radius+1]
                if patch.size == 0:
                    raise ValueError(f'Vòng tròn mẫu #{sample.pk} bị nằm ngoài ảnh.')
                _, png = cv2.imencode('.png', cv2.resize(patch, (32,32), interpolation=cv2.INTER_AREA))
                name = f'{label}/{sample.pk}_{cell["id"]}.png'
                archive.writestr(name, png.tobytes())
                bubble_files.append({'file': name, 'cell': cell['id'], 'label': label})
            manifest.append({'id': sample.pk, 'file': case, 'group_id': sample.source_hash,
                'split': 'validation' if int(sample.source_hash[:8],16) % 5 == 0 else 'train',
                'part': sample.part, 'question': sample.question, 'subquestion': sample.subquestion,
                'template_code': sample.template_code, 'detected': sample.detected,
                'answer': sample.answer, 'labels': sample.labels, 'cells': sample.cells,
                'geometry': geometry, 'source_file': source_file,
                'label_origin': 'human_confirmed', 'bubbles': bubble_files})
        archive.writestr('manifest.json', json.dumps({'schema_version': 2, 'samples': manifest},
                                                  ensure_ascii=False, indent=2))
        archive.writestr('README.txt', 'Human-reviewed crops only. No model weights are changed.\n'
                          'sources/ contains private original photos; do not publish student identifiers.\n'
                          'Use manifest split/group_id; never split bubbles from one photo across train/validation.\n')
    return len(manifest)
