# 📋 Chấm Điểm Trắc Nghiệm Online — Implementation Plan

> Website Django phục vụ giáo viên upload ảnh bài kiểm tra trắc nghiệm để máy chấm điểm tự động.
> **Phần engine chấm điểm là Python module đã có sẵn** — chỉ xây dựng web frontend + backend Django để tích hợp.

---

## 📌 Understanding Summary

- **Xây gì:** Website Django cho giáo viên tải ảnh bài kiểm tra trắc nghiệm lên, hệ thống tự động chấm điểm và trả kết quả
- **Tại sao:** Tự động hóa quy trình chấm bài, giảm thời gian và lỗi cho giáo viên
- **Cho ai:** Giáo viên tại các trường học
- **Ràng buộc:** 
  - Engine chấm điểm là **Python module** đã có sẵn (import trực tiếp)
  - Phải là Django (Python)
  - Giao diện phải **chuyên nghiệp và đẹp**
  - MySQL trên Linux (không xài XAMPP)
  - **Không đăng nhập bằng Google** — chỉ giáo viên có tài khoản được cấp mới đăng nhập được
- **Không bao gồm:** Viết engine chấm điểm, mobile app, API cho bên thứ 3, đăng nhập bên thứ 3

---

## 🎨 Design Direction: "Editorial Precision"

> **Aesthetic:** Editorial / Magazine × Luxury Minimal
> 
> Lấy cảm hứng từ design system đã có trên Stitch — "The Academic Editorial". Giao diện mang phong cách tạp chí học thuật cao cấp, biến công việc hành chính thành trải nghiệm premium.

### DFII Score (Design Feasibility & Impact Index)

| Dimension | Score | Rationale |
|:---|:---:|:---|
| Aesthetic Impact | 5 | Editorial layering + glassmorphism tạo ấn tượng mạnh |
| Context Fit | 5 | Giáo viên cần giao diện sạch, chuyên nghiệp, dễ dùng |
| Implementation Feasibility | 4 | Django templates + HTMX hoàn toàn khả thi |
| Performance Safety | 5 | Server-rendered, nhẹ, nhanh |
| Consistency Risk | 2 | Design system rõ ràng, dễ maintain |

**DFII = (5 + 5 + 4 + 5) − 2 = 17** → ✅ Excellent

### Differentiation Anchor

> "Nếu screenshot mà bỏ logo đi, người ta vẫn nhận ra nhờ: **bề mặt tonal nhiều lớp không viền (no-border)**, typography Manrope/DM Sans với hierarchy editorial, và hiệu ứng 'Paper Slide' khi kết quả chấm điểm xuất hiện."

---

## 🛠️ Technology Stack

### Backend (Django)

| Library | Mục đích |
|:---|:---|
| **Django 5.x** | Framework chính |
| **django-allauth** | Xác thực giáo viên (email/password — **không Google login**) |
| **django-htmx** | Tích hợp HTMX cho partial rendering |
| **Celery + Redis** | Xử lý chấm điểm bất đồng bộ (background tasks) |
| **django-import-export** | Xuất kết quả ra Excel/CSV |
| **Pillow** | Xử lý ảnh upload |
| **django-storages** *(tùy chọn)* | Lưu ảnh lên cloud nếu cần |
| **whitenoise** | Serve static files production |

### Frontend (Django Templates)

| Library | Mục đích |
|:---|:---|
| **HTMX 2.x** | Tương tác AJAX không cần JS framework nặng |
| **Alpine.js 3.x** | UI state nhỏ (dropdown, modal, tabs) |
| **Vanilla CSS** (custom design system) | Styling chính — **không dùng Tailwind** |
| **Chart.js** hoặc **Apache ECharts** | Biểu đồ thống kê kết quả |
| **Dropzone.js** | Khu vực drag & drop upload ảnh chuyên nghiệp |
| **GSAP (lite)** | Animation "Paper Slide" cho kết quả |

### Typography (Google Fonts)

| Role | Font | Lý do |
|:---|:---|:---|
| **Display & Headlines** | **Manrope** | Geometric precision, modern, dễ đọc ở size lớn |
| **Body & Data** | **DM Sans** | Tối ưu cho text nhỏ, data-dense UI, legibility cao |

> **Tránh:** Inter, Roboto, Arial — quá generic, vi phạm frontend-design skill.

---

## 🏗️ 6 Công Đoạn Triển Khai

---

### Công đoạn 1: Foundation — Django Project Setup
> *Khung dự án + cấu trúc + thiết lập ban đầu*

**Việc cần làm:**

