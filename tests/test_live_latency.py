"""No database writes. Live routing, rollback switches and recognition parity."""
import ast
import json
import os
from pathlib import Path
from types import SimpleNamespace
import unittest
from unittest.mock import patch

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'chamdiemtudong.settings')
import django
django.setup()
from django.test import override_settings
from django.core.files.uploadedfile import SimpleUploadedFile
from rest_framework.test import APIRequestFactory, force_authenticate
from api import views
from grading import grader
from grading.live_latency import LiveAnswerKeySelection, parts_signature


KEY_A = json.dumps({'part1': {'1': 'A'}})
KEY_B = json.dumps({'part1': {'1': 'B'}})


class SelectionTests(unittest.TestCase):
    def test_other_recognition_functions_are_unchanged_from_checkpoint(self):
        root = Path(__file__).resolve().parents[1]
        backup = root / 'scratch/restore_points/before_live_latency_20260914/before/grading/engine/hi.py'
        def functions(path):
            return {node.name: ast.dump(node) for node in ast.parse(path.read_text(encoding='utf-8')).body
                    if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)) and node.name != 'process_sheet'}
        before = functions(backup)
        current = functions(root / 'grading/engine/hi.py')
        self.assertEqual(set(current) - set(before), {'_live_box_background'})
        self.assertEqual(set(before) - set(current), set())
        for name in before:
            if name != 'preprocess':
                self.assertEqual(before[name], current[name], name)

    def test_selection_leaves_reading_configuration_and_key_intact(self):
        select = LiveAnswerKeySelection(KEY_A, [('001', KEY_A), ('002', KEY_B)], grader.parse_answer_key)
        self.assertEqual(select.resolve('002')['part1'][1], 'B')
        self.assertEqual(select.used_key, KEY_B)
        self.assertEqual(select.first_key, KEY_A)

    def test_blank_unknown_and_leading_zero_codes_preserve_old_fallback(self):
        for code in ('', '???', '2', '999'):
            select = LiveAnswerKeySelection(KEY_A, [('002', KEY_B)], grader.parse_answer_key)
            self.assertEqual(select.resolve(code)['part1'][1], 'A')

    def test_different_parts_require_old_rerun(self):
        key = json.dumps({'part1': {'1': 'B'}, 'parts': [20, 4, 6]})
        select = LiveAnswerKeySelection(KEY_A, [('002', key)], grader.parse_answer_key)
        self.assertEqual(select.resolve('002')['part1'][1], 'A')
        self.assertEqual(select.used_key, KEY_A)

    def test_equivalent_unrestricted_parts(self):
        for value in ('', 'A,B,C', '{}', '{"parts": []}', '{"parts": [null]}'):
            self.assertEqual(parts_signature(value), (None, None, None))
        self.assertEqual(parts_signature('{"parts": [0, 8, 6]}'), (0, 8, 6))

    def test_request_state_is_not_shared(self):
        first = LiveAnswerKeySelection(KEY_A, [('002', KEY_B)], grader.parse_answer_key)
        second = LiveAnswerKeySelection(KEY_B, [('002', KEY_A)], grader.parse_answer_key)
        first.resolve('002')
        second.resolve('002')
        self.assertEqual(first.used_key, KEY_B)
        self.assertEqual(second.used_key, KEY_A)

    def test_matching_explicit_parts_and_zero_limits(self):
        first = json.dumps({'part1': {'1': 'A'}, 'parts': [0, 8, 6]})
        second = json.dumps({'part1': {'1': 'B'}, 'parts': [0, 8, 6]})
        select = LiveAnswerKeySelection(first, [('002', second)], grader.parse_answer_key)
        self.assertEqual(select.resolve('002')['part1'][1], 'B')
        self.assertEqual(select.used_key, second)

    def test_key_hook_is_live_only_and_before_scoring(self):
        root = Path(__file__).resolve().parents[1]
        backup = root / 'scratch/restore_points/before_live_latency_20260914/before/grading/engine/hi.py'
        def function(path):
            return next(node for node in ast.parse(path.read_text(encoding='utf-8')).body
                        if isinstance(node, ast.FunctionDef) and node.name == 'process_sheet')
        old, new = function(backup), function(root / 'grading/engine/hi.py')
        hook = next(node for node in new.body if isinstance(node, ast.If)
                    and 'live_answer_key_resolver' in ast.unparse(node.test))
        self.assertIn('live_bubble_mode', ast.unparse(hook.test))
        score = next(node for node in new.body if isinstance(node, ast.If)
                     and ast.unparse(node.test) == 'correct_answers')
        self.assertLess(hook.lineno, score.lineno)


