# GradeFlow — Hệ thống chấm điểm trắc nghiệm tự động

> Hệ thống chấm điểm trắc nghiệm tự động bằng công nghệ nhận dạng ảnh (OMR — Optical Mark Recognition) — hỗ trợ cả **Web** và **Mobile App**.

---

## Mục lục

- [Tổng quan](#tổng-quan)
- [Tính năng](#tính-năng)
- [Công nghệ sử dụng](#công-nghệ-sử-dụng)
- [Cấu trúc dự án](#cấu-trúc-dự-án)
- [Cài đặt](#cài-đặt)
- [Chạy ứng dụng](#chạy-ứng-dụng)
- [Hướng dẫn sử dụng](#hướng-dẫn-sử-dụng)
- [Ứng dụng Mobile (Flutter)](#ứng-dụng-mobile-flutter)
- [REST API](#rest-api)
- [Cấu hình nâng cao](#cấu-hình-nâng-cao)
- [Nhóm phát triển](#nhóm-phát-triển)

---

## Tổng quan

**GradeFlow** là nền tảng chấm điểm trắc nghiệm dành cho giáo viên, hỗ trợ:

- **3 loại câu hỏi**: Trắc nghiệm ABCD (Phần I), Đúng/Sai (Phần II), Điền số (Phần III)
- **Nhận dạng phiếu trả lời** từ ảnh chụp hoặc scan
- **Nhiều mã đề** trong cùng một kỳ thi
- **Tính điểm tự động** theo thang điểm tùy chỉnh

---

## Tính năng

### Quản lý đề thi
- Tạo đề thi thủ công với giao diện trực quan (sidebar cấu hình + nhập đáp án)
- Import đáp án từ file Excel (.xlsx) — hỗ trợ nhiều mã đề
- Chọn mẫu phiếu trả lời phù hợp với cấu trúc đề

### Chấm điểm tự động
- Upload ảnh phiếu thi (kéo thả hoặc chọn file)
- Chụp trực tiếp từ camera (webcam trên desktop, camera native trên mobile)
- Chế độ chụp liên tục — chụp nhiều phiếu liên tiếp không cần thao tác lại
- Nhận dạng: SBD, mã đề, đáp án 3 phần
- Tự động khớp mã đề → so sánh đáp án → tính điểm

### Xem kết quả
- Bảng kết quả theo từng kỳ thi
- Chi tiết từng bài: so sánh đáp án học sinh vs đáp án đúng
- Ảnh gốc có đánh dấu đúng/sai trực tiếp
- Hỗ trợ chấm lại nếu cần

### Giao diện
- Thiết kế hiện đại với design system riêng (Manrope + DM Sans)
- Hỗ trợ Dark mode
- Responsive — dùng được trên điện thoại và máy tính
- Step indicator trực quan cho quy trình import/tạo đề

---

## Công nghệ sử dụng

| Thành phần | Công nghệ |
|---|---|
| **Backend** | Django 5.2 (Python) |
| **Database** | SQLite (dev) / PostgreSQL (production) |
| **Web Frontend** | Alpine.js, HTMX, CSS thuần (design system) |
| **Mobile App** | Flutter (Dart) — Android & iOS |
| **OMR Engine** | OpenCV + CNN (nhận dạng bubble) |
| **REST API** | Django REST Framework + Token Auth |
| **Document Scanner** | Google ML Kit Document Scanner |
| **Task Queue** | Celery + Redis (chấm điểm bất đồng bộ) |
| **Auth** | django-allauth (web) / DRF Token (mobile) |
| **Hosting** | Railway |
| **Static files** | WhiteNoise |

---

## Cấu trúc dự án

```
chamdiembaithiweb/
├── accounts/            # Xác thực người dùng (đăng nhập, đăng ký)
├── chamdiemtudong/      # Cấu hình Django (settings, urls, wsgi)
├── dashboard/           # Trang tổng quan (thống kê, lịch sử)
├── grading/             # Module chấm điểm chính
│   ├── engine/          # OMR engine (nhận dạng ảnh, xử lý bubble)
│   │   └── hi.py        # Core: extract_part1/2/3, grade, draw results
│   ├── grader.py        # Wrapper: parse answer key, compute score
│   ├── models.py        # Models: Exam, ExamVariant, Submission
│   ├── views.py         # Views: upload, import, results, detail
│   └── urls.py          # URL routing
├── static/
│   ├── css/             # Design system (components, layout, animations)
│   └── img/             # Logo, template previews
├── templates/
│   ├── base.html        # Layout chung
│   ├── dashboard/       # Templates trang chủ
│   └── grading/         # Templates chấm điểm
├── api/                 # REST API cho mobile app (DRF)
│   ├── views.py         # API views: login, grade, exams, submissions
│   └── urls.py          # API endpoints (/api/v1/...)
├── gradeflow_app/       # Flutter mobile app
│   ├── lib/
│   │   ├── screens/     # 7 màn hình: Login, Dashboard, Scan, ...
│   │   ├── services/    # API service, Auth service
│   │   ├── models/      # Exam, Submission, GradeResult
│   │   └── config/      # Theme, API config
│   ├── android/         # Android platform config
│   └── ios/             # iOS platform config
├── media/               # Ảnh upload (gitignored)
├── requirements.txt     # Danh sách thư viện
└── manage.py            # Django CLI
```

---

## Cài đặt

### Yêu cầu

- **Python** 3.10+
- **pip** (trình quản lý gói Python)
- **Redis** (nếu dùng Celery cho chấm điểm bất đồng bộ)

### Bước 1: Clone dự án

```bash
git clone https://github.com/Haxodraschool/chamdiembaithiweb.git
cd chamdiembaithiweb
```

### Bước 2: Tạo môi trường ảo

```bash
python -m venv venv

# Windows
venv\Scripts\activate

# Linux/Mac
source venv/bin/activate
```

### Bước 3: Cài thư viện

```bash
pip install -r requirements.txt
```

### Bước 4: Tạo database

```bash
python manage.py migrate
```

### Bước 5: Tạo tài khoản admin

```bash
python manage.py createsuperuser
```

### Bước 6: Thu thập file tĩnh

```bash
python manage.py collectstatic
```

---

## Chạy ứng dụng

### Chế độ phát triển (development)

```bash
python manage.py runserver
```

Truy cập: [http://127.0.0.1:8000](http://127.0.0.1:8000)

### Với Celery (xử lý bất đồng bộ)

Mở thêm 1 terminal:

```bash
celery -A chamdiemtudong worker --loglevel=info
```

> **Lưu ý**: Cần có Redis đang chạy. Nếu không dùng Celery, ứng dụng vẫn hoạt động — chấm điểm sẽ chạy đồng bộ.

---

## Hướng dẫn sử dụng

### 1. Tạo đề thi

**Cách 1 — Nhập thủ công:**
1. Vào **Chấm bài mới** → **Tạo đề thủ công**
2. Đặt tên đề, chọn môn học
3. Kéo slider để chọn số câu Phần I, II, III
4. Nhập đáp án cho từng câu
5. Chọn mẫu phiếu trả lời phù hợp
6. Bấm **Lưu đề thi**

**Cách 2 — Import từ Excel:**
1. Vào **Chấm bài mới** → **Import đáp án Excel**
2. Tải file .xlsx lên (hỗ trợ nhiều mã đề)
3. Xác nhận đáp án hiển thị đúng
4. Chọn mẫu phiếu → Lưu

### 2. Chấm điểm

1. Chọn đề thi đã tạo
2. Upload ảnh phiếu thi bằng 1 trong 3 cách:
   - **Kéo thả** file ảnh vào vùng upload
   - **Bấm chọn** file từ máy tính
   - **Chụp camera** — trên desktop mở webcam, trên mobile mở camera native
3. Hệ thống tự động:
   - Nhận dạng SBD, mã đề
   - Khớp mã đề với đáp án đúng
   - So sánh và tính điểm
4. Xem kết quả ngay sau khi chấm

### 3. Xem kết quả chi tiết

- Bấm vào tên học sinh để xem:
  - Đáp án học sinh vs đáp án đúng (từng câu)
  - Ảnh gốc có đánh dấu đúng ✅ / sai ❌
  - Điểm từng phần và tổng điểm
- Bấm **Chấm lại** nếu muốn chấm lại bài

### 4. Mẹo chụp ảnh phiếu thi

- Đảm bảo **đủ ánh sáng**, tránh bóng đổ
- Phiếu phải **phẳng**, không cong nhăn
- Camera **vuông góc** với mặt phiếu
- Thấy đủ **4 góc** phiếu trong khung hình
- Nền tối giúp nhận dạng góc phiếu tốt hơn

---

## Ứng dụng Mobile (Flutter)

### Tải APK

Tải file APK mới nhất tại [**GitHub Releases**](https://github.com/Haxodraschool/chamdiembaithiweb/releases).

### Tính năng mobile

- **Google ML Kit Document Scanner** — tự động crop, nắn phẳng, tăng cường ảnh phiếu thi
- **Chụp camera / chọn từ thư viện** — fallback khi scanner không khả dụng
- **Chấm điểm tức thì** — gửi ảnh lên server, nhận kết quả trong vài giây
- **Dashboard** — xem thống kê, lịch sử chấm bài
- **Quản lý đề thi** — xem danh sách đề, chọn đề để chấm

### Cài đặt trên Android

1. Tải file `GradeFlow.apk` từ Releases
2. Mở file → cho phép "Cài từ nguồn không xác định"
3. Cài đặt → mở app **GradeFlow**
4. Đăng nhập bằng tài khoản đã đăng ký trên web

### Trạng thái phát triển

| Tính năng | Trạng thái |
|---|---|
| Đăng nhập / Đăng xuất | ✅ Hoàn thành |
| Dashboard thống kê | ✅ Hoàn thành |
| Danh sách đề thi | ✅ Hoàn thành |
| Quét phiếu (Document Scanner) | ✅ Hoàn thành |
| Chấm điểm + xem kết quả | ✅ Hoàn thành |
| Lịch sử chấm bài | ✅ Hoàn thành |
| Hồ sơ người dùng | ✅ Hoàn thành |
| Tạo đề thi trên mobile | 🔜 Đang phát triển |
| Chế độ offline | 🔜 Đang phát triển |
| Thông báo đẩy (Push) | 🔜 Đang phát triển |

---

## REST API

Mobile app giao tiếp với server qua REST API:

| Method | Endpoint | Mô tả |
|---|---|---|
| POST | `/api/v1/auth/login/` | Đăng nhập, nhận token |
| POST | `/api/v1/auth/logout/` | Đăng xuất |
| GET | `/api/v1/auth/me/` | Thông tin người dùng |
| GET | `/api/v1/dashboard/` | Thống kê tổng quan |
| GET | `/api/v1/exams/` | Danh sách đề thi |
| POST | `/api/v1/grade/` | Chấm điểm ảnh (multipart) |
| GET | `/api/v1/submissions/` | Lịch sử bài chấm |

Xác thực: `Authorization: Token <token>`

---

## Cấu hình nâng cao

### Biến môi trường

| Biến | Mô tả | Mặc định |
|---|---|---|
| `DJANGO_SECRET_KEY` | Khóa bí mật Django | (có sẵn cho dev) |
| `DJANGO_DEBUG` | Chế độ debug | `True` |
| `DATABASE_URL` | Chuỗi kết nối database | SQLite |
| `CELERY_BROKER_URL` | URL Redis cho Celery | `redis://localhost:6379/0` |

### Thang điểm

Hệ thống hỗ trợ cấu hình thang điểm linh hoạt:

- **Phần I**: Điểm mỗi câu (mặc định 0.25đ)
- **Phần II**: Theo quy tắc MOET (đúng 4/4 = 1đ, 3/4 = 0.25đ)
- **Phần III**: Điểm mỗi câu (mặc định 0.5đ)
- Quy về **thang 10** với hệ số tùy chỉnh

---

## Giấy phép

Dự án được phát triển phục vụ mục đích giáo dục.

---

## Nhóm phát triển

| Thành viên | Vai trò |
|---|---|
| **V.Thắng** | Backend — Django, OMR Engine, REST API, Database |
| **B.Việt** | Frontend — Web UI, Flutter Mobile App, UX Design |

---

*Được xây dựng bởi [Haxodraschool](https://github.com/Haxodraschool)*
