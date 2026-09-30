# Tăng tốc Live trên VPS 2 vCPU

Ngày kiểm thử: 01/10/2026. Mục tiêu là giảm công CPU trước khi tăng cấu hình VPS.

## Thay đổi

- `LIVE_CPU_FAST=1`: chỉ áp dụng khi `fast_mode`, `live_bubble_mode` và
  `live_validation` đều bật, với góc từ camera hoặc ảnh đã nắn. Upload và đường
  chưa có xác thực Live vẫn dùng thuật toán cũ.
- Live đã đọc mã đề/SBD/P1/P2/P3 từ ảnh gốc đã nắn. Bỏ NLM, Gaussian nền và
  lượt đọc legacy bị ghi đè; giữ nguyên reader, ngưỡng, kích thước và chấm điểm.
- Ước lượng offset P3 trên ảnh xám gốc. Nếu một khung P3 không căn được, chạy
  lại đường tiền xử lý cũ đúng một lần trước khi chọn mã đề/chấm điểm.
  P1/P2/SBD/mã đề vốn dùng offset cố định hoặc không dùng offset, nên tiền xử lý
  cũ không cải thiện các khung này. Cảnh báo và xử lý ô mờ/tô nhiều ô vẫn giữ.
- Khóa RLock trong mỗi worker bảo vệ template globals và stdout capture khi
  nhiều request cùng quét; tránh tranh hai lõi CPU và trộn template. Giữ
  Gunicorn một worker/hai thread. Khóa không thay thế giới hạn tải toàn cụm.
- `LIVE_RESULT_JPEG_QUALITY=90` giảm dung lượng ảnh kết quả/overlay. Chỉ đổi
  ảnh hiển thị; ảnh đầu vào và pixel dùng nhận diện giữ nguyên. Có thể đặt 95.

## Kiểm thử trước triển khai

Đo trên container độc lập từ image production, cùng VPS Lightsail 2 vCPU,
OpenCV hai luồng; không gọi API thanh toán, không ghi dữ liệu người dùng.

| Phép đo | Bản cũ | Bản mới |
|---|---:|---:|
| Engine: 10 ảnh, bản mới chạy 3 lượt/ảnh | trung bình 9,576 s | trung bình 0,480 s |
| Engine: thời gian cao nhất trong 30 lượt mới | — | 0,587 s |
| Engine: CPU time trung bình (cộng thời gian các lõi) | 18,047 s | 0,546 s |
| 8 biến đổi tối/chì nhạt/bóng/mờ nhẹ từ 2 ảnh | trung bình 9,456 s | trung bình 0,451 s |
| API thật, cô lập ORM/billing: 4 ảnh, 3 lượt/ảnh | trung bình 9,691 s | trung bình 0,567 s |
| API: thời gian cao nhất trong 12 lượt mới | — | 0,884 s |
| API: phản hồi JSON gồm 3 ảnh base64 | trung bình 2.067 MB | trung bình 1.511 MB |

Tất cả lượt đối chiếu khớp SBD, mã đề, P1/P2/P3, điểm, confidence, chất lượng
và cảnh báo. API đối chiếu thêm điểm có trọng số. Bảng đáp án là khóa tổng hợp
để kiểm tra chấm điểm, không phải đáp án giáo viên. Các ảnh có nguồn trùng nhau
không được coi là các mẫu độc lập; biến đổi ánh sáng cũng chỉ là stress test.
Đã kiểm tra riêng các nhãn camera sửa P3, ô trống và tô nhiều ô bằng bộ test.
CPU time giảm khoảng 97% trong bộ đo; đây không phải % CPU tức thời của cả VPS.

45 kiểm thử OMR/latency/khóa/CLI đạt (8 mới, 18 latency, 13 validation,
6 P3 shadow). Trong Docker, 76 kiểm thử tài khoản/billing/phân quyền đạt;
8 kiểm thử mới đạt và `manage.py check` không có lỗi. Bộ test tài khoản dùng
`docker compose -f docker-compose.local.yml exec -T -e DJANGO_DEBUG=True web
python manage.py test accounts`; biến chỉ áp dụng tiến trình test để HTTP
test client không bị chuyển 301 sang HTTPS. Cấu hình dịch vụ vẫn giữ nguyên.

