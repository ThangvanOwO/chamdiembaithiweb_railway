# SYSTEM ARCHITECTURE (ACTUAL IMPLEMENTATION)

Tài liệu này mô tả kiến trúc **THỰC TẾ** hiện tại của hệ thống **GradeFlow**.

---

## 1. High-Level Architecture Overview

Hệ thống được tổ chức theo mô hình Web Server/API kết hợp Mobile Client:

```
┌─────────────────────────────────────────────────────────────┐
│                    FLUTTER MOBILE CLIENT                    │
│  - Camera Capture & Realtime Quad Detection (opencv_dart)   │
│  - Offline/Online UI Screens & State Management (Provider)  │
└──────────────────────────────┬──────────────────────────────┘
                               │
                               │ HTTP / REST API (JSON + Multipart Image)
                               ▼
┌─────────────────────────────────────────────────────────────┐
│                  DJANGO BACKEND SERVER                      │
│  ┌───────────────────────────────────────────────────────┐  │
│  │ API Layer (api/views.py) & Web Views (grading/views) │  │
│  └───────────────────────────┬───────────────────────────┘  │
│                              │                              │
│                              ▼                              │
│  ┌───────────────────────────────────────────────────────┐  │
│  │ Grader Adapter Layer (grading/grader.py)               │  │
│  └───────────────────────────┬───────────────────────────┘  │
│                              │                              │
│                              ▼                              │
│  ┌───────────────────────────────────────────────────────┐  │
│  │ OMR Computer Vision & AI Engine (grading/engine/hi.py)│  │
│  │  - Perspective Transform & Corner Alignment          │  │
│  │  - Printed Text Erasing & Morphological Cleaning     │  │
│  │  - Density Thresholding + ONNX CNN Bubble Classifier │  │
│  └───────────────────────────┬───────────────────────────┘  │
│                              │                              │
│                              ▼                              │
│  ┌───────────────────────────────────────────────────────┐  │
│  │ Data / Persistence Layer (grading/models.py ORM)       │  │
│  └───────────────────────────┬───────────────────────────┘  │
└──────────────────────────────┼──────────────────────────────┘
                               │
                               ▼
┌─────────────────────────────────────────────────────────────┐
│                  DATABASE (PostgreSQL / SQLite)             │
│  - Exam, ExamVariant, Submission, UserSettings, Training... │
└─────────────────────────────────────────────────────────────┘
```

---

## 2. Component Breakdown & Actual Data Flows

### 2.1 Request Flow (Web & Mobile API)
1. **Client Request**:
   - Web Client gửi request qua HTML Form / HTMX đến các URL trong `grading/urls.py` hoặc `dashboard/urls.py`.
   - Mobile Client gửi request qua HTTP Client (`http` package) kèm Token/Session Header đến `api/v1/` (`api/urls.py`).
2. **URL Dispatcher & Middleware**:
   - `chamdiemtudong/urls.py` điều hướng đến ứng dụng con thích hợp (`accounts`, `api`, `grading`, `dashboard`).
   - Middleware kiểm tra Security, CORS (`CorsMiddleware`), CSRF (`DisableCSRFOriginCheckMiddleware`), Authentication (`AuthenticationMiddleware`, `AccountMiddleware`), và HTMX header.

### 2.2 Grading Flow (Luồng Chấm Điểm Bài Thi)
1. **Upload & Initial State**:
   - Client gửi file ảnh bài thi tới endpoint `/api/v1/grade/` (`api/views.py:grade_api`) hoặc `/grading/upload/` (`grading/views.py:upload_view`).
   - Hệ thống khởi tạo record `Submission` trong database với trạng thái `pending`.
2. **Execution Strategy**:
   - *Synchronous Grading*: Đọc và xử lý trực tiếp request trong luồng chính khi client yêu cầu phản hồi tức thì.
   - *Async Grading (Celery)*: Đưa task vào Celery queue via Redis broker để xử lý nền đối với batch lớn `[NEEDS VERIFICATION: kiểm tra cấu hình task Celery cụ thể trong sản xuất]`.
3. **Engine Call**:
   - Callback gọi `grading/grader.py:grade_image(image_path, template_code, answer_key_json)`.
   - `grader.py` thêm `grading/engine` vào `sys.path` và gọi `hi.py`.
4. **OMR Processing in `hi.py`**:
   - Tự động phát hiện 4 góc phiếu thi (`auto_deskew_and_crop` / `detect_paper_and_warp`).
   - Warp ảnh về kích thước chuẩn `1400x1920`.
   - Xóa chữ in bảo vệ vùng tô (`erase_printed_text`).
   - Tính toán tỷ lệ pixel đen / tổng pixel (Thresholding) kết hợp với dự đoán từ `bubble_cnn.onnx`.
   - Đối chiếu đáp án với mã đề và tính điểm.
5. **Persist Results**:
   - Cập nhật record `Submission`: `score`, `correct_count`, `answers_detected` (JSON), `detail_json` (JSON chi tiết từng câu), trạng thái `completed`.
   - Trả kết quả JSON về cho Mobile Client hoặc render Template cho Web.

### 2.3 Authentication Flow
1. **Session & Form Auth**:
   - Django Auth mặc định + Django Allauth cho phép đăng nhập qua Form Web.
2. **Google OAuth**:
   - Tích hợp qua `allauth.socialaccount.providers.google`.
3. **Mobile API Auth**:
   - REST API hỗ trợ Register/Login (`/api/v1/auth/login/`), sử dụng Django Auth Session / Token Authentication để duy trì trạng thái đăng nhập cho mobile app.

### 2.4 Database Flow
- Dự án sử dụng Django ORM kết nối với:
  - **Development**: SQLite3 file local ([`db.sqlite3`](file:///c:/Users/Thang/Downloads/chamdiembaithiweb/db.sqlite3)).
  - **Production**: PostgreSQL trên Railway/Render thông qua biến môi trường `DATABASE_URL` (`dj_database_url.parse()`).
- Các models chính:
  - `User` & `TeacherProfile`: Quản lý tài khoản và thông tin giáo viên.
  - `Exam` & `ExamVariant`: Quản lý bài thi, số lượng câu hỏi và đáp án từng mã đề (JSON).
  - `Submission`: Lưu vết từng bài nộp, đường dẫn file ảnh, điểm số, kết quả chi tiết.
  - `TrainingSample`: Lưu ảnh phiếu được đóng góp để huấn luyện AI.

### 2.5 Mobile → API Flow
- Client Flutter (`gradeflow_app`) tương tác với Backend hoàn toàn qua REST API trong [`gradeflow_app/lib/services/api_service.dart`](file:///c:/Users/Thang/Downloads/chamdiembaithiweb/gradeflow_app/lib/services/api_service.dart).
- Khi chấm live camera, ứng dụng có thể xử lý crop góc trực tiếp trên thiết bị (dùng `opencv_dart`) trước khi upload file ảnh hoặc khung hình cropped lên server qua endpoint `/api/v1/grade/`.
