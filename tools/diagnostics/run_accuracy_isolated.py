"""Run the existing accuracy smoke suite on copies, never annotated source IO.

This historical suite reports detections, not labeled accuracy percentages.
"""
import argparse
import importlib.util
import json
from pathlib import Path
import shutil
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[2]


def main():
    parser = argparse.ArgumentParser(__doc__)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    output = args.output.resolve()
    if output.exists() or not output.is_relative_to(ROOT):
        parser.error('Use a new directory inside workspace')
    output.mkdir(parents=True)
    spec = importlib.util.spec_from_file_location('existing_accuracy', ROOT / 'tests/benchmarks/test_accuracy.py')
    suite = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(suite)
    copier = shutil.copy2
    def redirect(src, dst, *a, **kw):
        if Path(dst).parent.resolve() == (ROOT / 'tests/ketqua').resolve():
            dst = output / ('auto_' + Path(dst).name)
        return copier(src, dst, *a, **kw)
    excluded = ('_result', '_thresh', '_name', '_overlay', '_calibration', '_gray', '_cleaned', '_detect')
    rows = []
    for source in sorted((ROOT / 'anh').iterdir()):
        if source.suffix.lower() not in ('.jpg', '.jpeg', '.png') or any(word in source.name for word in excluded):
            continue
        local = output / source.name
        copier(source, local)
        with patch.object(shutil, 'copy2', redirect):
            row = suite.test_single_image(str(local))
        rows.append(row)
        (output / 'report.json').write_text(json.dumps(rows, indent=2, ensure_ascii=False), encoding='utf-8')
        print(json.dumps(row, ensure_ascii=True), flush=True)
    print(f'Completed {len(rows)} historical smoke cases', flush=True)
    if any(row['status'] == 'ERROR' for row in rows):
        raise SystemExit(1)


if __name__ == '__main__':
    main()
