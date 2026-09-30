# Live Camera: nghiên cứu APK và sửa kiểm tra JPEG sau chụp

Ngày: 2026-09-11. Phạm vi: Live Camera; không sửa backend, API Upload hoặc thuật toán chấm ô tô chung trong lần sửa này. Repository đã có nhiều thay đổi trước phiên làm việc; các thay đổi đó được giữ nguyên.

## 1. Phân biệt đúng lỗi

Ảnh người dùng gửi có preview xanh 4/4 góc và thông báo `FormatException ... marker_candidate_missing`. Thông báo này phát sinh khi `prepareLiveCapture` kiểm tra JPEG **sau** `takePicture`, không phải gate ổn định 500 ms. Preview hợp lệ không bảo đảm JPEG tiếp theo có cùng vị trí, độ nét, mức phơi sáng hoặc vùng nhìn.

Bằng chứng từ code và test:

- Bộ kiểm tra JPEG cũ tái sử dụng detector preview với bốn ROI cố định (`sqSizeRatio=0.25`; TL=(0,0), TR=(.75,0), BL=(0,.8), BR=(.75,.8)). Mỗi ROI chỉ chấp nhận đúng một ứng viên, kích thước tối thiểu phụ thuộc ROI (`roiWidth * .07`). Thay đổi vùng nhìn hoặc vị trí phiếu có thể làm góc rơi ngoài vùng hoặc bị loại vì kích thước.
- Fixture từ ảnh thật thu nhỏ 80%, dịch (35,40) pixel trên canvas 709×949 tái hiện việc detector cũ từ chối. Detector JPEG mới tìm đúng bốn tâm, sai số dưới giới hạn test 5 pixel.
- Test JPEG xoay ±6° và Gaussian blur radius=1 ban đầu còn thất bại: đường biên mờ bị làm tròn, bộ kiểm tra hình vuông loại bỏ. Bổ sung tìm lõi đậm ở nhiều mức tương phản giải quyết các test này mà không nới điều kiện phân biệt vuông/tròn.
- Đây là cơ chế lỗi được tái hiện trên fixture, **chưa phải chứng minh nguyên nhân chính xác của JPEG trong video mới**: hiện chỉ có ảnh chụp màn hình thông báo, chưa có file JPEG gốc của đúng lần lỗi đó. Blur mô phỏng không tương đương mọi dạng rung tay/rolling shutter thực tế.

## 2. Đã giải nén và đọc gì trong APK tham khảo?

Sáu APK gốc/base + ARM64 split được giải nén an toàn vào `scratch/apk_research_20260911/`; không cài hoặc chạy APK tham khảo. Công cụ `tools/diagnostics/inspect_reference_apks.py` dùng NDK `llvm-nm -D -C` đọc bảng symbol native. Danh sách đầy đủ file, SHA-256, models, thư viện và symbol nằm trong `scratch/apk_research_20260911/inventory.json`. Cạnh thư mục giải nén mỗi native library có file `*.symbols.txt`.

| Ứng dụng | Bằng chứng trực tiếp | Điều có thể kết luận |
|---|---|---|
| Azota Teacher | `libnative_opencv.so`; `Templates4::detect_frame`, `Templates4::correct_corner`, `Templates4::get_average_of_corners`, `Templates4/5::wrap_main_frame_base_on_input_corners` | Có code native xử lý khung/góc và nắn ảnh từ góc đầu vào |
| UnT Chấm Bài | `libffi_opencv_scanner.so`; `find4Points`, `_reDetectPoints`, `detectConnersAndCrop`, `sort4Contour`, `tranformPaperByRects` | Có xử lý contour, tìm lại góc và biến đổi hình học |
| UnT Dạy Học | Thư viện scanner tương tự, `findFrameQuadInRect`, `wrapRectInPaper`, `detectFrameR6R3` | Có nhiều hàm xử lý khung/template |

