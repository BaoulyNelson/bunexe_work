from django.contrib import messages
from django.contrib.auth import login
from django.contrib.auth.decorators import login_required
from django.db import transaction
from django.http import Http404, HttpResponse
from django.shortcuts import redirect, render
from django.utils import timezone
from django.utils.http import url_has_allowed_host_and_scheme
from django.utils.translation import gettext_lazy as _
from django.views.decorators.http import require_http_methods
from django_ratelimit.decorators import ratelimit

from applications.candidats.models import Candidat
from applications.documents.models import DemandeDocument
from applications.documents.pdf_layouts import generate_result_ticket_pdf
from applications.paiements.models import ModePaiement, Tarif
from applications.paiements.providers import PaymentVerificationError, get_provider
from applications.verification.models import AuditEvenement

from .forms import (
    AccountCreationForm,
    EmailAuthenticationForm,
    CandidateSearchForm,
    DocumentChoiceForm,
    PaymentReferenceForm,
    PaymentSelectionForm,
    ProfileEmailForm,
    ResultLookupForm,
)

STEP_LABELS = [
    _("Info Personnelle"),
    _("Choix documents"),
    _("Mode Paiement"),
    _("Id. Trx Mode Paiement"),
    _("Impression documents"),
]


def _clear_wizard(session):
    for key in ("wizard_step", "candidat_id", "type_document", "demande_id"):
        session.pop(key, None)


def _candidate_from_session(request):
    candidate_id = request.session.get("candidat_id")
    if not candidate_id:
        return None
    return Candidat.objects.filter(pk=candidate_id).first()


def home(request):
    return redirect("core:wizard_step", step=1)


def account(request):
    if request.user.is_authenticated:
        return redirect("core:profile")

    mode = request.POST.get("action") or request.GET.get("mode", "login")
    if mode not in {"login", "register"}:
        mode = "login"
    login_form = EmailAuthenticationForm(request=request)
    registration_form = AccountCreationForm()
    next_url = request.POST.get("next") or request.GET.get("next")

    if request.method == "POST":
        if mode == "login":
            login_form = EmailAuthenticationForm(request=request, data=request.POST)
            if login_form.is_valid():
                login(request, login_form.get_user())
                if next_url and url_has_allowed_host_and_scheme(
                    next_url,
                    allowed_hosts={request.get_host()},
                    require_https=request.is_secure(),
                ):
                    return redirect(next_url)
                return redirect("core:profile")
        elif mode == "register":
            registration_form = AccountCreationForm(request.POST)
            if registration_form.is_valid():
                user = registration_form.save()
                login(request, user)
                messages.success(request, _("Votre compte a été créé avec succès."))
                return redirect("core:profile")

    for form in (login_form, registration_form):
        for field in form.fields.values():
            field.widget.attrs["class"] = "form-control"

    return render(
        request,
        "core/account.html",
        {
            "login_form": login_form,
            "registration_form": registration_form,
            "next": next_url,
            "mode": mode,
        },
    )


@login_required(login_url="core:account")
def profile(request):
    if request.method == "POST":
        form = ProfileEmailForm(request.POST, user=request.user)
        if form.is_valid():
            request.user.email = form.cleaned_data["email"]
            request.user.save(update_fields=["email"])
            messages.success(request, _("Votre adresse e-mail a été mise à jour."))
            return redirect("core:profile")
    else:
        form = ProfileEmailForm(user=request.user)
    return render(request, "core/profile.html", {"form": form})


def new_request(request):
    _clear_wizard(request.session)
    return redirect("core:wizard_step", step=1)


def _wizard_context(step, form, candidat=None, demande=None, tarifs=None, modes=None):
    return {
        "step": step,
        "steps": STEP_LABELS,
        "form": form,
        "candidat": candidat,
        "demande": demande,
        "tarifs": tarifs,
        "modes": modes,
    }


