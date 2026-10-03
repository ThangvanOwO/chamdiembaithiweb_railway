# GradeFlow — tiếng Việt và thông báo quản trị, 03/10/2026

Đã xuất bản Android **1.0.1 / 2107**, cập nhật backend lên VPS và xác thực Firebase project `gradeflow-19d58`. Theo lựa chọn của người dùng, lần này xuất tệp cài đặt trước; chưa cài lên điện thoại và chưa xác nhận thông báo đến thiết bị khi app đóng.

## Tệp và cách sử dụng

- [APK cài trực tiếp cho điện thoại ARM64](<D:/chamtrac nghien v2/releases/GradeFlow-1.0.1-2107/GradeFlow-2107-arm64.apk>): 50.844.557 byte, versionCode **2107**, phiên bản **1.0.1**, package `vn.io.gradeflow.app`.
- [AAB để tải lên Google Play](<D:/chamtrac nghien v2/releases/GradeFlow-1.0.1-2107/GradeFlow-2107.aab>): 119.375.715 byte, versionCode **2107**. Kích thước AAB gồm nhiều kiến trúc, không phải kích thước tải xuống của từng người dùng.
- [Mã nguồn mobile đúng trạng thái đã đóng gói](<D:/chamtrac nghien v2/releases/GradeFlow-1.0.1-2107/mobile-source-2107.zip>): lưu toàn bộ giao diện hiện tại, gồm các thay đổi remake đang có. Không chứa khóa ký, cấu hình Firebase client, khóa Firebase máy chủ hoặc dữ liệu người dùng.
- [SHA-256](<D:/chamtrac nghien v2/releases/GradeFlow-1.0.1-2107/SHA256SUMS.txt>).

Trong app mới: **Tài khoản → Quản trị → Quản lý thông báo**. Mục quản trị chỉ hiện và API chỉ cho phép tài khoản superuser. Người dùng mở chuông trên trang chủ hoặc **Tài khoản → Thông báo**.

Quản trị viên soạn tiêu đề, nội dung, chọn thông tin/nhắc nhở/cập nhật, ngày hết hạn và tùy chọn gửi lên điện thoại. Lưu bản nháp, xem trước rồi xác nhận gửi. Thông báo đã gửi không sửa trực tiếp; có thể thu hồi khỏi hộp thông báo và tạo bản mới. Thu hồi không xóa thông báo Android đã nhận trước đó.

Người dùng có thể bật/tắt thông báo điện thoại, đọc từng thông báo hoặc đánh dấu tất cả đã đọc. Hộp thông báo vẫn hoạt động khi chưa cấp quyền thông báo Android. Nút cập nhật mở trang Google Play chính thức của GradeFlow, không mở URL tùy ý từ nội dung admin.

## Ảnh đã kiểm tra

Ảnh được dựng bằng Flutter widget test ở kích thước 390 × 844, tải font thật từ assets, không tải font qua mạng. Đây là kết quả dựng phần mềm, không phải ảnh chụp trên điện thoại.

- [Hộp thông báo](<D:/chamtrac nghien v2/artifacts/notifications_20261003/inbox.png>).
- [Quản lý thông báo](<D:/chamtrac nghien v2/artifacts/notifications_20261003/admin.png>).

## BUG FIX REPORT

- **ROOT CAUSE**:
  - Font DM Sans được Google Fonts chọn trước đây thiếu một số ký tự tiếng Việt trong bảng glyph, ví dụ `ư`, `ả`, `ậ`, `ề`, `ọ`, `ờ`. Các ký tự này phải dùng font thay thế, làm chữ không đồng nhất. Đã kiểm tra bảng cmap của font thay vì chỉ nhìn ảnh.
  - App chưa cấu hình locale Material tiếng Việt và chưa đóng gói đầy đủ font dùng cho giao diện.
  - Chưa có mô hình dữ liệu/hộp thông báo, đăng ký thiết bị FCM và tiến trình gửi riêng cho thông báo admin.
  - **Chưa kết luận nguyên nhân riêng của hiện tượng chữ/icon bị vỡ trong ảnh điện thoại.** Cần kiểm tra lại chính nút “Chọn đề này” trên máy thật với bản mới. Không tắt Impeller hoặc thay đổi renderer để thử đoán lỗi.
