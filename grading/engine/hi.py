"""
==========================================================================
 HỆ THỐNG CHẤM BÀI TRẮC NGHIỆM OMR (Optical Mark Recognition)
 Phiếu trắc nghiệm Việt Nam - OpenCV thuần (không Deep Learning)
==========================================================================
Cấu trúc phiếu:
  - Phần I  : 40 câu ABCD, 4 cột x 10 hàng
  - Phần II : 8 câu, mỗi câu a/b/c/d x Đúng/Sai
  - Phần III: 6 câu điền số (dấu trừ, dấu phẩy, 4 cột số 0-9)

Tọa độ bubble đã calibrate bằng HoughCircles trên ảnh warped 1400x1920.

Chống nhiễu chữ in (A, B, C, D, số thứ tự...) — 3 LỚP BẢO VỆ:
  LỚP 1) erase_printed_text(): tô TRẮNG chữ in trên ảnh warped TRƯỚC threshold
         → Xóa mạnh vùng rộng nhưng BẢO VỆ bubble bằng lỗ tròn (punch-holes)
  LỚP 2) Morphological opening: loại nét mảnh còn sót (viền, stroke nhỏ)
  LỚP 3) mask_printed_text(): tô ĐEN vùng text trên threshold (safety net)
"""

import cv2
import numpy as np
import os
import json
import logging
from datetime import datetime
from PIL import Image, ExifTags
from skimage import exposure

# Preserve direct CLI/legacy import of hi.py outside the repository root.
if not __package__:
    import sys
    sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
from grading.cpu_runtime import serialized_grading

logger = logging.getLogger(__name__)

# ╔════════════════════════════════════════════════════════════════════════╗
# ║                        CẤU HÌNH CHUNG                               ║
# ╚════════════════════════════════════════════════════════════════════════╝

# --- Kích thước ảnh warped (sau perspective transform) ---
WARP_WIDTH = 1400
WARP_HEIGHT = 1920

# --- Vùng crop tên học sinh trên ảnh warped ---
# (x, y, w, h) — dòng "4. Họ và tên thí sinh:......."
NAME_REGION = (255, 300, 745, 60)

# --- Tham số phát hiện bubble ---
# Ngưỡng tỷ lệ pixel đen / tổng pixel trong vòng tròn
# Bubble rỗng (viền) ~0.05-0.12 trên ảnh cleaned
# Bubble đã tô        ~0.25-0.85 (phone camera thấp hơn scan)
# Chỉnh trong khoảng 0.22 - 0.38 tùy chất lượng in/scan/phone
FILL_THRESHOLD = 0.15

# Bán kính bubble (pixel trên ảnh warped, đo từ HoughCircles ~11-14)
BUBBLE_RADIUS = 13

# IMPROVEMENT 2: Multi-scale bubble radius based on image dimensions
def _calc_adaptive_radius(warped_img):
    """Tính bubble radius thích ứng dựa trên kích thước ảnh warped."""
    h, w = warped_img.shape[:2]
    # Reference: WARP_WIDTH=1400 → radius=13
    # Scale proportionally for other resolutions
    scale = w / WARP_WIDTH
    adaptive_r = int(round(BUBBLE_RADIUS * scale))
    # Clamp to reasonable range [8, 20]
    return max(8, min(20, adaptive_r))

# Kích thước kernel morphological opening (LỚP 2) để loại nét chữ in
# Kernel 5x5 loại nét < 5px (chữ in ~2-3px, viền bubble ~2px)
# === CHỈNH KERNEL Ở ĐÂY === (5=an toàn, 7=mạnh hơn nhưng có thể phá bubble nhạt)
MORPH_KERNEL_SIZE = 3

# Ngưỡng circularity (hình tròn = 1.0, chữ cái < 0.5)
# Bubble tô đặc: circularity ~0.7-1.0
# Chữ cái A,B,C,D: circularity ~0.2-0.5
# === CHỈNH CIRCULARITY Ở ĐÂY === (0=tắt, 0.4-0.7=lọc text, >0.7=quá strict)
CIRCULARITY_THRESHOLD = 0.6

# Bán kính vùng bảo vệ bubble khi xóa text (LỚP 1)
# Phải >= BUBBLE_RADIUS để không xóa vào bubble
# +8px margin cho sai lệch warp ảnh phone (trước: +3px quá ít)
BUBBLE_PROTECT_RADIUS = BUBBLE_RADIUS + 8

# --- Hybrid OpenCV + CNN (bubble classifier) ---
# Có thể tắt CNN qua env var: HYBRID_CNN_ENABLE=0 (server yếu)
HYBRID_CNN_ENABLE = os.environ.get("HYBRID_CNN_ENABLE", "1").strip().lower() not in ("0", "false", "no")
BUBBLE_CNN_PATH = os.path.join(os.path.dirname(__file__), "bubble_cnn.pth")
BUBBLE_CNN_ONNX_PATH = os.path.join(os.path.dirname(__file__), "bubble_cnn.onnx")
CNN_IMG_SIZE = 32
CNN_FILL_THRESHOLD = 0.5
HYBRID_RATIO_LOW = 0.12
HYBRID_RATIO_HIGH = 0.45

# Part III hybrid thresholds (scores are 0-1)
P3_SIGN_SCORE_MIN = 0.18
P3_COMMA_SCORE_MIN = 0.10
P3_COMMA_GAP_MIN = 0.05
P3_DIGIT_SCORE_MIN = 0.28
P3_DIGIT_GAP_MIN = 0.05
P3_BLANK_COL_STD_MIN = 0.035
P3_OCR_ENABLE = os.environ.get("P3_OCR_ENABLE", "0").strip().lower() in ("1", "true", "yes")
P3_OCR_BOX_Y_OFFSET = -55  # relative to PART3_SIGN_Y
P3_OCR_BOX_SIZE = 34
P3_OCR_INK_MIN = 0.04
P3_OCR_INK_MAX = 0.45

# SBD/Mã đề thresholds (lighter pencil marks)
SBD_MADE_TOP_MIN = 0.18
SBD_MADE_GAP_MIN = 0.06
SBD_MADE_FALLBACK_TOP_MIN = 0.15
SBD_MADE_FALLBACK_GAP_MIN = 0.08

_CNN_MODEL = None
_CNN_DEVICE = None
_CNN_READY = False
_CNN_ERROR = None

# ╔════════════════════════════════════════════════════════════════════════╗
# ║              TỌA ĐỘ PHẦN I - 40 câu ABCD (4 cột x 10 hàng)        ║
# ╚════════════════════════════════════════════════════════════════════════╝
# start_x, start_y: tâm bubble đầu tiên (lựa chọn A, câu 1 của cột)
# step_x: khoảng cách ngang giữa A→B→C→D (~73px)
# step_y: khoảng cách dọc giữa các câu (~33px)
PART1_COLS = [
    {"start_x": 82,   "start_y": 689, "step_x": 72.3, "step_y": 33.1, "q_start": 1},   # Cột 1: Q1-Q10
    {"start_x": 430,  "start_y": 691, "step_x": 74,   "step_y": 33.1, "q_start": 11},  # Cột 2: Q11-Q20
    {"start_x": 781,  "start_y": 691, "step_x": 73,   "step_y": 33.1, "q_start": 21},  # Cột 3: Q21-Q30
    {"start_x": 1130, "start_y": 691, "step_x": 73,   "step_y": 33.1, "q_start": 31},  # Cột 4: Q31-Q40
]
PART1_NUM_ROWS = 10
PART1_CHOICES = ["A", "B", "C", "D"]

# ╔════════════════════════════════════════════════════════════════════════╗
# ║       TỌA ĐỘ PHẦN II - 8 câu x (a/b/c/d) x (Đúng/Sai)           ║
# ╚════════════════════════════════════════════════════════════════════════╝
# Mỗi block: start_x = tâm cột Đúng, start_x + step = tâm cột Sai
PART2_BLOCKS = [
    {"start_x": 81,   "start_y": 1190, "q": 1},
    {"start_x": 228,  "start_y": 1190, "q": 2},
    {"start_x": 430,  "start_y": 1190, "q": 3},
    {"start_x": 577,  "start_y": 1190, "q": 4},
    {"start_x": 781,  "start_y": 1190, "q": 5},
    {"start_x": 927,  "start_y": 1190, "q": 6},
    {"start_x": 1130, "start_y": 1190, "q": 7},
    {"start_x": 1276, "start_y": 1190, "q": 8},
]
PART2_STEP_X = 73   # Khoảng cách Đúng → Sai
PART2_STEP_Y = 33   # Khoảng cách a → b → c → d
PART2_ROWS = ["a", "b", "c", "d"]

# ╔════════════════════════════════════════════════════════════════════════╗
# ║      TỌA ĐỘ PHẦN III - 6 câu điền số (dấu trừ, phẩy, 4 cột 0-9) ║
# ╚════════════════════════════════════════════════════════════════════════╝
# Mỗi câu: sign_x = tâm bubble dấu trừ, cols_x = [4 tâm cột số]
PART3_BLOCKS = [
    {"sign_x": 81,   "cols_x": [90,  124, 159, 192],  "q": 1},
    {"sign_x": 313,  "cols_x": [324, 357, 391, 425],  "q": 2},
    {"sign_x": 547,  "cols_x": [557, 591, 624, 659],  "q": 3},
    {"sign_x": 780,  "cols_x": [790, 823, 858, 892],  "q": 4},
    {"sign_x": 1013, "cols_x": [1023, 1057, 1091, 1125], "q": 5},
    {"sign_x": 1247, "cols_x": [1249, 1283, 1317, 1351], "q": 6},
]
PART3_SIGN_Y = 1490         # Hàng dấu trừ (-)
PART3_COMMA_Y = 1522        # Hàng dấu phẩy (.)
PART3_DIGIT_START_Y = 1555  # Hàng chữ số 0
PART3_DIGIT_STEP_Y = 33.1   # Bước giữa các hàng 0→1→...→9
PART3_NUM_DIGIT_COLS = 4

# ╔════════════════════════════════════════════════════════════════════════╗
# ║     TỌA ĐỘ SỐ BÁO DANH (6 chữ số) + MÃ ĐỀ (3 chữ số)            ║
# ╚════════════════════════════════════════════════════════════════════════╝
# Vùng góc trên bên phải, mỗi cột có 10 bubble (digits 0-9)
# Tọa độ x cho từng cột (calibrated bằng HoughCircles)
SBD_COLS_X = [1057, 1085, 1113, 1141, 1169, 1197]  # 6 cột Số báo danh
MADE_COLS_X = [1292, 1321, 1345]                     # 3 cột Mã đề
# Tọa độ y cho hàng digit 0-9 (không đều nên dùng mảng tường minh)
SBD_MADE_DIGIT_Y = [173, 206, 249, 285, 326, 363, 401, 440, 480, 517]

# ╔════════════════════════════════════════════════════════════════════════╗
# ║    VÙNG CHỮ IN CẦN XÓA (aggressive — dùng với bubble protection)  ║
# ╚════════════════════════════════════════════════════════════════════════╝
# Mỗi vùng (x1, y1, x2, y2) sẽ bị xóa trắng/đen, NGOẠI TRỪ vùng tròn
# quanh mỗi bubble center (punch-holes). Nhờ đó có thể phủ RẤT RỘNG mà
# không phá hủy dữ liệu bubble.

def _build_text_erase_regions():
    """
    Tạo danh sách vùng chữ in cần xóa — RỘNG TỐI ĐA.
    Bubble được bảo vệ bởi punch-holes nên không sợ mất dữ liệu.
    """
    # === CHỈNH VÙNG MASK Ở ĐÂY ===
    regions = []

    # --- Phần I: Header "A B C D" + banner "PHẦN I" ---
    # Phủ TOÀN BỘ từ banner đến sát row 1 (y=590→680)
    # Chữ A,B,C,D thực tế ở y=655-668 → phải phủ đến y≥670
    # Bubble row 1 ở y=660 nhưng ĐƯỢC BẢO VỆ bởi punch-holes
    for cfg in PART1_COLS:
        sx = cfg["start_x"]
        ex = sx + 3 * cfg["step_x"]
        regions.append((sx - 30, 590, ex + 30, 680))
        # Số thứ tự câu bên trái: "1", "2", ..., "10"
        y_top = int(cfg["start_y"] - 15)
        col_rows = cfg.get("num_rows", PART1_NUM_ROWS)
        y_bot = int(cfg["start_y"] + (col_rows - 1) * cfg["step_y"] + 22)
        regions.append((sx - 60, y_top, sx - 3, y_bot))

    # Banner "PHẦN I" phía trên
    regions.append((15, 570, 1385, 595))

    # --- Phần II: Header "Câu N" + "Đúng Sai" + label "a) b) c) d)" ---
    regions.append((25, 1095, 1375, 1188))
    for blk in PART2_BLOCKS:
        sx = blk["start_x"]
        y_top = blk["start_y"] - 12
        y_bot = int(blk["start_y"] + 3 * PART2_STEP_Y + 12)
        regions.append((sx - 35, y_top, sx - 3, y_bot))

    # --- Phần III: Header "Câu N" + label "0"-"9" ---
    # CHÚ Ý: KHÔNG mask sign(-) và comma(.) — chỉ mask label số
    regions.append((25, 1305, 1375, 1400))
    for blk in PART3_BLOCKS:
        first_col_x = blk["cols_x"][0]
        y_top = int(PART3_DIGIT_START_Y - 8)
        y_bot = int(PART3_DIGIT_START_Y + 9 * PART3_DIGIT_STEP_Y + 15)
        regions.append((first_col_x - 45, y_top, first_col_x - 3, y_bot))

    # --- SBD + Mã đề: Label "0"-"9" bên trái ---
    sbd_left = min(SBD_COLS_X) - 45
    sbd_right = min(SBD_COLS_X) - 3
    regions.append((sbd_left, SBD_MADE_DIGIT_Y[0] - 8, sbd_right, SBD_MADE_DIGIT_Y[-1] + 15))
    made_left = min(MADE_COLS_X) - 45
    made_right = min(MADE_COLS_X) - 3
    regions.append((made_left, SBD_MADE_DIGIT_Y[0] - 8, made_right, SBD_MADE_DIGIT_Y[-1] + 15))

    return regions


TEXT_ERASE_REGIONS = _build_text_erase_regions()


def _collect_all_bubble_centers():
    """Thu thập TẤT CẢ tâm bubble trên phiếu → dùng cho punch-holes bảo vệ."""
    centers = []
    # Part I: mỗi cột có thể có num_rows riêng (hỗ trợ biến thể 26, 30 câu)
    for cfg in PART1_COLS:
        col_rows = cfg.get("num_rows", PART1_NUM_ROWS)
        for ci in range(4):
            for ri in range(col_rows):
                cx = int(cfg["start_x"] + ci * cfg["step_x"])
                cy = int(cfg["start_y"] + ri * cfg["step_y"])
                centers.append((cx, cy))
    # Part II: 8 block × 4 hàng × 2 cột = 64 bubble
    for blk in PART2_BLOCKS:
        for ci in range(2):
            for ri in range(4):
                cx = int(blk["start_x"] + ci * PART2_STEP_X)
                cy = int(blk["start_y"] + ri * PART2_STEP_Y)
                centers.append((cx, cy))
    # Part III: 6 câu × (1 sign + 4 comma + 4×10 digits)
    for blk in PART3_BLOCKS:
        centers.append((int(blk["sign_x"]), PART3_SIGN_Y))
        for col_x in blk["cols_x"]:
            centers.append((int(col_x), PART3_COMMA_Y))
            for d in range(10):
                cy = int(PART3_DIGIT_START_Y + d * PART3_DIGIT_STEP_Y)
                centers.append((int(col_x), cy))
    # SBD + Mã đề
    for cx in list(SBD_COLS_X) + list(MADE_COLS_X):
        for cy in SBD_MADE_DIGIT_Y:
            centers.append((int(cx), int(cy)))
    return centers


ALL_BUBBLE_CENTERS = _collect_all_bubble_centers()


def _build_erase_mask():
    """
    Pre-compute erase mask 1 lần duy nhất khi load module.
    Pixel=255 → sẽ bị xóa (trắng trên warped, đen trên threshold).
    Pixel=0   → được giữ nguyên (bao gồm vùng bubble).
    """
    mask = np.zeros((WARP_HEIGHT, WARP_WIDTH), dtype=np.uint8)
    # Phủ tất cả vùng text
    for (x1, y1, x2, y2) in TEXT_ERASE_REGIONS:
        x1c = max(0, int(x1))
        y1c = max(0, int(y1))
        x2c = min(WARP_WIDTH, int(x2))
        y2c = min(WARP_HEIGHT, int(y2))
        mask[y1c:y2c, x1c:x2c] = 255
    # Đục lỗ tròn (punch-holes) tại mỗi bubble center → bảo vệ bubble
    for (cx, cy) in ALL_BUBBLE_CENTERS:
        cv2.circle(mask, (cx, cy), BUBBLE_PROTECT_RADIUS, 0, -1)
    return mask


ERASE_MASK = _build_erase_mask()


# ╔════════════════════════════════════════════════════════════════════════╗
# ║                 JSON: LOAD TEMPLATE / ANSWERS / SAVE                 ║
# ╚════════════════════════════════════════════════════════════════════════╝

def load_template(json_path):
    """
    Đọc template JSON → cập nhật toàn bộ global constants.
    Gọi hàm này TRƯỚC khi chấm bài nếu muốn dùng phiếu khác.
    """
    global WARP_WIDTH, WARP_HEIGHT, NAME_REGION
    global FILL_THRESHOLD, BUBBLE_RADIUS, MORPH_KERNEL_SIZE
    global CIRCULARITY_THRESHOLD, BUBBLE_PROTECT_RADIUS
    global PART1_COLS, PART1_NUM_ROWS, PART1_CHOICES
    global PART2_BLOCKS, PART2_STEP_X, PART2_STEP_Y, PART2_ROWS
    global PART3_BLOCKS, PART3_SIGN_Y, PART3_COMMA_Y
    global PART3_DIGIT_START_Y, PART3_DIGIT_STEP_Y, PART3_NUM_DIGIT_COLS
    global SBD_COLS_X, MADE_COLS_X, SBD_MADE_DIGIT_Y
    global TEXT_ERASE_REGIONS, ALL_BUBBLE_CENTERS, ERASE_MASK

    with open(json_path, "r", encoding="utf-8") as f:
        t = json.load(f)

    # Warp
    WARP_WIDTH  = t["warp"]["width"]
    WARP_HEIGHT = t["warp"]["height"]

    # Name region (optional override)
    if "name_region" in t:
        nr = t["name_region"]
        NAME_REGION = (nr["x"], nr["y"], nr["w"], nr["h"])

    # Detection
    det = t["detection"]
    FILL_THRESHOLD         = det["fill_threshold"]
    BUBBLE_RADIUS          = det["bubble_radius"]
    MORPH_KERNEL_SIZE      = det["morph_kernel_size"]
    CIRCULARITY_THRESHOLD  = det["circularity_threshold"]
    BUBBLE_PROTECT_RADIUS  = det.get("bubble_protect_radius", BUBBLE_RADIUS + 3)

    # Part I
    p1 = t["part1"]
    PART1_COLS     = p1["columns"]
    PART1_NUM_ROWS = p1.get("num_rows", 10)
    PART1_CHOICES  = p1.get("choices", ["A", "B", "C", "D"])

    # Part II
    p2 = t["part2"]
    PART2_BLOCKS = p2["blocks"]
    PART2_STEP_X = p2["step_x"]
    PART2_STEP_Y = p2["step_y"]
    PART2_ROWS   = p2.get("rows", ["a", "b", "c", "d"])

    # Part III
    p3 = t["part3"]
    PART3_BLOCKS         = p3["blocks"]
    PART3_SIGN_Y         = p3["sign_y"]
    PART3_COMMA_Y        = p3["comma_y"]
    PART3_DIGIT_START_Y  = p3["digit_start_y"]
    PART3_DIGIT_STEP_Y   = p3["digit_step_y"]
    PART3_NUM_DIGIT_COLS = p3.get("num_digit_cols", 4)

    # SBD + Mã đề
    SBD_COLS_X       = t["sbd"]["cols_x"]
    MADE_COLS_X      = t["made"]["cols_x"]
    SBD_MADE_DIGIT_Y = t["sbd"]["digit_y"]

    # Rebuild derived data
    TEXT_ERASE_REGIONS = _build_text_erase_regions()
    ALL_BUBBLE_CENTERS = _collect_all_bubble_centers()
    ERASE_MASK         = _build_erase_mask()

    try:
        print(f"[OK] Template: {t.get('name', json_path)}")
    except Exception:
        pass
    return t


def load_answers(json_path):
    """
    Đọc đáp án từ file JSON → trả về dict tương thích với process_sheet().
    Keys JSON là string ("1", "2"...) → chuyển thành int.
    """
    with open(json_path, "r", encoding="utf-8") as f:
        raw = json.load(f)

    correct = {}

    # Part I: {"1": "A", ...} → {1: "A", ...}
    if "part1" in raw:
        correct["part1"] = {int(k): v for k, v in raw["part1"].items()}

    # Part II: {"1": {"a": "Dung", ...}} → {1: {"a": "Dung", ...}}
    if "part2" in raw:
        correct["part2"] = {int(k): v for k, v in raw["part2"].items()}

    # Part III: {"1": "1234", ...} → {1: "1234", ...}
    if "part3" in raw:
        correct["part3"] = {int(k): v for k, v in raw["part3"].items()}

    print(f"[OK] Đáp án: {raw.get('exam_name', json_path)}")
    return correct


def save_result(result, output_dir="results", correct_answers=None):
    """
    Lưu kết quả chấm bài ra file JSON đầy đủ.
    result: dict trả về từ process_sheet()
    correct_answers: dict đáp án đúng (tùy chọn, để ghi kèm vào JSON)
    Trả về đường dẫn file JSON đã lưu.
    """
    if result is None:
        return None

    os.makedirs(output_dir, exist_ok=True)

    sbd = result.get("sbd", "unknown")
    made = result.get("made", "unknown")
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    scores = result.get("scores", {})

    # Chuyển đáp án HS (key int → string cho JSON)
    out = {
        "timestamp": datetime.now().isoformat(),
        "sbd": sbd,
        "made": made,
        "score_total": result.get("score"),
        "max_score": result.get("max_score"),
        "score_part1": scores.get("part1"),
        "score_part2": scores.get("part2"),
        "score_part3": scores.get("part3"),
        "student_answers": {
            "part1": {str(k): v for k, v in result.get("part1", {}).items()},
            "part2": {str(k): v for k, v in result.get("part2", {}).items()},
            "part3": {str(k): v for k, v in result.get("part3", {}).items()},
        },
    }

    # Ghi kèm đáp án đúng nếu có
    if correct_answers:
        out["correct_answers"] = {
            "part1": {str(k): v for k, v in correct_answers.get("part1", {}).items()},
            "part2": {str(k): v for k, v in correct_answers.get("part2", {}).items()},
            "part3": {str(k): v for k, v in correct_answers.get("part3", {}).items()},
        }

    # Sanitize filename (SBD/MD có thể chứa '?' nếu không nhận được)
    safe_sbd = sbd.replace("?", "_")
    safe_made = made.replace("?", "_")
    fname = f"SBD_{safe_sbd}_MD_{safe_made}_{ts}.json"
    fpath = os.path.join(output_dir, fname)
    with open(fpath, "w", encoding="utf-8") as f:
        json.dump(out, f, ensure_ascii=False, indent=2)

    print(f"[OK] JSON → {fpath}")
    return fpath


