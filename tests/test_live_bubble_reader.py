"""Live-only regression: original camera JPEGs, negative and positive controls."""
import ast
import contextlib
import io
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

import cv2
import numpy as np

from grading.engine import hi as engine
from grading.engine import live_bubble_reader as live

ROOT = Path(__file__).resolve().parents[1]
TPL = ROOT / 'grading/engine/templates/template_default.json'


def fixtures():
    records = json.loads((ROOT / 'tests/ketqua/live_v3_device/20260911_212322_617709.json').read_text())
    import re
    by_size = {}
    for line in records['lines']:
        m = re.search(r'bytes=(\d+) corners=(\[.*\])', line)
        if m:
            by_size[int(m[1])] = json.loads(m[2])
    for path in sorted((ROOT / 'media/submissions/2026/09').glob('live*.jpg')):
        if path.stat().st_size in by_size:
            image = cv2.imread(str(path))
            yield path.name, engine._warp_to_rect(image, np.float32(by_size[path.stat().st_size]))


def p2(gray):
    return live.read_part2(gray, engine.PART2_BLOCKS, engine.PART2_STEP_X,
                          engine.PART2_STEP_Y, engine.PART2_ROWS)


def p3(gray):
    return live.read_part3(gray, engine.PART3_BLOCKS, engine.PART3_SIGN_Y,
                          engine.PART3_COMMA_Y, engine.PART3_DIGIT_START_Y,
                          engine.PART3_DIGIT_STEP_Y)


class LiveBubbleTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        with contextlib.redirect_stdout(io.StringIO()):
            engine.load_template(str(TPL))
        engine.HYBRID_CNN_ENABLE = False  # This offline test process only.
        cls.images = list(fixtures())
        assert len(cls.images) == 5, 'Real fixtures required, not silently skipped'

    def test_blank_originals_part2_part3(self):
        for name, image in self.images:
            with self.subTest(name=name):
                gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
                a2, _ = p2(gray)
                a3, _ = p3(gray)
                self.assertTrue(all(v == '' for rows in a2.values() for v in rows.values()), a2)
                self.assertTrue(all(v == '' for v in a3.values()), a3)

    def test_confirm_old_false_positive_on_same_image(self):
        image = dict(self.images)['live_zLyBU2p.jpg']
        processed, _, _ = engine.preprocess(image)
        old, _ = engine.extract_part2(processed, fast_mode=True)
        self.assertEqual(old[1]['d'], 'Dung')
        self.assertEqual(old[2]['d'], 'Dung')
        raw = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
        evidence = live.measure_ink(raw, 81, 1289)
        self.assertEqual(evidence.state, 'blank')
        self.assertLess(evidence.contrast, .03)

    def test_old_template_marks_never_become_a_wrong_answer(self):
        # These original synthetic dots are 3-6 px below the printed centers.
        # Preserve them as off-center/partial-fill controls: ambiguous ink must
        # remain unresolved, never be converted to an incorrect digit.
        for name, image in self.images:
            with self.subTest(name=name):
                gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
                # Add controlled marks to original background, not the result overlay.
                for x, y in [(81, 1190), (301, 1289), (81, 1492), (115, 1525),
                             (81, 1591), (115, 1624), (149, 1657), (183, 1690)]:
                    cv2.circle(gray, (x, y), 8, 65, -1)
                a2, _ = p2(gray)
                a3, _ = p3(gray)
                self.assertEqual(a2[1]['a'], 'Dung')
                self.assertEqual(a2[2]['d'], 'Sai')
                self.assertIn(a3[1], ('-1.234', ''), a3)

    def test_real_background_centered_positive_controls_all_five_images(self):
        # Fixed references independently measured on the unmarked originals
        # using external-contour moments after Otsu, NOT align_grid output.
        # Order: sign, decimal, then digits 1/2/3/4 in columns 0/1/2/3.
        centers = {
            'live.jpg': [(82,1488),(116,1521),(82,1587),(115,1620),(149,1654),(183,1687)],
            'live_klrrPli.jpg': [(82,1487),(116,1520),(82,1586),(116,1620),(150,1653),(183,1687)],
            'live_zLyBU2p.jpg': [(82,1486),(116,1519),(82,1585),(115,1619),(149,1652),(183,1686)],
            'live_ZtQLBlD.jpg': [(82,1488),(116,1521),(82,1587),(116,1620),(149,1654),(183,1687)],
            'live_ZVPQfEV.jpg': [(82,1487),(116,1520),(82,1586),(116,1619),(150,1653),(183,1686)],
        }
        for name, image in self.images:
            for dx, dy in [(0, 0), (-2, -2), (2, 2)]:
                with self.subTest(name=name, shift=(dx, dy)):
                    gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
                    for x, y in centers[name]:
                        cv2.circle(gray, (x + dx, y + dy), 8, 65, -1)
                    answers, _ = p3(gray)
                    self.assertEqual(answers[1], '-1.234', answers)

    def test_rims_shadows_specks_and_faint_erasures_are_not_marks(self):
        for background in [90, 140, 210, 245]:
            for dx in [-3, 0, 3]:
                image = np.full((80, 80), background, np.uint8)
                cv2.circle(image, (40 + dx, 40), 13, 35, 2)
                cv2.circle(image, (42, 42), 1, 35, -1)
                self.assertNotEqual(live.measure_ink(image, 40, 40).state, 'marked')
            image = np.full((80, 80), background, np.uint8)
            cv2.circle(image, (40, 40), 8, int(background * .96), -1)
            self.assertEqual(live.measure_ink(image, 40, 40).state, 'blank')

    def test_clear_marks_dark_and_light_paper_and_small_shift(self):
        for background in [90, 140, 210, 245]:
            for dx in [-2, 0, 2]:
                image = np.full((80, 80), background, np.uint8)
                cv2.circle(image, (40 + dx, 40), 9, int(background * .70), -1)
                self.assertEqual(live.measure_ink(image, 40, 40).state, 'marked')

    def test_multi_marked_digit_column_is_not_silently_compacted(self):
        gray = np.full((1920, 1400), 220, np.uint8)
        for x, y in [(81, 1558), (81, 1591), (115, 1624)]:
            cv2.circle(gray, (x, y), 9, 80, -1)
        answers, details = p3(gray)
        self.assertEqual(answers[1], '')
        self.assertTrue(details[1]['live_evidence']['needs_review'])

    def test_live_overlay_draws_picked_only_not_legacy_ratio_fallback(self):
        canvas = np.zeros((1920, 1400, 3), np.uint8)
        details = {1: {'picked': {'sign': False, 'comma_col': -1, 'digits': [1, -1, -1, -1]},
                       'digits': [{0: .9, 1: .8}], 'ocr_boxes': []}}
        live.draw_part3(canvas, {1: {'student': '1', 'is_correct': False}}, details,
                        engine.PART3_BLOCKS, 1492, 1525, 1558, 33.1, 13, 3,
                        (0, 200, 0), (0, 0, 220))
        self.assertTrue(canvas[1573:1610, 62:101].any())
        self.assertFalse(canvas[1539:1572, 62:101].any())

    def test_default_upload_routing_and_live_opt_in_in_full_pipeline(self):
        image = dict(self.images)['live_zLyBU2p.jpg']
        with tempfile.TemporaryDirectory(prefix='live-omr-test-') as folder:
            path = str(Path(folder) / 'fixture.jpg')
            cv2.imwrite(path, image)
            with contextlib.redirect_stdout(io.StringIO()), patch.object(
                    live, 'read_part2', wraps=live.read_part2) as reader:
                default = engine.process_sheet(path, pre_warped=True, fast_mode=True)
                reader.assert_not_called()  # Upload's fast=1 must NOT opt into Live.
                explicit = engine.process_sheet(path, pre_warped=True, fast_mode=True,
                                                live_bubble_mode=True)
                reader.assert_called_once()
            self.assertEqual(default['part1'], explicit['part1'])
            self.assertEqual(default['part2'][1]['d'], 'Dung')
            self.assertEqual(explicit['part2'][1]['d'], '')

    def test_api_opt_in_is_not_fast_and_default_flag_is_false(self):
        import inspect
        self.assertIs(inspect.signature(engine.process_sheet).parameters['live_bubble_mode'].default, False)
        source = (ROOT / 'api/views.py').read_text(encoding='utf-8-sig')
        tree = ast.parse(source)
        assignments = [n for n in ast.walk(tree) if isinstance(n, ast.Assign)
                       and any(isinstance(t, ast.Name) and t.id == 'live_bubble_mode' for t in n.targets)]
        expression = ast.Expression(assignments[0].value)
        code = compile(expression, '<live-routing>', 'eval')
        from types import SimpleNamespace
        for data, expected in [({}, False), ({'fast': '1'}, False),
                               ({'capture_pipeline': 'anything'}, False),
                               ({'capture_pipeline': 'live_capture_v3'}, True)]:
            self.assertEqual(eval(code, {'request': SimpleNamespace(data=data)}), expected)


if __name__ == '__main__':
    unittest.main()
