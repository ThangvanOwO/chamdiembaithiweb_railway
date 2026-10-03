"""Reviewed CNN assistance for uncertain raw ink, never for identifiers.

Keep definite marks, blank cells, invalid crops and unaligned grids intact.
Inference uses exactly the 27px raw crop -> 32px resize used by the export.
"""
from dataclasses import replace
from functools import lru_cache
import hashlib
import json
import logging
import os
from pathlib import Path

import cv2
import numpy as np

logger = logging.getLogger(__name__)
MODEL_DIR = Path(__file__).resolve().parent / 'reviewed_models'


def enabled():
    return os.environ.get('LIVE_REVIEWED_CNN', '1').strip() == '1'


@lru_cache(maxsize=1)
def metadata():
    try:
        info = json.loads((MODEL_DIR / 'manifest.json').read_text(encoding='utf-8'))
        return info if isinstance(info, dict) else {}
    except (OSError, ValueError):
        return {}


def supports_geometry(radius, width, height, centers):
    info = metadata()
    signature = hashlib.sha256(json.dumps(centers, separators=(',', ':')).encode()).hexdigest()
    return (enabled() and radius == 13 and [width, height] == info.get('warp')
            and signature == info.get('geometry_centres_sha256'))


@lru_cache(maxsize=1)
def session():
    try:
        info = metadata()
        name = info['file']
        if Path(name).name != name:
            raise ValueError('Invalid packaged model path')
        path = MODEL_DIR / name
        if hashlib.sha256(path.read_bytes()).hexdigest() != info['sha256']:
            raise ValueError('Reviewed model checksum mismatch')
        import onnxruntime as ort
        options = ort.SessionOptions()
        options.intra_op_num_threads = options.inter_op_num_threads = 1
        model = ort.InferenceSession(str(path), sess_options=options, providers=['CPUExecutionProvider'])
        if model.get_inputs()[0].shape[1:] != [1, 32, 32]:
            raise ValueError('Unexpected reviewed model input')
        logger.info('Loaded reviewed bubble model %s', info['version'])
        return model
    except Exception:
        logger.exception('Reviewed CNN unavailable; preserving raw ink evidence')
        return None


def crop_for_model(gray, point, radius=13):
    """Same rounding, inclusive edge and interpolation as write_dataset()."""
    x, y = (int(round(v)) for v in point)
    h, w = gray.shape
    if x-radius < 0 or y-radius < 0 or x+radius >= w or y+radius >= h:
        return None
    patch = gray[y-radius:y+radius+1, x-radius:x+radius+1]
    return cv2.resize(patch, (32, 32), interpolation=cv2.INTER_AREA)


def refine_evidence(gray, points, evidence, radius, aligned, diagnostics=None):
    if not enabled() or not aligned or radius != 13 or gray.ndim != 2 or len(points) != len(evidence):
        return evidence
    indices = [i for i, e in enumerate(evidence) if e.state == 'uncertain']
    if not indices:
        return evidence
    patches = [crop_for_model(gray, points[i], radius) for i in indices]
    if any(patch is None for patch in patches):
        return evidence
    model = session()
    if model is None:
        return evidence
    try:
        inputs = np.asarray(patches, dtype=np.float32)[:, None] / 255.0
        logits = model.run(None, {'input': inputs})[0]
        if logits.shape != (len(indices), 2) or not np.isfinite(logits).all():
            raise ValueError('Invalid reviewed model output')
        logits = logits - logits.max(axis=1, keepdims=True)
        exp = np.exp(logits)
        probabilities = exp[:, 1] / exp.sum(axis=1)
    except Exception:
        logger.exception('Reviewed CNN inference failed; preserving raw ink evidence')
        return evidence
    result = list(evidence)
    changed = 0
    for index, probability in zip(indices, probabilities):
        e = evidence[index]
        state = e.state
        # Keep the existing coverage/spatial support requirement. CNN can
        # confirm a broad faint mark, but cannot invent ink on blank paper.
        if probability >= .5 and e.contrast >= .07 and e.coverage >= .60 and e.dark_quarters >= 3:
            state = 'marked'
        elif (probability < .5 and e.coverage < .20) or (probability < .1 and e.coverage < .60):
            state = 'blank'
        if state != e.state:
            result[index] = replace(e, state=state)
            changed += 1
    if diagnostics is not None:
        diagnostics['inferred'] = diagnostics.get('inferred', 0) + len(indices)
        diagnostics['resolved'] = diagnostics.get('resolved', 0) + changed
    return result
