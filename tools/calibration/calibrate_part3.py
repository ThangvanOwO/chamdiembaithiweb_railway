"""
Đo tọa độ bubble Part III trên ảnh warped calibration.
Chạy: python tools/calibration/calibrate_part3.py anh/1_gray.jpg
"""
import cv2
import numpy as np
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]

img_arg = sys.argv[1] if len(sys.argv) > 1 else "anh/1_gray.jpg"
img_path = str(REPO_ROOT / img_arg) if not Path(img_arg).is_absolute() else img_arg

gray = cv2.imread(img_path, cv2.IMREAD_GRAYSCALE)
if gray is None:
    print(f"Không đọc được: {img_path}")
    sys.exit(1)

h, w = gray.shape
print(f"Ảnh: {w}x{h}")

# Part III region: y ~1450 → 1900, x = 0 → w
y_top, y_bot = 1440, 1900
roi = gray[y_top:y_bot, 0:w]

# Detect circles
circles = cv2.HoughCircles(
    roi, cv2.HOUGH_GRADIENT, dp=1, minDist=20,
    param1=50, param2=25, minRadius=8, maxRadius=18
)

if circles is None:
    print("Không tìm thấy circle nào!")
    sys.exit(1)

circles = np.round(circles[0]).astype(int)
# Convert back to full image coords
circles[:, 1] += y_top

print(f"\nTìm thấy {len(circles)} circles")

# Sort by x, then cluster into 6 questions (each ~230px apart)
# Each question has: 1 sign + 4 digit columns = ~5 x-clusters
circles_sorted = sorted(circles, key=lambda c: c[0])

# Group by x into clusters (gap > 15px = new cluster)
x_clusters = []
current = [circles_sorted[0]]
for c in circles_sorted[1:]:
    if c[0] - current[-1][0] > 15:
        x_clusters.append(current)
        current = [c]
    else:
        current.append(c)
x_clusters.append(current)

print(f"X clusters: {len(x_clusters)}")
print()

# For each cluster, compute mean x and list y values
for i, cluster in enumerate(x_clusters):
    xs = [c[0] for c in cluster]
    ys = sorted([c[1] for c in cluster])
    mean_x = int(np.mean(xs))
    print(f"  Cluster {i:2d}: x={mean_x:5d}  count={len(cluster):2d}  "
          f"y_range=[{min(ys)}-{max(ys)}]")

# Group clusters into 6 questions based on x gaps
# Expected: sign_col, col1, col2, col3, col4 per question
print("\n--- Suggested PART3_BLOCKS ---")
q_groups = []
current_q = [x_clusters[0]]
for cl in x_clusters[1:]:
    prev_x = int(np.mean([c[0] for c in current_q[-1]]))
    curr_x = int(np.mean([c[0] for c in cl]))
    if curr_x - prev_x > 80:  # Big gap = new question
        q_groups.append(current_q)
        current_q = [cl]
    else:
        current_q.append(cl)
q_groups.append(current_q)

for qi, qg in enumerate(q_groups):
    cols_x = []
    sign_x = None
    for ci, cl in enumerate(qg):
        mean_x = int(np.mean([c[0] for c in cl]))
        if ci == 0:
            sign_x = mean_x
        cols_x.append(mean_x)
    # First is sign, rest are digit columns
    if len(cols_x) >= 5:
        print(f'  {{"sign_x": {sign_x}, "cols_x": {cols_x[1:5]}, "q": {qi+1}}},')
    else:
        print(f'  Q{qi+1}: sign={sign_x} cols={cols_x} (incomplete)')

# Also measure Y coordinates
print("\n--- Y coordinates ---")
all_ys = sorted([c[1] for c in circles])
# Cluster Y values
y_clusters = []
current = [all_ys[0]]
for y in all_ys[1:]:
    if y - current[-1] > 10:
        y_clusters.append(current)
        current = [y]
    else:
        current.append(y)
y_clusters.append(current)

for i, yc in enumerate(y_clusters):
    mean_y = int(np.mean(yc))
    labels = ["sign(-)", "comma(,)", "digit 0", "digit 1", "digit 2",
              "digit 3", "digit 4", "digit 5", "digit 6", "digit 7",
              "digit 8", "digit 9"]
    lbl = labels[i] if i < len(labels) else "?"
    print(f"  Row {i:2d} ({lbl:10s}): y={mean_y:5d}  count={len(yc)}")
