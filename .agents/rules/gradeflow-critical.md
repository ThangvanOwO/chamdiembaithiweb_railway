# GradeFlow Critical Components Protection Rules

> **Áp dụng cho**: Bảo vệ các file cốt lõi, hợp đồng API và thuật toán OMR của dự án GradeFlow.

---

## 1. Protected Critical Files

Dưới đây là danh sách các file **ĐẶC BIỆT NGUY HIỂM** của hệ thống. Bất kỳ sự thay đổi nào trên các file này đều đòi hỏi sự cẩn trọng tối đa:

| Critical File | Vai Trò & Rủi Ro |
| :--- | :--- |
| [`grading/engine/hi.py`](file:///c:/Users/Thang/Downloads/chamdiembaithiweb/grading/engine/hi.py) | **OMR Core Engine (185KB)**: Thuật toán xử lý ảnh, căn chỉnh góc, xóa chữ in, tính toán tỷ lệ tô. Chỉnh sửa sai sẽ làm hỏng kết quả chấm điểm toàn hệ thống. |
| [`grading/grader.py`](file:///c:/Users/Thang/Downloads/chamdiembaithiweb/grading/grader.py) | **Grader Adapter**: Cầu nối giữa Django ORM và `hi.py`. Sử dụng `sys.path.insert` động. |
| [`grading/models.py`](file:///c:/Users/Thang/Downloads/chamdiembaithiweb/grading/models.py) | **Database Schema**: Chứa các model `Exam`, `ExamVariant`, `Submission`, `TrainingSample`, `UserSettings`. |
| [`api/views.py`](file:///c:/Users/Thang/Downloads/chamdiembaithiweb/api/views.py) | **REST API Monolithic Controller**: Chứa toàn bộ API endpoints mà ứng dụng Flutter đang phụ thuộc. |
| [`grading/views.py`](file:///c:/Users/Thang/Downloads/chamdiembaithiweb/grading/views.py) | **Web Controller Monolith**: Chứa logic xử lý giao diện Web và các thao tác chấm bài trực tiếp. |

---

## 2. Quy Trình Bắt Buộc Khi Phải Sửa Critical File

Nếu task bắt buộc phải chỉnh sửa một trong các **Critical Files** trên, AI phải tuân thủ nghiêm ngặt quy trình 5 bước:

1. **Xác Định Dependency**: Liệt kê tất cả các file/module có import hoặc gọi đến hàm/class sắp sửa.
2. **Kiểm Tra Caller**: Tìm và kiểm tra tất cả các vị trí gọi (call sites) để đảm bảo không vi phạm hàm/hợp đồng tham số.
3. **Kiểm Tra Test**: Tìm các test case sẵn có (như `test_accuracy.py`, `test_engine.py`) liên quan đến module đó.
4. **Review Git Diff**: So sánh diff kỹ lưỡng, đảm bảo không có dòng code thừa hoặc thay đổi ngoài phạm vi.
5. **Kiểm Tra Regression**: Chạy test kiểm thử khả năng tác động ngược (regression) đến các thành phần khác.

---

## 3. Strict System Invariants (Không Được Tự Ý Thay Đổi)

Trừ khi người dùng có yêu cầu thay đổi rõ ràng trong mô tả task, AI **TUYỆT ĐỐI KHÔNG** tự ý thay đổi các thành phần sau:

1. **OMR Algorithm & Thresholds**: Không thay đổi thuật toán xử lý ảnh, các giá trị hằng số như `WARP_WIDTH`, `WARP_HEIGHT`, `FILL_THRESHOLD`, `BUBBLE_RADIUS` trong `hi.py`.
2. **Database Schema**: Không sửa các trường (fields), kiểu dữ liệu (data types), hoặc quan hệ (relationships) trong `grading/models.py` hoặc `accounts/models.py`.
3. **API Contracts**: Không thay đổi tên endpoint, HTTP method, hoặc cấu trúc JSON response trong `api/views.py` vì sẽ làm vỡ Mobile App.
4. **Template Format**: Không thay đổi cấu trúc file JSON tọa độ mẫu phiếu trong `grading/engine/templates/*.json`.
5. **CNN Model Weights**: Không thay đổi hoặc thay thế file mô hình `bubble_cnn.onnx`.
6. **Authentication Flow**: Không thay đổi cơ chế xác thực Session/Token hoặc cấu hình Google OAuth Allauth.
7. **Flutter API Dependencies**: Không thay đổi cách gọi API trong [`gradeflow_app/lib/services/api_service.dart`](file:///c:/Users/Thang/Downloads/chamdiembaithiweb/gradeflow_app/lib/services/api_service.dart).
