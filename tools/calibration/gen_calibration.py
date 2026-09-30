import sys, os, io
from pathlib import Path

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')
REPO_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO_ROOT))
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'chamdiemtudong.settings')
from grading.engine import hi as engine

IMG_DIR = str(REPO_ROOT / 'anh')
originals = sorted([f for f in os.listdir(IMG_DIR) if f.lower().endswith('.jpg') and '_' not in f])

for img_name in originals:
    img_path = os.path.join(IMG_DIR, img_name)
    print(f'Processing {img_name}...')
    try:
        engine.process_sheet(img_path, correct_answers=None, debug=True)
        print(f'  OK - calibration saved')
    except Exception as e:
        print(f'  ERROR: {e}')
print('Done!')
