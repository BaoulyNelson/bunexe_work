from django.utils.translation import gettext_lazy as _

DOCUMENT_CHOICES = [
    ("releve", _("Relevé seulement")),
    ("certificat", _("Certificat seulement")),
    ("releve_certificat", _("Relevé + Certificat")),
]

EMITTED_DOCUMENT_CHOICES = [
    ("releve", _("E-relevé")),
    ("certificat", _("E-diplôme")),
]

DOCUMENTS_BY_PURCHASE = {
    "releve": ("releve",),
    "certificat": ("certificat",),
    "releve_certificat": ("releve", "certificat"),
}
