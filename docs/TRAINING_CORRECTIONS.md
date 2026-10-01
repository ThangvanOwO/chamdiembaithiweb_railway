# Gán nhãn câu bị nhận diện sai

Quy trình mới dùng ảnh gốc, cắt riêng câu đã chọn và lưu nhãn vòng tròn do admin xác nhận. Không lấy đáp án chuẩn của đề để đoán dấu tô của học sinh. Mẫu tự động trong kho cũ vẫn giữ nguyên, được ghi rõ **chưa xác minh** và không trộn vào gói dữ liệu đã duyệt.

## Trên ứng dụng

### Lấy toàn bộ phiếu

1. Sau khi quét, admin mở **Training AI · Lấy phiếu / sửa dấu tô** rồi chọn **Lấy toàn bộ phiếu / kiểm tra vùng vàng**.
2. Backend đọc ảnh một lần, căn phiếu một lần và tạo các vùng Phần I/II/III. Mẫu 40–08–06 có 78 vùng: 40 câu Phần I, 32 ý Phần II và 6 câu Phần III (494 vòng tròn).
3. Các nhãn máy đọc được điền sẵn để đối chiếu với ảnh. Đây là gợi ý, chưa phải dữ liệu đã duyệt. Dùng **Chỉ xem vùng cần kiểm tra** để tìm các vùng vàng. Kết quả quét ban đầu khác kết quả đọc lại cũng cần kiểm tra.
4. Chọn **Chọn vòng tròn thực tế / xác nhận**. Chạm vòng tròn hoặc nhãn để đổi đã tô/chưa tô; nhấn giữ vòng tròn để bỏ qua ô không rõ. Có thể chọn nhiều ô, cả cột để trống, dấu âm và dấu phẩy. Không lấy đáp án chuẩn của đề để gán nhãn.
5. Vùng vàng phải được xác nhận riêng. Vùng chưa khớp lưới không được chọn; có thể bỏ các vùng không muốn lấy. Bỏ chọn được báo rõ và vùng đó không được lưu.
6. Đối chiếu tất cả vùng đã chọn, tích xác nhận cả phiếu rồi nhấn **Xác nhận & lấy … vùng câu**. Admin đang duyệt chính các nhãn này nên các mẫu sẵn sàng xuất ngay. Không cần duyệt lại 78 câu riêng lẻ. Lưu lại cùng phiếu không nhân bản; nhãn thay đổi có revision mới.

Trong **Hồ sơ → Dữ liệu huấn luyện**, nút bút cho phép admin sửa từng vòng tròn của mẫu đã lưu. Sửa nhãn đưa mẫu về chờ duyệt; bản duyệt cũ không áp dụng cho nhãn mới.

### Chỉ lấy một câu

1. Quét phiếu và mở kết quả bằng tài khoản admin.
2. Nhấn **Training AI · Lấy phiếu / sửa dấu tô** và dùng bộ chọn câu bên dưới nút lấy toàn bộ.
3. Chọn phần, câu và ý a–d nếu là Phần II. Ý Phần II chưa đọc được sẽ được chọn trước. Với trường hợp anh gửi: chọn **Phần II → Câu 6 → Ý c**.
4. Nhấn **Xem ảnh câu đã chọn**. Đối chiếu hai vòng tròn trên ảnh gốc; có thể phóng to. Nếu cắt lệch hoặc thiếu ô, quét lại và không xác nhận mẫu này. Khi không căn được lưới, cả giao diện và backend đều chặn lưu.
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

- `sources/`: ảnh gốc của phiếu được lấy theo luồng toàn bộ, lưu một lần cho nhiều câu. Ảnh gốc có thể chứa thông tin học sinh; chỉ admin/chủ sở hữu được truy cập và gói xuất dành riêng cho người quản trị.
- `questions/`: ảnh vùng câu gốc dạng PNG xám, không có vòng màu chấm điểm hoặc thông tin tên/SBD trong phần đầu phiếu.
- `filled/` và `empty/`: ảnh vòng tròn 32×32, nhãn do người xác nhận. Nhãn `skip` không xuất thành mẫu phân lớp.
- `manifest.json`: phần/câu/ý, nhãn từng vòng, kết quả máy đọc, kết quả xác nhận, tọa độ và hash ảnh/mẫu phiếu.
- `group_id` và `split`: một ảnh nguồn nằm trong một nhóm train hoặc validation; không chia các vòng tròn của cùng ảnh vào cả hai tập.

Manifest phiên bản 2 thêm `source_file`, `label_origin` và giữ gợi ý máy đọc trong `geometry.machine_labels` để đối chiếu với nhãn người xác nhận. Mẫu cũ không có ảnh gốc vẫn xuất được với `source_file=null`. Chỉ ảnh gốc JPEG/PNG được hỗ trợ trong luồng lấy toàn bộ. Bản xem trước hết hạn sau 30 phút; khi hết hạn phải tải lại phiếu.

## Gói minh họa trên Windows

Chạy `python tools/training/export_training_demo.py` từ thư mục gốc để kiểm tra luồng preview → xác nhận → lấy cả phiếu → xuất ZIP bằng database và media tạm riêng. Công cụ không dùng dữ liệu thật. Đầu ra ở `Traing/demo_sheet_20261001/`, ghi rõ `synthetic_demo_not_production`; không được đưa gói DEMO vào tập dữ liệu thật đã duyệt.

