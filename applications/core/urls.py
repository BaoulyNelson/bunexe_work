from django.contrib.auth.views import (
    LogoutView,
    PasswordChangeDoneView,
    PasswordChangeView,
    PasswordResetCompleteView,
    PasswordResetConfirmView,
    PasswordResetDoneView,
    PasswordResetView,
)
from django.urls import path, reverse_lazy

from .forms import (
    BootstrapPasswordChangeForm,
    BootstrapPasswordResetForm,
    BootstrapSetPasswordForm,
)
from . import views

app_name = "core"

urlpatterns = [
    path("", views.home, name="home"),
    path("inscription/", views.account, name="account"),
    path("profil/", views.profile, name="profile"),
    path(
        "deconnexion/",
        LogoutView.as_view(next_page=reverse_lazy("core:account")),
        name="logout",
    ),
    path(
        "mot-de-passe/oublie/",
        PasswordResetView.as_view(
            form_class=BootstrapPasswordResetForm,
            template_name="core/password_reset_form.html",
            email_template_name="core/password_reset_email.html",
            subject_template_name="core/password_reset_subject.txt",
            success_url=reverse_lazy("core:password_reset_done"),
        ),
        name="password_reset",
    ),
    path(
        "mot-de-passe/oublie/envoye/",
        PasswordResetDoneView.as_view(template_name="core/password_reset_done.html"),
        name="password_reset_done",
    ),
    path(
        "mot-de-passe/r/<uidb64>/<token>/",
        PasswordResetConfirmView.as_view(
            form_class=BootstrapSetPasswordForm,
            template_name="core/password_reset_confirm.html",
            success_url=reverse_lazy("core:password_reset_complete"),
        ),
        name="pw_confirm",
    ),
    path(
        "mot-de-passe/reinitialise/",
        PasswordResetCompleteView.as_view(
            template_name="core/password_reset_complete.html"
        ),
        name="password_reset_complete",
    ),
    path(
        "mot-de-passe/modifier/",
        PasswordChangeView.as_view(
            form_class=BootstrapPasswordChangeForm,
            template_name="core/password_change_form.html",
            success_url=reverse_lazy("core:password_change_done"),
        ),
        name="password_change",
    ),
    path(
        "mot-de-passe/modifie/",
        PasswordChangeDoneView.as_view(template_name="core/password_change_done.html"),
        name="password_change_done",
    ),
    path("demande/nouvelle/", views.new_request, name="new_request"),
    path("demande/etape/<int:step>/", views.wizard_step, name="wizard_step"),
    path("demande/recherche/", views.candidate_search, name="candidate_search"),
    path("resultats/", views.resultats_bac, name="resultats"),
    path("resultats/ticket/", views.download_result_ticket, name="result_ticket"),
    path("e-document/", views.e_document, name="e_document"),
]
