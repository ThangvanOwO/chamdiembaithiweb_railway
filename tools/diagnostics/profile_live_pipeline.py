"""Offline Live profiling; does not edit production code or access the database.

Use the original fixture with its measured corners, never result-overlay JPEGs.
All artifacts, including the engine's automatic ketqua copies, go to this run's
output directory. Monkey patches exist only in this standalone process.
"""
import argparse
from collections import defaultdict
from contextlib import ExitStack
import cProfile
import hashlib
import io
import json
import os
from pathlib import Path
import pstats
import shutil
import statistics
import sys
import time
from functools import wraps
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "chamdiemtudong.settings")
import django
django.setup()
from grading import grader
from grading.engine import live_bubble_reader as live_reader


class Timings:
    """Nested wrappers report exclusive times: categories do not double count."""
    def __init__(self):
        self.rows = defaultdict(lambda: {"calls": 0, "exclusive_ms": 0.0, "inclusive_ms": 0.0})
        self.stack = []

    def wrap(self, function, category):
        @wraps(function)
        def measured(*args, **kwargs):
            label = category(*args, **kwargs) if callable(category) else category
            frame = [time.perf_counter(), 0.0]
            self.stack.append(frame)
            try:
                return function(*args, **kwargs)
            finally:
                elapsed = time.perf_counter() - frame[0]
                self.stack.pop()
                row = self.rows[label]
                row["calls"] += 1
                row["inclusive_ms"] += elapsed * 1000
                row["exclusive_ms"] += (elapsed - frame[1]) * 1000
                if self.stack:
                    self.stack[-1][1] += elapsed
        return measured


def write_category(filename, *args, **kwargs):
    name = str(filename)
    if name.endswith(("_calibration.jpg", "_gray.jpg", "_thresh.jpg", "_cleaned.jpg")):
        return "debug_image_write"
    if name.endswith("_result.jpg"):
        return "result_image_write"
    if name.endswith("_overlay.jpg"):
        return "overlay_image_write"
    if name.endswith("_name.jpg"):
        return "name_image_write"
    return "other_image_write"


def normalized_reading(result):
    keys = ("sbd", "made", "part1", "part2", "part3", "detail_json",
            "detect_method", "offsets", "scan_quality", "avg_confidence",
            "preprocess_mode", "validation_warnings")
    return {key: result.get(key) for key in keys}


