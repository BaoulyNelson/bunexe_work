import csv
from pathlib import Path

from django.core.management.base import BaseCommand, CommandError
from django.db import transaction

from applications.candidats.models import MatiereProgramme

REQUIRED_COLUMNS = {"examen", "serie", "matiere", "coefficient", "ordre"}


class Command(BaseCommand):
    help = "Importe le référentiel des matières à partir d'un fichier CSV."

    def add_arguments(self, parser):
        parser.add_argument("fichier", type=Path)

    def handle(self, *args, **options):
        path = options["fichier"]
        if not path.is_file():
            raise CommandError(f"Fichier introuvable : {path}")

        created = updated = 0
        with path.open(encoding="utf-8-sig", newline="") as source:
            reader = csv.DictReader(source)
            columns = {
                str(column).strip().lower()
                for column in reader.fieldnames or []
                if column is not None
            }
            missing = REQUIRED_COLUMNS - columns
            if missing:
                raise CommandError(
                    f"Colonnes manquantes : {', '.join(sorted(missing))}"
                )

            with transaction.atomic():
                for row_number, raw_row in enumerate(reader, start=2):
                    row = {
                        str(key).strip().lower(): (value or "").strip()
                        for key, value in raw_row.items()
                        if key is not None
                    }
                    try:
                        examen = row["examen"].upper()
                        serie = row["serie"].upper()
                        matiere = row["matiere"]
                        coefficient = int(row["coefficient"])
                        ordre = int(row["ordre"])
                        if not examen or not matiere or coefficient <= 0 or ordre <= 0:
                            raise ValueError(
                                "L'examen et la matière sont obligatoires; le coefficient et l'ordre doivent être positifs."
                            )
                    except (KeyError, TypeError, ValueError) as exc:
                        raise CommandError(
                            f"Ligne {row_number} invalide dans {path.name} : {exc}"
                        ) from exc

                    _, was_created = MatiereProgramme.objects.update_or_create(
                        examen=examen,
                        serie=serie,
                        matiere=matiere,
                        defaults={"coefficient": coefficient, "ordre": ordre},
                    )
                    created += int(was_created)
                    updated += int(not was_created)

        self.stdout.write(
            self.style.SUCCESS(
                f"Import terminé : {created} matière(s) créée(s), {updated} mise(s) à jour."
            )
        )
