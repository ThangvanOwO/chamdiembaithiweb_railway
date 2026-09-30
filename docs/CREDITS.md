# Tài khoản và tín dụng GradeFlow

Triển khai ngày 24/09/2026. Phạm vi giao diện: website Django; backend tính phí áp dụng cả API mà ứng dụng Android đang gọi. Chưa build APK mới trong tác vụ này.

## Đã hoạt động

- Nút hiện/ẩn mật khẩu trên đăng ký, đăng nhập và đặt mật khẩu mới. Không lưu hoặc trả lại mật khẩu dạng rõ.
- Thông báo đăng nhập/đăng ký thành công, tài khoản bị vô hiệu hóa không thể đi qua nhánh đăng nhập dự phòng.
- `/accounts/credits/`: số dư và 50 giao dịch gần nhất. Thanh điều hướng dẫn đến ví và admin (chỉ nhân viên).
- `/admin/auth/user/`: quản lý người dùng hiện có. `/admin/accounts/creditwallet/`: điều chỉnh bằng số điểm cộng/trừ và lý do bắt buộc. Cần quyền `accounts.change_creditwallet` và tài khoản staff hoạt động. Lịch sử chỉ đọc, ghi cả người điều chỉnh; số dư không sửa trực tiếp qua form.
- 100 điểm cấp đúng một lần: signal cho tài khoản mới từ web/API/Google/admin, data migration cho tài khoản cũ. Sổ giao dịch bảo vệ khỏi xóa dây chuyền; nên vô hiệu hóa tài khoản thay vì xóa dữ liệu tín dụng.
- Quét thành công 1 ảnh = 1 điểm. Giữ điểm trước khi gọi engine, hoàn phần ảnh lỗi sau khi trả kết quả. Lô ảnh cần đủ điểm cho cả lô; ZIP tính theo số ảnh có định dạng được hỗ trợ. Không tính tiền theo số lần nội bộ engine thử xoay hoặc đổi mã đề.
- Bao phủ `api.views.grade_api`, `grading.views.upload_view`, `submission_regrade_view`, `grade_frame_api`, `grading.chamtn_api.api_exam_grade_batch`. Nhập ảnh đáp án không phải quét bài làm nên không tính phí.
- API batch yêu cầu đăng nhập, CSRF và sở hữu đề thi. API frame dùng CSRF cho session. API mobile tiếp tục dùng cơ chế xác thực DRF hiện có.

## Gửi lại yêu cầu và đồng thời

Client nên gửi `Idempotency-Key` hoặc trường form `scan_key` (UUID, tối đa 128 ký tự ASCII chữ/số/`:_-`). Dùng cùng key khi retry cùng lần quét; tạo key mới khi chủ động quét lần khác. Form upload/chấm lại trên web tự tạo key.

Client cũ không gửi key được khử trùng theo dấu vân tay ảnh, tham số, endpoint và đáp án. Vì vậy ảnh và cấu hình giống hệt được trả kết quả đã lưu, không tính thêm điểm. Muốn cố ý quét lại cùng dữ liệu, gửi key mới. Không thay đổi cấu trúc JSON kết quả mà Flutter đang sử dụng; phản hồi hết điểm có `success:false`, `error`, mã HTTP 402.

Giao dịch dùng cập nhật có điều kiện ở DB, `F()` và transaction ngắn. Không giữ transaction trong lúc OpenCV chạy. Yêu cầu cùng key đang chạy trả 409. Key dùng lại cho nội dung khác trả 409. Kết quả hoàn tất được lưu để retry không tạo bài nộp/trừ tiền lần nữa.

**Giới hạn cần theo dõi:** nếu tiến trình bị tắt cứng/mất điện giữa lúc quét, lượt quét có thể còn `finished=False` và điểm tạm giữ chưa được hoàn. Xem `/admin/accounts/scanoperation/`, đối chiếu bài nộp/log trước khi điều chỉnh bằng admin có lý do. Không tự động hoàn lượt còn chạy vì có thể đã tạo kết quả. Bộ nhớ DB có lưu nội dung phản hồi để replay (bao gồm ảnh kết quả base64 trên mobile); cần bổ sung chính sách lưu trữ trước khi mở rộng tải lớn.

## Thanh toán và quảng cáo: chưa mở

Các nút mua điểm/xem quảng cáo được vô hiệu hóa và có thông báo rõ. Chưa có cổng thanh toán hoặc callback thưởng công khai, không có giao dịch tiền thật trong lần triển khai này.

`accounts/credit_integrations.py` là phần lõi chuẩn bị tích hợp:

- Đơn mua lưu cố định số điểm, số tiền theo đơn vị nhỏ nhất và tiền tệ phía server. Chỉ cộng khi sự kiện đã xác minh khớp đơn hàng và trạng thái `paid`; replay không cộng lại.
- Thưởng cần adapter xác minh hoàn tất, mã sự kiện duy nhất và tài khoản nhận. Giới hạn tối đa 3 lần; hỗ trợ chu kỳ ngày theo Asia/Ho_Chi_Minh hoặc toàn thời gian. Điểm thưởng mặc định 0, chu kỳ chưa cấu hình nên không cấp thưởng.
- Adapter chỉ được nạp từ cấu hình của quản trị viên. Không tin vào cờ “đã xem”, số điểm, số tiền hoặc user ID tự gửi từ trình duyệt. Không thưởng bằng thao tác nhấp quảng cáo AdSense thường.
- Sau khi chọn nhà cung cấp, cần viết adapter xác minh chữ ký/timestamp/user binding, nối checkout và webhook URL, giao diện nhận thưởng tự nguyện, rồi kiểm thử sandbox của nhà cung cấp trước khi bật. Chỉ đặt đường dẫn adapter vào settings chưa làm nút mua/thưởng hoạt động.

