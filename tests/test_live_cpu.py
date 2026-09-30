"""Live CPU routing, geometric fallback, scoring and thread isolation."""
import contextlib
import io
import os
from pathlib import Path
import tempfile
import subprocess
import sys
from threading import Event, Thread
import unittest
from unittest.mock import patch

import cv2
import numpy as np
from grading.cpu_runtime import serialized_grading
from grading.engine import hi as engine
from grading.engine import live_cpu

ROOT = Path(__file__).resolve().parents[1]


class LiveCpuTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.folder = Path(self.temp.name)
        with contextlib.redirect_stdout(io.StringIO()):
            engine.load_template(str(ROOT / 'grading/engine/templates/template_default.json'))
        gray = np.full((engine.WARP_HEIGHT, engine.WARP_WIDTH), 235, np.uint8)
        identifier_points = {(x, y) for x in engine.SBD_COLS_X + engine.MADE_COLS_X
                             for y in engine.SBD_MADE_DIGIT_Y}
        for x, y in engine.ALL_BUBBLE_CENTERS:
            cv2.circle(gray, (int(x), int(y)), 10 if (x, y) in identifier_points else 13, 75, 2)
        block = engine.PART1_COLS[0]
        cv2.circle(gray, (int(block['start_x'] + block['step_x']), int(block['start_y'])), 9, 40, -1)
        self.gray = gray
        self.image = self.folder / 'input.jpg'
        cv2.imwrite(str(self.image), gray)

    def run_sheet(self, **kwargs):
        with contextlib.redirect_stdout(io.StringIO()), patch('shutil.copy2'):
            return engine.process_sheet(str(self.image), pre_warped=True, debug=True,
                                        correct_answers={'part1': {1: 'B'}}, **kwargs)

    def test_raw_path_reads_real_marks_without_denoise_gaussian_or_cnn(self):
        with patch.object(engine, 'preprocess', side_effect=AssertionError('Heavy preprocessing')), \
             patch.object(engine, 'extract_part1', side_effect=AssertionError('Discarded legacy reader')), \
             patch.object(engine, '_load_bubble_cnn', side_effect=AssertionError('Unused CNN')):
            result = self.run_sheet(fast_mode=True, live_bubble_mode=True, live_validation=True, live_cpu_fast=True)
        self.assertEqual(result['preprocess_mode'], 'live_raw')
        self.assertEqual(result['part1'][1], 'B')
        self.assertEqual(result['score'], 1)
        self.assertEqual(result['cnn_status'], 'not_used_live')
        self.assertTrue(all(v == '' for v in result['part3'].values()))
        self.assertTrue((self.folder / 'input_result.jpg').exists())
        self.assertFalse((self.folder / 'input_thresh.jpg').exists())

    def test_unaligned_part3_falls_back_once_and_resolves_key_once(self):
        resolver = unittest.mock.Mock(return_value={'part1': {1: 'B'}})
        with patch.object(live_cpu, 'part3_grids_aligned', return_value=False), \
             patch.object(engine, 'preprocess', return_value=(self.gray, self.gray, self.gray)) as heavy:
            result = self.run_sheet(fast_mode=True, live_bubble_mode=True, live_validation=True,
                                    live_cpu_fast=True, live_answer_key_resolver=resolver)
        self.assertEqual(heavy.call_count, 1)
        self.assertEqual(result['preprocess_mode'], 'fast')
        self.assertEqual(result['part1'][1], 'B')
        resolver.assert_called_once()

    def test_upload_unvalidated_and_nonfast_live_stay_on_legacy(self):
        for options in (
            dict(fast_mode=True, live_bubble_mode=False, live_validation=True),
            dict(fast_mode=True, live_bubble_mode=True, live_validation=False),
            dict(fast_mode=False, live_bubble_mode=True, live_validation=True),
            dict(fast_mode=True, live_bubble_mode=True, live_validation=True, fast_background_trial=True),
        ):
            with self.subTest(options=options), \
                 patch.dict(os.environ, {'LIVE_CPU_FAST': '1'}), \
                 patch.object(engine, 'preprocess', return_value=(self.gray, self.gray, self.gray)) as heavy, \
                 patch.object(live_cpu, 'raw_gray', side_effect=AssertionError('Wrong route')):
                result = self.run_sheet(**options)
            self.assertGreaterEqual(heavy.call_count, 1)
            self.assertNotEqual(result['preprocess_mode'], 'live_raw')

    def test_environment_kill_switch_restores_original_preprocessing(self):
        with patch.dict(os.environ, {'LIVE_CPU_FAST': '0'}), \
             patch.object(engine, 'preprocess', return_value=(self.gray, self.gray, self.gray)) as heavy:
            result = self.run_sheet(fast_mode=True, live_bubble_mode=True, live_validation=True)
        self.assertEqual(heavy.call_count, 1)
        self.assertEqual(result['preprocess_mode'], 'fast')

    def test_only_part3_geometry_controls_seed_fallback(self):
        self.assertTrue(live_cpu.part3_grids_aligned({}))  # A template without Part III.
        self.assertTrue(live_cpu.part3_grids_aligned({1: {'live_grid': {'aligned': True}}}))
        self.assertFalse(live_cpu.part3_grids_aligned({1: {'live_grid': {'aligned': False}}}))
        self.assertFalse(live_cpu.part3_grids_aligned({1: {}}))

    def test_standalone_cli_can_load_without_repository_on_pythonpath(self):
        run = subprocess.run([sys.executable, '-X', 'utf8', str(ROOT / 'grading/engine/hi.py')],
                             cwd=self.folder, capture_output=True, encoding='utf-8', timeout=30)
        self.assertEqual(run.returncode, 0, run.stderr)
        self.assertIn('Cách dùng:', run.stdout)


class SerializationTests(unittest.TestCase):
    def test_grading_threads_cannot_mix_template_state(self):
        entered, release, second_started, second_entered = Event(), Event(), Event(), Event()
        state, observed = {}, []

        @serialized_grading
        def grade(template):
            state['template'] = template
            if template == 'A':
                entered.set()
                if not release.wait(3):
                    raise RuntimeError('Test timed out')
            else:
                second_entered.set()
            observed.append((template, state['template']))

        def second():
            second_started.set()
            grade('B')

        first, other = Thread(target=grade, args=('A',)), Thread(target=second)
        first.start()
        self.assertTrue(entered.wait(3))
        other.start()
        self.assertTrue(second_started.wait(3))
        try:
            self.assertFalse(second_entered.wait(.05))
        finally:
            release.set()
            first.join(3)
            other.join(3)
        self.assertEqual(observed, [('A', 'A'), ('B', 'B')])

    def test_lock_is_released_after_exception(self):
        @serialized_grading
        def grade(fail):
            if fail:
                raise ValueError('fail')
            return 'ok'
        with self.assertRaises(ValueError):
            grade(True)
        self.assertEqual(grade(False), 'ok')


if __name__ == '__main__':
    unittest.main()
