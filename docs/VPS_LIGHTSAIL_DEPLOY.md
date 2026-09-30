# Triển khai GradeFlow lên AWS Lightsail

Cấu hình này dành cho máy Ubuntu Lightsail 2 GB RAM/2 vCPU và giữ máy Windows
hiện tại làm đường lui. Luồng truy cập công khai là:

`Người dùng -> Cloudflare -> Cloudflare Tunnel -> 127.0.0.1:8000 -> Nginx -> Django -> PostgreSQL`

Không dùng `docker-compose.yml` cũ. Tất cả lệnh VPS trong tài liệu này dùng
`docker-compose.vps.yml`.

## 1. Chuẩn bị Lightsail

1. Gắn **Static IP** cho instance trước khi dùng SCP/SSH lâu dài.
2. Trong firewall của Lightsail chỉ giữ TCP 22 cho SSH. Không mở 80, 443,
   8000 hoặc 5432. Cloudflare Tunnel kết nối ra ngoài từ VPS.
3. Kết nối SSH bằng nút **Connect using SSH**.

Tạo swap 2 GB:

```bash
sudo fallocate -l 2G /swapfile
sudo chmod 600 /swapfile
sudo mkswap /swapfile
sudo swapon /swapfile
grep -q '^/swapfile ' /etc/fstab || echo '/swapfile none swap sw 0 0' | sudo tee -a /etc/fstab
free -h
```

## 2. Cài Docker Engine và Compose

```bash
sudo apt-get update
sudo apt-get install -y ca-certificates curl
sudo install -m 0755 -d /etc/apt/keyrings
sudo curl -fsSL https://download.docker.com/linux/ubuntu/gpg -o /etc/apt/keyrings/docker.asc
sudo chmod a+r /etc/apt/keyrings/docker.asc
echo "deb [arch=$(dpkg --print-architecture) signed-by=/etc/apt/keyrings/docker.asc] https://download.docker.com/linux/ubuntu $(. /etc/os-release && echo \"$VERSION_CODENAME\") stable" | sudo tee /etc/apt/sources.list.d/docker.list >/dev/null
sudo apt-get update
sudo apt-get install -y docker-ce docker-ce-cli containerd.io docker-buildx-plugin docker-compose-plugin git
sudo usermod -aG docker "$USER"
```

Thoát phiên SSH rồi kết nối lại, sau đó kiểm tra:

```bash
docker version
docker compose version
```

## 3. Lấy mã nguồn

```bash
cd /home/ubuntu
git clone https://github.com/ThangvanOwO/chamdiembaithiweb_railway.git gradeflow
cd gradeflow
git log -1 --oneline
```

## 4. Tạo cấu hình bí mật trên VPS

```bash
cd /home/ubuntu/gradeflow
cp .env.vps.example .env.vps
openssl rand -hex 32
openssl rand -hex 48
nano .env.vps
chmod 600 .env.vps
```

Dán chuỗi 64 ký tự đầu vào `POSTGRES_PASSWORD` và chuỗi 96 ký tự sau vào
`DJANGO_SECRET_KEY`. Không gửi hai giá trị này qua chat, không commit và không
đưa vào ảnh chụp màn hình.

Kiểm tra cấu hình Compose trước khi chạy:

```bash
docker compose --env-file .env.vps -f docker-compose.vps.yml config --quiet
```

## 5. Khởi động GradeFlow trên VPS

```bash
docker compose --env-file .env.vps -f docker-compose.vps.yml up -d --build
docker compose --env-file .env.vps -f docker-compose.vps.yml ps
curl -H 'Host: vps-test.gradeflow.io.vn' http://127.0.0.1:8000/ads.txt
```

Kết quả cần có: `db`, `web`, `proxy` đều chạy; `web` và `proxy` chuyển sang
`healthy`; lệnh `curl` trả về nội dung `ads.txt`.

## 6. Chuyển bản sao dữ liệu từ Windows

Hai tệp local được tạo tại:

```text
D:\chamtrac nghien v2\scratch\vps_migration\gradeflow-data.json
D:\chamtrac nghien v2\scratch\vps_migration\media.tar.gz
```

Chúng chứa dữ liệu riêng tư và tuyệt đối không được đưa lên GitHub.

Trên VPS tạo thư mục nhận file:

```bash
mkdir -p /home/ubuntu/vps_migration
chmod 700 /home/ubuntu/vps_migration
```

Từ **Windows PowerShell**, dùng Static IP và khóa Lightsail đã tải:

