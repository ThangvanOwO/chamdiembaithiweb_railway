# OMR ENGINE ARCHITECTURE & SPECIFICATION

> [!WARNING]
> **CẢNH BÁO MÃ NGUỒN NGUY HIỂM / CRITICAL CODE**:
> File [`grading/engine/hi.py`](file:///c:/Users/Thang/Downloads/chamdiembaithiweb/grading/engine/hi.py) là trung tâm thuật toán xử lý ảnh của toàn bộ dự án. File này chứa hơn 4,200 dòng mã nguồn liên kết chặt chẽ. **KHÔNG** tự ý sửa đổi, tái cấu trúc (refactor) hoặc chỉnh sửa tham số nếu chưa kiểm thử kỹ lưỡng trên tập dữ liệu mẫu.

---

## 1. Structure of `grading/engine/`

Thư mục `grading/engine/` chịu trách nhiệm toàn bộ bài toán Optical Mark Recognition (OMR):

- [`hi.py`](file:///c:/Users/Thang/Downloads/chamdiembaithiweb/grading/engine/hi.py): **Core OMR Pipeline Engine** (Căn chỉnh, xoay, xóa chữ in, tính toán tỷ lệ tô, CNN classification, chấm điểm).
- [`fast_grade.py`](file:///c:/Users/Thang/Downloads/chamdiembaithiweb/grading/engine/fast_grade.py): Module hỗ trợ chấm nhanh.
- [`extract_bubbles.py`](file:///c:/Users/Thang/Downloads/chamdiembaithiweb/grading/engine/extract_bubbles.py): Script trích xuất ô tô để chuẩn bị dữ liệu huấn luyện.
- [`bubble_cnn.onnx`](file:///c:/Users/Thang/Downloads/chamdiembaithiweb/grading/engine/bubble_cnn.onnx) & `bubble_cnn.pth`: Model weights đã huấn luyện để phân loại ô đã tô vs ô trống.
- [`train_bubble_cnn.py`](file:///c:/Users/Thang/Downloads/chamdiembaithiweb/grading/engine/train_bubble_cnn.py) & [`test_bubble_cnn.py`](file:///c:/Users/Thang/Downloads/chamdiembaithiweb/grading/engine/test_bubble_cnn.py): Scripts huấn luyện và kiểm thử mô hình CNN.
- `templates/*.json`: Chứa tọa độ mẫu (coordinates) của các loại phiếu thi (VD: `template_default.json`, `template_28_02_00.json`...).

---

## 2. Input & Output Contract

### Input
- **Image File**: Đường dẫn ảnh phiếu thi (`.jpg`, `.png`).
- **Template Code**: Mã mẫu phiếu thi (VD: `40-08-06`, `28-02-00`).
- **Answer Key (JSON / String)**: Chuỗi đáp án đúng của bài thi hoặc mã đề (phần I, phần II, phần III).

### Output
Structure kết quả trả về từ `hi.py`:
- `success` (bool): `True` nếu nhận diện và chấm thành công.
- `made` (str): Mã đề thi nhận diện được từ phiếu.
- `sbd` (str): Số báo danh nhận diện được từ phiếu.
- `answers` (dict): Danh sách đáp án bóc tách được (Phần I, II, III).
- `score` (float): Tổng điểm đã tính toán.
- `correct_count` (int): Số câu trả lời đúng.
- `total_questions` (int): Tổng số câu.
- `error` (str): Thông báo lỗi nếu thất bại.

---

## 3. OMR Processing Pipeline (10 Bước Chính)

```
[Ảnh Đầu Vào]
     │
     ▼
1. Auto Deskew & Paper Contour Detection (Tìm 4 góc phiếu thi)
     │
     ▼
2. Perspective Transformation (Warp ảnh về kích thước chuẩn 1400x1920)
     │
     ▼
3. Printed Text Erasing (Lớp 1: Tô trắng chữ in A,B,C,D, SBD... trước threshold)
     │
     ▼
4. Morphological Cleaning & Preprocessing (Lọc nét mảnh, cân bằng sáng Adaptive Hist)
     │
     ▼
5. Printed Text Masking (Lớp 3: Safety net tô đen chữ in còn sót)
     │
     ▼
6. Section & Bubble Offset Detection (Căn chỉnh độ lệch dòng/cột)
     │
     ▼
7. Bubble Center Extraction (Dựa trên Template JSON coordinates)
     │
     ▼
8. Fill Intensity Evaluation / CNN Classification:
   - Cách 1: Thresholding (Mật độ pixel đen / Tổng pixel)
   - Cách 2: Deep Learning Inference via bubble_cnn.onnx
     │
     ▼
9. Answer Extraction & Decoding (Giải mã Phần I ABCD, Phần II Đúng/Sai, Phần III Điền số)
     │
     ▼
10. Scoring & Result Synthesis (Tính điểm theo quy tắc từng phần)
```

---

## 4. Key Parameters in `hi.py`

| Tham số | Giá trị mặc định | Giải thích / Vai trò |
| :--- | :--- | :--- |
| `WARP_WIDTH` | `1400` | Chiều rộng chuẩn của ảnh sau khi Perspective Transform. |
| `WARP_HEIGHT` | `1920` | Chiều cao chuẩn của ảnh sau khi Perspective Transform. |
| `BUBBLE_RADIUS` | `13` | Bán kính ô tròn tô đáp án (pixel trên ảnh warped 1400x1920). |
| `FILL_THRESHOLD` | `0.15` (0.15 - 0.38) | Ngưỡng mật độ pixel để xác định ô được tô hay ô rỗng. |
| `NAME_REGION` | `(255, 300, 745, 60)` | Vùng tọa độ crop ảnh tên thí sinh. |

---

## 5. Template System (`templates/*.json`)

Mỗi loại phiếu thi có cấu trúc tọa độ riêng được lưu trong thư mục `grading/engine/templates/`:
- Định nghĩa tọa độ điểm neo (markers), khu vực Số báo danh (SBD), Mã đề (MĐ), và khu vực câu hỏi (Phần I, II, III).
- Khi chấm bài, `grading/grader.py:_template_json_path()` sẽ tự động khớp `template_code` để nạp file JSON phù hợp.

---

## 6. Adapter Layer (`grading/grader.py`)

- `grader.py` đóng vai trò cầu nối giữa Django ORM và `hi.py`.
- Sử dụng `sys.path.insert(0, str(ENGINE_DIR))` để nạp module `hi.py`.
- Hàm chính: `grade_image(image_path, template_code, answer_key_json)` tiếp nhận yêu cầu từ Views, gọi `hi.py`, xử lý ngoại lệ và trả kết quả đã định dạng về cho Views.