- **FILES CHANGED**:
  - Font và ngôn ngữ: [theme.dart](<D:/chamtrac nghien v2/gradeflow_app/lib/config/theme.dart>), [main.dart](<D:/chamtrac nghien v2/gradeflow_app/lib/main.dart>), [pubspec.yaml](<D:/chamtrac nghien v2/gradeflow_app/pubspec.yaml>), [fonts](<D:/chamtrac nghien v2/gradeflow_app/assets/fonts/Manrope-Regular.ttf>). Các lời gọi DM Sans đổi sang Manrope trong `stat_card`, `coach_mark_service`, `admin_test`, `admin_users`, `dashboard`, `exam_create`, `exam_import`, `exams`, `grade_result`, `history`, `results`, `scan`, `settings`.
  - Mobile thông báo: [notification_service.dart](<D:/chamtrac nghien v2/gradeflow_app/lib/services/notification_service.dart>), [notifications_screen.dart](<D:/chamtrac nghien v2/gradeflow_app/lib/screens/notifications_screen.dart>), [admin_notifications_screen.dart](<D:/chamtrac nghien v2/gradeflow_app/lib/screens/admin_notifications_screen.dart>), [notification_button.dart](<D:/chamtrac nghien v2/gradeflow_app/lib/widgets/notification_button.dart>), [profile_screen.dart](<D:/chamtrac nghien v2/gradeflow_app/lib/screens/profile_screen.dart>).
  - Android: [AndroidManifest.xml](<D:/chamtrac nghien v2/gradeflow_app/android/app/src/main/AndroidManifest.xml>), [MainActivity.kt](<D:/chamtrac nghien v2/gradeflow_app/android/app/src/main/kotlin/vn/io/gradeflow/app/MainActivity.kt>).
  - Backend: [notification_views.py](<D:/chamtrac nghien v2/api/notification_views.py>), [urls.py](<D:/chamtrac nghien v2/api/urls.py>), [models.py](<D:/chamtrac nghien v2/dashboard/models.py>), [announcements.py](<D:/chamtrac nghien v2/dashboard/announcements.py>), [admin.py](<D:/chamtrac nghien v2/dashboard/admin.py>), [migration](<D:/chamtrac nghien v2/dashboard/migrations/0001_initial.py>), [worker](<D:/chamtrac nghien v2/dashboard/management/commands/send_announcements.py>).
  - Vận hành: [Docker local](<D:/chamtrac nghien v2/docker-compose.local.yml>), [Docker VPS](<D:/chamtrac nghien v2/docker-compose.vps.yml>), [requirements.txt](<D:/chamtrac nghien v2/requirements.txt>), [.gitignore](<D:/chamtrac nghien v2/.gitignore>), [.dockerignore](<D:/chamtrac nghien v2/.dockerignore>), [chính sách bảo mật](<D:/chamtrac nghien v2/templates/website/privacy.html>), [API_ARCHITECTURE.md](<D:/chamtrac nghien v2/docs/API_ARCHITECTURE.md>).
  - Kiểm thử: [backend](<D:/chamtrac nghien v2/tests/test_notifications.py>), [mobile](<D:/chamtrac nghien v2/gradeflow_app/test/notifications_test.dart>).
- **CHANGES MADE**:
  - Manrope có đầy đủ ký tự tiếng Việt; đóng gói 7 độ đậm 200–800 và giấy phép OFL. Tắt tải font lúc chạy, đặt locale `vi_VN` cho cả màn khởi động và app chính.
  - Hộp thông báo có trạng thái đã đọc riêng theo tài khoản; bản nháp, thông báo thu hồi và hết hạn không xuất hiện ở người dùng. Các API mới bổ sung độc lập với API chấm bài hiện có.
  - Thông báo đẩy dùng FCM, quyền Android `POST_NOTIFICATIONS`, kênh tiếng Việt `gradeflow_announcements`; chạm thông báo mở hộp thông báo/chi tiết tương ứng. Bản mới giữ quảng cáo tắt.
  - Firebase được khởi tạo khi cần, tiến trình gửi riêng kiểm tra hàng đợi mỗi 10 giây. Chỉ lưu lớp lỗi, không lưu nội dung lỗi chứa token/khóa. Có retry tối đa 5 lần và chống gửi lại khi bấm gửi nhiều lần.
  - Thiết bị gắn với tài khoản và phiên hiện tại. Hàng đợi giữ hash đích/phiên, bỏ qua đích đã đăng xuất, đổi tài khoản hoặc thay FCM token. App bỏ qua phản hồi muộn của tài khoản cũ. Tắt thông báo được lưu trên máy và đồng bộ lại khi có mạng.
  - Khóa người dùng cung cấp được chuyển từ `tools` sang `.secrets/firebase-admin.json`, Git/Docker loại trừ và chỉ mount đọc tại runtime. VPS lưu cùng vị trí với quyền file `600`, thư mục `700`. Khóa không nằm trong APK/AAB, image hoặc Git.
  - Lượt sửa này không đổi thuật toán nhận diện, độ phân giải, luồng chụp, crop, tham số camera hay mẫu OMR. `scan_screen.dart` chỉ đổi lời gọi font trong phần giao diện; các thay đổi camera đã tồn tại từ trước trong working tree không bị sửa hoặc xóa.
