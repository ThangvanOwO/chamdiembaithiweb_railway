"""Compare fill ratios: Raw vs CLAHE for blank + filled sheets"""
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

def make_clahe_gray(warped):
    g = cv2.cvtColor(hi.erase_printed_text(warped), cv2.COLOR_BGR2GRAY)
    clahe = cv2.createCLAHE(clipLimit=2.0, tileGridSize=(16,16))
    return cv2.GaussianBlur(clahe.apply(g), (5,5), 0)

for rel_path, label in [('anh/1.jpg', 'BLANK/TEST'), ('anh/1111.jpg', 'FILLED')]:
    w = load_warped(rel_path)
    if w is None:
        continue
    g_clahe = make_clahe_gray(w)
    print(f"\n{'='*70}")
    print(f"  {label}: {rel_path} (CLAHE)")
    print(f"  std={np.std(g_clahe):.0f}, mean={np.mean(g_clahe):.0f}")
    print(f"{'='*70}")

    col = hi.PART1_COLS[0]
    for row in range(10):
        q = col['q_start'] + row
        vals = {}
        for ci, ch in enumerate(hi.PART1_CHOICES):
            cx = col['start_x'] + ci * col['step_x']
            cy = col['start_y'] + row * col['step_y']
            _, ratio = hi.is_bubble_filled(g_clahe, cx, cy)
            vals[ch] = ratio
        sv = sorted(vals.values())
        median = (sv[1] + sv[2]) / 2.0
        top_ch = max(vals, key=vals.get)
        top_r = vals[top_ch]
        second_r = sorted(vals.values(), reverse=True)[1]
        rise = top_r - median
        gap = top_r - second_r
        pct = rise/median*100 if median > 0 else 0
        print(f"  Q{q:2d}: max={top_r:.3f}({top_ch}) med={median:.3f} rise={rise:.3f}({pct:.0f}%) gap={gap:.3f}  A={vals['A']:.3f} B={vals['B']:.3f} C={vals['C']:.3f} D={vals['D']:.3f}")