```powershell
$Key = "$env:USERPROFILE\Downloads\LightsailDefaultKey-ap-southeast-1.pem"
$VpsIp = '<STATIC_IP_CUA_ANH>'
scp -i $Key 'D:\chamtrac nghien v2\scratch\vps_migration\gradeflow-data.json' "ubuntu@${VpsIp}:/home/ubuntu/vps_migration/"
scp -i $Key 'D:\chamtrac nghien v2\scratch\vps_migration\media.tar.gz' "ubuntu@${VpsIp}:/home/ubuntu/vps_migration/"
```

Quay lại SSH của VPS rồi nạp dữ liệu:

```bash
cd /home/ubuntu/gradeflow
docker compose --env-file .env.vps -f docker-compose.vps.yml cp /home/ubuntu/vps_migration/gradeflow-data.json web:/tmp/gradeflow-data.json
docker compose --env-file .env.vps -f docker-compose.vps.yml exec -T web python manage.py loaddata /tmp/gradeflow-data.json
docker compose --env-file .env.vps -f docker-compose.vps.yml exec -T web sh -c 'tar -xzf - -C /app/media' < /home/ubuntu/vps_migration/media.tar.gz
```

Kiểm tra các dữ liệu chính và tài khoản admin:

```bash
docker compose --env-file .env.vps -f docker-compose.vps.yml exec -T web python manage.py shell -c "from django.contrib.auth import get_user_model; from grading.models import Exam,Submission; from accounts.models import CreditWallet,CreditEntry; U=get_user_model(); print({'users':U.objects.count(),'admin_ok':U.objects.filter(email='zeprai12345s@gmail.com',is_staff=True,is_superuser=True).exists(),'exams':Exam.objects.count(),'submissions':Submission.objects.count(),'wallets':CreditWallet.objects.count(),'credit_entries':CreditEntry.objects.count()})"
```

`admin_ok` phải là `True`. Nếu là `False`, dừng trước khi chuyển tên miền và
kiểm tra bản dữ liệu nguồn.

## 7. Cài Cloudflare Tunnel trên VPS

Trong Cloudflare Zero Trust, tạo tunnel mới tên `gradeflow-vps`. Tạo Public
Hostname thử nghiệm:

```text
vps-test.gradeflow.io.vn -> http://localhost:8000
```

Cài `cloudflared` theo lệnh dành cho Ubuntu mà Cloudflare hiển thị. Để token
không xuất hiện trên màn hình hoặc lịch sử shell, có thể nhập token bằng:

```bash
read -rsp 'Cloudflare tunnel token: ' CF_TUNNEL_TOKEN; echo
sudo cloudflared service install "$CF_TUNNEL_TOKEN"
unset CF_TUNNEL_TOKEN
sudo systemctl status cloudflared --no-pager
```

Mở `https://vps-test.gradeflow.io.vn`, đăng nhập bằng tài khoản thử và kiểm tra:

- trang chủ, đăng nhập và admin;
- tạo đề và tải ảnh;
- quét/chấm một phiếu;
- số dư tín dụng chỉ bị trừ đúng một lần;
- ảnh bài làm chỉ xem được khi tài khoản có quyền.

## 8. Chuyển tên miền chính và đường lui

1. Dừng thao tác ghi dữ liệu trên hệ thống cũ trong thời gian chuyển đổi.
2. Xuất và nạp lại bản dữ liệu cuối cùng theo mục 6.
3. Trong Cloudflare Tunnel, chuyển hostname `gradeflow.io.vn` sang tunnel
   `gradeflow-vps`, service `http://localhost:8000`.
4. Kiểm tra web và ứng dụng Android với tên miền chính.
5. Giữ Docker trên Windows và tunnel cũ ở trạng thái dừng trong vài ngày. Nếu
   VPS có lỗi, chuyển hostname về tunnel cũ rồi bật lại Docker/tunnel Windows.

Không chạy đồng thời hai backend có thể nhận dữ liệu ghi trên cùng hostname;
điều đó có thể tạo hai cơ sở dữ liệu lệch nhau.

## 9. Lệnh vận hành

```bash
cd /home/ubuntu/gradeflow
docker compose --env-file .env.vps -f docker-compose.vps.yml ps
docker compose --env-file .env.vps -f docker-compose.vps.yml logs --tail=200 web
docker compose --env-file .env.vps -f docker-compose.vps.yml restart web
git pull --ff-only
docker compose --env-file .env.vps -f docker-compose.vps.yml up -d --build
```

Trước mỗi lần cập nhật, sao lưu PostgreSQL và media. AWS snapshot hữu ích cho
khôi phục cả máy nhưng không thay thế bản sao lưu dữ liệu ứng dụng.