Gói kiểm thử chứa 78 vùng câu, 94 ảnh ô tô, 400 ảnh ô trống và một ảnh gốc, có các ví dụ số âm/thập phân. `training-demo.zip` và `manifest.json` cho thấy chính xác cấu trúc xuất. Đồng bộ VPS vẫn dùng `scripts/sync_training.ps1` và snapshot `reviewed_*`, tách khỏi thư mục `demo_*`.

Đây là bước tạo bộ dữ liệu có nhãn, **không phải nút huấn luyện trực tiếp trên VPS**. Live hiện dùng bộ đọc dấu tô từ ảnh gốc và không gọi CNN để quyết định đáp án. Do đó lưu một mẫu không tự sửa câu 6c ngay. Sau khi có nhiều ảnh đa dạng và nhãn được duyệt, cần đánh giá lỗi, thử thuật toán/mô hình ứng viên trên nhóm ảnh độc lập, kiểm tra tốc độ rồi mới cân nhắc triển khai. Không thay model đang dùng hoặc giảm ngưỡng tô chỉ vì một ví dụ.

## Backend

Các API cũ giữ nguyên. Các API mới nằm dưới `/api/v1/training/corrections/`:

- POST `preview/`: ảnh gốc, mã phiếu, phần/câu/ý, góc Live nếu có. Trả crop và token ký có hiệu lực 30 phút, gắn với admin hiện tại.
- POST `save/`: token, toàn bộ nhãn vòng tròn và `confirmed: true`. Lưu hoặc cập nhật một câu; thay nhãn đưa mẫu về chờ duyệt.
- GET danh sách: lọc pending/approved/rejected, phân trang 20 mẫu.
- POST `<id>/review/`: duyệt/loại và xác nhận đã kiểm tra, gửi `revision` của nhãn đang xem. Mẫu đã bị sửa trong lúc mở màn hình trả HTTP 409 để tải lại.
- GET `export/`: ZIP chỉ chứa mẫu đã duyệt.

Ảnh được phục vụ qua private media có kiểm tra tài khoản. Preview không lưu nguyên phiếu trên server. Không thay đáp án bài thi, điểm, tín dụng hoặc ngưỡng OMR. Crop/align chỉ chạy khi mở Training AI, dùng cùng khóa bảo vệ trạng thái template của grader. Migration 0007 chỉ tạo bảng mới, không sửa dữ liệu cũ.

## BUG FIX REPORT

- **ROOT CAUSE**: Kho training cũ lưu nhãn máy tự đọc và không có chọn câu, nhãn xác nhận hay hàng chờ duyệt. Kết quả trống như 6c không trở thành ví dụ sửa lỗi có giám sát. Chỉ từ ảnh màn hình chưa đủ để xác định nguyên nhân OMR bỏ sót 6c.
- **FILES CHANGED**: [Crop/dataset](<D:/chamtrac nghien v2/grading/training_data.py>), [API](<D:/chamtrac nghien v2/api/training_views.py>), [Training AI](<D:/chamtrac nghien v2/gradeflow_app/lib/screens/training_correction_screen.dart>), [admin](<D:/chamtrac nghien v2/gradeflow_app/lib/screens/admin_training_screen.dart>), [đồng bộ](<D:/chamtrac nghien v2/scripts/sync_training.ps1>); model/migration TrainingCorrection, private media/admin và lệnh export. Các tệp lõi OMR và trọng số giữ nguyên.
- **CHANGES MADE**: Crop theo câu; nhãn tô/trống/bỏ qua; token ký; phân quyền; chống trùng; duyệt/loại; export có nhóm ảnh và snapshot Traing.
- **TESTS RUN**: Django tests training corrections, accounts; unittest Live CPU; Flutter widget/answer-key/Live capture; Dart analyze; APK debug; Docker health/check; đồng bộ VPS.
- **TEST RESULTS**: 13 kiểm thử mới đạt trên SQLite local/Docker và PostgreSQL VPS; 76 kiểm thử accounts, 8 Live CPU, 4 widget, 3 answer-key và 7 Live capture đạt. 7 case Live capture phụ thuộc fixture chưa được cung cấp bị skip. Dart analyze các tệp mới/API: không có lỗi. APK debug build 2007 thành công; Docker local/VPS healthy, `check` và migration check sạch. PowerShell 5.1 đồng bộ được snapshot 0 mẫu đã duyệt; không giả tạo nhãn thật. Chi tiết: [SUMMARY](<D:/chamtrac nghien v2/tests/test_ketqua/training_20261001/SUMMARY.md>).
- **REGRESSION RISK**: Migration thêm bảng và private-media mới; API cũ giữ nguyên. Độ chính xác bộ dữ liệu vẫn phụ thuộc việc admin đối chiếu nhãn với crop đúng vị trí. Chưa xác nhận camera trên điện thoại thật khi thiết bị ADB chưa kết nối.
- **UNRELATED ISSUES FOUND**: Phân loại CNN trong script cũ chưa dùng manifest chia nhóm; không dùng trực tiếp cách random-split cũ cho dataset mới. Chưa huấn luyện/thay trọng số trong thay đổi này.