- **TESTS RUN**:
  - Docker local: `docker compose -f docker-compose.local.yml up -d --build`, kiểm tra container và worker.
  - Local và VPS: `python manage.py test tests.test_notifications -v 1`; `python -m unittest discover -s tests -p test_reviewed_live_model.py -v` chạy trong container web.
  - Flutter: `notifications_test.dart`, `remake_exam_flow_test.dart`, `mobile_wallet_navigation_test.dart`, `mobile_remake_access_test.dart`, `widget_test.dart`, `admob_test.dart`. Chạy lại 4 ca thông báo sau các chỉnh sửa cuối; xuất ảnh bằng `CAPTURE_NOTIFICATIONS=1`.
  - Analyzer cho service, 2 màn thông báo, nút chuông, main và test mới.
  - Firebase Admin SDK `messaging.send(..., dry_run=True)` trên local và VPS: xác thực và mô phỏng gửi, **không phát thông báo thật**.
  - Build AAB release và APK ARM64 release bằng build-name `1.0.1`, build-number `2107`; bundletool validate/đọc version; jarsigner/apksigner kiểm tra chữ ký; zipalign và kiểm tra ELF native 16 KB.
  - Kiểm tra HTTPS công khai: `/ads.txt`, `/chinh-sach-bao-mat/`, `/accounts/register/`, `/api/v1/notifications/`.
- **TEST RESULTS**:
  - **13/13** kiểm thử thông báo backend đạt cả local và VPS. Bao gồm quyền truy cập, tiếng Việt, bản nháp, ngày hết hạn, gửi lặp, trạng thái đọc/tất cả đã đọc theo tài khoản, thu hồi, thay tài khoản, đăng xuất, retry và kiểm soát thiết bị.
  - **14/14** kiểm thử nhận diện đã duyệt đạt cả local và VPS. Không phát sinh đáp án giả ở ô trắng và vẫn giữ quy tắc tô đôi/vùng mơ hồ.
  - Nhóm mobile liên quan: **43 đạt, 24 bỏ qua**; các ca bỏ qua thuộc quảng cáo đang bị tắt. Lần chạy cuối riêng thông báo: **4/4 đạt**, gồm font assets thật, chi tiết/đã đọc, phản hồi muộn khi đổi tài khoản, hủy xem trước không gửi và admin ở cỡ chữ 200%.
  - Analyzer phạm vi mới: **No issues found**. Bảng glyph Manrope chứa đầy đủ các ký tự của chuỗi thử tiếng Việt.
  - AAB validate thành công, version **2107**; APK version **2107**, chữ ký release v2 hợp lệ, cùng chứng thư upload hiện có. AAB có `PAGE_ALIGNMENT_16K`; **0 thư viện 64-bit lỗi ELF alignment**, APK zipalign 16 KB đạt.
  - Manifest cuối có quyền thông báo, Analytics deactivated và FCM auto-init mặc định false; `MobileAdsInitProvider`/`AdService` đều `enabled=false`. Quyền AD_ID vẫn do SDK quảng cáo hiện có gộp vào; lượt này không khai báo thay cho người dùng trên Play Console.
  - Firebase dry-run đạt trên cả hai môi trường. Cơ sở dữ liệu thật sau kiểm tra: **0 thông báo, 0 thiết bị, 0 lượt gửi chờ**; không để lại thông báo giả cho người dùng.
  - HTTP công khai: ba trang **200**, hộp thông báo không đăng nhập **401 JSON** như thiết kế. Chính sách bảo mật công khai đã có phần FCM.
  - VPS web/db/proxy healthy, worker chạy. Một lần đo khi rảnh: worker **66,09 MiB / 0,00% CPU**, web **135,8 MiB / 0,03% CPU**. Đây là số đo tức thời, không phải benchmark tải chấm bài.
