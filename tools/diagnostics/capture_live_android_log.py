"""Read only GradeFlow LiveCamera diagnostics; never clear device logcat.

Run after opening Live Camera on the connected phone. Does not launch the app,
take pictures, upload grades, collect other apps' messages, or change settings.
"""
import argparse
from datetime import datetime
import json
from pathlib import Path
import subprocess

parser = argparse.ArgumentParser()
parser.add_argument('--serial', required=True)
args = parser.parse_args()
root = Path(__file__).resolve().parents[2]
adb = ['adb', '-s', args.serial]
package = 'com.gradeflow.gradeflow_app'
pid_result = subprocess.run(adb + ['shell', 'pidof', package],
                            capture_output=True, text=True, timeout=15)
pids = pid_result.stdout.strip().split()
lines = []
for pid in pids:
    if not pid.isdigit():
        raise ValueError('Invalid process id')
    result = subprocess.run(adb + ['logcat', '-d', '-v', 'threadtime',
                                  '--pid=' + pid, '-t', '10000'],
                            capture_output=True, text=True, errors='replace', timeout=30)
    if result.returncode:
        raise RuntimeError(result.stderr)
    lines.extend(line for line in result.stdout.splitlines() if '[LiveCamera' in line)
out = root / 'tests' / 'ketqua' / 'live_v3_device'
out.mkdir(parents=True, exist_ok=True)
stamp = datetime.now().strftime('%Y%m%d_%H%M%S_%f')
report = {'collected_at': stamp, 'serial': args.serial, 'package': package,
          'pids': pids, 'status': 'messages_found' if lines else 'no_live_messages',
          'note': 'Existing filtered logcat, not evidence of a completed test when empty',
          'lines': lines}
target = out / (stamp + '.json')
target.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding='utf-8')
print(json.dumps({'report': str(target), 'pids': pids, 'message_count': len(lines)},
                 ensure_ascii=False))
for line in lines[-60:]:
    print(line.encode('ascii', errors='backslashreplace').decode('ascii'))
