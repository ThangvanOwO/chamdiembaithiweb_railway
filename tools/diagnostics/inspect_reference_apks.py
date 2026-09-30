"""Extract user-provided APKs and inspect native symbols without executing them."""
import hashlib
import json
from pathlib import Path
import re
import subprocess
import zipfile

ROOT = Path(__file__).resolve().parents[2]
OUT = ROOT / 'scratch' / 'apk_research_20260911'
NM = Path('C:/Users/Thang/AppData/Local/Android/sdk/ndk/28.2.13676358/toolchains/llvm/prebuilt/windows-x86_64/bin/llvm-nm.exe')
OUT.mkdir(parents=True, exist_ok=True)
report = []
for apk in sorted((ROOT / 'apk_thamkhao').rglob('*.apk')):
    digest = hashlib.sha256(apk.read_bytes()).hexdigest()
    dest = OUT / apk.parent.name / (apk.stem + '_' + digest[:12])
    with zipfile.ZipFile(apk) as archive:
        names = archive.namelist()
        for name in names:
            if not (dest / name).resolve().is_relative_to(dest.resolve()):
                raise ValueError('Unsafe archive path')
        if not dest.exists():
            dest.mkdir(parents=True)
            archive.extractall(dest)
    row = {'apk': str(apk.relative_to(ROOT)), 'sha256': digest,
           'extracted': str(dest), 'libraries': [n for n in names if n.endswith('.so')],
           'models': [n for n in names if n.endswith(('.tflite', '.onnx'))], 'native_evidence': {}}
    for name in names:
        if not name.endswith(('libnative_opencv.so', 'libffi_opencv_scanner.so')):
            continue
        symbols = subprocess.check_output([str(NM), '-D', '-C', str(dest / name)], text=True, errors='replace')
        evidence = [line for line in symbols.splitlines() if re.search(
            r'cv::|scan|detect|corner|process|warp|perspective|contour|threshold|Java_', line, re.I)]
        (dest / (Path(name).name + '.symbols.txt')).write_text(symbols, encoding='utf-8')
        row['native_evidence'][name] = evidence
    report.append(row)
    print(json.dumps({'apk': row['apk'], 'libraries': row['libraries'],
                      'models': row['models'], 'native_evidence': row['native_evidence']}, ensure_ascii=False))
(OUT / 'inventory.json').write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding='utf-8')
print('Report:', OUT / 'inventory.json')
