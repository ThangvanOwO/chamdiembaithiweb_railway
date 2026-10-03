from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [('dashboard', '0001_initial')]
    operations = [
        migrations.AddField(model_name='announcement', name='event_starts_at', field=models.DateTimeField('Bắt đầu sự kiện', null=True, blank=True)),
        migrations.AddField(model_name='announcement', name='event_ends_at', field=models.DateTimeField('Kết thúc sự kiện', null=True, blank=True)),
        migrations.AlterField(model_name='announcement', name='kind', field=models.CharField('Loại', max_length=12, default='info', choices=[('info', 'Thông tin'), ('reminder', 'Nhắc nhở'), ('update', 'Cập nhật'), ('event', 'Sự kiện')])),
    ]
