"""Part III shadow regression and conservative ink/ambiguity controls."""
from pathlib import Path
import unittest

import cv2
import numpy as np
from grading.engine import live_bubble_reader as live


class Part3ShadowTests(unittest.TestCase):
    def bubble(self, ink=None, shadow=True):
        image = np.full((90, 90), 220, np.uint8)
        cv2.circle(image, (45, 45), 13, 65, 2)
        if ink is not None:
            cv2.circle(image, (45, 45), 9, ink, -1)
        if shadow:
            y = np.arange(90)[:, None]
            image = (image * (1 - .15 * np.exp(-((y - 45) / 12) ** 2))).astype(np.uint8)
        return image

    def test_horizontal_shadow_is_blank_only_with_local_paper_guard(self):
        image = self.bubble()
        self.assertEqual(live.measure_ink(image, 45, 45).state, 'uncertain')
        self.assertEqual(live.measure_ink(image, 45, 45, row_background=True).state, 'blank')

    def test_pencil_ink_under_shadow_is_preserved(self):
        for ink in (40, 90, 140):
            with self.subTest(ink=ink):
                image = self.bubble(ink)
                self.assertEqual(live.measure_ink(image, 45, 45, row_background=True).state, 'marked')

    def test_faint_erasure_and_partial_marks_stay_unresolved(self):
        for shadow in (False, True):
            image = self.bubble(198, shadow)
            self.assertEqual(live.measure_ink(image, 45, 45, row_background=True).state, 'uncertain')
        image = self.bubble(shadow=False)
        cv2.rectangle(image, (40, 39), (44, 51), 100, -1)
        self.assertEqual(live.measure_ink(image, 45, 45, row_background=True).state, 'uncertain')

    def test_dark_paper_and_one_dirty_reference_do_not_clear_faint_ink(self):
        image = self.bubble(198, False)
        image[:, 25:29] = 80  # Left paper reference only; right still proves faint ink.
        self.assertEqual(live.measure_ink(image, 45, 45, row_background=True).state, 'uncertain')
        self.assertEqual(live.measure_ink(np.full((90, 90), 30, np.uint8),
                                        45, 45, row_background=True).state, 'invalid')


class CameraPart3ShadowTests(unittest.TestCase):
    # Raw grayscale crops: no name, student ID, answer overlay, or correction.
    folder = Path(__file__).parent / 'fixtures' / 'part3_shadow'
    block = [{'q': 1, 'cols_x': [46, 80, 114, 148], 'sign_x': 46}]

    def read(self, gray):
        return live.read_part3(gray, self.block, 42, 75, 108, 33.1,
                               y_offset=-2, local_symbols=True)

    def test_corrected_camera_sheets_read_negative_decimal(self):
        for name in ('1029', '1048'):
            gray = cv2.imread(str(self.folder / (name + '.png')), cv2.IMREAD_GRAYSCALE)
            self.assertIsNotNone(gray)
            for gain in (.8, 1., 1.08):
                with self.subTest(capture=name, gain=gain):
                    image = np.clip(gray.astype(float) * gain, 0, 255).astype(np.uint8)
                    answers, detail = self.read(image)
                    self.assertEqual(answers[1], '-0.2')
                    self.assertFalse(detail[1]['live_evidence']['needs_review'])

    def test_actual_photo_with_second_digit_or_erasure_is_not_accepted(self):
        gray = cv2.imread(str(self.folder / '1048.png'), cv2.IMREAD_GRAYSCALE)
        self.assertIsNotNone(gray)
        _, details = self.read(gray)
        grid = details[1]['live_grid']
        point = (round(grid['columns'][1]), round(grid['rows'][5]))
        for ink in (60, 164):  # An extra strong mark or faint erasure in digit 0's column.
            with self.subTest(ink=ink):
                edited = gray.copy()
                cv2.circle(edited, point, 8, ink, -1)
                answers, detail = self.read(edited)
                self.assertEqual(answers[1], '')
                self.assertTrue(detail[1]['live_evidence']['needs_review'])


if __name__ == '__main__':
    unittest.main()
