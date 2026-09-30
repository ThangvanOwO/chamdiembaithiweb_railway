# Nhật ký nghiên cứu: Live Camera nhận sai marker và ảnh chụp thủ công

> Bản ghi lịch sử. Chẩn đoán sau đó xác nhận thêm ngưỡng marker quá tối và bộ góc warp sai; bỏ crop một mình chưa đủ. Bản sửa/kết quả hiện tại xem [Live Camera v2](LIVE_CAMERA_V2_VERIFICATION.md).

**Ngày:** 2026-09-10  
**Phạm vi:** Chẩn đoán luồng Live Camera. Không thay đổi luồng tải ảnh lên để chấm.

## Kết luận ngắn

Đây không phải chỉ là lỗi detector 4 marker. Ảnh từ Live Camera và ảnh tĩnh hiện **không đi vào backend với cùng dữ liệu**:

- Ảnh tĩnh/camera thường gửi ảnh gốc (chất lượng 95, không giới hạn kích thước).
- Live Camera, kể cả khi bấm nút chụp thủ công, luôn xoay, cắt theo một hình chữ nhật 3:4 cố định, resize tối đa 1600 px và JPEG quality 82 trước khi gửi.

Vì vậy marker ở preview có thể đúng nhưng ảnh chụp thật vẫn bị cắt sai khi tờ giấy lệch, xa/gần, hoặc có perspective. Bốn marker hiện chỉ được dùng để *cho phép chụp*; chúng không được chuyển thành bốn toạ độ thực trên ảnh JPEG để nắn phối cảnh. Đây là nguyên nhân phù hợp nhất với ảnh kết quả bị lệch/cắt trong `tests/ketqua`.

## Bằng chứng từ mã hiện tại

| Luồng | Dữ liệu gửi để chấm | Hệ quả |
|---|---|---|
| Tải ảnh/Gallery và camera thường | `scan_screen.dart:_pickFromCamera` lấy ảnh `imageQuality: 95`, sau đó `_setScannedFile` đọc bytes gốc. | Backend nhận ảnh gần với ảnh người dùng nhìn thấy. |
| Live Camera tự động | `AutoScanScreen._capturePhoto()` gọi `takePicture()`, rồi luôn gọi `_cropImageToOverlay()`. | Không gửi ảnh JPEG gốc vừa chụp. |
| Live Camera chụp thủ công | Nút thủ công cũng gọi đúng `_capturePhoto()`. | Vẫn chịu cùng crop/resize/nén; vì thế lỗi ở manual capture chứng minh lỗi không chỉ nằm ở debounce tự chụp. |
| Crop Live hiện tại | Xoay portrait nếu cần, center-crop 3:4, crop theo `cornerRatios` cố định, padding 2%, resize 1600 px, JPEG quality 82. | Không có homography/perspective warp theo bốn marker thật; hard-code này không thể đúng với mọi khoảng cách và góc máy. |
| API hiện tại | `ApiService.gradeImage` có thể gửi trường `corners`; `api/views.py` đã đọc và truyền nó vào `grade_image`. Nhưng `ScanScreen._gradeImage()` không truyền corners. | Backend **có sẵn đường nhận toạ độ**, nhưng Live hiện không dùng nó. |

Các vị trí cần đối chiếu trực tiếp:

- `gradeflow_app/lib/screens/live_camera_screen.dart:365` — cả auto lẫn manual đi qua `_capturePhoto`.
- `gradeflow_app/lib/screens/live_camera_screen.dart:820` — `_cropImageToOverlay` dùng fixed crop, không perspective warp.
- `gradeflow_app/lib/screens/scan_screen.dart:190` — camera thường lấy ảnh chất lượng 95.
- `gradeflow_app/lib/screens/scan_screen.dart:225` — request chấm hiện không truyền `corners`.
- `gradeflow_app/lib/services/api_service.dart:261` và `api/views.py:500` — API/backend đã hỗ trợ `corners` tùy chọn.

## Vì sao preview nhận marker khó hơn ảnh tĩnh

