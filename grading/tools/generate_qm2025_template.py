"""
Tạo bộ tệp JSON template cho toàn bộ các biến thể QM-2025 trong cacmaubaithi.
Hỗ trợ linh hoạt các cấu hình số câu: (P1, P2, P3).
"""
import json
import os
import re

def build_qm2025_template(p1_count=40, p2_count=8, p3_count=6, tpl_id=None, name=None):
    if not tpl_id:
        tpl_id = f"qm2025_{p1_count:02d}_{p2_count:02d}_{p3_count:02d}"
    if not name:
        name = f"Phiếu QM-2025 ({p1_count} câu P.I / {p2_count} câu P.II / {p3_count} câu P.III)"

    tpl = {
        "id": tpl_id,
        "name": name,
        "version": 1,
        "builtin": True,
        "note": f"Mẫu QM-2025 A4 ({p1_count}-{p2_count:02d}-{p3_count:02d})",
        "page_w": 1400.0,
        "page_h": 1920.0,
        "bubble_w": 26.0,
        "bubble_h": 26.0,
        "fid_w": 32.0,
        "fid_h": 32.0,
        "fiducials": [
            [0.0, 0.0],
            [1400.0, 0.0],
            [1400.0, 1920.0],
            [0.0, 1920.0]
        ],
        "aux": [],
        "counts": {
            "p1": p1_count,
            "p2": p2_count,
            "p2_subs": 4 if p2_count > 0 else 0,
            "p3": p3_count,
            "p3_slots": 4 if p3_count > 0 else 0,
            "sbd": 6,
            "made": 3
        },
        "crops": {
            "name": [255.0, 300.0, 745.0, 60.0],
            "sbd": [1030.0, 140.0, 200.0, 420.0],
            "made": [1270.0, 140.0, 100.0, 420.0],
            "p1": [50.0, 580.0, 1300.0, 460.0],
            "p2": [50.0, 1080.0, 1300.0, 260.0],
            "p3": [50.0, 1370.0, 1300.0, 520.0]
        },
        "fields": []
    }

    fields = tpl["fields"]

    def add_field(field_id, group, kind, opts):
        fields.append({
            "id": field_id,
            "g": group,
            "k": kind,
            "opts": [[str(val), round(float(x), 1), round(float(y), 1)] for val, x, y in opts]
        })

    # 1. Số báo danh (6 cột)
    sbd_cols = [1057, 1085, 1113, 1141, 1169, 1197]
    sbd_y = [173, 206, 249, 285, 326, 363, 401, 440, 480, 517]
    for i, cx in enumerate(sbd_cols):
        opts = [(str(d), cx, sbd_y[d]) for d in range(10)]
        add_field(f"sbd.{i+1}", "sbd", "digit", opts)

    # 2. Mã đề thi (3 cột)
    made_cols = [1292, 1321, 1345]
    for i, cx in enumerate(made_cols):
        opts = [(str(d), cx, sbd_y[d]) for d in range(10)]
        add_field(f"made.{i+1}", "made", "digit", opts)

    # 3. Phần I (Tối đa p1_count câu)
    part1_cols = [
        {"start_x": 82.0,  "start_y": 689.0, "step_x": 72.3, "step_y": 33.1, "q_start": 1},
        {"start_x": 430.0, "start_y": 691.0, "step_x": 74.0, "step_y": 33.1, "q_start": 11},
        {"start_x": 781.0, "start_y": 691.0, "step_x": 73.0, "step_y": 33.1, "q_start": 21},
        {"start_x": 1130.0,"start_y": 691.0, "step_x": 73.0, "step_y": 33.1, "q_start": 31},
    ]
    choices = ["A", "B", "C", "D"]
    for col_info in part1_cols:
        sx = col_info["start_x"]
        sy = col_info["start_y"]
        stx = col_info["step_x"]
        sty = col_info["step_y"]
        q_start = col_info["q_start"]
        for row in range(10):
            q_num = q_start + row
            if q_num > p1_count:
                continue
            cy = sy + row * sty
            opts = [(ch, sx + ci * stx, cy) for ci, ch in enumerate(choices)]
            add_field(f"p1.{q_num}", "p1", "choice", opts)

    # 4. Phần II (Tối đa p2_count câu)
    part2_blocks = [
        {"start_x": 81.0,   "start_y": 1190.0, "q": 1},
        {"start_x": 228.0,  "start_y": 1190.0, "q": 2},
        {"start_x": 430.0,  "start_y": 1190.0, "q": 3},
        {"start_x": 577.0,  "start_y": 1190.0, "q": 4},
        {"start_x": 781.0,  "start_y": 1190.0, "q": 5},
        {"start_x": 927.0,  "start_y": 1190.0, "q": 6},
        {"start_x": 1130.0, "start_y": 1190.0, "q": 7},
        {"start_x": 1276.0, "start_y": 1190.0, "q": 8},
    ]
    part2_step_x = 73.0
    part2_step_y = 33.0
    sub_labels = ["a", "b", "c", "d"]
    for blk in part2_blocks:
        q_num = blk["q"]
        if q_num > p2_count:
            continue
        sx = blk["start_x"]
        sy = blk["start_y"]
        for ri, sub in enumerate(sub_labels):
            cy = sy + ri * part2_step_y
            opts = [
                ("D", sx, cy),
                ("S", sx + part2_step_x, cy)
            ]
            add_field(f"p2.{q_num}.{sub}", "p2", "tf", opts)

    # 5. Phần III (Tối đa p3_count câu)
    part3_blocks = [
        {"sign_x": 81.0,   "cols_x": [90.0,  124.0, 159.0, 192.0],  "q": 1},
        {"sign_x": 313.0,  "cols_x": [324.0, 357.0, 391.0, 425.0],  "q": 2},
        {"sign_x": 547.0,  "cols_x": [557.0, 591.0, 624.0, 659.0],  "q": 3},
        {"sign_x": 780.0,  "cols_x": [790.0, 823.0, 858.0, 892.0],  "q": 4},
        {"sign_x": 1013.0, "cols_x": [1023.0, 1057.0, 1091.0, 1125.0], "q": 5},
        {"sign_x": 1247.0, "cols_x": [1249.0, 1283.0, 1317.0, 1351.0], "q": 6},
    ]
    sign_y = 1490.0
    comma_y = 1522.0
    digit_start_y = 1555.0
    digit_step_y = 33.1

    for blk in part3_blocks:
        q_num = blk["q"]
        if q_num > p3_count:
            continue
        cols = blk["cols_x"]
        add_field(f"p3.{q_num}.sign", "p3", "flag", [("-", blk["sign_x"], sign_y)])
        comma_opts = [(str(ci + 1), cx, comma_y) for ci, cx in enumerate(cols)]
        add_field(f"p3.{q_num}.comma", "p3", "comma", comma_opts)
        for ci, cx in enumerate(cols):
            slot_opts = [(str(d), cx, digit_start_y + d * digit_step_y) for d in range(10)]
            add_field(f"p3.{q_num}.s{ci+1}", "p3", "digit", slot_opts)

    return tpl


