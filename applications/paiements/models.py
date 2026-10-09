from django.db import models

from applications.core.constants import DOCUMENT_CHOICES


class Tarif(models.Model):
    type_document = models.CharField(
        max_length=24, choices=DOCUMENT_CHOICES, unique=True
    )
    prix = models.DecimalField(max_digits=10, decimal_places=2)
    devise = models.CharField(max_length=3, default="HTG")
    actif = models.BooleanField(default=True)

    class Meta:
        ordering = ["prix"]

    def __str__(self):
        return f"{self.get_type_document_display()} : {self.prix} {self.devise}"


class ModePaiement(models.Model):
    code = models.SlugField(max_length=32, unique=True)
    libelle = models.CharField(max_length=100)
    logo = models.ImageField(upload_to="paiements/logos/", blank=True)
    actif = models.BooleanField(default=True)
    gratuit = models.BooleanField(default=False)
    fournisseur = models.CharField(max_length=60, default="local")

    class Meta:
        ordering = ["libelle"]

    def __str__(self):
        return self.libelle