def wizard_step(request, step):
    if step < 1 or step > 5:
        return redirect("core:wizard_step", step=1)
    current_step = request.session.get("wizard_step", 1)
    if step > current_step:
        return redirect("core:wizard_step", step=current_step)
    candidat = _candidate_from_session(request)
    if step > 1 and candidat is None:
        _clear_wizard(request.session)
        return redirect("core:wizard_step", step=1)
    if step > 1 and candidat.statut != Candidat.Statut.ADMIS:
        _clear_wizard(request.session)
        messages.error(
            request,
            _("Échoué : aucun document n'est disponible pour ce dossier."),
        )
        return redirect("core:wizard_step", step=1)

    demande = None
    if step >= 4:
        demande = (
            DemandeDocument.objects.filter(
                pk=request.session.get("demande_id"), candidat=candidat
            )
            .select_related("mode_paiement", "candidat")
            .first()
        )
        if demande is None:
            return redirect("core:wizard_step", step=3)
    if step == 5 and not demande.autorisee:
        return redirect("core:wizard_step", step=4)

    payment_modes = ModePaiement.objects.filter(actif=True) if step == 3 else None

    form = None
    if step == 1:
        form = CandidateSearchForm()
    elif step == 2:
        form = DocumentChoiceForm(candidat=candidat)
    elif step == 3:
        form = PaymentSelectionForm(modes=payment_modes)
    elif step == 4 and not demande.mode_paiement.gratuit:
        form = PaymentReferenceForm()

    if request.method == "POST":
        if step == 1:
            return redirect("core:candidate_search")
        if step == 2:
            form = DocumentChoiceForm(request.POST, candidat=candidat)
            if form.is_valid():
                tarif = Tarif.objects.filter(
                    type_document=form.cleaned_data["type_document"], actif=True
                ).first()
                if tarif is None:
                    form.add_error(
                        None, _("Ce tarif n'est plus disponible. Réessayez.")
                    )
                else:
                    request.session["type_document"] = tarif.type_document
                    request.session["wizard_step"] = 3
                    return redirect("core:wizard_step", step=3)
        elif step == 3:
            form = PaymentSelectionForm(request.POST, modes=payment_modes)
            if form.is_valid():
                mode = form.cleaned_data["mode_paiement"]
                type_document = request.session.get("type_document")
                tarif = Tarif.objects.filter(
                    type_document=type_document, actif=True
                ).first()
                if tarif is None:
                    messages.error(
                        request, _("Le tarif sélectionné n'est plus disponible.")
                    )
                    return redirect("core:wizard_step", step=2)
                with transaction.atomic():
                    demande = DemandeDocument.objects.filter(
                        pk=request.session.get("demande_id"),
                        statut=DemandeDocument.Statut.EN_COURS,
                    ).first()
                    if demande is None:
                        demande = DemandeDocument(candidat=candidat)
                    demande.type_document = type_document
                    if (
                        candidat.statut != Candidat.Statut.ADMIS
                        or candidat.type_resultat == Candidat.TypeResultat.NEUVIEME_AF
                    ) and type_document != "releve":
                        messages.error(
                            request, _("Le certificat est réservé aux candidats admis.")
                        )
                        return redirect("core:wizard_step", step=2)
                    demande.montant = tarif.prix
                    demande.devise = tarif.devise
                    demande.mode_paiement = mode
                    demande.statut = DemandeDocument.Statut.EN_COURS
                    demande.etape_courante = 4
                    demande.ip = _client_ip(request)
                    demande.user_agent = request.META.get("HTTP_USER_AGENT", "")[:500]
                    demande.save()
                request.session["demande_id"] = demande.pk
                request.session["wizard_step"] = 4
                return redirect("core:wizard_step", step=4)
        elif step == 4:
            if demande.mode_paiement.gratuit:
                demande.statut = DemandeDocument.Statut.GRATUITE
                demande.etape_courante = 5
                demande.save(update_fields=["statut", "etape_courante"])
                request.session["wizard_step"] = 5
                return redirect("core:wizard_step", step=5)
            else:
                form = PaymentReferenceForm(request.POST)
                if form.is_valid():
                    try:
                        provider = get_provider(demande.mode_paiement.fournisseur)
                        verified = provider.verify(
                            form.cleaned_data["reference"],
                            demande.montant,
                            demande.devise,
                        )
                    except PaymentVerificationError as exc:
                        form.add_error("reference", str(exc))
                    else:
                        if verified:
                            demande.identifiant_transaction_fournisseur = (
                                form.cleaned_data["reference"]
                            )
                            demande.statut = DemandeDocument.Statut.PAYEE
                            demande.etape_courante = 5
                            demande.save(
                                update_fields=[
                                    "identifiant_transaction_fournisseur",
                                    "statut",
                                    "etape_courante",
                                ]
                            )
                            request.session["wizard_step"] = 5
                            return redirect("core:wizard_step", step=5)
                        form.add_error(
                            "reference",
                            _("Cette transaction n'a pas pu être vérifiée."),
                        )

    tarifs = Tarif.objects.filter(actif=True).order_by("prix") if step == 2 else None
    modes = payment_modes
    return render(
        request,
        "core/wizard_step.html",
        _wizard_context(step, form, candidat, demande, tarifs, modes),
    )


