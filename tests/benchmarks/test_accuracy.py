"""
IMPROVEMENT 10: Accuracy test suite
Test tat ca anh trong anh/ voi OMR engine da cai tien.
"""
import os
import sys
import time
from pathlib import Path

# Fix Windows console encoding
if sys.platform == "win32":
    sys.stdout.reconfigure(encoding="utf-8")
    sys.stderr.reconfigure(encoding="utf-8")

REPO_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO_ROOT))

from grading.engine.hi import process_sheet

TEST_DIR = str(REPO_ROOT / "anh")

def test_single_image(image_path):
    """Test một ảnh và trả về kết quả."""
    print(f"\n{'='*60}")
    print(f"Testing: {image_path}")
    print(f"{'='*60}")

    t0 = time.time()
    try:
        result = process_sheet(image_path, correct_answers=None, debug=False)
        elapsed = time.time() - t0

        # Analyze results
        p1 = result.get("part1", {})
        p2 = result.get("part2", {})
        p3 = result.get("part3", {})
        sbd = result.get("sbd", "")
        made = result.get("made", "")
        scan_quality = result.get("scan_quality", "UNKNOWN")
        avg_conf = result.get("avg_confidence", 0)
        detect_method = result.get("detect_method", "unknown")
        validation_warnings = result.get("validation_warnings", [])

        # Count non-empty answers
        # NOTE: '' in "ABCD" returns True in Python! Use tuple instead.
        # Part I: A/B/C/D
        p1_filled = sum(1 for v in p1.values() if v in ("A", "B", "C", "D"))
        # Part II: "Dung"/"Sai" (not "D"/"S")
        p2_filled = sum(1 for q_subs in p2.values() for v in q_subs.values() if v in ("Dung", "Sai"))
        # Part III: numbers (not "" or "?")
        p3_filled = sum(1 for v in p3.values() if v not in ("", "?"))

        total_filled = p1_filled + p2_filled + p3_filled

        return {
            "image": os.path.basename(image_path),
            "status": "OK",
            "sbd": sbd,
            "made": made,
            "p1_filled": p1_filled,
            "p2_filled": p2_filled,
            "p3_filled": p3_filled,
            "total_filled": total_filled,
            "scan_quality": scan_quality,
            "avg_confidence": avg_conf,
            "detect_method": detect_method,
            "validation_warnings": len(validation_warnings),
            "time": round(elapsed, 2),
        }
    except Exception as e:
        elapsed = time.time() - t0
        return {
            "image": os.path.basename(image_path),
            "status": "ERROR",
            "reason": str(e),
            "time": round(elapsed, 2),
        }

def main():
    """Chạy test trên tất cả ảnh trong anh/."""
    print("=" * 70)
    print("  GRADEFLOW OMR ACCURACY TEST SUITE")
    print("  Testing images from anh/")
    print("=" * 70)

    # Find all images
    images = []
    for f in os.listdir(TEST_DIR):
        if f.lower().endswith((".jpg", ".jpeg", ".png")):
            # Skip derived images
            skip_suffixes = ["_result", "_thresh", "_name", "_overlay", "_calibration", "_gray", "_cleaned", "_detect"]
            if any(s in f for s in skip_suffixes):
                continue
            images.append(os.path.join(TEST_DIR, f))

    images.sort()
    print(f"\nFound {len(images)} images to test.\n")

    # Run tests
    results = []
    for img in images:
        r = test_single_image(img)
        results.append(r)

        # Print immediate result
        if r["status"] == "OK":
            print(f"  SBD={r['sbd']:6s} | MADE={r['made']:3s} | "
                  f"P1={r['p1_filled']:2d} P2={r['p2_filled']:2d} P3={r['p3_filled']:2d} | "
                  f"conf={r['avg_confidence']:.2f} | {r['detect_method']:15s} | {r['time']:.1f}s | {r['image']}")
        elif r["status"] == "ERROR":
            print(f"  [X] ERROR | {r.get('reason', 'unknown')[:50]} | {r['image']}")

    # Summary
    print(f"\n{'='*70}")
    print("  SUMMARY")
    print(f"{'='*70}")

    ok_results = [r for r in results if r["status"] == "OK"]
    error_results = [r for r in results if r["status"] == "ERROR"]

    if ok_results:
        total = len(ok_results)
        avg_time = sum(r["time"] for r in ok_results) / total
        avg_p1 = sum(r["p1_filled"] for r in ok_results) / total
        avg_p2 = sum(r["p2_filled"] for r in ok_results) / total
        avg_p3 = sum(r["p3_filled"] for r in ok_results) / total

        print(f"\n  Total tested: {total}")
        print(f"  Errors: {len(error_results)}")
        print(f"  Avg P1 filled: {avg_p1:.1f}")
        print(f"  Avg P2 filled: {avg_p2:.1f}")
        print(f"  Avg P3 filled: {avg_p3:.1f}")
        print(f"  Avg processing time: {avg_time:.2f}s")

        # Detect method distribution
        methods = {}
        for r in ok_results:
            m = r["detect_method"]
            methods[m] = methods.get(m, 0) + 1
        print(f"\n  Detect methods:")
        for m, count in sorted(methods.items(), key=lambda x: -x[1]):
            print(f"    {m}: {count} ({count/total*100:.0f}%)")

    print()

if __name__ == "__main__":
    main()
