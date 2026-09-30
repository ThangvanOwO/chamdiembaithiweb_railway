"""
=============================================================================
  KIỂM THỬ TÍCH HỢP TOÀN DIỆN CHAMTN & MẪU PHIẾU QM-2025
=============================================================================
"""
import os
import sys
import json
import os
import django
from pathlib import Path

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT))
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "chamdiemtudong.settings")
django.setup()

import cv2
from django.test import Client
from django.contrib.auth.models import User
from grading.models import Exam, ExamVariant, Submission
from grading.engine.chamtn_core import Template, ChamTNEngine, ScoringEngine
from grading.engine.excel_reporter import export_exam_results_excel
from grading.engine import hi as legacy_hi


def test_templates_loading():
    print("\n[TEST 1] Kiểm tra tải Template JSON QM-2025...")
    tpl_dir = REPO_ROOT / "grading" / "templates_data"
    assert tpl_dir.exists(), "Thư mục templates_data không tồn tại!"
    
    # Priority 1: qm2025_40_08_06
    p1_path = tpl_dir / "qm2025_40_08_06.json"
    assert p1_path.exists(), "qm2025_40_08_06.json không tồn tại!"
    tpl = Template.load_json(str(p1_path))
    assert tpl.counts["p1"] == 40
    assert tpl.counts["p2"] == 8
    assert tpl.counts["p3"] == 6
    assert tpl.counts["sbd"] == 6
    assert tpl.counts["made"] == 3
    assert len(tpl.fields) == 117
    total_bubbles = sum(len(f["opts"]) for f in tpl.fields)
    assert total_bubbles == 584
    print(f"  ✓ Template qm2025_40_08_06: {len(tpl.fields)} fields, {total_bubbles} ô tròn (PASS)")

    json_files = list(tpl_dir.glob("*.json"))
    print(f"  ✓ Tổng số mẫu phiếu QM-2025 đã sinh: {len(json_files)} mẫu (PASS)")


def test_omr_extraction():
    print("\n[TEST 2] Kiểm tra nhận dạng OMR trên các ảnh thực tế (anh/1.jpg -> 4.jpg)...")
    tpl = Template.load_json(str(REPO_ROOT / "grading" / "templates_data" / "qm2025_40_08_06.json"))
    engine = ChamTNEngine(tpl)

    test_cases = [
        ("anh/1.jpg", "035258", "122", "-1", "1925"),
        ("anh/2.jpg", "010124", "122", "", ""),
        ("anh/3.jpg", "123456", "122", "", ""),
        ("anh/4.jpg", "077767", "122", "", "")
    ]

    for rel_path, exp_sbd, exp_made, exp_p3_1, exp_p3_6 in test_cases:
        full_p = REPO_ROOT / rel_path
        if not full_p.exists():
            continue
        img = cv2.imread(str(full_p))
        det = legacy_hi.auto_deskew_and_crop(img, debug=False)
        warped = det["warped"]
        ans = engine.extract_answers(warped)

        assert ans["sbd"] == exp_sbd, f"SBD sai: {ans['sbd']} != {exp_sbd}"
        assert ans["made"] == exp_made, f"Mã đề sai: {ans['made']} != {exp_made}"
        if exp_p3_1:
            assert ans["part3"][1] == exp_p3_1, f"P3.1 sai: {ans['part3'][1]} != {exp_p3_1}"
        if exp_p3_6:
            assert ans["part3"][6] == exp_p3_6, f"P3.6 sai: {ans['part3'][6]} != {exp_p3_6}"

        print(f"  ✓ {rel_path} -> SBD: {ans['sbd']}, Mã đề: {ans['made']}, Sep: {ans['quality']['separation']} (PASS)")


