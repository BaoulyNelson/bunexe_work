import re

from django.http import FileResponse, Http404
from django.shortcuts import get_object_or_404

from .models import DemandeDocument
from .services import issue_document


def _safe_filename_part(value):
    return re.sub(r'[<>:"/\\|?*\x00-\x1f]', "", value).strip(" .")


def download_document(request, transaction_id, document_type):
    demande = get_object_or_404(
        DemandeDocument.objects.select_related("candidat"),
        transaction_id=transaction_id,
    )
    try:
        document = issue_document(demande, document_type, request)
    except Http404:
        raise
    candidat = demande.candidat
    prefix = "e_releve" if document_type == "releve" else "e_diplome"
    candidate_code = f"C-{candidat.annee}{candidat.code}"
    filename = (
        f"{prefix}-{candidate_code}-"
        f"{_safe_filename_part(candidat.prenom)} "
        f"{_safe_filename_part(candidat.nom)}.pdf"
    )
    return FileResponse(
        document.fichier_pdf.open("rb"),
        as_attachment=True,
        filename=filename,
        content_type="application/pdf",
    )