Các symbol OpenCV hiện diện gồm `cv::findContours`, `cv::approxPolyDP`, `cv::adaptiveThreshold`, `cv::threshold`, `cv::GaussianBlur`, `cv::createCLAHE`, `cv::warpPerspective`; UnT còn có `cv::getPerspectiveTransform`, morphology và rotate/resize. Symbol chỉ chứng minh khả năng được liên kết, **không chứng minh tất cả được gọi trong cùng một pipeline**.

Cả ba là Flutter AOT (`libapp.so`, `libflutter.so`). Các model `quiz_12*.tflite`, `test_paper*.tflite`, barcode và face models có trong assets; tên model không đủ chứng minh vai trò, độ chính xác hoặc cách dùng. Không khẳng định đối thủ dùng optical flow, EMA, best-frame buffer hay thời gian debounce cụ thể. `get_average_of_corners` cũng không đủ để kết luận có smoothing theo thời gian.

Không sao chép thư viện, model hoặc mã độc quyền từ APK vào GradeFlow. Áp dụng nguyên lý CV tiêu chuẩn bằng triển khai Dart độc lập, chạy isolate: local threshold → thành phần liên thông → kiểm tra tứ giác → chọn bộ bốn góc → warp một lần. Không thêm native dependency vào bản sửa này; không tuyên bố đây là thuật toán nguyên bản của Azota/UnT.

## 3. Kiến trúc đã sửa

1. **Preview** giữ detector nhẹ, throttle 100 ms, một job tại một thời điểm; state machine 500 ms/EMA và dung sai rung đã có được giữ nguyên.
2. **Chụp tay** không phải chờ ready, cooldown tự chụp hoặc animation. Thời gian SDK stop stream/takePicture và xử lý JPEG là độ trễ riêng, không cam kết hoàn tất trong 500 ms.
3. **JPEG** đọc ảnh, chuẩn hóa EXIF một lần, tạo mẫu phân tích tối đa rộng 1000 pixel. `live_still_detector.dart` tìm ứng viên trên toàn ảnh với integral-image local threshold, hai bán kính 2.5%/5% chiều rộng và ba mức tương phản (12 tuyệt đối, 30%/50% local mean).
4. **Validation hình học**: component không chạm mép, kích thước/solidity/aspect hợp lý, lõi được tô kín, hull gần tứ giác. Gộp ứng viên trùng qua các mức threshold. Chọn quartet TL/TR/BR/BL có kích thước tương đồng, cạnh đối và tỉ lệ phiếu phù hợp; loại kết quả mơ hồ. Không lấy lại bốn tâm preview cũ khi JPEG thiếu góc.
5. **Tọa độ và ảnh đi cùng nhau**: trả tâm marker theo pixel của JPEG chuẩn hóa, không resize tiếp trong Live transport. Backend sẵn có nhận `corners` và `fast=1`, nắn một lần bằng cơ chế hiện hữu. Vì vậy **không cần sửa backend cho lần khắc phục này**; request Live vẫn sử dụng backend để chấm.
6. **Lỗi có kiểm soát**: JPEG không đạt thì trở lại camera, thông báo tiếng Việt trong màn hình thay vì snackbar chứa `FormatException`. Tự thử lại cách tối thiểu 750 ms sau thất bại; sau ba lần thất bại liên tiếp thì tạm dừng tự chụp, có nút “Thử tự chụp lại”. Chụp tay luôn dùng được; một lần chụp tay thất bại không tự kích hoạt thêm lần chụp ngầm. Đây là xử lý UX cho ảnh thật sự không đạt, không thay thế sửa detector.

Giới hạn hiện tại: phiếu theo hướng dọc và trải qua bốn phần tư ảnh; không phải document scanner cho mọi góc xoay/phiếu lệch hoàn toàn khỏi tâm. Bốn marker màu đen không có mã định danh nên hình dạng đơn thuần không thể bảo đảm không bao giờ nhận nhầm một bố cục giả. Không bỏ validation để ép chấm ảnh mờ/mất góc. Chưa thay đổi thuật toán chống méo do giấy cong hoặc rolling shutter.

