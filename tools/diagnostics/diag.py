"""Direct test of _calibrate_part3_dynamic"""
import sys, os
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
ENGINE_DIR = REPO_ROOT / 'grading' / 'engine'
sys.path.insert(0, str(ENGINE_DIR))

import hi, cv2, numpy as np
from PIL import Image, ExifTags

hi.load_template(str(ENGINE_DIR / 'templates' / 'template_default.json'))

img_path = str(REPO_ROOT / 'anh' / '1111.jpg')
img = cv2.imread(img_path)
try:
    pil_img = Image.open(img_path)
    exif = pil_img._getexif()
    if exif:
        ok = next((k for k, v in ExifTags.TAGS.items() if v == 'Orientation'), None)
        if ok and ok in exif:
            o = exif[ok]
            if o == 3: img = cv2.rotate(img, cv2.ROTATE_180)
            elif o == 6: img = cv2.rotate(img, cv2.ROTATE_90_CLOCKWISE)
            elif o == 8: img = cv2.rotate(img, cv2.ROTATE_90_COUNTERCLOCKWISE)
except Exception: pass

result = hi.auto_deskew_and_crop(img, debug=False)
warped = result["warped"]
print(f"Warped: {warped.shape}")

# Direct call
print("=== Direct _calibrate_part3_dynamic ===")
try:
    cal = hi._calibrate_part3_dynamic(warped)
    print(f"Result: {cal}")
except Exception as e:
    import traceback
    traceback.print_exc()

print("=" * 60)
print("PART I — Fill ratios (first 10 questions)")
print("=" * 60)
gray = cv2.cvtColor(warped, cv2.COLOR_BGR2GRAY) if len(warped.shape) == 3 else warped.copy()
for col in hi.PART1_COLS:
    for row in range(min(col.get("num_rows", hi.PART1_NUM_ROWS), 5)):
        q = col["q_start"] + row
        ratios = {}
        for ci, ch in enumerate(hi.PART1_CHOICES):
            cx = col["start_x"] + ci * col["step_x"]
            cy = col["start_y"] + row * col["step_y"]
            _, r = hi.is_bubble_filled(gray, cx, cy)
            ratios[ch] = round(r, 3)
        filled = hi._detect_filled_choices(ratios)
        print(f"  Q{q:2d}: {ratios}  → {filled if filled else '(empty)'}")
    break  # Just first column

print()
print("=" * 60)
print("PART III — Fill ratios")
print("=" * 60)
p3_offset = 0
for blk in hi.PART3_BLOCKS:
    q = blk["q"]
    cols_x = blk["cols_x"]
    # Sign
    _, r_sign = hi.is_bubble_filled(gray, blk["sign_x"], hi.PART3_SIGN_Y + p3_offset)
    print(f"\n  Câu {q}: sign_ratio={r_sign:.3f}")
    # Digits
    for ci, cx in enumerate(cols_x):
        col_ratios = {}
        for d in range(10):
            cy = hi.PART3_DIGIT_START_Y + d * hi.PART3_DIGIT_STEP_Y + p3_offset
            _, r = hi.is_bubble_filled(gray, cx, cy)
            col_ratios[d] = round(r, 3)
        sorted_items = sorted(col_ratios.items(), key=lambda x: x[1], reverse=True)
        top_d, top_r = sorted_items[0]
        second_r = sorted_items[1][1]
        gap = top_r - second_r
        print(f"    Col{ci}: top={top_d}({top_r:.3f}) 2nd={second_r:.3f} gap={gap:.3f}  "
              f"all={dict(sorted(col_ratios.items()))}")
