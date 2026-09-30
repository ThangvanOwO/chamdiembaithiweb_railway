# Sửa lỗi mã hóa khi tạo đề từ ảnh phiếu đáp án

## Nguyên nhân đã tái hiện

Luồng app: `ExamImportScreen._scanAnswerSheet` → `ApiService.parseImageFile` → `POST /api/v1/parse-image/` → `api.views.parse_image_api`.

Endpoint trước đây gọi trực tiếp `engine.process_sheet`, khác với luồng chấm có bọc output UTF-8. Console/pipe Windows dùng cp1252 không biểu diễn được nhiều dấu tiếng Việt.

Trên ảnh tạm `tmp7kablq4b.jpg` lúc 12:51:02, đã tái hiện chuỗi lỗi:

1. Engine tìm được phiếu theo `paper+markers`.
2. `hi.py` dòng 3683 in `[OK] Phát hiện bằng: ...` → UnicodeEncodeError ký tự `ệ` (`U+1EC7`).
3. UnicodeEncodeError thuộc nhóm ValueError, nên bị nhánh `except ValueError` bắt vào như lỗi phát hiện phiếu.
4. Dòng 3692 in `[LỖI] ...` → lỗi mới ở chữ `Ỗ` (`U+1ED6`), vị trí 2. Đây chính xác là thông báo trên ảnh màn hình, che mất lỗi in log ban đầu.

Vì vậy ảnh lỗi này không chứng minh detector đã hỏng. Không thay đổi thuật toán nhận diện để xử lý lỗi console.

## Thay đổi giới hạn trong nhập đề

- Thêm `api/answer_image_import.py`: chạy tác vụ nhập ảnh trong tiến trình Python riêng với `-X utf8`, `PYTHONIOENCODING=utf-8` và giải mã output UTF-8 rõ ràng.
- Output chẩn đoán đi stderr của tiến trình con, stdout chỉ chứa JSON dữ liệu đáp án. Không đổi/reconfigure `sys.stdout`, `sys.stderr` của server đang phục vụ Live.
- Tiến trình con nạp template mặc định rõ ràng, không phụ thuộc template toàn cục còn lại từ request khác.
- Đặt timeout 120 giây; không bật cửa sổ console phụ trên Windows; dọn thư mục tạm khi thành công, lỗi hoặc timeout. Các bản sao chẩn đoán mà engine lưu vào `tests/ketqua` theo hành vi có sẵn vẫn được giữ.
- Chỉ thay điểm gọi trong `api.views.parse_image_api`; giữ nguyên cấu trúc response cho bước Xác nhận.
- Không chỉnh Flutter/APK, detector camera, thời gian chụp, `hi.py`, `live_bubble_reader.py`, ngưỡng tô, API chấm Live hay Upload. Không chỉnh endpoint nhập đề web cũ `grading.views.parse_image_api`, không phải endpoint app trong ảnh này.

Đổi lại tác vụ nhập ảnh có chi phí khởi tạo tiến trình/model riêng. Chưa benchmark dưới tải nhiều người dùng; timeout không phải SLA thời gian xử lý.

## Kiểm thử

```powershell
python -m unittest discover -s tests -p test_answer_image_import.py -q
python -m unittest discover -s tests -p 'test_live_*.py' -q
python manage.py check
```

- **8 test nhập ảnh: OK, 10.166 giây**. Có test tái hiện đúng U+1ED6 vị trí 2 ở cách gọi cũ; ảnh thật lúc 12:51 đi qua endpoint với stdout cp1252 trả HTTP 200/success và dữ liệu review; ảnh hỏng trả thông báo dễ hiểu; kiểm tra file thiếu/sai đuôi, timeout/lỗi worker, dọn file tạm, giữ nguyên streams của server và format đáp án Đ/S.
- **17 test Live cũ: OK, 27.779 giây**, không sửa test Live trong lần này.
- Django system check không có lỗi; health server địa phương trả `ok: true`.
- Có ResourceWarning file PIL từ engine legacy trong test tái hiện lỗi và test Live; không sửa engine để dọn cảnh báo ngoài phạm vi.

Fixture giữ nguyên byte ở `tests/fixtures/exam_import_capture_20260912.jpg`.
SHA256: `E9E992C451E61034D8B82119DCBE1141E0205991DAF8AB623A70CD6C548906F0`.

Kiểm thử dùng APIRequestFactory với xác thực giả lập, không ghi đề thi/bài nộp vào database. Đây là xác nhận hết lỗi dừng xử lý/mã hóa và hợp đồng response; không phải chứng nhận mọi ô đáp án nhập tự động đều đúng hoặc thao tác giao diện trên điện thoại đã được thử lại.

## Nghiệm thu

Không cần build/cài APK mới cho sửa lỗi này. Backend phục vụ app phải chạy code mới. Người dùng thử lại Tạo đề từ file → Quét phiếu → Xác nhận; đối chiếu đáp án trước khi bấm Lưu. Phiên này không sửa dữ liệu đề đã lưu và không triển khai server từ xa.
