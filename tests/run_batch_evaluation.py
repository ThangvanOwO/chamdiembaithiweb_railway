import sys
import os
import json
import time

sys.stdout.reconfigure(encoding='utf-8')
sys.stderr.reconfigure(encoding='utf-8')
sys.path.insert(0, r'd:\chamtrac nghien v2\grading\engine')

import hi

test_files = [
    r"d:\chamtrac nghien v2\anh\1.jpg",
    r"d:\chamtrac nghien v2\anh\2.jpg",
    r"d:\chamtrac nghien v2\anh\3.jpg",
    r"d:\chamtrac nghien v2\anh\4.jpg",
    r"d:\chamtrac nghien v2\anh\9.jpg",
    r"d:\chamtrac nghien v2\anh\1111.jpg",
    r"d:\chamtrac nghien v2\anh\1233332.jpg",
    r"d:\chamtrac nghien v2\anh\test.jpg",
    r"d:\chamtrac nghien v2\tests\ketqua\20260908_113218_20260908_112319_tmpwqba4twc_sbd_033__1_md_44__overlay_sbd_3__16__md_5_6_overlay.jpg"
]

results = []

print("================================================================================")
print("             HỆ THỐNG CHẤM THI BẮT ĐẦU KIỂM THỬ BATCH TOÀN DIỆN                ")
print("================================================================================")

for fpath in test_files:
    fname = os.path.basename(fpath)
    if not os.path.exists(fpath):
        print(f"[SKIP] File khong ton tai: {fname}")
        continue

    print(f"\n---> ĐANG TEST: {fname}")
    t0 = time.time()
    try:
        res = hi.process_sheet(fpath)
        elapsed = round(time.time() - t0, 2)
        sbd = res.get('sbd', '')
        made = res.get('made', '')
        method = res.get('detect_method', '')
        p1 = res.get('part1', {})
        p2 = res.get('part2', {})
        p3 = res.get('part3', {})
        
        item = {
            'file': fname,
            'status': 'SUCCESS',
            'elapsed_sec': elapsed,
            'method': method,
            'sbd': sbd,
            'made': made,
            'p1_count': len(p1),
            'p2_count': len(p2),
            'p3_count': len(p3),
        }
        results.append(item)
        print(f"  [SUCCESS] SBD={sbd} | Made={made} | Method={method} | P1={len(p1)} P2={len(p2)} P3={len(p3)} ({elapsed}s)")
    except Exception as e:
        elapsed = round(time.time() - t0, 2)
        item = {
            'file': fname,
            'status': 'FAILED',
            'elapsed_sec': elapsed,
            'error': str(e)
        }
        results.append(item)
        print(f"  [FAILED] {e} ({elapsed}s)")

print("\n================================================================================")
print("                           BẢNG TỔNG KẾT KẾT QUẢ                               ")
print("================================================================================")
print(f"{'TÊN FILE':<35} | {'TRẠNG THÁI':<9} | {'SBD':<8} | {'MÃ ĐỀ':<6} | {'THỜI GIAN':<9} | {'GHI CHÚ'}")
print("-" * 90)
for r in results:
    f_short = (r['file'][:32] + '...') if len(r['file']) > 35 else r['file']
    status = r['status']
    sbd = r.get('sbd', '-')
    made = r.get('made', '-')
    sec = f"{r['elapsed_sec']}s"
    note = r.get('method', '') if status == 'SUCCESS' else r.get('error', '')
    print(f"{f_short:<35} | {status:<9} | {sbd:<8} | {made:<6} | {sec:<9} | {note}")

# Save json report
with open(r'd:\chamtrac nghien v2\tests\batch_test_report.json', 'w', encoding='utf-8') as jf:
    json.dump(results, jf, ensure_ascii=False, indent=2)

print("\nĐã lưu báo cáo JSON tại: d:\\chamtrac nghien v2\\tests\\batch_test_report.json")