1. **Độ phân giải và ánh sáng:** stream dùng mặt phẳng YUV giảm độ phân giải, auto-exposure/focus còn dao động; ảnh tĩnh được ISP xử lý đầy đủ trước khi lưu JPEG.
2. **Khác hệ toạ độ:** preview, frame stream và JPEG chụp có thể khác hướng, tỷ lệ, crop sensor và mirror. Tỷ lệ overlay trên màn hình không phải là tọa độ marker trên JPEG độ phân giải cao.
3. **Marker không phải hình học đầu vào:** detector hiện phát hiện ở frame preview để mở khoá UI, nhưng crop hậu chụp bỏ kết quả detector đó và dùng một khung chữ nhật cố định.
4. **OMR rất nhạy chi tiết:** resize nội suy và JPEG quality 82 thay đổi nét viền/độ đen của ô tròn. Điều này làm tăng nguy cơ backend nhận sai ô, kể cả khi crop không bị lệch.
5. **Manual không phải “ảnh tĩnh chuẩn”:** manual Live có camera API khác và một pipeline hậu xử lý khác `_pickFromCamera`; do đó không thể dùng nó để kết luận backend sai.

## Đối chiếu kiến trúc mã nguồn mở

### Flutter `document_scan`

Dự án tách riêng `DocumentDetector` (tìm corners trên stream) và `DocumentProcessor` (nắn/crop ảnh). Nó dùng `CornerStabilizer` và `AutoCaptureAnalyzer` cho preview, sau đó xử lý **ảnh vẫn bằng bộ corners tương ứng** hoặc corners do người dùng chỉnh. Đây là mẫu kiến trúc phù hợp nhất: preview chỉ để hướng dẫn/chống rung; ảnh JPEG cuối cùng mới là nguồn chân lý để nắn phối cảnh.

Nguồn: https://github.com/Ozdemiroguz/document_scan

### OMRChecker

OMRChecker là engine template-driven xử lý scan/ảnh điện thoại. Tài liệu của họ ghi rõ ảnh điện thoại đáng tin hơn khi phiếu có marker in sẵn; pipeline dùng `CropOnMarkers` để crop theo marker thực. Nó không coi overlay UI là một crop hình học chính xác; marker là dữ liệu đầu vào của preprocessing.

Nguồn: https://github.com/Udayraj123/OMRChecker  
Hướng dẫn `CropOnMarkers`: https://github.com/Udayraj123/OMRChecker/wiki/%5Bv1%5D-User-Guide

### Google ML Kit Document Scanner

ML Kit làm toàn bộ detect/crop/filter ngay trên thiết bị và trả về file scan đã chuẩn hóa cho app. Backend, nếu có, chỉ nhận file cuối để lưu hoặc phân tích nghiệp vụ. Nó cho phép người dùng crop/chỉnh lại, vì detector không nên là điểm quyết định không thể sửa.

Nguồn: https://developers.google.com/ml-kit/vision/doc-scanner?authuser=2  
Sample: https://github.com/googlesamples/mlkit/tree/master/android/documentscanner

### Bài học chung

| Việc | Làm tại client preview | Làm trên ảnh chụp thật / backend |
|---|---|---|
| Xác định có giấy/marker, cảnh báo mờ, chống rung, debounce | Có | Không bắt buộc |
| Xác định quadrilateral cuối cùng | Có thể gợi ý | Bắt buộc kiểm tra lại trên JPEG gốc |
| Perspective warp/crop | Có thể làm on-device | Hoặc backend, nhưng phải dùng corners thật của JPEG |
| Chấm bubble/điểm | Không cần ở stream | Backend OMR phù hợp |

## Có cần đụng backend không?

**Không cần sửa Django/backend để khắc phục nguyên nhân chính.** Backend hiện đã xử lý tốt hơn khi nhận ảnh nguồn đúng; test batch trên ảnh tĩnh có 8/8 request `SUCCESS`. Live cần ngừng biến đổi ảnh bằng crop cố định và gửi ảnh JPEG gốc (hoặc bản perspective-warp thực) vào đúng endpoint hiện tại.

Backend chỉ cần tham gia thêm nếu chọn kiến trúc tối ưu sau:

1. Client phát hiện bốn góc trên **JPEG gốc sau khi chụp**, chuẩn hóa chúng về tọa độ JPEG.
2. Client gửi `corners` cùng JPEG vào endpoint `/api/v1/grade/`.
3. Backend dùng đúng đường `provided_corners` vốn đã có, rồi thực hiện perspective warp và OMR.