def export_excel(all_results, output_path="results/bang_diem.xlsx"):
    """
    Xuất bảng điểm tổng hợp ra file Excel.
    all_results: list of dict (mỗi phần tử là return value từ process_sheet)
                 hoặc dict {filename: result}
    output_path: đường dẫn file .xlsx
    """
    try:
        from openpyxl import Workbook
        from openpyxl.styles import Font, Alignment, Border, Side, PatternFill
    except ImportError:
        print("[LỖI] Cần cài openpyxl: pip install openpyxl")
        return None

    # Chuẩn hóa input
    if isinstance(all_results, dict):
        results_list = [v for v in all_results.values() if v is not None]
    else:
        results_list = [r for r in all_results if r is not None]

    if not results_list:
        print("[WARN] Không có kết quả để xuất Excel")
        return None

    wb = Workbook()
    ws = wb.active
    ws.title = "Bảng điểm"

    # ── Styles ──
    header_font = Font(name="Arial", bold=True, size=11, color="FFFFFF")
    header_fill = PatternFill(start_color="2F5496", end_color="2F5496", fill_type="solid")
    header_align = Alignment(horizontal="center", vertical="center", wrap_text=True)
    cell_align = Alignment(horizontal="center", vertical="center")
    cell_align_left = Alignment(horizontal="left", vertical="center")
    thin_border = Border(
        left=Side(style="thin"), right=Side(style="thin"),
        top=Side(style="thin"), bottom=Side(style="thin"),
    )
    green_fill = PatternFill(start_color="C6EFCE", end_color="C6EFCE", fill_type="solid")
    red_fill = PatternFill(start_color="FFC7CE", end_color="FFC7CE", fill_type="solid")

    # ── Header row ──
    headers = [
        "STT", "SBD", "Mã đề", "Họ tên",
        "Phần I\n(/40)", "Phần II\n(/8)", "Phần III\n(/6)",
        "Tổng điểm\n(/54)", "Điểm 10",
    ]
    # Thêm cột đáp án Part I (Q1-Q40)
    for q in range(1, 41):
        headers.append(f"Q{q}")
    # Thêm cột Part III (Q1-Q6)
    for q in range(1, 7):
        headers.append(f"P3.Q{q}")

    for ci, h in enumerate(headers, 1):
        cell = ws.cell(row=1, column=ci, value=h)
        cell.font = header_font
        cell.fill = header_fill
        cell.alignment = header_align
        cell.border = thin_border

    # ── Data rows ──
    for ri, res in enumerate(sorted(results_list, key=lambda r: r.get("sbd", "")), start=1):
        scores = res.get("scores", {})
        s1 = scores.get("part1", 0) or 0
        s2 = scores.get("part2", 0) or 0
        s3 = scores.get("part3", 0) or 0
        total = res.get("score") or (s1 + s2 + s3)
        max_s = res.get("max_score") or 54
        diem10 = round(total / max_s * 10, 2) if max_s > 0 else 0

        row_data = [
            ri,
            res.get("sbd", ""),
            res.get("made", ""),
            "",  # Họ tên — user điền sau
            s1, s2, s3, total, diem10,
        ]
        # Đáp án Part I
        p1 = res.get("part1", {})
        for q in range(1, 41):
            row_data.append(p1.get(q, ""))
        # Đáp án Part III
        p3 = res.get("part3", {})
        for q in range(1, 7):
            row_data.append(p3.get(q, ""))

        row_num = ri + 1
        for ci, val in enumerate(row_data, 1):
            cell = ws.cell(row=row_num, column=ci, value=val)
            cell.border = thin_border
            if ci <= 4:
                cell.alignment = cell_align_left if ci == 4 else cell_align
            else:
                cell.alignment = cell_align

        # Highlight tổng điểm
        total_cell = ws.cell(row=row_num, column=8)
        if total >= 27:  # >= 50%
            total_cell.fill = green_fill
        else:
            total_cell.fill = red_fill

        # Highlight đáp án sai Part I (nếu tô trùng hoặc trống)
        for q in range(1, 41):
            ci = 9 + q  # column index (1-based)
            ans = p1.get(q, "")
            if ans in ("X", ""):
                ws.cell(row=row_num, column=ci).fill = red_fill

    # ── Column widths ──
    ws.column_dimensions["A"].width = 5    # STT
    ws.column_dimensions["B"].width = 12   # SBD
    ws.column_dimensions["C"].width = 8    # Mã đề
    ws.column_dimensions["D"].width = 25   # Họ tên
    ws.column_dimensions["E"].width = 9    # P1
    ws.column_dimensions["F"].width = 9    # P2
    ws.column_dimensions["G"].width = 9    # P3
    ws.column_dimensions["H"].width = 11   # Tổng
    ws.column_dimensions["I"].width = 9    # Điểm 10
    # Q1-Q40: narrow
    from openpyxl.utils import get_column_letter
    for ci in range(10, 10 + 40 + 6):
        ws.column_dimensions[get_column_letter(ci)].width = 5

    # Freeze header
    ws.freeze_panes = "A2"

    # ── Lưu ──
    os.makedirs(os.path.dirname(output_path) or ".", exist_ok=True)
    wb.save(output_path)
    print(f"[OK] Excel → {output_path}")
    return output_path


# ╔════════════════════════════════════════════════════════════════════════╗
# ║                    HÀM TIỆN ÍCH CƠ BẢN                             ║
# ╚════════════════════════════════════════════════════════════════════════╝

def order_points(pts):
    """
    [UnT-STYLE] sort4Contour — Sắp xếp 4 điểm: TL, TR, BR, BL.
    
    Cải tiến từ UnT Dạy Học: dùng centroid-based sorting chính xác hơn
    cho trường hợp perspective skew lớn (phone camera nghiêng).
    
    Method 1: sum/diff (classic — nhanh, đúng 95% cases)
    Method 2: centroid-based (UnT — robust cho extreme skew)
    
    Validate: nếu method 1 cho kết quả phi lý → dùng method 2.
    """
    pts = np.array(pts, dtype="float32")
    
    # ── Method 1: Classic sum/diff ──
    rect = np.zeros((4, 2), dtype="float32")
    s = pts.sum(axis=1)
    rect[0] = pts[np.argmin(s)]   # top-left: tổng nhỏ nhất
    rect[2] = pts[np.argmax(s)]   # bottom-right: tổng lớn nhất
    diff = np.diff(pts, axis=1)
    rect[1] = pts[np.argmin(diff)]  # top-right: x-y nhỏ nhất (x lớn, y nhỏ)
    rect[3] = pts[np.argmax(diff)]  # bottom-left: x-y lớn nhất (x nhỏ, y lớn)
    
    # ── Validate: check all 4 points are unique ──
    unique_check = len(set(map(tuple, rect.tolist())))
    if unique_check == 4:
        return rect
    
    # ── Method 2: Centroid-based sorting (UnT sort4Contour fallback) ──
    # Sort by angle from centroid
    cx = np.mean(pts[:, 0])
    cy = np.mean(pts[:, 1])
    angles = np.arctan2(pts[:, 1] - cy, pts[:, 0] - cx)
    # Sort clockwise starting from top-left (angle ≈ -3π/4)
    order = np.argsort(angles)
    sorted_pts = pts[order]
    # Rearrange: TL (smallest y first, then smallest x), then clockwise
    # Top points = 2 smallest y; Bottom points = 2 largest y
    y_sorted = pts[np.argsort(pts[:, 1])]
    top2 = y_sorted[:2]
    bot2 = y_sorted[2:]
    tl = top2[np.argmin(top2[:, 0])]
    tr = top2[np.argmax(top2[:, 0])]
    bl = bot2[np.argmin(bot2[:, 0])]
    br = bot2[np.argmax(bot2[:, 0])]
    return np.array([tl, tr, br, bl], dtype="float32")


# ╔════════════════════════════════════════════════════════════════════════╗
# ║   BƯỚC 1-2: TỰ ĐỘNG PHÁT HIỆN GIẤY + NẮN THẲNG ẢNH               ║
# ║   auto_deskew_and_crop — Pipeline 2 lớp robust cho ảnh thực tế     ║
# ╚════════════════════════════════════════════════════════════════════════╝

# --- Tham số paper detection ---
_PAPER_MIN_AREA_RATIO = 0.10  # Giấy chiếm tối thiểu 10% ảnh (phone xa)
_PAPER_MAX_AREA_RATIO = 0.98  # Tối đa 98%
_PAPER_SIDE_RATIO_MIN = 0.35  # Cạnh đối diện chênh tối đa 65% (perspective)
_PAPER_ASPECT_MIN     = 0.45  # min(w,h)/max(w,h) — A4 dọc ≈ 0.73

# --- Tham số corner markers ---
_MARKER_MIN_AREA_RATIO = 0.0001  # Ô vuông nhỏ nhất (phone xa, ảnh lớn)
_MARKER_MAX_AREA_RATIO = 0.012   # Ô vuông lớn nhất

# --- Tham số refinement ---
_REFINE_MARKER_MIN = 0.00003     # Marker trên ảnh warped nhỏ hơn
_REFINE_MARKER_MAX = 0.004
_REFINE_MIN_SPAN   = 0.60        # 4 marker phải trải ≥60% ảnh warped
_REFINE_MARGIN     = 0.20        # Mỗi marker phải trong 20% từ góc ảnh


def _score_warp_quality(warped, method_name, corners):
    """
    Chấm điểm chất lượng ảnh warped — đa yếu tố thực tế:
      1) Sharpness (Laplacian variance)     — 40%  (quan trọng nhất)
      2) Paper coverage (vùng trắng)        — 25%
      3) Cleanliness (ít noise)             — 20%
      4) Corner stability (hình học)        — 10%
      5) Bonus nhẹ cho corner_markers       — +8
      6) Marker refinement thành công       — +15
    Returns (total_score, sharpness_raw, refined_corners_or_None)
    """
    gray = cv2.cvtColor(warped, cv2.COLOR_BGR2GRAY) \
        if len(warped.shape) == 3 else warped.copy()
    h, w = gray.shape[:2]
    total_px = h * w
    score = 0.0
    detail = {}

    # ── 1) Sharpness — 40% (0-40) ──
    lap_var = cv2.Laplacian(gray, cv2.CV_64F).var()
    sharp_score = min(100.0, lap_var / 50.0) * 0.40
    score += sharp_score
    detail['sharp'] = f"{sharp_score:.1f}"

    # ── 2) Coverage — 25% (0-25) ──
    white_px = np.count_nonzero(gray > 150)
    coverage = (white_px / total_px) * 100.0 if total_px > 0 else 0
    cov_score = min(coverage, 100.0) * 0.25
    score += cov_score
    detail['cover'] = f"{cov_score:.1f}"

    # ── 3) Cleanliness — 20% (0-20) ──
    thresh = cv2.adaptiveThreshold(gray, 255, cv2.ADAPTIVE_THRESH_GAUSSIAN_C,
                                   cv2.THRESH_BINARY_INV, 11, 2)
    noise_ratio = cv2.countNonZero(thresh) / total_px
    # IMPROVEMENT 4: Noise rejection — reject warps with edge density <0.01 or >0.25
    if noise_ratio < 0.01 or noise_ratio > 0.25:
        clean = 0.0  # Too clean (no content) or too noisy
    else:
        clean = max(0.0, 100.0 - noise_ratio * 80.0)
    clean_score = clean * 0.20
    score += clean_score
    detail['clean'] = f"{clean_score:.1f}"

    # ── 4) Corner stability — 10% (0-10) ──
    if corners is not None and len(corners) == 4:
        ordered = order_points(corners)
        tl, tr, br, bl = ordered
        w_top = np.linalg.norm(tr - tl)
        w_bot = np.linalg.norm(br - bl)
        h_left = np.linalg.norm(bl - tl)
        h_right = np.linalg.norm(br - tr)
        if w_top > 0 and w_bot > 0 and h_left > 0 and h_right > 0:
            w_sym = min(w_top, w_bot) / max(w_top, w_bot)
            h_sym = min(h_left, h_right) / max(h_left, h_right)
            symmetry = (w_sym + h_sym) / 2.0
            avg_w = (w_top + w_bot) / 2
            avg_h = (h_left + h_right) / 2
            aspect = min(avg_w, avg_h) / max(avg_w, avg_h)
            a4_fit = max(0.0, 1.0 - abs(aspect - 0.707) * 3.0)
            stab = (symmetry * 0.5 + a4_fit * 0.5) * 10.0
            score += stab
            detail['stab'] = f"{stab:.1f}"

    # ── 5) Bonus nhẹ cho corner_markers ──
    # [FIX] Đã loại bỏ +8 điểm tùy ý vì nó có thể làm corner_markers thắng 
    #       ngay cả khi paper_contour nắn chuẩn hơn.
    if method_name.startswith("corner_markers"):
        score += 0.0
        detail['bonus'] = '+0'

    # ── 6) Marker refinement ──
    refined = _refine_targeted(warped)
    if refined is not None:
        score += 15.0
        detail['refine'] = 'targeted+15'
    else:
        refined = _refine_with_markers(warped)
        if refined is not None:
            score += 8.0
            detail['refine'] = 'global+8'
        else:
            detail['refine'] = 'none'

    try:
        print(f"    score_detail: {detail} -> {score:.1f}")
    except Exception:
        pass
    return score, sharp_score, refined


def auto_deskew_and_crop(image, debug=False):
    """
    Tự động phát hiện phiếu trắc nghiệm và nắn thẳng.

    Luôn chạy CẢ 2 method, chọn kết quả tốt nhất:
      Method A : Tìm 4 ô vuông đen góc → warp → refine
      Method B : Tìm viền giấy (Canny / threshold / saturation)
                 → warp trung gian → refine bằng corner markers

    Returns:
      dict {
        "warped"      : ndarray  — ảnh nắn thẳng WARP_WIDTH × WARP_HEIGHT
        "corners"     : ndarray 4×2 float32 [TL, TR, BR, BL] trên ảnh gốc
        "method"      : str
        "success"     : bool — True nếu tìm được
        "debug_image" : ndarray | None
      }
    Raise ValueError nếu cả 2 đều thất bại.
    """
    debug_img = image.copy() if debug else None
    candidates = []  # (score, warped, corners, method_name)

    # ─── Method A: Corner markers ───
    markers = _find_corner_markers(image, debug_img)
    if markers is not None:
        ordered = order_points(markers)
        if _validate_marker_quad(ordered, image.shape[1], image.shape[0]):
            warped_a = _warp_to_rect(image, ordered)
            score_a, sharp_a, refined_a = _score_warp_quality(
                warped_a, "corner_markers", ordered)
            method_a = "corner_markers"
            corners_a = ordered
            if refined_a is not None:
                # ── FIX: single-warp thay vì double-warp ──
                refined_orig = _map_warped_to_original(refined_a, ordered)
                if _validate_marker_quad(refined_orig, image.shape[1], image.shape[0]):
                    warped_a_ref = _warp_to_rect(image, refined_orig)
                    score_a_ref, sharp_a_ref, _ = _score_warp_quality(
                        warped_a_ref, "corner_markers+refine", refined_orig)
                    # [FIX] Chỉ dùng refinement nếu score KHÔNG kém hơn
                    if score_a_ref >= score_a:
                        warped_a = warped_a_ref
                        score_a = score_a_ref
                        sharp_a = sharp_a_ref
                        method_a = "corner_markers+refine"
                        corners_a = refined_orig
            # [FIX] Bonus ĐIỀU KIỆN theo symmetry — tránh false positive.
            # Quad đối xứng cao (> 0.97) = detect đúng → +5 bonus
            # Thấp hơn → bonus giảm hoặc không có
            sym_a = _quad_symmetry(corners_a)
            if sym_a > 0.97:
                score_a += 5.0
                bonus_note = f"+5 direct, sym={sym_a:.3f}"
            elif sym_a > 0.94:
                score_a += 2.0
                bonus_note = f"+2 direct, sym={sym_a:.3f}"
            else:
                bonus_note = f"no bonus, sym={sym_a:.3f} (suspicious)"
            candidates.append((score_a, sharp_a, warped_a, corners_a, method_a))
            try:
                print(f"  [A] {method_a} -> {score_a:.1f} ({bonus_note})")
            except Exception:
                pass

    # ─── Method B: Paper contour ───
    paper = _find_paper_contour(image, debug_img)
    if paper is not None:
        ordered_p = order_points(paper)
        warped_b = _warp_to_rect(image, ordered_p)
        score_b, sharp_b, refined_b = _score_warp_quality(
            warped_b, "paper_contour", ordered_p)
        method_b = "paper_contour"
        corners_b = ordered_p
        if refined_b is not None:
            # ── FIX: single-warp thay vì double-warp ──
            refined_orig_b = _map_warped_to_original(refined_b, ordered_p)
            if _validate_marker_quad(refined_orig_b, image.shape[1], image.shape[0]):
                warped_b_ref = _warp_to_rect(image, refined_orig_b)
                score_b_ref, sharp_b_ref, _ = _score_warp_quality(
                    warped_b_ref, "paper+refine", refined_orig_b)
                # [FIX] Chỉ dùng refinement nếu score KHÔNG kém hơn
                if score_b_ref >= score_b:
                    warped_b = warped_b_ref
                    score_b = score_b_ref
                    sharp_b = sharp_b_ref
                    method_b = "paper+refine"
                    corners_b = refined_orig_b
        candidates.append((score_b, sharp_b, warped_b, corners_b, method_b))
        try:
            print(f"  [B] {method_b} -> {score_b:.1f}")
        except Exception:
            pass

    # ─── Method C: HYBRID paper + corner markers (DIRECT) ───
    # Cách 1 (tối ưu): Dùng paper corners làm HOA TIÊU, tìm marker 
    # TRỰC TIẾP trên ảnh gốc — KHÔNG cần warp trung gian.
    #
    # Quy trình:
    #   1) Paper contour cho 4 góc thô (mép giấy) trên ảnh gốc
    #   2) Crop vùng nhỏ BÊN TRONG giấy quanh mỗi góc thô
    #   3) Tìm ô vuông đen (marker) thực sự trong mỗi ROI
    #   4) Lấy TÂM marker → đó là 4 điểm warp chính xác pixel-level
    #   5) 1 WARP DUY NHẤT từ ảnh gốc đến tâm markers
    if paper is not None:
        ordered_paper = order_points(paper)
        img_h, img_w = image.shape[:2]
        gray_orig = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY) \
            if len(image.shape) == 3 else image.copy()
        
        # Tâm giấy — dùng để xác định hướng "vào trong"
        paper_center_x = np.mean(ordered_paper[:, 0])
        paper_center_y = np.mean(ordered_paper[:, 1])

        paper_w = np.linalg.norm(ordered_paper[1] - ordered_paper[0])
        paper_h = np.linalg.norm(ordered_paper[3] - ordered_paper[0])

        # [TEMPLATE-AWARE] QM 2025: corner markers nằm CÁCH mép giấy ~4% về
        # phía trong. Search ROI CENTER PHẢI là điểm kỳ vọng của marker, KHÔNG
        # phải paper corner. Bán kính ROI ±3% đủ để bắt marker với perspective
        # biến thiên vừa phải.
        #
        # Layout QM 2025 (từ ảnh template):
        #   Paper edge -> 4%% white margin -> 2%% marker size -> form content
        #   Vậy marker CENTER ≈ paper_corner + 5%% về phía tâm
        INSET_RATIO = 0.05  # marker center inset 5% từ paper corner
        SEARCH_RADIUS_RATIO = 0.035  # ±3.5% quanh vị trí kỳ vọng
        inset_dist = int(min(paper_w, paper_h) * INSET_RATIO)
        search_r = max(20, int(min(paper_w, paper_h) * SEARCH_RADIUS_RATIO))

        marker_centers = []
        marker_sizes = []
        marker_results = []  # [(found_bool, corner_idx)] để log
        for i, corner_pt in enumerate(ordered_paper):
            cx_paper = int(corner_pt[0])
            cy_paper = int(corner_pt[1])

            # Hướng "vào trong" giấy
            dx_sign = int(np.sign(paper_center_x - cx_paper))
            dy_sign = int(np.sign(paper_center_y - cy_paper))

            # [FIX] Vị trí kỳ vọng của marker = paper_corner + inset về phía tâm
            mx_expected = cx_paper + dx_sign * inset_dist
            my_expected = cy_paper + dy_sign * inset_dist

            # ROI đối xứng quanh vị trí kỳ vọng
            x1 = max(0, mx_expected - search_r)
            x2 = min(img_w, mx_expected + search_r)
            y1 = max(0, my_expected - search_r)
            y2 = min(img_h, my_expected + search_r)

            roi = gray_orig[y1:y2, x1:x2]
            if roi.size == 0:
                marker_results.append((False, i))
                continue

            # Tọa độ "tâm ROI = vị trí kỳ vọng marker" trong hệ ROI
            cx_in_roi = mx_expected - x1
            cy_in_roi = my_expected - y1
            marker = _find_marker_near_corner(roi, cx_in_roi, cy_in_roi)
            if marker is None:
                marker_results.append((False, i))
                continue

            marker_x = x1 + marker[0]
            marker_y = y1 + marker[1]
            marker_size = marker[2] if len(marker) >= 3 else 0
            marker_centers.append([float(marker_x), float(marker_y)])
            marker_sizes.append(marker_size)
            marker_results.append((True, i))

        # [AZOTA-INSIGHT] Size consistency check: 4 markers đều là CÙNG 1
        # symbol in trên giấy → phải có kích thước GẦN GIỐNG NHAU.
        # Nếu 1 marker lớn/nhỏ bất thường so với 3 cái kia → đó là NOISE
        # (text, bóng, nếp gấp) bị nhầm → reject toàn bộ detection.
        size_consistent = True
        if len(marker_sizes) == 4 and all(s > 0 for s in marker_sizes):
            s_arr = np.array(marker_sizes, dtype=float)
            s_median = float(np.median(s_arr))
            if s_median > 0:
                # Mọi marker phải nằm trong 0.5x .. 2.0x median size
                deviations = s_arr / s_median
                if np.any(deviations < 0.5) or np.any(deviations > 2.0):
                    size_consistent = False
                    print(f"  [C] paper+markers: size inconsistent "
                          f"(sizes={marker_sizes}, median={s_median:.0f}) → reject")

        if not size_consistent:
            # Force skip — clear markers để fallback về method A/B
            marker_centers = []
        
        if len(marker_centers) == 4:
            markers_orig = order_points(
                np.array(marker_centers, dtype="float32"))
            
            # Validate: markers phải tạo hình chữ nhật hợp lệ
            if _validate_marker_quad(markers_orig, img_w, img_h):
                # 1 WARP DUY NHẤT từ ảnh gốc dùng tâm markers
                warped_c = _warp_to_rect(image, markers_orig)
                
                # Score (KHÔNG refine thêm — đã chính xác pixel-level)
                score_c, sharp_c, _ = _score_warp_quality(
                    warped_c, "paper+markers", markers_orig)
                # [IMPROVE] Bonus LỚN cho paper+markers vì markers chính xác hơn paper_contour
                # Paper_contour có thể bắt cả background (bàn phím, bàn gỗ...)
                # nên paper+markers cần bonus đủ lớn để luôn thắng
                sym_c = _quad_symmetry(markers_orig)
                if sym_c > 0.97:
                    score_c += 15.0
                    bonus_c = f"+15 cross-validate, sym={sym_c:.3f}"
                elif sym_c > 0.94:
                    score_c += 10.0
                    bonus_c = f"+10 cross-validate, sym={sym_c:.3f}"
                elif sym_c > 0.90:
                    score_c += 5.0
                    bonus_c = f"+5 cross-validate, sym={sym_c:.3f}"
                else:
                    bonus_c = f"no bonus, sym={sym_c:.3f} (suspicious)"
                candidates.append((score_c, sharp_c, warped_c, markers_orig,
                                   "paper+markers"))
                try:
                    print(f"  [C] paper+markers -> {score_c:.1f} ({bonus_c})")
                except Exception:
                    pass
            else:
                try:
                    print(f"  [C] paper+markers: quad invalid -> skip")
                except Exception:
                    pass
        else:
            corner_names = ["TL", "TR", "BR", "BL"]  # Top-Left, Top-Right, ...
            failed_corners = [corner_names[i] for found, i in marker_results if not found]
            try:
                print(f"  [C] paper+markers: only {len(marker_centers)}/4 markers -> skip"
                      f" (failed: {','.join(failed_corners) if failed_corners else 'none'})")
            except Exception:
                pass

    # ─── Chọn kết quả tốt nhất ───
    if not candidates:
        raise ValueError("Không tìm được viền giấy lẫn 4 góc đen.")

    # Sort by score desc
    candidates.sort(key=lambda x: x[0], reverse=True)

    # [FIX] Tie-breaker dựa trên SYMMETRY thay vì sharpness.
    # Sharpness đã được tính 40% trong score rồi — không cần đếm 2 lần.
    # Symmetry cao hơn = quad chuẩn hơn = warp ít skew hơn.
    if len(candidates) > 1:
        top = candidates[0]
        runner = candidates[1]
        if abs(top[0] - runner[0]) < 2.0:
            sym_top = _quad_symmetry(top[3])
            sym_runner = _quad_symmetry(runner[3])
            if sym_runner > sym_top + 0.01:
                print(f"  [TIE-BREAK] scores within 2pts, "
                      f"picking {runner[4]} (more symmetric: "
                      f"{sym_runner:.3f} > {sym_top:.3f})")
                candidates[0], candidates[1] = candidates[1], candidates[0]

    best_score, best_sharp, best_warped, best_corners, best_method = candidates[0]

    if len(candidates) > 1:
        print(f"  [PICK] {best_method} ({best_score:.1f}) "
              f"over {candidates[1][4]} ({candidates[1][0]:.1f})")

    if debug_img is not None:
        _draw_debug(debug_img, best_corners, None, best_method.upper(),
                    (0, 165, 255))

    result = _result(best_warped, best_corners, best_method, True, debug_img)
    # Lưu danh sách tất cả candidates để process_sheet có thể thử lại
    result["_candidates"] = candidates
    return result


def _validate_marker_quad(ordered, img_w, img_h):
    """
    Kiểm tra 4 marker [TL, TR, BR, BL] có tạo thành hình chữ nhật hợp lệ:
    1) Convex
    2) Aspect ratio gần A4 (0.55 - 0.90)
    3) Cạnh đối diện không chênh quá 40%
    4) Chiếm >= 15% diện tích ảnh (tránh marker quá gần nhau)
    5) Góc trong hợp lý (60° - 120°)
    """
    tl, tr, br, bl = ordered
    # Cạnh
    w_top = np.linalg.norm(tr - tl)
    w_bot = np.linalg.norm(br - bl)
    h_left = np.linalg.norm(bl - tl)
    h_right = np.linalg.norm(br - tr)

    avg_w = (w_top + w_bot) / 2
    avg_h = (h_left + h_right) / 2
    if avg_w == 0 or avg_h == 0:
        return False

    # Aspect ratio: A4 dọc ≈ 0.707 (210/297mm)
    aspect = min(avg_w, avg_h) / max(avg_w, avg_h)
    if aspect < 0.62 or aspect > 0.85:
        return False

    # Cạnh đối diện không chênh quá 40%
    if w_top > 0 and w_bot > 0:
        if min(w_top, w_bot) / max(w_top, w_bot) < 0.60:
            return False
    if h_left > 0 and h_right > 0:
        if min(h_left, h_right) / max(h_left, h_right) < 0.60:
            return False

    # Diện tích quad >= 15% ảnh
    quad_area = cv2.contourArea(ordered)
    img_area = img_w * img_h
    if quad_area / img_area < 0.15:
        return False

    # Góc trong hợp lý (60° - 120°)
    for i in range(4):
        p1 = ordered[i]
        p2 = ordered[(i + 1) % 4]
        p3 = ordered[(i + 2) % 4]
        v1 = p1 - p2
        v2 = p3 - p2
        cos_a = np.dot(v1, v2) / (np.linalg.norm(v1) * np.linalg.norm(v2) + 1e-8)
        angle = np.degrees(np.arccos(np.clip(cos_a, -1, 1)))
        if angle < 55 or angle > 125:
            return False

    return True


