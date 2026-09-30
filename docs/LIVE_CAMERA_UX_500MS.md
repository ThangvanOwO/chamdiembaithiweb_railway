# Live Camera — sẵn sàng sau 500 ms (2026-09-11)

Bản ghi này mô tả thay đổi gate trước lần sửa JPEG. Xem [nghiên cứu APK và log thiết bị mới](LIVE_CAMERA_APK_RESEARCH_2026-09-11.md) cho detector toàn ảnh, 30 test, APK mới và thời gian chụp/hậu xử lý thực tế.

## Kế hoạch đã thực hiện

1. Thay gate 10 frame/1.4 giây bằng state machine `searching -> stabilizing -> ready`, đếm thời gian monotonic trên các quan sát hợp lệ.
2. Làm mượt EMA (alpha 0.35), dung sai mỗi marker 3.5% chiều rộng so với vị trí đã làm mượt; giới hạn dịch chuyển tổng 6.5% để tránh chấp nhận di chuyển lớn.
3. Chụp tay gọi `_capturePhoto(manual: true)` ngay, độc lập với trạng thái marker; tự chụp dùng `manual: false` và kiểm tra ready.
4. Đổi tiến độ UI từ số frame sang `0.0/0.5 giây`, animation 400 ms chạy song song. Phân biệt đang chụp với đã chụp/đang kiểm tra ảnh.

## Hành vi

- Mốc ready là 500 ms có bằng chứng ổn định, không yêu cầu 10 frame. Callback đầu tiên đạt mốc sẽ kích hoạt tự chụp; không dùng timer mù khi marker đã biến mất.
- Throttle preview 100 ms, vẫn chỉ chạy một detector một lúc. Thời điểm ready thực tế phụ thuộc thời điểm frame hợp lệ đến; 500 ms là điều kiện ổn định, không phải cam kết toàn bộ quá trình camera/network kết thúc trong 500 ms.
- Rung nhẹ quanh vị trí đã làm mượt giữ nguyên tiến độ.
- Mất marker ngắn tối đa 400 ms giữ tiến độ, không cộng thời gian thiếu bằng chứng và không tự chụp khi đang mất marker. Khi thấy lại marker đúng vị trí thì tiếp tục.
- Frame hợp lệ đến chậm khác với mất marker: gap quan sát tối đa 750 ms vẫn được xử lý, tránh reset do máy chậm. Gap lớn hơn hoặc dịch chuyển lớn bắt đầu chuỗi mới.
- Nút chụp tay không đợi gate hoặc animation. Vẫn phải đợi SDK hoàn tất stop stream/takePicture và kiểm tra JPEG sau chụp. Không loại bỏ validation JPEG, không thay backend/Upload.
- Log `[LiveCamera timing] manual=... shutterMs=... postCaptureMs=...` tách thời gian lấy ảnh khỏi kiểm tra JPEG để debug trên thiết bị.

## Kiểm chứng

21/21 test pass, gồm 6 ca readiness mới: đúng 500 ms ở cadence 50/100/250/500 ms; rung 2% không reset; mất marker ngắn giữ tiến độ; không auto-capture khi frame hiện tại thiếu marker; gap/di chuyển lớn reset; manual độc lập gate. Các regression ảnh thật, EXIF, góc ảnh, threshold và transport vẫn pass.

Analyzer 3 file thay đổi: No issues found. Hai file production thay đổi là `live_camera_screen.dart` và `live_marker_detector.dart`; không sửa pipeline Upload hoặc backend.

## Test trên máy

```powershell
cd 'D:\chamtrac nghien v2\gradeflow_app'
& 'C:\flutter\bin\flutter.bat' test test/live_marker_detector_test.dart test/live_capture_test.dart --reporter expanded '--dart-define=LIVE_SCREENSHOT=C:/Users/Thang/AppData/Local/Temp/codex-clipboard-401879c6-3ede-4689-88a2-8a43a08f0980.png' '--dart-define=LIVE_OVERLAY=D:/chamtrac nghien v2/tests/ketqua/20260910_135818_scan_sbd__9_33__md_____overlay.jpg'
```

## Test thiết bị cần thực hiện

1. Đưa phiếu vào khung, rung tay nhẹ: tiến độ tăng, không quay về 0 liên tục.
2. Bấm chụp ngay khi mới mở Live, trước khi đủ góc: camera phải lấy ảnh ngay; ảnh không hợp lệ có thể yêu cầu chụp lại sau đó.
3. Khi đủ góc liên tục, xác nhận tiến độ đến 0.5 giây và tự chụp một lần.
4. Che góc thoáng qua rồi bỏ ra: giữ tiến độ; che lâu: reset. Di chuyển hẳn sang tờ khác: bắt đầu chuỗi mới.
5. Kiểm tra log shutterMs/postCaptureMs; không đánh đồng độ trễ xử lý JPEG hoặc API với thời gian giữ yên.

Chưa xác nhận thời gian thực trên điện thoại trong phiên này.

## Bản cài kiểm thử

Build release thành công ngày 2026-09-11 (160.6 giây):

- `gradeflow_app/build/app/outputs/flutter-apk/app-arm64-v8a-release.apk` — 44.4 MB, điện thoại ARM64.
- `gradeflow_app/build/app/outputs/flutter-apk/app-armeabi-v7a-release.apk` — 35.3 MB, ARM 32-bit.
- `gradeflow_app/build/app/outputs/flutter-apk/app-x86_64-release.apk` — 51.5 MB, x86_64.

Không dùng `app-release.apk` để kiểm thử lần này: đó là file cũ; lần build này xuất APK theo ABI.
ADB kiểm tra lại trong phiên này vẫn không có thiết bị kết nối.
