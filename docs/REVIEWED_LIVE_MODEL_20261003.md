# Áp dụng mô hình nhận diện đã duyệt — 03/10/2026

## BUG FIX REPORT

- **ROOT CAUSE**: Bộ đọc Live xác định một số ô tô nhạt hoặc có bóng/chữ in là `uncertain`, nên để trống câu thay vì đoán. Mô hình đã train phân loại được các ô đó nhưng chưa được nối vào luồng Live. Crop train là vùng ảnh xám gốc 27×27 (bán kính 13, cạnh cuối bao gồm) rồi resize 32×32; không thể dùng trực tiếp với cách crop/tiền xử lý của mô hình cũ.
- **FILES CHANGED**:
  - [reviewed_bubble_model.py](../grading/engine/reviewed_bubble_model.py): tải mô hình, kiểm tra checksum, crop và hỗ trợ bằng chứng mực chưa rõ.
  - [manifest.json](../grading/engine/reviewed_models/manifest.json), `reviewed_20261003.onnx`: mô hình epoch 4, 128.997 byte, đóng gói riêng.
  - [live_bubble_reader.py](../grading/engine/live_bubble_reader.py), [hi.py](../grading/engine/hi.py): gọi mô hình ở các vùng đáp án Live đã căn chỉnh.
  - [.env.vps.example](../.env.vps.example): công tắc `LIVE_REVIEWED_CNN`.
  - [test_reviewed_live_model.py](../tests/test_reviewed_live_model.py): bảo vệ phiếu trống, tô kép, crop, lỗi mô hình và hình học khác.
  - [audit_reviewed_live.py](../tools/training/audit_reviewed_live.py): so sánh trước/sau từ ảnh gốc, không ghi database hay trừ credit.
- **CHANGES MADE**: Giữ bộ đọc mực gốc làm chính. Chỉ chạy CNN cho ô `uncertain`, đúng mẫu 1400×1920/bán kính 13/toàn bộ tọa độ đã train, và vùng đã căn chỉnh. Ô đã rõ, trống, ngoài ảnh và số báo danh/mã đề không được CNN thay đổi. Để xác nhận tô nhạt, vẫn cần tương phản ≥0,07, độ phủ mực ≥0,60 và ít nhất 3 góc phần tư có mực. Tô kép vẫn báo `X`. Thiếu/hỏng mô hình hoặc lỗi inference giữ kết quả bộ đọc gốc. Dùng một luồng CPU và cache mô hình trong tiến trình; không đổi camera, API, database, tọa độ hay mô hình `bubble_cnn.*` cũ.
- **TESTS RUN**:
  - `python -X utf8 -m unittest discover -s tests -p test_reviewed_live_model.py -v`.
  - `python -X utf8 -m unittest discover -s tests -p test_live*.py -v`.
  - `python -X utf8 scratch/reviewed_original_controls_20261003.py`: bật mô hình mới và chạy 5 nhóm kiểm tra ảnh gốc sẵn có.
  - `python -X utf8 tools/training/audit_reviewed_live.py --dataset Traing/reviewed_20261003_130209 --output scratch/reviewed_live_local_20261003_b --repeats 3`.
  - Rebuild bằng `docker compose -f docker-compose.local.yml up -d --build`; kiểm tra container, `manage.py check` và các kiểm tra mới trong container.
  - VPS: build image mới, chạy 14 kiểm tra và `manage.py check` trong container thử trước khi thay web; chờ web healthy rồi reload proxy.
  - VPS: chạy lại audit 4 ảnh gốc, 3 lượt mỗi cấu hình; sau đó đo xen kẽ bật/tắt 5 lượt mỗi cấu hình trên từng phiếu để kiểm tra dao động thời gian và thời gian riêng của helper.
- **TEST RESULTS**: 14/14 kiểm tra mới đạt trên Windows, Docker local và Docker VPS. 5/5 nhóm ảnh gốc đạt khi bật mô hình: phiếu trống ở 3 mức sáng, tô kép Phần I/III, số âm/thập phân và các câu đã xác nhận trước đây. Bộ Live cũ chạy 53 test: 51 đạt; 1 lỗi setup và 1 thất bại vì thiếu 5 JPEG phiếu trống cũ đúng kích thước ghi trong fixture; không sửa hoặc bỏ assert. 4 ảnh gốc đã duyệt được căn chỉnh lại tự động rồi qua bộ đọc/chấm/vẽ ảnh Live: trước 307/312 vùng khớp, sau 312/312, cả local và VPS. Trung vị đọc/chấm/vẽ ở máy local khoảng 0,20–0,21 giây/phiếu; căn chỉnh ảnh gốc riêng khoảng 0,65–1,09 giây. VPS đã triển khai commit code `f6aac46`: db/proxy/web healthy, mô hình `20261003-epoch4` bật và session inference tải được, HTTP nội bộ và HTTPS công khai `/ads.txt` đều 200. Không cần cài lại app cho thay đổi backend này.
- **REGRESSION RISK**: Dữ liệu nhỏ, 4 ảnh gồm 3 ảnh train và 1 ảnh validation đã dùng chọn checkpoint; chưa có ảnh kiểm tra độc lập mới. 312/312 không chứng minh mọi ảnh thực tế đều đúng. Ô không đủ bằng chứng vẫn cần duyệt, không ép đoán. Giới hạn đúng mẫu phiếu, giữ nguyên trạng thái chắc chắn và công tắc tắt giúp giảm rủi ro.
- **UNRELATED ISSUES FOUND**: 5 JPEG fixture phiếu trống cũ thiếu/khác bản gốc nên hai kiểm tra không thể xác minh đầy đủ. Các thay đổi giao diện mobile/auth và các công cụ train đang có trong working tree không thuộc bản tích hợp này.

