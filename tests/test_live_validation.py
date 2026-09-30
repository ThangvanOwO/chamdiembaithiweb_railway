import contextlib
import io
import json
from pathlib import Path
import unittest
from unittest.mock import patch

import cv2
import numpy as np
from grading.engine import live_bubble_reader as live
from grading.live_latency import LiveAnswerKeySelection
from test_live_latency import KEY_A, KEY_B


class StrictVariantTests(unittest.TestCase):
    def test_unregistered_unclear_and_duplicate_digit_never_fallback(self):
        for code in ('002', '???', '', '00?', '1', '００１', None):
            for early in (False, True):
                selector = LiveAnswerKeySelection(KEY_A, [('001', KEY_A)], json.loads, strict=True, choose_early=early)
                with self.assertRaises(ValueError):
                    selector.resolve(code)

    def test_registered_code_selects_key_without_losing_leading_zero(self):
        selector = LiveAnswerKeySelection(KEY_A, [('001', KEY_A), ('002', KEY_B)], json.loads, strict=True)
        self.assertEqual(selector.resolve('002'), json.loads(KEY_B))


class RawEvidenceTests(unittest.TestCase):
    def test_incomplete_decimal_and_internal_gap_are_not_silently_shortened(self):
        blank = live.InkEvidence('blank', 0, 0, 0)
        marked = live.InkEvidence('marked', .5, 1., 4)
        for digits, comma in (([-1, 0, -1, -1], 2), ([2, -1, 2, -1], -1)):
            evidence = [blank] + [marked if i == comma else blank for i in range(4)]
            evidence += [marked if d == selected else blank for selected in digits for d in range(10)]
            with patch.object(live, 'align_grid', return_value=([60, 100, 140, 180], list(range(100, 500, 40)), False)), \
                 patch.object(live, 'measure_ink', side_effect=evidence):
                answers, detail = live.read_part3(np.zeros((600, 250), np.uint8),
                    [{'q': 1, 'cols_x': [60, 100, 140, 180], 'sign_x': 60}], 20, 60, 100, 40,
                    local_symbols=True)
            self.assertEqual(answers[1], '')
            self.assertTrue(detail[1]['live_evidence']['needs_review'])

    def sheet(self):
        image = np.full((520, 330), 235, np.uint8)
        for row in range(10):
            for col in range(4):
                cv2.circle(image, (60 + col * 60, 60 + row * 40), 13, 75, 2)
        return image

    def read(self, image):
        return live.read_part1(image, [{'start_x': 60, 'start_y': 60, 'step_x': 60, 'step_y': 40}], list('ABCD'))

    def test_printed_rims_never_become_marked(self):
        for gain in (.75, 1.):
            image = np.clip(self.sheet().astype(float) * gain, 0, 255).astype(np.uint8)
            answers, _, details = self.read(image)
            self.assertTrue(all(answer == '' for answer in answers.values()))
            self.assertTrue(all(not d['needs_review'] for d in details.values()))

    def test_two_unequally_dark_marks_are_invalid_not_argmax(self):
        image = self.sheet()
        cv2.circle(image, (60, 60), 9, 20, -1)
        cv2.circle(image, (120, 60), 9, 115, -1)
        answers, _, details = self.read(image)
        self.assertEqual(answers[1], 'X')
        self.assertTrue(details[1]['needs_review'])
        mask = np.zeros((*image.shape, 3), np.uint8)
        live.draw_choice_result(mask, {'student': 'X', 'correct': 'A', 'is_correct': False},
            details[1]['evidence'], details[1]['points'], list('ABCD'), 13, 5)
        self.assertTrue(np.any(np.all(mask == (0, 200, 255), axis=2)))
        self.assertFalse(np.any(np.all(mask == (0, 180, 0), axis=2)))

    def test_single_mark_and_blank_key_cell_overlay(self):
        image = self.sheet()
        cv2.circle(image, (60, 60), 9, 80, -1)
        answers, _, details = self.read(image)
        self.assertEqual(answers[1], 'A')
        mask = np.zeros((*image.shape, 3), np.uint8)
        live.draw_choice_result(mask, {'student': 'A', 'correct': 'B', 'is_correct': False},
            details[1]['evidence'], details[1]['points'], list('ABCD'), 13, 5)
        self.assertTrue(np.any(np.all(mask == (0, 0, 220), axis=2)))
        self.assertFalse(np.any(np.all(mask == (0, 180, 0), axis=2)))

    def test_part2_two_marks_same_row_invalid_but_different_rows_allowed(self):
        image = self.sheet()
        for point in ((60, 60), (120, 60), (60, 100), (120, 140)):
            cv2.circle(image, point, 9, 70, -1)
        answers, _ = live.read_part2(image, [{'q': 1, 'start_x': 60, 'start_y': 60}],
                                    60, 40, list('abcd'), align=True)
        self.assertEqual(answers[1]['a'], 'X')
        self.assertEqual(answers[1]['b'], 'Dung')
        self.assertEqual(answers[1]['c'], 'Sai')

    def test_invalid_answers_do_not_receive_points(self):
        from grading import grader
        self.assertEqual(grader.engine.grade_part1({1: 'X'}, {1: 'A'}, 1)[0], 0)
        self.assertEqual(grader.engine.grade_part3({1: ''}, {1: '7420'}, 1)[0], 0)
        score, _ = grader.score_part2_moet({1: {'a': 'X', 'b': 'Dung', 'c': 'Dung', 'd': 'Dung'}},
                                         {1: dict.fromkeys('abcd', 'Dung')})
        self.assertEqual(score, .5)  # Only the three valid subanswers earn credit.


class OriginalPhotoTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        from grading import grader
        cls.engine = grader.engine
        cls.root = Path(__file__).resolve().parents[1]
        with contextlib.redirect_stdout(io.StringIO()):
            cls.engine.load_template(str(cls.root / 'grading/engine/templates/template_default.json'))
        cls.images = {}
        records = json.loads((cls.root / 'scratch/live_validation_20260915_b/report.json').read_text(encoding='utf-8'))
        cls.offsets = {Path(r['source']).stem: r['result']['offsets'] for r in records if r['enabled']}
        # Original-pixel rectifications produced by audit_live_validation.py.
        for name in ('live_H6cQfZ2', 'live_XbTsC8z', 'live_M2fMCpf', 'live_t0EDDxm', 'exam_import_v1'):
            path = cls.root / 'scratch/live_validation_20260915_b' / (name + '_1') / 'raw_warp.png'
            image = cv2.imread(str(path), cv2.IMREAD_GRAYSCALE)
            assert image is not None, 'Run audit_live_validation.py to prepare original-pixel warps'
            cls.images[name] = image

    def read(self, gray, offsets=None):
        e = self.engine
        offsets = offsets or {'part1': 0, 'part2': 0, 'part3': 0}
        p1, _, detail = live.read_part1(gray, e.PART1_COLS, e.PART1_CHOICES, y_offset=offsets['part1'])
        p2, d2 = live.read_part2(gray, e.PART2_BLOCKS, e.PART2_STEP_X, e.PART2_STEP_Y, e.PART2_ROWS,
                               y_offset=offsets['part2'], align=True)
        p3, d3 = live.read_part3(gray, e.PART3_BLOCKS, e.PART3_SIGN_Y, e.PART3_COMMA_Y,
                               e.PART3_DIGIT_START_Y, e.PART3_DIGIT_STEP_Y,
                               y_offset=offsets['part3'], local_symbols=True)
        return p1, p2, p3, detail, d2, d3

    def test_confirmed_676_three_original_photos(self):
        e = self.engine
        for name in ('live_H6cQfZ2', 'live_XbTsC8z', 'live_M2fMCpf'):
            with self.subTest(name=name):
                gray = self.images[name]
                ids = live.read_identifiers(gray, e.SBD_COLS_X, e.MADE_COLS_X, e.SBD_MADE_DIGIT_Y)
                self.assertEqual(ids[:2], ('032215', '676'))
                p1, p2, p3, *_ = self.read(gray, self.offsets[name])
                self.assertEqual(p3[6], '7420')
                self.assertEqual(p1[4], 'B')

    def test_original_blank_sheet_and_brightness_controls(self):
        source = self.images['live_t0EDDxm']
        for gain in (.8, 1., 1.08):
            image = np.clip(source.astype(float) * gain, 0, 255).astype(np.uint8)
            p1, p2, p3, *_ = self.read(image)
            self.assertTrue(all(v == '' for v in p1.values()))
            self.assertTrue(all(v == '' for rows in p2.values() for v in rows.values()))
            self.assertTrue(all(v == '' for v in p3.values()))

    def test_stable_001_and_actual_double_mark(self):
        p1, p2, p3, details, *_ = self.read(self.images['exam_import_v1'])
        self.assertEqual(p1[10], 'X')
        self.assertTrue(details[10]['needs_review'])
        self.assertEqual(p3, {1: '-0.2', 2: '1599', 3: '-0.8', 4: '1.25', 5: '22', 6: '2100'})

    def test_photo_122_missing_part2_cells_and_blank_part3(self):
        path = self.root / 'scratch/live_validation_20260915_122/9_1/raw_warp.png'
        gray = cv2.imread(str(path), cv2.IMREAD_GRAYSCALE)
        self.assertIsNotNone(gray)
        p1, p2, p3, *_ = self.read(gray, {'part1': 0, 'part2': 0, 'part3': -7})
        self.assertEqual(p2[1], {'a': 'Dung', 'b': 'Dung', 'c': 'Dung', 'd': 'Sai'})
        self.assertEqual(p2[2], {'a': 'Dung', 'b': 'Dung', 'c': 'Sai', 'd': 'Dung'})
        self.assertEqual(p2[3], {'a': 'Dung', 'b': 'Dung', 'c': 'Sai', 'd': 'Sai'})
        self.assertEqual(p2[4], {'a': 'Dung', 'b': 'Sai', 'c': 'Dung', 'd': 'Dung'})
        self.assertTrue(all(value == '' for value in p3.values()))
        self.assertTrue(all(p1[q] == '' for q in range(25, 41)))

    def test_p3_double_digit_yellow_and_not_scored(self):
        gray = self.images['exam_import_v1'].copy()
        _, _, _, _, _, d3 = self.read(gray)
        grid = d3[6]['live_grid']
        point = (int(round(grid['columns'][0])), int(round(grid['rows'][3])))
        cv2.circle(gray, point, 9, 70, -1)  # Real first column already has digit 2.
        _, _, p3, _, _, details = self.read(gray)
        self.assertEqual(p3[6], '')
        self.assertTrue(details[6]['live_evidence']['needs_review'])
        e = self.engine
        mask = np.zeros((*gray.shape, 3), np.uint8)
        live.draw_part3(mask, {6: {'student': '', 'is_correct': False}}, details, e.PART3_BLOCKS,
            e.PART3_SIGN_Y, e.PART3_COMMA_Y, e.PART3_DIGIT_START_Y, e.PART3_DIGIT_STEP_Y,
            13, 5, (0, 180, 0), (0, 0, 220), warn_ambiguous=True)
        self.assertTrue(np.any(np.all(mask == (0, 200, 255), axis=2)))


if __name__ == '__main__':
    unittest.main()
