"""
Liệt kê tất cả camera khả dụng + tên thiết bị (Windows DirectShow).
Chạy cái này trước để tìm đúng index của Iriun Webcam.
"""
import cv2

try:
    # Dùng pygrabber / DirectShow để lấy tên camera
    from pygrabber.dshow_graph import FilterGraph
    graph = FilterGraph()
    devices = graph.get_input_devices()
    print("\n=== DANH SÁCH CAMERA (Tên thiết bị) ===")
    for i, name in enumerate(devices):
        print(f"  Index {i}: {name}")
    print()
except ImportError:
    print("[INFO] Không có pygrabber. Cài bằng: pip install pygrabber")
    print("[INFO] Đang thử quét index 0-9...\n")

    for idx in range(10):
        # DirectShow backend
        cap = cv2.VideoCapture(idx, cv2.CAP_DSHOW)
        if cap.isOpened():
            ret, frame = cap.read()
            status = "OK - có ảnh" if (ret and frame is not None) else "Mở được nhưng không đọc được"
            w = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
            h = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
            print(f"  Index {idx}: {status}  ({w}x{h})")
            cap.release()
        else:
            cap.release()
            # Thử backend mặc định
            cap2 = cv2.VideoCapture(idx)
            if cap2.isOpened():
                ret, frame = cap2.read()
                status = "OK (no DSHOW)" if (ret and frame is not None) else "Mở được (no DSHOW)"
                print(f"  Index {idx}: {status}")
                cap2.release()

print("\n[XONG] Chạy xong. Nhập index Iriun vào test_camera_scanner.py")