def _result(warped, corners, method, success, debug_img):
    """Helper tạo dict kết quả chuẩn."""
    return {
        "warped": warped,
        "corners": corners,
        "method": method,
        "success": success,
        "debug_image": debug_img,
    }


def _draw_debug(debug_img, paper_pts, marker_pts, label, color):
    """Vẽ thông tin debug lên ảnh gốc."""
    # Viền giấy (xanh lá)
    cv2.drawContours(debug_img, [paper_pts.astype(int)], -1, (0, 255, 0), 3)
    for pt in paper_pts:
        cx, cy = int(pt[0]), int(pt[1])
        box_half = 12
        cv2.rectangle(debug_img, (cx - box_half, cy - box_half),
                      (cx + box_half, cy + box_half), (0, 0, 255), 2)
    # Markers nếu có (cam)
    if marker_pts is not None:
        for pt in marker_pts:
            cv2.circle(debug_img, (int(pt[0]), int(pt[1])), 8, (0, 165, 255), -1)
    # Label
    y_lbl = max(15, int(paper_pts[0][1]) - 15)
    cv2.putText(debug_img, label, (int(paper_pts[0][0]), y_lbl),
                cv2.FONT_HERSHEY_SIMPLEX, 1.0, color, 2)


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
#  LỚP 1: CORNER MARKERS — tìm 4 ô vuông đen ở 4 góc phiếu
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

def _find_corner_markers(image, debug_img=None,
                          min_ratio=_MARKER_MIN_AREA_RATIO,
                          max_ratio=_MARKER_MAX_AREA_RATIO):
    """
    Tìm 4 ô vuông đen ở 4 góc phiếu.
    Thử adaptive → simple threshold.
    Trả về 4 điểm float32 hoặc None.
    """
    # [CHAMTN TOURNAMENT] Ưu tiên thuật toán Directional Tournament từ ChamTN
    # Triệt tiêu hoàn toàn nhiễu từ sàn gạch hoa văn, bàn gỗ phức tạp
    try:
        from chamtn_core import ChamTNEngine
        chamtn_quad = ChamTNEngine.find_corner_markers(image)
        if chamtn_quad is not None and len(chamtn_quad) == 4:
            return chamtn_quad.astype(np.float32)
    except Exception:
        pass

    gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
    h, w = image.shape[:2]
    min_a = (w * h) * min_ratio
    max_a = (w * h) * max_ratio

    all_sq = []

    # [IMPROVE] Preprocessing mạnh hơn cho ảnh phone camera
    # 1) Bilateral filter: giữ edge, giảm noise
    bilateral = cv2.bilateralFilter(gray, 9, 75, 75)
    # 2) CLAHE: tăng contrast cục bộ
    clahe = cv2.createCLAHE(clipLimit=2.0, tileGridSize=(8, 8))
    enhanced = clahe.apply(bilateral)
    blurred = cv2.GaussianBlur(enhanced, (5, 5), 0)

    # Chiến lược 1: Adaptive threshold (chịu ánh sáng không đều)
    at = cv2.adaptiveThreshold(blurred, 255, cv2.ADAPTIVE_THRESH_GAUSSIAN_C,
                               cv2.THRESH_BINARY_INV, 31, 10)
    all_sq.extend(_extract_squares(at, min_a, max_a))

    # [IMPROVE] Chiến lược 1b: Adaptive threshold với block lớn hơn (cho ảnh phone)
    if len(all_sq) < 4:
        at2 = cv2.adaptiveThreshold(blurred, 255, cv2.ADAPTIVE_THRESH_GAUSSIAN_C,
                                    cv2.THRESH_BINARY_INV, 51, 12)
        for s in _extract_squares(at2, min_a, max_a):
            if not any(abs(s[0]-e[0]) < 30 and abs(s[1]-e[1]) < 30
                       for e in all_sq):
                all_sq.append(s)

    # Chiến lược 2: Simple threshold (nhiều mức)
    if len(all_sq) < 4:
        for tval in [50, 60, 80, 100, 120, 140]:
            _, st = cv2.threshold(blurred, tval, 255, cv2.THRESH_BINARY_INV)
            for s in _extract_squares(st, min_a, max_a):
                if not any(abs(s[0]-e[0]) < 30 and abs(s[1]-e[1]) < 30
                           for e in all_sq):
                    all_sq.append(s)

    # [IMPROVE] Chiến lược 3: Otsu threshold (tự chọn ngưỡng tối ưu)
    if len(all_sq) < 4:
        _, otsu = cv2.threshold(blurred, 0, 255,
                                cv2.THRESH_BINARY_INV + cv2.THRESH_OTSU)
        for s in _extract_squares(otsu, min_a, max_a):
            if not any(abs(s[0]-e[0]) < 30 and abs(s[1]-e[1]) < 30
                       for e in all_sq):
                all_sq.append(s)

    if len(all_sq) < 4:
        return None

    # Chọn 4 ứng viên gần 4 góc ảnh nhất
    all_sq.sort(key=lambda s: s[2], reverse=True)
    cands = np.array([(s[0], s[1]) for s in all_sq[:30]], dtype="float32")
    corners = _greedy_assign_corners(cands, w, h)

    if debug_img is not None:
        for pt in corners:
            cv2.circle(debug_img, (int(pt[0]), int(pt[1])), 10, (255, 0, 0), -1)
        cv2.putText(debug_img, "MARKERS", (int(corners[0][0]),
                    max(15, int(corners[0][1]) - 15)),
                    cv2.FONT_HERSHEY_SIMPLEX, 1.0, (255, 0, 0), 2)
    
    # IMPROVEMENT 4: Sub-pixel corner refinement using cornerSubPix
    try:
        corners_float = np.float32(corners)
        criteria = (cv2.TERM_CRITERIA_EPS + cv2.TERM_CRITERIA_MAX_ITER, 30, 0.01)
        corners_refined = cv2.cornerSubPix(blurred, corners_float, (5, 5), (-1, -1), criteria)
        corners = corners_refined
    except Exception:
        pass  # If subpixel fails, use original corners
    
    return corners


