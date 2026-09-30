# GradeFlow: bản vá bảo mật 26/09/2026

## Phạm vi và hành vi

- API ChamTN cũ yêu cầu session đăng nhập, CSRF cho thao tác ghi và kiểm tra chủ sở hữu theo từng đề/bài làm. Không còn lấy người dùng đầu tiên hoặc toàn bộ dữ liệu khi chưa đăng nhập.
- `/media/` được Django kiểm tra quyền trước khi trả ảnh gốc, ảnh dẫn xuất, ảnh training và avatar. Chủ sở hữu hoặc superuser được đọc; file chưa gắn với bản ghi bị từ chối. Nginx local không còn phục vụ trực tiếp thư mục media. Ảnh trả `private, no-store`.
- Flutter nhận thêm `image_url` trong chi tiết bài chấm và gửi token khi tải ảnh. APK đã cài cần bản build mới để sử dụng đường dẫn ảnh đúng; đăng nhập và chấm điểm giữ nguyên API.
- Chỉ superuser được sửa tài khoản, đặt lại mật khẩu qua admin và sửa nhóm quyền. Nhân viên được phân quyền điều chỉnh tín dụng vẫn làm việc qua sổ giao dịch.
- Đăng nhập không còn bỏ qua kết quả từ authentication backend. Không ghi email và kết quả kiểm tra mật khẩu vào log tùy chỉnh.
- Production bắt buộc có `DJANGO_SECRET_KEY`, tự chuyển HTTP sang HTTPS và gửi HSTS 1 giờ (không áp dụng subdomain/preload). Chỉ `ads.txt` được miễn chuyển hướng để healthcheck Docker nội bộ hoạt động.

## Đăng ký và cấu hình còn thiếu

Tài khoản hiện có không bị thay đổi. Đăng ký email mới **đóng khi chưa đủ SMTP và Turnstile**. Đăng ký Google yêu cầu email đã xác minh từ Google; không tự tin vào email do trình duyệt gửi.

Để mở đăng ký email, cấu hình riêng trong `.env.docker.local` (không commit hoặc gửi khóa vào chat):

```dotenv
EMAIL_HOST=smtp.example.com
EMAIL_PORT=587
EMAIL_HOST_USER=your-smtp-user
EMAIL_HOST_PASSWORD=your-smtp-password
EMAIL_USE_TLS=true
DEFAULT_FROM_EMAIL=GradeFlow <your-verified-sender@example.com>
TURNSTILE_SITE_KEY=your-public-site-key
TURNSTILE_SECRET_KEY=your-private-secret-key
TURNSTILE_HOSTNAMES=gradeflow.io.vn
PUBLIC_SITE_URL=https://gradeflow.io.vn
```

Tạo widget Turnstile cho hostname trên. Backend gọi Siteverify và kiểm tra `success`, hostname và `action=signup`; lỗi mạng hoặc token sai bị từ chối. Không dùng khóa thử nghiệm trong production.

Sau CAPTCHA, server lưu yêu cầu chờ với mật khẩu đã băm và gửi liên kết có hạn 1 giờ. GET chỉ hiển thị trang; người đăng ký phải nhập lại mật khẩu và POST xác nhận. Lúc đó mới tạo tài khoản và cấp 100 điểm một lần. Link đã dùng/hết hạn không tạo thêm tài khoản. `/accounts/signup/` mặc định của allauth bị đóng để không đi vòng. Tài khoản chờ không thể đăng nhập/chấm bài.

API đăng ký trả `202` với `requires_email_verification` và `message`, không trả token khi chưa xác minh. Client cũ sẽ không tự đăng nhập. Hiện Flutter chưa có widget Turnstile; dùng đăng ký trên website rồi đăng nhập trong app bằng email/mật khẩu đã xác minh. Không bỏ xác minh phía server để hỗ trợ client cũ.

## Giới hạn xác thực

Lưu bucket băm trong database, cập nhật nguyên tử và dùng chung giữa worker/restart:

- Đăng nhập: 30 yêu cầu/IP/10 phút, thêm 12 yêu cầu/tên đăng nhập hoặc email/10 phút; tính cả lượt thành công.
- Đăng ký: 5 yêu cầu/IP/giờ, bao gồm Google tạo tài khoản mới.
- Quên mật khẩu: 5 yêu cầu/IP/giờ.
- Xác nhận đăng ký/đặt mật khẩu: 15 yêu cầu/IP/10 phút.