- [ ] Khởi tạo Django project: `chamdiemtudong`
- [ ] Tạo các Django apps:
  - `accounts` — Quản lý giáo viên (auth)
  - `grading` — Upload & chấm điểm
  - `dashboard` — Thống kê & kết quả
- [ ] Cấu hình `settings.py`:
  - Database: **MySQL trên Linux** (user `root`, password `123456`)
  - Media files cho upload ảnh
  - Static files structure
- [ ] Cài đặt dependencies (`requirements.txt`)
- [ ] Tạo base template structure:
  ```
  templates/
  ├── base.html          # Layout chính
  ├── partials/          # HTMX partials
  ├── accounts/          # Login, register
  ├── grading/           # Upload, kết quả
  └── dashboard/         # Thống kê
  ```
- [ ] Cấu hình HTMX + Alpine.js + static files

**Output:** Dự án Django chạy được, truy cập `localhost:8000` thấy trang trắng với base layout.

---

### Công đoạn 2: Design System — CSS Foundation
> *Xây dựng toàn bộ design system bằng CSS thuần*

**Việc cần làm:**

- [ ] Tạo `static/css/design-system.css` — Design tokens:
  ```css
  :root {
    /* Surface Layers (No-Border Philosophy) */
    --surface: #f8f9fa;
    --surface-container-low: #f3f4f5;
    --surface-container: #edeeef;
    --surface-container-high: #e7e8e9;
    --surface-container-highest: #e1e3e4;
    --surface-container-lowest: #ffffff;
    
    /* Primary Gradient */
    --primary: #005bbf;
    --primary-container: #1a73e8;
    
    /* Tertiary (Alerts) */
    --tertiary: #8f4d00;
    --tertiary-container: #b36200;
    
    /* Typography */
    --font-display: 'Manrope', sans-serif;
    --font-body: 'DM Sans', sans-serif;
    
    /* Roundness */
    --radius-sm: 0.375rem;
    --radius-md: 0.5rem;
    --radius-lg: 0.75rem;
    --radius-full: 9999px;
    
    /* Shadows (Ambient only) */
    --shadow-ambient: 0px 12px 32px rgba(25, 28, 29, 0.06);
    --shadow-glass: 0px 8px 24px rgba(0, 91, 191, 0.08);
  }
  ```

- [ ] Tạo `static/css/components.css` — Component styles:
  - Buttons (Primary gradient, Secondary tonal, Tertiary text)
  - Cards (Surface-layered, no borders)
  - Upload zone (Surface-high, glassmorphic drag-over)
  - Tables (No divider lines, spaced rows)
  - Input fields (Bottom ghost-border, focus animation)
  - Progress bars (Thin 4px, gradient indicator)
  - Chips/Badges (Full rounded, pill-shaped)
  - Toast notifications
  - Glassmorphism overlay cho modals

- [ ] Tạo `static/css/layout.css` — Grid & Spacing:
  - Sidebar layout (collapsible)
  - Main content area
  - Responsive breakpoints
  - Asymmetric compositions

- [ ] Import Google Fonts (Manrope + DM Sans variable)

**Output:** Design system hoàn chỉnh, có thể preview trên style guide page.

---

### Công đoạn 3: Authentication — Giáo viên Đăng nhập
> *Hệ thống auth hoàn chỉnh cho giáo viên*

**Việc cần làm:**

- [ ] Cài đặt `django-allauth` (chỉ dùng email/password — **tắt hết social providers**)
- [ ] Tạo model `TeacherProfile` (extends User):
  - Họ tên, trường, môn dạy, avatar
- [ ] Tạo trang **Login** (`/accounts/login/`):
  - Form đăng nhập email/password **duy nhất**
  - **Không có nút đăng nhập Google/Social** (để tránh ai cũng vào được)
  - Design: Surface-container-lowest card, centered, gradient CTA button
- [ ] **Tài khoản giáo viên do Admin tạo** — không có trang đăng ký công khai:
  - Admin tạo tài khoản qua Django Admin panel
  - Giáo viên nhận thông tin đăng nhập từ quản trị viên
- [ ] Tạo trang **Profile** (`/accounts/profile/`):
  - Thông tin giáo viên, đổi mật khẩu
- [ ] Middleware bảo vệ routes: chỉ giáo viên đã login mới truy cập được
- [ ] **Không có trang Register công khai** — bảo mật, chỉ người được cấp tài khoản mới truy cập

**Output:** Admin tạo tài khoản → Giáo viên đăng nhập → vào được trang chính. Không ai tự đăng ký được.

---

### Công đoạn 4: Core Feature — Upload & Chấm điểm
> *Tính năng chính: Upload ảnh bài KT → Nhận kết quả chấm điểm*

**Việc cần làm:**

