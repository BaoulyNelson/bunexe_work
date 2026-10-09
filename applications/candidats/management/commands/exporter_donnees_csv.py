from pathlib import Path

from django.core.management.base import BaseCommand, CommandError

from .csv_backup import MODEL_ORDER, model_filename, relation_fields
from .csv_backup import relation_filename, write_model_csv, write_relation_csv


class Command(BaseCommand):
    help = "Exporte les données métier, comptes et relations dans des fichiers CSV."

    def add_arguments(self, parser):
        parser.add_argument("dossier", type=Path)

    def handle(self, *args, **options):
        directory = options["dossier"]
        try:
            directory.mkdir(parents=True, exist_ok=True)
            for model in MODEL_ORDER:
                write_model_csv(directory, model)
            for model, field in relation_fields():
                write_relation_csv(directory, model, field)
        except OSError as exc:
            raise CommandError(f"Impossible d'écrire les fichiers CSV : {exc}") from exc

        files = [model_filename(model) for model in MODEL_ORDER]
        files.extend(
            relation_filename(model, field) for model, field in relation_fields()
        )
        self.stdout.write(
            self.style.SUCCESS(
                f"Export terminé : {len(files)} fichiers CSV dans {directory}."
            )
        )
