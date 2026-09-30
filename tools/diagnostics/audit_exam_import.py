"""Replay exact camera-prepared JPEG/geometry through the import API, no DB saves."""
import json
import os
from pathlib import Path
import sys
from types import SimpleNamespace

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'chamdiemtudong.settings')
import django
django.setup()
from django.core.files.uploadedfile import SimpleUploadedFile
from rest_framework.test import APIRequestFactory, force_authenticate
from api.views import parse_image_api

fixture = ROOT / 'tests/fixtures/exam_import_v1.jpg'
fields = json.loads(fixture.with_suffix('.json').read_text(encoding='utf-8'))
request = APIRequestFactory().post('/api/v1/parse-image/', {
    **fields, 'file': SimpleUploadedFile('camera.jpg', fixture.read_bytes())}, format='multipart')
force_authenticate(request, user=SimpleNamespace(is_authenticated=True))
response = parse_image_api(request)
record = {'source': str(fixture), 'request_fields': fields,
          'status': response.status_code, 'response': response.data,
          'note': 'Offline API replay; no exam or submission was saved.'}
folder = ROOT / 'tests/ketqua/exam_import_v2'
folder.mkdir(parents=True, exist_ok=True)
(folder / 'audit.json').write_text(json.dumps(record, ensure_ascii=False, indent=2), encoding='utf-8')
assert response.status_code == 200, response.data
data = response.data['data']
variant = data['variants'][0]
assert data['detect_method'] == 'frontend_corners'
assert variant['code'] == '001'
assert variant['p3'] == {'1':'-0.2','2':'1599','3':'-0.8','4':'1.25','5':'22','6':'2100'}
print(json.dumps({'status': response.status_code, 'method': data['detect_method'],
                  'code': variant['code'], 'p1': variant['p1'], 'p2': variant['p2'],
                  'p3': variant['p3']}, ensure_ascii=True))
