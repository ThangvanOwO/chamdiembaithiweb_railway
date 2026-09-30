"""Test all images in anh/ folder and print detailed SBD, MD, P1, P2, P3 results."""
import sys
import os
import json
import io
from pathlib import Path

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')
sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8', errors='replace')

REPO_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO_ROOT))

from grading.engine import hi as engine

IMG_DIR = str(REPO_ROOT / 'anh')

originals = sorted([
    f for f in os.listdir(IMG_DIR)
    if f.lower().endswith('.jpg') and not any(s in f for s in ['_result', '_thresh', '_name', '_overlay', '_calibration', '_gray', '_cleaned', '_detect'])
])

print(f"Found {len(originals)} images in {IMG_DIR}: {originals}\n")

for img_name in originals:
    img_path = os.path.join(IMG_DIR, img_name)
    print("=" * 80)
    print(f"  FILE: {img_name}")
    print("=" * 80)
    try:
        res = engine.process_sheet(img_path, debug=False)
        if res is None:
            print("  [LỖI] engine.process_sheet trả về None")
            continue

        p1 = res.get('answers', {}).get('part1', res.get('part1', {}))
        p2 = res.get('answers', {}).get('part2', res.get('part2', {}))
        p3 = res.get('answers', {}).get('part3', res.get('part3', {}))

        print(f"\n  SBD       : {res.get('sbd', '')}")
        print(f"  Mã đề     : {res.get('made', '')}")
        print(f"  Method    : {res.get('detect_method', '')}")
        offsets = res.get('offsets', {})
        print(f"  Offsets   : P1={offsets.get('part1',0):+d}  P2={offsets.get('part2',0):+d}  P3={offsets.get('part3',0):+d}")

        print("\n  === PHẦN I (40 câu ABCD) ===")
        p1_strs = [f"Q{q:2d}={ans}" for q, ans in sorted(p1.items())]
        for i in range(0, len(p1_strs), 10):
            print("    " + " | ".join(p1_strs[i:i+10]))

        print("\n  === PHẦN II (8 câu Đ/S) ===")
        for q, subs in sorted(p2.items()):
            sub_str = " | ".join([f"{k}={'Đ' if v=='Dung' else ('S' if v=='Sai' else '?')}" for k, v in sorted(subs.items())])
            print(f"    Câu {q}: {sub_str}")

        print("\n  === PHẦN III (6 câu điền số) ===")
        for q, ans in sorted(p3.items()):
            print(f"    Câu {q}: '{ans}'")

        p3_det = res.get('part3_details', {})
        if p3_det:
            print("\n  --- Part 3 chi tiết (picked) ---")
            for q, d in sorted(p3_det.items()):
                pk = d.get('picked', {})
                print(f"    Câu {q}: sign={pk.get('sign')}, comma_col={pk.get('comma_col')}, digits={pk.get('digits')}")

    except Exception as e:
        import traceback
        print(f"  [LỖI EXCEPTION]: {e}")
        traceback.print_exc()

print(f"\n{'='*80}")
print(f"  DONE - {len(originals)} images tested")
print(f"{'='*80}\n")
