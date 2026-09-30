"""Test Method C hybrid results across sample images."""
import sys, os
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
ENGINE_DIR = REPO_ROOT / 'grading' / 'engine'
sys.path.insert(0, str(ENGINE_DIR))
import hi

hi.load_template(str(ENGINE_DIR / 'templates' / 'template_default.json'))

rel_images = [
    'anh/1.jpg',
    'anh/2.jpg',
    'anh/3.jpg',
    'anh/1111.jpg',
]

print(f"{'Image':<40} {'Method':<25} {'P1':>4} {'SBD':<8} {'MD':<5}")
print("-" * 90)

for rel in rel_images:
    img = str(REPO_ROOT / rel)
    if not os.path.exists(img):
        continue
    r = hi.process_sheet(img, debug=False)
    p1 = r.get('part1', {})
    n = sum(1 for v in p1.values() if v and v != 'X')
    m = r.get('detect_method', '?')
    sbd = r.get('sbd', '?')
    md = r.get('made', '?')
    print(f"{rel:<40} {m:<25} {n:>2}/40 {sbd:<8} {md:<5}")
