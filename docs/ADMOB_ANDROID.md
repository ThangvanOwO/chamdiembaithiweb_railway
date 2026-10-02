# AdMob trong GradeFlow Android

## Cấu hình

- App ID: `ca-app-pub-6695808615282253~1245632973` trong `gradeflow_app/android/app/src/main/AndroidManifest.xml` (không có dấu gạch chéo trước `~`).
- Banner: `ca-app-pub-6695808615282253/5100942496`.
- Interstitial: `ca-app-pub-6695808615282253/2060021199`.
- Unit ID và chế độ thử nằm trong `gradeflow_app/lib/config/admob_config.dart`.
- SDK: `google_mobile_ads`, tích hợp Android. iOS/web/desktop không gửi yêu cầu quảng cáo; muốn bật iOS cần App ID và unit ID riêng.

## Hành vi

- Banner inline adaptive cuộn cùng nội dung: ở Tổng quan khi đã có đề hoặc kết quả; ở cuối danh sách Bài thi/Lịch sử khi có nội dung khớp bộ lọc. Không có banner trên trang trống, tìm kiếm không có kết quả, Tài khoản hoặc màn hình quét phiếu.
- Banner dùng chiều rộng thực tế sau padding/safe area, giới hạn chiều cao yêu cầu 120dp và lấy kích thước thực tế từ SDK sau khi tải. Có khoảng cách 24dp phía trên/dưới. Chỉ tab đang mở được tải banner; tab ẩn hủy quảng cáo. Banner ẩn khi bàn phím mở hoặc chưa tải được. Các trang mở đè lên MainShell, bao gồm camera, không có banner.
- Một bộ đếm dùng chung cho đổi tab khác, mở trang, quay lại trang và thay thế trang hiện tại. Không tính trang đầu tiên, bấm lại tab hiện tại, dialog, bottom sheet hoặc quay về từ nền.
- Sau ít nhất 5 lần chuyển màn hình, interstitial đã tải sẵn chỉ được phép hiện **sau khi lưu đề mới thành công và trước khi trở về danh sách**. Trang lưu đề phải vẫn đang mở, ứng dụng ở foreground và không trong hướng dẫn. Chờ đóng quảng cáo rồi mới trở về danh sách. SDK xác nhận hiển thị mới đặt lại bộ đếm. Chuyển tab, mở trang hoặc quay lại không tự hiện quảng cáo.
- Không có lời gọi hiển thị interstitial trong camera, trả ảnh, chấm bài, phiên liên tục, trang tài khoản, cài đặt hoặc kết quả. Không thay đổi luồng camera/chấm để tạo điểm hiển thị quảng cáo.
- Nếu chưa có quảng cáo hoặc mất mạng: tiếp tục sử dụng ứng dụng bình thường, giữ tối đa một lượt chờ. Tải thành công muộn không tự bật quảng cáo; chỉ lần lưu đề thành công tiếp theo mới có thể hiển thị nếu các điều kiện cho phép. Tải lỗi được thử lại sau 60 giây.
- Đăng xuất xóa bộ đếm và quảng cáo tải sẵn.

## Quyền riêng tư và chế độ thử

Ứng dụng cập nhật UMP một lần mỗi lần khởi động, ngay sau khung hình đầu tiên, kể cả trước đăng nhập. Bước đăng nhập dùng chung tác vụ consent đang chạy để tránh hai biểu mẫu đồng thời. Chỉ khởi tạo/tải quảng cáo trong phiên đăng nhập khi `canRequestAds()` cho phép. Nếu UMP yêu cầu, mục **Tài khoản → Quyền riêng tư quảng cáo** cho phép mở lại lựa chọn; quảng cáo tạm dừng trong lúc biểu mẫu mở. Lựa chọn mới được kiểm tra lại qua UMP trước khi tải quảng cáo tiếp. Lỗi mở biểu mẫu có thông báo để người dùng thử lại. Khi cập nhật consent thất bại, SDK UMP quyết định có thể dùng consent phiên trước hay không; ứng dụng không tự giả định sự đồng ý.

### Tạo và Publish biểu mẫu UMP

