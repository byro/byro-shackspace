from django.dispatch import receiver

from byro.members.signals import new_member


@receiver(new_member)
def add_member_to_mailman(sender, signal, **kwargs):
    member = sender
    # TODO: magic happens here
