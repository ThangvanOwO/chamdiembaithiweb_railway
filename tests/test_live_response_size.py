"""Exercise the real grade endpoint; mocks only grading, ORM and billing."""
import base64
import json
import os
from pathlib import Path
from types import SimpleNamespace
import unittest
from unittest.mock import patch

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'chamdiemtudong.settings')
import django
django.setup()
from django.core.files.uploadedfile import SimpleUploadedFile
from rest_framework.test import APIRequestFactory, force_authenticate
from api import views


class LiveResponseSizeTests(unittest.TestCase):
    def run_request(self, overlay=None):
        calls = []
        def grade(path, key, template, **kwargs):
            calls.append(kwargs)
            if 'live_answer_key_resolver' in kwargs:
                kwargs['live_answer_key_resolver']('001')
            Path(path).with_suffix('.jpg').write_bytes(b'source')
            base = Path(path).with_suffix('')
            Path(str(base) + '_overlay.jpg').write_bytes(b'overlay' * 1000)
            result = Path(str(base) + '_result.jpg')
            result.write_bytes(b'result')
            return dict(success=True, score=1, max_score=40, sbd='000012',
                        made='001', part1={1: 'B'}, part2={}, part3={},
                        result_image_path=str(result))
        exam = SimpleNamespace(template_code='40-08-06',
            answer_key=json.dumps({'part1': {'1': 'B'}}),
            variants=SimpleNamespace(all=lambda: [SimpleNamespace(
                variant_code='001', answer_key_str=json.dumps({'part1': {'1': 'B'}}))]))
        fields = dict(image=SimpleUploadedFile('fixture.jpg', b'input'),
                      exam_id='1', save='false', fast='1',
                      capture_pipeline='live_capture_v3')
        if overlay is not None:
            fields['include_overlay'] = overlay
        request = APIRequestFactory().post('/api/v1/grade/', fields, format='multipart')
        force_authenticate(request, user=SimpleNamespace(
            is_authenticated=True, is_active=True, is_staff=False))
        with patch.object(views.Exam.objects, 'get', return_value=exam), \
             patch.object(views, 'grade_image', side_effect=grade), \
             patch.object(views.Submission.objects, 'create', side_effect=AssertionError('DB write')), \
             patch('shutil.copy2'), \
             patch('accounts.scan_billing._request_identity', return_value=('size-test', 'fingerprint')), \
             patch('accounts.scan_billing.reserve_scan', return_value=(SimpleNamespace(), True)), \
             patch('accounts.scan_billing.finish_scan') as billing:
            response = views.grade_api(request)
        self.assertEqual(response.status_code, 200, response.data)
        self.assertTrue(response.data['success'], response.data)
        billing.assert_called_once()
        self.assertEqual(len(calls), 1)
        return response.data

    def test_opt_out_keeps_scoring_result_image_and_billing(self):
        full = self.run_request()
        compact = self.run_request('false')
        self.assertEqual(full['overlay_image'], base64.b64encode(b'overlay' * 1000).decode())
        self.assertEqual(compact['overlay_image'], '')
        for field in full:
            if field != 'overlay_image':
                self.assertEqual(compact[field], full[field], field)
        self.assertEqual(compact['result_image'], base64.b64encode(b'result').decode())
        self.assertLess(len(json.dumps(compact)), len(json.dumps(full)))

    def test_explicit_true_retains_legacy_response(self):
        self.assertEqual(self.run_request('true'), self.run_request())

if __name__ == '__main__':
    unittest.main()
