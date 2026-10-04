# Giao diện quản trị GradeFlow · 04/10/2026

## Kết quả

- Trang `/admin/` có tổng quan hệ thống, số liệu, lối vào nhanh, danh mục dữ liệu theo quyền và thao tác gần đây.
- Đồng bộ logo nền trong suốt, bảng danh sách, tìm kiếm, biểu mẫu, màu sáng/tối và bố cục trên điện thoại.
- Trang an toàn tài khoản dùng cùng hệ thống màu; biểu mẫu thông báo chia rõ nội dung, lịch sự kiện và thời hạn.
- Mục **Thiết bị nhận thông báo** đọc dữ liệu đăng ký hiện có. Chỉ superuser được xem; không cho sửa, thêm, xóa hay hiển thị FCM token/session hash.

## Thiết bị người dùng và đợt kiểm thử

Hệ thống hiện lưu `PushDevice`: mã cài đặt ngẫu nhiên, tài khoản hiện tại, trạng thái đăng ký và thời gian cập nhật đăng ký. Một người có thể có nhiều cài đặt, một cài đặt có thể đổi tài khoản. Trạng thái đăng ký không xác nhận máy đang online, còn cài app hoặc đang dùng app.

Chưa lưu hãng máy, model, phiên bản Android/app hoặc lịch sử mở ứng dụng. Không suy đoán thông tin này từ mã thông báo. Thiết bị chưa đăng ký nhận thông báo có thể không có trong danh sách. Không bổ sung theo dõi thiết bị vào ứng dụng trong thay đổi này.

Google Play quy định tối thiểu 12 người tham gia liên tục 14 ngày với các tài khoản cá nhân thuộc diện áp dụng. Điều kiện tham gia phải đối chiếu Play Console, không dùng số tài khoản GradeFlow hoặc thiết bị FCM để xác nhận đủ điều kiện. Nguồn: https://support.google.com/googleplay/android-developer/answer/14151465?hl=en

## Phạm vi

Các tệp thay đổi: `dashboard/admin.py`, `dashboard/templatetags/admin_dashboard.py`, các template trong `templates/admin/`, `static/css/admin-custom.css`, `static/css/admin-risk.css` và logo `static/img/gradeflow_logo_transparent.png` sao chép từ tài sản đã duyệt.

Không sửa schema, API, nhận diện, camera hoặc ứng dụng Flutter. Giữ các thay đổi khác đang có trong working tree.

## Kiểm tra

- Kiểm tra quản trị, quyền, danh sách thiết bị, tìm kiếm/lọc, ẩn mã xác thực, chặn sửa/xóa thiết bị; hồi quy xử lý rủi ro, ví tín dụng và ranh giới truy cập.
- Lệnh: `python manage.py test dashboard.test_admin_console accounts.test_risk.RiskTests accounts.tests.CreditAdminTests accounts.test_security.AccessBoundaryTests --noinput` trong Docker, tiến trình kiểm thử dùng `DJANGO_DEBUG=True` để HTTP của test client không bị chuyển sang HTTPS. Dữ liệu kiểm thử tách riêng; không đổi cấu hình dịch vụ.
- Kiểm tra cấu hình Django và kiểm tra migration chưa tạo: `manage.py check`, `manage.py makemigrations --check --dry-run`.
- Kết quả cuối: **33 ca đạt**, gồm thêm 5 ca hồi quy thông báo/sự kiện (`dashboard.test_events`). Django không phát hiện lỗi cấu hình hoặc migration mới.
- Đã kiểm tra bố cục máy tính 1440px và điện thoại 390px, sáng/tối. Trang tổng quan và thiết bị không tràn ngang; danh sách dữ liệu dài cuộn trong bảng.
- Kiểm tra hình ảnh trên trình duyệt với trang Django được render từ cơ sở dữ liệu kiểm thử riêng, tài khoản giả `example.com`; không chụp danh sách người dùng thật để làm mẫu.
- Ảnh và log: `artifacts/admin_ui_20261004/`. Ảnh minh họa không thể dùng làm báo cáo người tham gia kiểm thử thực tế.

## Đường lui

Bản sao các tệp trước khi sửa: `scratch/admin_ui_before_20261004/`. Thay đổi không yêu cầu migration, nên có thể khôi phục mã/giao diện và dựng lại Docker mà không phục hồi dữ liệu.

Website local cập nhật bằng `docker compose -f docker-compose.local.yml up -d --build` tại thư mục gốc. Giữ máy đang bật theo yêu cầu mới của người dùng.
