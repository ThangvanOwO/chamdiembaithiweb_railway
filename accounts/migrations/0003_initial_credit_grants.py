from django.db import migrations


def grant_existing_accounts(apps, schema_editor):
    User = apps.get_model('auth', 'User')
    Wallet = apps.get_model('accounts', 'CreditWallet')
    Entry = apps.get_model('accounts', 'CreditEntry')
    alias = schema_editor.connection.alias
    for user in User.objects.using(alias).iterator():
        wallet, created = Wallet.objects.using(alias).get_or_create(user_id=user.pk, defaults={'balance': 100})
        if created:
            Entry.objects.using(alias).create(wallet_id=wallet.pk, amount=100, balance_after=100,
                reference=f'welcome:{user.pk}', reason='100 điểm chào mừng')


class Migration(migrations.Migration):
    dependencies = [('accounts', '0002_creditpurchase_creditwallet_creditentry_rewardclaim_and_more')]
    operations = [migrations.RunPython(grant_existing_accounts, migrations.RunPython.noop)]
