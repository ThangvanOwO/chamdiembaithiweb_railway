"""
Test so sánh các giải pháp cho Phần III trên bộ ảnh thực tế anh/:
- Baseline: Cấu hình mặc định hiện tại (P3_OCR_ENABLE = True, col_std_min = 0.0)
- Giải pháp 1: Tắt OCR Fallback (P3_OCR_ENABLE = False)
- Giải pháp 2: Bật Blank Column Detection (col_std_min = 0.035, OCR bật)
- Giải pháp Kết hợp: Tắt OCR Fallback + Bật Blank Column Detection
"""

import os
import sys
import io
import json
from pathlib import Path
import cv2
import numpy as np

# Fix Unicode console encoding on Windows
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding="utf-8", errors="replace")

REPO_ROOT = Path(__file__).resolve().parents[2]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

PART3_DIR = REPO_ROOT / "tests" / "part3"
if str(PART3_DIR) not in sys.path:
    sys.path.insert(0, str(PART3_DIR))

# Import engine & experimental framework
from grading.engine import hi as engine
from experimental_p3 import extract_part3_parametric

# Load template
template_path = REPO_ROOT / "grading" / "engine" / "templates" / "template_default.json"
engine.load_template(str(template_path))

# Kỳ vọng thực tế bằng mắt thường trên ảnh gốc:
EXPECTED_REALITY = {
    "1.jpg": {1: "-1", 2: "2", 3: "0.75", 4: "-90", 5: "1.2", 6: "1925"},
    "1111.jpg": {1: "-1", 2: "2", 3: "0.75", 4: "-90", 5: "1.2", 6: "1925"},
    "2.jpg": {1: "", 2: "", 3: "", 4: "", 5: "", 6: ""},
    "3.jpg": {1: "", 2: "", 3: "", 4: "", 5: "", 6: ""},
    "4.jpg": {1: "", 2: "", 3: "", 4: "", 5: "", 6: ""},
    "9.jpg": {1: "", 2: "", 3: "", 4: "", 5: "", 6: ""},
}

TEST_CONFIGS = {
    "1. Baseline (Hiện tại)": {
        "enable_ocr": True,
        "col_std_min": 0.0,
        "score_min": 0.28,
        "gap_min": 0.05,
    },
    "2. Giải pháp 1 (Tắt OCR)": {
        "enable_ocr": False,
        "col_std_min": 0.0,
        "score_min": 0.28,
        "gap_min": 0.05,
    },
    "3. Giải pháp 2 (Blank Col Std >= 0.035)": {
        "enable_ocr": True,
        "col_std_min": 0.035,
        "score_min": 0.28,
        "gap_min": 0.05,
    },
    "4. Kết hợp (Tắt OCR + Blank Col Std)": {
        "enable_ocr": False,
        "col_std_min": 0.035,
        "score_min": 0.28,
        "gap_min": 0.05,
    },
}

def run_tests():
    anh_dir = REPO_ROOT / "anh"
    img_names = ["1.jpg", "1111.jpg", "2.jpg", "3.jpg", "4.jpg", "9.jpg"]

    print("=" * 80)
    print(" BẢNG KIỂM THỬ SO SÁNH CÁC GIẢI PHÁP CHO PHẦN III TRÊN BỘ ẢNH THẬT ANH/")
    print("=" * 80)

    results_table = {img: {} for img in img_names}

    for img_name in img_names:
        img_path = anh_dir / img_name
        if not img_path.exists():
            continue

        raw = cv2.imread(str(img_path))
        res_warp = engine.auto_deskew_and_crop(raw, debug=False)
        warped = res_warp["warped"]
        gray = cv2.cvtColor(warped, cv2.COLOR_BGR2GRAY) if len(warped.shape) == 3 else warped.copy()
        y_offset = engine.detect_part3_offset_from_digits(gray) or 0

        exp = EXPECTED_REALITY.get(img_name, {})

        print(f"\n>>> ẢNH: {img_name} (y_offset = {y_offset:+d})")
        print(f"    Thực tế trên giấy: {'Có làm bài (tô 6 câu)' if any(exp.values()) else 'Để trống hoàn toàn (0 câu)'}")

        for cfg_name, cfg in TEST_CONFIGS.items():
            ans, det = extract_part3_parametric(
                gray,
                y_offset=y_offset,
                score_min=cfg["score_min"],
                gap_min=cfg["gap_min"],
                col_std_min=cfg["col_std_min"],
                enable_ocr=cfg["enable_ocr"]
            )

            # Đánh giá so với thực tế trên giấy
            correct_q = sum(1 for q in range(1, 7) if ans.get(q, "") == exp.get(q, ""))
            fp_count = 0
            fn_count = 0
            for q in range(1, 7):
                pred = ans.get(q, "")
                truth = exp.get(q, "")
                if truth == "" and pred != "":
                    fp_count += 1
                elif truth != "" and pred != truth:
                    fn_count += 1

            compact_ans = {k: v for k, v in ans.items() if v}
            results_table[img_name][cfg_name] = {
                "ans": ans,
                "compact": compact_ans,
                "correct_q": correct_q,
                "fp": fp_count,
                "fn": fn_count,
                "status": "PASS (6/6)" if correct_q == 6 else f"FAIL ({correct_q}/6)",
            }

            status_symbol = "✓" if correct_q == 6 else "✗"
            print(f"   [{status_symbol}] {cfg_name:38s}: {str(compact_ans):35s} | {results_table[img_name][cfg_name]['status']}")

    print("\n" + "=" * 80)
    print(" TỔNG KẾT HIỆU QUẢ CÁC GIẢI PHÁP TRÊN TOÀN BỘ 6 ẢNH:")
    print("=" * 80)
    print(f"{'Cấu hình':<40s} | {'Số câu đúng (max 36)':<22s} | {'Bắt nhầm (FP)':<15s} | {'Bỏ sót (FN)':<15s}")
    print("-" * 100)

    for cfg_name in TEST_CONFIGS:
        total_correct = sum(results_table[img][cfg_name]["correct_q"] for img in img_names)
        total_fp = sum(results_table[img][cfg_name]["fp"] for img in img_names)
        total_fn = sum(results_table[img][cfg_name]["fn"] for img in img_names)
        print(f"{cfg_name:<40s} | {total_correct:2d}/36 câu ({total_correct/36:6.1%})   | {total_fp:<15d} | {total_fn:<15d}")

    # Ghi kết quả json
    out_json = REPO_ROOT / "tests" / "part3" / "reports" / "p3_solutions_benchmark_result.json"
    out_json.parent.mkdir(parents=True, exist_ok=True)
    with open(out_json, "w", encoding="utf-8") as f:
        json.dump(results_table, f, ensure_ascii=False, indent=2)
    print(f"\nĐã lưu chi tiết vào: {out_json}")

if __name__ == "__main__":
    run_tests()
