# Live latency: bản tối ưu an toàn và đường khôi phục

> Cập nhật: nếu đang dùng bản [15/09](LIVE_VALIDATION_2026-09-15.md), tắt
> `LIVE_SINGLE_PASS_GRADING` chỉ tắt tối ưu tốc độ, không bỏ kiểm tra mã đề bắt buộc.
> Hãy dùng checkpoint của bản 15/09 để khôi phục đợt sửa mới nhất trước.

## Bàn giao

Chỉ bật tối ưu **chọn bảng đáp án sau khi nhận diện, trước khi tính điểm/vẽ ảnh**.
Không thay threshold, marker, warp, tiền xử lý hay thuật toán đọc SBD/mã đề/P1/P2/P3.
Không sửa Flutter, APK, DB, mẫu phiếu, luồng web upload hoặc import ảnh/Excel.

`LIVE_SINGLE_PASS_GRADING=1` là mặc định trong code mới. API chỉ áp dụng cho
`capture_pipeline=live_capture_v3`; `fast=1` không đủ để kích hoạt.

Đã sửa source backend, chưa thực hiện triển khai hoặc chủ động restart dịch vụ
đang phục vụ điện thoại. Backend cần nạp code/settings mới; không cần APK mới.
Không có kết quả benchmark trực tiếp trên điện thoại trong đợt này.

## Cơ chế

Trước đây, API đọc/chấm/vẽ theo mã đề đầu tiên; nếu phát hiện mã đề khác thì gọi
lại toàn pipeline. Nay callback chọn đúng bảng đáp án từ các variant đã được
lọc theo giáo viên, sau khi tất cả bước đọc/validation hoàn tất. Lượt đó tính
điểm và vẽ đúng kết quả ngay. API không chạy lại nếu đã dùng đúng bảng đáp án.

- Selector tạo mới trong từng request, không cache ảnh/ô/callback toàn cục.
- Mã đề giữ dạng chuỗi, bảo toàn số 0 đầu; mã chưa nhận ra vẫn theo fallback cũ.
- So sánh cấu hình giới hạn số câu của 3 phần. Nếu khác, không chọn sớm;
  API giữ nguyên cách chạy lại với cấu hình đúng. Không ép tái sử dụng dữ liệu.
- Điểm có trọng số, ảnh kết quả và overlay đều theo bảng đáp án cuối.
- Những lượt vốn đã đúng mã đề đầu tiên không được lợi từ việc bỏ lần đọc lặp.

## Đo và đối chứng

Script `tools/diagnostics/verify_live_latency.py` nạp engine trước chỉnh sửa từ
checkpoint, giữ nguyên đường dẫn model/calibration, chạy tuần tự với input riêng.
Ảnh kết quả/debug và bản copy tự động đều được chuyển vào thư mục thí nghiệm;
không dùng ảnh đã đánh dấu làm input, không ghi DB.

Fixture gốc: `tests/fixtures/exam_import_v1.jpg` cùng corners trong JSON cạnh ảnh.
Giá trị xác nhận: SBD `011232`, mã đề `001`, câu 5 P3 `22`.
Bảng đáp án đối chứng là bảng tổng hợp cho thí nghiệm, không phải đáp án giáo viên.

Kết quả tại `scratch/live_latency_verify_20260914_final/report.json`:

| Đối chứng | Kết quả |
| --- | --- |
| Code mới tắt tối ưu so với engine trước chỉnh sửa | Toàn bộ dữ liệu và SHA-256 các ảnh khớp |
| Chọn mã đề trong 1 lượt so với lượt 2 dùng đúng đáp án của bản cũ | Dữ liệu/chi tiết/confidence/cảnh báo/điểm khớp |
| Ảnh result, overlay, name, gray, thresh, cleaned, calibration | SHA-256 khớp |
| Điểm có trọng số với 3 cấu hình chấm | Khớp |
| Upload bỏ qua tùy chọn Live | Dữ liệu và ảnh khớp bản cũ |
| Một phép đo trường hợp cần đổi mã đề | Cũ 2 lượt **8,37 s**; mới 1 lượt **4,22 s** |

Đây là thời gian offline trên máy hiện tại, không phải cam kết độ trễ điện thoại,
không bao gồm mạng/chụp ảnh. Con số 3,5 s trên UI cũ chỉ lấy thời gian lần xử lý
trả về; có thể đã không tính lần đầu khi pipeline chạy 2 lần. Do vậy không được
hiểu bản này đã biến 3,5 s thành dưới 1 s.

## Bộ lọc nhanh: đã thử và LOẠI KHỎI APP

Thử giảm kích thước ảnh nền 4 lần trước Gaussian sigma=120 rồi phóng lại.
Các bước khử nhiễu, sigma=30 và ngưỡng ô được giữ nguyên trong thí nghiệm.

