from django.db import models


class ShackProfile(models.Model):
    member = models.ForeignKey(
        to='members.Member',
        on_delete=models.CASCADE,
        related_name='profile_shack',
    )
    has_loeffelhardt_account = models.BooleanField(default=False)
    has_matomat_key = models.BooleanField(default=False)
    has_metro_card = models.BooleanField(default=False)
    has_safe_key = models.BooleanField(default=False)
    has_selgros_card = models.BooleanField(default=False)
    has_shack_iron_key = models.BooleanField(default=False)
    has_snackomat_key = models.BooleanField(default=False)
    is_keyholder = models.BooleanField(default=False)
    signed_DSV = models.BooleanField(default=False)
    ssh_public_key = models.TextField(null=True, blank=True)