- [ ] Tạo models:
  - `Exam` — Bài thi (tên, môn, số câu, đáp án đúng, ngày tạo)
  - `Submission` — Bài nộp (ảnh, học sinh, điểm, trạng thái, thời gian xử lý)
- [ ] Tạo trang **Tạo bài thi** (`/grading/exams/new/`):
  - Form nhập thông tin bài thi + đáp án
  - Hỗ trợ upload file đáp án (CSV/Excel) qua `django-import-export`
- [ ] Tạo trang **Upload & Chấm** (`/grading/upload/`):
  - **Dropzone.js** — Khu vực kéo thả ảnh (hỗ trợ nhiều ảnh cùng lúc)
  - Chọn bài thi để chấm
  - Nút "Bắt đầu chấm" (gradient CTA)
  - Progress bar realtime (HTMX polling)
- [ ] Tích hợp engine chấm điểm:
  - Celery task gọi engine chấm điểm đã có
  - Lưu kết quả vào database
  - Trả kết quả về frontend qua HTMX
- [ ] Tạo trang **Kết quả** (`/grading/results/<exam_id>/`):
  - Bảng kết quả (no-border table design)
  - Hiệu ứng **"Paper Slide"** khi kết quả mới xuất hiện
  - Chip badges: Giỏi (xanh), Khá (cam), TB (vàng), Yếu (đỏ)
  - Nút xuất Excel/CSV

**Output:** Giáo viên upload ảnh → Hệ thống chấm → Hiển thị kết quả + xuất file.

---

### Công đoạn 5: Dashboard — Thống kê & Quản lý
> *Trang tổng quan cho giáo viên theo dõi dữ liệu*

**Việc cần làm:**

- [ ] Tạo trang **Dashboard** (`/dashboard/`):
  - **Hero section:** Chào mừng giáo viên (Manrope display-lg)
  - **Stats cards** (Surface-layered):
    - Tổng bài đã chấm
    - Điểm trung bình
    - Tỉ lệ đạt/không đạt
    - Bài chấm hôm nay
  - **Biểu đồ** (Chart.js / ECharts):
    - Phân bố điểm (bar chart)
    - Xu hướng theo thời gian (line chart)
    - Tỉ lệ đúng theo câu hỏi (heatmap)
  - **Bảng bài thi gần đây** (HTMX infinite scroll)
  - **Quick actions:** Upload nhanh, tạo bài thi mới

- [ ] Tạo trang **Lịch sử chấm** (`/dashboard/history/`):
  - Danh sách tất cả submissions
  - Filter & search (HTMX realtime)
  - Sort theo ngày, điểm, bài thi

- [ ] Tạo **sidebar navigation** (Alpine.js collapsible):
  - Dashboard
  - Chấm điểm → Upload / Tạo bài thi
  - Lịch sử
  - Hồ sơ

**Output:** Dashboard đầy đủ thống kê, biểu đồ, và navigation chuyên nghiệp.

---

### Công đoạn 6: Polish — Hoàn thiện & Triển khai
> *Đánh bóng UX, animations, responsive & chuẩn bị deploy*

**Việc cần làm:**

- [ ] **Animations & Micro-interactions:**
  - "Paper Slide" spring animation cho kết quả mới (GSAP)
  - Upload zone: glassmorphic overlay khi drag-over
  - Button hover: subtle scale + shadow transition
  - Page transitions: fade-in cho HTMX swaps
  - Toast notification slide-in

- [ ] **Responsive Design:**
  - Mobile-first adjustments
  - Sidebar → Bottom nav trên mobile
  - Upload zone responsive
  - Tables → Cards trên mobile

- [ ] **Dark Mode** *(tùy chọn)*:
  - Toggle dark/light mode
  - Dark color tokens

- [ ] **Error Handling & Edge Cases:**
  - Upload thất bại → Toast error + retry
  - Ảnh không hợp lệ → Thông báo rõ ràng
  - Loading states cho mọi async action
  - Empty states (chưa có bài thi, chưa có kết quả)

- [ ] **Performance & SEO:**
  - Static file compression (whitenoise + gzip)
  - Image optimization cho uploads
  - Meta tags cho SEO
  - Lazy loading cho biểu đồ

- [ ] **Deployment preparation:**
  - `Dockerfile` + `docker-compose.yml`
  - Cấu hình production settings
  - `.env` cho secrets
  - README.md hướng dẫn cài đặt

**Output:** Website hoàn chỉnh, đẹp, responsive, sẵn sàng triển khai.

---

## 📂 Project Structure (Dự kiến)