def _extract_squares(thresh_img, min_a, max_a):
    """Tìm hình vuông đen trong ảnh binary. Trả về list (cx, cy, area)."""
    cnts, _ = cv2.findContours(thresh_img, cv2.RETR_EXTERNAL,
                               cv2.CHAIN_APPROX_SIMPLE)
    result = []
    for c in cnts:
        area = cv2.contourArea(c)
        if area < min_a or area > max_a:
            continue
        peri = cv2.arcLength(c, True)
        approx = cv2.approxPolyDP(c, 0.04 * peri, True)
        if 4 <= len(approx) <= 6:
            x, y, bw, bh = cv2.boundingRect(approx)
            asp = bw / float(bh) if bh > 0 else 0
            if 0.45 < asp < 2.2:  # Rộng hơn cho perspective phone
                result.append((x + bw // 2, y + bh // 2, area))
    return result


def _greedy_assign_corners(candidates, img_w, img_h):
    """Gán mỗi góc ảnh cho ứng viên gần nhất (greedy, không trùng)."""
    targets = np.array([
        [0, 0], [img_w, 0], [img_w, img_h], [0, img_h]
    ], dtype="float32")
    chosen = []
    used = set()
    for t in targets:
        best_i, best_d = -1, float("inf")
        for i, c in enumerate(candidates):
            if i in used:
                continue
            d = np.linalg.norm(c - t)
            if d < best_d:
                best_d = d
                best_i = i
        chosen.append(candidates[best_i])
        used.add(best_i)
    return np.array(chosen, dtype="float32")


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
#  LỚP 2: PAPER CONTOUR — tìm viền giấy trắng trên nền bất kỳ
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

def _find_paper_contour(image, debug_img=None):
    """
    Tìm viền giấy bằng nhiều chiến lược song song:
      A) Canny edge (nhiều mức low/high)
      B) Otsu threshold + morphology close
      C) Saturation channel (giấy trắng = saturation thấp)
      D) [IMPROVE] Enhanced preprocessing cho phone camera
    Trả về 4 góc giấy float32 hoặc None.
    """
    h, w = image.shape[:2]
    img_area = h * w
    gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)

    # [IMPROVE] Preprocessing mạnh hơn cho ảnh phone camera
    # Bilateral filter: giữ edge, giảm noise
    bilateral = cv2.bilateralFilter(gray, 9, 75, 75)
    # CLAHE: tăng contrast cục bộ
    clahe = cv2.createCLAHE(clipLimit=2.0, tileGridSize=(8, 8))
    enhanced = clahe.apply(bilateral)

    # Giảm kích thước nếu ảnh quá lớn (tăng tốc + giảm nhiễu)
    scale = 1.0
    if max(h, w) > 2000:
        scale = 2000.0 / max(h, w)
        small = cv2.resize(enhanced, None, fx=scale, fy=scale,
                           interpolation=cv2.INTER_AREA)
    else:
        small = enhanced.copy()

    blurred = cv2.GaussianBlur(small, (7, 7), 0)

    # Thu thập tất cả binary images từ nhiều chiến lược
    binaries = []

    # ── Chiến lược A: Canny edge (nhiều mức) ──
    for lo, hi in [(20, 60), (30, 100), (50, 150), (75, 200)]:
        edges = cv2.Canny(blurred, lo, hi)
        k = cv2.getStructuringElement(cv2.MORPH_RECT, (7, 7))
        edges = cv2.dilate(edges, k, iterations=2)
        edges = cv2.erode(edges, k, iterations=1)
        binaries.append(edges)

    # ── Chiến lược B: Otsu threshold + morphology close ──
    _, otsu = cv2.threshold(blurred, 0, 255,
                            cv2.THRESH_BINARY_INV + cv2.THRESH_OTSU)
    k_close = cv2.getStructuringElement(cv2.MORPH_RECT, (15, 15))
    closed = cv2.morphologyEx(otsu, cv2.MORPH_CLOSE, k_close, iterations=2)
    binaries.append(closed)

    # [IMPROVE] Chiến lược B2: Otsu trên ảnh enhanced (không blur)
    _, otsu2 = cv2.threshold(small, 0, 255,
                             cv2.THRESH_BINARY_INV + cv2.THRESH_OTSU)
    closed2 = cv2.morphologyEx(otsu2, cv2.MORPH_CLOSE, k_close, iterations=2)
    binaries.append(closed2)

    # ── Chiến lược C: Saturation channel (giấy trắng = S thấp) ──
    hsv_small = cv2.cvtColor(
        cv2.resize(image, None, fx=scale, fy=scale,
                   interpolation=cv2.INTER_AREA)
        if scale < 1.0 else image,
        cv2.COLOR_BGR2HSV
    )
    sat = hsv_small[:, :, 1]
    _, sat_bin = cv2.threshold(sat, 40, 255, cv2.THRESH_BINARY_INV)
    k_sat = cv2.getStructuringElement(cv2.MORPH_RECT, (11, 11))
    sat_bin = cv2.morphologyEx(sat_bin, cv2.MORPH_CLOSE, k_sat, iterations=3)
    sat_bin = cv2.morphologyEx(sat_bin, cv2.MORPH_OPEN, k_sat, iterations=1)
    binaries.append(sat_bin)

    # ── Chiến lược D: Adaptive threshold block lớn ──
    ada = cv2.adaptiveThreshold(blurred, 255, cv2.ADAPTIVE_THRESH_GAUSSIAN_C,
                                cv2.THRESH_BINARY, 51, 5)
    ada_inv = cv2.bitwise_not(ada)
    k_ada = cv2.getStructuringElement(cv2.MORPH_RECT, (15, 15))
    ada_inv = cv2.morphologyEx(ada_inv, cv2.MORPH_CLOSE, k_ada, iterations=3)
    binaries.append(ada_inv)

    # Tìm quad tốt nhất từ tất cả binary images
    best_quad = None
    best_score = -1

    sh, sw = small.shape[:2]
    small_area = sh * sw

    for bimg in binaries:
        quad = _best_quad_from_binary(bimg, small_area)
        if quad is None:
            continue
        score = _score_paper_quad(quad, sw, sh, small_area)
        if score > best_score:
            best_quad = quad
            best_score = score

    if best_quad is None:
        return None

    # Scale ngược về kích thước gốc
    if scale < 1.0:
        best_quad = best_quad / scale

    return best_quad.astype("float32")


def _score_paper_quad(quad, img_w, img_h, img_area):
    """
    Tính điểm cho quad dựa trên:
    - Diện tích (lớn hơn = tốt, nhưng không phải lớn nhất)
    - Aspect ratio gần A4 (0.73) → bonus
    - Phạt nếu góc sát mép ảnh (< 1%) → có thể là cả ảnh, không phải giấy
    - Phạt nếu chiếm > 90% ảnh (quá lớn = bắt cả nền)
    """
    area = cv2.contourArea(quad)
    ratio = area / img_area

    # Base score = normalized area (0-1)
    base = ratio

    # Bonus: aspect ratio gần A4 (0.73)
    ordered = order_points(quad)
    tl, tr, br, bl = ordered
    avg_w = (np.linalg.norm(tr - tl) + np.linalg.norm(br - bl)) / 2
    avg_h = (np.linalg.norm(bl - tl) + np.linalg.norm(br - tr)) / 2
    if avg_w == 0 or avg_h == 0:
        return -1
    aspect = min(avg_w, avg_h) / max(avg_w, avg_h)
    a4_bonus = 1.0 - abs(aspect - 0.73) * 2.0  # Max 1.0 khi aspect=0.73
    a4_bonus = max(0.1, a4_bonus)

    # Phạt: góc sát mép ảnh (< 1% hoặc > 99%)
    edge_margin = 0.01
    edge_penalty = 1.0
    for pt in ordered:
        x_r = pt[0] / img_w if img_w > 0 else 0
        y_r = pt[1] / img_h if img_h > 0 else 0
        if x_r < edge_margin or x_r > (1 - edge_margin):
            edge_penalty *= 0.7
        if y_r < edge_margin or y_r > (1 - edge_margin):
            edge_penalty *= 0.7

    # Phạt quad quá lớn (> 90% ảnh → có thể là toàn bộ ảnh)
    size_penalty = 1.0
    if ratio > 0.90:
        size_penalty = 0.5
    elif ratio > 0.85:
        size_penalty = 0.8

    return base * a4_bonus * edge_penalty * size_penalty


def _best_quad_from_binary(binary, img_area):
    """
    Từ ảnh binary, tìm quadrilateral lớn nhất hợp lệ.
    Trả về quad 4×2 float32 hoặc None.
    """
    cnts, _ = cv2.findContours(binary, cv2.RETR_EXTERNAL,
                               cv2.CHAIN_APPROX_SIMPLE)
    cnts = sorted(cnts, key=cv2.contourArea, reverse=True)

    for cnt in cnts[:15]:
        area = cv2.contourArea(cnt)
        ratio = area / img_area
        if ratio < _PAPER_MIN_AREA_RATIO or ratio > _PAPER_MAX_AREA_RATIO:
            continue

        peri = cv2.arcLength(cnt, True)
        # Thử nhiều epsilon xấp xỉ
        for eps in [0.015, 0.02, 0.03, 0.04, 0.06, 0.08]:
            approx = cv2.approxPolyDP(cnt, eps * peri, True)
            if len(approx) == 4:
                quad = approx.reshape(4, 2).astype("float32")
                if _is_valid_quad(quad, img_area):
                    return quad
                break  # Đã tìm được 4 cạnh, không thử eps khác

        # Nếu approxPolyDP không ra 4 điểm, thử convexHull + minAreaRect
        if len(approx) != 4:
            hull = cv2.convexHull(cnt)
            rect = cv2.minAreaRect(hull)
            box = cv2.boxPoints(rect).astype("float32")
            box_area = cv2.contourArea(box)
            if box_area / img_area >= _PAPER_MIN_AREA_RATIO:
                if _is_valid_quad(box, img_area):
                    return box

    return None


def _is_valid_quad(quad, img_area):
    """
    Kiểm tra tứ giác có hợp lệ làm viền giấy:
    - Diện tích hợp lý
    - Convex
    - Tỷ lệ cạnh hợp lý (phiếu A4)
    - Cạnh đối diện không chênh quá nhiều
    - Góc trong hợp lý (60°–120°)
    """
    area = cv2.contourArea(quad)
    ratio = area / img_area
    if ratio < _PAPER_MIN_AREA_RATIO or ratio > _PAPER_MAX_AREA_RATIO:
        return False

    if not cv2.isContourConvex(quad):
        return False

    ordered = order_points(quad)
    tl, tr, br, bl = ordered
    w_top = np.linalg.norm(tr - tl)
    w_bot = np.linalg.norm(br - bl)
    h_left = np.linalg.norm(bl - tl)
    h_right = np.linalg.norm(br - tr)

    avg_w = (w_top + w_bot) / 2
    avg_h = (h_left + h_right) / 2
    if avg_w == 0 or avg_h == 0:
        return False

    # Tỷ lệ khung
    aspect = min(avg_w, avg_h) / max(avg_w, avg_h)
    if aspect < _PAPER_ASPECT_MIN:
        return False

    # Cạnh đối diện không chênh quá nhiều
    if w_top > 0 and w_bot > 0:
        if min(w_top, w_bot) / max(w_top, w_bot) < _PAPER_SIDE_RATIO_MIN:
            return False
    if h_left > 0 and h_right > 0:
        if min(h_left, h_right) / max(h_left, h_right) < _PAPER_SIDE_RATIO_MIN:
            return False

    # Kiểm tra góc trong (tránh quad quá méo)
    for i in range(4):
        p1 = ordered[i]
        p2 = ordered[(i + 1) % 4]
        p3 = ordered[(i + 2) % 4]
        v1 = p1 - p2
        v2 = p3 - p2
        cos_a = np.dot(v1, v2) / (np.linalg.norm(v1) * np.linalg.norm(v2) + 1e-8)
        angle = np.degrees(np.arccos(np.clip(cos_a, -1, 1)))
        if angle < 50 or angle > 140:
            return False

    return True


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
#  REFINEMENT — tìm corner markers trên ảnh warped trung gian
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

def _refine_with_markers(warped_raw):
    """Fallback: tìm markers bằng global contour. Giữ lại cho tương thích."""
    h, w = warped_raw.shape[:2]
    markers = _find_corner_markers(
        warped_raw, debug_img=None,
        min_ratio=_REFINE_MARKER_MIN, max_ratio=_REFINE_MARKER_MAX
    )
    if markers is None:
        return None
    ordered = order_points(markers)
    if not _validate_corner_positions(ordered, w, h):
        return None
    return ordered


def _refine_targeted(warped_raw):
    """
    Tìm 4 corner markers bằng TARGETED LOCAL SEARCH (SullyChen-inspired).

    Thay vì tìm global (nhiều false positive), chỉ tìm trong vùng góc.
    Kết hợp: contour detection + template matching.

    Trả về 4 góc ordered hoặc None.
    """
    gray = cv2.cvtColor(warped_raw, cv2.COLOR_BGR2GRAY) \
        if len(warped_raw.shape) == 3 else warped_raw.copy()
    h, w = gray.shape[:2]

    # Vùng tìm kiếm: 15% width, 8% height từ mỗi góc
    mx = int(w * 0.15)
    my = int(h * 0.08)

    corner_rois = [
        (0,      0,      mx, my),       # TL
        (w - mx, 0,      w,  my),       # TR
        (w - mx, h - my, w,  h),        # BR
        (0,      h - my, mx, h),        # BL
    ]

    found = []
    for (x1, y1, x2, y2) in corner_rois:
        roi = gray[y1:y2, x1:x2]
        marker = _find_marker_in_roi(roi)
        if marker is not None:
            found.append((x1 + marker[0], y1 + marker[1]))

    if len(found) != 4:
        return None

    ordered = order_points(np.array(found, dtype="float32"))
    if not _validate_corner_positions(ordered, w, h):
        return None

    return ordered


def _find_marker_near_corner(roi_gray, corner_x_in_roi, corner_y_in_roi):
    """
    Tìm ô vuông đen (corner marker) trong ROI, ƯU TIÊN vị trí GẦN góc paper.
    
    Giống _find_marker_in_roi nhưng thêm proximity scoring:
    - Marker xa góc paper > 40px bị phạt nặng
    - Ưu tiên ô vuông nhỏ, đặc (15-25px) gần mép giấy
    
    corner_x_in_roi, corner_y_in_roi: tọa độ góc paper trong hệ ROI
    Returns (cx, cy, size) hoặc None. size = cạnh bounding box (px) để
    caller kiểm tra consistency giữa 4 markers.
    """
    rh, rw = roi_gray.shape[:2]
    if rh < 15 or rw < 15:
        return None

    best_center = None
    best_size = 0
    best_score = 0

    # [REVERT] Giữ threshold conservative 50-150 để tránh bắt noise nhẹ
    # (threshold < 50 sẽ bắt cả text in nhạt, chữ ký, smudge → false marker).
    # Otsu được thêm để adapt với lighting biến thiên.
    threshold_values = [50, 70, 90, 110, 130, 150]
    otsu_val, _ = cv2.threshold(roi_gray, 0, 255,
                                cv2.THRESH_BINARY_INV + cv2.THRESH_OTSU)
    if 50 <= otsu_val <= 180:
        threshold_values.append(int(otsu_val))

    for tval in threshold_values:
        _, binary = cv2.threshold(roi_gray, tval, 255, cv2.THRESH_BINARY_INV)
        contours, _ = cv2.findContours(binary, cv2.RETR_EXTERNAL,
                                       cv2.CHAIN_APPROX_SIMPLE)
        for cnt in contours:
            area = cv2.contourArea(cnt)
            # Marker trên ảnh gốc: 60-2000px² (nhỏ hơn trên warped)
            if area < 40 or area > 3000:
                continue
            x, y, bw, bh = cv2.boundingRect(cnt)
            asp = bw / float(bh) if bh > 0 else 0
            if 0.45 < asp < 2.2:
                fill = area / (bw * bh) if bw * bh > 0 else 0
                if fill < 0.5:
                    continue
                squareness = 1.0 - abs(asp - 1.0) * 0.5
                
                # Tâm contour
                mcx = x + bw // 2
                mcy = y + bh // 2
                
                # Khoảng cách đến TÂM ROI (= vị trí kỳ vọng của marker)
                dist = np.sqrt((mcx - corner_x_in_roi)**2 + 
                               (mcy - corner_y_in_roi)**2)
                
                # [TEMPLATE-AWARE] Caller đã center ROI vào vị trí kỳ vọng
                # của marker rồi, nên marker thật sẽ nằm GẦN TÂM ROI nhất.
                #   dist < 25px  : trúng vị trí → bonus tối đa 1.0
                #   25-50px      : chấp nhận được → giảm dần
                #   > 50px       : quá xa kỳ vọng → giảm mạnh
                if dist < 25:
                    proximity = 1.0
                elif dist <= 50:
                    proximity = 1.0 - (dist - 25) / 100.0  # 1.0 → 0.75
                else:
                    proximity = max(0.2, 0.75 - (dist - 50) / 100.0)
                
                score = area * squareness * fill * proximity
                if score > best_score:
                    best_score = score
                    best_center = (mcx, mcy)
                    best_size = max(bw, bh)

    if best_center is not None:
        return (best_center[0], best_center[1], best_size)

    # ── [UnT-STYLE] _reDetectPoints: Retry with different preprocessing ──
    # UnT Dạy Học retries corner detection with different params when initial
    # detection fails. We replicate this with CLAHE+dilate and adaptive threshold.
    retry_configs = [
        # (CLAHE clipLimit, dilate iterations, adaptive blockSize, adaptive C)
        (3.0, 1, 25, 8),
        (4.0, 2, 35, 6),
        (2.0, 0, 21, 12),
    ]
    for clip_limit, dilate_iters, block_sz, adapt_c in retry_configs:
        # CLAHE preprocessing (UnT uses CLAHE instead of equalizeHist)
        clahe_retry = cv2.createCLAHE(clipLimit=clip_limit, tileGridSize=(4, 4))
        enhanced_roi = clahe_retry.apply(roi_gray)
        
        # Optional dilate to thicken marker edges
        if dilate_iters > 0:
            dk = cv2.getStructuringElement(cv2.MORPH_RECT, (3, 3))
            enhanced_roi = cv2.dilate(enhanced_roi, dk, iterations=dilate_iters)
        
        # Adaptive threshold (different from simple threshold above)
        if block_sz % 2 == 0:
            block_sz += 1
        binary_retry = cv2.adaptiveThreshold(
            enhanced_roi, 255, cv2.ADAPTIVE_THRESH_GAUSSIAN_C,
            cv2.THRESH_BINARY_INV, block_sz, adapt_c)
        
        contours_retry, _ = cv2.findContours(
            binary_retry, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
        
        for cnt in contours_retry:
            area = cv2.contourArea(cnt)
            if area < 40 or area > 3000:
                continue
            x, y, bw, bh = cv2.boundingRect(cnt)
            asp = bw / float(bh) if bh > 0 else 0
            if 0.45 < asp < 2.2:
                fill = area / (bw * bh) if bw * bh > 0 else 0
                if fill < 0.5:
                    continue
                squareness = 1.0 - abs(asp - 1.0) * 0.5
                mcx = x + bw // 2
                mcy = y + bh // 2
                dist = np.sqrt((mcx - corner_x_in_roi)**2 + 
                               (mcy - corner_y_in_roi)**2)
                if dist < 25:
                    proximity = 1.0
                elif dist <= 50:
                    proximity = 1.0 - (dist - 25) / 100.0
                else:
                    proximity = max(0.2, 0.75 - (dist - 50) / 100.0)
                
                score = area * squareness * fill * proximity
                if score > best_score:
                    best_score = score
                    best_center = (mcx, mcy)
                    best_size = max(bw, bh)
        
        if best_center is not None:
            return (best_center[0], best_center[1], best_size)

    # Fallback: Template matching (giữ nguyên)
    for tsize in [16, 20, 24]:
        pad = 5
        tmpl = np.ones((tsize + pad * 2, tsize + pad * 2), dtype=np.uint8) * 200
        tmpl[pad:pad + tsize, pad:pad + tsize] = 30

        if rh < tmpl.shape[0] or rw < tmpl.shape[1]:
            continue

        result = cv2.matchTemplate(roi_gray, tmpl, cv2.TM_CCOEFF_NORMED)
        _, max_val, _, max_loc = cv2.minMaxLoc(result)

        if max_val > 0.35:
            return (max_loc[0] + tmpl.shape[1] // 2,
                    max_loc[1] + tmpl.shape[0] // 2,
                    tsize)

    return None


def _find_marker_in_roi(roi_gray):
    """
    Tìm ô vuông đen (corner marker) trong ROI nhỏ.

    2 phương pháp:
      1) Contour detection (multi-threshold)
      2) Template matching (SullyChen-inspired) — fallback

    Returns (cx, cy) hoặc None.
    """
    rh, rw = roi_gray.shape[:2]
    if rh < 15 or rw < 15:
        return None

    # --- Method 1: Contour detection (nhiều ngưỡng) ---
    best_center = None
    best_score = 0

    # Threshold conservative 50-150 + Otsu adaptive.
    threshold_values = [50, 70, 90, 110, 130, 150]
    otsu_val, _ = cv2.threshold(roi_gray, 0, 255,
                                cv2.THRESH_BINARY_INV + cv2.THRESH_OTSU)
    if 50 <= otsu_val <= 180:
        threshold_values.append(int(otsu_val))

    for tval in threshold_values:
        _, binary = cv2.threshold(roi_gray, tval, 255, cv2.THRESH_BINARY_INV)
        contours, _ = cv2.findContours(binary, cv2.RETR_EXTERNAL,
                                       cv2.CHAIN_APPROX_SIMPLE)
        for cnt in contours:
            area = cv2.contourArea(cnt)
            if area < 60 or area > 4000:
                continue
            x, y, bw, bh = cv2.boundingRect(cnt)
            asp = bw / float(bh) if bh > 0 else 0
            if 0.45 < asp < 2.2:
                # Fill ratio: contourArea / boundingRectArea (vuông đặc ≈ 0.8+)
                fill = area / (bw * bh) if bw * bh > 0 else 0
                if fill < 0.5:
                    continue
                squareness = 1.0 - abs(asp - 1.0) * 0.5
                score = area * squareness * fill
                if score > best_score:
                    best_score = score
                    best_center = (x + bw // 2, y + bh // 2)

    if best_center is not None:
        return best_center

    # --- Method 2: Template matching (SullyChen-inspired) ---
    for tsize in [16, 20, 24]:
        pad = 5
        tmpl = np.ones((tsize + pad * 2, tsize + pad * 2), dtype=np.uint8) * 200
        tmpl[pad:pad + tsize, pad:pad + tsize] = 30

        if rh < tmpl.shape[0] or rw < tmpl.shape[1]:
            continue

        result = cv2.matchTemplate(roi_gray, tmpl, cv2.TM_CCOEFF_NORMED)
        _, max_val, _, max_loc = cv2.minMaxLoc(result)

        if max_val > 0.35:
            return (max_loc[0] + tmpl.shape[1] // 2,
                    max_loc[1] + tmpl.shape[0] // 2)

    return None


def _validate_corner_positions(ordered_pts, img_w, img_h):
    """
    Kiểm tra 4 điểm [TL, TR, BR, BL] có ở gần 4 góc ảnh:
    1) Span tổng ≥ _REFINE_MIN_SPAN
    2) Mỗi điểm trong _REFINE_MARGIN % từ góc tương ứng
    """
    tl, tr, br, bl = ordered_pts
    xs = [tl[0], tr[0], br[0], bl[0]]
    ys = [tl[1], tr[1], br[1], bl[1]]

    span_w = (max(xs) - min(xs)) / img_w if img_w > 0 else 0
    span_h = (max(ys) - min(ys)) / img_h if img_h > 0 else 0
    if span_w < _REFINE_MIN_SPAN or span_h < _REFINE_MIN_SPAN:
        return False

    mx = img_w * _REFINE_MARGIN
    my = img_h * _REFINE_MARGIN
    expected = [(0, 0), (img_w, 0), (img_w, img_h), (0, img_h)]
    for pt, (ex, ey) in zip([tl, tr, br, bl], expected):
        if abs(pt[0] - ex) > mx or abs(pt[1] - ey) > my:
            return False

    return True


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
#  WARP HELPER + COMPATIBILITY WRAPPERS
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

def _warp_to_rect(image, corners):
    """Nắn ảnh nghiêng → hình chữ nhật WARP_WIDTH × WARP_HEIGHT."""
    dst = np.array([
        [0, 0], [WARP_WIDTH - 1, 0],
        [WARP_WIDTH - 1, WARP_HEIGHT - 1], [0, WARP_HEIGHT - 1]
    ], dtype="float32")
    M = cv2.getPerspectiveTransform(corners, dst)
    return cv2.warpPerspective(image, M, (WARP_WIDTH, WARP_HEIGHT))


def _quad_symmetry(corners):
    """
    Đo độ đối xứng của quad 4 góc [TL, TR, BR, BL] (ordered).
    Returns giá trị 0-1, với 1 = hoàn hảo (hình chữ nhật đều).
    Dùng để phát hiện false positive (quad bất đối xứng → detect sai).
    """
    tl, tr, br, bl = corners
    w_top = np.linalg.norm(tr - tl)
    w_bot = np.linalg.norm(br - bl)
    h_left = np.linalg.norm(bl - tl)
    h_right = np.linalg.norm(br - tr)
    if min(w_top, w_bot, h_left, h_right) <= 0:
        return 0.0
    w_sym = min(w_top, w_bot) / max(w_top, w_bot)
    h_sym = min(h_left, h_right) / max(h_left, h_right)
    return float((w_sym + h_sym) / 2.0)


def _map_warped_to_original(refined_pts, original_corners):
    """
    Map tọa độ từ warped space (1400×1920) ngược về ảnh gốc.

    Dùng nghịch đảo ma trận perspective để tránh double-warp.
    refined_pts:      4 điểm ordered trong warped space
    original_corners: 4 góc ordered dùng cho warp ban đầu
    Returns: 4 điểm tương ứng trên ảnh gốc (float32, ordered)
    """
    dst = np.array([
        [0, 0], [WARP_WIDTH - 1, 0],
        [WARP_WIDTH - 1, WARP_HEIGHT - 1], [0, WARP_HEIGHT - 1]
    ], dtype="float32")
    M = cv2.getPerspectiveTransform(original_corners, dst)
    M_inv = np.linalg.inv(M)
    pts = refined_pts.reshape(-1, 1, 2).astype("float64")
    mapped = cv2.perspectiveTransform(pts, M_inv)
    return order_points(mapped.reshape(-1, 2).astype("float32"))


# Alias cho code cũ — detect_paper_and_warp gọi auto_deskew_and_crop
def detect_paper_and_warp(image, debug=False):
    """Alias tương thích: gọi auto_deskew_and_crop."""
    return auto_deskew_and_crop(image, debug=debug)


def detect_corners(image):
    """Wrapper tương thích: trả về 4 góc [TL, TR, BR, BL]."""
    result = auto_deskew_and_crop(image, debug=False)
    return result["corners"]


def warp_perspective(image, corners):
    """Wrapper tương thích: nắn ảnh từ 4 góc đã cho."""
    return _warp_to_rect(image, corners)


# ╔════════════════════════════════════════════════════════════════════════╗
# ║   LỚP 1: XÓA CHỮ IN TRÊN ẢNH WARPED (Smart Erase + Punch-holes)  ║
# ╚════════════════════════════════════════════════════════════════════════╝

def erase_printed_text(warped_img):
    """
    LỚP 1 (MẠNH NHẤT): Tô TRẮNG chữ in trên ảnh warped TRƯỚC threshold.

    Kỹ thuật punch-holes:
      - Phủ HCN trắng lên TOÀN BỘ vùng text (kể cả chồng lên bubble)
      - Nhưng ĐỤC LỖ TRÒN (punch-holes) tại mỗi bubble center
      - → Text GIỮA các bubble bị xóa triệt để
      - → Bubble được BẢO VỆ nguyên vẹn

    Ưu điểm: có thể phủ vùng rất rộng (y=590-680 cho header ABCD)
    mà KHÔNG mất dữ liệu bubble row 1.
    """
    result = warped_img.copy()
    # Áp dụng pre-computed mask: nơi ERASE_MASK=255 → tô trắng
    result[ERASE_MASK == 255] = [255, 255, 255]
    return result


# ╔════════════════════════════════════════════════════════════════════════╗
# ║   BƯỚC 3: TIỀN XỬ LÝ — 3 LỚP BẢO VỆ                              ║
# ╚════════════════════════════════════════════════════════════════════════╝

def _is_phone_camera(gray_img):
    """Auto-detect if image is from phone camera (vs scanner).
    Phone camera images typically have:
    - Lower contrast (std dev of pixel values)
    - Uneven illumination (high std dev of local means)
    - More noise
    - Lower sharpness
    """
    h, w = gray_img.shape[:2]
    std_val = float(np.std(gray_img))
    # Tính variance cục bộ: chia ảnh thành grid 8x8, so sánh mean các block
    block_h, block_w = h // 8, w // 8
    means = []
    for r in range(8):
        for c in range(8):
            block = gray_img[r*block_h:(r+1)*block_h, c*block_w:(c+1)*block_w]
            means.append(float(np.mean(block)))
    local_std = float(np.std(means))
    
    # [IMPROVE] Thêm sharpness check
    lap_var = cv2.Laplacian(gray_img, cv2.CV_64F).var()
    
    # Phone camera: contrast thấp (std < 70) HOẶC ánh sáng không đều (local_std > 15)
    # HOẶC sharpness thấp (lap_var < 200)
    is_phone = std_val < 70 or local_std > 15 or lap_var < 200
    logger.info(f"Image analysis: global_std={std_val:.1f}, local_std={local_std:.1f}, "
                f"sharpness={lap_var:.1f} → {'PHONE' if is_phone else 'SCAN'}")
    return is_phone


def _live_box_background(gray):
    """Experimental five-box approximation of the sigma=120 background."""
    background = gray
    for width in (185, 185, 185, 187, 187):
        background = cv2.boxFilter(
            background, -1, (width, width), borderType=cv2.BORDER_DEFAULT
        )
    return background


def preprocess(warped, enhance_camera=None, mode="fast", fast_global_background=False):
    """
    Tiền xử lý: trả về ảnh xám (blur) cho detection.

    mode="fast":  simple pipeline — adaptive threshold + opening (nhanh, đủ cho ảnh tốt)
    mode="robust": full pipeline — multi-scale normalization + CLAHE + closing (chậm, cho ảnh khó)
    mode="phone":  enhanced pipeline cho ảnh phone camera (mạnh nhất)

    Pipeline robust (giống Azota-level):
    1) erase_printed_text (punch-hole)
    2) Illumination Flattening (background division)
    3) CLAHE (tăng contrast cục bộ)
    4) Gaussian blur (giảm noise)
    5) Adaptive threshold
    6) Morphological closing + opening
    """
    # --- LỚP 1: erase_printed_text (punch-hole) ---
    warped_clean = erase_printed_text(warped)

    gray_raw = cv2.cvtColor(warped_clean, cv2.COLOR_BGR2GRAY)

    # Auto-detect phone camera nếu không chỉ định
    if enhance_camera is None:
        enhance_camera = _is_phone_camera(gray_raw)

    # [IMPROVE] Nếu phone camera và mode="fast" → tự động upgrade lên "phone"
    if enhance_camera and mode == "fast":
        mode = "phone"
        logger.info("Phone camera detected → upgrading to 'phone' preprocessing mode")

    if mode == "fast":
        # ─── FAST MODE: Azota-style pipeline ───
        # 1) Auto brightness/contrast (like ImageSegment::automaticBrightnessAndContrast)
        # 2) Bilateral filter (preserve edges, like Azota)
        # 3) Adaptive threshold (local, no global blob)
        
        # Step 1: Auto brightness & contrast normalization
        bg = cv2.GaussianBlur(gray_raw, (0, 0), sigmaX=30)
        gray_norm = cv2.divide(gray_raw, bg, scale=255)
        clahe = cv2.createCLAHE(clipLimit=1.5, tileGridSize=(8, 8))
        gray_enhanced = clahe.apply(gray_norm)
        
        # Step 2: Median blur (kill salt-pepper noise dots around bubbles)
        gray_denoised = cv2.medianBlur(gray_enhanced, 3)
        
        # Step 3: Bilateral filter (Azota-style: preserve bubble edges)
        gray = cv2.bilateralFilter(gray_denoised, 5, 75, 75)
        
        # Step 4: Adaptive threshold (Azota-style: local threshold, no blob)
        thresh = cv2.adaptiveThreshold(
            gray, 255, cv2.ADAPTIVE_THRESH_GAUSSIAN_C,
            cv2.THRESH_BINARY, 51, 10
        )
        
        # Step 5: Light morphological opening to remove salt noise
        kernel = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (2, 2))
        cleaned = cv2.morphologyEx(thresh, cv2.MORPH_OPEN, kernel, iterations=1)
        
        # Step 6: Remove small blobs (< 20 pixels)
        contours, _ = cv2.findContours(cleaned, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
        for cnt in contours:
            if cv2.contourArea(cnt) < 20:
                cv2.drawContours(cleaned, [cnt], -1, 0, -1)
        
        return gray, thresh, cleaned

    # ─── PHONE MODE: Enhanced pipeline cho ảnh phone camera ───
    # [v2] Multi-scale illumination + pencil enhancement
    if mode == "phone":
        # Step 1: Non-local means denoising (mạnh hơn median/bilateral)
        gray_denoised = cv2.fastNlMeansDenoising(gray_raw, None, h=10,
                                                   templateWindowSize=7,
                                                   searchWindowSize=21)
        
        # Step 2: MULTI-SCALE illumination flattening
        # Pass 1: sigma=120 — loại gradient LỚN (bóng tay, đèn không đều)
        if fast_global_background:
            try:
                bg_global = _live_box_background(gray_denoised)
            except cv2.error:
                logger.exception("Fast Live background failed; using Gaussian")
                bg_global = cv2.GaussianBlur(gray_denoised, (0, 0), sigmaX=120)
        else:
            bg_global = cv2.GaussianBlur(gray_denoised, (0, 0), sigmaX=120)
        gray_flat = cv2.divide(gray_denoised, bg_global, scale=255)
        # Pass 2: sigma=30 — loại gradient CỤC BỘ (bóng giấy, nếp nhăn)
        bg_local = cv2.GaussianBlur(gray_flat, (0, 0), sigmaX=30)
        gray_norm = cv2.divide(gray_flat, bg_local, scale=255)
        
        # Step 3: Pencil mark enhancement — kéo giãn histogram
        # Nếu ảnh low-contrast (bút chì nhạt), stretch tăng gap tô/rỗng
        p2, p98 = np.percentile(gray_norm, (2, 98))
        if p98 - p2 < 200:  # Contrast thấp → stretch
            gray_norm = np.clip((gray_norm.astype(float) - p2) / max(1, p98 - p2) * 255,
                                0, 255).astype(np.uint8)
        
        # Step 4: CLAHE — tăng contrast cục bộ (clipLimit vừa phải tránh noise)
        clahe = cv2.createCLAHE(clipLimit=2.5, tileGridSize=(8, 8))
        gray_enhanced = clahe.apply(gray_norm)
        
        # Step 5: Bilateral filter (preserve bubble edges, kill noise)
        gray = cv2.bilateralFilter(gray_enhanced, 7, 60, 60)
        
        # Step 6: Adaptive threshold — block size=45 (smaller = tighter local)
        thresh = cv2.adaptiveThreshold(
            gray, 255, cv2.ADAPTIVE_THRESH_GAUSSIAN_C,
            cv2.THRESH_BINARY, 45, 10
        )
        
        # Step 7: Morphological closing (lấp lỗ nhỏ trong bubble tô)
        close_kernel = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (3, 3))
        thresh = cv2.morphologyEx(thresh, cv2.MORPH_CLOSE, close_kernel, iterations=1)
        
        # Step 8: Morphological opening (loại nét mảnh text/noise)
        open_kernel = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (2, 2))
        cleaned = cv2.morphologyEx(thresh, cv2.MORPH_OPEN, open_kernel, iterations=1)
        
        # Step 9: Remove small blobs (< 15 pixels)
        contours, _ = cv2.findContours(cleaned, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
        for cnt in contours:
            if cv2.contourArea(cnt) < 15:
                cv2.drawContours(cleaned, [cnt], -1, 0, -1)
        
        return gray, thresh, cleaned

    # ─── ROBUST MODE: full pipeline ───
    # Làm phẳng nền giấy (Multi-scale Illumination Normalization)
    # GaussianBlur: separable O(n*k) thay O(n*k²) → nhanh
    if enhance_camera:
        bg_large = cv2.GaussianBlur(gray_raw, (0, 0), sigmaX=50)
        gray_norm = cv2.divide(gray_raw, bg_large, scale=255)
    else:
        gray_norm = gray_raw

    bg_small = cv2.GaussianBlur(gray_norm, (0, 0), sigmaX=20)
    flat_gray = cv2.divide(gray_norm, bg_small, scale=255)

    # CLAHE
    clip_limit = 3.0 if enhance_camera else 2.0
    clahe = cv2.createCLAHE(clipLimit=clip_limit, tileGridSize=(8, 8))
    flat_gray = clahe.apply(flat_gray)

    gray = cv2.GaussianBlur(flat_gray, (5, 5), 0)

    block_size = 17 if enhance_camera else 15
    thresh_c = 6 if enhance_camera else 8
    thresh = cv2.adaptiveThreshold(
        gray, 255, cv2.ADAPTIVE_THRESH_GAUSSIAN_C,
        cv2.THRESH_BINARY_INV, block_size, thresh_c
    )

    if enhance_camera:
        close_kernel = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (3, 3))
        thresh = cv2.morphologyEx(thresh, cv2.MORPH_CLOSE, close_kernel, iterations=1)

    kernel = cv2.getStructuringElement(
        cv2.MORPH_ELLIPSE, (MORPH_KERNEL_SIZE, MORPH_KERNEL_SIZE)
    )
    cleaned = cv2.morphologyEx(thresh, cv2.MORPH_OPEN, kernel, iterations=1)

    return gray, thresh, cleaned


def _preprocess_for_bubbles(gray_img):
    """
    [UnT-STYLE] _preProcessCircle — Preprocessing RIÊNG cho bubble detection.
    
    UnT Dạy Học dùng preprocessing khác cho bubble detection vs paper detection:
    - CLAHE (Contrast Limited Adaptive Histogram Eq.) thay vì equalizeHist
    - Dilate nhẹ để lấp lỗ nhỏ trong bubble tô bút chì
    - Morphological close để nối các vùng tô rời rạc
    
    Input: gray image (đã warped, 1400×1920)
    Output: enhanced gray image tối ưu cho bubble fill ratio calculation
    """
    # Step 1: CLAHE — tăng contrast cục bộ mà KHÔNG over-amplify noise
    # (UnT dùng CLAHE clipLimit=2.0, grid=(8,8))
    clahe = cv2.createCLAHE(clipLimit=2.0, tileGridSize=(8, 8))
    enhanced = clahe.apply(gray_img)
    
    # Step 2: Light dilate — thicken pencil marks (bút chì nhạt)
    # UnT dùng dilate 1 iteration với kernel 3×3
    dk = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (3, 3))
    enhanced = cv2.dilate(enhanced, dk, iterations=1)
    
    # Step 3: Bilateral filter — smooth noise nhưng giữ edge bubble
    enhanced = cv2.bilateralFilter(enhanced, 5, 50, 50)
    
    return enhanced


def detect_section_offsets(gray):
    """
    Azota-style: fixed positions, no dynamic offset detection.

    Dynamic offset detection is unreliable for many templates.
    Use fixed template positions instead (like Azota).

    Returns: dict {"part1": 0, "part2": 0, "part3": 0}
    """
    # Disabled: dynamic offset detection causes grid misalignment
    # Azota uses fixed template positions - we do the same
    logger.info("Using fixed template positions (Azota-style) - offset detection disabled")
    return {"part1": 0, "part2": 0, "part3": 0}


def _cluster_1d(values, max_gap):
    """Cluster 1D values by max gap, return cluster centers."""
    if not values:
        return []
    vals = sorted(values)
    clusters = [[vals[0]]]
    for v in vals[1:]:
        if v - clusters[-1][-1] <= max_gap:
            clusters[-1].append(v)
        else:
            clusters.append([v])
    return [int(round(sum(c) / len(c))) for c in clusters]


def detect_part3_offset_from_digits(gray):
    """Estimate Part III vertical offset from digit bubble rows."""
    h, w = gray.shape[:2]

    cols = []
    for blk in PART3_BLOCKS:
        cols.append(blk["sign_x"])
        cols.extend(blk["cols_x"])

    if not cols:
        return None

    x_min = max(0, int(min(cols) - BUBBLE_RADIUS * 3))
    x_max = min(w, int(max(cols) + BUBBLE_RADIUS * 3))
    y_min = max(0, int(PART3_SIGN_Y - BUBBLE_RADIUS * 3))
    y_max = min(h, int(PART3_DIGIT_START_Y + 9 * PART3_DIGIT_STEP_Y + BUBBLE_RADIUS * 3))

    roi = gray[y_min:y_max, x_min:x_max]
    if roi.size == 0:
        return None

    roi_blur = cv2.medianBlur(roi, 5)
    circles = cv2.HoughCircles(
        roi_blur,
        cv2.HOUGH_GRADIENT,
        dp=1,
        minDist=20,
        param1=50,
        param2=25,
        minRadius=8,
        maxRadius=18,
    )
    if circles is None:
        return None

    ys = [int(c[1]) + y_min for c in circles[0]]
    row_centers = _cluster_1d(ys, max_gap=10)
    if not row_centers:
        return None

    digit_rows = [y for y in row_centers if y >= PART3_DIGIT_START_Y - 20]
    if not digit_rows:
        digit_rows = row_centers

    expected_rows = [int(PART3_DIGIT_START_Y + d * PART3_DIGIT_STEP_Y) for d in range(10)]
    offsets = []
    for exp in expected_rows:
        nearest = min(digit_rows, key=lambda y: abs(y - exp))
        if abs(nearest - exp) <= 25:
            offsets.append(nearest - exp)

    if len(offsets) < 4:
        return None

    offset = int(round(float(np.median(offsets))))
    # Clamp to avoid outlier shift from bad circle detection.
    return max(-12, min(12, offset))


def mask_printed_text(thresh_img):
    """
    LỚP 3 (safety net): Tô ĐEN vùng text trên ảnh threshold.
    Cũng dùng ERASE_MASK với punch-holes để bảo vệ bubble.
    """
    result = thresh_img.copy()
    # Nơi ERASE_MASK=255 → tô đen (=0) trên threshold
    result[ERASE_MASK == 255] = 0
    return result


# ╔════════════════════════════════════════════════════════════════════════╗
# ║        BƯỚC 4: KIỂM TRA BUBBLE CÓ ĐƯỢC TÔ ĐEN KHÔNG               ║
# ╚════════════════════════════════════════════════════════════════════════╝

def _azota_check_quarter(roi, rx, ry, inner_radius):
    """Azota CircleAzota::check_quarter_of_circle — phân tích 4 góc phần tư.
    Trả về (n_dark_quarters, quarter_ratios).
    Bubble tô đều: 3-4 quarters dark. Tô nửa/gạch: 1-2 quarters."""
    quarter_ratios = []
    h_roi, w_roi = roi.shape[:2]
    for qy, qx in [(0, 0), (0, 1), (1, 0), (1, 1)]:  # TL, TR, BL, BR
        mask = np.zeros((h_roi, w_roi), dtype=np.uint8)
        cv2.circle(mask, (rx, ry), inner_radius, 255, -1)
        # Zero out other 3 quarters
        if qx == 0:
            mask[:, rx:] = 0
        else:
            mask[:, :rx] = 0
        if qy == 0:
            mask[ry:, :] = 0
        else:
            mask[:ry, :] = 0
        qpix = roi[mask == 255]
        if len(qpix) > 5:
            quarter_ratios.append(float(np.mean(qpix)))
        else:
            quarter_ratios.append(255.0)
    return quarter_ratios


def _azota_is_white_bound(roi, rx, ry, radius):
    """Azota CircleAzota::is_white_bound — kiểm tra viền trắng xung quanh bubble.
    Bubble phải có viền trắng (giấy) bao quanh, không dính text/đường kẻ."""
    h_roi, w_roi = roi.shape[:2]
    ring_mask = np.zeros((h_roi, w_roi), dtype=np.uint8)
    cv2.circle(ring_mask, (rx, ry), radius + 3, 255, -1)
    cv2.circle(ring_mask, (rx, ry), radius, 0, -1)
    ring_pix = roi[ring_mask == 255]
    if len(ring_pix) < 8:
        return True  # Not enough data, assume OK
    ring_mean = float(np.mean(ring_pix))
    ring_dark_ratio = float(np.sum(ring_pix < 128)) / len(ring_pix)
    # Viền quá tối (>40% pixel đen) → dính text/line
    return ring_dark_ratio < 0.40


def is_bubble_filled(gray_img, cx, cy, radius=BUBBLE_RADIUS,
                     threshold=FILL_THRESHOLD, check_circularity=True,
                     adaptive_radius=None):
    """
    Azota-style 6-step bubble verification pipeline.
    
    Pipeline (giống CircleAzota):
    1. can_be_roi        — ROI hợp lệ?
    2. calculate_threshold — Ngưỡng riêng per-bubble (local_white adaptive)
    3. check_is_fill     — Fill ratio check chính
    4. check_quarter     — Phân tích 4 góc phần tư (phát hiện tô 1 nửa)
    5. is_white_bound    — Kiểm tra viền trắng (loại text dính)
    6. check_is_fill_contour — Verify bằng contour + convexity
    """
    h, w = gray_img.shape[:2]
    if adaptive_radius is not None:
        radius = adaptive_radius

    # ═══ STEP 1: can_be_roi — validate ROI ═══
    pad = max(8, int(radius * 0.8))
    x1 = max(0, int(cx - radius - pad))
    y1 = max(0, int(cy - radius - pad))
    x2 = min(w, int(cx + radius + pad))
    y2 = min(h, int(cy + radius + pad))

    roi = gray_img[y1:y2, x1:x2]
    if roi.size == 0 or roi.shape[0] < radius*2 or roi.shape[1] < radius*2:
        return False, 0.0

    rx, ry = int(cx - x1), int(cy - y1)

    # Inner mask (shrink 3px to avoid edge circle border noise)
    inner_radius = max(3, radius - 3)
    bubble_mask = np.zeros(roi.shape[:2], dtype=np.uint8)
    cv2.circle(bubble_mask, (rx, ry), inner_radius, 255, -1)
    bubble_pixels = roi[bubble_mask == 255]
    if len(bubble_pixels) == 0:
        return False, 0.0
    bubble_mean = float(np.mean(bubble_pixels))

    # Ring mask for local_white (immediate vicinity, avoids outside table borders)
    ring_mask = np.zeros(roi.shape[:2], dtype=np.uint8)
    cv2.circle(ring_mask, (rx, ry), radius + 6, 255, -1)
    cv2.circle(ring_mask, (rx, ry), radius + 2, 0, -1)
    ring_pixels = roi[ring_mask == 255]
    local_white = float(np.mean(ring_pixels)) if ring_pixels.size > 10 else 255.0
    local_white = max(local_white, 50.0)

    # ═══ STEP 2: calculate_threshold — per-bubble adaptive threshold ═══
    ratio = 1.0 - (bubble_mean / local_white)
    ratio = max(0.0, min(1.0, ratio))

    lw_clamped = max(50.0, min(255.0, local_white))
    adaptive_threshold = threshold * (0.85 + 0.30 * (lw_clamped - 50) / 205)
    adaptive_threshold = max(threshold * 0.8, min(threshold * 1.2, adaptive_threshold))

    # ═══ STEP 3: is_below_min_gray_threshold — absolute minimum ═══
    # Bubble cực đen (mean < 80) → chắc chắn filled, bypass mọi check
    if bubble_mean < 80 and ratio > adaptive_threshold:
        return True, ratio

    # Ratio quá thấp → chắc chắn empty
    if ratio <= adaptive_threshold * 0.7:
        return False, ratio

    # ═══ STEP 4: check_quarter_of_circle — phân tích 4 phần tư ═══
    if ratio > adaptive_threshold:
        quarter_means = _azota_check_quarter(roi, rx, ry, inner_radius)
        # Đếm quarters tối (mean < local_white * 0.75)
        dark_thresh = local_white * 0.75
        n_dark = sum(1 for qm in quarter_means if qm < dark_thresh)
        # 0 quarter dark → chắc chắn không tô / artifact → giảm mạnh
        if n_dark == 0 and ratio < adaptive_threshold + 0.10:
            ratio *= 0.5
            logger.debug(f"Quarter check: 0/4 dark at ({cx},{cy}) → ratio reduced to {ratio:.3f}")

    # ═══ STEP 5: is_white_bound — kiểm tra viền trắng ═══
    # Chỉ check cho vùng ambiguous (ratio gần threshold)
    if adaptive_threshold < ratio < adaptive_threshold + 0.08:
        if not _azota_is_white_bound(roi, rx, ry, radius):
            ratio *= 0.7
            logger.debug(f"White bound failed at ({cx},{cy}) → ratio reduced to {ratio:.3f}")

    # ═══ STEP 6: check_is_fill_contour — contour verification ═══
    if (adaptive_threshold - 0.05) < ratio < (adaptive_threshold + 0.15):
        _, bw = cv2.threshold(roi, int(local_white * 0.65), 255, cv2.THRESH_BINARY_INV)
        bw_masked = cv2.bitwise_and(bw, bw, mask=bubble_mask)
        cnts, _ = cv2.findContours(bw_masked, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
        if cnts:
            biggest = max(cnts, key=cv2.contourArea)
            cnt_area = cv2.contourArea(biggest)
            cnt_peri = cv2.arcLength(biggest, True)
            expected_area = np.pi * inner_radius * inner_radius

            if cnt_peri > 0:
                circularity = 4 * np.pi * cnt_area / (cnt_peri * cnt_peri)
                # Gạch chéo → circularity thấp → reject
                if circularity < 0.15:
                    ratio *= 0.5
                    logger.debug(f"Low circularity {circularity:.2f} at ({cx},{cy})")

            # Contour-based rescue: ratio thấp nhưng contour tốt → accept
            if ratio <= adaptive_threshold and cnt_area > 0.15 * expected_area:
                hull = cv2.convexHull(biggest)
                hull_area = cv2.contourArea(hull)
                solidity = cnt_area / hull_area if hull_area > 0 else 0
                if solidity > 0.5 and cnt_area < 0.8 * expected_area:
                    logger.debug(f"Contour rescue at ({cx},{cy}): area={cnt_area:.0f}, sol={solidity:.2f}")
                    return True, ratio

    # Final decision
    if ratio <= adaptive_threshold:
        return False, ratio
    return True, ratio


def _crop_bubble_for_cnn(gray_img, cx, cy, radius=BUBBLE_RADIUS, crop_size=CNN_IMG_SIZE):
    """Crop a square around bubble center for CNN input."""
    h, w = gray_img.shape[:2]
    pad = radius + 4
    x1 = max(0, int(cx - pad))
    y1 = max(0, int(cy - pad))
    x2 = min(w, int(cx + pad))
    y2 = min(h, int(cy + pad))
    roi = gray_img[y1:y2, x1:x2]
    if roi.size == 0:
        return None
    return cv2.resize(roi, (crop_size, crop_size), interpolation=cv2.INTER_AREA)


def _load_bubble_cnn():
    """Lazy-load CNN model — ONNX Runtime (preferred) or PyTorch (fallback)."""
    global _CNN_MODEL, _CNN_DEVICE, _CNN_READY, _CNN_ERROR
    if _CNN_READY or _CNN_ERROR is not None:
        return
    if not HYBRID_CNN_ENABLE:
        _CNN_ERROR = "disabled"
        return

    # [IMPROVE] Try ONNX Runtime first (26x faster than PyTorch)
    if os.path.exists(BUBBLE_CNN_ONNX_PATH):
        try:
            import onnxruntime as ort
            _CNN_MODEL = ort.InferenceSession(BUBBLE_CNN_ONNX_PATH)
            _CNN_DEVICE = "onnx"
            _CNN_READY = True
            logger.info("[CNN] Loaded ONNX model (fast inference)")
            return
        except Exception as exc:
            logger.warning(f"[CNN] ONNX load failed: {exc}, trying PyTorch...")

    # Fallback: PyTorch
    if not os.path.exists(BUBBLE_CNN_PATH):
        _CNN_ERROR = "model_not_found"
        return
    try:
        import torch
        from grading.engine.train_bubble_cnn import BubbleCNN
    except Exception as exc:
        _CNN_ERROR = str(exc)
        return

    device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
    model = BubbleCNN().to(device)
    try:
        state = torch.load(BUBBLE_CNN_PATH, map_location=device, weights_only=True)
    except TypeError:
        state = torch.load(BUBBLE_CNN_PATH, map_location=device)
    model.load_state_dict(state)
    model.eval()

    _CNN_MODEL = model
    _CNN_DEVICE = device
    _CNN_READY = True
    logger.info(f"[CNN] Loaded PyTorch model on {device}")


def _predict_bubble_cnn(gray_img, cx, cy):
    """Predict fill probability using CNN. Returns None if unavailable."""
    _load_bubble_cnn()
    if not _CNN_READY:
        return None

    crop = _crop_bubble_for_cnn(gray_img, cx, cy)
    if crop is None:
        return None

    try:
        img = crop.astype(np.float32) / 255.0
        # Ensure 2D grayscale input → (1, 1, H, W)
        if img.ndim == 3:
            img = img[:, :, 0]  # drop channels if accidentally color
        input_data = img[np.newaxis, np.newaxis, :, :]  # (1, 1, 32, 32)

        if _CNN_DEVICE == "onnx":
            # ONNX Runtime inference
            outputs = _CNN_MODEL.run(None, {'input': input_data.astype(np.float32)})
            probs = np.exp(outputs[0][0]) / np.sum(np.exp(outputs[0][0]))  # softmax
            return float(probs[1])
        else:
            # PyTorch inference (fallback)
            import torch
            tensor = torch.from_numpy(input_data).to(_CNN_DEVICE)
            with torch.no_grad():
                out = _CNN_MODEL(tensor)
                probs = torch.softmax(out, dim=1)
                return float(probs[0, 1].item())
    except Exception as e:
        print(f"[CNN WARN] _predict_bubble_cnn failed: {e}")
        return None


HYBRID_ALWAYS_CNN = False   # Only run CNN on ambiguous bubbles (saves ~80% time)

def _hybrid_score(gray_img, cx, cy, threshold=FILL_THRESHOLD, force_cnn=False):
    """Return (score, ratio, cnn_conf) using OpenCV + CNN.
    When HYBRID_ALWAYS_CNN=True, CNN runs on ALL bubbles and final score = max(ratio, cnn).
    """
    _, ratio = is_bubble_filled(gray_img, cx, cy, threshold=threshold)
    cnn_conf = None

    # Nếu ô hoàn toàn rỗng (< 0.16) → không cho CNN ghi đè gây nhận diện ảo
    if ratio < 0.16 and not force_cnn:
        return ratio, ratio, None

    use_cnn = HYBRID_CNN_ENABLE and (
        HYBRID_ALWAYS_CNN or force_cnn or (HYBRID_RATIO_LOW <= ratio <= HYBRID_RATIO_HIGH)
    )
    if use_cnn:
        cnn_conf = _predict_bubble_cnn(gray_img, cx, cy)

    if cnn_conf is None:
        return ratio, ratio, None

    score = max(ratio, cnn_conf)
    return score, ratio, cnn_conf


def _find_p3_box_near(gray_img, cx, cy, box_size=P3_OCR_BOX_SIZE):
    """Find a handwriting box near (cx, cy). Returns (x1,y1,x2,y2) or None."""
    h, w = gray_img.shape[:2]
    half = int(box_size / 2)
    search = int(box_size * 2.0)
    x1 = max(0, int(cx - search))
    y1 = max(0, int(cy - search))
    x2 = min(w, int(cx + search))
    y2 = min(h, int(cy + search))
    roi = gray_img[y1:y2, x1:x2]
    if roi.size == 0:
        return None

    thr = cv2.adaptiveThreshold(
        roi, 255, cv2.ADAPTIVE_THRESH_GAUSSIAN_C,
        cv2.THRESH_BINARY_INV, 31, 7
    )
    thr = cv2.medianBlur(thr, 3)
    kernel = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (3, 3))
    thr = cv2.dilate(thr, kernel, iterations=1)
    cnts, _ = cv2.findContours(thr, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    best = None
    for c in cnts:
        area = cv2.contourArea(c)
        if area < 120 or area > 5000:
            continue
        x, y, bw, bh = cv2.boundingRect(c)
        aspect = bw / float(bh) if bh > 0 else 0
        if 0.5 <= aspect <= 1.8:
            cx_c = x + bw / 2
            cy_c = y + bh / 2
            dist = (cx_c - (cx - x1)) ** 2 + (cy_c - (cy - y1)) ** 2
            if best is None or dist < best[0]:
                best = (dist, x, y, bw, bh)

    if best is None:
        return None

    _, bx, by, bw, bh = best
    gx1 = max(0, int(x1 + bx))
    gy1 = max(0, int(y1 + by))
    gx2 = min(w, int(x1 + bx + bw))
    gy2 = min(h, int(y1 + by + bh))
    return gx1, gy1, gx2, gy2


def _default_p3_box(gray_img, cx, cy, box_size=P3_OCR_BOX_SIZE):
    """Fallback box centered at (cx, cy)."""
    h, w = gray_img.shape[:2]
    half = int(box_size / 2)
    x1 = max(0, int(cx - half))
    y1 = max(0, int(cy - half))
    x2 = min(w, int(cx + half))
    y2 = min(h, int(cy + half))
    return x1, y1, x2, y2


def _ocr_digit_from_box(gray_img, box):
    """OCR a single digit from a handwriting box. Returns (digit, ink_ratio)."""
    if box is None:
        return -1, 0.0
    try:
        import pytesseract
    except Exception:
        return -1, 0.0

    x1, y1, x2, y2 = box
    roi = gray_img[y1:y2, x1:x2]
    if roi.size == 0:
        return -1, 0.0

    # Remove box border by cropping inner region.
    h, w = roi.shape[:2]
    margin = max(2, int(min(h, w) * 0.1))
    roi = roi[margin:h - margin, margin:w - margin]
    if roi.size == 0:
        return -1, 0.0

    # Resize to help OCR.
    roi = cv2.resize(roi, (0, 0), fx=2.0, fy=2.0, interpolation=cv2.INTER_CUBIC)
    blur = cv2.GaussianBlur(roi, (3, 3), 0)
    _, thr = cv2.threshold(blur, 0, 255, cv2.THRESH_BINARY_INV + cv2.THRESH_OTSU)
    ink_ratio = float(np.count_nonzero(thr)) / float(thr.size)
    if ink_ratio < P3_OCR_INK_MIN or ink_ratio > P3_OCR_INK_MAX:
        return -1, ink_ratio
    thr = cv2.medianBlur(thr, 3)
    kernel = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (3, 3))
    thr = cv2.dilate(thr, kernel, iterations=1)
    config = "--psm 10 -c tessedit_char_whitelist=0123456789"
    txt = pytesseract.image_to_string(thr, config=config)
    if not txt:
        txt = pytesseract.image_to_string(roi, config=config)
    txt = (txt or "").strip()
    if len(txt) != 1:
        return -1, ink_ratio
    ch = txt[0]
    return (int(ch) if ch.isdigit() else -1), ink_ratio


# ╔════════════════════════════════════════════════════════════════════════╗
# ║      BƯỚC 5a: TRÍCH XUẤT ĐÁP ÁN PHẦN I (40 câu ABCD)             ║
# ╚════════════════════════════════════════════════════════════════════════╝

def _detect_filled_choices(ratios, global_threshold=None, local_threshold=None, fast_mode=False):
    """
    Phát hiện bubble được tô — 4 phương pháp + cluster analysis.

    QUAN TRỌNG: Phải detect CHÍNH XÁC số bubble tô:
      - 0 bubble → "" (bỏ trống)
      - 1 bubble → "A"/"B"/"C"/"D"
      - 2+ bubble → "X" (tô nhiều, câu hỏng)
      - fast_mode=True: Giảm độ nhạy 20% (tăng ngưỡng 20%) cho Live Camera để tránh chấm nhầm
    """
    if not ratios:
        return []

    vals = list(ratios.values())
    # Giảm độ nhạy thêm 20% cho Live Camera (tổng giảm ~36% so với gốc): tăng ngưỡng tối thiểu từ 0.156 lên 0.187
    min_cutoff = 0.187 if fast_mode else 0.13
    if max(vals) < min_cutoff:
        return []

    # Sort by fill ratio descending
    paired = sorted(ratios.items(), key=lambda x: x[1], reverse=True)
    sorted_r = [p[1] for p in paired]
    top_ch, top_v = paired[0]
    second_v = paired[1][1] if len(paired) > 1 else 0
    gap = top_v - second_v
    mean_v = float(np.mean(vals))

    # Nét chì nhạt hoặc ô nhiễu nét trên Live Camera:
    # Bắt buộc phải có gap rõ rệt và vượt trội so với các ô còn lại trong câu
    # Giảm độ nhạy thêm 20% khi fast_mode=True:
    light_ceil = 0.36 if fast_mode else 0.25
    req_gap = 0.094 if fast_mode else 0.065
    req_ratio = 1.92 if fast_mode else 1.45
    req_mean_diff = 0.072 if fast_mode else 0.05

    if top_v < light_ceil:
        if gap < req_gap or (second_v > 0 and top_v / second_v < req_ratio) or (top_v - mean_v < req_mean_diff):
            return []  # Không đủ nổi bật → ô trống / viền in / nhiễu nét
        return [top_ch]

    # Check if all ratios are close (likely all empty)
    spread_limit = 0.086 if fast_mode else 0.06
    spread_max = 0.40 if fast_mode else 0.28
    ratio_spread = max(vals) - min(vals)
    if ratio_spread < spread_limit and max(vals) < spread_max:
        return []  # All bubbles have similar low ratios → all empty
    n = len(sorted_r)

    # Calculate adaptive thresholds based on noise floor
    noise_floor = float(np.std(sorted_r))
    scale_factor = 1.44 if fast_mode else 1.0
    min_gap_threshold = max(0.05 * scale_factor, 2.0 * scale_factor * noise_floor)
    min_separation = max(0.03 * scale_factor, 1.5 * scale_factor * noise_floor)

    # ── CLUSTER ANALYSIS: Tìm gap lớn nhất để tách filled/empty ──
    if n >= 2:
        gaps = [(i, sorted_r[i] - sorted_r[i + 1]) for i in range(n - 1)]
        best_gap_idx, best_gap = max(gaps, key=lambda x: x[1])

        if best_gap > min_gap_threshold:
            filled_cluster = [paired[i][0] for i in range(best_gap_idx + 1)]
            filled_ratios = sorted_r[:best_gap_idx + 1]
            empty_ratios = sorted_r[best_gap_idx + 1:]

            # Kiểm tra: cụm filled phải thực sự nổi bật
            filled_min = min(filled_ratios)
            empty_max = max(empty_ratios) if empty_ratios else 0
            separation = filled_min - empty_max

            if separation > min_separation:
                if len(filled_cluster) == 1:
                    return filled_cluster
                elif len(filled_cluster) >= 2:
                    inner_gap = filled_ratios[0] - filled_ratios[1]
                    inner_ratio = filled_ratios[0] / filled_ratios[1] if filled_ratios[1] > 0 else float('inf')
                    if inner_gap > (0.17 if fast_mode else 0.12) or inner_ratio > (2.0 if fast_mode else 1.5):
                        return [paired[0][0]]
                    logger.info(f"MULTI-BUBBLE: {filled_cluster} ratios={filled_ratios}")
                    return filled_cluster

    # ── METHOD 1: TNMaker Relative ──
    tn_gap_threshold = max(0.08 * scale_factor, 1.5 * scale_factor * noise_floor)
    if n >= 3:
        gap_top = sorted_r[0] - sorted_r[1]
        gap_rest = sorted_r[1] - sorted_r[2]
        if gap_top > tn_gap_threshold and gap_rest <= 0.2:
            return [paired[0][0]]
    elif n == 2:
        if sorted_r[0] - sorted_r[1] > tn_gap_threshold:
            return [paired[0][0]]

    # ── METHOD 2: 2-Level Threshold ──
    base_eff = max(local_threshold if local_threshold is not None else (global_threshold or 0.16), 0.16)
    eff_threshold = base_eff * scale_factor
    filled_2level = [ch for ch, r in ratios.items() if r > eff_threshold]
    if filled_2level:
        if len(filled_2level) == 1:
            return filled_2level
        filled_sorted = sorted([(ch, ratios[ch]) for ch in filled_2level],
                               key=lambda x: x[1], reverse=True)
        top_r = filled_sorted[0][1]
        second_r = filled_sorted[1][1]
        if (top_r - second_r) > (0.072 if fast_mode else 0.05) or (second_r > 0 and top_r / second_r > (1.8 if fast_mode else 1.3)):
            return [filled_sorted[0][0]]
        return filled_2level
    elif global_threshold is not None:
        filled_global = [ch for ch, r in ratios.items() if r > (global_threshold * scale_factor)]
        if filled_global:
            if len(filled_global) == 1:
                return filled_global
            filled_sorted = sorted([(ch, ratios[ch]) for ch in filled_global],
                                   key=lambda x: x[1], reverse=True)
            top_r = filled_sorted[0][1]
            second_r = filled_sorted[1][1]
            if (top_r - second_r) > (0.115 if fast_mode else 0.08) or (second_r > 0 and top_r / second_r > (2.0 if fast_mode else 1.5)):
                return [filled_sorted[0][0]]
            return filled_global

    # ── METHOD 3: Absolute threshold ──
    abs_threshold = FILL_THRESHOLD * scale_factor
    filled = [ch for ch, r in ratios.items() if r > abs_threshold]
    if filled:
        if len(filled) == 1:
            return filled
        filled_sorted = sorted([(ch, ratios[ch]) for ch in filled],
                               key=lambda x: x[1], reverse=True)
        top_r = filled_sorted[0][1]
        second_r = filled_sorted[1][1]
        gap = top_r - second_r
        if gap > (0.144 if fast_mode else 0.1) or (second_r > 0 and top_r / second_r > (2.0 if fast_mode else 1.5)):
            return [filled_sorted[0][0]]
        return filled

    # ── METHOD 4: Adaptive noise floor ──
    sorted_vals = sorted(vals)
    noise_floor = sorted_vals[1] if len(sorted_vals) >= 3 else sorted_vals[0]
    adjusted = [(ch, max(0.0, r - noise_floor)) for ch, r in ratios.items()]
    adjusted.sort(key=lambda x: x[1], reverse=True)

    sig_thr = 0.058 if fast_mode else 0.04
    significant = [(ch, adj) for ch, adj in adjusted if adj > sig_thr]
    if not significant:
        return []

    if len(significant) == 1:
        return [significant[0][0]]

    # Nhiều bubble nổi bật → check gap giữa chúng
    top_adj = significant[0][1]
    second_adj = significant[1][1]
    # IMPROVEMENT 8: Increase gap threshold from 0.03 to 0.05
    if (top_adj - second_adj) > 0.05:
        return [significant[0][0]]  # Chỉ 1 thật sự nổi bật
    # Cả 2 đều nổi bật → tô nhiều
    return [s[0] for s in significant]


def _pick_answer(filled_choices):
    """Convert filled_choices list → answer string."""
    if len(filled_choices) == 1:
        return filled_choices[0]
    elif len(filled_choices) > 1:
        return "X"
    return ""


def _confidence_score(ratios):
    """Compute 2D confidence score (0.0–1.0) for the detected answer.

    Two factors:
      1) Margin (w=0.6): top1 - top2 gap. Margin 0.3+ → 1.0
      2) Absolute strength (w=0.4): top1 fill ratio. Ratio 0.5+ → 1.0

    Prevents false confidence when:
      - Both top bubbles are weak (top=0.15, second=0.10 → margin ok but too faint)
      - One bubble dominates but very faintly
    """
    if not ratios:
        return 0.0
    vals = sorted(ratios.values(), reverse=True)
    if len(vals) < 2:
        return min(1.0, vals[0] * 2)
    top, second = vals[0], vals[1]
    # Factor 1: Margin
    margin = top - second
    margin_score = min(1.0, margin / 0.3)
    # Factor 2: Absolute strength
    abs_score = min(1.0, top / 0.5)
    # Weighted combination
    conf = 0.6 * margin_score + 0.4 * abs_score
    return round(conf, 3)


def _compute_global_threshold(all_ratios_by_question, looseness=1):
    """
    Tính global threshold từ TẤT CẢ bubble ratios trong phiếu.
    Port từ OMRChecker core.py:get_global_threshold().

    Args:
        all_ratios_by_question: dict {q_num: {'A': ratio, 'B': ratio, ...}, ...}
        looseness: độ rộng tìm kiếm gap (1=standard, 2=wider)

    Returns:
        (global_threshold, j_low, j_high)
    """
    all_vals = []
    for q_ratios in all_ratios_by_question.values():
        all_vals.extend(q_ratios.values())

    if not all_vals:
        return FILL_THRESHOLD, 0, 0

    q_vals = sorted(all_vals)
    l = len(q_vals) - looseness
    ls = (looseness + 1) // 2

    # Tìm FIRST LARGE GAP
    MIN_JUMP = 0.08
    max1, thr1 = MIN_JUMP, FILL_THRESHOLD

    for i in range(ls, l):
        jump = q_vals[min(i + ls, len(q_vals) - 1)] - q_vals[max(i - ls, 0)]
        if jump > max1:
            max1 = jump
            thr1 = q_vals[max(i - ls, 0)] + jump / 2

    return thr1, thr1 - max1 / 2, thr1 + max1 / 2


def _compute_local_threshold(strip_ratios, global_thr, no_outliers):
    """
    Tính local threshold cho 1 question strip.
    Port từ OMRChecker core.py:get_local_threshold().

    Args:
        strip_ratios: list of ratio values cho 1 câu hỏi (4 hoặc 2 giá trị)
        global_thr: global threshold đã tính
        no_outliers: True nếu strip này không có outlier (all similar)

    Returns:
        local_threshold
    """
    q_vals = sorted(strip_ratios)

    # Base case: ít hơn 3 giá trị
    if len(q_vals) < 3:
        if max(q_vals) - min(q_vals) < 0.05:
            return global_thr
        return np.mean(q_vals)

    # Tìm LARGEST GAP
    l = len(q_vals) - 1
    MIN_JUMP = 0.08
    max1, thr1 = MIN_JUMP, 1.0

    for i in range(1, l):
        jump = q_vals[i + 1] - q_vals[i - 1]
        if jump > max1:
            max1 = jump
            thr1 = q_vals[i - 1] + jump / 2

    CONFIDENT_SURPLUS = 0.03
    confident_jump = MIN_JUMP + CONFIDENT_SURPLUS

    # Nếu gap không đủ lớn → dùng global threshold
    if max1 < confident_jump:
        if no_outliers:
            return max(global_thr, 0.18)
        return max(float(np.mean(q_vals)), 0.18)

    return max(thr1, 0.18)


def _count_detected(answers_dict):
    """Count how many questions have a real answer (not '' or 'X')."""
    return sum(1 for a in answers_dict.values()
               if isinstance(a, str) and a not in ("", "X")
               or isinstance(a, dict) and any(v not in ("", "X") for v in a.values()))


def _auto_align_field_blocks(gray, max_shift=8, stride=1):
    """
    Tính horizontal shift cho mỗi Part I column dựa trên morphological analysis.
    Port từ OMRChecker auto-align logic.

    Ý tưởng: Dùng vertical morphological kernel để tìm đường dọc (cột bubble).
    So sánh vị trí đường dọc thực tế vs expected → tính shift pixel.

    Args:
        gray: ảnh grayscale đã preprocess (warped 1400x1920)
        max_shift: số pixel tối đa được phép shift
        stride: bước nhảy khi tìm shift

    Returns:
        dict {"part1_col0": shift_px, "part1_col1": shift_px, ...}
    """
    h, w = gray.shape[:2]
    shifts = {}

    for col_idx, cfg in enumerate(PART1_COLS):
        sx = int(cfg["start_x"])
        sy = int(cfg["start_y"])
        dx = cfg["step_x"]
        col_rows = cfg.get("num_rows", PART1_NUM_ROWS)
        block_h = int(col_rows * cfg["step_y"])
        # Block width: from first choice (A) to last choice (D)
        block_w = int(3 * dx) + 20

        # Extract region around this column (with margin for shifting)
        margin = max_shift + 10
        x1 = max(0, sx - margin)
        x2 = min(w, sx + block_w + margin)
        y1 = max(0, sy - 5)
        y2 = min(h, sy + block_h + 5)

        roi = gray[y1:y2, x1:x2]
        if roi.size == 0:
            shifts[f"part1_col{col_idx}"] = 0
            continue

        # Binary threshold to find dark marks (bubbles)
        _, roi_bin = cv2.threshold(roi, 0, 255, cv2.THRESH_BINARY_INV + cv2.THRESH_OTSU)

        # Vertical projection: sum each column → peaks = bubble columns
        v_proj = np.sum(roi_bin, axis=0).astype(float)
        if v_proj.max() == 0:
            shifts[f"part1_col{col_idx}"] = 0
            continue

        # Expected column positions (relative to roi)
        expected_cols = []
        for ci in range(4):  # A, B, C, D
            expected_x = (sx + ci * dx) - x1
            expected_cols.append(expected_x)

        # Try different shifts and find best match
        best_shift = 0
        best_score = 0

        for shift in range(-max_shift, max_shift + 1, stride):
            score = 0
            for exp_x in expected_cols:
                px = int(exp_x + shift)
                # Sum projection in small window around expected position
                lo = max(0, px - BUBBLE_RADIUS)
                hi = min(len(v_proj), px + BUBBLE_RADIUS)
                if lo < hi:
                    score += np.sum(v_proj[lo:hi])
            if score > best_score:
                best_score = score
                best_shift = shift

        shifts[f"part1_col{col_idx}"] = best_shift

    return shifts


def extract_part1(cleaned_img, y_offset=0, num_questions=None, fast_mode=False):
    """
    Đọc câu trắc nghiệm ABCD.
    y_offset: bù lệch y do ảnh phồng (từ detect_section_offsets).
    num_questions: giới hạn số câu quét (None = quét hết theo template).
    fast_mode: True → giảm độ nhạy 20% cho Live Camera.
    2-pass approach:
      Pass 1: Thu thập TẤT CẢ ratios
      Pass 2: Tính global/local thresholds → detect answers
    Trả về:
      answers: {1: 'A', 2: 'C', ...}  ('X'=tô nhiều, ''=không tô)
      details: {1: {'A': 0.05, 'B': 0.72, ...}, ...}  (fill ratio)
    """
    answers = {}
    details = {}

    # ── Auto-alignment: tính shift cho mỗi cột (safe) ──
    import time as _t
    _t0 = _t.time()
    try:
        align_shifts = _auto_align_field_blocks(cleaned_img, max_shift=5)
        any_shift = any(v != 0 for v in align_shifts.values())
        if any_shift:
            print(f"[OK] Auto-align Part I shifts: {align_shifts} ({(_t.time()-_t0)*1000:.0f}ms)")
    except Exception as e:
        print(f"[WARN] Auto-align failed: {e}")
        align_shifts = {f"part1_col{i}": 0 for i in range(len(PART1_COLS))}

    # ── PASS 1: Thu thập TẤT CẢ ratios (với alignment correction) ──
    for col_idx, cfg in enumerate(PART1_COLS):
        sx, sy = cfg["start_x"], cfg["start_y"]
        dx, dy = cfg["step_x"], cfg["step_y"]
        q_start = cfg["q_start"]
        col_shift = align_shifts.get(f"part1_col{col_idx}", 0)

        col_rows = cfg.get("num_rows", PART1_NUM_ROWS)
        for row in range(col_rows):
            q = q_start + row
            if num_questions is not None and q > num_questions:
                break
            cy = sy + row * dy + y_offset
            ratios = {}

            for ci, choice in enumerate(PART1_CHOICES):
                cx = sx + ci * dx + col_shift
                score, ratio, cnn_conf = _hybrid_score(cleaned_img, cx, cy)
                ratios[choice] = round(score, 3)

            details[q] = ratios

    # ── PASS 2: Tính global threshold từ tất cả ratios ──
    global_thr, _, _ = _compute_global_threshold(details)

    # Tính std cho mỗi strip → xác định no_outliers
    all_q_std_vals = []
    for q, ratios in details.items():
        vals = list(ratios.values())
        all_q_std_vals.append(np.std(vals))
    global_std_thresh = np.median(all_q_std_vals) if all_q_std_vals else 0.1

    # ── PASS 3: Detect answers với 2-level thresholds (kèm fast_mode -20% nhạy) ──
    for q, ratios in details.items():
        strip_std = np.std(list(ratios.values()))
        no_outliers = strip_std < global_std_thresh
        local_thr = _compute_local_threshold(
            list(ratios.values()), global_thr, no_outliers)

        filled_choices = _detect_filled_choices(
            ratios, global_threshold=global_thr, local_threshold=local_thr, fast_mode=fast_mode)
        ans = _pick_answer(filled_choices)
        conf = _confidence_score(ratios)
        answers[q] = ans

        # Debug: log fill ratios cho câu bị blank, uncertain, hoặc tất cả
        if ans in ("", "X"):
            logger.warning(
                f"P1 Q{q} BLANK: ratios={ratios}  "
                f"max={max(ratios.values()):.3f}  "
                f"g_thr={global_thr:.3f} l_thr={local_thr:.3f}  conf={conf}"
            )
        elif conf < 0.5:
            logger.warning(
                f"P1 Q{q}={ans} LOW_CONF({conf:.2f}): ratios={ratios} "
                f"g_thr={global_thr:.3f} l_thr={local_thr:.3f}"
            )
        else:
            logger.debug(f"P1 Q{q}={ans} conf={conf}: ratios={ratios}")

    return answers, details


# ╔════════════════════════════════════════════════════════════════════════╗
# ║   BƯỚC 5b: TRÍCH XUẤT ĐÁP ÁN PHẦN II (8 câu x a/b/c/d x Đ/S)    ║
# ╚════════════════════════════════════════════════════════════════════════╝

def extract_part2(cleaned_img, y_offset=0, num_questions=None, fast_mode=False):
    """
    Đọc câu Đúng/Sai cho mỗi ý a, b, c, d.
    y_offset: bù lệch y do ảnh phồng (từ detect_section_offsets).
    num_questions: giới hạn số câu quét (None = quét hết theo template).
    fast_mode: True → giảm độ nhạy 20% cho Live Camera.
    Hybrid 1-pass: max(OpenCV, CNN) cho mỗi bubble.
    Trả về:
      answers: {1: {'a': 'Dung', 'b': 'Sai', ...}, ...}
      details: {1: {'a': {'Dung': 0.7, 'Sai': 0.05}, ...}, ...}
    """
    answers = {}
    details = {}

    # Giảm độ nhạy thêm 20% cho Live Camera: tăng ngưỡng tối thiểu và khoảng cách gap (tổng x1.44)
    min_score = (0.22 * 1.44) if fast_mode else 0.22  # 0.317 vs 0.22
    min_gap = (0.14 * 1.44) if fast_mode else 0.14    # 0.20 vs 0.14

    for blk in PART2_BLOCKS:
        q = blk["q"]
        if num_questions is not None and q > num_questions:
            break
        sx, sy = blk["start_x"], blk["start_y"]
        q_ans, q_det = {}, {}

        for ri, label in enumerate(PART2_ROWS):
            cy = sy + ri * PART2_STEP_Y + y_offset
            # Cột Đúng / Sai: Dùng OpenCV fill ratio chuẩn
            _, score_dung = is_bubble_filled(cleaned_img, sx, cy)
            _, score_sai = is_bubble_filled(cleaned_img, sx + PART2_STEP_X, cy)

            q_det[label] = {"Dung": round(score_dung, 3), "Sai": round(score_sai, 3)}

            # Đúng / Sai: Phải có ít nhất 1 ô đạt ngưỡng tối thiểu VÀ có gap phân biệt
            if max(score_dung, score_sai) < min_score or abs(score_dung - score_sai) < min_gap:
                q_ans[label] = ""
            else:
                filled = _detect_filled_choices({"Dung": score_dung, "Sai": score_sai}, fast_mode=fast_mode)
                q_ans[label] = _pick_answer(filled)

        answers[q] = q_ans
        details[q] = q_det

    return answers, details


# ╔════════════════════════════════════════════════════════════════════════╗
# ║       BƯỚC 5c: TRÍCH XUẤT ĐÁP ÁN PHẦN III (6 câu điền số)        ║
# ╚════════════════════════════════════════════════════════════════════════╝

def extract_part3(cleaned_img, y_offset=0, num_questions=None, fast_mode=False):
    """
    Đọc câu điền số: dấu trừ (-), dấu phẩy (.), 4 cột số 0-9.
    y_offset: bù lệch y do ảnh phồng (từ detect_section_offsets).
    num_questions: giới hạn số câu quét (None = quét hết theo template).
    fast_mode: True → giảm độ nhạy 20% cho Live Camera.
    Mỗi cột chọn digit có fill_ratio cao nhất (nếu > threshold).
    Trả về:
      answers: {1: '1234', 2: '-5.67', ...}
      details: fill ratios chi tiết
    """
    answers = {}
    details = {}

    p3_score_min = (P3_DIGIT_SCORE_MIN * 1.44) if fast_mode else P3_DIGIT_SCORE_MIN
    p3_gap_min = (P3_DIGIT_GAP_MIN * 1.44) if fast_mode else P3_DIGIT_GAP_MIN
    blank_cv_thr = 0.14 if fast_mode else 0.10

    for blk in PART3_BLOCKS:
        q = blk["q"]
        if num_questions is not None and q > num_questions:
            break
        cols_x = blk["cols_x"]
        q_det = {}

        # 1) Kiểm tra dấu trừ (-)
        sign_score, r_neg, _ = _hybrid_score(
            cleaned_img, blk["sign_x"], PART3_SIGN_Y + y_offset, force_cnn=True
        )
        is_neg = bool(sign_score >= (P3_SIGN_SCORE_MIN * (1.20 if fast_mode else 1.0)))
        q_det["sign"] = round(r_neg, 3)

        # 2) Kiểm tra dấu phẩy (.) - cột nào được tô
        COMMA_THRESHOLD = 0.264 if fast_mode else 0.22
        comma_col = -1
        comma_scores = []
        comma_ratios = []
        for ci, cx in enumerate(cols_x):
            score, ratio, _ = _hybrid_score(
                cleaned_img, cx, PART3_COMMA_Y + y_offset,
                threshold=COMMA_THRESHOLD, force_cnn=True
            )
            comma_scores.append(score)
            comma_ratios.append(round(ratio, 3))
        q_det["comma"] = comma_ratios
        if comma_scores:
            order = sorted(range(len(comma_scores)), key=lambda i: comma_scores[i], reverse=True)
            top_i = order[0]
            top_s = comma_scores[top_i]
            second_s = comma_scores[order[1]] if len(order) > 1 else 0.0
            req_comma_score = (P3_COMMA_SCORE_MIN * 1.20) if fast_mode else P3_COMMA_SCORE_MIN
            req_comma_gap = (P3_COMMA_GAP_MIN * 1.20) if fast_mode else P3_COMMA_GAP_MIN
            if top_s >= req_comma_score and (top_s - second_s) >= req_comma_gap:
                comma_col = top_i

        # 3) Đọc 4 cột số (mỗi cột: chọn digit 0-9 có ratio cao nhất)
        digits = []
        digit_det = []
        digit_scores = []
        for ci, cx in enumerate(cols_x):
            col_ratios = {}
            col_scores = {}
            for d in range(10):
                cy = PART3_DIGIT_START_Y + d * PART3_DIGIT_STEP_Y + y_offset
                score, ratio, _ = _hybrid_score(cleaned_img, cx, cy, force_cnn=True)
                col_scores[str(d)] = round(score, 3)
                col_ratios[str(d)] = round(ratio, 3)
            digit_det.append({int(k): v for k, v in col_ratios.items()})
            digit_scores.append({int(k): v for k, v in col_scores.items()})
            # Lọc cột rỗng bằng CV ratio và độ lệch chuẩn
            max_cv = max(col_ratios.values()) if col_ratios else 0
            scores_list = list(col_scores.values())
            col_std = float(np.std(scores_list))
            is_blank_col = (max_cv < blank_cv_thr) or ((col_std < P3_BLANK_COL_STD_MIN) if P3_BLANK_COL_STD_MIN > 0 else False)

            # Pick MAX ratio nếu nổi bật và không phải cột rỗng
            sorted_items = sorted(col_scores.items(), key=lambda x: x[1], reverse=True)
            top_d, top_s = sorted_items[0]
            second_s = sorted_items[1][1] if len(sorted_items) > 1 else 0
            if not is_blank_col and top_s >= p3_score_min and (top_s - second_s) >= p3_gap_min:
                digits.append(int(top_d))
            else:
                digits.append(-1)  # Không tô hoặc không rõ
        q_det["digits"] = digit_det
        q_det["digits_score"] = digit_scores

        # 3b) OCR fallback from handwriting boxes (if enabled)
        ocr_digits = []
        ocr_boxes = []
        ocr_ink = []
        digit_count = sum(1 for d in digits if d >= 0)
        allow_ocr = P3_OCR_ENABLE and digit_count == 0
        if allow_ocr:
            ocr_digits = [-1] * len(cols_x)
            box_y = PART3_SIGN_Y + y_offset + P3_OCR_BOX_Y_OFFSET
            for ci, cx in enumerate(cols_x):
                box = _find_p3_box_near(cleaned_img, cx, box_y)
                if box is None:
                    box = _default_p3_box(cleaned_img, cx, box_y)
                ocr_boxes.append(box)
                digit, ink_ratio = _ocr_digit_from_box(cleaned_img, box)
                ocr_ink.append(round(ink_ratio, 3))
                if digits[ci] >= 0:
                    continue
                ocr_digits[ci] = digit
                if ocr_digits[ci] >= 0:
                    digits[ci] = ocr_digits[ci]
        q_det["ocr_digits"] = ocr_digits
        q_det["ocr_boxes"] = ocr_boxes
        q_det["ocr_ink"] = ocr_ink
        q_det["picked"] = {
            "sign": is_neg,
            "comma_col": comma_col,
            "digits": digits,
        }
        details[q] = q_det

        # 4) Ghép chuỗi số
        num_str = ""
        for i, d in enumerate(digits):
            if i == comma_col and num_str:
                has_after = any(dd >= 0 for dd in digits[i:])
                if has_after:
                    num_str += "."
            if d >= 0:
                num_str += str(d)
        if is_neg and num_str:
            num_str = "-" + num_str

        answers[q] = num_str

    return answers, details


# ╔════════════════════════════════════════════════════════════════════════╗
# ║                      CHẤM ĐIỂM (Grading)                            ║
# ╚════════════════════════════════════════════════════════════════════════╝

def extract_sbd_made(cleaned_img):
    """
    Đọc Số báo danh (6 chữ số) và Mã đề (3 chữ số).
    Mỗi cột chọn digit có fill_ratio cao nhất (nếu > threshold).
    Trả về: (sbd_str, made_str, details_dict)
    """
    def _read_digit_cols(cols_x, digit_y_list):
        """Đọc cột SBD/MĐ: 10 digits, chọn MAX nổi bật nhất."""
        digits = []
        det = []
        for cx in cols_x:
            col_r = {}
            for d, cy in enumerate(digit_y_list):
                _, r = is_bubble_filled(cleaned_img, cx, cy,
                                        check_circularity=False)
                col_r[d] = round(r, 3)
            det.append(col_r)
            # Pick MAX ratio nếu nổi bật so với 2nd
            sorted_items = sorted(col_r.items(), key=lambda x: x[1], reverse=True)
            top_d, top_r = sorted_items[0]
            second_r = sorted_items[1][1] if len(sorted_items) > 1 else 0
            gap = top_r - second_r
            if top_r >= SBD_MADE_TOP_MIN and gap >= SBD_MADE_GAP_MIN:
                digits.append(top_d)
            elif top_r >= SBD_MADE_FALLBACK_TOP_MIN and gap >= SBD_MADE_FALLBACK_GAP_MIN:
                digits.append(top_d)
            else:
                digits.append(-1)
        return digits, det

    sbd_digits, sbd_det = _read_digit_cols(SBD_COLS_X, SBD_MADE_DIGIT_Y)
    made_digits, made_det = _read_digit_cols(MADE_COLS_X, SBD_MADE_DIGIT_Y)

    sbd_str = "".join(str(d) if d >= 0 else "?" for d in sbd_digits)
    made_str = "".join(str(d) if d >= 0 else "?" for d in made_digits)

    details = {"sbd": sbd_det, "made": made_det}
    return sbd_str, made_str, details


# ╔════════════════════════════════════════════════════════════════════════╗
# ║                      CHẤM ĐIỂM (Grading)                            ║
# ╚════════════════════════════════════════════════════════════════════════╝

def grade_part1(student, correct, num_questions=None):
    """So sánh Part I. Trả về (score, results_dict)."""
    results = {}
    score = 0
    max_q = num_questions if num_questions is not None else 40
    for q in range(1, max_q + 1):
        s = student.get(q, "")
        c = correct.get(q, "")
        ok = (s == c and s not in ("", "X"))
        if ok:
            score += 1
        results[q] = {"student": s, "correct": c, "is_correct": ok}
    return score, results


def grade_part2(student, correct, num_questions=None):
    """So sánh Part II. Trả về (score, results_dict). 1 điểm nếu đúng cả 4 ý."""
    results = {}
    score = 0
    max_q = num_questions if num_questions is not None else 8
    for q in range(1, max_q + 1):
        q_res = {}
        n_correct = 0
        for row in PART2_ROWS:
            s = student.get(q, {}).get(row, "")
            c = correct.get(q, {}).get(row, "")
            ok = (s == c and s not in ("", "X"))
            if ok:
                n_correct += 1
            q_res[row] = {"student": s, "correct": c, "is_correct": ok}
        if n_correct == 4:
            score += 1
        results[q] = q_res
    return score, results


def grade_part3(student, correct, num_questions=None):
    """So sánh Part III. Trả về (score, results_dict)."""
    results = {}
    score = 0
    max_q = num_questions if num_questions is not None else 6
    for q in range(1, max_q + 1):
        s = student.get(q, "")
        c = correct.get(q, "")
        ok = (s == c and s != "")
        if ok:
            score += 1
        results[q] = {"student": s, "correct": c, "is_correct": ok}
    return score, results


# ╔════════════════════════════════════════════════════════════════════════╗
# ║                  VẼ KẾT QUẢ LÊN ẢNH (Visualization)                ║
# ╚════════════════════════════════════════════════════════════════════════╝

# Màu sắc (BGR) — đậm, nổi bật
COLOR_CORRECT   = (0, 180, 0)     # Xanh lá đậm  - đáp án HS đúng
COLOR_WRONG     = (0, 0, 220)     # Đỏ đậm       - đáp án HS sai
COLOR_RIGHT_ANS = (0, 180, 0)     # Xanh lá đậm - đáp án đúng (khi HS sai)
COLOR_UNANSWERED = (0, 200, 255)  # Vàng đậm - chưa khoanh / bỏ trống
THICKNESS_MARK  = 5


def draw_results_part1(image, results, y_offset=0):
    """Vẽ vòng tròn kết quả cho Part I."""
    for q, res in results.items():
        col_idx = (q - 1) // 10
        row_idx = (q - 1) % 10
        if col_idx >= len(PART1_COLS):
            continue
        cfg = PART1_COLS[col_idx]
        cy = int(cfg["start_y"] + row_idx * cfg["step_y"] + y_offset)
        student_ans = res["student"]
        is_blank = student_ans in ("", "-", "X")

        for ci, choice in enumerate(PART1_CHOICES):
            cx = int(cfg["start_x"] + ci * cfg["step_x"])
            # Đánh dấu đáp án học sinh (chỉ khi HS CÓ KHOANH)
            if not is_blank and choice == student_ans:
                color = COLOR_CORRECT if res["is_correct"] else COLOR_WRONG
                cv2.circle(image, (cx, cy), BUBBLE_RADIUS + 3, color, THICKNESS_MARK)
            # Đánh dấu đáp án đúng nếu HS sai
            if not is_blank and choice == res["correct"] and not res["is_correct"]:
                cv2.circle(image, (cx, cy), BUBBLE_RADIUS + 5, COLOR_RIGHT_ANS, THICKNESS_MARK)
    return image


def draw_results_part2(image, results, y_offset=0):
    """Vẽ vòng tròn kết quả cho Part II."""
    for q, q_res in results.items():
        blk = PART2_BLOCKS[q - 1]
        sx, sy = blk["start_x"], blk["start_y"]
        for ri, label in enumerate(PART2_ROWS):
            res = q_res[label]
            student_ans = res["student"]
            is_blank = student_ans in ("", "X")
            cy = int(sy + ri * PART2_STEP_Y + y_offset)
            for ci, col_name in enumerate(["Dung", "Sai"]):
                cx = int(sx + ci * PART2_STEP_X)
                if not is_blank and col_name == student_ans:
                    color = COLOR_CORRECT if res["is_correct"] else COLOR_WRONG
                    cv2.circle(image, (cx, cy), BUBBLE_RADIUS + 3, color, THICKNESS_MARK)
                if not is_blank and col_name == res["correct"] and not res["is_correct"]:
                    cv2.circle(image, (cx, cy), BUBBLE_RADIUS + 5, COLOR_RIGHT_ANS, THICKNESS_MARK)
    return image


def _parse_p3_string(s, num_cols=4):
    """Parse Part III answer string → (is_neg, comma_col, digits[4])."""
    if s is not None and not isinstance(s, str):
        s = str(s)
    if not s or s == '-':
        return False, -1, [-1] * num_cols
    is_neg = s.startswith('-')
    s = s.lstrip('-')
    comma_col = -1
    if '.' in s:
        comma_col = s.index('.')
        s = s.replace('.', '')
    digits = [-1] * num_cols
    for i, ch in enumerate(s):
        if i < num_cols:
            digits[i] = int(ch)
    return is_neg, comma_col, digits


def draw_results_part3(image, results, student_details, y_offset=0):
    """Vẽ kết quả Part III: khoanh đỏ bubble sai, xanh bubble đúng."""
    for q, res in results.items():
        blk = PART3_BLOCKS[q - 1]
        student_ans = res.get("student", "")
        if not student_ans or student_ans in ("-", "X"):
            continue  # Bỏ trống → KHÔNG vẽ gì lên bài thi

        q_det = student_details.get(q, {})
        is_correct = res["is_correct"]
        mark_color = COLOR_CORRECT if is_correct else COLOR_WRONG

        # --- Khoanh bubble học sinh đã tô ---
        picked = q_det.get("picked")
        if picked:
            if picked.get("sign"):
                cv2.circle(image, (int(blk["sign_x"]), PART3_SIGN_Y + y_offset),
                           BUBBLE_RADIUS + 3, mark_color, THICKNESS_MARK)
            comma_col = picked.get("comma_col", -1)
            if 0 <= comma_col < len(blk["cols_x"]):
                cx = int(blk["cols_x"][comma_col])
                cv2.circle(image, (cx, PART3_COMMA_Y + y_offset),
                           BUBBLE_RADIUS + 3, mark_color, THICKNESS_MARK)
            for ci, d in enumerate(picked.get("digits", [])):
                if 0 <= d <= 9 and ci < len(blk["cols_x"]):
                    cx = int(blk["cols_x"][ci])
                    cy = int(PART3_DIGIT_START_Y + d * PART3_DIGIT_STEP_Y + y_offset)
                    cv2.circle(image, (cx, cy),
                               BUBBLE_RADIUS + 3, mark_color, THICKNESS_MARK)

        # OCR boxes (handwriting) if present
        ocr_boxes = q_det.get("ocr_boxes", [])
        ocr_digits = q_det.get("ocr_digits", [])
        for i, box in enumerate(ocr_boxes):
            if box is None or i >= len(ocr_digits):
                continue
            if ocr_digits[i] < 0:
                continue
            x1, y1, x2, y2 = box
            cv2.rectangle(image, (x1, y1), (x2, y2), (255, 120, 0), 2)
        else:
            # Sign
            sign_r = q_det.get("sign", 0)
            if sign_r > FILL_THRESHOLD:
                cv2.circle(image, (int(blk["sign_x"]), PART3_SIGN_Y + y_offset),
                           BUBBLE_RADIUS + 3, mark_color, THICKNESS_MARK)
            # Comma
            for ci, r in enumerate(q_det.get("comma", [])):
                if r > FILL_THRESHOLD and ci < len(blk["cols_x"]):
                    cx = int(blk["cols_x"][ci])
                    cv2.circle(image, (cx, PART3_COMMA_Y + y_offset),
                               BUBBLE_RADIUS + 3, mark_color, THICKNESS_MARK)
            # Digits
            for ci, col_ratios in enumerate(q_det.get("digits", [])):
                if ci >= len(blk["cols_x"]):
                    continue
                cx = int(blk["cols_x"][ci])
                for d, r in col_ratios.items():
                    if r > FILL_THRESHOLD:
                        cy = int(PART3_DIGIT_START_Y + int(d) * PART3_DIGIT_STEP_Y + y_offset)
                        cv2.circle(image, (cx, cy),
                                   BUBBLE_RADIUS + 3, mark_color, THICKNESS_MARK)

        # --- Nếu sai: khoanh XANH đáp án đúng ---
        if not is_correct and res["correct"]:
            c_neg, c_comma, c_digits = _parse_p3_string(res["correct"])
            # Sign đúng
            if c_neg:
                cv2.circle(image, (int(blk["sign_x"]), PART3_SIGN_Y + y_offset),
                           BUBBLE_RADIUS + 5, COLOR_RIGHT_ANS, THICKNESS_MARK)
            # Comma đúng
            if 0 <= c_comma < len(blk["cols_x"]):
                cx = int(blk["cols_x"][c_comma])
                cv2.circle(image, (cx, PART3_COMMA_Y + y_offset),
                           BUBBLE_RADIUS + 5, COLOR_RIGHT_ANS, THICKNESS_MARK)
            # Digits đúng
            for ci, d in enumerate(c_digits):
                if 0 <= d <= 9 and ci < len(blk["cols_x"]):
                    cx = int(blk["cols_x"][ci])
                    cy = int(PART3_DIGIT_START_Y + d * PART3_DIGIT_STEP_Y + y_offset)
                    cv2.circle(image, (cx, cy),
                               BUBBLE_RADIUS + 5, COLOR_RIGHT_ANS, THICKNESS_MARK)

        # --- Text đáp án ---
        first_cx = blk["cols_x"][0]
        text_y = PART3_SIGN_Y - 25 + y_offset
        cv2.putText(image, f"={res['student']}",
                    (int(first_cx - 10), int(text_y)),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.45, mark_color, 2)
        if not is_correct:
            cv2.putText(image, f"({res['correct']})",
                        (int(first_cx - 10), int(text_y - 18)),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.38, COLOR_RIGHT_ANS, 2)
    return image


# ╔════════════════════════════════════════════════════════════════════════╗
# ║              CALIBRATION: VẼ LƯỚI BUBBLE DỰ KIẾN                    ║
# ╚════════════════════════════════════════════════════════════════════════╝

def draw_bubble_grid(warped_image, offsets=None):
    """Vẽ tất cả vị trí bubble dự kiến lên ảnh warped (debug/calibration).
    offsets: dict {"part1": dy, "part2": dy, "part3": dy} — bù lệch y cục bộ.
    """
    vis = warped_image.copy()
    dy1 = offsets.get("part1", 0) if offsets else 0
    dy2 = offsets.get("part2", 0) if offsets else 0
    dy3 = offsets.get("part3", 0) if offsets else 0

    # Part I: vòng tròn xanh lá
    for cfg in PART1_COLS:
        col_rows = cfg.get("num_rows", PART1_NUM_ROWS)
        for row in range(col_rows):
            cy = int(cfg["start_y"] + row * cfg["step_y"] + dy1)
            for ci in range(4):
                cx = int(cfg["start_x"] + ci * cfg["step_x"])
                cv2.circle(vis, (cx, cy), BUBBLE_RADIUS, (0, 255, 0), 1)

    # Part II: vòng tròn xanh dương
    for blk in PART2_BLOCKS:
        for ri in range(4):
            cy = int(blk["start_y"] + ri * PART2_STEP_Y + dy2)
            for ci in range(2):
                cx = int(blk["start_x"] + ci * PART2_STEP_X)
                cv2.circle(vis, (cx, cy), BUBBLE_RADIUS, (255, 100, 0), 1)

    # SBD + Mã đề: ô vuông + vòng tròn bên trong
    r = BUBBLE_RADIUS
    cell_half = r + 4  # nửa cạnh ô vuông bao quanh bubble

    for label, cols_x in [("SBD", SBD_COLS_X), ("MD", MADE_COLS_X)]:
        for ci, cx in enumerate(cols_x):
            cx_i = int(cx)
            # Ô vuông header (ô ghi số bên trên, y ~ 130-155)
            hdr_y = SBD_MADE_DIGIT_Y[0] - 40
            cv2.rectangle(vis, (cx_i - cell_half, hdr_y - cell_half),
                          (cx_i + cell_half, hdr_y + cell_half), (200, 0, 200), 1)

            for d, cy in enumerate(SBD_MADE_DIGIT_Y):
                cy_i = int(cy)
                # Ô vuông bao quanh mỗi cell
                cv2.rectangle(vis, (cx_i - cell_half, cy_i - cell_half),
                              (cx_i + cell_half, cy_i + cell_half), (200, 0, 200), 1)
                # Vòng tròn bubble bên trong
                cv2.circle(vis, (cx_i, cy_i), r, (0, 200, 200), 1)

            # Nhãn cột (SBD1..6, MD1..3)
            cv2.putText(vis, f"{ci}", (cx_i - 4, hdr_y + 4),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.35, (200, 0, 200), 1)

    # Part III: vòng tròn đỏ
    for blk in PART3_BLOCKS:
        # Dấu trừ
        cv2.circle(vis, (int(blk["sign_x"]), PART3_SIGN_Y + dy3), BUBBLE_RADIUS, (0, 0, 255), 1)
        for cx in blk["cols_x"]:
            # Dấu phẩy
            cv2.circle(vis, (int(cx), PART3_COMMA_Y + dy3), BUBBLE_RADIUS, (0, 0, 255), 1)
            # Số 0-9
            for d in range(10):
                cy = int(PART3_DIGIT_START_Y + d * PART3_DIGIT_STEP_Y + dy3)
                cv2.circle(vis, (int(cx), cy), BUBBLE_RADIUS, (0, 0, 255), 1)

    # Vẽ vùng erase mask (vàng mờ = vùng xóa, lỗ tròn = bubble bảo vệ)
    overlay = vis.copy()
    for (x1, y1, x2, y2) in TEXT_ERASE_REGIONS:
        cv2.rectangle(overlay, (max(0, int(x1)), max(0, int(y1))),
                       (min(WARP_WIDTH, int(x2)), min(WARP_HEIGHT, int(y2))),
                       (0, 200, 255), -1)
    # Đục lỗ tròn (hiển thị vùng bảo vệ bubble)
    for (cx, cy) in ALL_BUBBLE_CENTERS:
        cv2.circle(overlay, (cx, cy), BUBBLE_PROTECT_RADIUS, vis[cy, cx].tolist() if 0 <= cy < WARP_HEIGHT and 0 <= cx < WARP_WIDTH else (255,255,255), -1)
    cv2.addWeighted(overlay, 0.25, vis, 0.75, 0, vis)

    return vis


# ╔════════════════════════════════════════════════════════════════════════╗
# ║                     PIPELINE CHÍNH (Main)                            ║
# ╚════════════════════════════════════════════════════════════════════════╝

@serialized_grading
def process_sheet(image_path, correct_answers=None, debug=False, pre_warped=False, provided_corners=None, parts_config=None, fast_mode=False,
                  live_bubble_mode=False, live_answer_key_resolver=None, live_validation=False,
                  fast_background_trial=False, live_cpu_fast=None):
    """
    Pipeline đầy đủ: phát hiện góc → warp → tiền xử lý → đọc đáp án → chấm điểm.

    Tham số:
      image_path      : đường dẫn ảnh phiếu
      correct_answers : dict với keys 'part1', 'part2', 'part3'
      debug           : True → lưu ảnh calibration + threshold
      pre_warped      : True → bỏ qua detect corner (ảnh đã thẳng)
      provided_corners: Tọa độ 4 góc được truyền từ frontend (nếu có)
      parts_config    : [p1_count, p2_count, p3_count] — giới hạn số câu quét mỗi phần.
      fast_mode       : True → Bỏ các lượt thử lại tiền xử lý cho camera Live.
      live_cpu_fast   : None → dùng LIVE_CPU_FAST; False → đường lui tiền xử lý cũ.
    """
    # --- Parse parts_config → giới hạn số câu quét mỗi phần ---
    p1_limit = None
    p2_limit = None
    p3_limit = None
    if parts_config and isinstance(parts_config, (list, tuple)):
        p1_limit = parts_config[0] if len(parts_config) > 0 and parts_config[0] is not None else None
        p2_limit = parts_config[1] if len(parts_config) > 1 and parts_config[1] is not None else None
        p3_limit = parts_config[2] if len(parts_config) > 2 and parts_config[2] is not None else None

    try:
        print(f"\n{'='*60}")
        print(f"  Xu ly: {os.path.basename(image_path)}")
        if p1_limit is not None or p2_limit is not None or p3_limit is not None:
            print(f"  Gioi han: P1={p1_limit if p1_limit is not None else 'all'} P2={p2_limit if p2_limit is not None else 'all'} P3={p3_limit if p3_limit is not None else 'all'}")
        print(f"{'='*60}")
    except Exception:
        pass

    # --- Load ảnh ---
    base = os.path.splitext(image_path)[0]
    image = cv2.imread(image_path)
    if image is None:
        print(f"[LỖI] Không đọc được ảnh: {image_path}")
        return None

    # --- Fix EXIF orientation (ảnh camera điện thoại) ---
    try:
        pil_img = Image.open(image_path)
        exif = pil_img._getexif()
        if exif:
            orientation_key = next(
                (k for k, v in ExifTags.TAGS.items() if v == 'Orientation'), None
            )
            if orientation_key and orientation_key in exif:
                orient = exif[orientation_key]
                if orient == 3:
                    image = cv2.rotate(image, cv2.ROTATE_180)
                    print("[EXIF] Xoay 180°")
                elif orient == 6:
                    image = cv2.rotate(image, cv2.ROTATE_90_CLOCKWISE)
                    print("[EXIF] Xoay 90° (phải)")
                elif orient == 8:
                    image = cv2.rotate(image, cv2.ROTATE_90_COUNTERCLOCKWISE)
                    print("[EXIF] Xoay 90° (trái)")
    except Exception:
        pass  # Không có EXIF hoặc lỗi → bỏ qua

    # --- Bước 1-2: Detect corners + Warp ---
    if pre_warped:
        warped = cv2.resize(image, (WARP_WIDTH, WARP_HEIGHT))
        method = "pre_warped"
        _orig_method = method
        corners = None
        all_candidates = []
        print(f"[OK] Ảnh pre-warped ({WARP_WIDTH}x{WARP_HEIGHT})")
    elif provided_corners is not None and len(provided_corners) == 4:
        try:
            pts = np.array(provided_corners, dtype="float32")
            ordered_pts = order_points(pts)
            warped = _warp_to_rect(image, ordered_pts)
            method = "frontend_corners"
            _orig_method = method
            corners = ordered_pts
            all_candidates = []
            print(f"[OK] Sử dụng tọa độ góc từ Frontend: {ordered_pts.astype(int).tolist()}")
        except Exception as e:
            print(f"[LỖI] parse frontend_corners: {e}")
            return None
    else:
        try:
            detect_result = detect_paper_and_warp(image, debug=debug)
            warped = detect_result["warped"]
            method = detect_result["method"]
            _orig_method = method
            corners = detect_result["corners"]
            all_candidates = detect_result.get("_candidates", [])
            print(f"[OK] Phát hiện bằng: {method}")
            print(f"[OK] 4 góc: {corners.astype(int).tolist()}")
            print(f"[OK] Warped → {WARP_WIDTH}x{WARP_HEIGHT}")
            # Lưu ảnh debug detection nếu có
            if debug and detect_result["debug_image"] is not None:
                dbg_path = f"{base}_detect.jpg"
                cv2.imwrite(dbg_path, detect_result["debug_image"])
                print(f"[DEBUG] Ảnh detect → {dbg_path}")
        except ValueError as e:
            print(f"[LỖI] {e}")
            return None

    # --- Bước 2b: Post-warp validation — kiểm tra bubble grid alignment (skip in fast_mode) ---
    if not fast_mode:
        gray_check = cv2.cvtColor(warped, cv2.COLOR_BGR2GRAY) if len(warped.shape) == 3 else warped.copy()
        blurred_check = cv2.GaussianBlur(gray_check, (5, 5), 0)
        circles = cv2.HoughCircles(blurred_check, cv2.HOUGH_GRADIENT, dp=1.2,
                                    minDist=15, param1=50, param2=15,
                                    minRadius=8, maxRadius=18)
        if circles is not None:
            circles = np.round(circles[0, :]).astype(int)
            # Đếm bubble centers có circle gần (< 15px)
            matched = 0
            total_bubbles = len(ALL_BUBBLE_CENTERS)
            for bx, by in ALL_BUBBLE_CENTERS:
                for cx_c, cy_c, _ in circles:
                    if abs(bx - cx_c) < 15 and abs(by - cy_c) < 15:
                        matched += 1
                        break
            match_ratio = matched / max(1, total_bubbles)
            print(f"[OK] Grid alignment: {matched}/{total_bubbles} bubbles matched ({match_ratio:.0%})")
            
            # [IMPROVE] Nếu match ratio thấp → warp sai → thử method khác
            if match_ratio < 0.3 and method != "paper+markers":
                print(f"[WARN] Grid alignment poor ({match_ratio:.0%}) → trying other methods...")
                for cand_score, cand_sharp, cand_warped, cand_corners, cand_method in all_candidates:
                    if cand_method == method:
                        continue
                    cand_gray = cv2.cvtColor(cand_warped, cv2.COLOR_BGR2GRAY) if len(cand_warped.shape) == 3 else cand_warped.copy()
                    cand_blur = cv2.GaussianBlur(cand_gray, (5, 5), 0)
                    cand_circles = cv2.HoughCircles(cand_blur, cv2.HOUGH_GRADIENT, dp=1.2,
                                                      minDist=15, param1=50, param2=15,
                                                      minRadius=8, maxRadius=18)
                    if cand_circles is not None:
                        cand_circles = np.round(cand_circles[0, :]).astype(int)
                        cand_matched = 0
                        for bx, by in ALL_BUBBLE_CENTERS:
                            for cx_c, cy_c, _ in cand_circles:
                                if abs(bx - cx_c) < 15 and abs(by - cy_c) < 15:
                                    cand_matched += 1
                                    break
                        cand_ratio = cand_matched / max(1, total_bubbles)
                        if cand_ratio > match_ratio:
                            print(f"[RETRY] {cand_method}: {cand_matched}/{total_bubbles} ({cand_ratio:.0%}) > {match_ratio:.0%} → switching")
                            warped = cand_warped
                            method = cand_method
                            corners = cand_corners
                            match_ratio = cand_ratio
                            break

    # --- Bước 3: Tiền xử lý (FAST → check → ROBUST → PHONE nếu cần) ---
    import time as _time
    _t0 = _time.time()
    preprocess_mode = "fast"
    raw_live = (
        (os.environ.get('LIVE_CPU_FAST', '0') == '1' if live_cpu_fast is None else live_cpu_fast)
        and live_bubble_mode and live_validation and fast_mode
        and method in ('frontend_corners', 'pre_warped') and not fast_background_trial
    )
    fast_global_background = (
        os.environ.get("LIVE_FAST_BACKGROUND", "0") == "1"
        and fast_background_trial and live_bubble_mode and live_validation and fast_mode
        and method == "frontend_corners"
    )
    if raw_live:
        from grading.engine.live_cpu import raw_gray, part3_grids_aligned
        gray = raw_gray(warped)
        thresh = cleaned = None  # No artificial threshold image feeds the Live reader.
        preprocess_mode = 'live_raw'
    else:
        gray, thresh, cleaned = preprocess(
            warped, mode="fast", fast_global_background=fast_global_background
        )
    print(f"[OK] Preprocess FAST ({_time.time()-_t0:.2f}s)")

    # --- Bước 3b: Detect marker offsets (bù ảnh phồng) ---
    offsets = detect_section_offsets(gray)
    any_offset = any(v != 0 for v in offsets.values())
    if any_offset:
        print(f"[OK] Marker offsets: P1={offsets['part1']:+d}px  P2={offsets['part2']:+d}px  P3={offsets['part3']:+d}px")
    else:
        print("[OK] Marker offsets: 0 (ảnh thẳng)")

    p3_offset = detect_part3_offset_from_digits(gray)
    if p3_offset is not None:
        offsets["part3"] = p3_offset
        print(f"[OK] Part3 offset (digits): {p3_offset:+d}px")

    # --- Bước 4-5: Đọc đáp án (FAST pass) ---
    if raw_live:
        # These legacy answers would be overwritten by validated raw evidence.
        sbd, made, sbd_det, p1_ans, p1_det = '', '', {}, {}, {}
    else:
        sbd, made, sbd_det = extract_sbd_made(gray)
        p1_ans, p1_det = extract_part1(gray, y_offset=offsets["part1"], num_questions=p1_limit, fast_mode=fast_mode)

    # --- Hybrid Decision: try multiple preprocessing, KEEP THE BEST ---
    fast_confs = [_confidence_score(ratios) for ratios in p1_det.values()]
    fast_avg_conf = sum(fast_confs) / max(1, len(fast_confs))
    fast_low = sum(1 for c in fast_confs if c < 0.4)
    fast_blank = sum(1 for a in p1_ans.values() if a == "")

    # Track best result across all preprocessing modes
    best_avg_conf = fast_avg_conf
    best_gray, best_thresh, best_cleaned = gray, thresh, cleaned
    best_offsets = offsets.copy()
    best_sbd, best_made, best_sbd_det = sbd, made, sbd_det
    best_p1_ans, best_p1_det = p1_ans, p1_det
    best_preprocess_mode = preprocess_mode

    need_robust = (not fast_mode) and (fast_low / max(1, len(fast_confs)) > 0.25 or
                                      fast_blank / max(1, len(fast_confs)) > 0.3)

    if need_robust:
        for retry_mode, retry_label, retry_kwargs in [
            ("robust", "ROBUST", {"mode": "robust"}),
            ("enhanced_camera", "ENHANCED", {"enhance_camera": True, "mode": "robust"}),
            ("phone", "PHONE", {"mode": "phone"}),
        ]:
            _t1 = _time.time()
            r_gray, r_thresh, r_cleaned = preprocess(warped, **retry_kwargs)
            r_offsets = detect_section_offsets(r_gray)
            r_p3_offset = detect_part3_offset_from_digits(r_gray)
            if r_p3_offset is not None:
                r_offsets["part3"] = r_p3_offset
            r_sbd, r_made, r_sbd_det = extract_sbd_made(r_gray)
            r_p1_ans, r_p1_det = extract_part1(r_gray, y_offset=r_offsets["part1"], num_questions=p1_limit, fast_mode=fast_mode)

            r_confs = [_confidence_score(ratios) for ratios in r_p1_det.values()]
            r_avg_conf = sum(r_confs) / max(1, len(r_confs))
            r_low = sum(1 for c in r_confs if c < 0.4)
            r_blank = sum(1 for a in r_p1_ans.values() if a == "")

            print(f"[RETRY] {retry_label} avg_conf={r_avg_conf:.2f}, low={r_low}, blank={r_blank} ({_time.time()-_t1:.2f}s)")

            # Keep this result if it's better than the current best
            if r_avg_conf > best_avg_conf:
                print(f"  → {retry_label} better: {r_avg_conf:.3f} > {best_avg_conf:.3f} → switching")
                best_avg_conf = r_avg_conf
                best_gray, best_thresh, best_cleaned = r_gray, r_thresh, r_cleaned
                best_offsets = r_offsets.copy()
                best_sbd, best_made, best_sbd_det = r_sbd, r_made, r_sbd_det
                best_p1_ans, best_p1_det = r_p1_ans, r_p1_det
                best_preprocess_mode = retry_mode
            else:
                print(f"  → {retry_label} worse: {r_avg_conf:.3f} <= {best_avg_conf:.3f} → keeping {best_preprocess_mode}")

            # If quality is now good enough, stop retrying
            good_enough = (r_low / max(1, len(r_confs)) <= 0.25 and
                           r_blank / max(1, len(r_confs)) <= 0.3)
            if good_enough and r_avg_conf >= best_avg_conf:
                print(f"  → {retry_label} good enough, stopping retries")
                break

        print(f"[BEST] Using preprocess: {best_preprocess_mode} (avg_conf={best_avg_conf:.3f})")
    else:
        print(f"[OK] FAST sufficient: avg_conf={fast_avg_conf:.2f}, low={fast_low}, blank={fast_blank}")

    # Restore best results
    gray, thresh, cleaned = best_gray, best_thresh, best_cleaned
    offsets = best_offsets
    sbd, made, sbd_det = best_sbd, best_made, best_sbd_det
    p1_ans, p1_det = best_p1_ans, best_p1_det
    preprocess_mode = best_preprocess_mode
    p1_live_details = {}
    live_validation = live_bubble_mode and live_validation

    if live_bubble_mode:
        from grading.engine import live_bubble_reader as live_reader
        # Evidence must precede text whitening and contrast enhancement.
        # Upload/import defaults remain unchanged; the grading API explicitly
        # opts into the additional raw Part I validation below.
        live_gray = gray if raw_live else (cv2.cvtColor(warped, cv2.COLOR_BGR2GRAY) if warped.ndim == 3 else warped.copy())
        sbd, made, sbd_det = live_reader.read_identifiers(
            live_gray, SBD_COLS_X, MADE_COLS_X, SBD_MADE_DIGIT_Y)
        if live_validation:
            p1_ans, p1_det, p1_live_details = live_reader.read_part1(
                live_gray, PART1_COLS, PART1_CHOICES, BUBBLE_RADIUS, offsets['part1'], p1_limit)
        p2_ans, p2_det = live_reader.read_part2(
            live_gray, PART2_BLOCKS, PART2_STEP_X, PART2_STEP_Y, PART2_ROWS,
            BUBBLE_RADIUS, offsets["part2"], p2_limit, **({'align': True} if live_validation else {}))
        p3_ans, p3_det = live_reader.read_part3(
            live_gray, PART3_BLOCKS, PART3_SIGN_Y, PART3_COMMA_Y,
            PART3_DIGIT_START_Y, PART3_DIGIT_STEP_Y, BUBBLE_RADIUS, offsets["part3"], p3_limit,
            **({'local_symbols': True} if live_validation else {}))
        if raw_live and not part3_grids_aligned(p3_det):
            logger.info('Live raw grid fit incomplete; falling back to legacy preprocessing')
            return process_sheet(
                image_path, correct_answers=correct_answers, debug=debug,
                pre_warped=pre_warped, provided_corners=provided_corners,
                parts_config=parts_config, fast_mode=fast_mode,
                live_bubble_mode=live_bubble_mode,
                live_answer_key_resolver=live_answer_key_resolver,
                live_validation=live_validation, fast_background_trial=fast_background_trial,
                live_cpu_fast=False,
            )
        print("[LIVE OMR] IDs/P2/P3 raw-paper evidence; "
              f"ID grids aligned={sbd_det['sbd_live']['aligned']}/{sbd_det['made_live']['aligned']}; "
              "no CNN/argmax rescue of empty cells")
    else:
        p2_ans, p2_det = extract_part2(gray, y_offset=offsets["part2"], num_questions=p2_limit, fast_mode=fast_mode)
        p3_ans, p3_det = extract_part3(gray, y_offset=offsets["part3"], num_questions=p3_limit, fast_mode=fast_mode)

    # --- Debug output ---
    if debug:
        cv2.imwrite(f"{base}_calibration.jpg", draw_bubble_grid(warped, offsets=offsets))
        cv2.imwrite(f"{base}_gray.jpg", gray)
        if not raw_live:
            cv2.imwrite(f"{base}_thresh.jpg", thresh)
            cv2.imwrite(f"{base}_cleaned.jpg", cleaned)
        print('[DEBUG] Đã lưu: _calibration.jpg, _gray.jpg' +
              ('' if raw_live else ', _thresh.jpg, _cleaned.jpg'))

    # --- Global Quality Gate ---
    # Tính confidence cho Part 1 (số câu thực tế đã quét) — đủ data để đánh giá
    p1_confidences = []
    for q, ratios in p1_det.items():
        p1_confidences.append(_confidence_score(ratios))

    n_total_p1 = len(p1_confidences)
    n_low_conf = sum(1 for c in p1_confidences if c < 0.4)
    n_blank = sum(1 for a in p1_ans.values() if a == "")
    avg_conf = sum(p1_confidences) / max(1, n_total_p1)

    low_conf_ratio = n_low_conf / max(1, n_total_p1)
    blank_ratio = n_blank / max(1, n_total_p1)

    # Quyết định: REJECT nếu quá nhiều câu uncertain hoặc blank
    # More lenient thresholds for pencil marks
    scan_quality = "OK"
    if low_conf_ratio > 0.7 or blank_ratio > 0.7:
        scan_quality = "REJECT_SCAN"
        print(f"\n  ⚠️ REJECT_SCAN: low_conf={n_low_conf}/{n_total_p1} ({low_conf_ratio:.0%}), "
              f"blank={n_blank}/{n_total_p1} ({blank_ratio:.0%}), avg_conf={avg_conf:.2f}")
        print(f"  → Khuyến nghị: Scan lại ảnh với ánh sáng tốt hơn")
    elif low_conf_ratio > 0.5 or blank_ratio > 0.5:
        scan_quality = "LOW_QUALITY"
        print(f"\n  ⚠ LOW_QUALITY: low_conf={n_low_conf}/{n_total_p1}, "
              f"blank={n_blank}/{n_total_p1}, avg_conf={avg_conf:.2f}")
    else:
        print(f"\n  ✓ Scan quality: OK (avg_conf={avg_conf:.2f}, low_conf={n_low_conf}/{n_total_p1})")

    # --- Retry với method khác nếu SBD hoặc Mã đề có '?' (VÔ HIỆU HÓA vì SBD/Made không bắt buộc) ---
    # sbd_has_q = '?' in str(sbd)
    # made_has_q = '?' in str(made)
    # if (sbd_has_q or made_has_q) and len(all_candidates) > 1:
    #     print(f"\n  [RETRY] SBD='{sbd}' MĐ='{made}' có '?' → thử method khác (đã tắt).")


    # Cảnh báo nếu sau tất cả vẫn còn '?'
    if '?' in str(sbd) or '?' in str(made):
        print(f"\n  [CẢNH BÁO] SBD='{sbd}' MĐ='{made}' — "
              f"học sinh chưa tô hoặc ảnh không rõ. Đã thử {len(all_candidates)} method.")

    # --- Ghi lại debug images nếu retry đã chuyển method ---
    if debug and not pre_warped and method != _orig_method:
        cv2.imwrite(f"{base}_calibration.jpg", draw_bubble_grid(warped, offsets=offsets))
        cv2.imwrite(f"{base}_gray.jpg", gray)
        if not raw_live:
            cv2.imwrite(f"{base}_thresh.jpg", thresh)
            cv2.imwrite(f"{base}_cleaned.jpg", cleaned)
        print(f"[DEBUG] Ghi lại debug images cho method: {method}")

    # --- In kết quả ---
    print(f"\n  SỐ BÁO DANH: {sbd}", flush=True)
    print(f"  MÃ ĐỀ      : {made}", flush=True)
    _print_answers(p1_ans, p2_ans, p3_ans)

    # --- IMPROVEMENT 9: Post-processing validation ---
    validation_warnings = []
    for q, detail in p1_live_details.items():
        if detail['needs_review']:
            reason = 'tô nhiều đáp án; không tính điểm câu này' if p1_ans[q] == 'X' else 'ô chưa rõ; không tự chọn đáp án'
            validation_warnings.append(f'Live P1 {q}: {reason}')
    if live_bubble_mode:
        for q, rows in p2_det.items():
            for label, detail in rows.items():
                if live_validation and p2_ans[q][label] == 'X':
                    validation_warnings.append(f'Live P2 {q}{label}: tô cả Đúng và Sai; không tính điểm ý này')
                elif any(e["state"] in ("uncertain", "invalid") for e in detail["live_evidence"]):
                    validation_warnings.append(f"Live P2 {q}{label}: ô mờ/không rõ, cần kiểm tra lại")
        for q, detail in p3_det.items():
            if detail["live_evidence"]["needs_review"]:
                if live_validation:
                    validation_warnings.append(f'Live P3 {q}: ô chưa rõ, tô nhiều ô hoặc số chưa hoàn chỉnh; không tự đoán đáp án')
                else:
                    validation_warnings.append(f"Live P3 {q}: số mờ hoặc tô nhiều ô; không tự đoán đáp án")

    # Check 1: >80% same answer in Part I (possible systematic bias)
    if p1_ans:
        from collections import Counter
        p1_vals = [v for v in p1_ans.values() if v in "ABCD"]
        if p1_vals:
            counter = Counter(p1_vals)
            most_common_answer, most_common_count = counter.most_common(1)[0]
            same_ratio = most_common_count / len(p1_vals)
            if same_ratio > 0.8:
                validation_warnings.append(
                    f"Part I: {same_ratio:.0%} câu đều đáp án '{most_common_answer}' — có thể tô lệch hoặc template sai"
                )

    # Check 2: Too many blanks in Part I
    if p1_ans:
        blank_count = sum(1 for v in p1_ans.values() if v == "")
        blank_ratio = blank_count / max(1, len(p1_ans))
        if blank_ratio > 0.5:
            validation_warnings.append(
                f"Part I: {blank_count}/{len(p1_ans)} câu trống ({blank_ratio:.0%}) — ảnh mờ hoặc góc khuất"
            )

    # Check 3: Part II sub-answer consistency (each question should have 1 answer)
    if p2_ans:
        for q, subs in p2_ans.items():
            filled_subs = [k for k, v in subs.items() if v == "D"]
            empty_subs = [k for k, v in subs.items() if v == ""]
            if len(filled_subs) == 0 and len(empty_subs) == len(subs):
                validation_warnings.append(f"Part II: Câu {q} không có đáp án nào")
            elif len(filled_subs) > 1:
                validation_warnings.append(f"Part II: Câu {q} có {len(filled_subs)} đáp án con được tô")

    # Check 4: Part III answer detection
    # p3_det chứa chi tiết từng câu (sign, comma, digits, digits_score, ...)
    # p3_ans chứa đáp án đã pick (string hoặc rỗng)
    if p3_det and p3_ans:
        for q, det in p3_det.items():
            ans = p3_ans.get(q, "")
            digits_list = det.get("digits", [])
            # Đếm số digit phát hiện được (>= 0)
            digit_count = sum(1 for d_dict in digits_list
                              if isinstance(d_dict, dict) and any(v > 0.15 for v in d_dict.values()))
            # Chỉ cảnh báo nếu CÓ tô (digit_count > 0) nhưng kết quả rỗng → mâu thuẫn
            if digit_count > 0 and not ans:
                validation_warnings.append(
                    f"Part III: Câu {q} có {digit_count} cột tô nhưng không pick được đáp án")

    # Print validation results
    if validation_warnings:
        print(f"\n  ⚠️ CẢNH BÁO VALIDATION ({len(validation_warnings)}):")
        for w in validation_warnings:
            print(f"    • {w}")
    else:
        print(f"\n  ✓ Validation: OK")

    # Select only the answer key AFTER recognition and BEFORE all scoring and
    # overlays. Caller must retain the first key if recognition limits differ.
    if live_bubble_mode and live_answer_key_resolver is not None:
        correct_answers = live_answer_key_resolver(made)

    # --- Bước 6: Chấm điểm (nếu có đáp án đúng) ---
    # Vẽ lên mask trống → blend vào warped (addWeighted overlay)
    result_mask = np.zeros_like(warped)   # mask trống để vẽ kết quả
    result_image = warped.copy()
    total_score = None

    if correct_answers:
        scores = {}
        _p1_max = p1_limit if p1_limit is not None else 40
        _p2_max = p2_limit if p2_limit is not None else 8
        _p3_max = p3_limit if p3_limit is not None else 6

        if "part1" in correct_answers:
            s, r = grade_part1(p1_ans, correct_answers["part1"], num_questions=p1_limit)
            scores["part1"] = s
            if live_validation:
                for q, result in r.items():
                    detail = p1_live_details.get(q)
                    if detail:
                        live_reader.draw_choice_result(result_mask, result, detail['evidence'],
                            detail['points'], PART1_CHOICES, BUBBLE_RADIUS, THICKNESS_MARK)
            else:
                draw_results_part1(result_mask, r, y_offset=offsets["part1"])
            print(f"\n  Phần I  : {s}/{_p1_max}")

        if "part2" in correct_answers:
            s, r = grade_part2(p2_ans, correct_answers["part2"], num_questions=p2_limit)
            scores["part2"] = s
            if live_validation:
                for q, rows in r.items():
                    for label, result in rows.items():
                        detail = p2_det.get(q, {}).get(label)
                        if detail:
                            live_reader.draw_choice_result(result_mask, result, detail['live_evidence'],
                                detail['points'], ('Dung', 'Sai'), BUBBLE_RADIUS, THICKNESS_MARK)
            else:
                draw_results_part2(result_mask, r, y_offset=offsets["part2"])
            print(f"  Phần II : {s}/{_p2_max}")

        if "part3" in correct_answers:
            s, r = grade_part3(p3_ans, correct_answers["part3"], num_questions=p3_limit)
            scores["part3"] = s
            if live_bubble_mode:
                live_reader.draw_part3(result_mask, r, p3_det, PART3_BLOCKS,
                    PART3_SIGN_Y, PART3_COMMA_Y, PART3_DIGIT_START_Y, PART3_DIGIT_STEP_Y,
                    BUBBLE_RADIUS, THICKNESS_MARK, COLOR_CORRECT, COLOR_WRONG, offsets["part3"],
                    **({'warn_ambiguous': True} if live_validation else {}))
            else:
                draw_results_part3(result_mask, r, p3_det, y_offset=offsets["part3"])
            print(f"  Phần III: {s}/{_p3_max}")

        total_score = sum(scores.values())
        max_score = sum([_p1_max if "part1" in scores else 0,
                         _p2_max if "part2" in scores else 0,
                         _p3_max if "part3" in scores else 0])
        print(f"  ─────────────────")
        print(f"  TỔNG ĐIỂM: {total_score}/{max_score}")

        # Ghi điểm to lên mask
        cv2.putText(result_mask, f"DIEM: {total_score}/{max_score}",
                    (30, 55), cv2.FONT_HERSHEY_SIMPLEX, 1.5, (0, 0, 220), 3)

    # Ghi SBD + Mã đề lên mask
    cv2.putText(result_mask, f"SBD: {sbd}  MD: {made}",
                (30, 95), cv2.FONT_HERSHEY_SIMPLEX, 0.8, (180, 0, 0), 2)

    # Blend mask lên warped: nền bài + kết quả bán trong suốt
    result_image = cv2.addWeighted(result_image, 1, result_mask, 0.7, 0)

    # --- Lưu ảnh kết quả (warped) ---
    out_path = f"{base}_result.jpg"
    result_jpeg_quality = 95
    if raw_live:
        try:
            result_jpeg_quality = max(80, min(95, int(os.environ.get('LIVE_RESULT_JPEG_QUALITY', '90'))))
        except ValueError:
            pass
    cv2.imwrite(out_path, result_image, [cv2.IMWRITE_JPEG_QUALITY, result_jpeg_quality])
    print(f"\n[OK] Ảnh kết quả: {out_path}")

    # Tự động gửi ảnh kết quả vào tests/ketqua nếu có thư mục
    try:
        _kq_dir = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))), "tests", "ketqua")
        if os.path.exists(_kq_dir):
            import shutil
            _ts = datetime.now().strftime("%Y%m%d_%H%M%S")
            _stem = os.path.splitext(os.path.basename(image_path))[0]
            _sbd_str = str(sbd).replace('?', '_') if sbd else "nosbd"
            _md_str = str(made).replace('?', '_') if made else "nomd"
            _kq_dst = os.path.join(_kq_dir, f"{_ts}_{_stem}_sbd_{_sbd_str}_md_{_md_str}_result.jpg")
            shutil.copy2(out_path, _kq_dst)
            print(f"[OK] Đã gửi ảnh kết quả vào tests/ketqua: {_kq_dst}")
    except Exception as _e_kq:
        print(f"[WARN] Không thể lưu vào tests/ketqua: {_e_kq}")

    # --- Inverse Warp: nắn kết quả ngược về ảnh gốc ---
    if not pre_warped and corners is not None:
        try:
            dst_pts = np.array([
                [0, 0], [WARP_WIDTH - 1, 0],
                [WARP_WIDTH - 1, WARP_HEIGHT - 1], [0, WARP_HEIGHT - 1]
            ], dtype="float32")
            inv_M = cv2.getPerspectiveTransform(dst_pts, corners)
            h_orig, w_orig = image.shape[:2]
            # Nắn mask kết quả ngược về perspective gốc
            inv_mask = cv2.warpPerspective(result_mask, inv_M, (w_orig, h_orig))
            # Overlay lên ảnh gốc
            overlay_image = cv2.addWeighted(image, 1, inv_mask, 0.8, 0)
            overlay_path = f"{base}_overlay.jpg"
            cv2.imwrite(overlay_path, overlay_image, [cv2.IMWRITE_JPEG_QUALITY, result_jpeg_quality])
            print(f"[OK] Ảnh overlay (inverse warp): {overlay_path}")

            # Gửi cả ảnh overlay vào tests/ketqua
            try:
                if os.path.exists(_kq_dir):
                    import shutil
                    _kq_ov_dst = os.path.join(_kq_dir, f"{_ts}_{_stem}_sbd_{_sbd_str}_md_{_md_str}_overlay.jpg")
                    shutil.copy2(overlay_path, _kq_ov_dst)
            except Exception:
                pass
        except Exception as e:
            print(f"[WARN] Inverse warp failed: {e}")

    # --- Crop vùng tên học sinh từ ảnh warped gốc (sạch) ---
    name_path = ""
    nx, ny, nw, nh = NAME_REGION
    if nw > 0 and nh > 0:
        h_img, w_img = warped.shape[:2]
        y1 = max(0, ny)
        y2 = min(h_img, ny + nh)
        x1 = max(0, nx)
        x2 = min(w_img, nx + nw)
        if y2 > y1 and x2 > x1:
            name_crop = warped[y1:y2, x1:x2]
            name_path = f"{base}_name.jpg"
            cv2.imwrite(name_path, name_crop)
            print(f"[OK] Ảnh tên: {name_path}")

    if not raw_live:
        _load_bubble_cnn()
    cnn_status = 'not_used_live' if raw_live else ("ready" if _CNN_READY else f"error:{_CNN_ERROR}")

    return {
        "sbd": sbd, "made": made,
        "part1": p1_ans, "part2": p2_ans, "part3": p3_ans,
        "score": total_score,
        "max_score": max_score if correct_answers else None,
        "scores": scores if correct_answers else {},
        "details": {"sbd": sbd_det, "part1": p1_det, "part2": p2_det, "part3": p3_det,
                    **({'part1_live': p1_live_details} if live_validation else {})},
        "name_image_path": name_path,
        "detect_method": method if not pre_warped else "pre_warped",
        "offsets": offsets,
        "cnn_status": cnn_status,
        "scan_quality": scan_quality,
        "avg_confidence": round(avg_conf, 3),
        "preprocess_mode": preprocess_mode,
        "validation_warnings": validation_warnings,
        "parts_config": parts_config,
    }


