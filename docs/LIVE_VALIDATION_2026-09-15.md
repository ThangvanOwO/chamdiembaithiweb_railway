# Live: mã đề khớp chính xác, tô kép và overlay cảnh báo

## Phạm vi

Chỉ API chấm `live_capture_v3` bật `live_validation=True`. Không đổi Flutter,
APK, template, weights/CNN, ngưỡng đo mực, bộ lọc Gaussian, schema DB hoặc luồng
upload/import. Các tham số mới ở grader/engine/reader đều mặc định tắt.

Source đã sửa và kiểm thử offline. Chưa chủ động restart/deploy backend hay cài
APK trên điện thoại. Backend phải nạp code mới để ứng dụng sử dụng thay đổi.

## Mã đề: không đoán, không fallback

- Đề chỉ khai báo `001`: nhận `002` trả `success:false` và lỗi mã đề chưa khai báo.
- Khai báo cả `001`, `002`: chọn bảng đáp án khớp chính xác, giữ số 0 đầu.
- Mã trống, chứa `?`, tô nhiều số hoặc không đọc rõ: yêu cầu quét lại.
- Chưa chọn đề/đề chưa có variant: chặn trước khi gọi engine.
- Kiểm tra ngay trong callback trước tính điểm/vẽ kết quả; API kiểm tra lại trước
  lưu Submission. Nếu phải chạy lần hai do khác số câu, lượt hai cũng xác nhận
  đúng mã đã chọn, không được tự chuyển sang mã khác.
- `LIVE_SINGLE_PASS_GRADING=0` chỉ tắt tối ưu tốc độ; **không tắt kiểm tra mã đề**.
  Đây là thay đổi có chủ đích so với phiên bản ngày 14/09.

Ảnh debug tiền xử lý có thể được tạo trước khi phát hiện lỗi mã đề. Không tạo
ảnh chấm điểm/overlay đúng-sai và không lưu bài chấm thành công cho mã không hợp lệ.

## Tô kép và quy ước màu

- Phần I: >=2 ô được xác nhận tô trong cùng câu → `X`, 0 điểm câu đó, vòng vàng.
- Phần II: cả Đúng/Sai trong **cùng ý a/b/c/d** → `X`, ý đó không được điểm.
  Các ý hợp lệ còn lại vẫn chấm theo cấu hình. Tô một ô ở mỗi ý là bình thường.
- Phần III: nhiều chữ số trong **cùng cột**, nhiều dấu phẩy, hoặc bằng chứng chưa
  rõ → không ghép một số đoán mò; câu cần kiểm tra, không được điểm. Nhiều chữ số
  ở các cột khác nhau (ví dụ 7420) hoàn toàn hợp lệ.
- Xanh: ô học sinh tô được chấm đúng. Đỏ: ô học sinh tô được chấm sai.
- Vàng: tô kép hoặc bằng chứng cần đối chiếu. Ô trống không vẽ đáp án chuẩn màu
  xanh lên đó nữa, tránh hiểu nhầm rằng app nhận ô trống là đã tô.

Ảnh kết quả và inverse overlay dùng cùng mask. P1/P2 vẽ tại tọa độ đã căn lưới;
P3 vẽ cả cảnh báo khi câu bị bỏ vì không chắc chắn, thay vì im lặng không vẽ gì.

## Nguyên nhân và sửa nhận diện

1. P1 cũ đọc ảnh tăng tương phản và có lựa chọn tương đối giữa các ô. Live mới đo
   mực trên ảnh giấy gốc đã nắn, căn theo đường tròn in; dùng tiêu chí contrast,
   coverage, số góc tối đang có ở reader Live. Không cứu ô trống bằng argmax/CNN.
2. P2 cũ đo ở tọa độ cố định. Giờ căn lưới từ các đường tròn in của cặp câu cạnh
   nhau, fallback sang từng câu khi cần. Không tăng dung sai/ngưỡng tô.
3. P3 lấy dịch chuyển trung vị của 10 hàng để suy ra dấu ở phía trên. Phiếu co
   giãn theo chiều dọc khiến điểm đo dấu trừ/phẩy chạm viền ô, dù 7420 đã đọc đúng.
   Giờ dùng các hàng chữ số gần phía trên để suy ra vị trí dấu, có kiểm tra tỷ lệ
   bước hàng; không coi dấu nghi ngờ là trống một cách tùy tiện.

## Đối chiếu bốn ảnh người dùng

Tìm được ảnh gốc cùng các phiếu trong `media/submissions/2026/09`:

