from django.db import models

from applications.documents.models import DocumentEmis


class AuditEvenement(models.Model):
    class Type(models.TextChoices):
        IMPRESSION = "impression", "Impression"
        VERIFICATION = "verification", "Vérification"

    type_evenement = models.CharField(max_length=16, choices=Type.choices)
    document = models.ForeignKey(
        DocumentEmis,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="evenements_audit",
    )
    code_saisi = models.CharField(max_length=80, blank=True)
    ip = models.GenericIPAddressField(null=True, blank=True)
    user_agent = models.CharField(max_length=500, blank=True)
    cree_le = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-cree_le"]
        indexes = [models.Index(fields=["type_evenement", "cree_le"])]

    def __str__(self):
        return f"{self.get_type_evenement_display()} - {self.cree_le:%Y-%m-%d %H:%M}"