## Kết quả theo ảnh gốc đã duyệt

| Phiếu | Nhóm | Trước | Sau | Vùng sửa được |
| --- | --- | ---: | ---: | --- |
| 1 | Train | 76/78 | 78/78 | II.5b, III.2 |
| 2 | Train | 78/78 | 78/78 | Không cần inference |
| 3 | Validation | 77/78 | 78/78 | III.2 = −1,5 |
| 4 | Train | 76/78 | 78/78 | I.40 = B, II.6c = Đúng |

Ảnh kết quả và JSON local: `scratch/reviewed_live_local_20261003_b/`. Dữ liệu ảnh/nhãn được giữ ngoài Git. Audit dùng nhãn chỉ để chấm đối chiếu sau khi đọc ảnh; không dùng đáp án để chọn ô tô.

## Đo thời gian trên VPS thực tế

| Phiếu | Trung vị bản gốc | Trung vị bản mới | Thời gian helper mới |
| --- | ---: | ---: | ---: |
| 1 | 0,423 s | 0,460 s | 1,80 ms |
| 2 | 0,423 s | 0,443 s | 1,05 ms |
| 3 | 0,448 s | 0,442 s | 1,44 ms |
| 4 | 0,431 s | 0,442 s | 1,70 ms |

Phép đo xen kẽ 5 lượt/cấu hình/phiếu gồm đọc ảnh đã căn chỉnh, đọc đáp án, chấm đối chiếu và lưu ảnh kết quả. Helper tính cả các lần gọi không cần inference; chỉ 1–2 ô chưa rõ cần inference trên các phiếu 1/3/4. Tất cả 20 lượt bật mô hình đều khớp 78/78 vùng mỗi phiếu. Mô hình cải thiện nhận diện, không chứng minh chấm nhanh hơn; mức chênh thời gian toàn lượt nhỏ nhưng còn dao động.

Audit đầu tiên có trung vị 0,408–1,036 giây, trong đó phiếu 3 có các lượt 0,789/1,036/1,351 giây. Kiểm tra xen kẽ sau đó trên đúng ảnh đó đạt trung vị 0,442 giây, helper khoảng 1,44 ms; không tái hiện mức tăng 0,6 giây của lượt trước. Chưa xác định được nguồn dao động, không quy cho CNN hay khẳng định đã loại bỏ mọi độ trễ. Căn chỉnh tự động từ ảnh gốc (không dùng góc app) trên VPS mất 2,50–4,60 giây. Các số đọc/chấm trên không tính camera, truyền ảnh, căn chỉnh lại từ ảnh gốc hoặc chờ xử lý; không phải cam kết toàn bộ thao tác dưới 1 giây.

Ảnh và bằng chứng tải về: `tests/test_ketqua/reviewed_live_vps_20261003/` (`report.json`, `alternating_benchmark.json`, 4 ảnh `phieu_*_candidate_result.jpg`). Bản lưu trên VPS: `/home/ubuntu/gradeflow/scratch/reviewed_live_audit_20261003/`.

## Đường lui

Không thay thế mô hình cũ. Bản trước sửa code local được lưu ở `scratch/reviewed_model_before_20261003/`. Có thể tắt riêng mô hình mới mà không thay đổi camera hoặc bộ đọc mực:

1. Trong `/home/ubuntu/gradeflow/.env.vps`, đặt `LIVE_REVIEWED_CNN=0`.
2. Tại `/home/ubuntu/gradeflow`, chạy:

```bash
docker compose --env-file .env.vps -f docker-compose.vps.yml up -d --no-deps --force-recreate web
```

Kiểm tra `ps` và `/ads.txt` sau khi web khởi động. `LIVE_CPU_FAST` giữ nguyên. Nếu cần quay lại toàn bộ bản server, image trước là `gradeflow-vps-web:reviewed-before-20261003`, commit `ef7ca63`; đã lưu thông tin image/commit và cấu hình riêng tư trong `/home/ubuntu/gradeflow/scratch/reviewed_model_before_20261003/` (quyền 700). Script `rollback.sh` trong đó đã kiểm tra cú pháp, chưa thực thi vì bản mới hoạt động tốt:

```bash
bash /home/ubuntu/gradeflow/scratch/reviewed_model_before_20261003/rollback.sh
docker compose --env-file .env.vps -f docker-compose.vps.yml exec -T proxy nginx -s reload
```

Script đổi tag image và tạo lại web với image cũ; không reset working tree hoặc xóa database/media. Không đưa bản sao cấu hình chứa bí mật lên Git.
