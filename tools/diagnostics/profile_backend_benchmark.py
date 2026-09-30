"""Profile three representative calls AFTER benchmark_backend_images completes."""
import argparse
from contextlib import ExitStack
import json
from pathlib import Path
import shutil
import sys
import time
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
from tools.diagnostics.profile_live_pipeline import Timings, write_category
from grading import grader
from grading.engine import live_bubble_reader
from grading.live_latency import LiveAnswerKeySelection


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("report", type=Path)
    args = parser.parse_args()
    report = json.loads(args.report.read_text(encoding="utf-8"))
    output = args.report.parent / "stages"
    output.mkdir(exist_ok=False)
    original_copy = shutil.copy2
    selected = [c for c in report["cases"] if c["id"] in ("upload_full_1", "upload_fast_1", "live_fixture")]
    key = report["method"]["synthetic_answer_key"]
    records = []
    for case in selected:
        folder = output / case["id"]
        folder.mkdir()
        image = folder / "input.jpg"
        original_copy(ROOT / case["source"], image)
        def redirect(src, dst, *a, **kw):
            if Path(dst).parent.resolve() == (ROOT / "tests/ketqua").resolve():
                dst = folder / ("auto_overlay.jpg" if str(dst).endswith("_overlay.jpg") else "auto_result.jpg")
            return original_copy(src, dst, *a, **kw)
        options = dict(case["options"])
        if options.get("live_bubble_mode"):
            selector = LiveAnswerKeySelection(key, [("001", key)], grader.parse_answer_key, strict=True, choose_early=True)
            options["live_answer_key_resolver"] = selector.resolve
        with patch.object(shutil, "copy2", redirect):
            grader.grade_image(str(image), key, "40-08-06", **options)
        timer = Timings()
        with ExitStack() as stack:
            stack.enter_context(patch.object(shutil, "copy2", timer.wrap(redirect, "artifact_copy")))
            engine_names = {"preprocess": "preprocessing", "detect_paper_and_warp": "marker_detection",
                            "detect_section_offsets": "alignment", "detect_part3_offset_from_digits": "alignment",
                            "extract_sbd_made": "legacy_ids", "extract_part1": "legacy_part1",
                            "extract_part2": "legacy_part2", "extract_part3": "legacy_part3",
                            "draw_bubble_grid": "debug_draw", "load_template": "template",
                            "grade_part1": "scoring", "grade_part2": "scoring", "grade_part3": "scoring"}
            for name, label in engine_names.items():
                stack.enter_context(patch.object(grader.engine, name, timer.wrap(getattr(grader.engine, name), label)))
            for name in ("read_identifiers", "read_part1", "read_part2", "read_part3"):
                stack.enter_context(patch.object(live_bubble_reader, name, timer.wrap(getattr(live_bubble_reader, name), "live_" + name)))
            cvnames = {"imread": "image_decode", "imwrite": write_category, "warpPerspective": "perspective_transform",
                       "fastNlMeansDenoising": "denoising",
                       "GaussianBlur": lambda src, ksize, sigmaX=0, *a, **kw: f"gaussian_sigma_{sigmaX}"}
            for name, label in cvnames.items():
                stack.enter_context(patch.object(grader.engine.cv2, name, timer.wrap(getattr(grader.engine.cv2, name), label)))
            started = time.perf_counter_ns()
            result = grader.grade_image(str(image), key, "40-08-06", **options)
            elapsed = (time.perf_counter_ns() - started) / 1e6
        row = {"case": case["id"], "wall_ms": elapsed, "success": result["success"], "stages": dict(timer.rows),
               "other_ms": elapsed - sum(r["exclusive_ms"] for r in timer.rows.values())}
        records.append(row)
        print(json.dumps(row), flush=True)
    (output / "report.json").write_text(json.dumps(records, indent=2), encoding="utf-8")


if __name__ == "__main__":
    main()
