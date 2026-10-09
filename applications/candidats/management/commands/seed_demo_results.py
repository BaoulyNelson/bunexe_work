from datetime import date

from django.core.management.base import BaseCommand
from django.db import transaction
from django.utils import timezone

from applications.candidats.models import Candidat, NoteMatiere
from applications.paiements.models import ModePaiement, Tarif

FIRST_NAMES = (
    "Mireille",
    "Jean-Marc",
    "Judeline",
    "Frantz",
    "Roseline",
    "Wilner",
    "Natacha",
    "Robenson",
    "Carline",
    "Stevens",
    "Judith",
    "Samuel",
)

LAST_NAMES = (
    "Jean",
    "Joseph",
    "Pierre",
    "Charles",
    "Augustin",
    "Desir",
    "Louis",
    "Paul",
    "Alexandre",
    "Michel",
    "Laurent",
    "Beauvoir",
)

SCHOOLS = (
    "Lycée de démonstration",
    "Collège du Centre (démo)",
    "Institution Horizon (démo)",
)

BAC_SERIES = {
    "SES": (
        ("Économie", 400),
        ("Histoire et Géographie", 400),
        ("Philosophie", 200),
        ("Créole", 200),
        ("Mathématiques", 200),
        ("Anglais / Espagnol", 200),
        ("Physique", 100),
        ("SVT", 100),
        ("Chimie", 100),
    ),
    "SMP": (
        ("Mathématiques", 400),
        ("Physique", 400),
        ("Philosophie", 200),
        ("Français / Chimie", 200),
        ("Créole", 200),
        ("Anglais / Espagnol", 200),
        ("Histoire et Géographie", 200),
        ("SVT", 100),
    ),
    "SVT": (
        ("SVT / Biologie", 400),
        ("Chimie", 300),
        ("Mathématiques", 200),
        ("Physique", 200),
        ("Philosophie", 200),
        ("Créole", 200),
        ("Anglais / Espagnol", 200),
        ("Histoire et Géographie", 200),
    ),
    "L'A": (
        ("Philosophie / Français", 400),
        ("Créole", 300),
        ("Anglais / Espagnol", 300),
        ("Histoire et Géographie", 300),
        ("Arts / Éducation Artistique", 200),
        ("Mathématiques", 200),
        ("Sciences (Physique/Chimie/SVT)", 200),
    ),
}

NINE_AF_SUBJECTS = (
    ("Créole", 300),
    ("Français", 300),
    ("Sciences Sociales", 300),
    ("Sciences Expérimentales", 300),
    ("Mathématiques", 300),
    ("Anglais", 200),
    ("Espagnol", 200),
    ("ETAP", 200),
    ("EPS", 200),
    ("EEA", 200),
    ("Éducation à la Citoyenneté", 200),
)

PHILO_SERIES = {
    "Philo A": (
        ("Philosophie", 400),
        ("Français", 300),
        ("Créole", 200),
        ("Histoire et Géographie", 300),
        ("Anglais", 200),
        ("Mathématiques", 200),
        ("Sciences", 300),
    ),
    "Philo C": (
        ("Philosophie", 400),
        ("Mathématiques", 400),
        ("Physique", 300),
        ("Français", 200),
        ("Créole", 200),
        ("Histoire et Géographie", 200),
        ("Langue vivante", 200),
    ),
    "Philo D": (
        ("Philosophie", 400),
        ("SVT", 400),
        ("Chimie", 300),
        ("Mathématiques", 200),
        ("Français", 200),
        ("Créole", 200),
        ("Histoire et Géographie", 200),
    ),
}

CATEGORIES = (
    (Candidat.TypeResultat.BAC_UNIQUE, "01", "BAC", 18),
    (Candidat.TypeResultat.PERM_NS4, "02", "NS4", 16),
    (Candidat.TypeResultat.PERM_PHILO, "03", "PHILO", 18),
    (Candidat.TypeResultat.NEUVIEME_AF, "04", "9AF", 14),
)


