import cv2
import os
import sys
import json
from pathlib import Path

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT / "grading" / "engine"))

from chamtn_core import Template, ChamTNEngine, ScoringEngine

def test_all():
    image_files = [
        "1.jpg",
        "2.jpg",
        "3.jpg",
        "4.jpg",
        "9.jpg",
        "1111.jpg",
        "1233332.jpg",
        "test.jpg",
    ]

    tpl = Template.load_json(str(REPO_ROOT / "grading" / "templates_data" / "qm2025_40_08_06.json"))
    engine = ChamTNEngine(tpl)

    print("=" * 105)
    print(f"{'FILE':<14} | {'SBD':<8} | {'MÃ ĐỀ':<6} | {'P.I (ĐÃ LÀM)':<14} | {'P.II':<10} | {'P.III ĐIỀN SỐ':<24} | {'GRID SC':<8} | {'STATUS'}")
    print("=" * 105)

    results = []

    for name in image_files:
        img_path = str(REPO_ROOT / "anh" / name)
        if not os.path.exists(img_path):
            continue

        img = cv2.imread(img_path)
        if img is None:
            print(f"{name:<14} | ERROR READING IMAGE")
            continue

        # 1. Warp bằng ChamTN Tournament
        detect_res = engine.detect_and_warp(img)
        warped = detect_res["warped"]
        grid_sc = detect_res.get("grid_score", 0.0)

        # 2. Bóc tách bằng ChamTN Sampler
        ans = engine.extract_answers(warped)

        sbd = ans["sbd"]
        made = ans["made"]

        # Part 1 count
        p1_done = sum(1 for q in range(1, 41) if ans["part1"].get(q, ""))
        p1_str = f"{p1_done}/40 câu"

        # Part 2 count
        p2_done = sum(1 for q in range(1, 9) if any(v in ["D", "S"] for v in ans["part2"].get(q, {}).values()))
        p2_str = f"{p2_done}/8 câu"

        # Part 3 text
        p3_vals = [ans["part3"].get(q, "") for q in range(1, 7)]
        p3_non_empty = [v for v in p3_vals if v]
        p3_str = ", ".join(p3_non_empty) if p3_non_empty else "(bỏ trống)"

        status = "✓ PASS" if (sbd and made and (p1_done > 0 or p3_non_empty)) else "CHECK"

        print(f"{name:<14} | {sbd:<8} | {made:<6} | {p1_str:<14} | {p2_str:<10} | {p3_str:<24} | {grid_sc:<8.2f} | {status}")
        results.append({
            "name": name,
            "sbd": sbd,
            "made": made,
            "p1_done": p1_done,
            "p1": ans["part1"],
            "p2_done": p2_done,
            "p2": ans["part2"],
            "p3": ans["part3"],
            "grid_sc": grid_sc,
            "method": detect_res.get("method"),
            "separation": ans["quality"]["separation"]
        })

    print("=" * 105)
    return results

if __name__ == "__main__":
    test_all()