def run_once(output, name, source, fields, answer_key, debug, profile=False):
    folder = output / name
    folder.mkdir()
    image = folder / "input.jpg"
    shutil.copy2(source, image)
    timings = Timings()
    original_process = grader.engine.process_sheet
    original_copy = shutil.copy2

    def configured_process(*args, **kwargs):
        kwargs["debug"] = debug
        return original_process(*args, **kwargs)

    def relocated_copy(src, dst, *args, **kwargs):
        # Keep the actual disk-copy work, but isolate automatic ketqua artifacts.
        destination = Path(dst)
        if destination.parent.resolve() == (ROOT / "tests/ketqua").resolve():
            destination = folder / ("auto_" + destination.name)
        return original_copy(src, destination, *args, **kwargs)

    engine_functions = {
        "load_template": "template_load",
        "preprocess": "preprocessing",
        "_warp_to_rect": "marker_warp",
        "detect_paper_and_warp": "marker_warp",
        "detect_section_offsets": "grid_alignment",
        "detect_part3_offset_from_digits": "grid_alignment",
        "extract_sbd_made": "legacy_identifier_read",
        "extract_part1": "part1_read",
        "draw_bubble_grid": "debug_grid_draw",
        "grade_part1": "answer_comparison", "grade_part2": "answer_comparison",
        "grade_part3": "answer_comparison",
        "draw_results_part1": "result_draw", "draw_results_part2": "result_draw",
        "draw_results_part3": "result_draw",
        "_load_bubble_cnn": "cnn_load_or_check",
    }
    profiler = cProfile.Profile() if profile else None
    with ExitStack() as stack:
        stack.enter_context(patch.object(grader.engine, "process_sheet", configured_process))
        stack.enter_context(patch.object(shutil, "copy2", timings.wrap(relocated_copy, "artifact_copy")))
        for function, category in (engine_functions.items() if not profile else []):
            original = getattr(grader.engine, function)
            stack.enter_context(patch.object(grader.engine, function, timings.wrap(original, category)))
        live_functions = {"read_identifiers": "live_identifier_read", "read_part2": "part2_read",
                          "read_part3": "part3_read", "draw_part3": "result_draw"}
        for function, category in (live_functions.items() if not profile else []):
            stack.enter_context(patch.object(live_reader, function, timings.wrap(getattr(live_reader, function), category)))
        cv2 = grader.engine.cv2
        cv_functions = {"imread": "image_read", "imwrite": write_category,
                        "warpPerspective": "perspective_transform", "addWeighted": "image_blend",
                        "GaussianBlur": lambda src, ksize, sigmaX=0, *a, **kw: f"gaussian_sigma_{sigmaX}",
                        "fastNlMeansDenoising": "denoising"}
        for function, category in (cv_functions.items() if not profile else []):
            stack.enter_context(patch.object(cv2, function, timings.wrap(getattr(cv2, function), category)))
        started = time.perf_counter()
        if profiler:
            profiler.enable()
        try:
            result = grader.grade_image(str(image), answer_key, "40-08-06",
                corners=json.loads(fields["corners"]), fast_mode=True, live_bubble_mode=True)
        finally:
            if profiler:
                profiler.disable()
        elapsed = (time.perf_counter() - started) * 1000
    if not result.get("success"):
        raise RuntimeError(result.get("error"))
    (folder / "engine.log").write_text(result.get("debug_log", ""), encoding="utf-8")
    if profiler:
        profiler.dump_stats(str(folder / "pipeline.prof"))
        stream = io.StringIO()
        pstats.Stats(profiler, stream=stream).strip_dirs().sort_stats("cumulative").print_stats(45)
        (folder / "profile.txt").write_text(stream.getvalue(), encoding="utf-8")
    measured = sum(row["exclusive_ms"] for row in timings.rows.values())
    return result, {"name": name, "debug": debug, "profile_enabled": profile,
        "wall_ms": elapsed, "reported_processing_ms": result["processing_time"] * 1000,
        "stages": dict(timings.rows), "other_ms": elapsed - measured,
        "reading": normalized_reading(result), "scores": result["scores"]}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--pairs", type=int, default=3)
    args = parser.parse_args()
    if args.pairs < 1:
        parser.error("pairs must be positive")
    output = args.output.resolve()
    if not output.is_relative_to(ROOT) or output.exists():
        parser.error("output must be a NEW directory inside the workspace")
    output.mkdir(parents=True)
    source = ROOT / "tests/fixtures/exam_import_v1.jpg"
    fields = json.loads(source.with_suffix(".json").read_text(encoding="utf-8"))
    records = []
    cold, record = run_once(output, "cold_no_key", source, fields, "", True)
    records.append(record)
    # Controlled synthetic answer keys, not the teacher's actual answer key.
    key_a = {k: cold[k] for k in ("part1", "part2", "part3")}
    key_b = json.loads(json.dumps(key_a))
    key_b["part1"]["1"] = "D" if key_b["part1"].get("1") != "D" else "A"
    key_strings = [json.dumps(key_a), json.dumps(key_b)]
    for pair in range(args.pairs):
        for debug in ([True, False] if pair % 2 == 0 else [False, True]):
            result, record = run_once(output, f"pair{pair}_debug{int(debug)}", source, fields,
                                      key_strings[0], debug)
            records.append(record)
            assert normalized_reading(result) == normalized_reading(cold), "Debug/key changed recognition"
    changed, record = run_once(output, "key_b_full_rerun", source, fields, key_strings[1], True)
    records.append(record)
    assert normalized_reading(changed) == normalized_reading(cold), "Changing answer key changed recognition"
    scoring = []
    for _ in range(100):
        started = time.perf_counter()
        correct = grader.parse_answer_key(key_strings[1])
        scores = {part: getattr(grader.engine, f"grade_{part}")(cold[part], correct[part])[0]
                  for part in ("part1", "part2", "part3")}
        scoring.append((time.perf_counter() - started) * 1000)
        assert scores == changed["scores"], "Cached recognition rescoring disagrees with full pipeline"
    profiled, record = run_once(output, "cprofile_debug_on", source, fields, key_strings[0], True, profile=True)
    records.append(record)
    assert normalized_reading(profiled) == normalized_reading(cold)
    means = {}
    for debug in (True, False):
        group = [r for r in records if r["name"].startswith("pair") and r["debug"] == debug]
        means[str(debug)] = {"wall_ms": statistics.mean(r["wall_ms"] for r in group),
            "stages_exclusive_ms": {stage: statistics.mean(r["stages"].get(stage, {}).get("exclusive_ms", 0) for r in group)
                                    for stage in sorted(set().union(*(r["stages"] for r in group)))}}
    report = {"scope": "Offline Live replay, one original JPEG, supplied corners, fast=True, live=True; not the screenshot's real request, network, DB, mobile or p95 benchmark",
        "source_sha256": hashlib.sha256(source.read_bytes()).hexdigest(),
        "pairs": args.pairs, "means": means, "cached_comparison_mean_ms": statistics.mean(scoring),
        "recognition_and_rescore_parity": True, "records": records}
    (output / "report.json").write_text(json.dumps(report, indent=2, ensure_ascii=False), encoding="utf-8")
    print(json.dumps({"means": means, "cached_comparison_mean_ms": report["cached_comparison_mean_ms"],
                      "parity": True, "output": str(output)}, ensure_ascii=True, indent=2))


if __name__ == "__main__":
    main()
