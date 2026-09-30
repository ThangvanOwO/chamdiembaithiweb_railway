# Ví tín dụng và quảng cáo thưởng trên APK

Tài khoản hiển thị số dư thật, cập nhật khi vào lại tab, khi ứng dụng trở lại
foreground hoặc nhấn cập nhật. Lỗi mạng không hiển thị thành số dư 0.
Lịch sử gồm 20 giao dịch gần nhất của chính tài khoản đăng nhập.
Thông tin ứng dụng/máy chủ và quản trị thu vào nhóm mở rộng; bỏ hiển thị token.

API bổ sung, dùng xác thực Token/Session hiện có:

- `GET /api/v1/credits/`: balance, scan_cost=1, entries và reward
  (enabled, points, remaining).
- `POST /api/v1/credits/reward-ticket/`: phát ticket có chữ ký gắn user,
  ngày Asia/Ho_Chi_Minh, nonce. Không cộng điểm. Giới hạn 15 ticket/giờ/user.
- `POST /api/v1/credits/reward-status/`: body ticket, chỉ xem trạng thái
  claimed của chính tài khoản. Không cộng điểm.
- `GET /api/v1/credits/admob-callback/`: Google SSV, xác minh ECDSA SHA256
  trên query trước signature sau giải mã percent-encoding, giữ nguyên thứ tự
  tham số theo Google URI.getQuery(), không dựng lại query. Public key tải từ Google qua HTTPS,
  cache 1 giờ. Kiểm tra unit, timestamp, ticket, ngày, tài khoản bị khóa,
  giới hạn. Callback giả hoặc lặp lại không cộng thêm điểm.

Thưởng được người dùng chọn: **5 điểm/lượt hoàn tất, tối đa 3 lượt/ngày**.
Tận dụng giao dịch ví và RewardClaim hiện có, không đổi schema.
Mỗi ticket chỉ cộng một lần, kể cả có nhiều transaction Google cho cùng ticket.
SSV có thể đến chậm; APK chờ trạng thái tối đa 30 giây rồi thông báo cập nhật ví
sau. Ticket và callback phải thuộc ngày phát ticket, timestamp tối đa 24 giờ.

## Bật SSV trong AdMob

1. Mở GradeFlow → Đơn vị quảng cáo → Rewarded
   `ca-app-pub-6695808615282253/6070051413`.
2. Chỉnh Server-side verification, đặt callback URL:
   `https://gradeflow.io.vn/api/v1/credits/admob-callback/`.
   SDK cung cấp custom_data ticket tự động.
   Hộp xác minh URL trong AdMob cần custom_data là mã kiểm tra riêng do
   `create_verification_probe()` trên backend sinh (hết hạn sau 20 phút).
   Để trống user ID thử nghiệm, nhập mã vào dữ liệu tùy chỉnh, chọn Xác minh URL,
   Sử dụng URL đã xác minh, rồi Lưu ở trang đơn vị quảng cáo.
   Công cụ Google dùng ad_unit mẫu `1234567890`, chỉ được phép trong luồng mã
   xác minh riêng này; luồng thưởng vẫn yêu cầu unit thật của GradeFlow.
   Callback kiểm tra vẫn xác minh chữ ký Google nhưng không tạo RewardClaim,
   không cộng điểm, hoạt động được trước khi bật ADMOB_SSV_ENABLED.
3. Sau khi URL được lưu, đặt `ADMOB_SSV_ENABLED=1` trong môi trường backend
   (`.env.docker.local` trên máy này), build/restart bằng cấu hình Docker local.
4. Để kiểm tra cấp thưởng thật, dùng công cụ thử SSV với custom_data là ticket
   hợp lệ từ API của tài khoản thử (khác mã xác minh URL). Xác minh một callback chỉ cộng 5 và callback
   lặp không cộng thêm. Debug APK dùng unit sample nên chỉ kiểm tra hiển thị,
   không xác minh callback SSV của unit thật và không cộng điểm thật.

Mặc định `ADMOB_SSV_ENABLED=0` đến khi cấu hình AdMob hoàn tất; release hiển thị
Chưa mở khi server chưa bật. Debug/profile dùng unit Google sample
`ca-app-pub-3940256099942544/5224354917`, đăng ký testDeviceIds qua AdService,
hiển thị **Quảng cáo thử · không cộng điểm**, không gửi yêu cầu cấp thưởng thật.
UMP phải cho phép request và phiên đăng nhập còn hiệu lực trước khi quảng cáo mở.
Interstitial bị giữ trong lúc tải/hiển thị rewarded.

Google hướng dẫn:
https://developers.google.com/admob/flutter/rewarded
https://developers.google.com/admob/android/ssv

## Nạp tín dụng

Mục Nạp tín dụng đang hiển thị **Chưa mở**. Cần người dùng chọn nhà cung cấp
thanh toán, các gói điểm/giá bán và cấu hình nhà cung cấp. Chỉ cấp điểm sau
backend xác minh thanh toán thành công; không cấp điểm từ callback Flutter.

## Kiểm thử

`python manage.py test api.test_credits`: xác thực/chủ sở hữu, welcome không
cộng lặp, chữ ký Google sai/nội dung bị sửa, ticket giả/sai tài khoản,
thời gian sai/unit sai, callback lặp, giới hạn 3 lượt, khóa bonus.

`flutter test test/credit_wallet_test.dart test/admob_test.dart test/server_config_dialog_test.dart`:
số dư/lỗi mạng/cập nhật khi vào tab, UMP, test unit, earned/cancel,
SSV trước show, logout trong lúc tải, interstitial và server dialog.