@ratelimit(key="ip", rate="5/m", method="POST", block=True, group="candidate_search")
@require_http_methods(["POST"])
def candidate_search(request):
    _clear_wizard(request.session)
    form = CandidateSearchForm(request.POST)
    if not form.is_valid():
        return render(request, "core/wizard_step.html", _wizard_context(1, form))
    values = form.cleaned_data
    candidat = Candidat.objects.filter(
        annee=values["annee"],
        code=values["code"].strip(),
        nom__iexact=values["nom"].strip(),
        prenom__iexact=values["prenom"].strip(),
    ).first()
    if candidat is None:
        form.add_error(
            None,
            _(
                "Aucun dossier ne correspond à ces informations. Vérifiez l'année, le code, le nom et le prénom."
            ),
        )
        return render(request, "core/wizard_step.html", _wizard_context(1, form))
    if candidat.statut != Candidat.Statut.ADMIS:
        messages.error(
            request,
            _("Échoué : aucun document n'est disponible pour ce dossier."),
        )
        return render(request, "core/wizard_step.html", _wizard_context(1, form))
    request.session["candidat_id"] = candidat.pk
    request.session["wizard_step"] = 2
    return redirect("core:wizard_step", step=2)


def _client_ip(request):
    return request.META.get("REMOTE_ADDR")


@ratelimit(key="ip", rate="10/m", method="GET", block=True, group="result_search")
def resultats_bac(request):
    form = ResultLookupForm(request.GET if "matricule" in request.GET else None)
    candidat = None
    result_type = request.GET.get("type_resultat", "bac_unique")
    if result_type not in Candidat.TypeResultat.values:
        result_type = Candidat.TypeResultat.BAC_UNIQUE
    if form.is_bound and form.is_valid():
        candidat = (
            Candidat.objects.filter(
                type_resultat=result_type,
                code__iexact=form.cleaned_data["matricule"].strip(),
            )
            .order_by("-annee")
            .first()
        )
        if candidat is None:
            form.add_error(
                None,
                _("Aucun résultat ne correspond à ce matricule dans cette catégorie."),
            )
    return render(
        request,
        "core/resultats.html",
        {
            "form": form,
            "candidat": candidat,
            "matieres": candidat.notes_matieres.all() if candidat else [],
            "result_score": (
                format(candidat.total_points.normalize(), "f") if candidat else ""
            ),
            "result_mention": (candidat.mention_affichee if candidat else ""),
            "result_type": result_type,
            "verification_count": AuditEvenement.objects.filter(
                type_evenement=AuditEvenement.Type.VERIFICATION
            ).count(),
            "result_year": timezone.localdate().year,
        },
    )


@ratelimit(key="ip", rate="10/m", method="GET", block=True, group="result_ticket")
def download_result_ticket(request):
    result_type = request.GET.get("type_resultat", Candidat.TypeResultat.BAC_UNIQUE)
    if result_type not in Candidat.TypeResultat.values:
        raise Http404
    form = ResultLookupForm(request.GET)
    if not form.is_valid():
        raise Http404
    candidat = (
        Candidat.objects.filter(
            type_resultat=result_type,
            code__iexact=form.cleaned_data["matricule"].strip(),
        )
        .order_by("-annee")
        .first()
    )
    if candidat is None:
        raise Http404
    response = HttpResponse(
        generate_result_ticket_pdf(candidat), content_type="application/pdf"
    )
    response["Content-Disposition"] = (
        f'attachment; filename="resultat-{candidat.code}-{candidat.annee}.pdf"'
    )
    return response


def e_document(request):
    _clear_wizard(request.session)
    return redirect("core:wizard_step", step=1)
