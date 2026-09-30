# Live Camera false-positive regression

Hướng dẫn hiện tại: [UX 500 ms](LIVE_CAMERA_UX_500MS.md). Kết quả replay hình học: [Live Camera v2](LIVE_CAMERA_V2_VERIFICATION.md).

Phạm vi của bộ này chỉ là `gradeflow_app/lib/screens/live_camera_screen.dart`
và `live_marker_detector.dart`. Luồng Upload/chấm ảnh tĩnh không được dùng để
đánh giá việc tự động chụp.

## Automated cases

Chạy trong thư mục `gradeflow_app/`:

```text
flutter test test/live_marker_detector_test.dart
```

Các điều kiện bắt buộc:

1. Bốn marker vuông đặc, cùng kích thước, đúng bố cục A4 phải được nhận.
2. Frame trắng phải bị loại vì không có tương phản/marker hợp lệ.
3. Blob nhiễu thưa trong cả bốn ROI phải bị loại.
4. Một blob quá lớn hoặc lệch kích thước phải bị loại.

## Device acceptance test

1. Mở Live Camera, đưa bàn tay/bàn/tường có các vật tối vào cả bốn vùng ROI
   nhưng không đưa phiếu vào. Giữ cảnh đó ít nhất 10 giây: không được chụp.
2. Đưa phiếu vào rồi rung/di chuyển liên tục: không được chụp khi chuỗi frame
   bị đứt.
3. Đặt phiếu đúng khung, rung tay nhẹ: tiến độ vẫn tăng, sẵn sàng sau 0.5 giây
   quan sát hợp lệ. Không phụ thuộc bộ đếm 10 frame.
4. Mất marker ngắn giữ tiến độ nhưng không chụp; mất quá 400 ms phải reset.
5. Rời app rồi quay lại: chỉ có một image stream hoạt động, không tăng tốc độ
   callback và không tạo hai lần chụp.
6. Với cùng một tờ phiếu ở cùng ánh sáng, chụp một ảnh bằng Camera thường và
   một ảnh bằng Live Camera (bấm tay). Request Live phải gửi ảnh đã chuẩn hóa
   EXIF/resize cùng tọa độ đo trên ảnh đó; ảnh không được center-crop theo UI,
   resize 1600 px hoặc encode lại quality 82.
   So sánh SBD, mã đề, đáp án và ảnh overlay từ backend. Chỉ khác biệt do ảnh
   gốc thực tế (focus/exposure) mới được chấp nhận, không phải khác biệt do
   client crop theo overlay.

Pass criteria: trong các ca 1, 2 và 4 có 0 lần chụp; ca 3 có đúng 1 lần chụp;
ca 5 không có exception `already streaming`; ca 6 không còn ảnh Live bị cắt
theo khung 3:4 cố định.
