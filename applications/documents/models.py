import secrets
import uuid

from django.db import models

from applications.candidats.models import Candidat
from applications.core.constants import DOCUMENT_CHOICES, EMITTED_DOCUMENT_CHOICES
from applications.paiements.models import ModePaiement


def verification_code():
    return secrets.token_urlsafe(20)


class DemandeDocument(models.Model):
    class Statut(models.TextChoices):
        EN_COURS = "en_cours", "En cours"
        PAYEE = "payee", "Payée"
        GRATUITE = "gratuite", "Gratuite"
        ANNULEE = "annulee", "Annulée"

    candidat = models.ForeignKey(
        Candidat, on_delete=models.PROTECT, related_name="demandes"
    )
    type_document = models.CharField(max_length=24, choices=DOCUMENT_CHOICES)
    montant = models.DecimalField(max_digits=10, decimal_places=2)
    devise = models.CharField(max_length=3, default="HTG")
    mode_paiement = models.ForeignKey(
        ModePaiement, on_delete=models.PROTECT, related_name="demandes"
    )
    transaction_id = models.UUIDField(default=uuid.uuid4, unique=True, editable=False)
    statut = models.CharField(
        max_length=12, choices=Statut.choices, default=Statut.EN_COURS
    )
    etape_courante = models.PositiveSmallIntegerField(default=1)
    identifiant_transaction_fournisseur = models.CharField(max_length=120, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    ip = models.GenericIPAddressField(null=True, blank=True)
    user_agent = models.CharField(max_length=500, blank=True)

    class Meta:
        ordering = ["-created_at"]
        indexes = [models.Index(fields=["statut", "created_at"])]

    def __str__(self):
        return f"{self.transaction_id} - {self.candidat}"

    @property
    def autorisee(self):
        return self.statut in {self.Statut.PAYEE, self.Statut.GRATUITE}


class DocumentEmis(models.Model):
    demande = models.ForeignKey(
        DemandeDocument, on_delete=models.CASCADE, related_name="documents_emis"
    )
    type_document = models.CharField(max_length=12, choices=EMITTED_DOCUMENT_CHOICES)
    code_verification = models.CharField(
        max_length=40, unique=True, default=verification_code, editable=False
    )
    fichier_pdf = models.FileField(upload_to="documents/%Y/%m/", blank=True)
    pdf_version = models.PositiveSmallIntegerField(default=1)
    date_emission = models.DateTimeField(auto_now_add=True)
    nb_impressions = models.PositiveIntegerField(default=0)
    annule = models.BooleanField(default=False)
    annule_le = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ["type_document"]
        constraints = [
            models.UniqueConstraint(
                fields=["demande", "type_document"],
                name="unique_document_emis_par_demande",
            )
        ]

    def __str__(self):
        return f"{self.get_type_document_display()} - {self.code_verification}"
