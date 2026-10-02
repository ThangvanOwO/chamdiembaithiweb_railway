# GradeFlow — Bản kiểm thử kín không quảng cáo 2104

Đã chuẩn bị ngày 02/10/2026. Ứng dụng Android có thể đăng ký bằng họ tên, tên tài khoản, mật khẩu và xác nhận mật khẩu. Backend đã triển khai lên `https://gradeflow.io.vn`. Chưa upload hoặc phát hành gói này trong Play Console.

## BUG FIX REPORT

- **ROOT CAUSE**: Đăng ký cũ yêu cầu SMTP và Turnstile nên chưa mở khi thiếu cấu hình. Giao diện mobile gửi email và tên tách đôi, đồng thời hướng dẫn mật khẩu 6 ký tự khác với yêu cầu 8 ký tự của backend. Quảng cáo có thể khởi tạo UMP từ lúc mở app và tự khởi tạo SDK qua Android provider; chỉ giấu banner không đủ để chặn các lời gọi này.
- **FILES CHANGED**:
  - Backend: [forms.py](<D:/chamtrac nghien v2/accounts/forms.py>), [registration.py](<D:/chamtrac nghien v2/accounts/registration.py>), [views.py](<D:/chamtrac nghien v2/accounts/views.py>), [API auth](<D:/chamtrac nghien v2/api/views.py>), [settings.py](<D:/chamtrac nghien v2/chamdiemtudong/settings.py>), [register.html](<D:/chamtrac nghien v2/templates/accounts/register.html>), [login.html](<D:/chamtrac nghien v2/templates/accounts/login.html>), [.env.vps.example](<D:/chamtrac nghien v2/.env.vps.example>).
  - Mobile: [admob_config.dart](<D:/chamtrac nghien v2/gradeflow_app/lib/config/admob_config.dart>), [ad_service.dart](<D:/chamtrac nghien v2/gradeflow_app/lib/services/ad_service.dart>), [credit_wallet_card.dart](<D:/chamtrac nghien v2/gradeflow_app/lib/widgets/credit_wallet_card.dart>), [auth_service.dart](<D:/chamtrac nghien v2/gradeflow_app/lib/services/auth_service.dart>), [register_screen.dart](<D:/chamtrac nghien v2/gradeflow_app/lib/screens/register_screen.dart>), [login_screen.dart](<D:/chamtrac nghien v2/gradeflow_app/lib/screens/login_screen.dart>), [Gradle](<D:/chamtrac nghien v2/gradeflow_app/android/app/build.gradle.kts>), [AndroidManifest.xml](<D:/chamtrac nghien v2/gradeflow_app/android/app/src/main/AndroidManifest.xml>).
  - Kiểm thử: [username signup](<D:/chamtrac nghien v2/accounts/test_username_signup.py>), [closed testing](<D:/chamtrac nghien v2/gradeflow_app/test/closed_testing_test.dart>), [AdMob](<D:/chamtrac nghien v2/gradeflow_app/test/admob_test.dart>), [mobile forms](<D:/chamtrac nghien v2/gradeflow_app/test/mobile_remake_access_test.dart>). Hợp đồng mới được ghi trong [API_ARCHITECTURE.md](<D:/chamtrac nghien v2/docs/API_ARCHITECTURE.md>).