1. Đăng nhập [AdMob](https://admob.google.com/), mở **Privacy & messaging → European regulations → Create** (hoặc **Manage → Create message**).
2. Chọn ứng dụng GradeFlow có App ID `ca-app-pub-6695808615282253~1245632973`; không nhập Banner/Interstitial Unit ID thay cho App ID.
3. Nhập tên ứng dụng và URL chính sách quyền riêng tư: `https://gradeflow.io.vn/chinh-sach-bao-mat/`. Trang công khai không yêu cầu đăng nhập, không tải quảng cáo/biểu mẫu consent; email tiếp nhận yêu cầu dữ liệu là `zephuyaa@gmail.com`.
4. Chọn ngôn ngữ phù hợp, lựa chọn người dùng và khu vực hiển thị. **GDPR countries** áp dụng EEA/UK/Thụy Sĩ; **Everywhere** hiển thị toàn cầu nếu nhà phát hành chọn phạm vi đó. Có thể bật **Do not consent** để người dùng từ chối ngay từ trang đầu.
5. Xem lại biểu mẫu, nhấn **Publish**, xác nhận trạng thái đã xuất bản và đúng ứng dụng.

Hướng dẫn chính thức: [Tạo thông báo](https://support.google.com/admob/answer/10113207?hl=vi), [URL chính sách quyền riêng tư](https://support.google.com/admob/answer/10113106?hl=vi).

### Kiểm thử biểu mẫu

UMP chỉ hiện biểu mẫu khi SDK xác định cần thu thập consent. Ở Việt Nam, biểu mẫu chỉ nhắm EEA/UK/Thụy Sĩ có thể không xuất hiện. Giả lập vùng EEA trên thiết bị thử đã đăng ký:

```powershell
& C:\flutter\bin\flutter.bat run --debug --dart-define=UMP_DEBUG_GEOGRAPHY=eea
```

Muốn thử lại trải nghiệm lần đầu, thêm `--dart-define=UMP_RESET_CONSENT=true` cho bản thử đó. Mặc định không reset consent. Các cờ địa lý `eea`, `us`, `other` và reset chỉ hoạt động khi dùng quảng cáo thử; release quảng cáo thật bỏ qua toàn bộ cờ UMP debug. Không bật reset cho bản dùng thường xuyên. Debug vẫn cần biểu mẫu đã Publish với App ID thật; cờ giả lập không khắc phục lỗi thiếu biểu mẫu trong tài khoản.

Debug/profile tự dùng unit quảng cáo thử của Google. Release mặc định dùng các unit ID ở trên. Để kiểm thử một bản release bằng quảng cáo thử:

```powershell
Set-Location 'D:\chamtrac nghien v2\gradeflow_app'
& C:\flutter\bin\flutter.bat build apk --release --dart-define=ADMOB_TEST_ADS=true
```

### Đăng ký thiết bị thử (addTestDevice)

Trong Flutter, API tương ứng là `MobileAds.instance.updateRequestConfiguration(RequestConfiguration(testDeviceIds: ...))`. Ứng dụng chờ cấu hình này hoàn tất **trước khi khởi tạo SDK và trước mọi yêu cầu banner/interstitial**. Nếu bước cấu hình lỗi, quảng cáo chưa được bật. Chỉ áp dụng ở debug/profile hoặc release có `ADMOB_TEST_ADS=true`; release thông thường không đăng ký thiết bị thử.

Lấy chuỗi Test Device ID do Ads SDK in trong logcat, tại dòng chứa `setTestDeviceIds`. Đây không phải mã unit, App ID hay serial từ `adb devices`. Sau đó chạy (thay `YOUR_HASHED_DEVICE_ID` bằng ID của điện thoại):

```powershell
& C:\flutter\bin\flutter.bat run --debug --dart-define=ADMOB_TEST_DEVICE_IDS=YOUR_HASHED_DEVICE_ID
```

Có thể truyền nhiều ID, ngăn cách bằng dấu phẩy. Debug vẫn dùng unit mẫu của Google; việc bổ sung danh sách thiết bị không chuyển sang unit thật. Điện thoại 2412DPC0AG kết nối USB đã được Ads SDK xác nhận ID `40BFB923AB20AB89042D82271ED4BD11`; cấu hình debug/profile dùng ID này mặc định nếu không truyền `ADMOB_TEST_DEVICE_IDS`. Cùng ID được đăng ký cho UMP trong chế độ thử. Release thông thường không dùng các ID debug. Emulator được Google tự nhận là thiết bị thử. Xem [hướng dẫn test ads của Google](https://developers.google.com/admob/flutter/test-ads).

Bản release dùng quảng cáo thật:

```powershell
& C:\flutter\bin\flutter.bat build apk --release
```

## Kiểm tra

```powershell
& C:\flutter\bin\flutter.bat test --no-pub test/admob_test.dart
```

Ngày 02/10/2026: 24 kiểm thử AdMob dùng mock SDK đạt, gồm consent, quảng cáo thử, bộ đếm, điều hướng không tự hiện quảng cáo, điểm lưu đề thành công, chờ đóng quảng cáo, trang không còn hiện tại, lỗi SDK, tải muộn/no-fill, camera, background/hướng dẫn, banner ẩn/tab ẩn/Tổng quan trống và nhận thưởng. Chạy cùng các kiểm thử lưu đề và điều hướng ví: tổng 41 kiểm thử đạt. Mock SDK không thay thế kiểm thử quảng cáo thử trên thiết bị và không xác nhận Google đã phê duyệt.

Kiểm tra trên điện thoại bằng quảng cáo thử: đăng nhập và chuyển tab nhiều lần, xác nhận không tự hiện xen kẽ; tạo và lưu một đề thành công khi đã đủ 5 lượt chuyển, đóng quảng cáo rồi mới thấy danh sách. Lưu lỗi/hủy đề không được hiện quảng cáo. Xem Tài khoản, Tổng quan trống, camera, bàn phím và tab ẩn để kiểm tra không có banner. Thử mất mạng và SDK không có quảng cáo: đề vẫn lưu bình thường. Không dùng quảng cáo thật để tự tạo lượt xem hoặc lượt nhấp thử.

Ngày 2026-09-29: bộ test chạy bằng Flutter 3.41.7 / Dart 3.11.5. Đã khôi phục Android SDK tại `D:\AndroidSdk`, cấu hình Flutter dùng SDK này và JDK 17. Build debug arm64 phiên bản 4010 thành công và cài cập nhật lên điện thoại, giữ dữ liệu. Bộ đệm Gradle/tệp tạm đặt tại `D:\GradeFlowBuildCache`; script `build-admob.ps1` tại đó dùng bộ đệm riêng và giới hạn plugin native ở arm64 cho điện thoại thử. Release thật chưa được kiểm tra. Đây là ghi nhận lịch sử; cấu hình hiện tại ký release bằng upload keystore riêng, không được fallback về debug key.

Log UMP lịch sử ngày 29/09 trên điện thoại báo `Publisher misconfiguration ... no form(s) configured for the input app ID`. Cần tạo/publish thông báo phù hợp trong **AdMob → Privacy & messaging** cho App ID này. Không bỏ kiểm tra `canRequestAds()` để xử lý lỗi cấu hình tài khoản.

Bản sửa ngày 02/10/2026 có thay đổi website/backend: phục vụ `/app-ads.txt` cùng seller với `/ads.txt`, loại AdSense khỏi trang xác thực và ứng dụng riêng tư, chỉ cho phép mã ở Trang chủ/Hướng dẫn. Sau sửa phải rebuild `docker-compose.local.yml` theo quy tắc dự án. Địa chỉ website nhà phát triển trên Google Play phải trỏ về `https://gradeflow.io.vn/`; kiểm tra xác minh app-ads.txt trong AdMob sau khi crawler cập nhật. Không tự suy ra lỗi từ chối tài khoản là do tệp này.

Firebase Analytics đã được gỡ khỏi dependency Android và có cờ `firebase_analytics_collection_deactivated=true` để giữ thu thập tắt nếu SDK được thêm gián tiếp về sau. Không thay UMP bằng cờ này: AdMob vẫn đi qua consent. Các bản cũ trên thiết bị chưa tự được cập nhật; khai báo An toàn dữ liệu trên Play phải tính đến bản đang phân phối thực tế.

Tài liệu SDK: [Khởi tạo](https://developers.google.com/admob/flutter/quick-start), [banner](https://developers.google.com/admob/flutter/banner), [interstitial](https://developers.google.com/admob/flutter/interstitial), [UMP](https://developers.google.com/admob/flutter/privacy).

Ngày 02/10/2026: APK Trial debug 2103 và AAB release 2103 đã build; manifest debug/release xác nhận tắt Analytics, dependency tree không còn firebase-analytics. AAB được ký bằng cấu hình upload keystore hiện có, chưa tải lên Play. Xem báo cáo `docs/ADMOB_POLICY_FIX_20261002.md` và artifact trong `tests/test_ketqua/admob_policy_20261002/`.
