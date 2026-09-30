# GradeFlow trên Docker Desktop của máy này

GradeFlow chạy bằng `docker-compose.local.yml`. Docker Desktop được thêm vào khóa `HKCU\Software\Microsoft\Windows\CurrentVersion\Run` của tài khoản Windows hiện tại. Khi anh **đăng nhập Windows**, Docker Desktop mở, rồi các container `restart: unless-stopped` sẽ tự chạy lại. Cloudflared vẫn chạy dưới dịch vụ Windows `Automatic` và chuyển `gradeflow.io.vn` tới `127.0.0.1:8000`.

## Dữ liệu hiện có

- `db.sqlite3` của dự án được gắn trực tiếp vào container; không tạo PostgreSQL mới và không đổi tài khoản/điểm tín dụng.
- `media/` chỉ được gắn vào web. Django kiểm tra chủ sở hữu hoặc superuser trước khi trả ảnh; proxy không được đọc trực tiếp thư mục này.
- Cổng 8000 chỉ nghe trên `127.0.0.1` của máy, không mở trực tiếp ra mạng LAN hoặc Internet. Truy cập công khai vẫn đi qua Cloudflare Tunnel.
- Secret key riêng của Docker ở `.env.docker.local` (đã được `.gitignore` bỏ qua). Lần chuyển từ Django chạy trực tiếp sang Docker có thể cần đăng nhập lại vì session cũ dùng secret key khác.
- Bản vá bảo mật, giới hạn xác thực và cấu hình SMTP/Turnstile: [SECURITY_HARDENING.md](SECURITY_HARDENING.md). Khi chưa cấu hình đủ, đăng ký email mới tạm đóng; tài khoản có sẵn vẫn đăng nhập được.
- Bản sao SQLite trước khi chuyển nằm trong `scratch/docker_local_backup/`. **Không dùng đồng thời** `python manage.py runserver` và container trên cùng cổng/cơ sở dữ liệu.

## Quản lý

Chạy trong PowerShell tại thư mục dự án:

```powershell
docker compose -f docker-compose.local.yml ps
docker compose -f docker-compose.local.yml logs --tail 80 web proxy
```

Sau khi sửa code, cập nhật image:

```powershell
docker compose -f docker-compose.local.yml up -d --build
```

Nếu đã dừng thủ công và muốn chạy lại:

```powershell
docker compose -f docker-compose.local.yml up -d
```

`restart: unless-stopped` nghĩa là container được tự chạy sau khi Docker Engine khởi động lại, **trừ khi anh đã dừng container thủ công**. Máy tính phải được bật, vào tài khoản Windows và có mạng thì website mới hoạt động.

Không chạy `docker compose down -v` vì lệnh này xóa volume của các Compose khác nếu chỉ nhầm file; cấu hình local này dùng bind mount để bảo toàn SQLite và media trên máy.

## Đã xác minh lúc triển khai

- `docker compose ps`: web khỏe, proxy đang chạy và chỉ xuất cổng `127.0.0.1:8000`.
- `python manage.py check` bên trong container: không có lỗi; 4 kiểm thử avatar đạt.
- SQLite từ container: 6 tài khoản và 6 ví tín dụng, bằng dữ liệu hiện có.
- `http://127.0.0.1:8000/`, `/ads.txt`, CSS; `https://gradeflow.io.vn/`, trang đăng nhập và CSS đều trả HTTP 200.
- Tệp `.env.docker.local` được bỏ qua bởi Git và Docker build; đã xác minh không có trong image.
- Khóa Windows Run trỏ đến bản Docker Desktop đang cài; Cloudflared ở trạng thái `Running`, `Automatic`.
