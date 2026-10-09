from django import forms
from django.contrib.auth import get_user_model
from django.contrib.auth import authenticate
from django.contrib.auth.forms import (
    AuthenticationForm,
    PasswordChangeForm,
    PasswordResetForm,
    SetPasswordForm,
    UserCreationForm,
    UsernameField,
)
from django.utils import timezone
from django.utils.translation import gettext_lazy as _

from applications.candidats.models import (
    CANDIDATE_CODE_VALIDATOR,
    Candidat,
)
from applications.paiements.models import ModePaiement, Tarif


class EmailAuthenticationForm(AuthenticationForm):
    username = UsernameField(
        label=_("Nom d'utilisateur ou adresse e-mail"),
        widget=forms.TextInput(attrs={"autofocus": True, "autocomplete": "username"}),
    )

    def clean(self):
        username = self.cleaned_data.get("username")
        password = self.cleaned_data.get("password")
        if username and password:
            usernames = [username]
            if "@" in username:
                usernames = list(
                    get_user_model()
                    .objects.filter(email__iexact=username)
                    .values_list("username", flat=True)
                )
                if username not in usernames:
                    usernames.append(username)

            self.user_cache = None
            for login_username in usernames:
                self.user_cache = authenticate(
                    self.request, username=login_username, password=password
                )
                if self.user_cache is not None:
                    break

            if self.user_cache is None:
                raise self.get_invalid_login_error()
            self.confirm_login_allowed(self.user_cache)
        return self.cleaned_data


class BootstrapPasswordFormMixin:
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for field in self.fields.values():
            field.widget.attrs["class"] = "form-control"


class BootstrapPasswordResetForm(BootstrapPasswordFormMixin, PasswordResetForm):
    pass


class BootstrapSetPasswordForm(BootstrapPasswordFormMixin, SetPasswordForm):
    pass


class BootstrapPasswordChangeForm(BootstrapPasswordFormMixin, PasswordChangeForm):
    pass


class CandidateSearchForm(forms.Form):
    annee = forms.ChoiceField(
        label=_("Année d'examen"), widget=forms.Select(attrs={"class": "form-select"})
    )
    code = forms.CharField(
        label=_("Numéro de candidat / code"),
        max_length=10,
        min_length=10,
        validators=[CANDIDATE_CODE_VALIDATOR],
        widget=forms.TextInput(
            attrs={
                "class": "form-control",
                "placeholder": "0300002669",
                "inputmode": "numeric",
                "pattern": r"(?:0[1-9]|10)[0-9]{8}",
                "data-candidate-code": "",
                "title": _("10 chiffres, en commençant par 01 à 10"),
            }
        ),
    )
    nom = forms.CharField(
        label=_("Nom"),
        max_length=100,
        widget=forms.TextInput(
            attrs={"class": "form-control", "placeholder": "Nom de famille"}
        ),
    )
    prenom = forms.CharField(
        label=_("Prénom"),
        max_length=100,
        widget=forms.TextInput(
            attrs={"class": "form-control", "placeholder": "Prénom(s)"}
        ),
    )
    telephone = forms.CharField(
        label=_("Téléphone"),
        max_length=32,
        required=False,
        widget=forms.TextInput(
            attrs={
                "class": "form-control",
                "placeholder": "Telephone",
                "autocomplete": "tel",
            }
        ),
    )
    website = forms.CharField(required=False, widget=forms.HiddenInput)

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["annee"].choices = [("", _("Choisissez une année"))] + [
            (year, str(year)) for year in range(timezone.localdate().year, 1979, -1)
        ]

    def clean(self):
        cleaned_data = super().clean()
        if cleaned_data.get("website"):
            raise forms.ValidationError(_("La demande n'a pas pu être traitée."))
        return cleaned_data


class ResultLookupForm(forms.Form):
    matricule = forms.CharField(
        label=_("Matricule"),
        max_length=10,
        min_length=10,
        validators=[CANDIDATE_CODE_VALIDATOR],
        widget=forms.TextInput(
            attrs={
                "class": "form-control",
                "placeholder": _("Matricule à 10 chiffres"),
                "autocomplete": "off",
                "autofocus": True,
                "inputmode": "numeric",
                "pattern": r"(?:0[1-9]|10)[0-9]{8}",
                "data-candidate-code": "",
                "title": _("10 chiffres, en commençant par 01 à 10"),
            }
        ),
    )


class AccountCreationForm(UserCreationForm):
    email = forms.EmailField(
        label=_("Adresse e-mail"),
        widget=forms.EmailInput(
            attrs={"class": "form-control", "autocomplete": "email"}
        ),
    )

    class Meta(UserCreationForm.Meta):
        model = get_user_model()
        fields = (*UserCreationForm.Meta.fields, "email")

    def clean_email(self):
        email = self.cleaned_data["email"].strip()
        if get_user_model().objects.filter(email__iexact=email).exists():
            raise forms.ValidationError(_("Cette adresse e-mail est déjà utilisée."))
        return email


class ProfileEmailForm(forms.Form):
    email = forms.EmailField(
        label=_("Adresse e-mail de récupération"),
        widget=forms.EmailInput(
            attrs={"class": "form-control", "autocomplete": "email"}
        ),
    )

    def __init__(self, *args, user, **kwargs):
        self.user = user
        super().__init__(*args, initial={"email": user.email}, **kwargs)

    def clean_email(self):
        email = self.cleaned_data["email"].strip()
        users = (
            get_user_model()
            .objects.filter(email__iexact=email)
            .exclude(pk=self.user.pk)
        )
        if users.exists():
            raise forms.ValidationError(_("Cette adresse e-mail est déjà utilisée."))
        return email


class DocumentChoiceForm(forms.Form):
    type_document = forms.ChoiceField(
        label=_("Je veux imprimer :"),
        widget=forms.RadioSelect,
    )

    def __init__(self, *args, candidat, **kwargs):
        super().__init__(*args, **kwargs)
        tarifs = Tarif.objects.filter(actif=True).order_by("prix")
        if (
            candidat.statut != Candidat.Statut.ADMIS
            or candidat.type_resultat == Candidat.TypeResultat.NEUVIEME_AF
        ):
            tarifs = tarifs.exclude(
                type_document__in=["certificat", "releve_certificat"]
            )
        choices = [
            (
                tarif.type_document,
                f"{tarif.get_type_document_display()} ({format(tarif.prix.normalize(), 'f')} {'gourdes' if tarif.devise == 'HTG' else tarif.devise})",
            )
            for tarif in tarifs
        ]
        self.fields["type_document"].choices = choices
        if choices and not self.is_bound:
            self.initial["type_document"] = choices[0][0]


class PaymentSelectionForm(forms.Form):
    mode_paiement = forms.ModelChoiceField(
        queryset=ModePaiement.objects.none(),
        widget=forms.RadioSelect,
        label=_("Mode de paiement"),
    )

    def __init__(self, *args, modes=None, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["mode_paiement"].queryset = (
            modes if modes is not None else ModePaiement.objects.filter(actif=True)
        )


class PaymentReferenceForm(forms.Form):
    reference = forms.CharField(
        label=_("Identifiant de transaction"),
        max_length=120,
        widget=forms.TextInput(attrs={"class": "form-control", "autocomplete": "off"}),
    )