def generate_all():
    out_dir = os.path.join(os.path.dirname(os.path.dirname(__file__)), "templates_data")
    os.makedirs(out_dir, exist_ok=True)

    # 15 cấu hình từ cacmaubaithi
    variants = [
        (40, 8, 6, "qm2025_40_08_06", "Phiếu QM-2025 A4 (40-08-06 chuẩn)"),
        (24, 6, 0, "qm2025_24_06_00", "Phiếu QM-2025 A4 (24-06-00)"),
        (26, 2, 0, "qm2025_26_02_00", "Phiếu QM-2025 A4 (26-02-00)"),
        (26, 2, 6, "qm2025_26_02_06", "Phiếu QM-2025 A4 (26-02-06)"),
        (28, 0, 0, "qm2025_28_00_00", "Phiếu QM-2025 A4 (28-00-00)"),
        (28, 2, 0, "qm2025_28_02_00", "Phiếu QM-2025 A4 (28-02-00)"),
        (28, 2, 4, "qm2025_28_02_04", "Phiếu QM-2025 A4 (28-02-04)"),
        (28, 3, 0, "qm2025_28_03_00", "Phiếu QM-2025 A4 (28-03-00)"),
        (28, 4, 0, "qm2025_28_04_00", "Phiếu QM-2025 A4 (28-04-00)"),
        (28, 8, 0, "qm2025_28_08_00", "Phiếu QM-2025 A4 (28-08-00)"),
        (30, 4, 6, "qm2025_30_04_06", "Phiếu QM-2025 A4 (30-04-06)"),
        (32, 2, 0, "qm2025_32_02_00", "Phiếu QM-2025 A4 (32-02-00)"),
        (32, 4, 0, "qm2025_32_04_00", "Phiếu QM-2025 A4 (32-04-00)"),
        (40, 0, 0, "qm2025_40_00_00", "Phiếu QM-2025 A4 (40-00-00)"),
        (40, 4, 0, "qm2025_40_04_00", "Phiếu QM-2025 A4 (40-04-00)"),
    ]

    for p1, p2, p3, tid, name in variants:
        tpl = build_qm2025_template(p1, p2, p3, tid, name)
        out_path = os.path.join(out_dir, f"{tid}.json")
        with open(out_path, "w", encoding="utf-8") as f:
            json.dump(tpl, f, ensure_ascii=False, indent=2)
        n_b = sum(len(f["opts"]) for f in tpl["fields"])
        print(f"  + {tid}: {len(tpl['fields'])} trường, {n_b} ô tròn ({name})")

if __name__ == "__main__":
    generate_all()