Cần chủ dự án chốt: 3 lượt/ngày hay tổng cộng; điểm mỗi lượt; giá gói; nhà cung cấp thanh toán và quảng cáo có thưởng. Các test adapter hiện dùng sự kiện giả lập trong test DB, không chứng minh tích hợp nhà cung cấp thật.

## Khôi phục mật khẩu

`/accounts/password-reset/` dùng token đặt lại mật khẩu của Django. Cấu hình môi trường: `EMAIL_HOST`, `EMAIL_PORT`, `EMAIL_HOST_USER`, `EMAIL_HOST_PASSWORD`, `EMAIL_USE_TLS`, `DEFAULT_FROM_EMAIL`. Khi chưa có SMTP, giao diện báo chưa cấu hình; không giả báo gửi thành công. Đã kiểm tra luồng token dùng một lần với email backend trong bộ test, chưa gửi email thật.

## Triển khai và kiểm thử

- Đã sao lưu SQLite bằng SQLite backup API vào `scratch/credit_rollout_20260924/before_credits.sqlite3` trước migration.
- Chạy `python manage.py migrate --noinput`, `python manage.py collectstatic --noinput` khi triển khai checkout này ở môi trường khác.
- Kiểm thử: `python manage.py test accounts website`; kiểm thử routing Live độc lập: `python -m unittest discover -s tests -p test_live_latency.py -q`.
- Routing test cũ chỉ kiểm tra engine với user giả, nên mock ranh giới tính phí để giữ đặc tính không ghi DB. Các kiểm thử tín dụng mới dùng DB test và endpoint thật với engine giả lập; không chạy đo độ chính xác OMR vì thuật toán không đổi.
- Kiểm tra trình duyệt: trang tín dụng của phiên QA, trang đăng ký và nút hiện/ẩn mật khẩu. Không tạo tài khoản thực hay giao dịch mua điểm để kiểm thử.
- Kết quả: bộ tài khoản/website 60 test đạt; sau các kiểm tra bổ sung, bộ endpoint/concurrency 15 test đạt; routing Live 16 test đạt. `manage.py check` và `makemigrations --check --dry-run` đạt. Migration local có 6 tài khoản, 6 ví và đúng 6 giao dịch tặng điểm. Log trong `scratch/credit_rollout_20260924/`.
- `git diff --check` trong phạm vi chỉnh sửa đạt. Kiểm tra toàn worktree còn báo whitespace đã có sẵn ở `grading/engine/hi.py`; không sửa file engine trong tác vụ này.

## BUG FIX REPORT — kiểm soát tài khoản và API quét

- **ROOT CAUSE**: nhánh đăng nhập dự phòng chỉ kiểm tra mật khẩu, bỏ qua `is_active`; API batch cũ tìm đề thi bằng ID mà không kiểm tra đăng nhập/chủ sở hữu; tham số `next` chuyển hướng trực tiếp ra ngoài website.
- **FILES CHANGED**: `accounts/views.py`, `grading/chamtn_api.py`, `grading/views.py`, `static/chamtn/js/core.js` và các bài test trong `accounts/`.
- **CHANGES MADE**: chặn tài khoản bị vô hiệu hóa; giới hạn chuyển hướng cùng website; bảo vệ endpoint batch/frame bằng xác thực/CSRF và kiểm tra quyền sở hữu batch; client SPA gửi CSRF header.
- **TESTS RUN**: `manage.py test accounts website`, các test endpoint/concurrency bổ sung, routing Live độc lập như trên.
- **TEST RESULTS**: các bộ test sau sửa đều đạt. Test đầu đã phát hiện static manifest thiếu asset mới; chạy collectstatic đã khắc phục. Assertion URL asset trong test dùng Django static resolver để tương thích tên file có hash.
- **REGRESSION RISK**: client session tự viết gọi batch/frame phải gửi CSRF header. Client mobile token vẫn đi endpoint v1 như trước. Yêu cầu quét hiện cần đủ tín dụng theo thay đổi đã yêu cầu.
- **UNRELATED ISSUES FOUND**: lỗi scoring không cấu hình được ghi ngay bên dưới; thuật toán OMR và whitespace trong engine không thay đổi.

## Phát hiện ngoài phạm vi

Test bước đầu với đề thi không có cấu hình scoring gặp lỗi có sẵn trong web upload/regrade: `scoring_config.get(...)` khi `scoring_config=None`. Không sửa thuật toán/scoring trong tác vụ tín dụng. Bộ test tính phí sử dụng đề thi có cấu hình hợp lệ; khi lỗi xử lý xuất hiện, điểm được hoàn lại.

Nguồn kỹ thuật: [Django F expressions](https://docs.djangoproject.com/en/6.0/ref/models/expressions/), [chính sách quảng cáo có thưởng](https://support.google.com/adsense/answer/9121589?hl=en-GB).
