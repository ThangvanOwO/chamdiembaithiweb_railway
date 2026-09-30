"""Test OpenCV vs CNN solo on anh/1.jpg - detailed comparison log."""
import sys, os, io
from pathlib import Path

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')
REPO_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO_ROOT))
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'chamdiemtudong.settings')

from grading.engine import hi as engine

img_path = str(REPO_ROOT / 'anh' / '1.jpg')
if os.path.exists(img_path):
    print(f"Testing CNN vs CV on {img_path}...")
    res = engine.process_sheet(img_path, debug=False)
    print(f"Result SBD: {res.get('sbd')}, Mã đề: {res.get('made')}")
else:
    print(f"Image {img_path} not found.")
