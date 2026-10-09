from datetime import date
from decimal import Decimal
from io import StringIO
import re
import tempfile
from urllib.parse import unquote, urlsplit
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.core import mail
from django.core.cache import cache
from django.core.management import call_command
from django.test import TestCase
from django.test import override_settings
from django.urls import reverse
from django.utils import timezone

from applications.core.forms import CandidateSearchForm
from applications.candidats.models import Candidat, NoteMatiere
from applications.documents.models import DemandeDocument, DocumentEmis
from applications.paiements.models import ModePaiement, Tarif
from applications.paiements.providers import PROVIDERS
from applications.verification.models import AuditEvenement


class CertificateWizardTests(TestCase):
    def setUp(self):
        cache.clear()
        self.candidat = Candidat.objects.create(
            annee=2025,
            code="0300002669",
            nom="NELSON",
            prenom="Baouly",
            date_naissance=date(2003, 1, 28),
            total_points=991,
            total_sur=1900,
            mention="Admise",
            statut=Candidat.Statut.ADMIS,
        )
        Tarif.objects.create(type_document="releve", prix="150", devise="HTG")
        Tarif.objects.create(type_document="certificat", prix="250", devise="HTG")
        Tarif.objects.create(
            type_document="releve_certificat", prix="400", devise="HTG"
        )
        self.mode_gratuit = ModePaiement.objects.create(
            code="sevis-gratis",
            libelle="SÈVIS GRATIS",
            gratuit=True,
            fournisseur="local",
        )

    def search_candidate(self):
        return self.client.post(
            reverse("core:candidate_search"),
            {
                "annee": "2025",
                "code": self.candidat.code,
                "nom": self.candidat.nom,
                "prenom": self.candidat.prenom,
                "telephone": "",
                "website": "",
            },
        )

    def test_candidate_search_years_cover_1980_through_current_year(self):
        choices = dict(CandidateSearchForm().fields["annee"].choices)
        self.assertIn(1980, choices)
        self.assertIn(timezone.localdate().year, choices)
        self.assertEqual(choices[1980], "1980")

    def test_candidate_codes_require_ten_digits_and_prefix_01_to_10(self):
        valid_payload = {
            "annee": "2025",
            "code": "0300002669",
            "nom": "NELSON",
            "prenom": "Baouly",
            "website": "",
        }
        self.assertTrue(CandidateSearchForm(valid_payload).is_valid())
        for invalid_code in ("DEMO-BAC-001", "1100000000", "030000266", "03000026690"):
            payload = {**valid_payload, "code": invalid_code}
            self.assertFalse(CandidateSearchForm(payload).is_valid(), invalid_code)

    def test_account_page_registers_user_and_starts_session(self):
        response = self.client.post(
            reverse("core:account"),
            {
                "action": "register",
                "username": "nouveau",
                "email": "nouveau@example.com",
                "password1": "UnMotDePasseSolide!2026",
                "password2": "UnMotDePasseSolide!2026",
            },
        )
        self.assertRedirects(response, reverse("core:profile"))
        self.assertTrue(response.wsgi_request.user.is_authenticated)
        self.assertTrue(get_user_model().objects.filter(username="nouveau").exists())

    def test_account_page_logs_in_existing_user(self):
        response = self.client.get(reverse("core:account"))
        self.assertContains(response, "Mot de passe oublié")
        self.assertContains(response, "Se connecter")
        self.assertContains(response, "adresse e-mail")
        response = self.client.get(reverse("core:account") + "?mode=register")
        self.assertContains(response, "Créer mon compte")
        self.assertContains(response, "Vous avez déjà un compte")

        get_user_model().objects.create_user(
            username="existant",
            email="existant@example.com",
            password="UnMotDePasseSolide!2026",
        )
        response = self.client.post(
            reverse("core:account"),
            {
                "action": "login",
                "username": "existant",
                "password": "UnMotDePasseSolide!2026",
            },
        )
        self.assertRedirects(response, reverse("core:profile"))
        self.assertTrue(response.wsgi_request.user.is_authenticated)
        self.client.logout()
        response = self.client.post(
            reverse("core:account"),
            {
                "action": "login",
                "username": "existant@example.com",
                "password": "UnMotDePasseSolide!2026",
            },
        )
        self.assertRedirects(response, reverse("core:profile"))
        self.assertTrue(response.wsgi_request.user.is_authenticated)

    def test_authenticated_account_link_opens_profile(self):
        user = get_user_model().objects.create_user(
            username="membre", password="UnMotDePasseSolide!2026"
        )
        self.client.force_login(user)

        response = self.client.get(reverse("core:account"))

        self.assertRedirects(response, reverse("core:profile"))
        self.assertContains(self.client.get(reverse("core:profile")), "Mon profil")

    def test_profile_updates_email_and_password(self):
        user = get_user_model().objects.create_user(
            username="membre", password="UnMotDePasseSolide!2026"
        )
        self.client.force_login(user)
        response = self.client.post(
            reverse("core:profile"), {"email": "membre@example.com"}
        )
        self.assertRedirects(response, reverse("core:profile"))
        user.refresh_from_db()
        self.assertEqual(user.email, "membre@example.com")

        response = self.client.post(
            reverse("core:password_change"),
            {
                "old_password": "UnMotDePasseSolide!2026",
                "new_password1": "UneAutrePhraseLongue!2027",
                "new_password2": "UneAutrePhraseLongue!2027",
            },
        )
        self.assertRedirects(response, reverse("core:password_change_done"))
        user.refresh_from_db()
        self.assertTrue(user.check_password("UneAutrePhraseLongue!2027"))

    def test_password_reset_email_changes_password(self):
        get_user_model().objects.create_user(
            username="recuperation",
            email="recuperation@example.com",
            password="UnMotDePasseSolide!2026",
        )
        response = self.client.get(reverse("core:password_reset"))
        self.assertContains(response, 'class="form-control"')
        response = self.client.post(
            reverse("core:password_reset"), {"email": "recuperation@example.com"}
        )
        self.assertRedirects(response, reverse("core:password_reset_done"))
        self.assertEqual(len(mail.outbox), 1)
        reset_link = re.search(r"https?://[^\s]+", mail.outbox[0].body).group(0)
        reset_path = urlsplit(reset_link).path
        self.assertTrue(reset_path, mail.outbox[0].body)
        response = self.client.get(reset_path)
        self.assertEqual(response.status_code, 302)
        confirm_path = response.url
        response = self.client.get(confirm_path)
        self.assertTrue(
            response.context.get("validlink"),
            f"Lien {reset_path}, confirmation {confirm_path}, page {response.request['PATH_INFO']}",
        )
        self.assertEqual(
            response.context["form"].fields["new_password1"].widget.attrs["class"],
            "form-control",
        )
        response = self.client.post(
            response.request["PATH_INFO"],
            {
                "new_password1": "UneAutrePhraseLongue!2027",
                "new_password2": "UneAutrePhraseLongue!2027",
            },
        )
        self.assertRedirects(response, reverse("core:password_reset_complete"))
        user = get_user_model().objects.get(username="recuperation")
        self.assertTrue(user.check_password("UneAutrePhraseLongue!2027"))

    def test_result_page_searches_bac_unique_by_matricule(self):
        response = self.client.get(reverse("core:resultats"))
        self.assertContains(response, "Matricule à 10 chiffres")
        self.assertContains(response, "PERM. NS4")
        response = self.client.get(
            reverse("core:resultats"),
            {"matricule": "0300002669", "type_resultat": "bac_unique"},
        )
        self.assertContains(response, "NELSON Baouly")
        self.assertContains(response, "Télécharger le résultat (ticket PDF)")
        ticket = self.client.get(
            reverse("core:result_ticket"),
            {"matricule": self.candidat.code, "type_resultat": "bac_unique"},
        )
        self.assertEqual(ticket.status_code, 200)
        self.assertEqual(ticket["Content-Type"], "application/pdf")
        self.assertTrue(ticket.content.startswith(b"%PDF"))
        self.assertIn(b"R\\311SULTAT OFFICIEL", ticket.content)
        self.assertFalse(
            DemandeDocument.objects.filter(candidat=self.candidat).exists()
        )

    def test_admitted_documents_are_downloaded_through_the_wizard(self):
        self.candidat.prenom = "Andréfaite"
        self.candidat.type_resultat = Candidat.TypeResultat.PERM_PHILO
        self.candidat.serie = "Philo C"
        self.candidat.save(update_fields=["prenom", "type_resultat", "serie"])
        result = self.client.get(
            reverse("core:resultats"),
            {
                "matricule": self.candidat.code,
                "type_resultat": self.candidat.type_resultat,
            },
        )
        self.assertNotContains(result, "Télécharger le relevé de notes")
        self.assertNotContains(result, "Télécharger le diplôme")
        self.assertFalse(
            DemandeDocument.objects.filter(candidat=self.candidat).exists()
        )

        response = self.search_candidate()
        self.assertRedirects(response, reverse("core:wizard_step", args=[2]))
        response = self.client.get(reverse("core:wizard_step", args=[2]))
        self.assertEqual(response.context["form"].initial["type_document"], "releve")
        self.assertEqual(
            [
                label
                for _, label in response.context["form"].fields["type_document"].choices
            ],
            [
                "Relevé seulement (150 gourdes)",
                "Certificat seulement (250 gourdes)",
                "Relevé + Certificat (400 gourdes)",
            ],
        )
        self.assertNotContains(response, "gratuit après réussite")
        response = self.client.post(
            reverse("core:wizard_step", args=[2]),
            {"type_document": "releve_certificat"},
        )
        self.assertRedirects(response, reverse("core:wizard_step", args=[3]))
        response = self.client.get(reverse("core:wizard_step", args=[3]))
        self.assertEqual(response.context["modes"].count(), 1)
        mode = response.context["modes"].get()
        self.assertTrue(mode.gratuit)
        response = self.client.post(
            reverse("core:wizard_step", args=[3]), {"mode_paiement": mode.pk}
        )
        self.assertRedirects(response, reverse("core:wizard_step", args=[4]))
        response = self.client.post(reverse("core:wizard_step", args=[4]))
        self.assertRedirects(response, reverse("core:wizard_step", args=[5]))
        response = self.client.get(reverse("core:wizard_step", args=[5]))
        self.assertContains(response, "IMPRIMER E-RELEVÉ")
        self.assertContains(response, "IMPRIMER E-DIPLÔME")
        demande = DemandeDocument.objects.get(
            candidat=self.candidat, type_document="releve_certificat"
        )
        self.assertEqual(demande.statut, DemandeDocument.Statut.GRATUITE)
        self.assertEqual(demande.montant, Decimal("400"))

        with tempfile.TemporaryDirectory() as media_root:
            with override_settings(MEDIA_ROOT=media_root):
                for document_type in ("releve", "certificat"):
                    download = self.client.get(
                        reverse(
                            "documents:download",
                            args=[demande.transaction_id, document_type],
                        )
                    )
                    self.assertEqual(download.status_code, 200)
                    self.assertEqual(download["Content-Type"], "application/pdf")
                    pdf_content = b"".join(download.streaming_content)
                    prefix = "e_releve" if document_type == "releve" else "e_diplome"
                    self.assertIn(
                        f"{prefix}-C-{self.candidat.annee}{self.candidat.code}-Andréfaite NELSON.pdf",
                        unquote(download["Content-Disposition"]),
                    )
                    self.assertTrue(pdf_content.startswith(b"%PDF"))
                    if document_type == "releve":
                        self.assertEqual(pdf_content.count(b"Philo"), 1)
                    document = DocumentEmis.objects.get(
                        demande=demande, type_document=document_type
                    )
                    verification = self.client.get(
                        reverse(
                            "verification:verify_code",
                            args=[document.code_verification],
                        )
                    )
                    self.assertTrue(verification.context["documents_available"])
                    self.assertContains(
                        verification,
                        reverse("core:wizard_step", args=[1]),
                    )

        non_admitted = Candidat.objects.create(
            annee=2025,
            code="0300000002",
            nom="AJOURNÉ",
            prenom="Élève",
            total_points=896,
            total_sur=1900,
            mention="Assez bien",
            statut=Candidat.Statut.ECHOUE,
        )
        ninth_grade = Candidat.objects.create(
            annee=2025,
            code="0400000002",
            nom="ADMIS",
            prenom="Élève",
            total_points=1000,
            total_sur=1900,
            statut=Candidat.Statut.ADMIS,
            type_resultat=Candidat.TypeResultat.NEUVIEME_AF,
        )
        for candidate in (non_admitted, ninth_grade):
            result = self.client.post(
                reverse("core:candidate_search"),
                {
                    "annee": candidate.annee,
                    "code": candidate.code,
                    "nom": candidate.nom,
                    "prenom": candidate.prenom,
                    "website": "",
                },
            )
            if candidate == non_admitted:
                self.assertEqual(result.status_code, 200)
                self.assertContains(result, "Échoué")
                self.assertNotIn("candidat_id", self.client.session)
                self.assertFalse(
                    DemandeDocument.objects.filter(candidat=candidate).exists()
                )
                continue
            self.assertRedirects(result, reverse("core:wizard_step", args=[2]))
            step = self.client.get(reverse("core:wizard_step", args=[2]))
            if candidate.type_resultat == Candidat.TypeResultat.NEUVIEME_AF:
                self.assertContains(step, "examens de 9ÈME A.F")
                self.assertNotContains(step, "examens du bac")
            choices = [
                value
                for value, _ in step.context["form"].fields["type_document"].choices
            ]
            self.assertEqual(choices, ["releve"])
            self.assertFalse(
                DemandeDocument.objects.filter(
                    candidat=candidate, type_document="releve_certificat"
                ).exists()
            )

    def test_result_buttons_search_their_own_exam_category(self):
        categories = [
            (Candidat.TypeResultat.BAC_UNIQUE, self.candidat.code, self.candidat),
        ]
        for result_type, code, name in (
            (Candidat.TypeResultat.PERM_NS4, "0200000001", "Élève NS4"),
            (Candidat.TypeResultat.PERM_PHILO, "0300000001", "Élève Philo"),
            (Candidat.TypeResultat.NEUVIEME_AF, "0400000001", "Élève 9e"),
        ):
            candidate = Candidat.objects.create(
                annee=2025,
                code=code,
                nom=name,
                prenom="Démo",
                total_points=1200,
                mention="Bien",
                statut=Candidat.Statut.ADMIS,
                type_resultat=result_type,
            )
            categories.append((result_type, code, candidate))

        for result_type, code, candidate in categories:
            NoteMatiere.objects.create(
                candidat=candidate, matiere="Physique", note=40, coefficient=100
            )
            response = self.client.get(
                reverse("core:resultats"),
                {"matricule": code, "type_resultat": result_type},
            )
            self.assertEqual(response.context["candidat"], candidate)
            self.assertEqual(
                response.context["result_score"],
                format(Decimal(str(candidate.total_points)).normalize(), "f"),
            )
            self.assertEqual(
                response.context["result_mention"],
                candidate.mention or candidate.get_statut_display(),
            )
            self.assertContains(
                response,
                f"{response.context['result_score']} sur {candidate.total_sur}",
            )
            self.assertContains(response, "Coefficient")
            self.assertContains(response, 'class="is-failing"', html=False)

    def test_demo_results_seed_is_repeatable_and_covers_all_categories(self):
        call_command("seed_demo_results", stdout=StringIO())
        call_command("seed_demo_results", stdout=StringIO())

        demo_codes = [
            f"{prefix}{index:08d}"
            for prefix in ("01", "02", "03", "04")
            for index in range(1, 13)
        ]
        demo_candidates = Candidat.objects.filter(code__in=demo_codes)
        self.assertEqual(demo_candidates.count(), 48)
        for result_type in Candidat.TypeResultat.values:
            self.assertEqual(
                demo_candidates.filter(type_resultat=result_type).count(), 12
            )
        self.assertEqual(Tarif.objects.filter(actif=True).count(), 3)
        self.assertTrue(
            ModePaiement.objects.filter(
                code="sevis-gratis", actif=True, gratuit=True
            ).exists()
        )
        self.assertEqual(
            demo_candidates.filter(type_resultat=Candidat.TypeResultat.NEUVIEME_AF)
            .first()
            .notes_matieres.count(),
            11,
        )
        for candidate in demo_candidates.filter(
            type_resultat__in=[
                Candidat.TypeResultat.PERM_NS4,
                Candidat.TypeResultat.PERM_PHILO,
            ]
        ):
            self.assertTrue(candidate.notes_matieres.exists())
            self.assertTrue(
                all(
                    note.note * 2 < note.coefficient
                    for note in candidate.notes_matieres.all()
                )
            )

    def test_seeded_admitted_candidate_gets_documents_in_the_wizard(self):
        call_command("seed_demo_results", stdout=StringIO())
        candidat = Candidat.objects.get(code="0100000001")
        response = self.client.post(
            reverse("core:candidate_search"),
            {
                "annee": str(candidat.annee),
                "code": candidat.code,
                "nom": candidat.nom,
                "prenom": candidat.prenom,
                "website": "",
            },
        )
        self.assertRedirects(response, reverse("core:wizard_step", args=[2]))
        response = self.client.get(reverse("core:wizard_step", args=[2]))
        self.assertEqual(
            response.context["form"].fields["type_document"].choices,
            [
                ("releve", "Relevé seulement (150 gourdes)"),
                ("certificat", "Certificat seulement (250 gourdes)"),
                ("releve_certificat", "Relevé + Certificat (400 gourdes)"),
            ],
        )
        self.assertNotContains(response, "gratuit après réussite")
        response = self.client.post(
            reverse("core:wizard_step", args=[2]),
            {"type_document": "releve_certificat"},
        )
        self.assertRedirects(response, reverse("core:wizard_step", args=[3]))
        response = self.client.get(reverse("core:wizard_step", args=[3]))
        mode = response.context["modes"].get()
        self.client.post(
            reverse("core:wizard_step", args=[3]), {"mode_paiement": mode.pk}
        )
        self.assertEqual(self.client.session["wizard_step"], 4)
        response = self.client.post(reverse("core:wizard_step", args=[4]))
        self.assertRedirects(response, reverse("core:wizard_step", args=[5]))
        response = self.client.get(reverse("core:wizard_step", args=[5]))
        self.assertContains(response, "IMPRIMER E-RELEVÉ")
        self.assertContains(response, "IMPRIMER E-DIPLÔME")
        self.assertEqual(
            DemandeDocument.objects.get(
                candidat=candidat, type_document="releve_certificat"
            ).statut,
            DemandeDocument.Statut.GRATUITE,
        )

    def test_verification_home_shows_camera_scanner(self):
        response = self.client.get(reverse("verification:verify"))
        self.assertContains(response, "SCANNER POUR VÉRIFIER")
        self.assertContains(response, "Saisir un code manuellement")

    def complete_free_request(self, document_type="releve"):
        if document_type == "releve_certificat":
            response = self.search_candidate()
            self.assertRedirects(response, reverse("core:wizard_step", args=[2]))
            response = self.client.post(
                reverse("core:wizard_step", args=[2]),
                {"type_document": "releve_certificat"},
            )
            self.assertRedirects(response, reverse("core:wizard_step", args=[3]))
            mode = (
                self.client.get(reverse("core:wizard_step", args=[3]))
                .context["modes"]
                .get()
            )
            response = self.client.post(
                reverse("core:wizard_step", args=[3]), {"mode_paiement": mode.pk}
            )
            self.assertRedirects(response, reverse("core:wizard_step", args=[4]))
            response = self.client.post(reverse("core:wizard_step", args=[4]))
            self.assertRedirects(response, reverse("core:wizard_step", args=[5]))
            return DemandeDocument.objects.get(
                candidat=self.candidat, type_document="releve_certificat"
            )

        self.candidat.type_resultat = Candidat.TypeResultat.NEUVIEME_AF
        self.candidat.total_points = Decimal("1000")
        self.candidat.save(update_fields=["type_resultat", "total_points"])
        response = self.search_candidate()
        self.assertRedirects(response, reverse("core:wizard_step", args=[2]))
        response = self.client.get(reverse("core:wizard_step", args=[2]))
        self.assertEqual(response.status_code, 200)
        response = self.client.post(
            reverse("core:wizard_step", args=[2]), {"type_document": document_type}
        )
        self.assertRedirects(response, reverse("core:wizard_step", args=[3]))
        response = self.client.post(
            reverse("core:wizard_step", args=[3]),
            {"mode_paiement": self.mode_gratuit.pk},
        )
        self.assertRedirects(response, reverse("core:wizard_step", args=[4]))
        demande = DemandeDocument.objects.get(candidat=self.candidat)
        self.assertEqual(
            demande.montant, Tarif.objects.get(type_document=document_type).prix
        )
        response = self.client.post(reverse("core:wizard_step", args=[4]))
        self.assertRedirects(response, reverse("core:wizard_step", args=[5]))
        demande.refresh_from_db()
        self.assertEqual(demande.statut, DemandeDocument.Statut.GRATUITE)
        return demande

    def test_direct_access_to_next_step_is_blocked(self):
        response = self.client.get(reverse("core:wizard_step", args=[3]))
        self.assertRedirects(response, reverse("core:wizard_step", args=[1]))

    def test_e_document_starts_a_new_request_at_personal_information(self):
        session = self.client.session
        session["wizard_step"] = 4
        session["candidat_id"] = self.candidat.pk
        session.save()

        response = self.client.get(reverse("core:e_document"))

        self.assertRedirects(response, reverse("core:wizard_step", args=[1]))
        self.assertNotIn("candidat_id", self.client.session)

    def test_exact_candidate_match_is_required(self):
        response = self.client.post(
            reverse("core:candidate_search"),
            {
                "annee": "2025",
                "code": "0300002669",
                "nom": "NELSON",
                "prenom": "André",
                "website": "",
            },
        )
        self.assertContains(response, "Aucun dossier ne correspond", status_code=200)
        self.assertNotIn("candidat_id", self.client.session)

    def test_candidate_search_is_rate_limited(self):
        payload = {
            "annee": "2025",
            "code": "wrong",
            "nom": "UNKNOWN",
            "prenom": "UNKNOWN",
            "website": "",
        }
        for _ in range(5):
            self.assertEqual(
                self.client.post(reverse("core:candidate_search"), payload).status_code,
                200,
            )
        self.assertEqual(
            self.client.post(reverse("core:candidate_search"), payload).status_code,
            403,
        )

    def test_complete_releve_request_generates_pdf_and_verifies(self):
        demande = self.complete_free_request("releve")
        response = self.client.get(reverse("core:wizard_step", args=[5]))
        self.assertContains(response, "IMPRIMER E-RELEVÉ")
        self.assertNotContains(response, "IMPRIMER E-DIPLÔME")
        response = self.client.get(
            reverse("documents:download", args=[demande.transaction_id, "releve"])
        )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response["Content-Type"], "application/pdf")
        self.assertTrue(response.getvalue().startswith(b"%PDF"))
        document = DocumentEmis.objects.get(demande=demande, type_document="releve")
        self.assertEqual(document.nb_impressions, 1)
        self.assertTrue(document.fichier_pdf)
        verification = self.client.get(
            reverse("verification:verify_code", args=[document.code_verification])
        )
        self.assertContains(verification, "Document authentique")
        self.assertFalse(verification.context["documents_available"])
        self.assertEqual(
            AuditEvenement.objects.filter(type_evenement="impression").count(), 1
        )
        self.assertEqual(
            AuditEvenement.objects.filter(type_evenement="verification").count(), 1
        )

    def test_failed_candidate_is_blocked_and_cannot_download_releve(self):
        self.candidat.total_points = Decimal("949")
        self.candidat.save(update_fields=["total_points"])
        response = self.search_candidate()
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Échoué")
        self.assertContains(response, 'class="alert alert-danger"')
        self.assertNotIn("candidat_id", self.client.session)

        demande = DemandeDocument.objects.create(
            candidat=self.candidat,
            type_document="releve",
            montant=150,
            devise="HTG",
            mode_paiement=self.mode_gratuit,
            statut=DemandeDocument.Statut.GRATUITE,
        )
        response = self.client.get(
            reverse("documents:download", args=[demande.transaction_id, "releve"])
        )
        self.assertEqual(response.status_code, 404)

    def test_failed_candidate_cannot_continue_an_existing_wizard_session(self):
        session = self.client.session
        session["wizard_step"] = 2
        session["candidat_id"] = self.candidat.pk
        session.save()
        self.candidat.total_points = Decimal("949")
        self.candidat.save(update_fields=["total_points"])

        response = self.client.get(reverse("core:wizard_step", args=[2]))

        self.assertRedirects(response, reverse("core:wizard_step", args=[1]))
        self.assertNotIn("candidat_id", self.client.session)

    def test_revoked_document_fails_public_verification(self):
        demande = self.complete_free_request("releve")
        document = DocumentEmis.objects.create(
            demande=demande, type_document="releve", annule=True
        )
        response = self.client.get(
            reverse("verification:verify_code", args=[document.code_verification])
        )
        self.assertContains(response, "document a été annulé")

    def test_bundle_authorizes_both_downloads(self):
        NoteMatiere.objects.create(
            candidat=self.candidat,
            matiere="Physique",
            note=40,
            coefficient=100,
        )
        demande = self.complete_free_request("releve_certificat")
        response = self.client.get(reverse("core:wizard_step", args=[5]))
        self.assertContains(response, "IMPRIMER E-DIPLÔME")
        self.assertContains(response, "IMPRIMER E-RELEVÉ")
        for document_type in ("releve", "certificat"):
            response = self.client.get(
                reverse(
                    "documents:download", args=[demande.transaction_id, document_type]
                )
            )
            self.assertEqual(response.status_code, 200)
            pdf_content = response.getvalue()
            self.assertTrue(pdf_content.startswith(b"%PDF"))
            if document_type == "releve":
                self.assertIn(b"RELEV", pdf_content)
                self.assertIn(b"Physique", pdf_content)
            else:
                self.assertIn(b"DIPL", pdf_content)

    def test_paid_provider_strategy_verifies_transaction_reference(self):
        self.candidat.type_resultat = Candidat.TypeResultat.NEUVIEME_AF
        self.candidat.total_points = Decimal("1000")
        self.candidat.save(update_fields=["type_resultat", "total_points"])

        class TestProvider:
            def verify(self, reference, amount, currency):
                return (
                    reference == "CONFIRMED-123"
                    and amount == Tarif.objects.get(type_document="releve").prix
                    and currency == "HTG"
                )

        mode = ModePaiement.objects.create(
            code="test-payant", libelle="Paiement de test", fournisseur="test-provider"
        )
        with patch.dict(PROVIDERS, {"test-provider": TestProvider}):
            self.search_candidate()
            self.client.post(
                reverse("core:wizard_step", args=[2]), {"type_document": "releve"}
            )
            self.client.post(
                reverse("core:wizard_step", args=[3]), {"mode_paiement": mode.pk}
            )
            response = self.client.post(
                reverse("core:wizard_step", args=[4]), {"reference": "CONFIRMED-123"}
            )
        self.assertRedirects(response, reverse("core:wizard_step", args=[5]))
        demande = DemandeDocument.objects.get(candidat=self.candidat)
        self.assertEqual(demande.statut, DemandeDocument.Statut.PAYEE)
        self.assertEqual(demande.identifiant_transaction_fournisseur, "CONFIRMED-123")
