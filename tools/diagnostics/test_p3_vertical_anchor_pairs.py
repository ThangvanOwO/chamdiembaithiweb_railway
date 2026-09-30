"""
PART III VERTICAL ANCHOR PAIRS & HORIZONTAL EDGE SKEW AUDIT
Visually detects and pairs the printed black square anchors at the TOP and BOTTOM
of Part III vertical column dividers across all active images in anh/.

DOES NOT MODIFY PRODUCTION ENGINE CODE (grading/engine/hi.py).
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

# 7 Expected X-coordinates for the 7 vertical dividers of Part III in 1400x1920
EXPECTED_DIVIDER_XS = [9.0, 231.0, 348.0, 466.0, 700.0, 933.0, 1167.0, 1390.0]

def detect_vertical_divider_anchors(warped):
    """
    Detects candidates in TOP region (y ~ 1300-1365) and BOTTOM region (y ~ 1880-1930).
    Pairs TOP and BOTTOM anchors by X proximity.
    """
    h, w = warped.shape[:2]
    gray = cv2.cvtColor(warped, cv2.COLOR_BGR2GRAY) if len(warped.shape) == 2 else cv2.cvtColor(warped, cv2.COLOR_BGR2GRAY)

    blur = cv2.GaussianBlur(gray, (3, 3), 0)
    _, thresh = cv2.threshold(blur, 120, 255, cv2.THRESH_BINARY_INV)

    # 1. TOP Candidates (y in [1300, 1365])
    roi_top = thresh[1300:1365, :]
    cnts_top, _ = cv2.findContours(roi_top, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    
    top_candidates = []
    for c in cnts_top:
        area = cv2.contourArea(c)
        x, y, bw, bh = cv2.boundingRect(c)
        aspect = bw / float(bh)
        solidity = area / float(max(1, bw * bh))
        abs_cx = x + bw / 2.0
        abs_cy = 1300 + y + bh / 2.0

        if 150 <= area <= 600 and 0.65 <= aspect <= 1.40 and solidity > 0.70:
            top_candidates.append({
                "center": (abs_cx, abs_cy),
                "bbox": (x, 1300 + y, bw, bh),
                "area": area,
                "aspect": round(aspect, 2),
                "solidity": round(solidity, 2)
            })
    top_candidates.sort(key=lambda a: a["center"][0])

    # 2. BOTTOM Candidates (y in [1880, 1930])
    roi_bot = thresh[1880:1930, :]
    cnts_bot, _ = cv2.findContours(roi_bot, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)

    bot_candidates = []
    for c in cnts_bot:
        area = cv2.contourArea(c)
        x, y, bw, bh = cv2.boundingRect(c)
        aspect = bw / float(bh)
        solidity = area / float(max(1, bw * bh))
        abs_cx = x + bw / 2.0
        abs_cy = 1880 + y + bh / 2.0

        if 120 <= area <= 600 and 0.65 <= aspect <= 2.6 and solidity > 0.70:
            bot_candidates.append({
                "center": (abs_cx, abs_cy),
                "bbox": (x, 1880 + y, bw, bh),
                "area": area,
                "aspect": round(aspect, 2),
                "solidity": round(solidity, 2)
            })
    bot_candidates.sort(key=lambda a: a["center"][0])

    # 3. Pairing TOP and BOTTOM by X proximity
    pairs = []
    used_bot = set()

    for tc in top_candidates:
        xt, yt = tc["center"]
        best_bot = None
        min_dx = 999.0

        for bi, bc in enumerate(bot_candidates):
            if bi in used_bot:
                continue
            xb, yb = bc["center"]
            dx = abs(xb - xt)
            dy = abs(yb - yt)

            # Valid pair must have dx <= 25px and dy in [550, 600]
            if dx <= 25.0 and 540.0 <= dy <= 600.0 and dx < min_dx:
                min_dx = dx
                best_bot = (bi, bc)

        if best_bot is not None:
            bi, bc = best_bot
            used_bot.add(bi)
            xb, yb = bc["center"]

            dx = xb - xt
            dy = yb - yt
            conf = 1.0 - (abs(dx) / 25.0)

            pairs.append({
                "top": tc,
                "bottom": bc,
                "xt": round(xt, 1),
                "yt": round(yt, 1),
                "xb": round(xb, 1),
                "yb": round(yb, 1),
                "dx": round(dx, 2),
                "dy": round(dy, 2),
                "confidence": round(conf, 2)
            })

    # Find missing expected anchors
    missing_expected = []
    for exp_x in [231.0, 348.0, 466.0, 700.0, 933.0, 1167.0]:
        found = any(abs(p["xt"] - exp_x) < 20 for p in pairs)
        if not found:
            missing_expected.append(exp_x)

    return top_candidates, bot_candidates, pairs, missing_expected

def calculate_edge_skews(pairs):
    """
    Calculates theta_top, theta_bottom, and theta_difference using horizontal line angles:
    theta_top = atan2(y_top_right - y_top_left, x_top_right - x_top_left)
    theta_bottom = atan2(y_bottom_right - y_bottom_left, x_bottom_right - x_bottom_left)
    """
    if len(pairs) < 2:
        return 0.0, 0.0, 0.0

    pairs_sorted = sorted(pairs, key=lambda p: p["xt"])
    p_left = pairs_sorted[0]
    p_right = pairs_sorted[-1]

    dx_top = p_right["xt"] - p_left["xt"]
    dy_top = p_right["yt"] - p_left["yt"]
    theta_top_rad = math.atan2(dy_top, dx_top)
    theta_top_deg = math.degrees(theta_top_rad)

    dx_bot = p_right["xb"] - p_left["xb"]
    dy_bot = p_right["yb"] - p_left["yb"]
    theta_bot_rad = math.atan2(dy_bot, dx_bot)
    theta_bot_deg = math.degrees(theta_bot_rad)

    theta_diff_deg = theta_bot_deg - theta_top_deg

    return round(theta_top_deg, 3), round(theta_bot_deg, 3), round(theta_diff_deg, 3)

def generate_visual_debug(warped, top_candidates, bot_candidates, pairs, missing_expected, out_filename):
    vis = warped.copy()
    if len(vis.shape) == 2:
        vis = cv2.cvtColor(vis, cv2.COLOR_GRAY2BGR)

    # 1. GREEN = Correctly detected anchors (TOP & BOTTOM)
    for p in pairs:
        cv2.circle(vis, (int(p["xt"]), int(p["yt"])), 7, (0, 255, 0), 2)
        cv2.circle(vis, (int(p["xb"]), int(p["yb"])), 7, (0, 255, 0), 2)

    # 2. YELLOW LINE = Accepted TOP/BOTTOM pair
    for p in pairs:
        pt1 = (int(p["xt"]), int(p["yt"]))
        pt2 = (int(p["xb"]), int(p["yb"]))
        cv2.line(vis, pt1, pt2, (0, 255, 255), 2)
        mid_x = int((p["xt"] + p["xb"]) / 2.0)
        mid_y = int((p["yt"] + p["yb"]) / 2.0)
        label = f"dx:{p['dx']:+.1f}px"
        cv2.putText(vis, label, (mid_x + 6, mid_y), cv2.FONT_HERSHEY_SIMPLEX, 0.45, (0, 255, 255), 1)

    # 3. RED = Missing expected anchors
    for mx in missing_expected:
        cv2.circle(vis, (int(mx), 1342), 9, (0, 0, 255), 2)
        cv2.line(vis, (int(mx) - 8, 1342), (int(mx) + 8, 1342), (0, 0, 255), 2)
        cv2.putText(vis, "MISSING", (int(mx) - 20, 1320), cv2.FONT_HERSHEY_SIMPLEX, 0.4, (0, 0, 255), 1)

    out_path = str(DEBUG_DIR / out_filename)
    cv2.imwrite(out_path, vis)
    print(f"  [DEBUG SAVED] {out_path}")

def run_suite():
    img_dir = str(REPO_ROOT / 'anh')
    images = sorted([
        os.path.join(img_dir, f) for f in os.listdir(img_dir)
        if f.lower().endswith('.jpg') and not any(s in f for s in ['_result', '_thresh', '_name', '_overlay', '_calibration', '_gray', '_cleaned', '_detect'])
    ])

    print("=" * 85)
    print("  PART III VERTICAL ANCHORS & HORIZONTAL SKEW AUDIT SUITE")
    print("=" * 85)

    report_data = []

    for path in images:
        name = os.path.basename(path)
        img = cv2.imread(path)
        if img is None:
            continue

        warped = hi.auto_deskew_and_crop(img, debug=False)["warped"]
        top_c, bot_c, pairs, missing = detect_vertical_divider_anchors(warped)
        theta_top, theta_bot, theta_diff = calculate_edge_skews(pairs)

        debug_name = f"p3_pairs_{os.path.splitext(name)[0]}.png"
        generate_visual_debug(warped, top_c, bot_c, pairs, missing, debug_name)

        x_shifts = [p["dx"] for p in pairs]
        avg_x_shift = round(float(np.mean(x_shifts)), 2) if x_shifts else 0.0
        max_x_shift = round(float(np.max(np.abs(x_shifts))), 2) if x_shifts else 0.0

        report_data.append({
            "name": name,
            "top_count": len(top_c),
            "bot_count": len(bot_c),
            "pairs_count": len(pairs),
            "missing_count": len(missing),
            "pairs": pairs,
            "theta_top": theta_top,
            "theta_bot": theta_bot,
            "theta_diff": theta_diff,
            "avg_x_shift": avg_x_shift,
            "max_x_shift": max_x_shift,
            "status": "100% DETECTED & PAIRED" if len(pairs) >= 6 else "PARTIAL DETECTION"
        })

    print("\n" + "=" * 85)
    print("  DETAILED PAIRING & SKEW REPORT")
    print("=" * 85)
    for r in report_data:
        print(f"\n▶ IMAGE: {r['name']} ({r['status']})")
        print(f"  • Top Anchors Found   : {r['top_count']}")
        print(f"  • Bottom Anchors Found: {r['bot_count']}")
        print(f"  • Paired Anchors      : {r['pairs_count']}")
        print(f"  • Missing Anchors     : {r['missing_count']}")
        print(f"  • Top Edge Angle      : {r['theta_top']:+.3f}°")
        print(f"  • Bottom Edge Angle   : {r['theta_bot']:+.3f}°")
        print(f"  • Skew Difference     : {r['theta_diff']:+.3f}°")
        print(f"  • Avg X Shift         : {r['avg_x_shift']:+.2f} px (Max: {r['max_x_shift']:.2f} px)")

        for i, p in enumerate(r['pairs'], 1):
            print(f"    Pair #{i}: TOP=({p['xt']}, {p['yt']}) -> BOT=({p['xb']}, {p['yb']}) | dx={p['dx']:+.1f}px, dy={p['dy']:.1f}px (conf={p['confidence']})")

    print("\n" + "=" * 85)
    print("  SUMMARY BENCHMARK TABLE")
    print("=" * 85)
    print(f"{'IMAGE':<10} | {'PAIRS':<7} | {'MISSING':<8} | {'THETA TOP':<10} | {'THETA BOT':<10} | {'THETA DIFF':<11} | {'MAX DX':<8} | {'STATUS'}")
    print("-" * 85)
    for r in report_data:
        print(f"{r['name']:<10} | {r['pairs_count']:<7d} | {r['missing_count']:<8d} | {r['theta_top']:>+9.3f}° | {r['theta_bot']:>+9.3f}° | {r['theta_diff']:>+10.3f}° | {r['max_x_shift']:>6.1f}px | {r['status']}")
    print("=" * 85 + "\n")

if __name__ == "__main__":
    run_suite()
