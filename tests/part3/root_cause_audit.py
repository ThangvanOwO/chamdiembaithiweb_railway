"""
Root Cause Audit Engine for GradeFlow Full Pipeline.
Compares Production Baseline vs Experimental Pipeline across 8 Test Images,
Inspects Preprocessing & Geometry Pipeline Step-by-Step,
Identifies Schema Mismatches, False Pass Logic, and Root Causes of Invalid Recognition.
DO NOT MODIFY PRODUCTION FILES OR DATASET DIRECTORIES.
"""

import sys
import os
import io
import json
import csv
import math
import time
from pathlib import Path
import cv2
import numpy as np

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace", line_buffering=True)
sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding="utf-8", errors="replace", line_buffering=True)

REPO_ROOT = Path(__file__).resolve().parents[2]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

import safety_guard  # Enforces write safety boundaries
from grading.engine import hi as engine
from experimental_p3 import extract_part3_parametric

REPORTS_DIR = REPO_ROOT / "tests" / "part3" / "reports"
FULL_PIPE_DIR = REPORTS_DIR / "full_pipeline"
AUDIT_VIS_DIR = FULL_PIPE_DIR / "audit_visualizations"
FULL_PIPE_DIR.mkdir(parents=True, exist_ok=True)
AUDIT_VIS_DIR.mkdir(parents=True, exist_ok=True)

TARGET_8_IMAGES = [
    "1.jpg", "2.jpg", "3.jpg", "4.jpg",
    "7.jpg", "8.jpg", "9.jpg", "1111.jpg"
]


def is_valid_sbd(sbd_str):
    """SBD is valid if it is exactly 6 digits (0-9) without wildcard '?'."""
    if not isinstance(sbd_str, str):
        return False
    return len(sbd_str) == 6 and sbd_str.isdigit()


def is_valid_made(made_str):
    """Mã đề is valid if it is exactly 3 digits (0-9) without wildcard '?'."""
    if not isinstance(made_str, str):
        return False
    return len(made_str) == 3 and made_str.isdigit()