class ApiRoutingTests(unittest.TestCase):
    def run_request(self, live, single=True, background=False, code='002', second=KEY_B,
                    codes=('001', '002'), trial_header=False, staff=False, corners=False):
        variants = [SimpleNamespace(variant_code='001', answer_key_str=KEY_A),
                    SimpleNamespace(variant_code='002', answer_key_str=second)]
        variants = [v for v in variants if v.variant_code in codes]
        exam = SimpleNamespace(template_code='40-08-06', answer_key='',
                               variants=SimpleNamespace(all=lambda: variants))
        calls = []
        def fake_grade(path, key, template, **kwargs):
            calls.append((key, kwargs))
            try:
                parsed = kwargs['live_answer_key_resolver'](code) if 'live_answer_key_resolver' in kwargs else grader.parse_answer_key(key)
            except ValueError as exc:
                return {'success': False, 'error': str(exc)}
            return {'success': True, 'made': code, 'sbd': '011232', 'score': 1,
                    'max_score': 40, 'part1': {1: 'B'}, 'part2': {}, 'part3': {},
                    'scores': {'part1': int(parsed['part1'][1] == 'B')}}
        fields = {'image': SimpleUploadedFile('latency_test.jpg', b'test'), 'exam_id': '1',
                  'save': '1' if live and code not in codes else '0', 'fast': '1'}
        if live:
            fields['capture_pipeline'] = 'live_capture_v3'
        if corners:
            fields['corners'] = json.dumps([[0, 0], [1, 0], [1, 1], [0, 1]])
        request = APIRequestFactory().post('/api/v1/grade/', fields, format='multipart',
            HTTP_X_GRADEFLOW_BACKGROUND_TRIAL='box5' if trial_header else '')
        force_authenticate(request, user=SimpleNamespace(
            is_authenticated=True, is_active=True, is_staff=staff))
        with override_settings(LIVE_SINGLE_PASS_GRADING=single), \
             patch.dict(os.environ, {'LIVE_FAST_BACKGROUND': '1' if background else '0'}), \
             patch.object(views.Exam.objects, 'get', return_value=exam), \
             patch.object(views.Submission.objects, 'create', side_effect=AssertionError('No DB writes')), \
             patch.object(views, 'grade_image', side_effect=fake_grade), \
             patch('accounts.scan_billing._request_identity', return_value=('routing-test', 'fingerprint')), \
             patch('accounts.scan_billing.reserve_scan', return_value=(SimpleNamespace(), True)), \
             patch('accounts.scan_billing.finish_scan'):
            response = views.grade_api(request)
        self.assertEqual(response.status_code, 200, response.data)
        if live and code not in codes:
            self.assertFalse(response.data['success'], response.data)
        else:
            self.assertTrue(response.data['success'], response.data)
        return response.data, calls

    def test_live_different_key_only_one_call(self):
        result, calls = self.run_request(True)
        self.assertEqual(len(calls), 1)
        self.assertEqual(result['scores']['part1'], 1)
        self.assertEqual(result['correct_answers']['part1'][1], 'B')

    def test_kill_switch_restores_two_calls(self):
        result, calls = self.run_request(True, single=False)
        self.assertEqual(len(calls), 2)
        self.assertIn('live_answer_key_resolver', calls[0][1])  # Validation remains mandatory.
        self.assertEqual(result['scores']['part1'], 1)

    def test_upload_ignores_both_enabled_flags(self):
        _, calls = self.run_request(False, background=True, trial_header=True, staff=True, corners=True)
        self.assertEqual(len(calls), 2)
        for _, options in calls:
            self.assertNotIn('live_answer_key_resolver', options)
            self.assertNotIn('fast_background_trial', options)

    def test_parts_mismatch_falls_back_without_experimental_filter(self):
        key = json.dumps({'part1': {'1': 'B'}, 'parts': [20, 4, 6]})
        _, calls = self.run_request(True, background=True, second=key)
        self.assertEqual(len(calls), 2)
        self.assertNotIn('fast_background_trial', calls[1][1])

    def test_unknown_rejected_and_first_code_no_rerun(self):
        for code in ('???', '', '001'):
            _, calls = self.run_request(True, code=code)
            self.assertEqual(len(calls), 1)

    def test_rejected_background_trial_is_not_exposed(self):
        _, calls = self.run_request(True, single=False, background=True)
        self.assertNotIn('fast_background_trial', calls[0][1])

    def test_trial_requires_server_switch_staff_header_and_corners(self):
        for overrides in ({'background': False}, {'staff': False},
                          {'trial_header': False}, {'corners': False}):
            options = dict(background=True, staff=True, trial_header=True, corners=True)
            options.update(overrides)
            _, calls = self.run_request(True, **options)
            self.assertNotIn('fast_background_trial', calls[0][1], overrides)

        _, calls = self.run_request(True, background=True, staff=True,
                                    trial_header=True, corners=True)
        self.assertTrue(calls[0][1]['fast_background_trial'])

    def test_trial_flag_survives_live_variant_retry(self):
        _, calls = self.run_request(True, single=False, background=True,
                                    staff=True, trial_header=True, corners=True)
        self.assertEqual(len(calls), 2)
        self.assertTrue(all(call[1].get('fast_background_trial') for call in calls))

    def test_only_001_rejects_002_even_when_optimization_is_off(self):
        for single in (True, False):
            result, calls = self.run_request(True, single=single, code='002', codes=('001',))
            self.assertEqual(len(calls), 1)
            self.assertIn('002', result['error'])
            self.assertNotIn('score', result)
            self.assertNotIn('submission_id', result)

    def test_exam_without_variants_never_calls_engine(self):
        result, calls = self.run_request(True, codes=())
        self.assertFalse(result['success'])
        self.assertEqual(calls, [])


if __name__ == '__main__':
    unittest.main()