- **CHANGES MADE**: Công tắc `GRADEFLOW_ADS_ENABLED` mặc định `false`, chặn SDK/UMP/banner/interstitial/rewarded và ẩn nút nhận thưởng. Android provider và service đọc cùng công tắc, đều `enabled=false` trong AAB đã tạo. Đăng ký username bật bằng `ALLOW_USERNAME_SIGNUP=1`; không gán email hoặc giả xác minh email. Giữ mật khẩu băm, kiểm tra độ mạnh, CSRF, giới hạn đăng ký 5 lần POST/IP/giờ, theo dõi multi-account và quyền người dùng thường. Username không dấu, chuẩn hóa chữ thường, dài 3–30 ký tự; họ tên bắt buộc. Google OAuth và đăng ký email xác minh cũ giữ nguyên. Không đổi schema, điểm thưởng hay xử lý camera.
- **TESTS RUN**:
  - Docker local: `docker compose -f docker-compose.local.yml up -d --build` và kiểm tra dịch vụ.
  - `docker compose -f docker-compose.local.yml exec -e DJANGO_DEBUG=True -T web python manage.py test accounts website --verbosity 1`.
  - Flutter: closed-testing, đăng ký/đăng nhập, logout, server settings, tạo đề, ví và điều hướng; thêm AdMob suite riêng với `--dart-define=GRADEFLOW_ADS_ENABLED=true` để kiểm tra đường bật lại.
  - Analyzer 9 tệp liên quan; release AAB với `--build-number=2104 --dart-define=GRADEFLOW_ADS_ENABLED=false`.
  - [bundletool của Google](https://developer.android.com/tools/bundletool): validate AAB và dump manifest trực tiếp từ AAB; kiểm tra chữ ký và so sánh chứng thư với bản 2103.
  - Kiểm thử HTTP thật ở local và VPS: form đăng ký, tạo tài khoản, lấy hồ sơ, đăng nhập lại, đăng xuất, token bị thu hồi, đăng nhập web bằng username. Tài khoản QA và điểm chào mừng chưa sử dụng đã được dọn đúng theo ID sinh trong từng lần thử.
- **TEST RESULTS**: Backend 127 ca: **122 đạt, 5 bỏ qua** vì các ca đó cần Node trong container. Mobile **46 đạt**. Đường quảng cáo bật lại **24 đạt**. Analyzer không có lỗi. Kiểm thử bản tắt quảng cáo ghi nhận **0 lời gọi Ads/UMP**, ví không xin reward ticket. Native manifest trong AAB xác nhận provider/service quảng cáo tắt. Bundletool validate và xác minh chữ ký đạt; cùng chứng thư upload với 2103. VPS db/web/proxy healthy. Cả HTTP local và HTTPS công khai đều đạt. Sáu tệp camera/OMR được kiểm tra hash, không thay đổi trong công việc này.
- **REGRESSION RISK**: Chưa kiểm thử bản 2104 trực tiếp trên điện thoại vì không có thiết bị ADB kết nối. Chưa có kết quả tiếp nhận/duyệt của Play Console. Username mới không có email khôi phục, nên giao diện hướng dẫn liên hệ admin khi quên mật khẩu. Giới hạn IP tính cả lần nhập lỗi và có thể ảnh hưởng người kiểm thử dùng cùng Wi-Fi. Tắt quảng cáo áp dụng cho bản Android 2104; bản cũ đang được cài vẫn có cấu hình quảng cáo cũ. Quảng cáo công khai trên website không nằm trong công tắc Android.
- **UNRELATED ISSUES FOUND**: Các thay đổi remake/training trước đó vẫn được giữ nguyên trong working tree. Backend của nhiệm vụ này đã push và triển khai ở commit `32eaa22`; các thay đổi mobile đang có trước đó chưa được gộp vào commit backend. Các cảnh báo chứng thư tự ký/timestamp/ZIP stream từ jarsigner được lưu đầy đủ; `jar verified` và bundletool validate đều trả mã 0. Không coi kiểm tra chữ ký cục bộ là xác nhận của Play Console.

## Gói để upload

[GradeFlow-closed-testing-no-ads-release-2104.aab](<D:/chamtrac nghien v2/tests/test_ketqua/closed_testing_20261002/GradeFlow-closed-testing-no-ads-release-2104.aab>)

- Package: `vn.io.gradeflow.app`; versionName `1.0.0`, versionCode `2104`.
- Kích thước: 74.126.109 byte (khoảng 70,7 MiB).
- SHA-256: `FB103CB88275A507D7869F57BB5F5A3653DE069AF9CFF84131470DB3FEE51D49`.
- Upload gói này vào bản phát hành của kênh kiểm thử kín. Người kiểm thử cần cập nhật sang bản 2104 để dùng cấu hình không quảng cáo.
- Log và [artifact-manifest.json](<D:/chamtrac nghien v2/tests/test_ketqua/closed_testing_20261002/artifact-manifest.json>) nằm cùng thư mục. Bản AAB 2103 trước đó vẫn được giữ ở thư mục `admob_policy_20261002`.

## Bật lại và đường lui

Để đóng đăng ký username mới, đặt `ALLOW_USERNAME_SIGNUP=0` trong `.env.vps`, rồi chạy trên VPS:

```sh
cd /home/ubuntu/gradeflow
docker compose --env-file .env.vps -f docker-compose.vps.yml up -d --no-deps --force-recreate web
```

Tài khoản đã tạo vẫn đăng nhập được. Muốn bật lại quảng cáo, phải tạo và phát hành bản Android mới với `--dart-define=GRADEFLOW_ADS_ENABLED=true`, sau khi đã hoàn tất các cấu hình quảng cáo cần thiết. Không thể đổi công tắc này từ xa trên AAB 2104.

Nguồn trước thay đổi được sao lưu ở `D:\chamtrac nghien v2\scratch\closed_testing_before_20261002_1345` (17 tệp ứng dụng/cấu hình, danh sách hash). Camera không thuộc bản sao lưu này vì không sửa. VPS giữ image `gradeflow-vps-web:closed-testing-before-20261002`, commit trước `3684d9d` và bản cấu hình riêng tại `/home/ubuntu/gradeflow/scratch/closed_testing_before_20261002_1400`; không đưa cấu hình chứa secret lên Git.

Các lần kiểm thử đầu tiên phát hiện cấu hình môi trường/harness: HTTP test suite dùng cấu hình production bị chuyển HTTPS; fixture tiếng Việt thiếu header UTF-8; dọn QA bị chặn bởi sổ tín dụng; probe HTTP nội bộ không tự gửi Secure cookie. Các lỗi này đã được xác định và sửa ở cách chạy/harness, không hạ bảo vệ của ứng dụng. Các log harness ban đầu được giữ cùng kết quả cuối.
