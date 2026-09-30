"""
Debug test: Chạy 1 ảnh và in chi tiết kết quả để tìm bug.
"""
import os
import sys
from pathlib import Path

# Fix Windows console encoding
if sys.platform == "win32":
    sys.stdout.reconfigure(encoding="utf-8")
    sys.stderr.reconfigure(encoding="utf-8")

REPO_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO_ROOT))

from grading.engine.hi import process_sheet

# Test 1 ảnh
image_path = str(REPO_ROOT / "cacmaubaithi" / "40-00-00---QM-2025---A4--Ky-kiem-tra" / "40 00 00 - QM 2025 - A4 -Ky kiem tra_page-0001.jpg")

print(f"Testing: {image_path}")
print(f"File exists: {os.path.exists(image_path)}")
print()

result = process_sheet(image_path, correct_answers=None, debug=False)

print("=== RESULT KEYS ===")
print(list(result.keys()))
print()

print("=== PART1 ===")
p1 = result.get("part1", {})
print(f"Type: {type(p1)}")
print(f"Keys (first 5): {list(p1.keys())[:5]}")
print(f"Values (first 10): {list(p1.values())[:10]}")
print()

# Count filled
p1_filled = sum(1 for v in p1.values() if v in "ABCD")
print(f"p1_filled (v in 'ABCD'): {p1_filled}")

# Count all non-empty
p1_nonempty = sum(1 for v in p1.values() if v != "")
print(f"p1_nonempty (v != ''): {p1_nonempty}")

# Count X
p1_x = sum(1 for v in p1.values() if v == "X")
print(f"p1_x (v == 'X'): {p1_x}")

# Count blank
p1_blank = sum(1 for v in p1.values() if v == "")
print(f"p1_blank (v == ''): {p1_blank}")

# Show all values
print(f"\nAll P1 values: {dict(list(p1.items())[:20])}")
print()

print("=== PART2 ===")
p2 = result.get("part2", {})
print(f"Type: {type(p2)}")
if p2:
    first_key = list(p2.keys())[0]
    print(f"First key: {first_key}, value type: {type(p2[first_key])}")
    print(f"First value: {p2[first_key]}")
print()

print("=== PART3 ===")
p3 = result.get("part3", {})
print(f"Type: {type(p3)}")
print(f"Values (first 10): {list(p3.values())[:10]}")
print()

print("=== SCAN QUALITY ===")
print(f"scan_quality: {result.get('scan_quality', 'N/A')}")
print(f"avg_confidence: {result.get('avg_confidence', 'N/A')}")
print(f"detect_method: {result.get('detect_method', 'N/A')}")
print(f"validation_warnings: {result.get('validation_warnings', [])}")
