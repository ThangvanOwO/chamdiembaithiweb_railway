"""Extract bubble crops from BEST images and ADD to existing dataset (no clear)."""
import sys, os, io
from pathlib import Path

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')
REPO_ROOT = Path(__file__).resolve().parents[2]
ENGINE_DIR = REPO_ROOT / 'grading' / 'engine'
sys.path.insert(0, str(ENGINE_DIR))
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'chamdiemtudong.settings')

from extract_bubbles import load_and_warp, extract_from_image, DATASET_DIR

# Best images (corner_markers, highest detection rates)
BEST_IMAGES = [str(REPO_ROOT / 'anh' / f) for f in ['1.jpg', '2.jpg', '3.jpg', '4.jpg']]

# Count existing
for sub in ['filled', 'empty', 'unknow']:
    d = os.path.join(DATASET_DIR, sub)
    if os.path.exists(d):
        n = len([f for f in os.listdir(d) if f.endswith('.png')])
        print(f'  Existing {sub}: {n}')

# DO NOT clear old dataset - just append
total_f, total_e, total_u = 0, 0, 0
for i, path in enumerate(BEST_IMAGES, 1):
    print(f'\n[{i}/{len(BEST_IMAGES)}] {path}')
    _, gray = load_and_warp(path)
    if gray is None:
        print('  FAILED to load/warp')
        continue
    name = os.path.splitext(os.path.basename(path))[0]
    # Add suffix to avoid overwriting existing crops from same image
    name = f'{name}_v2'
    f, e, u = extract_from_image(gray, name)
    total_f += f
    total_e += e
    total_u += u
    print(f'  filled={f}, empty={e}, unknow={u}')

print(f'\nNEW extracted: filled={total_f}, empty={total_e}, unknow={total_u}')

# Count total
for sub in ['filled', 'empty', 'unknow']:
    d = os.path.join(DATASET_DIR, sub)
    if os.path.exists(d):
        n = len([f for f in os.listdir(d) if f.endswith('.png')])
        print(f'  Total {sub}: {n}')
