# BACKEND & API ARCHITECTURE

> Cập nhật bảo mật 26/09/2026: xem [SECURITY_HARDENING.md](SECURITY_HARDENING.md). Đăng ký email `/api/v1/auth/register/` yêu cầu `turnstile_token`, trả HTTP 202 với `requires_email_verification` và `message`; chưa trả token cho đến khi xác minh và đăng nhập. Chi tiết bài nộp có thêm `image_url`, phải gửi Authorization khi tải ảnh. Các API ChamTN `/api/exams`, `/api/sheets`, `/api/me` yêu cầu session và CSRF cho thao tác ghi; dữ liệu được lọc theo chủ sở hữu.

Tài liệu này chi tiết cấu trúc REST API, Web Views, Routing, Authentication và luồng tương tác với cơ sở dữ liệu.

---

## 1. Backend Modules Structure

- [`api/`](file:///c:/Users/Thang/Downloads/chamdiembaithiweb/api/): Cung cấp các RESTful API endpoints dành riêng cho Flutter Mobile App.
- [`accounts/`](file:///c:/Users/Thang/Downloads/chamdiembaithiweb/accounts/): Quản lý người dùng, đăng nhập/đăng ký, Google OAuth, và profile giáo viên (`TeacherProfile`).
- [`grading/`](file:///c:/Users/Thang/Downloads/chamdiembaithiweb/grading/): Chứa Database Models cốt lõi (`Exam`, `ExamVariant`, `Submission`, `TrainingSample`, `UserSettings`) và Web views phục vụ giao diện HTML Web.
- [`dashboard/`](file:///c:/Users/Thang/Downloads/chamdiembaithiweb/dashboard/): Web view hiển thị tổng quan thống kê bài thi cho giáo viên.

---

## 2. Root URL Routing (`chamdiemtudong/urls.py`)

| Prefix | Included App / View | Description |
| :--- | :--- | :--- |
| `/sw.js` | Service Worker View | Phục vụ PWA Service Worker tại root scope. |
| `/admin/` | `admin.site.urls` | Django Admin Control Panel. |
| `/accounts/` | `accounts.urls` & `allauth.urls` | Auth views (Login, Logout, Profile, Google OAuth). |
| `/api/` | `api.urls` | **REST API v1 cho Mobile Client**. |
| `/grading/` | `grading.urls` | Web Views quản lý bài thi, upload, kết quả. |
| `/` | `dashboard.urls` | Dashboard trang chủ giáo viên. |

---

## 3. REST API Endpoints Table (`api/urls.py`)

> [!IMPORTANT]
> **API CONTRACTS PHỤ THUỘC BỞI FLUTTER APP**:
> Các endpoints được đánh dấu **[CRITICAL FOR FLUTTER]** là các contract trực tiếp với `gradeflow_app`. Không tự ý thay đổi tên field trong JSON response hoặc thay đổi đường dẫn URL.

| Method | Endpoint | Function View | Critical Contract |
| :--- | :--- | :--- | :--- |
| `POST` | `/api/v1/auth/register/` | `register_api` | Đăng ký tài khoản từ Mobile |
| `POST` | `/api/v1/auth/login/` | `login_api` | **[CRITICAL FOR FLUTTER]** Đăng nhập |
| `POST` | `/api/v1/auth/logout/` | `logout_api` | Đăng xuất |
| `GET` | `/api/v1/auth/me/` | `me_api` | Lấy thông tin user hiện tại |
| `GET` | `/api/v1/dashboard/` | `dashboard_api` | Thống kê nhanh cho Mobile Dashboard |
| `GET/POST`| `/api/v1/exams/` | `exams_list_api` | **[CRITICAL FOR FLUTTER]** Lấy/Tạo danh sách bài thi |
| `GET` | `/api/v1/exams/<id>/` | `exam_detail_api` | **[CRITICAL FOR FLUTTER]** Chi tiết bài thi & đáp án mã đề |
| `DELETE` | `/api/v1/exams/<id>/delete/`| `exam_delete_api` | Xóa bài thi |
| `POST` | `/api/v1/parse-excel/` | `parse_excel_api` | Parse file Excel đáp án |
| `POST` | `/api/v1/parse-image/` | `parse_image_api` | Parse đáp án từ ảnh bảng đáp án |
| `GET` | `/api/v1/templates/` | `templates_list_api` | Lấy danh sách phiếu thi được hỗ trợ |
| `POST` | `/api/v1/grade/` | `grade_api` | **[CRITICAL FOR FLUTTER]** Upload & Chấm bài thi |
| `GET` | `/api/v1/submissions/` | `submissions_list_api` | Lấy lịch sử các bài nộp |
| `GET` | `/api/v1/submissions/<id>/`| `submission_detail_api` | **[CRITICAL FOR FLUTTER]** Chi tiết bài nộp |
| `GET/POST`| `/api/v1/settings/` | `user_settings_api` | Cấu hình tự động xóa ảnh/góp dữ liệu |
| `POST` | `/api/v1/training/upload/` | `training_upload_api` | Gửi phiếu đóng góp AI Active Learning |

---

## 4. Request / Response Data Flow

```
Flutter App Request
       │ (JSON payload / Multipart File)
       ▼
   api/views.py
       │
       ├─► Validation (Check Auth Token, User Permission)
       │
       ├─► Database Access (models.Exam, models.Submission)
       │
       ├─► Execution: Call grading/grader.py -> grading/engine/hi.py
       │
       ▼
JSON Response Format:
{
    "success": true,
    "data": {
        "submission_id": 123,
        "score": 8.5,
        "correct_count": 34,
        "total_questions": 40,
        "student_id": "012345",
        "student_name": "Nguyen Van A",
        "detail": { ... }
    },
    "message": "Chấm bài thành công"
}
```

---

## 5. Models Layer Reference (`grading/models.py`)

- `UserSettings`: OneToOne với `User`, lưu số ngày tự động xóa ảnh (`temp_retention_days`), bật/tắt đóng góp dữ liệu AI (`contribute_training_data`).
- `Exam`: Bài thi chính, lưu tên môn, số câu hỏi (`num_questions`), cấu hình phần thi (`parts_config`), điểm trung bình (`average_score`).
- `ExamVariant`: Lưu đáp án đúng của từng mã đề cụ thể (`variant_code`, `answers_json`).
- `Submission`: Lưu kết quả chấm bài thi của học sinh (`image`, `status`, `score`, `answers_detected`, `detail_json`, `error_message`).
- `TrainingSample`: Lưu thông tin ảnh mẫu "sạch" được giáo viên tự nguyện đóng góp để huấn luyện lại CNN.

## 6. Closed-testing username registration (02/10/2026)

Enable explicitly with `ALLOW_USERNAME_SIGNUP=1`. No database migration is needed.

- `POST /api/v1/auth/register/` accepts `{username, password, full_name, email?}` and returns HTTP 201 with the existing `{token, user}` session shape. `user.username` is additive. From Android 2105, the form requires a contact email; the backend keeps it optional for older clients.
- Username: normalized lowercase, 3–30 ASCII characters (`a-z`, `0-9`, `.`, `_`); the first character must be a letter or number. Names containing `@` are rejected. Full name is required (100 characters maximum).
- Password: existing Django validators and hashing. Role/credit fields are never accepted from clients. The existing signup limit remains 5 POST attempts per IP per hour, including unsuccessful attempts.
- A provided contact email is validated, normalized to lowercase and stored in `User.email` plus an **unverified** `EmailAddress`. Existing email addresses are rejected. Omitted emails still create email-less accounts. Google email-based authentication only links to an already verified local email address; existing linked Google provider IDs remain valid. Entering an email does not prove ownership.
- Legacy `{email, password, first_name, last_name, turnstile_token}` registration still returns HTTP 202 and requires email verification. It is not opened by the username flag.
- Login retains `{email, password}`: the `email` field accepts a username or an existing email address. Disabled users cannot log in.
- Web registration displays full name, username, email, password and password confirmation when enabled. Web login accepts username or email and retains CSRF protection.
- Set `ALLOW_USERNAME_SIGNUP=0` and recreate the web service to close new username registrations. Existing accounts continue to log in. The new contact field does not activate automatic email verification or password-reset delivery; administrator assistance remains available.
