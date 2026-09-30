"""Scoped, hash-guarded backup/rollback. No git reset, DB or APK changes.

snapshot before editing; seal after testing; verify by default. Restore refuses
later edits and moves newly added files into the checkpoint, never deletes them.
"""
import argparse
import hashlib
import json
from pathlib import Path
import shutil

ROOT = Path(__file__).resolve().parents[2]
CHECKPOINT = ROOT / 'scratch/restore_points/before_live_latency_20260914'
FILES = ('api/views.py', 'grading/grader.py', 'grading/engine/hi.py',
         'chamdiemtudong/settings.py', 'grading/live_latency.py',
         'grading/engine/live_background.py')


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest() if path.is_file() else None


def main():
    parser = argparse.ArgumentParser(__doc__)
    parser.add_argument('action', choices=('snapshot', 'seal', 'verify', 'restore'), default='verify', nargs='?')
    args = parser.parse_args()
    manifest = CHECKPOINT / 'manifest.json'
    if args.action == 'snapshot':
        CHECKPOINT.mkdir(parents=True, exist_ok=False)
        rows = []
        for name in FILES:
            source = ROOT / name
            saved = CHECKPOINT / 'before' / name
            if source.exists():
                saved.parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(source, saved)
            rows.append({'path': name, 'before': digest(source)})
    else:
        rows = json.loads(manifest.read_text(encoding='utf-8'))
        for row in rows:
            if row['path'] not in FILES:
                raise RuntimeError('Unexpected target in manifest')
            if digest(CHECKPOINT / 'before' / row['path']) != row['before']:
                raise RuntimeError('Backup hash mismatch: ' + row['path'])
        if args.action == 'seal':
            if any('after' in row for row in rows):
                raise RuntimeError('Already sealed; will not overwrite expected hashes')
            for row in rows:
                row['after'] = digest(ROOT / row['path'])
        else:
            for row in rows:
                if 'after' not in row or digest(ROOT / row['path']) != row['after']:
                    raise RuntimeError('Unsealed or later edits; refusing rollback: ' + row['path'])
            if args.action == 'restore':
                # All targets checked before any mutation. Keep the replaced code.
                retired = CHECKPOINT / 'replaced'
                retired.mkdir(exist_ok=False)
                for row in rows:
                    target = ROOT / row['path']
                    if target.exists():
                        saved = retired / row['path']
                        saved.parent.mkdir(parents=True, exist_ok=True)
                        shutil.move(str(target), str(saved))
                    if row['before'] is not None:
                        shutil.copy2(CHECKPOINT / 'before' / row['path'], target)
            print(f'{args.action}: {len(rows)} targets verified; {CHECKPOINT}')
            return
    manifest.write_text(json.dumps(rows, indent=2), encoding='utf-8')
    print(f'{args.action}: {CHECKPOINT}')


if __name__ == '__main__':
    main()
