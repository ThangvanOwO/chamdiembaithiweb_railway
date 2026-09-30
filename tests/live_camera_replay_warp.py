"""Render the existing server warp using corners produced by the Dart replay.

Geometry diagnostic only: source is already annotated, not grading ground truth.
No backend files or original evidence are modified.
"""
import ast
import json
from pathlib import Path

import cv2
import numpy as np

root = Path(__file__).resolve().parents[1]
out = root / 'tests' / 'ketqua' / 'live_v2_replay'
meta = json.loads((out / 'capture.json').read_text(encoding='utf-8'))
source = root / 'grading' / 'engine' / 'hi.py'
tree = ast.parse(source.read_text(encoding='utf-8-sig'))
# Execute only the exact pure warp helper to avoid importing engine training,
# model-loading and grading/output side effects.
helper = next(node for node in tree.body
              if isinstance(node, ast.FunctionDef) and node.name == '_warp_to_rect')
constants = [node for node in tree.body if isinstance(node, ast.Assign)
             and any(isinstance(t, ast.Name) and t.id in ('WARP_WIDTH', 'WARP_HEIGHT')
                     for t in node.targets)]
namespace = {'cv2': cv2, 'np': np}
exec(compile(ast.Module(body=constants + [helper], type_ignores=[]),
             str(source), 'exec'), namespace)
image = cv2.imread(str(out / 'capture.jpg'))
assert image is not None
points = np.float32(meta['corners'])
warped = namespace['_warp_to_rect'](image, points)
target = out / 'verified_corners_warp.jpg'
assert cv2.imwrite(str(target), warped)
print(json.dumps({'output': str(target), 'corners': meta['corners'],
                  'size': list(warped.shape[:2][::-1]),
                  'scope': 'geometry only; not an answer-accuracy evaluation'}, indent=2))
