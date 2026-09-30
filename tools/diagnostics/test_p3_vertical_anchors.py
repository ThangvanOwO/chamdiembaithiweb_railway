"""
PART III VERTICAL DIVIDER ANCHOR DETECTOR & DIAGNOSTIC TEST
Detects black square anchors located at the TOP (y ~ 1342px) and BOTTOM (y ~ 1910px)
of each vertical divider in Part III.

DOES NOT MODIFY PRODUCTION OMR ENGINE CODE (grading/engine/hi.py).
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

# Output directory for visual debug images
DEBUG_DIR = REPO_ROOT / 'tmp' / 'part3_debug'
DEBUG_DIR.mkdir(parents=True, exist_ok=True)

def detect_part3_vertical_anchors(warped):
    """
    Detects top and bottom black square anchors belonging to Part III vertical dividers.
    """
    h, w = warped.shape[:2]
    gray = cv2.cvtColor(warped, cv2.COLOR_BGR2GRAY) if len(warped.shape) == 3 else warped.copy()

    # Threshold dark pixels
    blur = cv2.GaussianBlur(gray, (3, 3), 0)
    _, thresh = cv2.threshold(blur, 110, 255, cv2.THRESH_BINARY_INV)

    # 1. TOP ANCHOR REGION: y in [1320, 1365]
    roi_top = thresh[1320:1365, :]
    cnts_top, _ = cv2.findContours(roi_top, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)

    top_candidates = []
    rejected_top = []

    for c in cnts_top:
        area = cv2.contourArea(c)
        x, y, bw, bh = cv2.boundingRect(c)
        aspect = bw / float(bh)
        solidity = area / float(max(1, bw * bh))
        abs_cx = x + bw / 2.0
        abs_cy = 1320 + y + bh / 2.0

        if 200 <= area <= 600 and 0.70 <= aspect <= 1.35 and solidity > 0.75:
            top_candidates.append({
                "center": (abs_cx, abs_cy),
                "bbox": (x, 1320 + y, bw, bh),
                "area": area,
                "aspect": round(aspect, 2),
                "solidity": round(solidity, 2)
            })
        else:
            rejected_top.append((abs_cx, abs_cy, bw, bh))

    top_candidates.sort(key=lambda a: a["center"][0])

    # 2. BOTTOM ANCHOR REGION: y in [1890, 1930]
    roi_bot = thresh[1890:1930, :]
    cnts_bot, _ = cv2.findContours(roi_bot, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)

    bot_candidates = []
    rejected_bot = []

    for c in cnts_bot:
        area = cv2.contourArea(c)
        x, y, bw, bh = cv2.boundingRect(c)
        aspect = bw / float(bh)
        solidity = area / float(max(1, bw * bh))
        abs_cx = x + bw / 2.0
        abs_cy = 1890 + y + bh / 2.0

        # Bottom anchors can be square or horizontal timing bars (w/h up to 2.5)
        if 120 <= area <= 500 and 0.65 <= aspect <= 2.6 and solidity > 0.75:
            bot_candidates.append({
                "center": (abs_cx, abs_cy),
                "bbox": (x, 1890 + y, bw, bh),
                "area": area,
                "aspect": round(aspect, 2),
                "solidity": round(solidity, 2)
            })
        else:
            rejected_bot.append((abs_cx, abs_cy, bw, bh))

    bot_candidates.sort(key=lambda a: a["center"][0])

    # 3. PAIRING TOP & BOTTOM ANCHORS BY X PROXIMITY (|xt - xb| <= 35px)
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
            if dx <= 35.0 and dx < min_dx:
                min_dx = dx
                best_bot = (bi, bc)

        if best_bot is not None:
            bi, bc = best_bot
            used_bot.add(bi)
            xb, yb = bc["center"]

            dx = xb - xt
            dy = yb - yt
            # Angle of vertical divider inclination theta = atan2(dx, dy)
            theta_rad = math.atan2(dx, dy)
            theta_deg = math.degrees(theta_rad)

            pairs.append({
                "top": tc,
                "bottom": bc,
                "xt": xt,
                "yt": yt,
                "xb": xb,
                "yb": yb,
                "x_shift": round(dx, 2),
                "y_distance": round(dy, 2),
                "angle_deg": round(theta_deg, 3)
            })

    return top_candidates, bot_candidates, pairs, rejected_top + rejected_bot

def generate_visual_debug_image(warped, top_candidates, bot_candidates, pairs, rejected_list, out_filename):
    """
    Draws visual overlay:
    - GREEN: Top anchors
    - BLUE: Bottom anchors
    - YELLOW: Connecting lines for paired anchors
    - RED: Rejected candidates
    """
    vis = warped.copy()
    if len(vis.shape) == 2:
        vis = cv2.cvtColor(vis, cv2.COLOR_GRAY2BGR)

    # Red for rejected
    for rx, ry, rw, rh in rejected_list:
        cv2.rectangle(vis, (int(rx - rw/2), int(ry - rh/2)), (int(rx + rw/2), int(ry + rh/2)), (0, 0, 255), 1)

    # Green for Top candidates
    for tc in top_candidates:
        cx, cy = tc["center"]
        cv2.circle(vis, (int(cx), int(cy)), 7, (0, 255, 0), 2)
        cv2.putText(vis, "TOP", (int(cx) - 15, int(cy) - 10), cv2.FONT_HERSHEY_SIMPLEX, 0.4, (0, 255, 0), 1)

    # Blue for Bottom candidates
    for bc in bot_candidates:
        cx, cy = bc["center"]
        cv2.circle(vis, (int(cx), int(cy)), 7, (255, 100, 0), 2)
        cv2.putText(vis, "BOT", (int(cx) - 15, int(cy) + 18), cv2.FONT_HERSHEY_SIMPLEX, 0.4, (255, 100, 0), 1)

    # Yellow lines for paired anchors
    for p in pairs:
        pt_t = (int(p["xt"]), int(p["yt"]))
        pt_b = (int(p["xb"]), int(p["yb"]))
        cv2.line(vis, pt_t, pt_b, (0, 255, 255), 2)
        label = f"dx:{p['x_shift']:+.1f}px ({p['angle_deg']:+.2f}deg)"
        mid_x = int((p["xt"] + p["xb"]) / 2.0)
        mid_y = int((p["yt"] + p["yb"]) / 2.0)
        cv2.putText(vis, label, (mid_x + 5, mid_y), cv2.FONT_HERSHEY_SIMPLEX, 0.38, (0, 255, 255), 1)

    out_path = str(DEBUG_DIR / out_filename)
    cv2.imwrite(out_path, vis)
    print(f"  [DEBUG IMAGE SAVED] {out_path}")

def run_diagnostic():
    img_dir = str(REPO_ROOT / 'anh')
    images = sorted([
        os.path.join(img_dir, f) for f in os.listdir(img_dir)
        if f.lower().endswith('.jpg') and not any(s in f for s in ['_result', '_thresh', '_name', '_overlay', '_calibration', '_gray', '_cleaned', '_detect'])
    ])

    print("=" * 90)
    print("  GRADEFLOW — PART III VERTICAL DIVIDER ANCHOR AUDIT")
    print("=" * 90)

    all_pairs_summary = []

    for path in images:
        name = os.path.basename(path)
        img = cv2.imread(path)
        if img is None:
            continue

        res = hi.auto_deskew_and_crop(img, debug=False)
        warped = res["warped"]

        top_cnts, bot_cnts, pairs, rejected = detect_part3_vertical_anchors(warped)
        
        # Save visual debug image
        debug_filename = f"part3_anchors_{os.path.splitext(name)[0]}.png"
        generate_visual_debug_image(warped, top_cnts, bot_cnts, pairs, rejected, debug_filename)

        print(f"\nImage: {name}")
        print(f"  Top Anchors Found   : {len(top_cnts)}")
        print(f"  Bottom Anchors Found: {len(bot_cnts)}")
        print(f"  Valid Pairs Found   : {len(pairs)}")

        for idx, p in enumerate(pairs, 1):
            print(f"  Pair #{idx}:")
            print(f"    TOP    = ({p['xt']:.1f}, {p['yt']:.1f})")
            print(f"    BOTTOM = ({p['xb']:.1f}, {p['yb']:.1f})")
            print(f"    X shift    = {p['x_shift']:+.2f} px")
            print(f"    Y distance = {p['y_distance']:.2f} px")
            print(f"    Angle      = {p['angle_deg']:+.3f}°")

        all_pairs_summary.append({
            "image": name,
            "top_cnt": len(top_cnts),
            "bot_cnt": len(bot_cnts),
            "pairs_cnt": len(pairs),
            "pairs": pairs
        })

    print("\n" + "=" * 90)
    print("  SUMMARY AUDIT REPORT")
    print("=" * 90)
    for s in all_pairs_summary:
        print(f"  Image: {s['image']:<12} | Top: {s['top_cnt']} | Bot: {s['bot_cnt']} | Pairs: {s['pairs_cnt']}")
        if s['pairs']:
            shifts = [p['x_shift'] for p in s['pairs']]
            angles = [p['angle_deg'] for p in s['pairs']]
            print(f"    -> X shifts: min={min(shifts):+.1f}px, max={max(shifts):+.1f}px, avg={np.mean(shifts):+.2f}px")
            print(f"    -> Angles  : min={min(angles):+.2f}°, max={max(angles):+.2f}°, avg={np.mean(angles):+.2f}°")
        else:
            print("    -> No valid pairs detected")
    print("=" * 90 + "\n")

if __name__ == "__main__":
    run_diagnostic()