def test_scoring_ladder():
    print("\n[TEST 3] Kiểm tra tính điểm chuẩn Bộ GD&ĐT (Ladder scoring)...")
    mock_ans = {
        "part1": {1: "A", 2: "B", 3: "C"},
        "part2": {
            1: {"a": "D", "b": "S", "c": "D", "d": "S"}, # đúng 4 ý -> 1.0đ
            2: {"a": "D", "b": "D", "c": "S", "d": "S"}, # đúng 2 ý -> 0.25đ
            3: {"a": "D", "b": "S", "c": "S", "d": "S"}, # đúng 1 ý -> 0.1đ
            4: {"a": "S", "b": "S", "c": "S", "d": "S"}, # đúng 0 ý -> 0.0đ
        },
        "part3": {1: "-1.5", 2: "2.0"}
    }
    mock_key = {
        "part1": {1: "A", 2: "B", 3: "D"}, # đúng 2 câu P1 -> 0.5đ
        "part2": {
            1: {"a": "D", "b": "S", "c": "D", "d": "S"},
            2: {"a": "D", "b": "D", "c": "D", "d": "D"},
            3: {"a": "D", "b": "D", "c": "D", "d": "D"},
            4: {"a": "D", "b": "D", "c": "D", "d": "D"}
        },
        "part3": {1: "-1,5", 2: "2"} # đúng cả 2 câu -> 1.0đ
    }
    graded = ScoringEngine.grade_exam(mock_ans, mock_key, p1_pts=0.25, p3_pts=0.5)
    assert graded["p1_score"] == 0.5
    assert graded["p2_score"] == 1.35  # 1.0 + 0.25 + 0.1 + 0.0
    assert graded["p3_score"] == 1.0
    assert graded["total_score"] == 2.85
    print(f"  ✓ P1: {graded['p1_score']}đ, P2 Ladder: {graded['p2_score']}đ, P3 Numeric: {graded['p3_score']}đ -> Tổng: {graded['total_score']}đ (PASS)")


def test_api_and_ui():
    print("\n[TEST 4] Kiểm tra toàn bộ REST API endpoints của ChamTN...")
    client = Client()

    # 1. /chamtn/ SPA UI
    res = client.get("/chamtn/")
    assert res.status_code == 200, f"SPA failed: {res.status_code}"
    print("  ✓ GET /chamtn/ -> 200 OK (ChamTN Studio UI)")

    # 2. Health & Me
    res = client.get("/api/health")
    assert res.status_code == 200 and res.json().get("ok")
    res = client.get("/api/me")
    assert res.status_code == 200 and res.json().get("ok")
    print("  ✓ GET /api/health & /api/me -> 200 OK")

    # 3. Templates list
    res = client.get("/api/templates")
    assert res.status_code == 200
    tpls = res.json().get("items", [])
    assert len(tpls) >= 15
    assert tpls[0]["id"] == "qm2025_40_08_06"
    print(f"  ✓ GET /api/templates -> 200 OK ({len(tpls)} mẫu phiếu)")

    # 4. Create Exam & Batch Grade
    user = User.objects.filter(is_active=True).first()
    res = client.post("/api/exams", json.dumps({
        "name": "Kỳ thi Đánh Giá Năng Lực 2026",
        "subject": "Khoa học Tự nhiên",
        "code": "40-08-06"
    }), content_type="application/json")
    assert res.status_code == 200
    exam_id = res.json()["id"]

    # Upload anh/1.jpg
    with open(str(REPO_ROOT / "anh" / "1.jpg"), "rb") as f:
        res = client.post(f"/api/exams/{exam_id}/grade", {"files": f})
    assert res.status_code == 200
    g_data = res.json()
    assert g_data.get("n_processed") == 1
    sheet_id = g_data["items"][0]["id"]
    print(f"  ✓ POST /api/exams/{exam_id}/grade -> Đã chấm thành công sheet #{sheet_id}")

    # 5. Soát phiếu (Review UI)
    res = client.get(f"/api/sheets/{sheet_id}")
    assert res.status_code == 200
    rev = res.json()
    assert rev["sbd"] == "035258"
    assert rev["made"] == "122"
    print(f"  ✓ GET /api/sheets/{sheet_id} -> Soát phiếu: SBD {rev['sbd']}, Mã đề {rev['made']}")

    # 6. Sửa tay đáp án & tính lại điểm ngay
    raw_ans = rev["answers"]
    raw_ans["part1"]["1"] = "B"
    res = client.put(f"/api/sheets/{sheet_id}", json.dumps({
        "answers": raw_ans,
        "sbd": "035258",
        "made": "122"
    }), content_type="application/json")
    assert res.status_code == 200
    print(f"  ✓ PUT /api/sheets/{sheet_id} -> Sửa tay đáp án thành công, điểm mới: {res.json()['score']}")

    # 7. Xuất Excel 4 sheets
    res = client.get(f"/api/exams/{exam_id}/export.xlsx")
    assert res.status_code == 200
    assert len(res.content) > 5000
    print(f"  ✓ GET /api/exams/{exam_id}/export.xlsx -> Xuất báo cáo Excel 4 sheets ({len(res.content)} bytes)")


if __name__ == "__main__":
    test_templates_loading()
    test_omr_extraction()
    test_scoring_ladder()
    test_api_and_ui()
    print("\n============================================================")
    print("  ★ TẤT CẢ CÁC BÀI KIỂM THỬ ĐÃ VƯỢT QUA 100% THÀNH CÔNG! ★")
    print("============================================================\n")
