# Gán nhãn câu bị nhận diện sai

Quy trình mới dùng ảnh gốc, cắt riêng câu đã chọn và lưu nhãn vòng tròn do admin xác nhận. Không lấy đáp án chuẩn của đề để đoán dấu tô của học sinh. Mẫu tự động trong kho cũ vẫn giữ nguyên, được ghi rõ **chưa xác minh** và không trộn vào gói dữ liệu đã duyệt.

## Trên ứng dụng

1. Quét phiếu và mở kết quả bằng tài khoản admin.
2. Nhấn **Training AI · Chọn câu cần sửa**.
3. Chọn phần, câu và ý a–d nếu là Phần II. Ý Phần II chưa đọc được sẽ được chọn trước. Với trường hợp anh gửi: chọn **Phần II → Câu 6 → Ý c**.
4. Nhấn **Xem ảnh câu đã chọn**. Đối chiếu hai vòng tròn trên ảnh gốc; có thể phóng to. Nếu cắt lệch hoặc thiếu ô, quét lại và không xác nhận mẫu này.
5. Chọn dấu tô thực tế: Đúng/Sai, cả hai, không tô hoặc không rõ. Phần I chọn A–D; Phần III xác nhận dấu âm, dấu phẩy và từng cột số, không lấy chữ viết tay.
6. Xác nhận đã đối chiếu ảnh và nhãn; nhấn **Lưu mẫu câu này**. Chọn thêm câu khác nếu cần.
7. Vào **Hồ sơ → Dữ liệu huấn luyện**, xem ảnh và từng nhãn, rồi duyệt hoặc loại. Chỉ mẫu đã duyệt được xuất.

Admin web cũng có trang `/admin/grading/trainingcorrection/`: ảnh câu, nhãn, bộ lọc trạng thái/phần/mẫu phiếu và thao tác duyệt/loại. Chỉ superuser truy cập được API quản trị; staff hoặc giáo viên thường không được gán nhãn/duyệt qua API.

## Đồng bộ về Windows

Tại `D:\chamtrac nghien v2`, chạy một dòng trong Windows PowerShell 5.1 hoặc PowerShell 7:

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File .\scripts\sync_training.ps1
```

Mặc định dùng VPS `52.220.123.56` và khóa SSH riêng trong `%USERPROFILE%\.ssh\LightsailDefaultKey-ap-southeast-1.pem`. Khóa/mật khẩu không được chép vào mã nguồn. Có thể truyền `-VpsIp`, `-Key` và `-OutputDirectory` để thay cấu hình.

Dữ liệu nguồn nằm trong volume `media` và PostgreSQL trên VPS. Máy Windows nhận snapshot mới tại `D:\chamtrac nghien v2\Traing\reviewed_<thời gian>\`; `LATEST.txt` chỉ đến snapshot gần nhất. Không xóa hoặc ghi đè snapshot cũ. Thư mục Traing đã bị loại khỏi Git và Docker build.

Gói dữ liệu gồm:

- `questions/`: ảnh vùng câu gốc dạng PNG xám, không có vòng màu chấm điểm hoặc thông tin tên/SBD trong phần đầu phiếu.
- `filled/` và `empty/`: ảnh vòng tròn 32×32, nhãn do người xác nhận. Nhãn `skip` không xuất thành mẫu phân lớp.
- `manifest.json`: phần/câu/ý, nhãn từng vòng, kết quả máy đọc, kết quả xác nhận, tọa độ và hash ảnh/mẫu phiếu.
- `group_id` và `split`: một ảnh nguồn nằm trong một nhóm train hoặc validation; không chia các vòng tròn của cùng ảnh vào cả hai tập.

Đây là bước tạo bộ dữ liệu có nhãn, **không phải nút huấn luyện trực tiếp trên VPS**. Live hiện dùng bộ đọc dấu tô từ ảnh gốc và không gọi CNN để quyết định đáp án. Do đó lưu một mẫu không tự sửa câu 6c ngay. Sau khi có nhiều ảnh đa dạng và nhãn được duyệt, cần đánh giá lỗi, thử thuật toán/mô hình ứng viên trên nhóm ảnh độc lập, kiểm tra tốc độ rồi mới cân nhắc triển khai. Không thay model đang dùng hoặc giảm ngưỡng tô chỉ vì một ví dụ.

## Backend

Các API cũ giữ nguyên. Các API mới nằm dưới `/api/v1/training/corrections/`:

- POST `preview/`: ảnh gốc, mã phiếu, phần/câu/ý, góc Live nếu có. Trả crop và token ký có hiệu lực 30 phút, gắn với admin hiện tại.
- POST `save/`: token, toàn bộ nhãn vòng tròn và `confirmed: true`. Lưu hoặc cập nhật một câu; thay nhãn đưa mẫu về chờ duyệt.
- GET danh sách: lọc pending/approved/rejected, phân trang 20 mẫu.
- POST `<id>/review/`: duyệt/loại và xác nhận đã kiểm tra.
- GET `export/`: ZIP chỉ chứa mẫu đã duyệt.

Ảnh được phục vụ qua private media có kiểm tra tài khoản. Preview không lưu nguyên phiếu trên server. Không thay đáp án bài thi, điểm, tín dụng hoặc ngưỡng OMR. Crop/align chỉ chạy khi mở Training AI, dùng cùng khóa bảo vệ trạng thái template của grader. Migration 0007 chỉ tạo bảng mới, không sửa dữ liệu cũ.

## BUG FIX REPORT

- **ROOT CAUSE**: Kho training cũ lưu nhãn máy tự đọc và không có chọn câu, nhãn xác nhận hay hàng chờ duyệt. Kết quả trống như 6c không trở thành ví dụ sửa lỗi có giám sát. Chỉ từ ảnh màn hình chưa đủ để xác định nguyên nhân OMR bỏ sót 6c.
- **FILES CHANGED**: `grading/training_data.py`, `api/training_views.py`, model/migration TrainingCorrection, private media/admin, màn hình Flutter Training AI và quản trị, lệnh export và script sync. Các tệp lõi OMR và trọng số giữ nguyên.
- **CHANGES MADE**: Crop theo câu; nhãn tô/trống/bỏ qua; token ký; phân quyền; chống trùng; duyệt/loại; export có nhóm ảnh và snapshot Traing.
- **TESTS RUN**: Django tests training corrections, accounts; unittest Live CPU; Flutter widget/answer-key/Live capture; Dart analyze; APK debug; Docker health/check; đồng bộ VPS.
- **TEST RESULTS**: Kết quả cuối cùng và giới hạn kiểm tra ghi trong `tests/test_ketqua/training_20261001/SUMMARY.md` trên máy.
- **REGRESSION RISK**: Migration thêm bảng và private-media mới; API cũ giữ nguyên. Độ chính xác bộ dữ liệu vẫn phụ thuộc việc admin đối chiếu nhãn với crop đúng vị trí. Chưa xác nhận camera trên điện thoại thật khi thiết bị ADB chưa kết nối.
- **UNRELATED ISSUES FOUND**: Phân loại CNN trong script cũ chưa dùng manifest chia nhóm; không dùng trực tiếp cách random-split cũ cho dataset mới. Chưa huấn luyện/thay trọng số trong thay đổi này.