```
Chamdiemtudongweb/
├── chamdiemtudong/           # Django project
│   ├── settings.py
│   ├── urls.py
│   └── wsgi.py
├── accounts/                 # App: Auth & Profile
│   ├── models.py
│   ├── views.py
│   ├── urls.py
│   └── forms.py
├── grading/                  # App: Upload & Chấm
│   ├── models.py
│   ├── views.py
│   ├── urls.py
│   ├── tasks.py              # Celery tasks
│   └── forms.py
├── dashboard/                # App: Thống kê
│   ├── views.py
│   └── urls.py
├── templates/
│   ├── base.html
│   ├── partials/
│   │   ├── _navbar.html
│   │   ├── _sidebar.html
│   │   ├── _toast.html
│   │   └── _upload_zone.html
│   ├── accounts/
│   ├── grading/
│   └── dashboard/
├── static/
│   ├── css/
│   │   ├── design-system.css
│   │   ├── components.css
│   │   ├── layout.css
│   │   └── animations.css
│   ├── js/
│   │   ├── htmx.min.js
│   │   ├── alpine.min.js
│   │   ├── dropzone.min.js
│   │   ├── chart.min.js
│   │   └── app.js
│   └── images/
├── media/                    # Uploaded exam images
├── requirements.txt
├── Dockerfile
├── docker-compose.yml
└── manage.py
```

---

## 🔍 Decision Log

| # | Quyết định | Các lựa chọn khác | Lý do chọn |
|:---:|:---|:---|:---|
| 1 | **Django Templates + HTMX** thay vì React/Vue SPA | React + DRF, Vue + DRF | Đơn giản hơn, cùng team backend, không cần API layer riêng, performance tốt |
| 2 | **Vanilla CSS** thay vì Tailwind | Tailwind, Bootstrap, Bulma | Frontend-design skill yêu cầu intentional design system, không dùng framework CSS generic |
| 3 | **Manrope + DM Sans** thay vì Inter/Roboto | Inter, Work Sans, IBM Plex Sans | Manrope cho headlines editorial, DM Sans tối ưu cho data tables nhỏ |
| 4 | **Celery + Redis** cho async grading | Django Channels, synchronous processing | Engine chấm điểm CPU-intensive, cần background processing để UI không bị block |
| 5 | **Dropzone.js** cho upload | Native HTML5 drag-drop, FilePond | Mature, lightweight, customizable, hỗ trợ multi-file upload |
| 6 | **Alpine.js** cho UI state | jQuery, vanilla JS | Lightweight (15KB), declarative, works perfectly với Django templates |

---

## ✅ Verification Plan

### Automated Tests
```bash
# Unit tests
python manage.py test accounts grading dashboard

# Check migrations
python manage.py makemigrations --check --dry-run

# Static files collection
python manage.py collectstatic --noinput
```

### Browser Testing
- [ ] Flow: Register → Login → Tạo bài thi → Upload ảnh → Xem kết quả → Xuất Excel
- [ ] Responsive: Test trên 3 viewports (Mobile 375px, Tablet 768px, Desktop 1440px)
- [ ] Animations: "Paper Slide", drag-over glassmorphism, toast notifications

### Manual Verification
- [ ] Design system nhất quán trên tất cả trang
- [ ] HTMX partial rendering hoạt động smooth
- [ ] Celery task chấm điểm chạy đúng
- [ ] Upload nhiều ảnh cùng lúc không lỗi

---

## ⚠️ User Review Required

> [!NOTE]
> **Engine chấm điểm:** ✅ Đã xác nhận là Python module, sẽ import trực tiếp trong Celery task.
> Khi tích hợp, anh Hà cho em biết thêm:
> - Tên module/function cần gọi?
> - Input: nhận file ảnh (path) hay image bytes?
> - Output: trả về gì (điểm số, dict chi tiết từng câu...)?

> [!NOTE]
> **Database:** ✅ Đã xác nhận — MySQL trên Linux, user `root`, password `123456`.

> [!NOTE]
> **Google Login:** ✅ Đã xác nhận — **KHÔNG** dùng Google Login. Chỉ đăng nhập bằng email/password, tài khoản do Admin tạo.

---

## 📝 Assumptions

1. ✅ Engine chấm điểm là **Python module** — import và gọi trực tiếp trong Celery task
2. ✅ **MySQL trên Linux** — user `root`, password `123456` (KHÔNG dùng XAMPP)
3. ✅ **Không Google Login** — chỉ email/password, tài khoản do Admin cấp
4. Redis cho Celery sẽ cài thêm (hoặc dùng RabbitMQ)
5. Không cần multi-tenancy (nhiều trường trên cùng 1 hệ thống)
6. Giáo viên tự tạo bài thi và upload đáp án
7. Mỗi ảnh upload là 1 bài làm của 1 học sinh