## 4. Kiểm thử đã chạy

`flutter test` hai file `test/live_marker_detector_test.dart`, `test/live_capture_test.dart` với cả `LIVE_SCREENSHOT` và `LIVE_OVERLAY`: **30/30 test pass**.

- 500 ms ở nhiều cadence; rung 2% không reset; mất quan sát ngắn giữ progress nhưng không auto-capture trên frame thiếu góc; di chuyển/gap lớn reset; manual độc lập gate.
- YUV rotation/stride/padding, ảnh tối, marker xám, nhiễu, marker sai kích thước.
- JPEG EXIF chạy trong isolate; multipart giữ nguyên bytes và tọa độ.
- Ảnh overlay thật: đúng marker ngoài, không dùng quad méo cũ.
- Thu nhỏ 80% dịch (35,40); thu nhỏ 90% dịch (55,50) và blur 1; xoay +6°/-6° với blur 1, JPEG quality 90. Tọa độ đo nằm trong 5 pixel so với biến đổi kỳ vọng.
- Xóa lần lượt từng marker ngoài trên ảnh thật: cả bốn biến thể đều bị từ chối, không lấy ô vuông bên trong thay thế.
- 12 tổ hợp bán kính ô tròn 5/7/10/14 và blur 0/1/2 đều bị từ chối. Bốn hình vuông trên nền trống không được gửi chấm; quartet mơ hồ cũng bị từ chối.
- Retry có giới hạn, manual không bị cooldown chặn.

Analyzer trên 6 file production/test Live liên quan: **No issues found**.

Các ảnh nguồn ở `tests/ketqua` là ảnh đã annotate, không phải ground truth đáp án. Kết quả trên kiểm chứng geometry/logic/transport, **không chứng minh độ chính xác chấm điểm hoặc hết lỗi trên mọi camera**.

Lệnh chạy lại từ `gradeflow_app`:

```powershell
& 'C:\flutter\bin\flutter.bat' test test/live_marker_detector_test.dart test/live_capture_test.dart --reporter expanded '--dart-define=LIVE_SCREENSHOT=C:/Users/Thang/AppData/Local/Temp/codex-clipboard-401879c6-3ede-4689-88a2-8a43a08f0980.png' '--dart-define=LIVE_OVERLAY=D:/chamtrac nghien v2/tests/ketqua/20260910_135818_scan_sbd__9_33__md_____overlay.jpg'
```

Nếu không truyền hai define, test fixture thật bị skip; không gọi đó là 30 test ảnh đầy đủ đã chạy. File screenshot trong Temp có thể bị hệ thống xóa.

## 5. Log điện thoại và nghiệm thu thực tế

Điện thoại `2412DPC0AG` đã được ADB nhìn thấy ở `192.168.1.5:41547`. Người dùng đã đồng ý cài bản mới và đọc log. Tình trạng build/cài/test cuối cùng được cập nhật bên dưới sau khi thực hiện.

`tools/diagnostics/capture_live_android_log.py --serial 192.168.1.5:41547` chỉ đọc log của PID GradeFlow, chỉ giữ dòng `[LiveCamera ...]`, không xóa logcat hoặc thu log ứng dụng khác. Output tại `tests/ketqua/live_v3_device/*.json`.

- `[LiveCamera v2]`: rotation, stride, preview match/reject reason.
- `[LiveCamera timing]`: thời gian lấy JPEG và thời gian kiểm tra ảnh sau chụp tách biệt.
- `[LiveCamera capture rejected]`: manual/auto, elapsedMs, reason, số ứng viên khi lỗi tìm góc.
- `[LiveCamera v2] capture=... corners=...`: JPEG được chấp nhận và bốn tọa độ tương ứng.

