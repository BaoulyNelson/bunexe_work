from django.shortcuts import get_object_or_404, render
from django.utils.translation import gettext as _
from django.views.decorators.http import require_http_methods

from applications.candidats.models import Candidat
from applications.documents.models import DocumentEmis

from .models import AuditEvenement


@require_http_methods(["GET", "POST"])
def verify_code(request, code=None):
    submitted_code = (code or request.POST.get("code", "")).strip()
    document = None
    if submitted_code:
        document = (
            DocumentEmis.objects.select_related("demande__candidat")
            .filter(code_verification=submitted_code)
            .first()
        )
        AuditEvenement.objects.create(
            type_evenement=AuditEvenement.Type.VERIFICATION,
            document=document,
            code_saisi=submitted_code[:80],
            ip=request.META.get("REMOTE_ADDR"),
            user_agent=request.META.get("HTTP_USER_AGENT", "")[:500],
        )
    return render(
        request,
        "verification/result.html",
        {
            "code": submitted_code,
            "document": document,
            "not_found": bool(submitted_code) and document is None,
            "revoked": bool(document and document.annule),
            "documents_available": bool(
                document
                and not document.annule
                and document.demande.candidat.statut == Candidat.Statut.ADMIS
                and document.demande.candidat.type_resultat
                != Candidat.TypeResultat.NEUVIEME_AF
            ),
        },
    )
