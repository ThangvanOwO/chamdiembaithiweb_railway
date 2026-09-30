from django.contrib.auth import get_user_model
from django.db.models.signals import post_save
from django.dispatch import receiver

from .credits import ensure_wallet


@receiver(post_save, sender=get_user_model(), dispatch_uid='accounts.initial_credit_wallet')
def create_credit_wallet(sender, instance, created, raw=False, **kwargs):
    if created and not raw:
        ensure_wallet(instance)
        from .risk import current_request
        request = current_request.get()
        if request is not None:
            request.risk_users.add(instance.pk)