Nghiệm thu: mở Live, đưa phiếu vào khung; rung nhẹ 10 lần tự chụp, thử 10 lần chụp tay không đợi ready; thay đổi ánh sáng/khoảng cách; che từng góc; quay sang nền trống; xác nhận không chấm ảnh thiếu góc và không có vòng lặp snackbar. Ghi tỉ lệ nhận được phiếu, tỉ lệ từ chối đúng/sai và shutterMs/postCaptureMs. Việc test này cần phiếu thật trước camera; chỉ cài APK thành công chưa phải nghiệm thu camera.

### Build và cài đặt đã xác nhận

- `flutter build apk --release --split-per-abi --no-pub`: thành công, Gradle 118.9 giây.
- APK ARM64: `gradeflow_app/build/app/outputs/flutter-apk/app-arm64-v8a-release.apk`, 44.4 MB.
- SHA-256: `34d0869b76c19a362f248c95af162c3e31ac9a8e3434bfe230d5823ba94390b1`.
- `adb -s 192.168.1.5:41547 install -r <APK ARM64>`: **Success**; cập nhật tại chỗ, không uninstall, không clear data.
- Người dùng được yêu cầu mở lại Live Camera và thử rung/chụp tay. Chưa có kết luận thực nghiệm camera tại thời điểm ghi mục này.

### Log thực tế sau cài — 21:20–21:23

Đã đọc `tests/ketqua/live_v3_device/20260911_212322_617709.json`: PID 18655, 28 dòng LiveCamera. Package sau cài có versionCode=4006, lastUpdateTime=2026-09-11 21:19:59.

| Thời điểm | Chế độ | Lấy JPEG (ms) | Xử lý sau chụp (ms) | Kết quả frontend |
|---|---|---:|---:|---|
| 21:20:46 | Auto | 411 | 2450 | Chấp nhận đủ bốn góc |
| 21:21:05 | Auto | 259 | 2262 | Chấp nhận đủ bốn góc |
| 21:22:26 | Manual | 311 | 4335 | Chấp nhận đủ bốn góc |
| 21:22:43 | Auto | 276 | 2006 | Chấp nhận đủ bốn góc |
| 21:22:58 | Auto | 311 | 2130 | Chấp nhận đủ bốn góc |

Trong cửa sổ log này không có dòng `capture rejected`. Preview vẫn có `marker_candidate_missing` xen kẽ khi chưa khớp khung; đây không phải exception sau chụp. Log không ghi mức rung tay vật lý, không chứng minh 20 lần nghiệm thu đã hoàn thành và không xác nhận điểm chấm backend đúng.

**Sai khác preview/JPEG đã có bằng chứng trực tiếp trên máy**: stream 1920×1080, rotation=90; JPEG chuẩn hóa 1080×1920. Preview dùng crop 3:4, nhưng JPEG giữ toàn khung 9:16. Ví dụ JPEG chấp nhận đầu tiên có TL=(69.12,301.28), TR=(970.92,314.78). ROI trên của bộ kiểm tra JPEG cũ cao bằng 25% chiều rộng, tức 270 pixel trên ảnh 1080 pixel, nên cả hai góc này nằm ngoài ROI cũ. Trong bản phân tích 1000 pixel, cùng sự loại nhầm xảy ra sau scale. Đây là bằng chứng cụ thể cho sai lệch vùng tìm góc, không chỉ giả thuyết threshold.

**Hạn chế UX còn đo được**: xử lý JPEG sau lấy ảnh mất 2.006–4.335 giây trên thiết bị này. Chụp tay lấy ảnh trong 311 ms, không chờ 3 giây ổn định; tuy nhiên tổng thời gian thấy kết quả chưa dưới 0.5 giây. Cần phân tích riêng thời gian decode/resize/threshold/components/encode nếu tối ưu tiếp độ trễ hậu xử lý. Bản sửa này ưu tiên đúng góc và không chấm nhầm, không che giấu thời gian xử lý bằng số liệu gate.
