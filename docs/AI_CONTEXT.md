# AI PROJECT KNOWLEDGE BASE: CONTEXT & RULES

> **MỤC TIÊU FILE**: Đây là tài liệu khởi đầu dành cho AI / Agent khi làm việc với dự án **GradeFlow**. Đọc file này giúp nắm bắt toàn bộ bối cảnh, quy tắc an toàn, entry point và chiến lược tải context mà không cần scan lại toàn bộ codebase.

---

## 1. Project Overview & Purpose
- **Tên dự án**: GradeFlow (Hệ thống chấm điểm trắc nghiệm tự động).
- **Mục đích**: Tự động hóa quá trình chấm bài thi trắc nghiệm Việt Nam (Phần I: ABCD 40 câu; Phần II: Đúng/Sai 8 câu; Phần III: Điền số 6 câu) qua ảnh chụp/scan phiếu thi.
- **Mô hình triển khai**: Hybrid (Backend Django phục vụ Web Dashboard & REST API + Client Flutter App phục vụ quét camera tại chỗ hoặc gửi về server).

---

## 2. Technology Stack
- **Language**: Python 3.11+ (Backend / ML), Dart 3.5+ (Mobile App).
- **Backend Framework**: Django 5.2, Django REST Framework (DRF) 3.15.2, Django HTMX 1.27.0.
- **Mobile Framework**: Flutter 3.24+, Provider (State Management), `opencv_dart`, `camera` plugin.
- **Computer Vision & AI**: OpenCV (`opencv-python-headless`), NumPy, Scikit-Image, PyTorch / ONNX Runtime (`bubble_cnn.onnx`).
- **Task Queue**: Celery 5.6.3 + Redis 7.4.0 (Broker & Result Backend).
- **Authentication**: Django Allauth (Session, Email/Password + Google OAuth JWT), PyJWT.
- **Database**: PostgreSQL (`psycopg2-binary`, `dj-database-url`) trên Production; SQLite (`db.sqlite3`) trên Dev.
- **Production Server & Deployment**: Gunicorn 22.0.0, WhiteNoise 6.12.0, Nginx, Docker, Railway / Render / GCP.

---

## 3. Repository Structure & Core Modules
```
chamdiembaithiweb/
├── chamdiemtudong/            # [Core Config] Settings, Root URLs, WSGI/ASGI, Middleware
├── api/                       # [API Module] REST API v1 cho Mobile App (urls.py, views.py)
├── accounts/                  # [Auth Module] User & TeacherProfile models, Auth views
├── dashboard/                 # [Web Dashboard] Web views cho trang chủ/thống kê giáo viên
├── grading/                   # [Grading Module] Database Models (Exam, Submission) & Grader Adapter
│   └── engine/                # [OMR Engine] Computer Vision pipeline (hi.py, bubble_cnn.onnx, templates/)
├── gradeflow_app/             # [Mobile App] Flutter application (lib/, assets/, pubspec.yaml)
├── templates/                 # [Web UI] HTML Templates cho Django Frontend
├── static/                    # [Static Assets] CSS, JS, Service Worker (sw.js)
├── scripts/                   # [Deployment] Scripts hỗ trợ SSL, deploy, admin
├── docs/                      # [AI Knowledge Base] Tài liệu kiến trúc và hướng dẫn AI
└── [Root Scripts]             # 23+ script Python thử nghiệm/test/calibration rải rác ở root
```

---

## 4. Entry Points

