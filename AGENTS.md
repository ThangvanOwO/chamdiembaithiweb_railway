# Hướng dẫn cho AI làm việc với GradeFlow

- Trước khi sửa code, đọc `docs/AI_CONTEXT.md` và các quy tắc liên quan trong `.agents/rules/`.
- Giữ nguyên các thay đổi đang có trong working tree; chỉ sửa những tệp thuộc phạm vi yêu cầu.
- Website trên máy này chạy qua Docker Desktop bằng `docker-compose.local.yml`. Sau khi sửa code ảnh hưởng đến website/backend, chạy lệnh sau **tại thư mục gốc dự án** để cập nhật dịch vụ:

  ```powershell
  docker compose -f docker-compose.local.yml up -d --build
  ```

- Sau đó kiểm tra container và chức năng liên quan. Đọc [hướng dẫn Docker](docs/DOCKER_DESKTOP_LOCAL.md) để biết lệnh kiểm tra, dữ liệu và cách khởi động. Không dùng `docker-compose.yml` của môi trường khác thay cho cấu hình local.
- Máy phải bật và đăng nhập Windows để Docker Desktop và website hoạt động. Nếu Docker Engine chưa chạy, khởi động Docker Desktop trước khi chạy lệnh trên.