def _print_answers(p1, p2, p3):
    """In đáp án học sinh ra console."""
    p1_max = max(p1.keys()) if p1 else 0
    p2_max = max(p2.keys()) if p2 else 0
    p3_max = max(p3.keys()) if p3 else 0

    print("\n  ── Đáp án học sinh ──")
    if p1_max:
        print("  Phần I:")
        for q in range(1, p1_max + 1):
            a = p1.get(q, "")
            flag = " [!]" if a in ("X", "") else ""
            end = "  " if q % 5 != 0 else "\n"
            print(f"    Q{q:2d}: {a or '-'}{flag}", end=end)
        if p1_max % 5 != 0:
            print()

    if p2_max:
        print("  Phần II:")
        for q in range(1, p2_max + 1):
            qa = p2.get(q, {})
            parts = [f"{r}={qa.get(r, '-')}" for r in PART2_ROWS]
            print(f"    Q{q}: {', '.join(parts)}")

    if p3_max:
        print("  Phần III:")
        for q in range(1, p3_max + 1):
            print(f"    Q{q}: {p3.get(q, '-') or '-'}")


# ╔════════════════════════════════════════════════════════════════════════╗
# ║                      XỬ LÝ HÀNG LOẠT                                ║
# ╚════════════════════════════════════════════════════════════════════════╝

