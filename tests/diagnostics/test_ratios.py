"""So sánh fill ratio giữa các ảnh test."""
import sys, os
from pathlib import Path
import cv2, numpy as np
from PIL import Image, ExifTags

REPO_ROOT = Path(__file__).resolve().parents[2]
ENGINE_DIR = REPO_ROOT / 'grading' / 'engine'
sys.path.insert(0, str(ENGINE_DIR))

import hi
hi.load_template(str(ENGINE_DIR / 'templates' / 'template_default.json'))

def load_warped(rel_path):
    path = str(REPO_ROOT / rel_path) if not Path(rel_path).is_absolute() else rel_path
    if not os.path.exists(path):
        return None
    img = cv2.imread(path)
    try:
        pil = Image.open(path)
        exif = pil._getexif()
        if exif:
            ok = next((k for k,v in ExifTags.TAGS.items() if v=='Orientation'), None)
            if ok and ok in exif:
                o = exif[ok]
                if o==6: img = cv2.rotate(img, cv2.ROTATE_90_CLOCKWISE)
                elif o==3: img = cv2.rotate(img, cv2.ROTATE_180)
                elif o==8: img = cv2.rotate(img, cv2.ROTATE_90_COUNTERCLOCKWISE)
    except Exception: pass
    r = hi.auto_deskew_and_crop(img)
    return r['warped']

for name in ['anh/1111.jpg', 'anh/1.jpg']:
    w = load_warped(name)
    if w is None:
        continue
    g = cv2.GaussianBlur(cv2.cvtColor(w, cv2.COLOR_BGR2GRAY), (5,5), 0)
    std_val = float(np.std(g))
    mean_val = float(np.mean(g))
    print(f"\n{'='*60}")
    print(f"  {name}")
    print(f"  std={std_val:.0f}, mean={mean_val:.0f}")
    print(f"{'='*60}")

    # Part I Q1-10 fill ratios
    print("  Part I (Q1-10):")
    col = hi.PART1_COLS[0]
    for row in range(10):
        q = col['q_start'] + row
        vals = {}
        for ci, ch in enumerate(hi.PART1_CHOICES):
            cx = col['start_x'] + ci * col['step_x']
            cy = col['start_y'] + row * col['step_y']
            _, r = hi.is_bubble_filled(g, cx, cy)
            vals[ch] = r
        mx = max(vals.values())
        best = max(vals, key=vals.get)
        mark = " <<<" if mx > 0.18 else ""
        print(f"    Q{q:2d}: max={mx:.3f}({best})  A={vals['A']:.3f} B={vals['B']:.3f} C={vals['C']:.3f} D={vals['D']:.3f}{mark}")