Điều này không đụng tới luồng upload ảnh: chỉ Live Camera gửi thêm metadata tùy chọn. Không nên bắt upload tĩnh gửi `corners` hoặc thay đổi cách nó nén ảnh.

## Kiến trúc cần thay thế (không phải hotfix)

```text
YUV preview frames
  -> detector marker/quad + focus/blur/exposure checks
  -> stabilizer: cùng hình học N frame liên tiếp
  -> chỉ mở nút / tự chụp

JPEG gốc từ takePicture()
  -> detect lại bốn marker trên JPEG gốc (nguồn chân lý)
  -> reject nếu thiếu marker, blur, hoặc geometry xấu
  -> perspective warp theo 4 corners THẬT
  -> gửi original + corners, hoặc ảnh warp chuẩn, tới API chấm hiện hữu
```

Điểm không được giữ lại: `center crop 3:4 -> cornerRatios cố định -> JPEG 82`. Nó là nguyên nhân tạo ra đầu vào khác hoàn toàn với ảnh tĩnh.

## Thí nghiệm chẩn đoán xác nhận nguyên nhân (không cần sửa backend)

Trên cùng một tờ phiếu và cùng vị trí camera, lưu ba file riêng biệt:

1. `A_raw_live.jpg`: JPEG nguyên gốc từ `takePicture()`.
2. `B_current_live_crop.jpg`: bytes sau `_cropImageToOverlay()` hiện tại.
3. `C_static_camera.jpg`: ảnh từ camera thường/Gallery.

Chạy cả ba qua endpoint chấm hiện hữu và log: width/height, EXIF orientation, byte size, hash SHA-256, marker corners, SBD/mã đề/điểm, và ảnh overlay kết quả. Tiêu chí xác nhận:

- Nếu `A` gần `C` hơn rõ rệt, còn `B` lỗi/lệch, nguyên nhân fixed crop được chứng minh.
- Nếu `A` cũng lỗi trong khi `C` đúng, so lại orientation, camera lens/focus, exposure và marker detection **trên JPEG A**.
- Chỉ sau khi A/B/C đã tách bạch mới điều chỉnh threshold; không dùng threshold để che lỗi hệ tọa độ/crop.

## Log hiện có và giới hạn kiểm thử

- `tests/batch_test_report.json` (2026-09-10 21:20) ghi 8/8 request `SUCCESS`; các ảnh `1.jpg`–`1233332.jpg` trả mã đề `122`, riêng `9.jpg` và `test.jpg` có SBD không đọc được. Điều này cho thấy backend chưa phải nguyên nhân duy nhất và tập ảnh tĩnh cũng có mẫu chất lượng kém cần giữ làm regression set.
- `tests/ketqua` đang có cặp `_overlay.jpg`/`_result.jpg`; ảnh người dùng cung cấp cho thấy ảnh bị crop/xiên và red detections sai, phù hợp với giả thuyết input Live đã bị biến đổi trước khi chấm.
- `flutter test test/live_marker_detector_test.dart` chưa chạy được trên máy hiện tại vì lệnh `flutter`/`dart` không có trong PATH. Đây là giới hạn môi trường, không phải kết quả pass/fail.

## Kết luận hành động

Không hạ threshold của backend và không sửa upload tĩnh. Bước sửa đúng là tái kiến trúc Live Camera để **không crop theo overlay cố định**, xác minh marker trên JPEG gốc, và giữ mapping corners xuyên suốt từ capture tới perspective warp. Việc đó xử lý đồng thời false positive preview, manual capture sai, và sai khác với ảnh tĩnh.

### Trạng thái triển khai 2026-09-10

Đã thực hiện pha an toàn đầu tiên, chỉ trong Live Camera: xoá `_cropImageToOverlay` khỏi đường chụp và trả nguyên `rawBytes` từ `takePicture()`. Vì thế Live không còn tự xoay, center-crop 3:4, resize 1600 px hay JPEG encode quality 82 trước khi vào API. Không có file backend hay luồng Upload nào bị sửa bởi thay đổi này.

Pha tiếp theo chỉ được thực hiện sau khi kiểm thử A/B/C trên thiết bị cho thấy ảnh JPEG gốc vẫn cần nắn trước khi chấm. Khi đó, việc nắn phải dùng bốn marker xác minh lại trên chính JPEG gốc — không dùng toạ độ overlay/preview.
