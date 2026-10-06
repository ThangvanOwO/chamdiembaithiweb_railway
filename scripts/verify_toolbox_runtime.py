"""Read-only deployment checks. No credentials, names, or response bodies are logged."""
import hashlib
import json
import os
import sqlite3
import sys
import urllib.error
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'chamdiemtudong.settings')
import django
django.setup()

from django.contrib.auth import get_user_model
from rest_framework.test import APIClient
from grading.models import Exam


def main():
    output = ROOT / 'artifacts/toolbox_20261006'
    output.mkdir(parents=True, exist_ok=True)
    audit = {'http': {}, 'authenticated': {}, 'protected_files_unchanged': {}, 'data_counts': {}}
    for url in ('http://127.0.0.1:8000/ads.txt', 'http://127.0.0.1:8000/api/v1/classrooms/',
                'https://gradeflow.io.vn/api/v1/classrooms/'):
        try:
            response = urllib.request.urlopen(url, timeout=15)
            audit['http'][url] = response.status
        except urllib.error.HTTPError as exc:
            audit['http'][url] = exc.code
        except Exception as exc:
            audit['http'][url] = type(exc).__name__
    teacher = get_user_model().objects.filter(is_active=True).first()
    if teacher:
        client = APIClient()
        client.force_authenticate(teacher)
        paths = ['/api/v1/classrooms/', '/api/v1/submissions/?limit=1&page=1', '/api/v1/review-queue/',
                 '/api/v1/templates/40-08-06/pdf/', '/api/v1/support/']
        exam = Exam.objects.filter(teacher=teacher).first()
        if exam:
            paths += [f'/api/v1/exams/{exam.pk}/report/', f'/api/v1/exams/{exam.pk}/export/xlsx/',
                      f'/api/v1/exams/{exam.pk}/export/pdf/']
        for path in paths:
            response = client.get(path)
            audit['authenticated'][path] = response.status_code
            if response.status_code != 200:
                raise RuntimeError(f'Read-only API check failed: {path} ({response.status_code})')
    snapshot = ROOT / 'scratch/toolbox_before_20261006'
    for path in ('gradeflow_app/lib/screens/live_camera_screen.dart', 'gradeflow_app/lib/services/live_still_detector.dart',
                 'grading/engine/hi.py', 'grading/models.py', 'accounts/models.py'):
        if (snapshot / path).exists():
            sha = lambda p: hashlib.sha256(p.read_bytes()).hexdigest()
            audit['protected_files_unchanged'][path] = sha(ROOT / path) == sha(snapshot / path)
    backup = snapshot / 'db.sqlite3'
    if backup.exists() and (ROOT / 'db.sqlite3').exists():
        for db_key, path in [('before', backup), ('after', ROOT / 'db.sqlite3')]:
            db = sqlite3.connect(f'file:{path.as_posix()}?mode=ro', uri=True)
            audit['data_counts'][db_key] = {table: db.execute(f'SELECT COUNT(*) FROM {table}').fetchone()[0]
                                          for table in ('auth_user', 'grading_exam', 'grading_submission', 'accounts_creditwallet')}
            db.close()
    (output / 'runtime_audit.json').write_text(json.dumps(audit, indent=2, ensure_ascii=False), encoding='utf-8')
    print(json.dumps(audit, indent=2, ensure_ascii=False))


if __name__ == '__main__':
    main()
