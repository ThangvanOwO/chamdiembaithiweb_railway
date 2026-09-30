# GradeFlow Academic UI — bản thử nghiệm đầu tiên

## Phạm vi đã làm

Đây là giai đoạn ba màn hình mẫu trong kế hoạch được duyệt, chưa phải hoàn thành thiết kế lại toàn bộ app.

- **Tổng quan:** hero navy/teal mang chủ đề học đường; số liệu thật từ API được trình bày thành thẻ tự co giãn; nút Chấm bài/Đề thi chuyển đúng tab hiện có, không tạo bản sao màn hình camera. Giữ danh sách bài gần đây và refresh. Tab Dashboard đổi thành Tổng quan.
- **Xác nhận đáp án:** tiêu đề phân cấp rõ hơn, thẻ thông tin tổng hợp có wrap; ô đáp án lớn, lưới theo chiều rộng/cỡ chữ; P2 dùng wrap thay vì một hàng cố định. Cảnh báo mở rộng theo nhu cầu. Hiển thị lý do chưa thể tiếp tục khi thiếu tên đề hoặc mã đề.
- **Kết quả chấm:** thẻ điểm mới hiển thị ngay điểm thật, SBD/mã đề/số câu đúng; trạng thái lưu chỉ xác nhận nếu response có submissionId. Đưa cảnh báo nhận diện lên gần đầu trang. Giữ phần ảnh, chi tiết đáp án, debug quản trị và nút Quét tiếp đang có.
- **Thành phần chung:** AcademicStyle, AcademicCard, AcademicHeading, AcademicNotice, AcademicMetric, AcademicReveal; không thêm dependency animation.
- **Chuyển động:** xuất hiện fade + dịch 10 logical pixels trong 240 ms, ease-out. Khi hệ điều hành yêu cầu giảm chuyển động thì hiển thị ngay. Không count-up điểm, không animation giả phần trăm, không thay logic chụp.

## Những phần được giữ nguyên

Không sửa backend, API service, payload, model chấm, camera preview/crop/tọa độ, detector, độ nhạy, debounce 500ms, LiveCapture hoặc thuật toán chấm. Không đổi theme toàn app để tránh ảnh hưởng hàng loạt các màn hình chưa được duyệt. Font Manrope/DM Sans hiện có của app vẫn giữ; đóng gói font offline chưa triển khai trong giai đoạn này.

## Kiểm thử

- 9 widget test UI mới đạt: ba trang thành phần ở 320 logical pixels/cỡ chữ 200%; ba lượt render; điều hướng không gọi callback trùng và chế độ giảm chuyển động; semantic labels cho ô chưa rõ; điểm và trạng thái lưu không bị bịa.
- Tổng lượt test Flutter mục tiêu: **35 pass, 7 skip**. Bao gồm test nhập đề và Live đang có. Bảy ca cần screenshot/overlay lịch sử không còn ở đường dẫn cũ bị skip, không tính là pass.
- Analyzer các file chỉnh sửa: exit 0, không error/warning; còn 11 info deprecation/unnecessary import trong phần mã có sẵn.
- `git diff --check` trên bốn màn hình đã chỉnh không báo lỗi whitespace.
- Đã mở và kiểm tra trực quan ba preview; khắc phục thiếu icon/font trong bộ render QA trước khi bàn giao.

Lệnh kiểm tra từ `gradeflow_app`:

```powershell
$env:QA_FONT='C:/flutter/bin/cache/artifacts/material_fonts/Roboto-Regular.ttf'
$env:UI_PREVIEW_OUTPUT='D:/chamtrac nghien v2/tests/ketqua/ui_academic_v1'
& C:/flutter/bin/flutter.bat test --no-pub test/academic_ui_test.dart test/exam_import_service_test.dart test/live_capture_test.dart test/live_marker_detector_test.dart
```

## Preview và giới hạn

`tests/ketqua/ui_academic_v1/dashboard.png`, `answer-review.png`, `result.png` là ảnh render từ widget Flutter thật, với dữ liệu minh họa (không phải điểm thực của học sinh). Khung QA dùng Roboto từ Flutter SDK; app vẫn dùng typography đã có. Đây là preview thành phần, không phải ảnh chụp toàn bộ ba màn hình từ điện thoại: các form nhập tên/mã đề và chi tiết kết quả còn lại được giữ ở màn hình thực tế.

Chưa nghiệm thu trên thiết bị thật, chưa đo FPS/profile/mức tiêu thụ pin; không khẳng định đạt 60 fps chỉ từ widget test. Kiểm tra cỡ chữ lớn mới bao phủ thành phần mới, không phải tất cả biểu đồ/ảnh/debug cũ của app. Chưa sửa các luồng onboarding, đăng nhập, lịch sử, tài khoản và quản trị trong giai đoạn này.

Bước tiếp theo sau khi duyệt phong cách: đưa thiết kế nhất quán sang danh sách đề thi, tạo đề thủ công, lịch sử và các trạng thái tải/trống/lỗi; sau đó mở rộng điều hướng và animation toàn app. Không mở rộng chức năng backend trong đợt UI này.

## Build bàn giao

APK release ARM64 build-number 2008 đã build thành công (Gradle 126.3 giây, khoảng 44.4 MB): `gradeflow_app/build/app/outputs/flutter-apk/gradeflow-academic-ui-v1-2008-arm64.apk`.
Danh sách ADB trống ở lần kiểm tra cuối: chưa cài/chưa thao tác trực tiếp trên điện thoại. Bản 2007 nhập đề vẫn được giữ riêng để đối chiếu; không xóa dữ liệu ứng dụng.