class Command(BaseCommand):
    help = "Crée ou actualise 12 dossiers fictifs par catégorie de résultats."

    def handle(self, *args, **options):
        current_year = timezone.localdate().year
        created_count = 0
        updated_count = 0
        seeded_candidates = []

        with transaction.atomic():
            for document_type, price in (
                ("releve", 150),
                ("certificat", 250),
                ("releve_certificat", 400),
            ):
                Tarif.objects.update_or_create(
                    type_document=document_type,
                    defaults={"prix": price, "devise": "HTG", "actif": True},
                )
            ModePaiement.objects.update_or_create(
                code="sevis-gratis",
                defaults={
                    "libelle": "SÈVIS GRATIS",
                    "actif": True,
                    "gratuit": True,
                    "fournisseur": "local",
                },
            )

            for category_index, (result_type, prefix, legacy_prefix, age) in enumerate(
                CATEGORIES
            ):
                for index in range(12):
                    exam_year = current_year - index % 3
                    code = f"{prefix}{index + 1:08d}"
                    legacy_code = f"DEMO-{legacy_prefix}-{index + 1:03d}"
                    if result_type == Candidat.TypeResultat.PERM_PHILO:
                        series = tuple(PHILO_SERIES)[index % len(PHILO_SERIES)]
                        all_subjects = PHILO_SERIES[series]
                    elif result_type == Candidat.TypeResultat.NEUVIEME_AF:
                        series = ""
                        all_subjects = NINE_AF_SUBJECTS
                    else:
                        series = tuple(BAC_SERIES)[index % len(BAC_SERIES)]
                        all_subjects = BAC_SERIES[series]

                    permanent = result_type in {
                        Candidat.TypeResultat.PERM_NS4,
                        Candidat.TypeResultat.PERM_PHILO,
                    }
                    all_marks = []
                    displayed_marks = []
                    for subject_index, (subject, coefficient) in enumerate(
                        all_subjects
                    ):
                        percent = (
                            35 + (index + subject_index) % 12
                            if permanent and subject_index == 0
                            else 35
                            + (index * 17 + subject_index * 13 + category_index * 11)
                            % 63
                        )
                        note = round(coefficient * percent / 100)
                        all_marks.append((subject, note, coefficient))
                        if not permanent or note * 2 < coefficient:
                            displayed_marks.append((subject, note, coefficient))

                    points = sum(note for _, note, _ in all_marks)
                    total_sur = sum(coefficient for _, _, coefficient in all_marks)
                    admitted = points * 2 >= total_sur
                    mention = (
                        "Très bien"
                        if points >= 1500
                        else (
                            "Bien"
                            if points >= 1200
                            else "Passable" if admitted else "Échoué"
                        )
                    )
                    values = {
                        "type_resultat": result_type,
                        "nom": LAST_NAMES[index],
                        "prenom": FIRST_NAMES[
                            (index + category_index * 3) % len(FIRST_NAMES)
                        ],
                        "date_naissance": date(
                            exam_year - age, index % 12 + 1, index % 27 + 1
                        ),
                        "lieu_naissance": "Port-au-Prince",
                        "telephone": "",
                        "total_points": points,
                        "total_sur": total_sur,
                        "mention": mention,
                        "statut": (
                            Candidat.Statut.ADMIS
                            if admitted
                            else Candidat.Statut.ECHOUE
                        ),
                        "serie": series,
                        "ecole": SCHOOLS[index % len(SCHOOLS)],
                    }
                    candidat = Candidat.objects.filter(
                        annee=exam_year, code=code
                    ).first()
                    legacy_candidat = Candidat.objects.filter(
                        annee=exam_year, code=legacy_code
                    ).first()
                    if candidat is None and legacy_candidat is not None:
                        candidat = legacy_candidat
                        candidat.code = code
                        for field, value in values.items():
                            setattr(candidat, field, value)
                        candidat.save()
                        created = False
                    else:
                        candidat, created = Candidat.objects.update_or_create(
                            annee=exam_year,
                            code=code,
                            defaults=values,
                        )
                    created_count += int(created)
                    updated_count += int(not created)
                    for subject, note, coefficient in displayed_marks:
                        NoteMatiere.objects.update_or_create(
                            candidat=candidat,
                            matiere=subject,
                            defaults={"note": note, "coefficient": coefficient},
                        )
                    NoteMatiere.objects.filter(candidat=candidat).exclude(
                        matiere__in=[subject for subject, _, _ in displayed_marks]
                    ).delete()
                    seeded_candidates.append(
                        (result_type, exam_year, code, values["nom"], values["prenom"])
                    )

        self.stdout.write(
            self.style.SUCCESS(
                f"Seed terminé : {created_count} créé(s), {updated_count} actualisé(s)."
            )
        )
        for result_type, exam_year, code, last_name, first_name in seeded_candidates:
            label = Candidat.TypeResultat(result_type).label
            self.stdout.write(
                f"{label} | {exam_year} | {code} | {last_name} {first_name}"
            )