Đây là cửa sổ cố định; đạt giới hạn trả 429 và `Retry-After`. Lỗi lưu bộ đếm trả 503. Bucket hết hạn được dọn khi tạo bucket mới. Không phải giải pháp chống mọi bot phân tán/DDoS; cần theo dõi thêm Cloudflare và giới hạn tài nguyên khi mở rộng tải.

`TRUST_PROXY_CLIENT_IP=1` chỉ dùng với cấu hình local: cổng proxy chỉ mở `127.0.0.1:8000`, Cloudflare Tunnel là cổng vào Internet. Nginx ghi đè `X-GradeFlow-Client-IP` bằng `CF-Connecting-IP` (hoặc địa chỉ peer nếu thiếu). Không mở cổng proxy/web ra Internet với cấu hình này. CORS mặc định đóng; ứng dụng Android native không cần CORS. Nếu có Flutter Web riêng, khai báo chính xác `CORS_ALLOWED_ORIGINS`.

## Triển khai và kiểm tra

```powershell
python manage.py test accounts website --noinput
docker compose -f docker-compose.local.yml up -d --build
docker compose -f docker-compose.local.yml ps
```

Migration 0004 chỉ thêm hai bảng bảo mật, không sửa tài khoản/ví/bài thi hiện có. Sao lưu SQLite bằng API backup trước triển khai. Không chạy các script tích hợp cũ có thể ghi trực tiếp vào database thật.

Kiểm tra sau triển khai: khách không có session/token bị 401 ở API riêng tư và media; trang chủ, robots, sitemap, ads.txt vẫn công khai. Nếu trước đây CDN từng cache ảnh riêng tư, cần purge cache Cloudflare; header mới chỉ có tác dụng khi CDN lấy lại từ origin. Không thể thu hồi ảnh đã được người khác tải trước bản vá.

## Giới hạn kết luận

Đây là bản vá các lỗi đã tìm thấy, không phải chứng nhận an toàn tuyệt đối hoặc kiểm thử xâm nhập đầy đủ. Chưa kết luận dữ liệu từng bị truy cập trái phép hay chưa; cần phân tích log riêng. Cần hoàn tất cấu hình SMTP/Turnstile thật và kiểm tra gửi mail/challenge thật trước khi mở đăng ký email.

## Kết quả triển khai ngày 26/09/2026

- `python manage.py test accounts website --noinput`: 87 bài đạt ở lần chạy đầu; sau đó thêm kiểm thử đồng thời (1 bài đạt) và chạy lại nhóm xác thực/HTTPS (6 bài đạt).
- Chạy toàn bộ trong image Docker cuối cùng: 89 bài, 84 đạt, 5 bỏ qua vì image không có Node.js. Năm bài service-worker đó đã chạy đạt trên máy Windows trong lần chạy đầu.
- Docker web healthy, proxy đang chạy; Nginx kiểm tra cấu hình thành công. Đã rebuild đúng compose local.
- Kiểm tra Internet: HTTP trang login chuyển 301 sang HTTPS; HTTPS login, ads.txt và sitemap trả 200; API `/api/exams` không đăng nhập trả 401.
- Sau khi chủ website xác nhận Purge Everything, kiểm tra 3 ảnh đang tồn tại qua Internet: tất cả trả 401, `CF-Cache-Status: BYPASS`, `Cache-Control: private, no-store, max-age=0`. Trước purge, một ảnh còn trả 200/HIT từ cache cũ.
- So sánh trước/sau migration: tổng số tài khoản, ví, giao dịch tín dụng, đề thi, bài nộp và tổng số dư không thay đổi. Backup nhất quán ở `scratch/security_before_20260926/before_deploy.sqlite3`.
- `check --deploy` còn hai cảnh báo do chủ động chưa bật HSTS cho mọi subdomain và preload; không giả định tất cả subdomain đều dùng HTTPS. Không có lỗi check thường hoặc migration thiếu.
- Không có Flutter/Dart trong PATH để build/analyze APK ở phiên này. Mã client đã cập nhật xử lý thông báo chờ xác minh và URL ảnh có xác thực; chưa phát hành APK mới. SMTP và Turnstile thật chưa được cấu hình, các kiểm thử dùng nhà cung cấp giả lập trong database test riêng.
- `git diff --check` toàn repository phát hiện hai dòng khoảng trắng có sẵn ở `grading/engine/hi.py`; không sửa thuật toán hoặc thay đổi sẵn có ngoài phạm vi.
