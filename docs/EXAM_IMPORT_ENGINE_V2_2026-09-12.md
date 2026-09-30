# Nâng cấp riêng luồng quét phiếu tạo đề

## Nguyên nhân kết quả cũ sai

Sửa UTF-8 trước đó chỉ giúp request chạy xong. Luồng `ExamImportScreen` vẫn bỏ `LiveCapture.corners`, chỉ gửi `capture.bytes` qua `parseImageFile`. Backend phải tìm lại khung bằng pipeline legacy, rồi đọc bằng bộ P2/P3/ID cũ. Vì vậy cùng camera nhưng tạo đề có thể lệch khung và đọc khác với chấm Live đã ổn định.

## Thay đổi

1. Thêm `exam_import_service.dart`, chỉ dùng cho tạo đề bằng camera. Gửi nguyên JPEG cùng bốn góc và kích thước, không nén/resize sau đo góc. Multipart đi `/api/v1/parse-image/`, không gọi API chấm hoặc lưu bài. Protocol `exam_import_capture_v1`.
2. Import worker giữ cách ly UTF-8; xác thực hình học hữu hạn, bốn điểm lồi không tự cắt, nằm trong ảnh, diện tích đủ lớn. Kiểm tra kích thước JPEG thực tế và EXIF đã chuẩn hóa trước khi dùng tọa độ.
3. Gọi engine hiện có với `provided_corners`, `fast_mode=True`, `live_bubble_mode=True` cho camera. Không tìm lại một quartet khác. Tái sử dụng bộ đọc ID/P2/P3 mới, không sửa một dòng thuật toán Live nào.
4. Ảnh thư viện/ứng dụng cũ không có metadata vẫn tự detect, nhưng dùng reader ID/P2/P3 mới. Đường này không được bảo đảm giống camera có tọa độ: **cần APK mới để sửa trọn luồng camera tạo đề**.
5. Mã đề không rõ trả rỗng, không tự bịa `001`. Giao diện tạo đề có ô xác nhận/nhập mã ba chữ số, hiển thị cảnh báo đọc không rõ; tiếp tục yêu cầu tên đề và mã hợp lệ. Các ô không chắc chắn không được ép thành đáp án.
6. Hủy camera không tự mở thư viện; không setState sau khi màn hình bị đóng trong lúc đang xử lý.

Không chỉnh `live_camera_screen.dart`, detector preview/still, `live_capture.dart`, `live_bubble_reader.py`, `hi.py`, template, `gradeLiveCapture`, `ApiService.gradeImage`, API chấm Live/Upload. Không sửa đề/bài nộp đã lưu. Các thay đổi từ các phiên trước vẫn được giữ nguyên.

## Bằng chứng trên JPEG thật

Lấy ảnh 12:51 đã dùng tái hiện lỗi import, chạy qua **chính `prepareLiveCapture` hiện có của Flutter**, lưu cặp `tests/fixtures/exam_import_v1.jpg` và `.json`. Đưa cặp này qua endpoint import thật bằng APIRequestFactory, không ghi database.

Kết quả: HTTP 200, `detect_method=frontend_corners`, mã `001`.

- P3: `-0.2`, `1599`, `-0.8`, `1.25`, `22`, `2100`.
- P2 câu 1: Đ/S/S/Đ; câu 2: Đ/Đ/Đ/S; câu 3–8 không sinh đáp án.
- P1 các câu 31–40 đọc B/C/A/D/C/C/C/B/D/C thay vì mất cả vùng. Q10 không có đáp án xác nhận, không ép chọn từ các dấu tô không rõ/tô nhiều.
- SBD/mã đề/Q5 đã được người dùng xác nhận trong phiên trước; những câu còn lại được đối chiếu trực quan, không coi là tập nhãn độc lập đầy đủ.

Log đầy đủ: `tests/ketqua/exam_import_v2/audit.json`. Chạy lại:

```powershell
python tools/diagnostics/audit_exam_import.py
python -m unittest discover -s tests -p test_answer_image_import.py -q
python -m unittest discover -s tests -p 'test_live_*.py' -q
```

Để tái tạo fixture từ Flutter:

```powershell
cd gradeflow_app
$env:EXPORT_IMPORT_FIXTURE='1'
& C:/flutter/bin/flutter.bat test --no-pub test/exam_import_service_test.dart
```

## Kết quả kiểm thử

- 12/12 test backend import đạt (16.688 giây): ảnh thật/6 đáp án P3, mã đề, vùng P2 trống, tọa độ sai/NaN/ngoài ảnh, JPEG sai kích thước, UTF-8/cp1252, dọn file tạm, timeout và hợp đồng API.
- 17/17 test backend Live cũ đạt (29.133 giây), không sửa các test này.
- 26 test Flutter đạt gồm 3 test import mới; 7 test Live ảnh lịch sử bị skip vì fixture screenshot/overlay cũ không còn ở đường dẫn đã lưu. Không tính skip là pass. Fixture ảnh camera mới thực sự chạy thành công.
- Django system check không có lỗi. Analyzer lần đầu chỉ báo warning/info đã có trong màn hình import; đã bỏ import/biến không dùng tại màn hình này. Các cảnh báo deprecation `withOpacity` không thuộc sửa nhận diện.

## Bàn giao và giới hạn

Bản Android ARM64 build-number 2007 cần cài cùng backend mới. Điện thoại ADB hiện chưa kết nối; chưa cài hoặc thử UI trên thiết bị trong lần nâng cấp này. Cần quét lại phiếu và đối chiếu trước khi lưu, không dùng đề đã tạo từ đáp án sai để đánh giá kết quả mới.

Đây là sửa kết nối pipeline tạo đề với bộ nhận diện hiện có, không tuyên bố chính xác tuyệt đối mọi ảnh/giấy/bút. Ảnh thư viện hoặc APK cũ không có góc camera vẫn có hạn chế tự tìm khung. Bộ test mặc định `widget_test.dart` dạng counter cũ không nằm trong lượt test mục tiêu này.

## APK hoàn tất

Build release ARM64 thành công, Gradle 185.7 giây, build-number 2007.
File bàn giao: `gradeflow_app/build/app/outputs/flutter-apk/gradeflow-import-v2-2007-arm64.apk` (46,570,170 bytes; khoảng 44.4 MiB).
SHA256: `B4D3A08DCA0BEAE471244CD165CBB8CC4738EB7577088B968FD6038F13556468`.
Analyzer service/test import mới: **No issues found**. Chưa cài thiết bị do danh sách ADB trống.
