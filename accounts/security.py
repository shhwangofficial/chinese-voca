import hashlib
from datetime import timedelta

from django.db import transaction
from django.db.models import F
from django.utils import timezone

from .models import AuthThrottle


def allow_attempt(scope, identity, limit, minutes=15):
    """Only REMOTE_ADDR is used for IP limits; never trust client forwarding headers."""
    now = timezone.now()
    key = hashlib.sha256(f"{scope}:{identity}".encode()).hexdigest()
    AuthThrottle.objects.filter(window_start__lt=now - timedelta(days=1)).delete()
    with transaction.atomic():
        row, _ = AuthThrottle.objects.get_or_create(
            key=key, defaults={"window_start": now}
        )
        AuthThrottle.objects.filter(
            pk=row.pk, window_start__lte=now - timedelta(minutes=minutes)
        ).update(window_start=now, count=0)
        return bool(
            AuthThrottle.objects.filter(pk=row.pk, count__lt=limit).update(
                count=F("count") + 1
            )
        )