def batch_process(folder, correct_answers=None, debug=False,
                   results_dir="results", excel_path="results/bang_diem.xlsx"):
    """
    Chấm tất cả ảnh .jpg/.png trong thư mục.
    Tự động lưu JSON từng bài + xuất Excel tổng hợp.
    """
    exts = (".jpg", ".jpeg", ".png", ".bmp")
    skip = ("_result", "_calibration", "_thresh", "_cleaned",
            "_simtest", "_sim59", "_simdup")
    files = [f for f in os.listdir(folder)
             if f.lower().endswith(exts) and not any(s in f for s in skip)]
    print(f"Tìm thấy {len(files)} ảnh trong {folder}")
    results = {}
    for fname in sorted(files):
        path = os.path.join(folder, fname)
        res = process_sheet(path, correct_answers, debug=debug)
        results[fname] = res
        if res:
            save_result(res, results_dir, correct_answers)

    # Xuất Excel tổng hợp
    valid = [r for r in results.values() if r is not None]
    if valid:
        export_excel(valid, excel_path)

    return results


# ╔════════════════════════════════════════════════════════════════════════╗
# ║          ĐÁP ÁN MẪU (thay đổi theo đề thi thực tế)                 ║
# ╚════════════════════════════════════════════════════════════════════════╝

