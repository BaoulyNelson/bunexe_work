from pathlib import Path

from django.core.management.base import BaseCommand, CommandError
from django.core.management.color import no_style
from django.db import connection, transaction

from .csv_backup import (
    MODEL_ORDER,
    import_model_csv,
    import_relation_csv,
    model_filename,
    relation_fields,
    relation_filename,
)


class Command(BaseCommand):
    help = "Restaure ou met à jour les données métier à partir d'un export CSV complet."

    def add_arguments(self, parser):
        parser.add_argument("dossier", type=Path)

    def handle(self, *args, **options):
        directory = options["dossier"]
        if not directory.is_dir():
            raise CommandError(f"Dossier introuvable : {directory}")

        files = [directory / model_filename(model) for model in MODEL_ORDER]
        files.extend(
            directory / relation_filename(model, field)
            for model, field in relation_fields()
        )
        missing = [path.name for path in files if not path.is_file()]
        if missing:
            raise CommandError(
                f"Export CSV incomplet. Fichiers manquants : {', '.join(missing)}"
            )

        try:
            with transaction.atomic():
                for model in MODEL_ORDER:
                    import_model_csv(directory / model_filename(model), model)
                for model, field in relation_fields():
                    import_relation_csv(
                        directory / relation_filename(model, field), model, field
                    )
                reset_sql = connection.ops.sequence_reset_sql(
                    no_style(), list(MODEL_ORDER)
                )
                with connection.cursor() as cursor:
                    for statement in reset_sql:
                        cursor.execute(statement)
        except Exception as exc:
            raise CommandError(f"Restauration CSV annulée : {exc}") from exc

        self.stdout.write(
            self.style.SUCCESS(f"Restauration CSV terminée depuis {directory}.")
        )
