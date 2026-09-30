# Live Camera — sửa ô trống Phần II/III bị nhận đã tô

## Kết luận có bằng chứng

Người dùng xác nhận lỗi ở Phần II và III. Đã đối chiếu 5 ảnh kết quả ngày 11/09 trong `tests/ketqua` với JPEG gốc tương ứng ở `media/submissions/2026/09/live*.jpg`, ghép theo kích thước byte với log capture và sử dụng đúng bốn góc đã gửi.

Lỗi Phần II tái hiện được offline trên ảnh gốc: cả 5 ảnh đều bị đọc nhầm câu 1d=Đúng; hai ảnh còn bị đọc nhầm câu 2d=Đúng. Tổng 7 lựa chọn sai trong nhóm ảnh này.

Ví dụ `live_zLyBU2p.jpg`, tâm P2 1d=(81,1289):

- Độ sáng trung bình lõi ô trên ảnh chưa xử lý khoảng 134.2; nền giấy lân cận khoảng 135.0 — gần như không có mực tô.
- Pipeline cũ lại trả fill score 0.379. Câu 2d có score 0.348.
- `preprocess()` gọi `erase_printed_text()` **trước** ước lượng nền/CLAHE. Vùng chữ và xung quanh bị làm trắng nhân tạo nhưng vùng bảo vệ ô giữ nền giấy xám. Việc đo tương phản sau đó sinh ra “ô tô” giả. Các ảnh `part2_raw.png` và `part2_processed.png` minh họa trực tiếp.

Phần III có thêm lỗi logic vẽ: `else` trong `draw_results_part3` gắn với vòng `for` OCR, nên fallback có thể chạy ngay cả khi đã có `picked`; fallback khoanh mọi ratio vượt ngưỡng, không chỉ chữ số được chọn. Test renderer đã kiểm chứng bản Live mới không khoanh chữ số không được chọn, dù cố tình cấp ratio cao cho chữ số đó. Năm JPEG Live mới nhất đang có P3 trống; chưa dùng chúng để khẳng định đã tái hiện mọi trường hợp P3 trong toàn bộ ảnh lịch sử.

## Phạm vi sửa — có nhánh backend riêng cho Live

Không thể sửa kết quả tính điểm chỉ bằng đổi màu vòng vẽ trên app. Đã thêm module `grading/engine/live_bubble_reader.py` và các điểm gọi có điều kiện:

- App `live_grading_service.dart` gửi `capture_pipeline=live_capture_v3`.
- API chuyển cờ riêng qua `grade_image(... live_bubble_mode=False)` tới engine.
- Chỉ khi opt-in chính xác mới dùng bộ đọc và renderer P2/P3 mới. Không dùng `fast` làm cờ nguồn vì `ApiService.gradeImage` của Upload cũng dùng `fast=1`.
- Không đổi `ApiService`, các hàm đọc/vẽ legacy, thông số template, thuật toán Part I, gate 500 ms hoặc detector marker.
- Không dùng monkeypatch/global switch trong server. Bộ đọc mới nhận template/ảnh/thông số qua đối số.
- Backend cần chạy code mới **và** app cần APK mới để bật nhánh này. Chỉ cập nhật một phía không đủ. Các request không có cờ tiếp tục chạy như trước.

## Thuật toán Live mới

Đo trên ảnh xám sau warp nhưng **trước xóa chữ và tăng tương phản**:

1. Lõi đo bằng nửa bán kính ô để tránh viền in.
2. Nền tham chiếu lấy percentile 75 của vòng giấy thật bên ngoài ô.
3. Cần đồng thời đủ tương phản lõi/nền (>=0.16), diện tích mực trong lõi (>=60%), và ít nhất 3/4 phần tư có bằng chứng mực.
4. Ô rất ít tương phản/coverage được coi là trống; trường hợp ở giữa hoặc ROI không hợp lệ là không chắc chắn, không tự cứu bằng CNN/argmax.
5. P2 chỉ chọn khi có bằng chứng rõ; tô cả hai trả X. P3 có nhiều chữ số cùng cột hoặc bằng chứng không chắc chắn thì không ghép số đoán, phát cảnh báo cần kiểm tra.
6. Renderer Live P3 chỉ vẽ `picked`, không chạy fallback khoanh toàn bộ ratio.