### Backend Entry Points
- **Development CLI**: [`manage.py`](file:///c:/Users/Thang/Downloads/chamdiembaithiweb/manage.py)
- **Production WSGI**: [`chamdiemtudong/wsgi.py`](file:///c:/Users/Thang/Downloads/chamdiembaithiweb/chamdiemtudong/wsgi.py)
- **Production ASGI**: [`chamdiemtudong/asgi.py`](file:///c:/Users/Thang/Downloads/chamdiembaithiweb/chamdiemtudong/asgi.py)
- **Root URL Routing**: [`chamdiemtudong/urls.py`](file:///c:/Users/Thang/Downloads/chamdiembaithiweb/chamdiemtudong/urls.py)

### Mobile App Entry Point
- **Flutter Main Entry**: [`gradeflow_app/lib/main.dart`](file:///c:/Users/Thang/Downloads/chamdiembaithiweb/gradeflow_app/lib/main.dart)

### OMR Engine Execution Flow
- [`grading/views.py`](file:///c:/Users/Thang/Downloads/chamdiembaithiweb/grading/views.py) / [`api/views.py`](file:///c:/Users/Thang/Downloads/chamdiembaithiweb/api/views.py) 
  → [`grading/grader.py`](file:///c:/Users/Thang/Downloads/chamdiembaithiweb/grading/grader.py) 
  → [`grading/engine/hi.py`](file:///c:/Users/Thang/Downloads/chamdiembaithiweb/grading/engine/hi.py)

---

## 5. Summary of Key Components

| Component | Responsibility | Important Files |
| :--- | :--- | :--- |
| **OMR Engine** | Xử lý thị giác máy tính (Perspective warp, contouring, thresholding, CNN classification) | [`grading/engine/hi.py`](file:///c:/Users/Thang/Downloads/chamdiembaithiweb/grading/engine/hi.py), [`grading/engine/bubble_cnn.onnx`](file:///c:/Users/Thang/Downloads/chamdiembaithiweb/grading/engine/bubble_cnn.onnx) |
| **Data Layer** | Quản lý schema bài thi, mã đề, bài nộp và mẫu huấn luyện | [`grading/models.py`](file:///c:/Users/Thang/Downloads/chamdiembaithiweb/grading/models.py), [`accounts/models.py`](file:///c:/Users/Thang/Downloads/chamdiembaithiweb/accounts/models.py) |
| **REST API** | Cung cấp endpoints cho Flutter client | [`api/urls.py`](file:///c:/Users/Thang/Downloads/chamdiembaithiweb/api/urls.py), [`api/views.py`](file:///c:/Users/Thang/Downloads/chamdiembaithiweb/api/views.py) |
| **Mobile UI/Service** | Giao diện di động, quét camera, gọi API server | [`gradeflow_app/lib/main.dart`](file:///c:/Users/Thang/Downloads/chamdiembaithiweb/gradeflow_app/lib/main.dart), [`gradeflow_app/lib/services/api_service.dart`](file:///c:/Users/Thang/Downloads/chamdiembaithiweb/gradeflow_app/lib/services/api_service.dart) |
| **Task Queue** | Chạy tác vụ chấm điểm nền bất đồng bộ | [`requirements.txt`](file:///c:/Users/Thang/Downloads/chamdiembaithiweb/requirements.txt) (Celery/Redis config trong `settings.py`) |

---

## 6. Critical Rules cho AI / Assistant

> [!CAUTION]
> Tuân thủ nghiêm ngặt các quy tắc dưới đây để không phá vỡ logic chấm điểm hoặc gây vỡ tương thích hệ thống:

1. **KHÔNG tự ý thay đổi thuật toán OMR trong [`grading/engine/hi.py`](file:///c:/Users/Thang/Downloads/chamdiembaithiweb/grading/engine/hi.py)** trừ khi task yêu cầu trực tiếp. Đây là file monolithic (185KB) nhạy cảm cao với độ chính xác chấm điểm.
2. **KHÔNG refactor các God Modules** (`hi.py`, `grading/views.py`, `api/views.py`) trong lúc thực hiện fix bug nhỏ.
3. **KHÔNG thay đổi API Contract** (`api/urls.py`, response JSON format trong `api/views.py`) nếu chưa đối chiếu và cập nhật tương thích trong Flutter client (`gradeflow_app/lib/services/api_service.dart`).
4. **KHÔNG sửa Database Schema** (`grading/models.py`) mà không kiểm tra tính tương thích dữ liệu cũ và cập nhật migrations.
5. **KHÔNG thay đổi template JSON** trong `grading/engine/templates/` mà không chạy thử nghiệm kiểm tra tương thích tọa độ (calibration).
6. **KHÔNG xóa các file test/calibration ở root** chỉ vì chúng nằm rải rác.
7. **KHÔNG sửa nhiều module không liên quan** đến phạm vi của task được giao.

---

## 7. Context Loading Strategy cho AI

Khi tiếp nhận một task mới, AI cần tuân theo thứ tự sau:

1. **Bước 1**: Đọc [`docs/AI_CONTEXT.md`](file:///c:/Users/Thang/Downloads/chamdiembaithiweb/docs/AI_CONTEXT.md) để định hình toàn cục.
2. **Bước 2**: Tra cứu sơ đồ module liên quan trong các tài liệu chuyên biệt:
   - Thuật toán chấm điểm → Đọc [`docs/OMR_ENGINE.md`](file:///c:/Users/Thang/Downloads/chamdiembaithiweb/docs/OMR_ENGINE.md)
   - API Backend → Đọc [`docs/API_ARCHITECTURE.md`](file:///c:/Users/Thang/Downloads/chamdiembaithiweb/docs/API_ARCHITECTURE.md)
   - App Mobile → Đọc [`docs/MOBILE_ARCHITECTURE.md`](file:///c:/Users/Thang/Downloads/chamdiembaithiweb/docs/MOBILE_ARCHITECTURE.md)
   - Đánh giá rủi ro → Đọc [`docs/KNOWN_RISKS.md`](file:///c:/Users/Thang/Downloads/chamdiembaithiweb/docs/KNOWN_RISKS.md)
3. **Bước 3**: Chỉ dùng `view_file` mở chính xác các file mã nguồn trực tiếp liên quan đến task.
4. **Bước 4**: Mở rộng context trace dependency **chỉ khi có bằng chứng rõ ràng** về sự ảnh hưởng liên module.
5. **Tối kỵ**: Không tự ý dùng tool scan/read toàn bộ các file trong repository nếu không thực sự cần thiết.