SAMPLE_CORRECT = {
    "part1": {i: ["A", "B", "C", "D"][(i - 1) % 4] for i in range(1, 41)},
    "part2": {q: {"a": "Dung", "b": "Sai", "c": "Dung", "d": "Sai"} for q in range(1, 9)},
    "part3": {1: "1234", 2: "-5.67", 3: "0042", 4: "8", 5: "-9999", 6: "31.41"},
}


# ╔════════════════════════════════════════════════════════════════════════╗
# ║      TEST: Tạo phiếu mô phỏng (tô bubble lên ảnh trắng)           ║
# ╚════════════════════════════════════════════════════════════════════════╝

def create_test_sheet(blank_path, output_path, ans_p1=None, ans_p2=None, ans_p3=None,
                      sbd_str=None, made_str=None):
    """
    Tô bubble lên phiếu trắng để tạo ảnh test.
    ans_p1: {1: 'A', 2: 'C', ...}
    ans_p2: {1: {'a': 'Dung', 'b': 'Sai', ...}, ...}
    ans_p3: {1: {'sign': False, 'comma_col': -1, 'digits': [1,2,3,4]}, ...}
    sbd_str: '002568' (6 chữ số)
    made_str: '001' (3 chữ số)
    """
    image = cv2.imread(blank_path)
    if image is None:
        return None
    corners = detect_corners(image)
    warped = warp_perspective(image, corners)

    r = BUBBLE_RADIUS - 2  # Tô nhỏ hơn bubble thật một chút

    # Tô Part I (hỗ trợ tô trùng: "AC" → tô cả A và C)
    if ans_p1:
        choice_map = {"A": 0, "B": 1, "C": 2, "D": 3}
        for q, ans in ans_p1.items():
            col_idx, row_idx = (q - 1) // 10, (q - 1) % 10
            cfg = PART1_COLS[col_idx]
            cy = int(cfg["start_y"] + row_idx * cfg["step_y"])
            for ch in str(ans):
                if ch in choice_map:
                    ci = choice_map[ch]
                    cx = int(cfg["start_x"] + ci * cfg["step_x"])
                    cv2.circle(warped, (cx, cy), r, (0, 0, 0), -1)

    # Tô Part II (hỗ trợ tô trùng: "X" → tô cả Đúng và Sai)
    if ans_p2:
        col_map = {"Dung": 0, "Sai": 1}
        for q, q_ans in ans_p2.items():
            blk = PART2_BLOCKS[q - 1]
            for ri, label in enumerate(PART2_ROWS):
                a = q_ans.get(label, "")
                if a == "X":
                    cy = int(blk["start_y"] + ri * PART2_STEP_Y)
                    for ci in range(2):
                        cx = int(blk["start_x"] + ci * PART2_STEP_X)
                        cv2.circle(warped, (cx, cy), r, (0, 0, 0), -1)
                elif a in col_map:
                    cx = int(blk["start_x"] + col_map[a] * PART2_STEP_X)
                    cy = int(blk["start_y"] + ri * PART2_STEP_Y)
                    cv2.circle(warped, (cx, cy), r, (0, 0, 0), -1)

    # Tô Part III
    if ans_p3:
        for q, data in ans_p3.items():
            blk = PART3_BLOCKS[q - 1]
            if data.get("sign"):
                cv2.circle(warped, (int(blk["sign_x"]), PART3_SIGN_Y), r, (0, 0, 0), -1)
            # comma_col: int hoặc list[int] (tô trùng)
            cc = data.get("comma_col", -1)
            ccs = cc if isinstance(cc, list) else [cc]
            for c in ccs:
                if 0 <= c < len(blk["cols_x"]):
                    cv2.circle(warped, (int(blk["cols_x"][c]), PART3_COMMA_Y), r, (0, 0, 0), -1)
            # digits: mỗi phần tử là int hoặc list[int] (tô trùng)
            for ci, d in enumerate(data.get("digits", [])):
                ds = d if isinstance(d, list) else [d]
                for dd in ds:
                    if 0 <= dd <= 9 and ci < len(blk["cols_x"]):
                        cx = int(blk["cols_x"][ci])
                        cy = int(PART3_DIGIT_START_Y + dd * PART3_DIGIT_STEP_Y)
                        cv2.circle(warped, (cx, cy), r, (0, 0, 0), -1)

    # Tô SBD
    if sbd_str:
        for ci, ch in enumerate(sbd_str):
            if ci < len(SBD_COLS_X) and ch.isdigit():
                d = int(ch)
                cx = SBD_COLS_X[ci]
                cy = SBD_MADE_DIGIT_Y[d]
                cv2.circle(warped, (int(cx), int(cy)), r, (0, 0, 0), -1)

    # Tô Mã đề
    if made_str:
        for ci, ch in enumerate(made_str):
            if ci < len(MADE_COLS_X) and ch.isdigit():
                d = int(ch)
                cx = MADE_COLS_X[ci]
                cy = SBD_MADE_DIGIT_Y[d]
                cv2.circle(warped, (int(cx), int(cy)), r, (0, 0, 0), -1)

    cv2.imwrite(output_path, warped)
    print(f"[TEST] Phiếu mô phỏng: {output_path}")
    return output_path


