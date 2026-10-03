# GradeFlow 1.0.1 — 2107

- **GradeFlow-2107-arm64.apk**: bản cài trực tiếp cho điện thoại Android ARM64, 50.844.557 byte; versionCode 2107. Chưa được cài lên máy thật trong lượt này.
- **GradeFlow-2107.aab**: dùng khi tạo bản phát hành Google Play, versionCode 2107; không cài trực tiếp như APK. Chưa được tải lên Play trong lượt này.
- **mobile-source-2107.zip**: mã nguồn mobile hiện tại; không chứa cấu hình Firebase client hoặc khóa ký/khóa máy chủ. Các cấu hình đó vẫn được lưu riêng trên máy.
- **SHA256SUMS.txt**, **native-aab.json**, **native-apk.json**: hash và kiểm tra thư viện native 16 KB.

VPS đã có backend thông báo. Trong app mới, quản trị viên mở **Tài khoản → Quản trị → Quản lý thông báo**; người dùng mở chuông hoặc **Tài khoản → Thông báo**. Bật thông báo và cấp quyền Android để đăng ký điện thoại với Firebase. Quảng cáo vẫn tắt.

Báo cáo: [MOBILE_NOTIFICATIONS_FONT_20261003.md](<D:/chamtrac nghien v2/docs/MOBILE_NOTIFICATIONS_FONT_20261003.md>).

## Ghi chú phát hành

```text
<vi>
- Đồng bộ font chữ và giao diện tiếng Việt.
- Thêm hộp thông báo, trạng thái đã đọc và tùy chọn bật/tắt thông báo điện thoại.
- Thêm mục Quản lý thông báo cho quản trị viên: soạn nháp, xem trước, gửi và thu hồi.
- Hỗ trợ nhận nhắc nhở và thông báo cập nhật qua Firebase.
- Tiếp tục tắt quảng cáo trong giai đoạn thử nghiệm.
</vi>
```
