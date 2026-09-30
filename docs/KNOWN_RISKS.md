# KNOWN RISKS & TECHNICAL DEBT ASSESSMENT

Tài liệu này tổng hợp các **KHU VỰC RỦI RO** và nợ kỹ thuật được ghi nhận trong đợt kiểm tra cấu trúc (Audit). Các nhà phát triển và AI cần tham khảo tài liệu này trước khi tiến hành bất kỳ thay đổi nào.

---

## 1. HIGH RISK AREAS (Rủi Ro Cao)

### 1.1 `grading/engine/hi.py` (Monolithic OMR Core Engine)
- **Đặc điểm**: File đơn có kích thước lên tới **185 KB** (>4,200 dòng code).
- **Lý do Rủi ro**: 
  - Chứa toàn bộ các lớp bảo vệ xử lý ảnh (chống nhiễu chữ in, căn chỉnh góc, warp perspective, bóc tách ô tô, đối chiếu đáp án).
  - Thiếu bộ unit test tự động cách ly cho từng hàm con.
  - Phụ thuộc cao vào các magic numbers và thresholds (`WARP_WIDTH=1400`, `FILL_THRESHOLD=0.15`, `BUBBLE_RADIUS=13`).
- **Tác động nếu sửa đổi không cẩn thận**: Làm sai lệch kết quả chấm điểm trên quy mô lớn, nhận diện sai ô tô/ô trống, vỡ căn chỉnh trên các mẫu phiếu thi khác.
- **Module cần kiểm tra trước khi sửa**: `grading/grader.py`, các script benchmark ở root (`test_accuracy.py`, `test_cnn_vs_cv.py`), các file `templates/*.json`.

### 1.2 Root Directory Hygiene & Hygiene Risks
- **Đặc điểm**: Hơn 23 file Python script thử nghiệm/calibration/test nằm trực tiếp tại thư mục gốc repository (`test_accuracy.py`, `test_camera_scanner.py`, `gen_calibration.py`, `batch_grade.py`...).
- **Lý do Rủi ro**: 
  - Dễ vô tình đè file hoặc đưa dữ liệu rác vào Docker Image / Production deployment build.
  - Gây nhầm lẫn về entry point chính thức của ứng dụng đối với người mới tiếp quản dự án.
- **Tác động nếu xóa nhầm**: Mất các công cụ diagnostic, benchmark và gen calibration dữ liệu khi cần kiểm tra thuật toán.
- **Khuyến nghị**: Di chuyển cẩn trọng vào `tests/` hoặc `tools/` ở các sprint tái cấu trúc chính thức.

---

## 2. MEDIUM RISK AREAS (Rủi Ro Trung Bình)

### 2.1 `grading/views.py` & `api/views.py` (Monolithic Web/API Controllers)
- **Đặc điểm**: 
  - `grading/views.py` có kích thước **59.8 KB**.
  - `api/views.py` có kích thước **41.4 KB**.
- **Lý do Rủi ro**:
  - Tập trung quá nhiều endpoint views vào 1 file duy nhất.
  - Lặp lại logic xử lý (ví dụ: parse Excel/Image đáp án bị trùng giữa API và Web).
  - Trộn lẫn logic điều hướng UI với logic xử lý dữ liệu (thiếu Service Layer).
- **Tác động nếu sửa đổi**: Dễ làm hỏng các router URLs khác trong cùng file, tạo bất đồng bộ giữa Web UI và Mobile API.
- **Module cần kiểm tra trước khi sửa**: `grading/urls.py`, `api/urls.py`, `gradeflow_app/lib/services/api_service.dart`.

### 2.2 Dynamic Import Hack (`sys.path.insert`)
- **Đặc điểm**: [`grading/grader.py`](file:///c:/Users/Thang/Downloads/chamdiembaithiweb/grading/grader.py) nạp module engine qua `sys.path.insert(0, str(ENGINE_DIR))`.
- **Lý do Rủi ro**: Phụ thuộc vào đường dẫn thư mục động runtime, dễ gặp lỗi `ImportError` nếu thay đổi vị trí file hoặc chạy Celery worker ở môi trường khác.
- **Module cần kiểm tra trước khi sửa**: `grading/grader.py`, Celery tasks config.

---

## 3. LOW RISK AREAS (Rủi Ro Thấp)

### 3.1 Oversized Flutter Screens (`gradeflow_app/lib/screens/`)
- **Đặc điểm**: Một số màn hình Flutter có kích thước lớn (>30 KB) như `grade_result_screen.dart`, `exam_import_screen.dart`.
- **Lý do Rủi ro**: Chứa cả layout UI và logic xử lý form/state cục bộ dài dòng, làm giảm khả năng tái sử dụng widget.
- **Tác động nếu sửa đổi**: Ảnh hưởng giao diện màn hình đó, không làm vỡ logic backend.

---

## 4. Checklist An Toàn Trước Khi Thay Đổi Code (Pre-edit Verification)

1. [ ] Kiểm tra xem thay đổi có chạm tới `grading/engine/hi.py` hay không. Nếu có, bắt buộc chạy script benchmark [`test_accuracy.py`](file:///c:/Users/Thang/Downloads/chamdiembaithiweb/test_accuracy.py) để kiểm tra độ chính xác sau chỉnh sửa.
2. [ ] Kiểm tra xem thay đổi trong `api/views.py` có làm thay đổi JSON response schema của Mobile API hay không.
3. [ ] Đối chiếu API contract với [`gradeflow_app/lib/services/api_service.dart`](file:///c:/Users/Thang/Downloads/chamdiembaithiweb/gradeflow_app/lib/services/api_service.dart) nếu thay đổi REST API.
4. [ ] Tuyệt đối không xóa bớt file hoặc refactor cấu trúc thư mục trong các ticket fix bug khẩn cấp.
