"""Instrumentation checks; never run the OMR engine or access the database."""
import unittest
from unittest.mock import patch
from tools.diagnostics.profile_live_pipeline import Timings, write_category


class LiveProfilerTests(unittest.TestCase):
    def test_nested_times_do_not_double_count(self):
        timer = Timings()
        child = timer.wrap(lambda: "reading", "child")
        parent = timer.wrap(lambda: child(), "parent")
        with patch("tools.diagnostics.profile_live_pipeline.time.perf_counter", side_effect=[0, 1, 3, 5]):
            self.assertEqual(parent(), "reading")
        self.assertEqual(timer.rows["parent"]["inclusive_ms"], 5000)
        self.assertEqual(timer.rows["parent"]["exclusive_ms"], 3000)
        self.assertEqual(timer.rows["child"]["exclusive_ms"], 2000)
        self.assertEqual(timer.stack, [])

    def test_exception_propagates_and_stack_is_restored(self):
        timer = Timings()
        def fail():
            raise ValueError("unchanged failure")
        with self.assertRaisesRegex(ValueError, "unchanged failure"):
            timer.wrap(fail, "failed")()
        self.assertEqual(timer.rows["failed"]["calls"], 1)
        self.assertEqual(timer.stack, [])

    def test_debug_images_are_distinguished_from_required_outputs(self):
        for suffix in ("calibration", "gray", "thresh", "cleaned"):
            self.assertEqual(write_category(f"input_{suffix}.jpg"), "debug_image_write")
        for suffix in ("result", "overlay", "name"):
            self.assertEqual(write_category(f"input_{suffix}.jpg"), f"{suffix}_image_write")


if __name__ == "__main__":
    unittest.main()
