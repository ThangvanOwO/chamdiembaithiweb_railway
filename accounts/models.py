import uuid

from django.db import models
from django.contrib.auth.models import User


class TeacherProfile(models.Model):
    """Extended profile for teachers. Account created by Admin only."""
    
    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name='teacher_profile')
    school = models.CharField('Trường', max_length=200, blank=True, default='')
    subject = models.CharField('Môn dạy', max_length=100, blank=True, default='')
    phone = models.CharField('Số điện thoại', max_length=20, blank=True, default='')
    avatar = models.ImageField('Ảnh đại diện', upload_to='avatars/', blank=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = 'Hồ sơ giáo viên'
        verbose_name_plural = 'Hồ sơ giáo viên'

    def __str__(self):
        return f"{self.user.get_full_name() or self.user.email} — {self.school}"
    
    @property
    def display_name(self):
        return self.user.get_full_name() or self.user.email
    
    @property
    def initials(self):
        name = self.user.get_full_name()
        if name:
            parts = name.split()
            return ''.join([p[0].upper() for p in parts[:2]])
        return self.user.email[0].upper()


class CreditWallet(models.Model):
    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name='credit_wallet')
    balance = models.PositiveIntegerField('Điểm khả dụng', default=100)
    bonus_blocked = models.BooleanField('Khóa nhận bonus', default=False)

    class Meta:
        verbose_name = 'Ví tín dụng'
        verbose_name_plural = 'Ví tín dụng'

    def __str__(self):
        return f'{self.user.email}: {self.balance}'


class ScanOperation(models.Model):
    wallet = models.ForeignKey(CreditWallet, on_delete=models.PROTECT)
    key = models.CharField(max_length=128)
    fingerprint = models.CharField(max_length=64)
    reserved = models.PositiveIntegerField()
    charged = models.PositiveIntegerField(default=0)
    finished = models.BooleanField(default=False)
    response_body = models.TextField(blank=True)
    response_status = models.PositiveSmallIntegerField(default=200)
    response_type = models.CharField(max_length=100, default='application/json')
    redirect_url = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        constraints = [models.UniqueConstraint(fields=['wallet', 'key'], name='unique_scan_request')]
        verbose_name = 'Lượt quét'
        verbose_name_plural = 'Lượt quét'


class CreditEntry(models.Model):
    wallet = models.ForeignKey(CreditWallet, on_delete=models.PROTECT, related_name='entries')
    amount = models.IntegerField('Thay đổi điểm')
    balance_after = models.PositiveIntegerField('Số dư sau giao dịch')
    reference = models.CharField(max_length=180, unique=True)
    reason = models.CharField('Lý do', max_length=255)
    actor = models.ForeignKey(User, null=True, blank=True, on_delete=models.SET_NULL, related_name='+')
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-id']
        verbose_name = 'Giao dịch tín dụng'
        verbose_name_plural = 'Giao dịch tín dụng'


class CreditPurchase(models.Model):
    user = models.ForeignKey(User, on_delete=models.PROTECT)
    reference = models.UUIDField(unique=True)
    points = models.PositiveIntegerField()
    amount_minor = models.PositiveIntegerField()
    currency = models.CharField(max_length=3)
    paid = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)


class RewardClaim(models.Model):
    wallet = models.ForeignKey(CreditWallet, on_delete=models.PROTECT)
    event_id = models.CharField(max_length=180, unique=True)
    period = models.CharField(max_length=20)
    created_at = models.DateTimeField(auto_now_add=True)


class SecurityRateBucket(models.Model):
    """Shared, atomic limits across workers; identities are stored as hashes."""
    key = models.CharField(max_length=64, primary_key=True)
    hits = models.PositiveIntegerField(default=0)
    expires_at = models.DateTimeField(db_index=True)


class PendingSignup(models.Model):
    """No User or welcome credits exist before ownership of email is proven."""
    token = models.UUIDField(default=uuid.uuid4, unique=True, editable=False)
    email = models.EmailField(unique=True, max_length=150)
    password_hash = models.CharField(max_length=128)
    first_name = models.CharField(max_length=150, blank=True)
    last_name = models.CharField(max_length=150, blank=True)
    expires_at = models.DateTimeField(db_index=True)


class AccountNetwork(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE)
    network = models.CharField(max_length=64, db_index=True)
    first_seen = models.DateTimeField(auto_now_add=True)
    last_seen = models.DateTimeField(db_index=True)

    class Meta:
        constraints = [models.UniqueConstraint(fields=['user', 'network'], name='unique_account_network')]


class AccountRisk(models.Model):
    user_a = models.ForeignKey(User, on_delete=models.CASCADE, related_name='+')
    user_b = models.ForeignKey(User, on_delete=models.CASCADE, related_name='+')
    score = models.PositiveSmallIntegerField(default=20)
    evidence = models.JSONField(default=dict)
    status = models.CharField(max_length=16, default='new', choices=[
        ('new', 'Chờ kiểm tra'), ('review', 'Đang theo dõi'),
        ('dismissed', 'Đã loại nghi vấn'), ('confirmed', 'Đã xác nhận')])
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        constraints = [models.UniqueConstraint(fields=['user_a', 'user_b'], name='unique_account_risk_pair'),
                       models.CheckConstraint(condition=models.Q(user_a__lt=models.F('user_b')), name='ordered_account_risk_pair')]

    @property
    def level(self):
        return 'Cao' if self.score >= 80 else 'Nghi vấn' if self.score >= 40 else 'Theo dõi'


class ModerationEvent(models.Model):
    user = models.ForeignKey(User, on_delete=models.PROTECT, related_name='+')
    actor = models.ForeignKey(User, on_delete=models.PROTECT, related_name='+')
    action = models.CharField(max_length=24)
    reason = models.CharField(max_length=255)
    reference = models.UUIDField(unique=True)
    details = models.JSONField(default=dict)
    created_at = models.DateTimeField(auto_now_add=True)

    @property
    def action_label(self):
        return {'revoke': 'Thu hồi bonus', 'block_bonus': 'Khóa bonus',
                'unblock_bonus': 'Mở bonus', 'lock': 'Khóa tài khoản',
                'unlock': 'Mở tài khoản', 'review': 'Đánh giá nghi vấn'}.get(self.action, self.action)
