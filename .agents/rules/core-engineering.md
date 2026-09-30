# Core Engineering Rules

> **Áp dụng cho**: Toàn bộ công việc phân tích, phát triển và bảo trì trong codebase GradeFlow.

---

## 1. Context Loading & Efficiency

1. **Đọc Documentation trước**: Khi bắt đầu một task lớn hoặc tìm hiểu dự án, AI **bắt buộc** đọc [`docs/AI_CONTEXT.md`](file:///c:/Users/Thang/Downloads/chamdiembaithiweb/docs/AI_CONTEXT.md) trước tiên.
2. **Chống Tải Context Tràn Lan**:
   - **KHÔNG** dùng tool scan/read toàn bộ repository nếu task không yêu cầu.
   - Chỉ load và đọc các file liên quan trực tiếp đến task được giao.
   - Trace dependency sang file khác **chỉ khi** có bằng chứng về mối liên hệ gọi hàm hoặc dữ liệu.
3. **Ưu tiên Knowledge Base**:
   - Khi công việc lớn hoặc context window bắt đầu phình to, ưu tiên tra cứu tài liệu kiến trúc có sẵn trong `docs/` (`ARCHITECTURE.md`, `OMR_ENGINE.md`, `API_ARCHITECTURE.md`, `MOBILE_ARCHITECTURE.md`, `KNOWN_RISKS.md`) thay vì đọc lại toàn bộ mã nguồn.

---

## 2. Evidence-Based & No-Guessing Policy

1. **Không Tự Đoán**:
   - Nếu không đủ thông tin về một hàm, schema, API endpoint hoặc tham số, AI phải tiếp tục dùng tool đọc code để tìm bằng chứng thực tế.
   - Nếu không thể xác minh thông tin từ mã nguồn, AI **bắt buộc** ghi nhận bằng nhãn `[NEEDS VERIFICATION]`.
   - **KHÔNG** tạo tài liệu giả hoặc đưa ra giả định không có căn cứ.
2. **Dừng Khi Thiếu Thông Tin**:
   - Nếu đã tra cứu nhưng vẫn không đủ thông tin để xác định nguyên nhân hoặc giải pháp, AI phải dừng lại và báo cáo rõ những thông tin còn thiếu cho người dùng.

---

## 3. Scope Control & Refactoring Limits

1. **Giới Hạn Phạm Vi (Minimal Scope)**:
   - Chỉ làm đúng những gì task yêu cầu. Không sửa nhiều module không liên quan.
   - **KHÔNG** tự ý refactor code ngoài phạm vi của bug/task.
2. **Không Tự Ý Fix Technical Debt**:
   - Khi task chỉ yêu cầu sửa bug, **KHÔNG** tự ý sửa nợ kỹ thuật (technical debt), dọn dẹp file, hoặc tái cấu trúc module.
3. **Ghi Nhận Vấn Đề Kiến Trúc**:
   - Nếu phát hiện vấn đề kiến trúc hoặc mã xấu không liên quan trực tiếp đến task hiện tại: **Ghi nhận vào phần báo cáo** ("UNRELATED ISSUES FOUND") nhưng **KHÔNG** tự ý sửa code.