- **REGRESSION RISK**:
  - Font mới thay đổi độ rộng chữ; đã kiểm tra màn mới ở 390 px/cỡ chữ 200% và các ca điều hướng liên quan, chưa kiểm tra mọi màn trên điện thoại.
  - Chưa xác nhận hình chữ/icon bị vỡ trên GPU máy thật và chưa kiểm thử thông báo foreground/background/terminated trên thiết bị. Không coi dry-run là bằng chứng thiết bị đã nhận thông báo.
  - Android cần quyền thông báo và dịch vụ Google phù hợp. Khi người dùng **Buộc dừng** app trong cài đặt hệ thống, cần mở lại app để nhận FCM; khác với đóng app thông thường. Tham khảo [Firebase receive messages](https://firebase.google.com/docs/cloud-messaging/flutter/receive-messages).
  - FCM không đảm bảo người dùng đã xem hay thiết bị đã nhận khi SDK trả message ID. Admin hiển thị “Firebase đã nhận” thay vì kết luận giao thành công đến người dùng.
  - Worker có thể gửi lại nếu tiến trình dừng sau khi FCM nhận nhưng trước khi lưu trạng thái; notification tag theo ID giúp thay thế thông báo trùng trên Android. Không cam kết gửi đúng một lần trong mọi tình huống sự cố.
  - APK ký bằng khóa upload local; cài cập nhật đè phụ thuộc chữ ký của bản đang có. Chưa cài/gỡ bất cứ app nào trên điện thoại trong lượt này.
- **UNRELATED ISSUES FOUND**:
  - Full-project analyzer còn các cảnh báo có sẵn ngoài phạm vi này; không dọn lại toàn bộ project để tránh thay đổi luồng camera.
  - Working tree đã có nhiều thay đổi remake/mobile và tài liệu từ các lượt trước. Chỉ commit backend/thông báo của lượt này; giữ nguyên phần còn lại và xuất ZIP nguồn mobile đúng trạng thái build.

## VPS và đường lui

Backend đã commit/push **`686c07f`** lên `ThangvanOwO/chamdiembaithiweb_railway/main`, VPS đã pull và dựng lại bằng `docker-compose.vps.yml`. Mã backend, cấu hình local/VPS và test mới có trên Git; khóa riêng không được commit.

Trước cập nhật đã lưu:

- Image: `gradeflow-vps-web:before-notifications-20261003`.
- VPS: `/home/ubuntu/gradeflow/scratch/notifications_before_20261003/commit.txt`, `docker-compose.vps.yml`, `database.sql` (41.669.645 byte, quyền `600`). Commit trước: `42d35fb`.
- SQLite local: `scratch/notifications_backup/db_before.sqlite3`.
- Điểm lui giao diện trước remake vẫn giữ ở `scratch/mobile_remake_20261001/rollback/mobile-source-before.zip`. ZIP `mobile-source-2107.zip` lưu riêng mã mobile hiện tại để tránh mất các thay đổi chưa commit.

Nếu cần quay lại backend cũ, chạy trên VPS:

```bash
cd /home/ubuntu/gradeflow
docker compose --env-file .env.vps -f docker-compose.vps.yml stop notifications
docker tag gradeflow-vps-web:before-notifications-20261003 gradeflow-vps-web:latest
docker compose --env-file .env.vps -f docker-compose.vps.yml up -d --no-deps --no-build --pull never --force-recreate web
docker compose --env-file .env.vps -f docker-compose.vps.yml exec -T proxy nginx -s reload
```

Giữ các bảng mới và dữ liệu đang có; image cũ không sử dụng bảng thông báo. Chỉ phục hồi bản sao cơ sở dữ liệu nếu có lý do độc lập, vì phục hồi sẽ thay dữ liệu được tạo sau thời điểm sao lưu.

## Kiểm tra trên máy thật sau khi cài

1. Kiểm tra “Chọn đề này”, đăng nhập/đăng ký và một lượt quét camera, đối chiếu bản hiện tại.
2. Mở Thông báo, bấm Bật thông báo và cấp quyền Android; admin xác nhận có thiết bị đăng ký.
3. Admin tạo thông báo thử dành cho đợt kiểm tra đã thống nhất, xem trước và gửi; thử khi app đang mở, chạy nền và đóng bình thường.
4. Chạm thông báo để mở chi tiết, đánh dấu đã đọc, thử đăng xuất/đổi tài khoản và tắt thông báo.

Các bước thiết bị còn lại chưa thực hiện vì người dùng chọn xuất bản cài đặt trước.
