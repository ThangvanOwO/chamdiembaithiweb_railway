"""Test all images in anh/ and print summary."""
import sys, os
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
ENGINE_DIR = REPO_ROOT / 'grading' / 'engine'
sys.path.insert(0, str(ENGINE_DIR))
import hi as engine

IMG_DIR = REPO_ROOT / 'anh'
images = [str(IMG_DIR / f"{i}.jpg") for i in range(1, 8) if (IMG_DIR / f"{i}.jpg").exists()]
results = []

for img in images:
    print(f"\n{'='*60}")
    print(f"  {img}")
    print(f"{'='*60}")
    try:
        res = engine.process_sheet(img, debug=False)
        if res:
            p1 = res.get('part1', {})
            p1_filled = sum(1 for v in p1.values() if v in "ABCD")
            print(f"  OK: SBD={res.get('sbd')} MĐ={res.get('made')} P1_filled={p1_filled}/40 method={res.get('detect_method')}")
        else:
            print("  FAILED: process_sheet returned None")
    except Exception as e:
        print(f"  ERROR: {e}")
