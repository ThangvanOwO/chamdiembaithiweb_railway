"""Sequential local grade_image latency, with real recognition and disk outputs.

No database/network requests. Only automatic result-copy destinations are
redirected into the report folder; production processing options stay intact.
"""
import argparse
from datetime import datetime
import hashlib
import json
import os
from pathlib import Path
import platform
import random
import shutil
import statistics
import sys
import time
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "chamdiemtudong.settings")
import django
django.setup()
from grading import grader
from grading.live_latency import LiveAnswerKeySelection
import cv2
import numpy as np


def summarize(rows):
    values = [r["wall_ms"] for r in rows]
    return {"count": len(rows), "success_count": sum(r["success"] for r in rows),
            "mean_ms": statistics.mean(values), "median_ms": statistics.median(values),
            "p95_ms": float(np.percentile(values, 95)), "min_ms": min(values),
            "max_ms": max(values)}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--repeats", type=int, default=5)
    parser.add_argument("--live-repeats", type=int, default=20)
    args = parser.parse_args()
    output = args.output.resolve()
    if output.exists() or not output.is_relative_to(ROOT) or min(args.repeats, args.live_repeats) < 1:
        parser.error("Use a NEW output directory inside the workspace and positive repeat counts")
    output.mkdir(parents=True)
    key = json.dumps({"part1": {str(i): "ABCD"[(i-1) % 4] for i in range(1, 41)},
                      "part2": {str(i): {"a": "Dung", "b": "Sai", "c": "Dung", "d": "Sai"} for i in range(1, 9)},
                      "part3": {str(i): "1" for i in range(1, 7)}})
    cases = []
    for mode, fast in (("upload_full", False), ("upload_fast", True)):
        for name in ("1", "2", "3", "4", "9", "1111", "1233332", "test"):
            cases.append({"id": f"{mode}_{name}", "mode": mode, "source": ROOT / f"anh/{name}.jpg",
                          "options": {"fast_mode": fast}, "repeats": args.repeats})
    fixture = ROOT / "tests/fixtures/exam_import_v1.jpg"
    fields = json.loads(fixture.with_suffix(".json").read_text(encoding="utf-8"))
    cases.append({"id": "live_fixture", "mode": "live_validated", "source": fixture,
                  "options": {"fast_mode": True, "live_bubble_mode": True,
                              "live_validation": True, "corners": json.loads(fields["corners"])},
                  "repeats": args.live_repeats})
    for case in cases:
        folder = output / case["id"]
        folder.mkdir()
        case["input"] = folder / "input.jpg"
        shutil.copy2(case["source"], case["input"])
        im = cv2.imread(str(case["input"]))
        case["dimensions"] = [int(im.shape[1]), int(im.shape[0])]
        case["sha256"] = hashlib.sha256(case["source"].read_bytes()).hexdigest()

    original_copy = shutil.copy2
    active_folder = output
    def redirect_copy(src, dst, *a, **kw):
        if Path(dst).parent.resolve() == (ROOT / "tests/ketqua").resolve():
            dst = active_folder / ("auto_overlay.jpg" if str(dst).endswith("_overlay.jpg") else "auto_result.jpg")
        return original_copy(src, dst, *a, **kw)

    records, baselines = [], {}
    def run(case, phase, iteration):
        nonlocal active_folder
        active_folder = case["input"].parent
        options = dict(case["options"])
        if options.get("live_bubble_mode"):
            selection = LiveAnswerKeySelection(key, [("001", key)], grader.parse_answer_key, strict=True, choose_early=True)
            options["live_answer_key_resolver"] = selection.resolve
        start = time.perf_counter_ns()
        result = grader.grade_image(str(case["input"]), key, "40-08-06", **options)
        elapsed = (time.perf_counter_ns() - start) / 1e6
        reading = {k: result.get(k) for k in ("sbd", "made", "part1", "part2", "part3")}
        digest = hashlib.sha256(json.dumps(reading, sort_keys=True).encode()).hexdigest()
        baselines.setdefault(case["id"], digest)
        detail = json.loads(result.get("detail_json") or "{}")
        record = {"case": case["id"], "mode": case["mode"], "phase": phase, "iteration": iteration,
                  "wall_ms": elapsed, "reported_processing_ms": result.get("processing_time", 0) * 1000,
                  "success": result.get("success", False), "error": result.get("error", ""),
                  "reading_stable": digest == baselines[case["id"]], "reading": reading,
                  "scan_quality": result.get("scan_quality"), "warnings": result.get("validation_warnings", []),
                  "cnn_status": detail.get("cnn_status"), "detect_method": result.get("detect_method")}
        records.append(record)
        (active_folder / "engine.log").write_text(result.get("debug_log", ""), encoding="utf-8")
        with (output / "samples.jsonl").open("a", encoding="utf-8") as f:
            f.write(json.dumps(record, ensure_ascii=False) + "\n")
        print(f"{phase} {case['id']} #{iteration}: {elapsed:.1f} ms success={record['success']}", flush=True)

    with patch.object(shutil, "copy2", redirect_copy):
        run(cases[0], "cold_first_call", 0)
        for case in cases:
            run(case, "warmup", 0)
        schedule = [(case, i + 1) for case in cases for i in range(case["repeats"])]
        random.Random(20260924).shuffle(schedule)
        for case, iteration in schedule:
            run(case, "measured", iteration)

    measured = [r for r in records if r["phase"] == "measured"]
    report = {"created_at": datetime.now().astimezone().isoformat(),
              "scope": "Local sequential grade_image, real recognition/scoring/debug/result writes; excludes imports, HTTP, network, database and API variant reruns. Synthetic scoring key; not an accuracy benchmark.",
              "environment": {"python": sys.version, "platform": platform.platform(), "django": django.get_version(),
                              "opencv": cv2.__version__, "numpy": np.__version__, "opencv_threads": cv2.getNumThreads(),
                              "cnn_backend": grader.engine._CNN_DEVICE, "cnn_ready": grader.engine._CNN_READY},
              "method": {"clock": "perf_counter_ns", "p95": "numpy.percentile linear interpolation", "seed": 20260924,
                         "debug": True, "concurrency": 1, "synthetic_answer_key": key},
              "summaries": {mode: summarize([r for r in measured if r["mode"] == mode]) for mode in sorted({r["mode"] for r in measured})},
              "cases": [{**{k: v for k, v in c.items() if k not in ("source", "input")}, "source": str(c["source"].relative_to(ROOT)),
                         "summary": summarize([r for r in measured if r["case"] == c["id"]])} for c in cases],
              "stable_readings": all(r["reading_stable"] for r in measured), "records": records}
    (output / "report.json").write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps({"summary": report["summaries"], "stable_readings": report["stable_readings"], "output": str(output)}, indent=2))


if __name__ == "__main__":
    main()