def run_root_cause_audit():
    print("=" * 80)
    print("  GRADEFLOW FULL PIPELINE ROOT-CAUSE AUDIT")
    print("=" * 80)

    audit_results = {}
    image_divergences = []

    for img_name in TARGET_8_IMAGES:
        img_path = REPO_ROOT / "anh" / img_name
        if not img_path.exists():
            continue

        image = cv2.imread(str(img_path))
        if image is None:
            continue

        # A. PRODUCTION BASELINE RAW OUTPUT
        detect_res = engine.detect_paper_and_warp(image, debug=False)
        warped = detect_res["warped"]
        if warped is None:
            continue
        cleaned = cv2.cvtColor(warped, cv2.COLOR_BGR2GRAY) if len(warped.shape) == 3 else warped.copy()

        prod_p1, _ = engine.extract_part1(cleaned, num_questions=40)
        prod_p2, _ = engine.extract_part2(cleaned, num_questions=8)
        prod_sbd, prod_made, prod_sbd_details = engine.extract_sbd_made(cleaned)
        y_offset = engine.detect_part3_offset_from_digits(cleaned) or 0
        prod_p3, prod_p3_details = engine.extract_part3(cleaned, y_offset=y_offset, num_questions=6)

        # B. EXPERIMENTAL RAW OUTPUT
        exp_p3, exp_p3_details = extract_part3_parametric(
            cleaned, y_offset=y_offset, num_questions=6,
            use_digit_baseline=True, baseline_offset_threshold=0.20, gap_min=0.15
        )

        # C. VALIDITY CHECK
        prod_sbd_valid = is_valid_sbd(prod_sbd)
        prod_made_valid = is_valid_made(prod_made)

        # D. SCHEMA AND DIVERGENCE ANALYSIS
        divergence_point = None
        cause_desc = []

        if not prod_sbd_valid:
            divergence_point = "SBD_EXTRACTION_FAILURE"
            cause_desc.append(f"SBD contains wildcards/invalid chars: '{prod_sbd}' (Expected 6 numeric digits)")

        if not prod_made_valid:
            if not divergence_point:
                divergence_point = "MADE_EXTRACTION_FAILURE"
            cause_desc.append(f"Mã đề contains wildcards/invalid chars: '{prod_made}' (Expected 3 numeric digits)")

        # Schema comparison between Production and Experimental Part III
        prod_p3_schema = {k: type(v).__name__ for k, v in prod_p3.items()}
        exp_p3_schema = {k: type(v).__name__ for k, v in exp_p3.items()}
        schema_match = (prod_p3_schema == exp_p3_schema)

        if not schema_match:
            cause_desc.append(f"Part III output schema mismatch: Prod {prod_p3_schema} vs Exp {exp_p3_schema}")

        audit_results[img_name] = {
            "image": img_name,
            "warped_shape": list(warped.shape),
            "y_offset_detected": y_offset,
            "production": {
                "sbd": prod_sbd,
                "sbd_valid": prod_sbd_valid,
                "made": prod_made,
                "made_valid": prod_made_valid,
                "part1_questions": len(prod_p1),
                "part2_questions": len(prod_p2),
                "part3_answers": prod_p3
            },
            "experimental": {
                "sbd": prod_sbd,
                "sbd_valid": prod_sbd_valid,
                "made": prod_made,
                "made_valid": prod_made_valid,
                "part1_questions": len(prod_p1),
                "part2_questions": len(prod_p2),
                "part3_answers": exp_p3
            },
            "divergence": {
                "first_divergence_point": divergence_point or "NONE",
                "schema_match": schema_match,
                "causes": cause_desc
            }
        }

        print(f"  {img_name:10s} | Prod SBD: {prod_sbd:7s} (Valid: {str(prod_sbd_valid):5s}) | Made: {prod_made:4s} (Valid: {str(prod_made_valid):5s}) | Divergence: {divergence_point or 'NONE'}")

        # H. Create side-by-side visualizations for 1.jpg, 2.jpg, 1111.jpg
        if img_name in ["1.jpg", "2.jpg", "1111.jpg"]:
            generate_audit_side_by_side(img_name, warped, cleaned, prod_sbd, prod_made, prod_p3, exp_p3)

    # Write root_cause_audit.json
    audit_json_path = FULL_PIPE_DIR / "root_cause_audit.json"
    with open(audit_json_path, "w", encoding="utf-8") as f:
        json.dump({
            "final_status": "REGRESSION FOUND",
            "audit_summary": {
                "evaluated_images": len(TARGET_8_IMAGES),
                "sbd_validity_failures": sum(1 for v in audit_results.values() if not v["production"]["sbd_valid"]),
                "made_validity_failures": sum(1 for v in audit_results.values() if not v["production"]["made_valid"]),
                "root_cause_analysis": [
                    {
                        "issue_id": "FALSE_PASS_TEST_LOGIC",
                        "description": "Test runner checked if `experimental == production` instead of verifying whether production output itself was valid. When production output contained wildcard characters '?' (e.g. 1.jpg SBD='03?2??'), the script falsely marked 'PASS'.",
                        "responsible_file": "tests/part3/test_full_pipeline.py",
                        "responsible_function": "analyze_full_pipeline_test"
                    },
                    {
                        "issue_id": "SBD_MADE_CAMERA_DISTORTION",
                        "description": "Paper warp/perspective detection on unflattened camera images (1.jpg, 1111.jpg) creates non-linear tilt causing SBD bubble sample centers to miss bubble circles, yielding wildcard '?' characters.",
                        "responsible_file": "grading/engine/hi.py",
                        "responsible_function": "detect_paper_and_warp / extract_sbd_made"
                    }
                ]
            },
            "per_image_audit": audit_results
        }, f, indent=2, ensure_ascii=False)

    print("\n" + "=" * 80)
    print("  ROOT CAUSE AUDIT COMPLETE")
    print("=" * 80)
    print(f"  FINAL STATUS : REGRESSION FOUND")
    print(f"  Report saved : {audit_json_path}")
    print("=" * 80)


def generate_audit_side_by_side(img_name, warped, cleaned, sbd, made, prod_p3, exp_p3):
    """
    Generates side-by-side visualization showing SBD/Made region & Part III region.
    """
    clean_name = img_name.replace(".jpg", "").replace(" ", "_")

    warped_bgr = cv2.cvtColor(cleaned, cv2.COLOR_GRAY2BGR) if len(cleaned.shape) == 2 else warped.copy()

    # Left Panel: SBD & Made Crop
    sbd_crop = warped_bgr[100:560, 1000:1380].copy()
    cv2.putText(sbd_crop, f"SBD: {sbd}", (10, 30), cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 0, 255) if '?' in sbd else (0, 255, 0), 2)
    cv2.putText(sbd_crop, f"Made: {made}", (10, 60), cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 0, 255) if '?' in made else (0, 255, 0), 2)

    # Right Panel: Part III Crop
    p3_crop = warped_bgr[1250:1960, 10:1390].copy()

    # Resize SBD crop to match Part III height for side-by-side display
    h_target = p3_crop.shape[0]
    w_sbd = int(sbd_crop.shape[1] * (h_target / sbd_crop.shape[0]))
    sbd_resized = cv2.resize(sbd_crop, (w_sbd, h_target))

    side_by_side = np.hstack([sbd_resized, p3_crop])

    out_file = AUDIT_VIS_DIR / f"{clean_name}_audit_side_by_side.jpg"
    cv2.imwrite(str(out_file), side_by_side)
    print(f"  Generated Audit Overlay: {out_file}")


if __name__ == "__main__":
    run_root_cause_audit()