Trên 6 tình huống (1 ảnh gốc + 5 biến đổi kiểm soát: tối, sáng, mờ nhẹ, bóng,
giảm tương phản), 5 tình huống giữ đáp án; **mờ nhẹ đổi P1 câu 1 từ A thành B**.
Thời gian giảm mạnh nhưng không đạt yêu cầu bảo toàn nhận diện. Một số bằng chứng
confidence/offset cũng thay đổi dù đáp án cuối chưa đổi.

Vì vậy đã gỡ toàn bộ hook/config/import của bộ lọc thử khỏi production. Code thử
chỉ còn ở `tools/diagnostics/experimental_live_background.py`, được gọi qua
monkey-patch trong tiến trình kiểm thử độc lập. Không có công tắc backend để bật
nhầm bộ lọc này. Không chấp nhận một sai khác đáp án chỉ để có số benchmark đẹp.

## Kiểm thử đã chạy

- `python -m unittest discover -s tests -p 'test_live_latency*.py'`: **18/18**.
  Gồm route 1/2 lượt, kill switch, Upload, khác cấu hình, mã không rõ, số 0 đầu,
  không chia sẻ state; AST chứng minh chỉ thêm hook sau nhận diện; khôi phục
  trong sandbox, bảo toàn bản cũ và từ chối ghi đè sửa đổi về sau.
- `python -m unittest discover -s tests -p test_answer_image_import.py`: **12/12**.
- `python -m unittest discover -s tests -p test_live_profiler.py`: **3/3**.
- `python -m unittest discover -s tests -p test_live_identifiers.py`: **6/7**.
  Ca còn lại dừng vì thiếu 5 JPEG gốc (fixtures trả 0 thay vì 5), không phải assertion
  sai nhận diện. Không sửa/bỏ/skip test để che thiếu dữ liệu. Ba raw-warp gốc,
  kiểm tra mã/SBD/Q5 và các kiểm soát còn có dữ liệu vẫn chạy được.
- Bộ `tests/benchmarks/test_accuracy.py` chạy qua wrapper cô lập trên 8 ảnh cũ:
  **8/8 không lỗi thực thi**, vẫn có ảnh bị cảnh báo/REJECT_SCAN như cơ chế hiện có.
  Bộ này không có nhãn đầy đủ, không được diễn giải thành chính xác 100%.
- `python manage.py check`: không có lỗi.

Các bài AST và script so sánh bản trước yêu cầu giữ checkpoint bên dưới. Chưa đủ
ảnh độc lập/phiếu trắng để tuyên bố không thể có sai sót trên mọi đầu vào.

## Khôi phục nhanh: không cần sửa source

Đặt biến môi trường **của tiến trình backend**, rồi restart backend:

```powershell
$env:LIVE_SINGLE_PASS_GRADING = '0'
```

Ví dụ khi chạy development thủ công: đặt biến trên trong chính terminal sẽ chạy
`python manage.py runserver ...`. Nếu dùng dịch vụ, đặt ở cấu hình môi trường của
dịch vụ. Không chỉ tạo file `.env` rồi giả định ứng dụng đã nạp nó.

`0` trả API Live về cách chấm cũ. Muốn bật lại dùng `1` và restart. Không xóa app,
không mất dữ liệu. Không cần thay đổi chế độ Live speed ở Flutter.

## Khôi phục source đúng bản trước đợt này

Checkpoint: `scratch/restore_points/before_live_latency_20260914/`.
Được tạo trước sửa source, gồm cả những sửa đổi chưa commit của người dùng.
Manifest ghi SHA-256 trước/sau cho phạm vi file liên quan; không dùng git reset.

Kiểm tra an toàn, KHÔNG khôi phục:

```powershell
python tools/diagnostics/checkpoint_live_latency.py verify
```

Chỉ khi người dùng yêu cầu khôi phục, dừng backend liên quan rồi chạy:

```powershell
python tools/diagnostics/checkpoint_live_latency.py restore
```

Sau đó khởi động lại backend. Công cụ kiểm tra tất cả hash trước khi thay file,
từ chối nếu có sửa đổi về sau hoặc backup hỏng. File mới/file bị thay được giữ
trong `replaced/`, không xóa vĩnh viễn. Đây là rollback source có phạm vi, không
phải backup toàn DB/APK. Tài liệu, log và công cụ thí nghiệm vẫn được giữ lại.

## Bước nghiệm thu trên điện thoại

1. Đề có ít nhất 2 mã, quét mã không đứng đầu danh sách: so trước/sau cả thời gian,
   điểm, đáp án, ảnh đúng/sai và dữ liệu lưu bài.
2. Quét mã đầu tiên: kết quả phải như cũ, không kỳ vọng giảm một nửa thời gian.
3. Thử mã chưa rõ và các variant khác số câu: hành vi fallback phải như trước.
4. Upload ảnh/import Excel vẫn chạy đường cũ.
5. Nếu có bất kỳ lệch đáp án/điểm, tắt `LIVE_SINGLE_PASS_GRADING`, restart backend
   và giữ ảnh gốc + mã đề + kết quả hai chế độ để điều tra, không hạ ngưỡng vá lỗi.