Số trên không bao gồm chụp/chuẩn bị ảnh, upload/download, HTTP qua Cloudflare
hoặc độ trễ DB thật. Không phải cam kết p95 sản phẩm hay độ chính xác cho mọi
máy/mẫu phiếu. Phiếu cần quay lui có thể mất thời gian như bản cũ. Khi nhiều
người quét, thời gian chờ khóa tăng theo tải; ưu tiên độ chính xác.

Kết quả đầy đủ trên máy anh ở `tests/test_ketqua/vps_cpu_20261001/` gồm
`optimized_report.json`, `stress_report.json`, `api_report.json`.

## Đo lại

Manifest JSON gồm `name`, `image`, `corners`, hoặc `pre_warped: true`.
Tên ảnh tính tương đối từ thư mục manifest. Thư mục kết quả phải chưa tồn tại.

```bash
python tools/diagnostics/benchmark_live_cpu.py --manifest manifest.json --output new-engine-result --rounds 3 --threads 2
python tools/diagnostics/benchmark_live_api.py --manifest manifest.json --output new-api-result --rounds 3
```

Script API cô lập quyền sở hữu/billing bằng mock để không sửa DB. Nó dùng
reader, grader, API view, tính điểm có trọng số, ảnh và JSON renderer thật.
Chỉ dùng trong tiến trình benchmark; không áp dụng mock vào web đang chạy.

## Bật và quay lui

Trong `.env.vps` (không commit):

```dotenv
LIVE_CPU_FAST=1
LIVE_RESULT_JPEG_QUALITY=90
```

Tại `/home/ubuntu/gradeflow`:

```bash
docker compose --env-file .env.vps -f docker-compose.vps.yml up -d --build
docker compose --env-file .env.vps -f docker-compose.vps.yml ps
```

Muốn khôi phục đường tiền xử lý cũ: sửa `LIVE_CPU_FAST=0`, rồi:

```bash
docker compose --env-file .env.vps -f docker-compose.vps.yml up -d --force-recreate web
```

Trên Windows vẫn dùng `docker compose -f docker-compose.local.yml up -d --build`
tại thư mục dự án. Cờ tương tự đặt trong `.env.docker.local`.

## BUG FIX REPORT

- **ROOT CAUSE**: NLM/Gaussian và reader legacy chạy trước reader raw Live,
  rồi các đáp án bị ghi đè. Chỉ offset P3 cần có đường lui khi local fit lỗi.
- **FILES CHANGED**: `grading/engine/hi.py`, `grading/engine/live_cpu.py`,
  `grading/cpu_runtime.py`, `grading/grader.py`, `.env.vps.example`,
  `.gitignore`, `tests/test_live_cpu.py`, hai script benchmark trong
  `tools/diagnostics/` và tài liệu này.
- **CHANGES MADE**: Bỏ công dư ở validated Live; fallback P3; tuần tự hóa
  engine trong worker; nén ảnh hiển thị; giữ tương thích CLI và API.
- **TESTS RUN**: `unittest discover` cho `test_live_cpu.py`,
  `test_live_latency.py`, `test_live_validation.py`, `test_part3_shadow.py`;
  Django `test accounts`; `manage.py check`; hai benchmark ở trên.
- **TEST RESULTS**: 121 kiểm thử đạt (không đếm lượt chạy lặp); 30 lượt engine,
  8 stress và 12 lượt API mới không có khác biệt trong các trường đối chiếu.
- **REGRESSION RISK**: Bộ ảnh hữu hạn; local fit có thể lỗi trên mẫu/ánh sáng
  khác và quay về đường cũ. Upload không áp dụng thay đổi thuật toán này.
- **UNRELATED ISSUES FOUND**: HTTP test client bị redirect khi chạy với cấu
  hình production; xử lý bằng môi trường riêng cho test. Chưa tối ưu upload
  legacy hoặc thay kiến trúc lưu phản hồi idempotency có base64 trong DB.
