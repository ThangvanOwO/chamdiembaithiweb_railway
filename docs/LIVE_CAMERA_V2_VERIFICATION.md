# Live Camera v2 — bản sửa và bằng chứng

> Cập nhật UX 2026-09-11: gate 10 frame/1.4 giây trong bản ghi này đã được thay bằng [gate 500 ms và dung sai rung](LIVE_CAMERA_UX_500MS.md).

## Thay đổi

- Detector dùng tương phản cục bộ thay cho ngưỡng đen tuyệt đối 55/68; kiểm tra vùng đặc, hình dạng, kích thước và hình học bốn marker. ROI có nhiều ứng viên hợp lệ bị từ chối.
- Xử lý rotation 0/90/180/270 và row/pixel stride rõ ràng. Frame thiếu dữ liệu bị loại. Exception có log, không im lặng giữ viền đỏ.
- Gate dùng đồng hồ monotonic, 10 frame ổn định và ít nhất 1.4 giây. Một frame mất marker, gap >750 ms hoặc dịch chuyển tích lũy >1.2% chiều rộng sẽ reset.
- Chụp tay và tự động cùng chạy `prepareLiveCapture`: decode, chuẩn hóa EXIF một lần, resize tối đa 2000 px chiều rộng, đo marker trên JPEG nguồn đã chuẩn hóa; encode quality 95. Không crop theo overlay hoặc tự warp ở client.
- Kết quả trả về có kiểu `LiveCapture`: ảnh và tọa độ pixel TL/TR/BR/BL đi cùng nhau. Từ chối capture thiếu marker hoặc vùng nội dung không đủ tương phản.
- `live_grading_service.dart` gửi nguyên cặp ảnh/tọa độ vào trường `corners` backend đã hỗ trợ. Không đi qua nhánh nén Upload 800 KB; tránh scale sai tọa độ. Backend warp một lần.
- Đã cập nhật các nơi mở Live Camera: chấm đơn, batch, admin test và import đáp án. Chấm đơn/batch/admin dùng transport Live; import chỉ thích nghi kiểu kết quả, vẫn dùng API parse hiện có.
- Đã bỏ rung mạnh ngay trước chụp, chỉ chạy animation khi chụp và không khóa AF/AE vì chỉ thấy hình học marker.

Backend và `api_service.dart` không được chỉnh trong bản sửa này. Các màn hình dùng chung chỉ được thêm/đổi phần nhận và gửi kết quả Live; đường ảnh Gallery/camera thường vẫn gọi `ApiService.gradeImage` như trước.

## Bằng chứng replay ảnh người dùng

- Screenshot: `codex-clipboard-401879c6-3ede-4689-88a2-8a43a08f0980.png`, 1220x2712. Test lấy đúng vùng preview y=449, h=1627, chạy detector thật và capture processor thật.
- Overlay lịch sử: `tests/ketqua/20260910_135818_scan_sbd__9_33__md_____overlay.jpg`, 709x949.
- Tọa độ mới đo trên overlay: TL=(60,54), TR=(657,54), BR=(644,882), BL=(65,881). Tất cả nằm trong 5 pixel so với vị trí kiểm tra ngoài cùng.
- Đối chiếu trước đó suy ra khung warp sai gần TL=(64,56), TR=(594,107), BR=(639,877), BL=(112,825). Góc phải trên/trái dưới cũ lệch rõ.
- `tests/live_camera_replay_warp.py` lấy đúng helper `_warp_to_rect` và kích thước đích từ mã backend bằng AST, chạy với tọa độ mới; không import các tác vụ chấm/lưu/model của backend.
- Ảnh kiểm tra: `tests/ketqua/live_v2_replay/verified_corners_warp.jpg`.

**Ảnh replay chỉ chứng minh hình học.** Vòng tròn đỏ và điểm 0/54 đã có sẵn trên overlay nguồn, không phải kết quả chấm mới. Chưa có căn cứ tuyên bố độ đúng đáp án 100% hoặc không còn false-positive trong mọi môi trường.

## Chạy lại test

Kết quả trong phiên sửa: **16/16 test pass**, bao gồm hai fixture thực (không skip).
Analyzer 6 file core/test Live: **No issues found**. Build `flutter build apk --debug` thành công;
APK tại `gradeflow_app/build/app/outputs/flutter-apk/app-debug.apk`.

```powershell
cd 'D:\chamtrac nghien v2\gradeflow_app'
& 'C:\flutter\bin\flutter.bat' test test/live_marker_detector_test.dart test/live_capture_test.dart --reporter expanded '--dart-define=LIVE_SCREENSHOT=C:/Users/Thang/AppData/Local/Temp/codex-clipboard-401879c6-3ede-4689-88a2-8a43a08f0980.png' '--dart-define=LIVE_OVERLAY=D:/chamtrac nghien v2/tests/ketqua/20260910_135818_scan_sbd__9_33__md_____overlay.jpg'
```

Hai test ảnh thực sẽ báo skip nếu không truyền đường dẫn. Giữ ảnh nguồn khi chạy trên máy khác. Các ca khác kiểm tra marker xám, frame tối/trắng, dữ liệu thiếu, xoay + padding, kích thước sai, hình tròn giả, EXIF trong isolate, thiếu marker khi chụp tay, debounce và giữ nguyên multipart >800 KB.

## Kiểm tra trên điện thoại

1. Cài APK mới. Mở Live và xem log có tiền tố `[LiveCamera v2]` để xác nhận đúng bản.
2. Đưa toàn bộ phiếu vào khung; marker phải vẫn nhận dưới ánh sáng như screenshot. Chụp tay thiếu một góc phải yêu cầu chụp lại, không gửi ảnh để chấm.
3. Rung giấy hoặc che marker giữa chuỗi frame: không được tự chụp. Giữ yên đủ lâu: chụp một lần.
4. Chụp cùng phiếu bằng Live và Gallery, đối chiếu SBD/mã đề/đáp án với dữ liệu chuẩn do người dùng xác nhận. Kiểm tra kết quả ở backend dùng `frontend_corners` cho request Live.
5. Chuyển nền/quay lại và xoay điện thoại: không nhận kết quả frame cũ, không treo stream.

ADB chưa thấy thiết bị khi kiểm tra trong phiên này; chưa thực hiện bước camera thật. Analyzer các file Live mới sạch; các màn hình dùng chung còn lint cũ (unused/deprecated) ngoài phạm vi sửa.
