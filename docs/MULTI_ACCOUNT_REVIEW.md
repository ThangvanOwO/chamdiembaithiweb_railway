# Multi-account: phát hiện và kiểm tra thủ công

Mở `/admin/security/` bằng tài khoản superuser, hoặc Admin → Mở bảng điều khiển.

## Tín hiệu và giới hạn
- Cùng IP đã quan sát trong 30 ngày: +20.
- Ngày tạo hai tài khoản cách nhau không quá 60 phút: +20.
- Đáp án trùng (ít nhất 10 giá trị câu trả lời, trong đề tạo 30 ngày gần đây): +30.
- Hai đề trùng đáp án tạo cách nhau không quá 10 phút: +30.
- Dưới 40: theo dõi; 40–79: nghi vấn; từ 80: cao. Điểm là quy tắc ưu tiên kiểm tra, KHÔNG phải xác suất gian lận.
- Không tự động khóa hoặc trừ điểm. Giáo viên cùng trường có thể có các dấu hiệu này hợp lệ.
- JSON chỉ so sánh p1/p2/p3; CSV chuẩn hóa khoảng trắng và chữ hoa. Không so khớp ngữ nghĩa giữa hai định dạng khác nhau. Không lấy cấu hình mẫu phiếu làm đáp án.
- Ghi nhận từ request thành công của người đã xác thực và lần tạo tài khoản; hỗ trợ web, Google callback, API token. Chưa có dữ liệu IP cũ thì không suy đoán.
- IP dùng HMAC với secret máy chủ, không lưu địa chỉ thô. Dữ liệu mạng hết 30 ngày được dọn khi có quan sát mới. Đổi secret làm mất liên kết IP cũ. Hồ sơ kiểm tra và lịch sử xử lý được giữ để đối chiếu.
- Không phát hiện chắc chắn một người đổi mạng/VPN và đổi đáp án. Tài khoản staff không đưa vào hệ thống so khớp này.
- Dữ liệu được cập nhật khi người dùng hoạt động (quan sát mạng tối đa mỗi 15 phút hoặc request ghi dữ liệu), không phải tác vụ nền. Nếu DB lỗi khi ghi tín hiệu, log lỗi và không chặn hoạt động hợp lệ.

## Xử lý
Superuser đọc bằng chứng, chọn tài khoản và thao tác, nhập lý do, đánh dấu xác nhận.
- Thu hồi bonus: phân bổ chi tiêu vào bonus chào mừng trước, hoàn phần bonus khi quét thất bại. Chỉ thu hồi phần còn lại tối đa 100; điểm mua/cộng thêm không biến thành bonus. Từ chối khi có lượt quét còn giữ điểm. Chặn thu hồi lần hai bằng mã sổ cái duy nhất, kể cả gửi thao tác với UUID mới. Đồng thời khóa bonus.
- Khóa bonus: chặn callback thưởng ở backend; không ngăn cộng điểm mua đã xác minh.
- Khóa tài khoản: is_active=False, xóa token API. Session hiện có không còn xác thực theo backend chuẩn. Có thao tác mở lại.
- Mở bonus không cấp lại 100 điểm. Nếu thu hồi nhầm, superuser có thể bù điểm có lý do qua Ví tín dụng.
- Cập nhật ví và audit trong cùng transaction, có retry SQLite. Các thao tác lặp cùng UUID không trừ lặp. Không cho xử lý chính admin hoặc tài khoản staff bằng công cụ này.
- Đánh giá hồ sơ (theo dõi / loại nghi vấn / xác nhận) không tự áp dụng hình phạt. Tín hiệu mới không ghi đè quyết định của admin.

Biểu đồ 14 ngày, tổng số dư, số tài khoản khóa, bảng nghi vấn có lọc và phân trang đều lấy dữ liệu thật. Không dùng dữ liệu mẫu trong production.

Kiểm thử: `python manage.py test accounts.test_risk accounts.test_security accounts.test_credits accounts.tests --noinput`.
Triển khai theo `docs/DOCKER_DESKTOP_LOCAL.md`; migration 0005 bổ sung bảng/field, không thay đổi số dư hoặc khóa người dùng cũ.

## Kết quả triển khai 26/09/2026
- 69 kiểm thử tài khoản / tín dụng / phân quyền đạt trên Windows và container. Trong test runner container tắt HTTPS redirect cho request test HTTP; cấu hình production không đổi.
- 14 kiểm thử riêng multi-account đạt, gồm 3 ca bổ sung: đăng nhập API ghi nhận mạng, form xử lý bắt buộc xác nhận / đúng cặp tài khoản, hai thao tác thu hồi đồng thời chỉ có một giao dịch.
- Playwright trên Edge headless dựng giao diện bằng SQLite bộ nhớ (dữ liệu minh họa), kiểm tra desktop 1440px và mobile 390px, không tràn chiều ngang; ảnh trong scratch/risk-*.png.
- Docker local build/recreate thành công; web healthy, proxy chạy. URL công khai yêu cầu đăng nhập; CSS HTTP200. Request urllib mặc định bị Cloudflare403, dùng User-Agent trình duyệt xác minh HTTP200 trang login.
- Sao lưu trước triển khai: scratch/risk_before_deploy.sqlite3. Trước/sau đều 6 ví, tổng 599 điểm, không phát sinh thao tác xử lý tài khoản thật.