Điều này không phải tăng ngưỡng chung để che lỗi: nguồn đo đã được tách khỏi nền trắng nhân tạo. Không sửa dữ liệu JPEG gốc, không sửa/xóa các bài đã lưu hoặc điểm cũ.

## Kiểm chứng

- **9/9 test Python pass** (`tests/test_live_bubble_reader.py`), gồm test tích hợp pipeline và nhiều subcase.
- Cả 5 ảnh thật có P2/P3 để trống đều không còn sinh đáp án P2/P3 ở bộ đọc mới.
- Positive controls: thêm dấu tô có kiểm soát lên cả 5 nền ảnh gốc; đọc được P2 Đúng/Sai và P3 `-1.234`. Đây là dấu tô tổng hợp, chưa phải tập đáp án viết tay thật có nhãn đầy đủ.
- Kiểm tra giấy sáng/tối, viền in lệch ±3 pixel, hạt nhiễu, tẩy mờ; kiểm tra dấu tô rõ lệch ±2 pixel và độ tối tương đối 30%.
- Kiểm tra nhiều ô tô trong cùng cột số không bị ghép thành số khác.
- Test renderer không khoanh ô có ratio cao nhưng không được chọn.
- Test tích hợp: `fast_mode=True` mặc định vẫn dùng bộ đọc Upload cũ; opt-in Live mới gọi module mới; Part I trước/sau giống nhau trên fixture này.
- **30/30 test Flutter pass**, có cả hai fixture ảnh thật; multipart chứa cờ Live riêng.
- Flutter analyzer hai file liên quan: **No issues found**.
- `python manage.py check`: **System check identified no issues**.

Lệnh chạy lại từ thư mục gốc:

```powershell
python tools/diagnostics/audit_live_bubble_false_positives.py
python -m unittest discover -s tests -p test_live_bubble_reader.py -v
python manage.py check
```

Test tích hợp gặp ResourceWarning đóng file PIL từ helper legacy; không sửa helper Upload trong nhiệm vụ này. `git diff --check` còn ghi nhận hai dòng whitespace trong các sửa đổi có sẵn của `hi.py`, không thuộc nhánh Live vừa thêm.

## Artifact để đối chiếu

`tests/ketqua/live_bubble_audit_20260912/summary.json` có kết quả cũ/mới, bằng chứng từng ô và bốn góc của từng JPEG. Mỗi thư mục ảnh có:

- `raw_warp.jpg`: ảnh gốc được warp, chưa vẽ chấm.
- `part2_raw.png` / `part2_processed.png`: trước/sau tiền xử lý legacy.
- `part2_before.png` / `part2_after.png`: các ô được nhận đã tô trước/sau; không phải điểm chấm của đề thi.
- `audit.json`: số đo và đáp án tương ứng.

## Hạn chế và nghiệm thu

Chưa chứng minh hết false positive trên mọi ánh sáng, giấy cong, lệch grid hoặc bút chì tẩy. Dấu tô quá nhạt có thể được yêu cầu kiểm tra thay vì đoán. Cần thêm ảnh có nhãn thật ở P2/P3 để đánh giá cả false positive lẫn false negative.

Ở lần kiểm tra ADB trong phiên này chưa có điện thoại kết nối. Chưa cài bản mới/chưa có log test vật lý cho thay đổi P2/P3 này. Server địa phương đang chạy `manage.py runserver` có autoreload; không khởi động lại hoặc thay cấu hình server ngoài phạm vi.

Nghiệm thu trên điện thoại: quét phiếu P2/P3 trống; tô một ô Đúng/Sai; tô một số âm/thập phân; tô hai số trong cùng cột; kiểm tra ảnh kết quả chỉ khoanh các ô có mực, và debug log có `[LIVE OMR] P2/P3 raw-paper evidence`. Kiểm tra thêm Upload trên cùng ảnh để xác nhận vẫn dùng nhánh cũ.

## Bản build bàn giao

Build `flutter build apk --release --split-per-abi --no-pub` thành công (Gradle 165.1 giây). APK điện thoại ARM64: `gradeflow_app/build/app/outputs/flutter-apk/app-arm64-v8a-release.apk`, khoảng 44.4 MB. Không dùng file `app-release.apk` cũ.

Server địa phương trả `ok: true` tại `http://127.0.0.1:8000/api/health` sau khi sửa. Đây là kiểm tra khả dụng, không thay thế thử một lần chấm Live từ APK mới. Chưa cài APK P2/P3 này lên điện thoại do chưa có ADB kết nối.
