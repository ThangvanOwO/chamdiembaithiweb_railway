import cv2
import sys
import os
from pathlib import Path

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT / "grading" / "engine"))

from chamtn_core import Template, ChamTNEngine
import hi

def test_image(img_name="1233332.jpg"):
    img_path = str(REPO_ROOT / "anh" / img_name)
    img = cv2.imread(img_path)
    if img is None:
        print(f"Error: Could not read {img_path}")
        return

    print(f"File: {img_path}")
    print(f"Image shape: {img.shape}")

    # 1. Khởi tạo template và engine ChamTN
    tpl = Template.load_json(str(REPO_ROOT / "grading" / "templates_data" / "qm2025_40_08_06.json"))
    engine = ChamTNEngine(tpl)

    # 2. Phát hiện và nắn thẳng chuẩn bằng ChamTN Alignment (Grid Score Tournament)
    detect_res = engine.detect_and_warp(img)
    print(f"Detection method: {detect_res.get('method')} (Grid Score: {detect_res.get('grid_score', 0):.2f})")
    print(f"Corners:\n{detect_res.get('corners')}")
    warped = detect_res["warped"]

    # 3. Bóc tách đáp án bằng ChamTN Sampler
    res = engine.extract_answers(warped)

    print("\n" + "=" * 50)
    print(f"  KẾT QUẢ NHẬN DIỆN PHIẾU {img_name}")
    print("=" * 50)
    print(f"SỐ BÁO DANH: {res['sbd']}")
    print(f"MÃ ĐỀ THI  : {res['made']}")
    
    print("\n--- PHẦN I (40 CÂU TRẮC NGHIỆM ABCD) ---")
    for blk in range(4):
        q_start = blk * 10 + 1
        items = []
        for q in range(q_start, q_start + 10):
            ans = res["part1"].get(q, "-") or "-"
            items.append(f"Q{q:02d}: {ans}")
        print("  " + "  ".join(items))

    print("\n--- PHẦN II (8 CÂU ĐÚNG / SAI) ---")
    for q in range(1, 9):
        subs = res["part2"].get(q, {})
        s_str = " ".join([f"{s}={subs.get(s, '-')}" for s in ["a", "b", "c", "d"]])
        print(f"  Câu {q}: {s_str}")

    print("\n--- PHẦN III (6 CÂU TRẢ LỜI NGẮN) ---")
    for q in range(1, 7):
        ans = res["part3"].get(q, "")
        print(f"  Câu {q}: {ans if ans else '(bỏ trống)'}")

    print("\n--- CHẤT LƯỢNG QUÉT & ĐỘ PHÂN TÁCH ---")
    q_info = res["quality"]
    print(f"  Kênh đọc vết bút: {q_info.get('mark_channel')}")
    print(f"  Độ hồng nét in  : {q_info.get('print_red')}")
    print(f"  Điểm phân tách  : {q_info.get('separation')} (Ngưỡng > 0.3 là rất rõ)")

if __name__ == "__main__":
    name = sys.argv[1] if len(sys.argv) > 1 else "1233332.jpg"
    test_image(name)
