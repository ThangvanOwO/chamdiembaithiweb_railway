"""Test engine on all images in anh/ folder."""
import sys
import os
import glob
import time
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
ENGINE_DIR = REPO_ROOT / 'grading' / 'engine'
sys.path.insert(0, str(ENGINE_DIR))
import hi as engine

IMAGE_DIR = str(REPO_ROOT / 'anh')
images = sorted([f for f in glob.glob(os.path.join(IMAGE_DIR, '*.jpg')) if not any(s in f for s in ['_result', '_thresh', '_name', '_overlay', '_calibration', '_gray', '_cleaned', '_detect'])])

print(f"Found {len(images)} images in {IMAGE_DIR}")
for img in images:
    print(f"\nProcessing: {os.path.basename(img)}")
    t0 = time.time()
    try:
        res = engine.process_sheet(img, debug=False)
        print(f"Done in {time.time()-t0:.2f}s | Method: {res.get('detect_method')} | SBD: {res.get('sbd')} | MĐ: {res.get('made')}")
    except Exception as e:
        print(f"ERROR in {time.time()-t0:.2f}s: {e}")
