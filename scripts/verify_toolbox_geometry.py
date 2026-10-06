"""Compare the unchanged OMR corner detector on the source and rendered printable PDF."""
import json
import sys
from pathlib import Path
import cv2
import numpy as np

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'grading/engine'))
import hi


def normalized_markers(path):
    image = cv2.imread(str(path))
    points = hi._find_corner_markers(image)
    if points is None:
        raise RuntimeError(f'OMR could not find all four markers: {path.name}')
    return points / np.array([image.shape[1], image.shape[0]])


def main():
    output = ROOT / 'artifacts/toolbox_20261006'
    source = next((ROOT / 'cacmaubaithi/40-08-06---QM-2025---A4').glob('*.jpg'))
    original = normalized_markers(source)
    printed = normalized_markers(output / 'mau_40_08_06.png')
    delta = float(np.max(np.abs(original - printed)))
    result = {'source_markers': original.tolist(), 'pdf_markers': printed.tolist(), 'max_normalized_delta': delta,
              'tolerance': 0.005, 'passed': delta < 0.005,
              'method': 'same OMR marker detector on source JPEG and rasterized A4 PDF; not a physical print/camera test'}
    (output / 'template_geometry.json').write_text(json.dumps(result, indent=2), encoding='utf-8')
    print(json.dumps(result, indent=2))
    if not result['passed']:
        raise RuntimeError('PDF marker geometry changed')


if __name__ == '__main__':
    main()