| Phiếu | Kết quả đối chiếu |
| --- | --- |
| Phiếu trắng (`live_t0EDDxm.jpg`) | P1/P2/P3 đều trống ở nhánh mới; mã `???` bị API từ chối |
| Phiếu 122 (`9.jpg`, ảnh số 2) | Đọc lại đủ 16 ý P2 câu 1–4; câu 5–8 và P3 vẫn trống |
| Phiếu 676 (`live_H6cQfZ2.jpg`) | P1 câu 4 đọc B; P2 từ 16 lên 32 ý; P3 câu 6 từ rỗng thành 7420 |
| Phiếu 676 (`live_XbTsC8z.jpg`) | P2 từ 27 lên 32 ý; P3 câu 6 vẫn 7420 |
| Capture bổ sung 676 (`live_M2fMCpf.jpg`) | Q6 ra 7420 nhưng P2 vẫn còn ý chưa đọc chắc; không tuyên bố sửa mọi ảnh |
| Mẫu ổn định 001 (`exam_import_v1.jpg`, `live_iQ7kqOT.jpg`) | Giữ SBD 011232, mã 001, các số P3; P1 câu 10 tô A/C là X và vẽ vàng |

Người dùng xác nhận 032215 / 676 / 7420. Không suy diễn đáp án từ chữ viết tay
hoặc vòng màu đã vẽ. Ảnh gốc được warp lại trong kiểm thử; với ảnh không có log
corners, dùng detector backend, không khẳng định tái hiện y hệt buffer mobile.

Các ảnh trong thư mục audit dùng bảng đáp án rỗng **chỉ để kiểm tra overlay**;
điểm 0 và các vòng đỏ ở đó không phải kết quả chấm bài thật của giáo viên.

## Kiểm thử và bằng chứng

- `test_live_latency.py`: 16 test; mã không đăng ký, thiếu variant, kill-switch,
  cấu hình khác, Upload, request isolation, chặn lưu bài dù request yêu cầu save.
- `test_live_validation.py`: 13 test; tô kép độ đậm khác nhau, giấy trắng/ánh sáng,
  màu vàng, không vẽ xanh đáp án chuẩn ở ô trống, điểm của đáp án invalid, ảnh gốc
  676/122 và mẫu ổn định 001. Các test ảnh cần raw warps do audit tạo.
- `test_answer_image_import.py`: 12/12 pass.
- `verify_validation_isolation.py`: nạp cả engine và reader từ checkpoint trước
  sửa; dữ liệu và SHA-256 mọi ảnh đầu ra của Upload/import mặc định khớp hoàn toàn.
  Ca mã 001 không khai báo bị chặn trước hàm chấm điểm và không sinh result/overlay.
- `manage.py check`: không lỗi.

Bằng chứng:

- `scratch/live_validation_20260915_release/report.json` (7 ảnh gốc, mỗi ảnh 2 chế độ).
- `scratch/live_validation_20260915_122/report.json` (ảnh 122, 2 chế độ).
- `scratch/live_validation_isolation_20260915/report.json` (kiểm tra cách ly).
- `scratch/live_validation_accuracy_20260915/report.json` (smoke suite cũ).
- Ví dụ vòng vàng: `scratch/live_validation_20260915_release/exam_import_v1_1/input_result.jpg`.

Không có bộ nhãn đầy đủ cho mọi câu/mọi điều kiện chụp; không cam kết lỗi bằng 0.
Nhận diện số Phần III có kiểm tra cấu trúc: không tự rút ngắn số khi thiếu chữ số ở
giữa, không tự bỏ dấu phẩy cuối, và không ghép các bằng chứng rời rạc thành đáp án.
Capture bổ sung còn vùng chưa đọc chắc phải giữ cảnh báo, không hạ threshold để
ép ra đáp án. Năm ảnh phiếu trắng lịch sử trước đây bị thiếu vẫn không được thay
bằng ảnh khác để giả vờ chạy đủ bộ test cũ.

## Đường lui riêng cho đợt này

Checkpoint `scratch/restore_points/before_live_validation_20260915/` được tạo trước
sửa; không ghi đè checkpoint tối ưu tốc độ trước đó. Backup gồm source và test
đã tồn tại; manifest SHA-256 trước/sau ngăn ghi đè sửa đổi mới của người dùng.

Chỉ kiểm tra, không sửa file:

```powershell
python tools/diagnostics/checkpoint_live_validation.py verify
```

Nếu người dùng yêu cầu khôi phục: dừng backend liên quan, chạy lệnh dưới rồi
khởi động lại backend. Việc này cũng trả về chính sách mã đề cũ, nên cần hiểu rõ
rủi ro fallback của bản cũ.

```powershell
python tools/diagnostics/checkpoint_live_validation.py restore
```

Không git reset, không uninstall APK, không xóa DB. File thay thế được giữ trong
`replaced/`. Công cụ từ chối nếu backup hỏng hoặc source có sửa đổi sau đợt này;
khi đó cần đối chiếu diff, không được ép ghi đè. Tài liệu/công cụ/test mới và log
được giữ lại phục vụ điều tra; không tự chạy test tính năng mới sau rollback.