# ╔════════════════════════════════════════════════════════════════════════╗
# ║                          ENTRY POINT (CLI)                            ║
# ╚════════════════════════════════════════════════════════════════════════╝

if __name__ == "__main__":
    import sys

    SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
    ROOT_DIR   = os.path.dirname(SCRIPT_DIR)

    # Load template + đáp án
    template_path = os.path.join(ROOT_DIR, "templates", "template_default.json")
    answers_path  = os.path.join(ROOT_DIR, "answers", "de_mau.json")
    results_dir   = os.path.join(SCRIPT_DIR, "results")
    os.makedirs(results_dir, exist_ok=True)

    if os.path.exists(template_path):
        load_template(template_path)

    correct = None
    if os.path.exists(answers_path):
        correct = load_answers(answers_path)

    # Chấm ảnh từ command line
    if len(sys.argv) < 2:
        print("Cách dùng: python hi.py <ảnh1.jpg> [ảnh2.jpg] ...")
        print("Hoặc dùng giao diện web: streamlit run app.py")
        sys.exit(0)

    all_results = []
    for img_path in sys.argv[1:]:
        if os.path.isfile(img_path):
            result = process_sheet(img_path, correct_answers=correct, debug=True)
            if result:
                save_result(result, results_dir, correct)
                all_results.append(result)

    if len(all_results) > 1:
        excel_path = os.path.join(results_dir, "bang_diem.xlsx")
        export_excel(all_results, excel_path)

    print(f"\nXong — {len(all_results)} bài đã chấm.")
