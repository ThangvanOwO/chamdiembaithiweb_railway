# Rà soát chính sách quảng cáo GradeFlow — 02/10/2026

## Kết luận và giới hạn

Đã đối chiếu mã nguồn hiện tại, website công khai và các chính sách Google liên quan từ [trang anh gửi](https://support.google.com/admob/answer/6128543?hl=vi). Phát hiện một thiếu sót xác minh ứng dụng và một số rủi ro về vị trí/thời điểm quảng cáo cần xử lý. **Chưa xác định được lý do Google không phê duyệt tài khoản.** Không coi các phát hiện dưới đây là thông báo vi phạm do Google ban hành.

Ảnh AdMob ghi tài khoản chưa được phê duyệt. Email anh cung cấp lại ghi AdSense và chỉ nêu yêu cầu chỉnh sửa chung. Việc duyệt tài khoản, duyệt website AdSense, xác minh ứng dụng và xét trạng thái sẵn sàng AdMob là những bước riêng. Cần đối chiếu đúng thông báo của từng sản phẩm. [Hướng dẫn tài khoản AdMob không được phê duyệt](https://support.google.com/admob/answer/9905175?hl=vi), [trạng thái sẵn sàng ứng dụng](https://support.google.com/admob/answer/10564477?hl=vi).

Không truy cập được tài khoản AdMob/AdSense/Play Console đang đăng nhập trong trình duyệt được kết nối. Không kiểm tra hồ sơ thanh toán, tài khoản trùng, lịch sử traffic, bản AAB đang phân phối hay quảng cáo thật trên thiết bị. Rà soát này không chứng nhận toàn bộ hệ thống tuân thủ.

## Những điểm cần xử lý

### 1. app-ads.txt đang thiếu trên tên miền — đã xác minh

Kiểm tra HTTP công khai lúc khoảng 10:20, giờ Việt Nam:

| Đường dẫn | Kết quả |
| --- | --- |
| `https://gradeflow.io.vn/app-ads.txt` | 404 |
| `https://gradeflow.io.vn/ads.txt` | 200, văn bản thuần |
| `https://gradeflow.io.vn/chinh-sach-bao-mat/` | 200 |
| `https://gradeflow.io.vn/xoa-tai-khoan/` | 200 |
| `/accounts/login/`, `/accounts/register/` | 200, có tải mã AdSense |

`website/urls.py` hiện khai báo `ads.txt`, chưa khai báo `app-ads.txt`. Dòng công khai trong `ads.txt` là:

```text
google.com, pub-6695808615282253, DIRECT, f08c47fec0942fa0
```

AdMob dùng `app-ads.txt` để xác minh quyền kiếm tiền của ứng dụng mới trước khi phân phát đầy đủ quảng cáo. `ads.txt` của website không thay thế bước này. Đây là thiếu sót xác minh ứng dụng; **không đủ để giải thích việc từ chối tài khoản**. [Quy trình xác minh](https://support.google.com/admob/answer/14538460?hl=vi).

Khuyến nghị: phục vụ `app-ads.txt` tại gốc tên miền bằng đoạn mã lấy từ chính tài khoản AdMob; xác nhận website nhà phát triển trên trang Google Play công khai trỏ đúng tên miền. Sau đó kiểm tra trạng thái crawler trong AdMob. Chưa xác minh website nhà phát triển đang được khai báo trên cửa hàng. [Hướng dẫn thiết lập và crawler](https://support.google.com/admob/answer/9363762).

### 2. Banner trên màn hình Tài khoản — rủi ro cao về vị trí

`gradeflow_app/lib/screens/profile_screen.dart:118` chèn `InlineAdBanner` giữa các lựa chọn tài khoản và thông tin ứng dụng. Màn hình này chủ yếu gồm hồ sơ, Cài đặt, quyền riêng tư, xóa tài khoản, quản trị và đăng xuất.

Google không cho đặt quảng cáo trên màn hình chỉ phục vụ điều hướng/hành vi hoặc thiếu nội dung có giá trị. Khuyến nghị bỏ banner tại Tài khoản và không cho quảng cáo toàn màn hình xuất hiện tại các trang quản trị, cài đặt, xác thực hay quyền riêng tư. Đây là đánh giá từ cấu trúc giao diện; chưa quan sát quảng cáo thật trên bản đang phát hành. [Chính sách giá trị nội dung và vị trí quảng cáo](https://support.google.com/admob/answer/10502938).

### 3. Quảng cáo toàn màn hình sau khi trang đã hiện — rủi ro cao về thời điểm

`gradeflow_app/lib/services/ad_navigation_observer.dart:22` đợi hoạt ảnh chuyển trang hoàn tất rồi gọi `addPostFrameCallback` để yêu cầu hiển thị. Thay đổi tab cũng đi qua cơ chế này. `ad_service.dart:298` quyết định hiển thị khi bộ đếm đạt 5 lần chuyển màn hình, quảng cáo đã sẵn sàng và các điều kiện khác cho phép.

Hiện không có danh sách chỉ cho phép các điểm kết thúc công việc cụ thể. Vì vậy, một trang biểu mẫu/cài đặt/kết quả có thể đã xuất hiện rồi bị quảng cáo che. Google yêu cầu quảng cáo xen kẽ ở điểm nghỉ tự nhiên, tránh xuất hiện bất ngờ sau khi trang tải hoặc lúc người dùng điền biểu mẫu/đọc nội dung. Bộ đếm 5 lần không tự bảo đảm thời điểm phù hợp. [Cách triển khai xen kẽ không được phép](https://support.google.com/admob/answer/6201362?hl=vi).

Khuyến nghị: dùng điểm chuyển tiếp rõ ràng sau khi người dùng hoàn tất công việc; không tự bật theo mọi lần chuyển trang. Kiểm tra bằng quảng cáo thử trên thiết bị. Giữ nguyên luồng camera và phiên chấm liên tục.

### 4. Mã AdSense có trên trang đăng nhập/đăng ký — cần kiểm tra cấu hình hiển thị

`templates/accounts/login.html:10` và `register.html:10` tải mã AdSense. HTML công khai đang chạy cũng xác nhận điều này. Chưa xác minh Auto ads bật hay đã loại trừ các URL đó; tải thư viện **không chứng minh quảng cáo thật đang hiển thị**.

Khuyến nghị loại mã/quảng cáo khỏi các trang xác thực và thao tác tài khoản. Trang quyền riêng tư và xóa tài khoản hiện đã không tải mã quảng cáo. Trang chủ và Hướng dẫn có nội dung công khai; chưa thấy căn cứ để kết luận website hoàn toàn không có nội dung. [Chính sách màn hình thiếu nội dung và quảng cáo gây cản trở](https://support.google.com/admob/answer/10502938).

### 5. Firebase Analytics và khai báo quyền riêng tư — cần xác minh

`gradeflow_app/android/app/build.gradle.kts:76` thêm Firebase Analytics. Trong phạm vi mã Android/Dart đã rà, chưa thấy cờ tắt thu thập Analytics hoặc cơ chế điều khiển riêng cho SDK này. Trang chính sách hiện mô tả AdMob, UMP và dữ liệu vận hành, chưa giải thích cụ thể việc phân tích sử dụng bằng Firebase Analytics.

Không suy ra SDK chưa thu thập chỉ vì Dart không gọi ghi sự kiện. Cần kiểm tra SDK trong bản phát hành và hành vi thực tế; nếu không dùng Analytics thì cân nhắc bỏ hoặc tắt, nếu dùng thì khai báo đúng dữ liệu/mục đích và cơ chế consent phù hợp. UMP cho phép yêu cầu AdMob không đồng nghĩa đã xử lý mọi hoạt động của Analytics. [Google hướng dẫn kiểm soát thu thập Analytics trên Android](https://firebase.google.com/docs/analytics/android/configure-data-collection), [yêu cầu công bố quyền riêng tư](https://support.google.com/admob/answer/10502938).

## Những phần đang làm đúng hướng trong mã

| Hạng mục | Bằng chứng | Giới hạn |
| --- | --- | --- |
| Chế độ thử | `admob_config.dart:9`: debug/profile dùng ID quảng cáo thử; release có tùy chọn `ADMOB_TEST_ADS` | Chưa biết bản anh đang tự thử có phải release dùng quảng cáo thật không |
| Consent AdMob | Khởi tạo UMP, kiểm tra `canRequestAds()` trước yêu cầu quảng cáo, có mục mở lại lựa chọn quyền riêng tư khi cần | Chưa xác minh biểu mẫu đã publish và hoạt động trong AdMob hiện tại |
| Xen kẽ | Preload; không tự bật khi quảng cáo tải muộn; không hiện ở nền/tutorial; bảo vệ route camera và batch scan | Không giải quyết rủi ro thời điểm trên các màn hình còn lại |
| Banner | Banner nằm trong bố cục, có khoảng cách, ẩn khi bàn phím hiện hoặc tab không hoạt động | Khoảng cách 24 không phải mức Google chứng nhận an toàn; cần xem bố cục trên thiết bị |
| Nhận điểm | Người dùng chủ động chọn; hiển thị điểm/lượt và số lượt; quảng cáo thử không cộng điểm thật | Cần kiểm tra giao phần thưởng thực tế và đường thoát khi không muốn xem |
| Chống giả mạo thưởng | Ticket gắn tài khoản, chữ ký SSV, nonce, giới hạn/ngày và chống cộng trùng | Đây là cơ chế chống lạm dụng, không thay thế việc tuân thủ nội dung quảng cáo |
| Dữ liệu trong yêu cầu quảng cáo | `AdRequest()` không chủ động đính kèm email, ảnh phiếu, tên học sinh hay điểm số; SSV dùng ticket | Không phải bản kiểm toán traffic của mọi SDK |

Điểm tín dụng hiện dùng cho lượt quét trong GradeFlow; chưa thấy cơ chế rút tiền hoặc chuyển điểm trong các luồng đã kiểm tra. Rewarded Ads có thể cấp quyền lợi nội bộ không chuyển nhượng. Phải báo rõ phần thưởng, cho phép từ chối/đóng, không cản trở sử dụng bình thường và giao đúng phần thưởng đã hứa. Không dùng thưởng để yêu cầu người dùng bấm quảng cáo banner/xen kẽ. [Chính sách quảng cáo có thưởng](https://support.google.com/admob/answer/7313578).

Không tự bấm quảng cáo thật hoặc tạo lượt xem nhân tạo để thử. Bộ mã quảng cáo thử là cách kiểm tra được Google hướng dẫn; không có bằng chứng ở đây để xác nhận hay loại trừ invalid traffic trong quá khứ. [Chính sách hành vi và lượt nhấp không hợp lệ](https://support.google.com/admob/answer/2753860).

## Cấu hình tài khoản/cửa hàng chưa xác minh

- **[NEEDS VERIFICATION]** AdMob: nguyên nhân từ chối cụ thể; hồ sơ người nhận thanh toán, xác minh cần thiết và tài khoản nhà xuất bản trùng nếu Google báo. Không tạo thêm tài khoản để né quyết định.
- **[NEEDS VERIFICATION]** Google Play: ứng dụng đã công khai hay đang thử kín; package cửa hàng có khớp `vn.io.gradeflow.app` và bản liên kết AdMob; website nhà phát triển có đúng không. Bản debug `.trial` là package khác.
- **[NEEDS VERIFICATION]** Privacy & messaging: biểu mẫu UMP đã publish cho đúng App ID. Tài liệu dự án ghi lỗi thiếu biểu mẫu ngày 29/09; đây là log cũ, không kết luận cấu hình hôm nay còn lỗi. Nếu phục vụ quảng cáo cá nhân hóa ở EEA/Anh/Thụy Sĩ, cần CMP được Google chứng nhận. [Yêu cầu quản lý đồng ý](https://support.google.com/admob/answer/13554116?hl=vi).
- **[NEEDS VERIFICATION]** Đối tượng tuổi trong Play: chính sách website mô tả ứng dụng dành cho giáo viên. Không tự coi mọi ứng dụng giáo dục là dành cho trẻ em. Nếu đối tượng thực tế bao gồm trẻ em, cần kiểm tra cờ xử lý trẻ em, phân loại quảng cáo và các yêu cầu tương ứng. [Chính sách Gia đình](https://support.google.com/admob/answer/6223431?hl=vi).
- **[NEEDS VERIFICATION]** Khai báo An toàn dữ liệu trên Play có khớp AdMob, Analytics, dữ liệu tài khoản, ảnh và kết quả chấm hay không. Chưa đọc được câu trả lời đang lưu trong Console.

Tài liệu `docs/ADMOB_ANDROID.md` còn mô tả ký release bằng debug key và các vị trí banner cũ. Mã Gradle hiện có cấu hình ký release riêng; vị trí banner đã thay đổi theo bản remake. Không dùng các mô tả cũ đó làm kết luận về bản hiện tại.

## Kiểm thử và thứ tự khuyến nghị

Bộ `flutter test --no-pub test/admob_test.dart` đã chạy: **22/22 kiểm thử đạt**. Các test dùng SDK giả lập để kiểm tra consent, chế độ thử, điều hướng, vòng đời banner và thưởng. Kết quả này không xác nhận Google đã phê duyệt, không đo invalid traffic và không chứng minh quảng cáo thật nằm đúng vị trí.

Ưu tiên: (1) xử lý `app-ads.txt` và kiểm tra liên kết cửa hàng; (2) sửa vị trí banner/thời điểm xen kẽ và loại quảng cáo ở trang xác thực; (3) xác minh UMP, Analytics và khai báo Play; (4) đối chiếu thông báo từ chối cụ thể, xử lý rồi gửi xét duyệt đúng mục. Không có cam kết được duyệt hay thời gian duyệt cố định.

Trong lượt rà soát này chỉ tạo báo cáo. Không sửa mã ứng dụng, camera, thuật toán chấm, dữ liệu, VPS hoặc cấu hình tài khoản Google; không gửi lại đơn hay xác nhận thay anh việc tuân thủ chính sách.

## Cập nhật sau khi được phép sửa — 02/10/2026

Các phát hiện trên mô tả trạng thái trước khi sửa. Sau khi người dùng cho phép, đã bổ sung app-ads.txt, giới hạn mã quảng cáo website, bỏ banner ở trang tài khoản/trạng thái không có nội dung, chuyển xen kẽ về điểm lưu đề thành công và tắt Firebase Analytics ở cấu hình Android mới. Phần website đã push commit `0a312b2` và triển khai VPS; APK thử được build riêng, chưa thay ứng dụng trên thiết bị hoặc Google Play. Xem [báo cáo sửa và bằng chứng](<D:/chamtrac nghien v2/docs/ADMOB_POLICY_FIX_20261002.md>). Không thay đổi kết luận rằng nguyên nhân từ chối tài khoản cụ thể và cấu hình trong Console vẫn chưa được xác minh.
