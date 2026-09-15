# GradeFlow

> Nền tảng tạo đề và chấm bài trắc nghiệm OMR dành cho giáo viên, trung tâm và nhà trường.

GradeFlow kết hợp **Website quản lý** với **ứng dụng Mobile quét phiếu**. Giáo viên có thể tạo đề từ Excel hoặc phiếu đáp án, chấm phiếu bằng ảnh trên Web, hoặc dùng Live Camera trên điện thoại để nhận diện và xem kết quả nhanh chóng.

![GradeFlow](https://img.shields.io/badge/GradeFlow-OMR%20Grading-0f766e?style=for-the-badge)
![Backend](https://img.shields.io/badge/Backend-Django%20REST-0c4a6e?style=flat-square)
![Mobile](https://img.shields.io/badge/Mobile-Flutter-02569b?style=flat-square)
![Vision](https://img.shields.io/badge/Vision-OpenCV-5c3ee8?style=flat-square)

## Mục tiêu sản phẩm

GradeFlow được xây dựng để giảm thời gian chấm bài thủ công và tăng khả năng kiểm tra lại kết quả:

- Tự động đọc phiếu trả lời trắc nghiệm.
- Hỗ trợ nhiều mã đề trong cùng một kỳ thi.
- Nhận diện SBD, mã đề và đáp án theo cấu trúc phiếu.
- Hiển thị ảnh kết quả có overlay để giáo viên đối chiếu.
- Cảnh báo dữ liệu không chắc chắn thay vì tự đoán đáp án.

## Sản phẩm gồm những gì?

### Website

Website là trung tâm quản lý dành cho giáo viên:

- Đăng ký, đăng nhập và quản lý tài khoản.
- Tạo đề thủ công.
- Tạo đề từ file Excel có nhiều mã đề.
- Tạo đề từ ảnh phiếu đáp án đã tô.
- Upload một hoặc nhiều ảnh phiếu để chấm.
- Xem lịch sử bài chấm và chi tiết từng bài.
- Xem điểm theo từng phần, từng câu và mã đề.
- Xem ảnh overlay để kiểm tra vùng nhận diện.
- Hướng dẫn quy trình tạo đề và chấm bài.

> Live Camera là tính năng dành cho Mobile. Trên Website, người dùng sử dụng upload ảnh và Excel.

### Ứng dụng Mobile

Ứng dụng Flutter dành cho giáo viên chấm bài trên điện thoại:

- Dashboard tổng quan.
- Danh sách đề thi.
- Live Camera nhận diện phiếu.
- Chụp thủ công hoặc chọn ảnh từ thư viện.
- Nhận diện bốn marker góc và nắn phối cảnh.
- Đọc SBD, mã đề và câu trả lời.
- Xem kết quả chấm ngay trên điện thoại.
- Xem cảnh báo nhận diện và bài chấm gần đây.

## Cấu trúc phiếu hiện tại

GradeFlow hỗ trợ mẫu phiếu 54 câu:

| Phần | Nội dung | Số lượng |
|---|---|---:|
| Phần I | Trắc nghiệm A/B/C/D | 40 câu |
| Phần II | Đúng/Sai, bốn ý mỗi câu | 8 câu |
| Phần III | Trả lời ngắn dạng số | 6 câu |

## Quy trình sử dụng

### Tạo đề

```text
Excel hoặc phiếu đáp án
          ↓
Đọc đáp án và các mã đề
          ↓
Giáo viên kiểm tra
          ↓
Lưu đề thi
```

### Chấm bài

```text
Live Camera trên Mobile / Upload ảnh trên Web
          ↓
Phát hiện marker và nắn phối cảnh
          ↓
Đọc SBD và mã đề
          ↓
Đọc các vùng đáp án
          ↓
Đối chiếu đáp án của đúng mã đề
          ↓
Tính điểm và tạo overlay
```

## Các cơ chế kiểm tra quan trọng

### Kiểm tra mã đề chính xác

Hệ thống giữ nguyên số 0 đầu và chỉ sử dụng bảng đáp án khớp chính xác.

- Đề có mã `001`, phiếu có mã `001` → tiếp tục chấm.
- Đề có mã `001`, phiếu có mã `002` → từ chối, không fallback sang mã đầu tiên.
- Mã đề bị mờ, trống hoặc đọc không chắc chắn → yêu cầu quét lại.

### Xử lý tô nhiều đáp án

- Phần I: nhiều lựa chọn trong cùng câu → `X`, không tính điểm câu đó.
- Phần II: cùng một ý vừa tô Đúng vừa tô Sai → `X`, cảnh báo cần kiểm tra.
- Phần III: chữ số hoặc dấu câu không đủ chắc chắn → giữ trạng thái cần kiểm tra, không ghép số đoán mò.

### Màu overlay

- **Xanh:** ô học sinh tô và được xác định là đúng.
- **Đỏ:** ô học sinh tô và được xác định là sai.
- **Vàng:** tô kép hoặc bằng chứng nhận diện chưa chắc chắn.

## Kiến trúc hệ thống

```text
Flutter Mobile
 ├── Live Camera
 ├── Capture / Gallery
 └── Result UI
          │ REST API
          ▼
Django + Django REST Framework
 ├── Authentication
 ├── Exam / Variant management
 ├── Grading API
 ├── Submission history
 └── Web interface
          │
          ▼
OMR Engine
 ├── OpenCV image processing
 ├── Marker / contour detection
 ├── Perspective transform
 ├── Bubble evidence reader
 ├── Answer-key matching
 └── Score calculation and overlay
```

## Công nghệ

| Lớp | Công nghệ |
|---|---|
| Mobile | Flutter, Dart |
| Backend | Python, Django, Django REST Framework |
| Computer Vision | OpenCV, NumPy, xử lý ảnh OMR |
| Database | SQLite cho development, PostgreSQL cho production |
| Web UI | Django Templates, HTML/CSS/JavaScript |
| Authentication | Django authentication và token API |
| Deployment | Railway/Docker/WSGI tùy môi trường |

## Cấu trúc thư mục chính

```text
.
├── api/                         # REST API cho Mobile và client khác
├── accounts/                    # Tài khoản và xác thực
├── chamdiemtudong/              # Django settings, URL và WSGI
├── dashboard/                   # Dashboard Website
├── grading/                     # Nghiệp vụ đề thi và chấm điểm
│   ├── engine/                  # OMR engine và template phiếu
│   ├── grader.py                # Điều phối đọc đáp án và tính điểm
│   └── models.py                # Exam, ExamVariant, Submission
├── gradeflow_app/               # Flutter Mobile App
│   ├── lib/screens/             # Các màn hình ứng dụng
│   ├── lib/services/            # API, camera và grading services
│   └── lib/widgets/             # Thành phần giao diện dùng chung
├── static/                      # CSS, JavaScript và tài nguyên Web
├── templates/                   # Giao diện Django
├── tests/                       # Unit test và fixture kiểm thử
├── tools/                       # Công cụ diagnostics và audit
├── Dockerfile                   # Cấu hình container
├── railway.json                 # Cấu hình Railway
├── requirements.txt             # Python dependencies
└── manage.py                    # Django CLI
```

## Chạy Backend local

### Yêu cầu

- Python 3.10+
- `pip`
- SQLite cho development
- Redis nếu bật Celery hoặc các tác vụ nền

### Cài đặt

```bash
git clone https://github.com/ThangvanOwO/chamdiembaithiweb_railway.git
cd chamdiembaithiweb_railway

python -m venv .venv

# Windows
.venv\\Scripts\\activate

# macOS/Linux
source .venv/bin/activate

pip install -r requirements.txt
python manage.py migrate
python manage.py createsuperuser
python manage.py collectstatic --noinput
python manage.py runserver
```

Mở `http://127.0.0.1:8000` để sử dụng Website.

### Kiểm tra nhanh

```bash
python manage.py check
python -m unittest discover -s tests -p "test_*.py"
```

## REST API chính

| Method | Endpoint | Chức năng |
|---|---|---|
| POST | `/api/v1/auth/login/` | Đăng nhập và nhận token |
| POST | `/api/v1/auth/logout/` | Đăng xuất |
| GET | `/api/v1/auth/me/` | Thông tin tài khoản |
| GET | `/api/v1/dashboard/` | Thống kê tổng quan |
| GET | `/api/v1/exams/` | Danh sách đề thi |
| POST | `/api/v1/grade/` | Chấm ảnh phiếu |
| GET | `/api/v1/submissions/` | Lịch sử bài chấm |

API yêu cầu token theo dạng:

```http
Authorization: Token <token>
```

## Mobile APK

APK nên được phát hành qua GitHub Releases của repository này để người dùng tải đúng phiên bản. Không commit database, file media người dùng, log debug hoặc APK dung lượng lớn trực tiếp vào source nếu không cần thiết.

## Triển khai

Các file triển khai có sẵn trong repository:

- `Dockerfile`
- `railway.json`
- `Procfile`
- `runtime.txt`
- `nginx.conf`

Khi triển khai production cần cấu hình tối thiểu:

```text
DJANGO_SECRET_KEY
DJANGO_DEBUG=False
DATABASE_URL
ALLOWED_HOSTS
CSRF_TRUSTED_ORIGINS
```

## Kiểm thử và chất lượng

Dự án có các nhóm kiểm thử cho:

- Logic chọn đúng mã đề.
- Nhận diện tô kép và cảnh báo màu vàng.
- Bảo toàn hành vi của Upload/import.
- Nhận diện SBD, mã đề và các phần đáp án.
- Kiểm tra ảnh trắng, ảnh lệch và ảnh có điều kiện ánh sáng khác nhau.
- Kiểm tra checkpoint để có thể khôi phục thay đổi an toàn.

Các báo cáo kỹ thuật chi tiết nằm trong thư mục [`docs/`](docs/), bao gồm báo cáo Live validation và hiệu năng.

## Định hướng phát triển

### Ngắn hạn

- Hoàn thiện bộ test có nhãn cho nhiều thiết bị và điều kiện ánh sáng.
- Bổ sung profiler để đo riêng thời gian decode, warp, đọc bubble, ghi ảnh và API.
- Cải thiện thông báo lỗi và hướng dẫn chụp trên Mobile.
- Hoàn thiện xuất Excel/PDF kết quả theo lớp.

### Trung hạn

- Cache marker và ảnh warp giữa các frame Live Camera.
- Tách pipeline preview realtime khỏi pipeline chấm cuối.
- Tối ưu xử lý bằng native OpenCV trên Android.
- Hỗ trợ chấm hàng loạt ổn định hơn.
- Bổ sung phân quyền giáo viên, lớp học và kỳ thi.

### Dài hạn

- Chế độ offline hoặc offline-first trên Mobile.
- Dashboard thống kê chất lượng học tập.
- Đồng bộ nhiều thiết bị.
- Phát hiện chất lượng ảnh trước khi chụp.
- Mở rộng template phiếu và cấu hình mẫu theo từng trường.

## Trạng thái sản phẩm

| Hạng mục | Trạng thái |
|---|---|
| Website quản lý tài khoản và đề thi | Đang sử dụng |
| Tạo đề từ Excel | Đã có |
| Upload ảnh để chấm trên Web | Đã có |
| Flutter Mobile App | Đã có |
| Live Camera trên Mobile | Đã có, tiếp tục tối ưu |
| Nhận diện mã đề nghiêm ngặt | Đã triển khai cho Live |
| Cảnh báo tô kép | Đã triển khai cho Live |
| Offline Mobile | Định hướng |
| Native OpenCV acceleration | Định hướng |

## Đóng góp và phát triển

1. Tạo branch theo tính năng.
2. Viết test cho thay đổi mới.
3. Không commit dữ liệu cá nhân, ảnh học sinh, secret hoặc database production.
4. Mô tả rõ ảnh hưởng đến Live Camera và Upload/import.
5. Tạo Pull Request kèm kết quả kiểm thử.

## Giấy phép

Dự án được phát triển cho mục đích giáo dục và thử nghiệm sản phẩm. Chính sách cấp phép chính thức sẽ được bổ sung khi dự án công bố rộng rãi.

## Nhóm phát triển

| Thành viên | Vai trò |
|---|---|
| V. Thắng | Backend, OMR Engine, REST API và hệ thống dữ liệu |
| B. Việt | Web UI, Flutter Mobile và UX |

---

**GradeFlow — biến quy trình chấm phiếu thủ công thành một quy trình số hóa, minh bạch và có thể kiểm tra lại.**
