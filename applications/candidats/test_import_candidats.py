import tempfile
from io import StringIO
from pathlib import Path

from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group, Permission
from django.core.management import call_command
from django.test import TestCase
from django.urls import reverse
from openpyxl import Workbook

from applications.candidats.models import Candidat, MatiereProgramme, NoteMatiere
from applications.documents.models import DemandeDocument, DocumentEmis
from applications.paiements.models import ModePaiement, Tarif
from applications.verification.models import AuditEvenement


class ImportCandidatsTests(TestCase):
    def test_subject_catalog_import_is_repeatable_and_visible_in_admin(self):
        admin_user = get_user_model().objects.create_superuser(
            username="admin-matieres",
            email="admin-matieres@example.com",
            password="MotDePasseSolide!2026",
        )
        self.client.force_login(admin_user)
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "matieres_menfp.csv"
            path.write_text(
                "examen,serie,matiere,coefficient,ordre\n"
                "9AF,,Créole,300,1\n"
                "NS4,SES,Économie,400,1\n",
                encoding="utf-8",
            )
            call_command("import_matieres", str(path), stdout=StringIO())
            path.write_text(
                "examen,serie,matiere,coefficient,ordre\n"
                "9AF,,Créole,250,1\n"
                "NS4,SES,Économie,400,1\n",
                encoding="utf-8",
            )
            call_command("import_matieres", str(path), stdout=StringIO())

        self.assertEqual(MatiereProgramme.objects.count(), 2)
        self.assertEqual(MatiereProgramme.objects.get(examen="9AF").coefficient, 250)
        response = self.client.get(
            reverse("admin:candidats_matiereprogramme_changelist")
        )
        self.assertContains(response, "Créole")
        self.assertContains(response, "Économie")

    def test_admin_shows_status_as_readonly_and_calculates_it_on_save(self):
        admin_user = get_user_model().objects.create_superuser(
            username="admin-candidats",
            email="admin@example.com",
            password="MotDePasseSolide!2026",
        )
        self.client.force_login(admin_user)
        add_url = reverse("admin:candidats_candidat_add")
        response = self.client.get(add_url)
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Statut")
        self.assertNotIn("statut", response.context["adminform"].form.fields)
        inline_formset = response.context["inline_admin_formsets"][0].formset
        prefix = inline_formset.prefix
        self.assertIn("matiere", inline_formset.forms[0].fields)

        response = self.client.post(
            add_url,
            {
                "type_resultat": Candidat.TypeResultat.BAC_UNIQUE,
                "annee": "2025",
                "code": "0300002669",
                "nom": "NELSON",
                "prenom": "Andréfaite",
                "total_points": "950",
                "total_sur": "1900",
                "mention": "",
                "serie": "",
                "ecole": "",
                "_save": "Enregistrer",
                f"{prefix}-TOTAL_FORMS": "1",
                f"{prefix}-INITIAL_FORMS": "0",
                f"{prefix}-MIN_NUM_FORMS": "0",
                f"{prefix}-MAX_NUM_FORMS": "1000",
                f"{prefix}-0-matiere": "Philosophie",
                f"{prefix}-0-note": "120",
                f"{prefix}-0-coefficient": "200",
            },
        )
        self.assertEqual(response.status_code, 302)
        candidat = Candidat.objects.get(code="0300002669")
        self.assertEqual(candidat.statut, Candidat.Statut.ADMIS)
        note = candidat.notes_matieres.get()
        self.assertEqual(
            (note.matiere, note.note, note.coefficient), ("Philosophie", 120, 200)
        )

    def test_editing_complete_subject_set_recalculates_total_and_status(self):
        admin_user = get_user_model().objects.create_superuser(
            username="admin-notes",
            email="admin-notes@example.com",
            password="MotDePasseSolide!2026",
        )
        self.client.force_login(admin_user)
        candidat = Candidat.objects.create(
            annee=2025,
            code="0300002669",
            nom="NELSON",
            prenom="Andréfaite",
            total_points=960,
            total_sur=1900,
            serie="SES",
        )
        subject_values = (
            ("Économie", 200, 400),
            ("Histoire et Géographie", 200, 400),
            ("Philosophie", 100, 200),
            ("Créole", 100, 200),
            ("Mathématiques", 100, 200),
            ("Anglais / Espagnol", 100, 200),
            ("Physique", 60, 100),
            ("SVT", 50, 100),
            ("Chimie", 50, 100),
        )
        for subject, note, coefficient in subject_values:
            NoteMatiere.objects.create(
                candidat=candidat,
                matiere=subject,
                note=note,
                coefficient=coefficient,
            )

        change_url = reverse("admin:candidats_candidat_change", args=[candidat.pk])
        response = self.client.get(change_url)
        formset = response.context["inline_admin_formsets"][0].formset
        prefix = formset.prefix
        payload = {
            "type_resultat": candidat.type_resultat,
            "annee": candidat.annee,
            "code": candidat.code,
            "nom": candidat.nom,
            "prenom": candidat.prenom,
            "date_naissance": "",
            "lieu_naissance": "",
            "telephone": "",
            "total_points": candidat.total_points,
            "total_sur": candidat.total_sur,
            "mention": "",
            "serie": candidat.serie,
            "ecole": "",
            "_save": "Enregistrer",
            f"{prefix}-TOTAL_FORMS": str(len(formset.forms)),
            f"{prefix}-INITIAL_FORMS": str(formset.initial_form_count()),
            f"{prefix}-MIN_NUM_FORMS": "0",
            f"{prefix}-MAX_NUM_FORMS": "1000",
        }
        for index, inline_form in enumerate(formset.forms):
            inline_note = inline_form.instance
            payload[f"{prefix}-{index}-id"] = inline_note.pk or ""
            payload[f"{prefix}-{index}-candidat"] = candidat.pk
            payload[f"{prefix}-{index}-matiere"] = inline_note.matiere or ""
            payload[f"{prefix}-{index}-note"] = (
                (0 if index == 0 else inline_note.note) if inline_note.pk else ""
            )
            payload[f"{prefix}-{index}-coefficient"] = inline_note.coefficient or ""

        response = self.client.post(change_url, payload)
        self.assertEqual(response.status_code, 302)
        candidat.refresh_from_db()
        self.assertEqual(candidat.total_points, 760)
        self.assertEqual(candidat.statut, Candidat.Statut.ECHOUE)

    def test_csv_backup_restores_related_data_and_accounts(self):
        MatiereProgramme.objects.create(
            examen="9AF",
            matiere="Créole",
            coefficient=300,
            ordre=1,
        )
        candidat = Candidat.objects.create(
            annee=2025,
            code="0300002669",
            nom="NELSON",
            prenom="Andréfaite",
        )
        NoteMatiere.objects.create(
            candidat=candidat, matiere="Philosophie", note=120, coefficient=200
        )
        tarif = Tarif.objects.create(type_document="releve", prix="150.00")
        mode = ModePaiement.objects.create(
            code="paiement-csv", libelle="Paiement CSV", fournisseur="local"
        )
        group = Group.objects.create(name="Gestionnaires CSV")
        permission = Permission.objects.get(
            content_type__app_label="candidats", codename="view_candidat"
        )
        group.permissions.add(permission)
        user = get_user_model().objects.create_user(
            username="compte-csv", password="MotDePasseSolide!2026"
        )
        user.groups.add(group)
        user.user_permissions.add(permission)
        demande = DemandeDocument.objects.create(
            candidat=candidat,
            type_document="releve",
            montant=tarif.prix,
            devise=tarif.devise,
            mode_paiement=mode,
        )
        document = DocumentEmis.objects.create(
            demande=demande,
            type_document="releve",
            code_verification="CODE-CSV-001",
        )
        AuditEvenement.objects.create(
            type_evenement=AuditEvenement.Type.IMPRESSION,
            document=document,
            ip="127.0.0.1",
        )

        with tempfile.TemporaryDirectory() as temporary_directory:
            backup_directory = Path(temporary_directory) / "sauvegarde"
            call_command("exporter_donnees_csv", str(backup_directory))

            get_user_model().objects.all().delete()
            Group.objects.all().delete()
            AuditEvenement.objects.all().delete()
            DocumentEmis.objects.all().delete()
            DemandeDocument.objects.all().delete()
            NoteMatiere.objects.all().delete()
            Candidat.objects.all().delete()
            Tarif.objects.all().delete()
            ModePaiement.objects.all().delete()

            call_command("importer_donnees_csv", str(backup_directory))

        restored_candidate = Candidat.objects.get(code="0300002669")
        self.assertEqual(restored_candidate.notes_matieres.get().matiere, "Philosophie")
        self.assertEqual(MatiereProgramme.objects.get(examen="9AF").matiere, "Créole")
        restored_user = get_user_model().objects.get(username="compte-csv")
        self.assertTrue(restored_user.check_password("MotDePasseSolide!2026"))
        self.assertEqual(restored_user.groups.get().name, "Gestionnaires CSV")
        self.assertTrue(
            restored_user.user_permissions.filter(pk=permission.pk).exists()
        )
        self.assertTrue(
            Group.objects.get(name="Gestionnaires CSV")
            .permissions.filter(pk=permission.pk)
            .exists()
        )
        restored_document = DocumentEmis.objects.get(code_verification="CODE-CSV-001")
        self.assertEqual(restored_document.demande.candidat, restored_candidate)
        self.assertTrue(
            AuditEvenement.objects.filter(document=restored_document).exists()
        )

    def test_imports_utf8_csv_and_updates_by_year_and_code(self):
        content = (
            "annee,code,nom,prenom,date_naissance,total_points,statut\n"
            "2025,0300002669,NELSON,Andréfaite,28/01/2003,991,Ajournée\n"
        )
        with tempfile.NamedTemporaryFile(
            mode="w", encoding="utf-8", suffix=".csv", delete=False
        ) as csv_file:
            csv_file.write(content)
            csv_path = Path(csv_file.name)
        try:
            call_command(
                "import_candidats",
                str(csv_path),
                stdout=StringIO(),
            )
            candidat = Candidat.objects.get(annee=2025, code="0300002669")
            self.assertEqual(candidat.prenom, "Andréfaite")
            self.assertEqual(candidat.statut, Candidat.Statut.ADMIS)
            call_command(
                "import_candidats",
                str(csv_path),
                stdout=StringIO(),
            )
            self.assertEqual(
                Candidat.objects.filter(annee=2025, code="0300002669").count(), 1
            )
        finally:
            csv_path.unlink(missing_ok=True)

    def test_import_ignores_csv_status_and_calculates_it_from_scores(self):
        content = (
            "annee,code,nom,prenom,total_points,total_sur,statut\n"
            "2025,0300002669,NELSON,Andréfaite,949,1900,admis\n"
            "2025,0400000001,PIERRE,Jean,950,1900,ajourne\n"
        )
        with tempfile.NamedTemporaryFile(
            mode="w", encoding="utf-8", suffix=".csv", delete=False
        ) as csv_file:
            csv_file.write(content)
            csv_path = Path(csv_file.name)
        try:
            call_command("import_candidats", str(csv_path), stdout=StringIO())
            self.assertEqual(
                Candidat.objects.get(code="0300002669").statut,
                Candidat.Statut.ECHOUE,
            )
            self.assertEqual(
                Candidat.objects.get(code="0400000001").statut,
                Candidat.Statut.ADMIS,
            )
        finally:
            csv_path.unlink(missing_ok=True)

    def test_status_recalculates_when_scores_are_partially_updated(self):
        candidat = Candidat.objects.create(
            annee=2025,
            code="0300002669",
            nom="NELSON",
            prenom="Andréfaite",
            total_points=949,
            total_sur=1900,
            statut=Candidat.Statut.ADMIS,
        )
        self.assertEqual(candidat.statut, Candidat.Statut.ECHOUE)
        candidat.total_points = 950
        candidat.save(update_fields=["total_points"])
        candidat.refresh_from_db()
        self.assertEqual(candidat.statut, Candidat.Statut.ADMIS)

    def test_failed_candidate_does_not_display_stale_passing_mention(self):
        candidat = Candidat.objects.create(
            annee=2026,
            code="1091434105",
            nom="AUGUSTIN",
            prenom="Esther",
            total_points=896,
            total_sur=1900,
            mention="Assez bien",
        )
        self.assertEqual(candidat.mention, "Assez bien")
        self.assertEqual(candidat.mention_affichee, "Échoué")

    def test_imports_xlsx_rows(self):
        with tempfile.NamedTemporaryFile(suffix=".xlsx", delete=False) as excel_file:
            excel_path = Path(excel_file.name)
        workbook = Workbook()
        sheet = workbook.active
        sheet.append(["annee", "code", "nom", "prenom", "statut"])
        sheet.append([2025, "0400000001", "PIERRE", "Jean", "ajourne"])
        workbook.save(excel_path)
        try:
            call_command("import_candidats", str(excel_path), stdout=StringIO())
            candidat = Candidat.objects.get(annee=2025, code="0400000001")
            self.assertEqual(candidat.nom, "PIERRE")
            self.assertEqual(candidat.statut, Candidat.Statut.ECHOUE)
        finally:
            excel_path.unlink(missing_ok=True)

    def test_imports_result_category(self):
        content = (
            "annee,code,nom,prenom,type_resultat\n"
            "2025,0200000001,JEAN,Mireille,perm_ns4\n"
        )
        with tempfile.NamedTemporaryFile(
            mode="w", encoding="utf-8", suffix=".csv", delete=False
        ) as csv_file:
            csv_file.write(content)
            csv_path = Path(csv_file.name)
        try:
            call_command("import_candidats", str(csv_path), stdout=StringIO())
            candidat = Candidat.objects.get(code="0200000001")
            self.assertEqual(candidat.type_resultat, Candidat.TypeResultat.PERM_NS4)
        finally:
            csv_path.unlink(missing_ok=True)

    def test_imports_subject_note_and_coefficient(self):
        content = (
            "annee,code,nom,prenom,type_resultat,matiere,note,coefficient\n"
            "2025,0200000001,JEAN,Mireille,perm_ns4,Physique,40,100\n"
        )
        with tempfile.NamedTemporaryFile(
            mode="w", encoding="utf-8", suffix=".csv", delete=False
        ) as csv_file:
            csv_file.write(content)
            csv_path = Path(csv_file.name)
        try:
            call_command("import_candidats", str(csv_path), stdout=StringIO())
            candidat = Candidat.objects.get(code="0200000001")
            note = NoteMatiere.objects.get(candidat=candidat, matiere="Physique")
            self.assertEqual((note.note, note.coefficient), (40, 100))
            self.assertTrue(note.is_failing)
        finally:
            csv_path.unlink(missing_ok=True)
