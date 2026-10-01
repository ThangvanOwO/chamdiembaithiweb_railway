"""Exercise the actual bulk API/export in a disposable SQLite DB and media root.

All marks are a generated fixture, never labels inferred from a student's photo.
Run from the project root: python tools/training/export_training_demo.py
"""
import json
import os
import sys
import tempfile
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'chamdiemtudong.settings')


def main():
    import django
    django.setup()
    import cv2
    import numpy as np
    from django.conf import settings
    from django.contrib.auth.models import User
    from django.core.management import call_command
    from django.core.files.uploadedfile import SimpleUploadedFile
    from django.db import connection
    from rest_framework.test import APIClient
    from grading.grader import engine
    from grading.models import TrainingCorrection
    from grading.training_data import write_dataset

    output = ROOT / 'Traing' / 'demo_sheet_20261001'
    output.mkdir(parents=True, exist_ok=True)
    # Redirect before any ORM operation. Real DB and media are never touched.
    with tempfile.TemporaryDirectory() as isolated:
        if connection.vendor != 'sqlite':
            raise RuntimeError('Run this demo locally with SQLite; never use the VPS database.')
        connection.close()
        connection.settings_dict['NAME'] = str(Path(isolated) / 'demo.sqlite3')
        settings.MEDIA_ROOT = str(Path(isolated) / 'media')
        settings.SECURE_SSL_REDIRECT = False
        assert Path(connection.settings_dict['NAME']).parent == Path(isolated)
        call_command('migrate', verbosity=0)
        admin = User.objects.create_user('synthetic-demo-admin', is_superuser=True, is_staff=True)
        client = APIClient()
        client.force_authenticate(admin)
        engine.load_template(str(ROOT / 'grading/engine/templates/template_default.json'))
        photo = np.full((1920, 1400, 3), 245, np.uint8)
        for x, y in engine.ALL_BUBBLE_CENTERS:
            cv2.circle(photo, (round(x), round(y)), engine.BUBBLE_RADIUS, (65, 65, 65), 2)
        truth = {}
        def fill(x, y):
            cv2.circle(photo, (round(x), round(y)), 9, (35, 35, 35), -1)
        for n, block in enumerate(engine.PART1_COLS):
            for row in range(10):
                q = n*10+row+1
                choice = (q-1) % len(engine.PART1_CHOICES)
                marked = engine.PART1_CHOICES[choice]
                truth[1, q, ''] = {c: 'filled' if c == marked else 'empty' for c in engine.PART1_CHOICES}
                fill(block['start_x'] + choice * block['step_x'], block['start_y'] + row * block['step_y'])
        for block in engine.PART2_BLOCKS:
            for row, sub in enumerate('abcd'):
                col = (block['q']+row) % 2
                if block['q'] == 6 and sub == 'c':
                    col = 0
                truth[2, block['q'], sub] = {'Dung': 'filled' if col == 0 else 'empty',
                                            'Sai': 'filled' if col == 1 else 'empty'}
                fill(block['start_x']+col*engine.PART2_STEP_X, block['start_y']+row*engine.PART2_STEP_Y)
        values = [({'digit_1_0','comma_2','digit_3_2','sign'}),
                  {'digit_0_1','digit_1_5','digit_2_9','digit_3_9'},
                  {'digit_1_0','comma_2','digit_3_8','sign'},
                  {'digit_0_1','comma_1','digit_2_2','digit_3_5'},
                  {'digit_0_2','digit_1_2'},
                  {'digit_0_7','digit_1_4','digit_2_2','digit_3_0'}]
        for block, marks in zip(engine.PART3_BLOCKS, values):
            coordinates = {'sign': (block['sign_x'], engine.PART3_SIGN_Y)}
            for col, x in enumerate(block['cols_x']):
                coordinates[f'comma_{col}'] = (x, engine.PART3_COMMA_Y)
                for digit in range(10):
                    coordinates[f'digit_{col}_{digit}'] = (x, engine.PART3_DIGIT_START_Y+digit*engine.PART3_DIGIT_STEP_Y)
            truth[3, block['q'], ''] = {key: 'filled' if key in marks else 'empty' for key in coordinates}
            for key in marks:
                fill(*coordinates[key])
        raw = cv2.imencode('.png', photo)[1].tobytes()
        endpoint = '/api/v1/training/corrections/sheet/'
        preview = client.post(endpoint+'preview/', {'image': SimpleUploadedFile('synthetic.png', raw),
            'template_code': '40-08-06', 'corners': json.dumps([[0,0],[1399,0],[1399,1919],[0,1919]])}, format='multipart')
        assert preview.status_code == 200, preview.data
        items = []
        for sample in preview.data['samples']:
            assert sample['geometry']['aligned'], (sample['part'], sample['question'], sample['subquestion'])
            items.append({'preview_token':sample['preview_token'], 'review_confirmed':True,
                'labels': truth[sample['part'], sample['question'], sample['subquestion']]})
        fields = {'image':SimpleUploadedFile('synthetic.png',raw), 'items':json.dumps(items),
                  'confirmed':'true','approve':'true'}
        saved = client.post(endpoint+'save/',fields,format='multipart')
        assert saved.status_code == 200, saved.data
        archive_path = output / 'training-demo.zip'
        with archive_path.open('wb') as file:
            assert write_dataset(file,TrainingCorrection.objects.all()) == 78
        # Mark the demonstration explicitly; it must not enter real reviewed data.
        with zipfile.ZipFile(archive_path) as archive:
            files = {name:archive.read(name) for name in archive.namelist()}
        manifest = json.loads(files['manifest.json'])
        manifest['dataset_kind'] = 'synthetic_demo_not_production'
        for sample in manifest['samples']:
            sample['label_origin'] = 'known_synthetic_fixture'
        files['manifest.json'] = json.dumps(manifest,ensure_ascii=False,indent=2).encode()
        with zipfile.ZipFile(archive_path,'w',zipfile.ZIP_DEFLATED) as archive:
            for name, content in files.items():
                archive.writestr(name,content)
        for name, content in files.items():
            dest = output / name
            dest.parent.mkdir(parents=True,exist_ok=True)
            dest.write_bytes(content)
        summary = {'kind':'synthetic_demo_not_production','questions':78,
                   'filled':0,
                   'empty':0,'original_photos':len([n for n in files if n.startswith('sources/')]),
                   'parts': {str(p):sum(s['part']==p for s in manifest['samples']) for p in (1,2,3)},
                   'scan_needs_review':preview.data['needs_review']}
        for label in ('filled','empty'):
            summary[label] = sum(n.startswith(label+'/') for n in files)
        assert summary['filled']+summary['empty'] == 494
        (output/'summary.json').write_text(json.dumps(summary,indent=2),encoding='utf-8')
        (output/'DEMO.txt').write_text('SYNTHETIC TEST ONLY: generated sheet and known fixture marks.\n'
            'Not a student submission; not synchronized from VPS; no production labels inserted.\n',encoding='utf-8')
        print(json.dumps(summary))
        connection.close()


if __name__ == '__main__':
    main()
