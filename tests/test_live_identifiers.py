"""User-confirmed IDs/Q5 and an additional third capture, plus blank controls.

Run tools/diagnostics/audit_live_identifiers.py to rebuild the offline original-
pixel warps. Annotated result pixels are never inputs to the reader under test.
"""
import contextlib
import io
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

import cv2
import numpy as np
from grading.engine import hi as engine
from grading.engine import live_bubble_reader as live
from test_live_bubble_reader import fixtures

ROOT = Path(__file__).resolve().parents[1]
BASE = ROOT / 'tests/ketqua/live_identifiers_20260912'


class IdentifierTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        with contextlib.redirect_stdout(io.StringIO()):
            engine.load_template(str(ROOT / 'grading/engine/templates/template_default.json'))
        cls.images = []
        for name in ['live_O2ZBpeK', 'live_F6lMUpt', 'live_Mq6I2UX']:
            image = cv2.imread(str(BASE / name / 'raw_warp.png'), cv2.IMREAD_GRAYSCALE)
            assert image is not None, 'Required original-pixel warp is missing'
            cls.images.append((name, image))

    def read(self, image):
        ids = live.read_identifiers(image, engine.SBD_COLS_X, engine.MADE_COLS_X, engine.SBD_MADE_DIGIT_Y)
        answers, details = live.read_part3(image, engine.PART3_BLOCKS, engine.PART3_SIGN_Y,
            engine.PART3_COMMA_Y, engine.PART3_DIGIT_START_Y, engine.PART3_DIGIT_STEP_Y)
        return ids, answers, details

    def test_three_original_captures_match_confirmed_ground_truth(self):
        for name, image in self.images:
            with self.subTest(source=name):
                ids, answers, details = self.read(image)
                self.assertEqual(ids[:2], ('011232', '001'))
                self.assertEqual(answers[5], '22')
                self.assertFalse(details[5]['live_evidence']['needs_review'])
                self.assertEqual(answers, {1: '-0.2', 2: '1599', 3: '-0.8', 4: '1.25', 5: '22', 6: '2100'})

    def test_brightness_blur_and_small_translation(self):
        for name, original in self.images:
            for gain, dx, dy, blur in [(.85, 0, 0, False), (1.1, 0, 0, True), (1., 2, 2, False)]:
                with self.subTest(source=name, gain=gain, shift=(dx, dy), blur=blur):
                    image = np.clip(original.astype(float) * gain, 0, 255).astype(np.uint8)
                    if blur:
                        image = cv2.GaussianBlur(image, (3, 3), .6)
                    if dx or dy:
                        image = cv2.warpAffine(image, np.float32([[1, 0, dx], [0, 1, dy]]),
                            (image.shape[1], image.shape[0]), borderValue=230)
                    ids, answers, _ = self.read(image)
                    self.assertEqual(ids[:2], ('011232', '001'))
                    self.assertEqual(answers[5], '22')

    def test_five_blank_originals_do_not_acquire_identifier_digits(self):
        images = list(fixtures())
        self.assertEqual(len(images), 5)
        for name, image in images:
            with self.subTest(source=name):
                gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
                ids, answers, _ = self.read(gray)
                self.assertEqual(ids[:2], ('??????', '???'))
                self.assertTrue(all(answer == '' for answer in answers.values()))

    def test_alignment_does_not_lock_to_sparse_filled_dots(self):
        image = np.full((600, 400), 230, np.uint8)
        cv2.circle(image, (105, 105), 10, 50, -1)
        xs, ys, aligned = live.align_grid(image, [100, 130, 160], list(range(100, 400, 30)), 10)
        self.assertFalse(aligned)
        self.assertEqual(xs, [100, 130, 160])

    def test_different_identifier_values_are_read_from_ink(self):
        image = np.full((1920, 1400), 230, np.uint8)
        for columns, value in [(engine.SBD_COLS_X, '123456'), (engine.MADE_COLS_X, '987')]:
            for col, x in enumerate(columns):
                for digit, y in enumerate(engine.SBD_MADE_DIGIT_Y):
                    center = (round(x), round(y))
                    cv2.circle(image, center, 9, 80, 2)
                    if digit == int(value[col]):
                        cv2.circle(image, center, 6, 70, -1)
        ids, _, _ = self.read(image)
        self.assertEqual(ids[:2], ('123456', '987'))

    def test_double_filled_identifier_column_is_unknown_not_argmax(self):
        image = self.images[0][1].copy()
        _, _, details = live.read_identifiers(image, engine.SBD_COLS_X, engine.MADE_COLS_X,
                                              engine.SBD_MADE_DIGIT_Y)
        grid = details['made_live']
        cv2.circle(image, (round(grid['columns'][0]), round(grid['rows'][5])), 8, 50, -1)
        ids, _, _ = self.read(image)
        self.assertEqual(ids[1][0], '?')

    def test_complete_pipeline_uses_new_ids_and_keeps_upload_legacy_reader(self):
        color = cv2.cvtColor(self.images[0][1], cv2.COLOR_GRAY2BGR)
        with tempfile.TemporaryDirectory(prefix='live-id-test-') as folder:
            path = str(Path(folder) / 'original.png')
            cv2.imwrite(path, color)
            # Write outputs only in this temporary directory, never original files.
            with patch.object(engine, 'HYBRID_CNN_ENABLE', False), \
                 patch.object(live, 'read_identifiers', wraps=live.read_identifiers) as reader, \
                 contextlib.redirect_stdout(io.StringIO()), contextlib.redirect_stderr(io.StringIO()):
                legacy = engine.process_sheet(path, pre_warped=True, fast_mode=True)
                reader.assert_not_called()
                current = engine.process_sheet(path, pre_warped=True, fast_mode=True, live_bubble_mode=True)
                reader.assert_called_once()
            self.assertEqual((current['sbd'], current['made'], current['part3'][5]), ('011232', '001', '22'))
            self.assertEqual(legacy['part1'], current['part1'])


if __name__ == '__main__':
    unittest.main()
