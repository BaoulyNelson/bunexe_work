from django.core.files.base import ContentFile
from django.db import transaction
from django.db.models import F
from django.http import Http404
from django.urls import reverse

from applications.candidats.models import Candidat
from applications.core.constants import DOCUMENTS_BY_PURCHASE
from applications.verification.models import AuditEvenement

from .models import DemandeDocument, DocumentEmis
from .pdf_layouts import generate_document_pdf

PDF_LAYOUT_VERSION = 3


def issue_document(demande, document_type, request):
    if not demande.autorisee:
        raise Http404
    candidat = demande.candidat
    if candidat.statut != Candidat.Statut.ADMIS:
        raise Http404
    if (
        demande.type_document == "releve_certificat"
        and candidat.type_resultat == Candidat.TypeResultat.NEUVIEME_AF
    ):
        raise Http404
    allowed_types = DOCUMENTS_BY_PURCHASE.get(demande.type_document, ())
    if document_type not in allowed_types:
        raise Http404

    with transaction.atomic():
        document, _ = DocumentEmis.objects.get_or_create(
            demande=demande,
            type_document=document_type,
        )
        if document.annule:
            raise Http404
        if not document.fichier_pdf or document.pdf_version < PDF_LAYOUT_VERSION:
            verification_url = request.build_absolute_uri(
                reverse(
                    "verification:verify_code",
                    args=[document.code_verification],
                )
            )
            pdf_content = generate_document_pdf(document, verification_url)
            if document.fichier_pdf:
                document.fichier_pdf.delete(save=False)
            document.fichier_pdf.save(
                f"{document.code_verification}.pdf",
                ContentFile(pdf_content),
                save=False,
            )
            document.pdf_version = PDF_LAYOUT_VERSION
            document.save(update_fields=["fichier_pdf", "pdf_version"])
        DocumentEmis.objects.filter(pk=document.pk).update(
            nb_impressions=F("nb_impressions") + 1
        )
        AuditEvenement.objects.create(
            type_evenement=AuditEvenement.Type.IMPRESSION,
            document=document,
            ip=request.META.get("REMOTE_ADDR"),
            user_agent=request.META.get("HTTP_USER_AGENT", "")[:500],
        )
    document.refresh_from_db(fields=["nb_impressions"])
    return document
