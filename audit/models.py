"""Immutable audit event log."""
from django.db import models
from django.conf import settings


class AuditEvent(models.Model):
    """
    Append-only security and business audit log.
    Records must not be deleted or modified by ordinary application code.
    """

    timestamp = models.DateTimeField(auto_now_add=True, db_index=True)
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="audit_events",
    )
    username_snapshot = models.CharField(max_length=150, blank=True)
    event_type = models.CharField(max_length=80, db_index=True)
    description = models.TextField(blank=True)
    ip_address = models.GenericIPAddressField(null=True, blank=True)
    extra = models.JSONField(default=dict, blank=True)

    class Meta:
        ordering = ["-timestamp"]
        verbose_name = "Audit Event"
        verbose_name_plural = "Audit Events"

    def __str__(self):
        return f"[{self.timestamp:%Y-%m-%d %H:%M}] {self.event_type} — {self.username_snapshot}"
