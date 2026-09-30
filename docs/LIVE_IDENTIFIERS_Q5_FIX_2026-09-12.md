# Live Camera: SBD, mã đề và Phần III câu 5

## Kết quả đã kiểm chứng

Người dùng xác nhận chuẩn: SBD `011232`, mã đề `001`, câu 5 Phần III `22`.
Ba JPEG gốc đều đọc đúng ba giá trị này sau sửa:

| JPEG gốc trong media/submissions/2026/09 | Kết quả đối chiếu | SBD / mã đề / P3-5 |
| --- | --- | --- |
| live_O2ZBpeK.jpg | 20260912_051201_live_sbd_011_3__md___1_result.jpg | 011232 / 001 / 22 |
| live_F6lMUpt.jpg | 20260912_121135_tmpdnbev9i2_sbd_011_3__md_0_1_result.jpg | 011232 / 001 / 22 |
| live_Mq6I2UX.jpg | 20260912_051225_live_sbd_011_3__md_0_1_result.jpg | 011232 / 001 / 22 |

Đây là kiểm thử offline trên pixel JPEG gốc, không phải lần quét mới trên điện thoại. Ảnh thứ ba là ca bổ sung trong quá trình phát triển, không phải tập kiểm thử độc lập chưa từng dùng để điều chỉnh thuật toán.

## Nguyên nhân

1. Nhánh Live P2/P3 đã dùng ảnh gốc, nhưng SBD/mã đề vẫn đọc qua tiền xử lý legacy có xóa chữ/tăng tương phản. Vị trí đo số còn lệch so với tâm vòng tròn thật.
2. Phần III dùng tọa độ cố định. Ví dụ Q5 ảnh đầu: cột mẫu `[1016,1051,1085,1119]`, cột đo được `[1011.5,1045.5,1079.5,1113.5]`; hàng số 0 mẫu y=1558, thực tế y=1550.5. Lệch 4–8 pixel khiến viền ô trống lọt vào lõi đo, tạo trạng thái không chắc chắn và hủy cả câu dù hai số 2 có mực.
3. Đây không chỉ là thiếu độ nhạy. Nới ngưỡng mực chung dễ tái sinh lỗi nhận ô trống đã tô.

## Sửa trong nhánh Live

- `grading/engine/live_bubble_reader.py`: căn lưới cục bộ theo vòng tròn in bằng Hough; ghép ứng viên với hàng/cột gần nhất; yêu cầu đủ phân bố trên nhiều hàng/cột, không chạy theo chấm đen đơn lẻ. Dịch chuyển giới hạn dưới nửa khoảng cách ô; thiếu tối đa 20% hàng chỉ được suy ra khi các hàng còn lại chứng minh lưới đều.
- SBD/mã đề đo mực từ ảnh gốc đã warp với bán kính phù hợp ô nhỏ; giữ số 0 đầu; ô trống, không rõ hoặc tô nhiều số cùng cột không được đoán bằng argmax.
- P3 dùng tâm lưới đã căn, dịch dấu âm/dấu phẩy cùng vùng; vòng khoanh kết quả dùng đúng tọa độ đã đo.
- Ngưỡng bằng chứng mực giữ nguyên: tương phản >=0.16, phủ lõi >=60%, ít nhất 3/4 phần tư có mực. Q5 ảnh đầu: hai số 2 có coverage 1.0 và 0.9781; tất cả ô số khác là blank.
- `grading/engine/hi.py`: gọi bộ đọc ID mới **chỉ trong `if live_bubble_mode`**; log có `[LIVE OMR] IDs/P2/P3 raw-paper evidence` và trạng thái căn lưới ID.
- Cờ kích hoạt vẫn là `capture_pipeline=live_capture_v3`; không lấy `fast=1` làm cờ vì Upload cũng dùng fast. Không sửa template dùng chung, bộ đọc legacy, Part I, giao diện camera hoặc thời gian chụp trong lần sửa này.

## Kiểm thử và log

Lệnh chạy từ thư mục dự án:

```powershell
python tools/diagnostics/audit_live_identifiers.py
python -m unittest discover -s tests -p 'test_live_*.py' -q
python manage.py check
```

Kết quả cuối: **17 tests, 22.212 giây, OK**; Django check không có lỗi. Bao gồm:

- Ba ảnh thật đúng SBD/mã đề/Q5; 9 biến thể tăng/giảm sáng, mờ nhẹ hoặc tịnh tiến 2 pixel vẫn đúng.
- Năm ảnh cũ trống vùng ID/P3 không sinh chữ số/đáp án giả; P2/P3 chống nhận nhầm cũ vẫn đạt.
- Tô hai số cùng cột ID trả `?`; dữ liệu tổng hợp khác (`123456`/`987`) đọc theo mực, không gắn cứng đáp án người dùng.
- Test tích hợp xác nhận Upload mặc định và cả `fast_mode=True` không gọi bộ đọc Live; Part I không đổi trên các fixture tích hợp.
- Ca tô giả lập cũ dùng tâm template lệch 3–6 pixel so với ô thật được giữ để kiểm tra không sinh đáp án sai (có thể từ chối nếu mực không chắc chắn). Bổ sung 15 ca tô ở tâm đo độc lập bằng moment contour, gồm lệch ±2 pixel, đều đọc đúng `-1.234`. Không hạ tiêu chuẩn mực để ép ca tô lệch đạt.

Các test tích hợp vẫn phát ResourceWarning đóng file PIL từ helper legacy. `git diff --check` báo hai dòng whitespace có sẵn ở hi.py ngoài phần sửa này; không chỉnh mã Upload để dọn chúng.

Artifact tại `tests/ketqua/live_identifiers_20260912/`:

- `summary.json`: nguồn ảnh, phép biến đổi, bằng chứng mực và kết quả từng ca.
- Mỗi thư mục ảnh có `audit.json`, `raw_warp.png`, `identifiers.png`, `q5.png`, `verified_live.png`.
- `verified_live.png` chỉ khoanh lựa chọn ID/P3 bằng màu vàng, không chấm đúng/sai hay tạo điểm giả; đã kiểm tra trực quan ảnh đầu.
- Do không có log góc chụp mới, công cụ offline dùng SIFT/RANSAC khôi phục warp từ cặp gốc/kết quả (707/536/530 inlier, sai số trung vị <1px). Mực luôn đo trên pixel ảnh gốc; không đọc pixel vòng khoanh kết quả. SIFT này không được đưa vào pipeline production.

## Triển khai và giới hạn

Đây là sửa backend dành riêng cho Live. App đã gửi `live_capture_v3` không cần đổi giao thức hoặc build APK mới cho lần sửa này. Backend phục vụ điện thoại phải chạy mã mới; phiên này kiểm tra được health server địa phương `127.0.0.1:8000`, không triển khai lên server từ xa và không sửa bài/điểm đã lưu.

Cần nghiệm thu bằng lần chụp mới trên điện thoại: cùng phiếu ở vài điều kiện sáng, kiểm tra SBD/mã đề/Q5; thêm phiếu trống và tô nhiều số cùng cột. Chưa có lần thử điện thoại mới cho thay đổi này. Các test không chứng minh chính xác tuyệt đối với mọi giấy cong, độ mờ, bút chì hoặc mẫu in khác.
