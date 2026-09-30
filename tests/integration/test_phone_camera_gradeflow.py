"""
Launcher & Tester - Kết nối Camera Điện thoại giả lập GradeFlow APK
Cho phép người dùng lựa chọn phương thức kết nối camera điện thoại để test thực tế.

Cách sử dụng:
  python tests/integration/test_phone_camera_gradeflow.py
"""

import os
import sys
import subprocess
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
SCANNER_SCRIPT = REPO_ROOT / 'tests' / 'integration' / 'test_camera_scanner.py'

if sys.platform == 'win32':
    try:
        sys.stdout.reconfigure(encoding='utf-8')
    except Exception:
        pass


def check_opencv_gui():
    """Kiểm tra opencv có hỗ trợ hiển thị cửa sổ GUI không."""
    try:
        import cv2
        cv2.namedWindow("_test_gui_check", cv2.WINDOW_NORMAL)
        cv2.destroyWindow("_test_gui_check")
        return True
    except Exception:
        return False


def main():
    print("=" * 65)
    print(" 📱 HƯỚNG DẪN KẾT NỐI CAMERA ĐIỆN THOẠI TOÀN DIỆN (GRADEFLOW TEST)")
    print("=" * 65)

    has_gui = check_opencv_gui()
    if not has_gui:
        print(" ⚠️  PHÁT HIỆN: Thư viện OpenCV hiện tại đang ở bản Headless (không mở cửa sổ GUI).")
        print(" 💡 Nếu bạn muốn mở CỬA SỔ HIỂN THỊ TRỰC TIẾP (GUI Window), hãy chạy lệnh sau:")
        print("     pip install opencv-python --force-reinstall\n")
        print(" 📌 Nếu giữ nguyên bản hiện tại: Ứng dụng vẫn sẽ tự động quét, căn chỉnh,")
        print("    chấm bài và ghi ảnh live stream trực tiếp vào thư mục test_scan_output/\n")
    else:
        print(" ✅ Thư viện OpenCV của bạn hỗ trợ đầy đủ Cửa Sổ Hồi Đáp Trực Tiếp (GUI Window)!\n")

    print(" Bạn có thể kết nối camera điện thoại qua 3 phương thức phổ biến:\n")
    print(" 1️⃣  IRIUN WEBCAM (Khuyên dùng - Nhanh & Nét nhất)")
    print("     • Tải app 'Iriun Webcam' trên CH Play / App Store")
    print("     • Tải driver Iriun Webcam cho PC (iriun.com)")
    print("     • Mở app trên đt & PC kết nối chung Wi-Fi hoặc cắm cáp USB.\n")

    print(" 2️⃣  DROIDCAM")
    print("     • Tải app 'DroidCam' trên CH Play / App Store")
    print("     • Mở app DroidCam trên đt & PC.\n")

    print(" 3️⃣  IP WEBCAM (App IP Webcam trên Android)")
    print("     • Tải 'IP Webcam' bởi Pavel Khlebovich trên CH Play")
    print("     • Bấm 'Start server' trên điện thoại")
    print("     • Nhập URL hiển thị trên màn hình (ví dụ: http://192.168.1.15:8080/video)\n")

    print(" 4️⃣  WEBCAM LAPTOP / USB CAMERA THƯỜNG (Index 0, 1, 2...)\n")

    print("-" * 65)
    print(" MỜI BẠN CHỌN PHƯƠNG THỨC KẾT NỐI:")
    print("   [1] Tự động chọn Iriun Webcam / Camera mặc định")
    print("   [2] Nhập IP Camera URL (HTTP / RTSP)")
    print("   [3] Chọn Camera theo Index (0, 1, 2...)")
    print("   [4] Khởi chạy chế độ AUTO-SCAN (Tự động chấm khi đúng vị trí)")
    print("   [0] Thoát")
    print("-" * 65)

    choice = input(" Nhập lựa chọn của bạn (0-4): ").strip()

    cmd = [sys.executable, str(SCANNER_SCRIPT)]

    if choice == '1':
        print("\n [OK] Đang tự động tìm kiếm Iriun Webcam...")
    elif choice == '2':
        url = input(" Nhập URL IP Camera (VD: http://192.168.1.10:8080/video): ").strip()
        if url:
            cmd.extend(["--cam", url])
        else:
            print(" [WARN] URL không hợp lệ, dùng camera mặc định.")
    elif choice == '3':
        idx = input(" Nhập Camera Index (VD: 0 hoặc 1 hoặc 2): ").strip()
        if idx:
            cmd.extend(["--cam", idx])
    elif choice == '4':
        print("\n [OK] Đã bật chế độ Auto-Scan...")
        cmd.append("--auto")
    elif choice == '0':
        print(" Tạm biệt!")
        sys.exit(0)
    else:
        print(" Lựa chọn không hợp lệ, mặc định tìm Iriun Webcam.")

    print(f"\n🚀 Đang chạy lệnh: {' '.join(cmd)}\n")
    subprocess.run(cmd)


if __name__ == "__main__":
    main()
