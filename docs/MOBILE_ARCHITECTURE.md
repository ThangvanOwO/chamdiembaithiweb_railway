# MOBILE APP ARCHITECTURE (FLUTTER)

Tài liệu này mô tả kiến trúc ứng dụng di động Flutter nằm trong thư mục `gradeflow_app/`.

---

## 1. Directory Structure (`gradeflow_app/lib/`)

```
gradeflow_app/lib/
├── main.dart                  # Entry Point, App Initialization, Provider Providers Setup
├── config/                    # Cấu hình ứng dụng
│   ├── api_config.dart        # Base URLs, API Endpoints routes
│   └── theme.dart             # Custom Design System, Colors, Typography
├── models/                    # Data Transfer Objects / Data Models
│   ├── exam.dart              # Model Bài thi & Mã đề
│   ├── grade_result.dart      # Model Kết quả chấm bài
│   └── submission.dart        # Model Bài nộp
├── screens/                   # Các màn hình giao diện chính (22 screens)
│   ├── login_screen.dart / register_screen.dart
│   ├── main_shell.dart        # Shell chứa Bottom Navigation Bar
│   ├── dashboard_screen.dart  # Trang chủ thống kê
│   ├── exams_screen.dart / exam_create_screen.dart / exam_import_screen.dart
│   ├── live_camera_screen.dart/ live_scanner.dart / scan_screen.dart # Trình quét camera
│   ├── grade_result_screen.dart / submission_detail_screen.dart # Hiển thị kết quả
│   ├── history_screen.dart / results_screen.dart
│   ├── profile_screen.dart / settings_screen.dart
│   └── admin_*.dart           # Màn hình quản trị admin (training, users, test)
├── services/                  # Business Logic & Networking Services
│   ├── api_service.dart       # Client gửi REST API tới Django Server
│   ├── auth_service.dart      # Quản lý Đăng nhập/Đăng xuất/Token Storage
│   ├── training_uploader.dart # Tải ảnh đóng góp dữ liệu AI
│   ├── idle_detector.dart     # Phát hiện trạng thái rảnh
│   └── tutorial_flow.dart / coach_mark_service.dart # Onboarding & hướng dẫn
└── widgets/                   # UI Widgets tái sử dụng (stat_card.dart...)
```

---

## 2. Layered Architecture Pattern

Ứng dụng tuân theo kiến trúc phân lớp sạch (Clean Layered Architecture):

```
┌─────────────────────────────────────────────────────────────┐
│                    UI LAYER (Widgets & Screens)             │
│  - Render UI, lắng nghe user input                          │
│  - Ví dụ: scan_screen.dart, live_camera_screen.dart         │
└──────────────────────────────┬──────────────────────────────┘
                               │
                               ▼
┌─────────────────────────────────────────────────────────────┐
│                 STATE & CONTROLLER LAYER                    │
│  - Quản lý trạng thái bằng Provider (ChangeNotifier)        │
└──────────────────────────────┬──────────────────────────────┘
                               │
                               ▼
┌─────────────────────────────────────────────────────────────┐
│                       SERVICE LAYER                         │
│  - Gọi `api_service.dart` & `auth_service.dart`             │
│  - Xử lý multipart requestupload ảnh                       │
│  - Bắt lỗi HTTP status codes                                │
└──────────────────────────────┬──────────────────────────────┘
                               │
                               ▼ (HTTP / JSON Payload)
┌─────────────────────────────────────────────────────────────┐
│                    DJANGO REST API BACKEND                  │
└─────────────────────────────────────────────────────────────┘
```

---

## 3. Realtime Camera & Corner Detection
- Sử dụng package `camera` để bắt luồng video từ camera điện thoại.
- Kết hợp package `opencv_dart` để phát hiện khung hình chứa phiếu thi trắc nghiệm (quad/corner detection) ngay tại thiết bị theo thời gian thực.
- Sau khi đóng khung phiếu chuẩn, ứng dụng chụp ảnh và gửi về Backend API (`/api/v1/grade/`).

---

## 4. API Endpoints Client Dependencies

| Mobile Service Method (`api_service.dart`) | Target Django API Endpoint | Description |
| :--- | :--- | :--- |
| `login(email, password)` | `POST /api/v1/auth/login/` | Đăng nhập hệ thống |
| `getExams()` | `GET /api/v1/exams/` | Lấy danh sách bài thi |
| `getExamDetail(id)` | `GET /api/v1/exams/<id>/` | Lấy chi tiết đáp án |
| `gradeImage(file, examId)` | `POST /api/v1/grade/` | Upload ảnh phiếu thi để chấm |
| `getSubmissions(examId)` | `GET /api/v1/submissions/` | Lấy danh sách bài nộp |
| `uploadTrainingSample(...)` | `POST /api/v1/training/upload/` | Đóng góp mẫu ảnh cho server |
