"""Import API regression. No database writes; engine tests use temp inputs."""
import contextlib
import io
import json
import os
from pathlib import Path
import subprocess
import sys
from types import SimpleNamespace
import unittest
from unittest.mock import patch

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'chamdiemtudong.settings')
import django
django.setup()
from django.core.files.uploadedfile import SimpleUploadedFile
from rest_framework.test import APIRequestFactory, force_authenticate
from api import answer_image_import as importer
from api.views import parse_image_api

ROOT = Path(__file__).resolve().parents[1]
FIXTURE = ROOT / 'tests/fixtures/exam_import_capture_20260912.jpg'
PAYLOAD = {'made': '007', 'part1': {'1': 'a'},
           'part2': {'1': {'a': 'Dung', 'b': 'Sai'}}, 'part3': {'5': '22'}}


class AnswerImportTests(unittest.TestCase):
    def test_old_direct_call_reproduces_exact_masked_unicode_error(self):
        import numpy as np
        from grading.engine import hi as engine
        detection = {'warped': np.zeros((20, 20, 3), dtype=np.uint8),
                     'method': 'test', 'corners': np.zeros((4, 2))}
        sink = io.TextIOWrapper(io.BytesIO(), encoding='cp1252')
        with patch.object(engine, 'detect_paper_and_warp', return_value=detection), \
             contextlib.redirect_stdout(sink), self.assertRaises(UnicodeEncodeError) as caught:
            engine.process_sheet(str(FIXTURE), correct_answers=None, debug=False)
        # First diagnostic failed; the [LỖI] handler then hid that exception.
        self.assertEqual(caught.exception.object[caught.exception.start], '\u1ed6')
        self.assertEqual(caught.exception.start, 2)
        self.assertIsInstance(caught.exception.__context__, UnicodeEncodeError)

    def request(self, file=None, fields=None):
        request = APIRequestFactory().post('/api/v1/parse-image/',
            {**(fields or {}), **({} if file is None else {'file': file})}, format='multipart')
        force_authenticate(request, user=SimpleNamespace(is_authenticated=True))
        return parse_image_api(request)

    def test_utf8_child_and_cleanup_without_changing_parent_streams(self):
        paths = []
        parent_out, parent_err = sys.stdout, sys.stderr
        def child(cmd, **kwargs):
            paths.append(Path(cmd[-1]))
            self.assertTrue(paths[-1].is_file())
            self.assertIn('utf8', cmd)
            self.assertEqual(kwargs['encoding'], 'utf-8')
            self.assertEqual(kwargs['env']['PYTHONIOENCODING'], 'utf-8')
            self.assertTrue(kwargs['check'])
            self.assertEqual(kwargs['timeout'], 120)
            paths[-1].with_name('sheet_result.jpg').touch()
            return SimpleNamespace(stdout=json.dumps(PAYLOAD), stderr='[OK] Đã đọc phiếu')
        with patch.object(importer.subprocess, 'run', side_effect=child):
            result = importer.parse_answer_image(SimpleUploadedFile('phiếu.jpg', b'bytes'))
        self.assertEqual(result, PAYLOAD)
        self.assertFalse(paths[0].parent.exists())
        self.assertIs(sys.stdout, parent_out)
        self.assertIs(sys.stderr, parent_err)

    def test_failure_and_timeout_always_cleanup(self):
        for error in [subprocess.CalledProcessError(1, ['python'], stderr='lỗi xử lý'),
                      subprocess.TimeoutExpired(['python'], 120)]:
            paths = []
            def fail(cmd, **kwargs):
                paths.append(Path(cmd[-1]))
                raise error
            with self.subTest(error=type(error).__name__), \
                 patch.object(importer.subprocess, 'run', side_effect=fail), \
                 self.assertRaises(RuntimeError):
                importer.parse_answer_image(SimpleUploadedFile('sheet.jpg', b'bytes'))
            self.assertFalse(paths[0].parent.exists())

    def test_api_keeps_existing_review_payload(self):
        with patch.object(importer, 'parse_answer_image', return_value=PAYLOAD):
            response = self.request(SimpleUploadedFile('sheet.jpg', b'bytes'))
        self.assertEqual(response.status_code, 200)
        variant = response.data['data']['variants'][0]
        self.assertEqual(variant['code'], '007')
        self.assertEqual(variant['p1'], {'1': 'A'})
        self.assertEqual(variant['p2'], {'1': {'a': 'Đ', 'b': 'S'}})
        self.assertEqual(variant['p3'], {'5': '22'})

    def test_api_missing_or_unsupported_file_never_starts_worker(self):
        with patch.object(importer, 'parse_answer_image') as reader:
            self.assertEqual(self.request().status_code, 400)
            self.assertEqual(self.request(SimpleUploadedFile('sheet.exe', b'x')).status_code, 400)
            reader.assert_not_called()

    def test_no_sheet_remains_a_readable_error(self):
        with patch.object(importer, 'parse_answer_image', return_value=None):
            response = self.request(SimpleUploadedFile('sheet.jpg', b'x'))
        self.assertEqual(response.status_code, 400)
        self.assertIn('Không thể đọc phiếu', response.data['error'])

    def test_unknown_variant_is_not_invented_as_001(self):
        with patch.object(importer, 'parse_answer_image', return_value={**PAYLOAD, 'made': '?01'}):
            response = self.request(SimpleUploadedFile('sheet.jpg', b'x'))
        self.assertEqual(response.data['data']['variants'][0]['code'], '')

    def test_invalid_camera_metadata_is_rejected_before_worker(self):
        fields = {'capture_pipeline': 'exam_import_capture_v1',
                  'capture_width': '200', 'capture_height': '300',
                  'corners': json.dumps([[10,10],[190,10],[190,290],[10,290]])}
        self.assertEqual(importer.capture_options(fields)['width'], 200)
        for change in [ {'capture_pipeline': 'other'}, {'corners': 'invalid'},
                        {'corners': '[[0,0],[1,0],[1,1],[0,1]]'},
                        {'corners': '[[10,10],[190,290],[190,10],[10,290]]'},
                        {'corners': '[[10,10],[200,10],[190,290],[10,290]]'},
                        {'corners': '[[10,10],[NaN,10],[190,290],[10,290]]'} ]:
            with self.subTest(change=change), patch.object(importer, 'parse_answer_image') as reader:
                response = self.request(SimpleUploadedFile('sheet.jpg', b'x'), {**fields, **change})
                self.assertEqual(response.status_code, 400)
                reader.assert_not_called()

    def test_camera_fixture_reads_new_identifiers_and_part3(self):
        fields = json.loads((ROOT / 'tests/fixtures/exam_import_v1.json').read_text())
        image = (ROOT / 'tests/fixtures/exam_import_v1.jpg').read_bytes()
        response = self.request(SimpleUploadedFile('camera.jpg', image), fields)
        self.assertEqual(response.status_code, 200, response.data)
        data = response.data['data']
        self.assertEqual(data['detect_method'], 'frontend_corners')
        variant = data['variants'][0]
        self.assertEqual(variant['code'], '001')
        self.assertEqual(variant['p3'], {'1':'-0.2','2':'1599','3':'-0.8','4':'1.25','5':'22','6':'2100'})
        self.assertFalse(any(str(q) in variant['p2'] for q in range(3, 9)))
        # Actual marked answers towards the right of the sheet must survive.
        self.assertEqual(variant['p1']['31'], 'B')
        self.assertEqual(variant['p1']['39'], 'D')

    def test_camera_dimensions_must_match_uploaded_jpeg(self):
        fields = json.loads((ROOT / 'tests/fixtures/exam_import_v1.json').read_text())
        fields['capture_width'] = str(int(fields['capture_width']) + 10)
        image = (ROOT / 'tests/fixtures/exam_import_v1.jpg').read_bytes()
        response = self.request(SimpleUploadedFile('camera.jpg', image), fields)
        self.assertEqual(response.status_code, 400)
        self.assertIn('không khớp', response.data['error'])

    def test_real_bad_image_under_cp1252_has_no_charmap_exception(self):
        sink = io.TextIOWrapper(io.BytesIO(), encoding='cp1252')
        with contextlib.redirect_stdout(sink):
            response = self.request(SimpleUploadedFile('sheet.jpg', b'not an image'))
            self.assertIs(sys.stdout, sink)
        self.assertEqual(response.status_code, 400)
        self.assertIn('Không thể đọc phiếu', response.data['error'])

    def test_real_1251_capture_under_cp1252_reaches_review(self):
        self.assertTrue(FIXTURE.is_file(), 'Real 12:51 capture fixture required')
        sink = io.TextIOWrapper(io.BytesIO(), encoding='cp1252')
        with contextlib.redirect_stdout(sink):
            response = self.request(SimpleUploadedFile('sheet.jpg', FIXTURE.read_bytes()))
            self.assertIs(sys.stdout, sink)
        self.assertEqual(response.status_code, 200, response.data)
        self.assertTrue(response.data['success'])
        data = response.data['data']
        self.assertEqual(data['source'], 'image')
        self.assertEqual(data['variantCount'], 1)
        self.assertTrue(data['variants'][0]['p1'])


if __name__ == '__main__':
    unittest.main()
