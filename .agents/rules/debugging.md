# Debugging & Bug-Fixing Rules

> **Áp dụng cho**: Tất cả các công việc chẩn đoán lỗi, xử lý bug và kiểm thử trong dự án GradeFlow.

---

## 1. Quy Trình 9 Bước Sửa Lỗi Bắt Buộc (Mandatory Debugging Workflow)

Khi nhận được yêu cầu sửa lỗi, AI **bắt buộc** tuân thủ 9 bước theo đúng thứ tự:

```
1. Understand  ──► Hiểu chính xác triệu chứng lỗi và mong muốn của người dùng.
       │
2. Locate      ──► Định vị module/file/dòng code nghi vấn dựa trên log hoặc stack trace.
       │
3. Trace       ──► Trace luồng dữ liệu từ input đầu vào đến vị trí phát sinh lỗi.
       │
4. Reproduce   ──► Xác nhận kịch bản hoặc viết test case để tái hiện lỗi.
       │
5. Diagnose    ──► Xác định chính xác NGUYÊN NHÂN GỐC RỄ (Root Cause) bằng chứng cứ log/code.
       │
6. Plan        ──► Lên phương án sửa đổi nhỏ nhất (Minimal Fix) ít rủi ro nhất.
       │
7. Minimal Fix ──► Thực hiện chỉnh sửa mã nguồn ngắn gọn, đúng trọng tâm.
       │
8. Test        ──► Chạy verification/test để xác nhận lỗi đã được khắc phục hoàn toàn.
       │
9. Review Diff ──► Review lại toàn bộ git diff để đảm bảo không dư thừa hoặc gây side effect.
```

---

## 2. Nguyên Tắc An Toàn Khi Sửa Lỗi

1. **Không Sửa Code Khi Chưa Xác Định Root Cause**:
   - **Tuyệt đối KHÔNG** thử sai (trial-and-error), sửa ngẫu nhiên hoặc vá triệu chứng khi chưa tìm ra nguyên nhân gốc rễ.
2. **Bảo Vệ Bộ Test Case**:
   - **KHÔNG** xóa unit test, **KHÔNG** comment out test thất bại hoặc chỉnh sửa câu lệnh assert chỉ để làm cho test pass.
   - Nếu test fail, phải tìm nguyên nhân hỏng hợp đồng mã nguồn thay vì sửa test.
3. **Sử Dụng Minimal Fix**:
   - Chỉ thay đổi số dòng code tối thiểu cần thiết để sửa bug. Không nhân cơ hội này để dọn dẹp các hàm xung quanh.

---

## 3. Mandatory Post-Bugfix Report Format

Sau khi hoàn thành bất kỳ bug fix nào, AI **bắt buộc** trình bày báo cáo tổng kết theo đúng định dạng sau:

```markdown
### BUG FIX REPORT

- **ROOT CAUSE**: [Mô tả chi tiết nguyên nhân gốc rễ gây ra lỗi]
- **FILES CHANGED**: [Danh sách file đã sửa đổi kèm đường dẫn clickable]
- **CHANGES MADE**: [Tóm tắt các chỉnh sửa đã thực hiện]
- **TESTS RUN**: [Các lệnh kiểm thử/verification command đã chạy]
- **TEST RESULTS**: [Kết quả đầu ra của test (Pass/Fail/Log)]
- **REGRESSION RISK**: [Đánh giá rủi ro ảnh hưởng tác dụng phụ tới các module khác]
- **UNRELATED ISSUES FOUND**: [Các vấn đề kiến trúc/code nợ phát hiện thêm nhưng chưa sửa]
```
