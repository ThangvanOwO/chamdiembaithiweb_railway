"""
COMPREHENSIVE TEST FOR NEW IMAGES: 7.jpg, 8.jpg, 9.jpg
1. Runs OMR engine process_sheet() on 7.jpg, 8.jpg, 9.jpg.
2. Runs Part III vertical anchor pairing audit.
3. Saves visual debug images to tmp/part3_debug/.

DOES NOT MODIFY PRODUCTION OMR CODE (grading/engine/hi.py).
"""
import os
import sys
import math
import cv2
import numpy as np
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
ENGINE_DIR = REPO_ROOT / 'grading' / 'engine'
sys.path.insert(0, str(ENGINE_DIR))

import hi

hi.load_template(str(ENGINE_DIR / 'templates' / 'template_default.json'))

DEBUG_DIR = REPO_ROOT / 'tmp' / 'part3_debug'
DEBUG_DIR.mkdir(parents=True, exist_ok=True)

NEW_IMAGES = ['anh/7.jpg', 'anh/8.jpg', 'anh/9.jpg']

def run_tests():
    print("=" * 85)
    print("  GRADEFLOW — OMR & PART III ANCHOR TEST FOR IMAGES 7.jpg, 8.jpg, 9.jpg")
    print("=" * 85)

    from test_p3_vertical_anchor_pairs import detect_vertical_divider_anchors, calculate_edge_skews, generate_visual_debug

    omr_results = []
    anchor_results = []

    for rel in NEW_IMAGES:
        img_path = str(REPO_ROOT / rel)
        name = os.path.basename(img_path)

        if not os.path.exists(img_path):
            print(f"[ERR] File not found: {img_path}")
            continue

        print(f"\n" + "=" * 60)
        print(f"  TESTING: {name}")
        print("=" * 60)

        # 1. OMR Processing
        res = hi.process_sheet(img_path, debug=False)
        if res:
            sbd = res.get("sbd", "N/A")
            made = res.get("made", "N/A")
            conf = res.get("avg_confidence", 0.0)
            method = res.get("detect_method", "N/A")
            p1_ans = res.get("part1", {})
            p2_ans = res.get("part2", {})
            p3_ans = res.get("part3", {})

            omr_results.append({
                "name": name,
                "sbd": sbd,
                "made": made,
                "conf": round(conf, 3),
                "method": method,
                "p1_count": len([k for k, v in p1_ans.items() if v and v != 'X']),
                "p2_count": len([k for k, v in p2_ans.items() if any(v.values())]),
                "p3_answers": p3_ans
            })

            print(f"  [OMR] SBD: {sbd} | MĐ: {made} | Conf: {conf:.2f} | Method: {method}")
            print(f"  [OMR] Part III Answers: {p3_ans}")

        # 2. Anchor Pairing Audit
        img = cv2.imread(img_path)
        res_warp = hi.auto_deskew_and_crop(img, debug=False)
        warped = res_warp["warped"]

        top_c, bot_c, pairs, missing = detect_vertical_divider_anchors(warped)
        theta_top, theta_bot, theta_diff = calculate_edge_skews(pairs)

        debug_name = f"p3_pairs_{os.path.splitext(name)[0]}.png"
        generate_visual_debug(warped, top_c, bot_c, pairs, missing, debug_name)

        x_shifts = [p["dx"] for p in pairs]
        avg_dx = round(float(np.mean(x_shifts)), 2) if x_shifts else 0.0
        max_dx = round(float(np.max(np.abs(x_shifts))), 2) if x_shifts else 0.0

        anchor_results.append({
            "name": name,
            "top_cnt": len(top_c),
            "bot_cnt": len(bot_c),
            "pairs_cnt": len(pairs),
            "missing_cnt": len(missing),
            "theta_top": theta_top,
            "theta_bot": theta_bot,
            "theta_diff": theta_diff,
            "avg_dx": avg_dx,
            "max_dx": max_dx,
            "pairs": pairs
        })

        print(f"  [ANCHOR] Top: {len(top_c)} | Bot: {len(bot_c)} | Pairs: {len(pairs)} | Missing: {len(missing)}")
        print(f"  [ANCHOR] Edge Skew: Top={theta_top:+.3f}°, Bot={theta_bot:+.3f}°, Diff={theta_diff:+.3f}°")
        print(f"  [ANCHOR] Max X Shift: {max_dx:.1f}px")

    print("\n" + "=" * 85)
    print("  SUMMARY OMR & ANCHOR BENCHMARK")
    print("=" * 85)
    print(f"{'IMAGE':<8} | {'SBD':<8} | {'MADE':<6} | {'CONF':<6} | {'METHOD':<15} | {'PAIRS':<6} | {'THETA TOP':<10} | {'THETA BOT':<10} | {'MAX DX'}")
    print("-" * 85)
    for o, a in zip(omr_results, anchor_results):
        print(f"{o['name']:<8} | {o['sbd']:<8} | {o['made']:<6} | {o['conf']:<6.2f} | {o['method']:<15} | {a['pairs_cnt']:<6d} | {a['theta_top']:>+9.3f}° | {a['theta_bot']:>+9.3f}° | {a['max_dx']:>6.1f}px")
    print("=" * 85 + "\n")

if __name__ == "__main__":
    run_tests()
