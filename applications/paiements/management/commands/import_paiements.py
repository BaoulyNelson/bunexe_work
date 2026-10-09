import csv
from pathlib import Path

from django.core.management.base import BaseCommand, CommandError
from django.db import transaction

from applications.core.constants import DOCUMENT_CHOICES
from applications.paiements.models import ModePaiement, Tarif


def _read_rows(path, required_columns):
    if not path.is_file():
        raise CommandError(f"Fichier introuvable : {path}")
    with path.open(encoding="utf-8-sig", newline="") as source:
        reader = csv.DictReader(source)
        columns = {column.strip().lower() for column in reader.fieldnames or []}
        missing = required_columns - columns
        if missing:
            raise CommandError(
                f"Colonnes manquantes dans {path.name} : {', '.join(sorted(missing))}"
            )
        for row_number, row in enumerate(reader, start=2):
            yield row_number, {
                str(key).strip().lower(): (value or "").strip()
                for key, value in row.items()
                if key is not None
            }


def _boolean(value, field, path, row_number):
    normalized = value.lower()
    if normalized in {"1", "true", "vrai", "oui", "yes"}:
        return True
    if normalized in {"0", "false", "faux", "non", "no"}:
        return False
    raise CommandError(
        f"Valeur booléenne invalide pour {field} dans {path.name}, ligne {row_number} : {value}"
    )


class Command(BaseCommand):
    help = "Importe les modes de paiement et les tarifs depuis deux fichiers CSV."

    def add_arguments(self, parser):
        parser.add_argument("modes", type=Path)
        parser.add_argument("tarifs", type=Path)

    def handle(self, *args, **options):
        modes_path = options["modes"]
        tarifs_path = options["tarifs"]
        required_mode_columns = {"code", "libelle", "actif", "gratuit", "fournisseur"}
        required_tarif_columns = {"type_document", "prix", "devise", "actif"}
        created_modes = updated_modes = created_tarifs = updated_tarifs = 0

        try:
            with transaction.atomic():
                for row_number, row in _read_rows(modes_path, required_mode_columns):
                    defaults = {
                        "libelle": row["libelle"],
                        "actif": _boolean(
                            row["actif"], "actif", modes_path, row_number
                        ),
                        "gratuit": _boolean(
                            row["gratuit"], "gratuit", modes_path, row_number
                        ),
                        "fournisseur": row["fournisseur"],
                    }
                    if row.get("logo"):
                        defaults["logo"] = row["logo"]
                    _, created = ModePaiement.objects.update_or_create(
                        code=row["code"], defaults=defaults
                    )
                    created_modes += int(created)
                    updated_modes += int(not created)

                allowed_document_types = {value for value, _ in DOCUMENT_CHOICES}
                for row_number, row in _read_rows(tarifs_path, required_tarif_columns):
                    document_type = row["type_document"]
                    if document_type not in allowed_document_types:
                        raise CommandError(
                            f"Type de document invalide dans {tarifs_path.name}, ligne {row_number} : {document_type}"
                        )
                    defaults = {
                        "prix": row["prix"],
                        "devise": row["devise"],
                        "actif": _boolean(
                            row["actif"], "actif", tarifs_path, row_number
                        ),
                    }
                    _, created = Tarif.objects.update_or_create(
                        type_document=document_type, defaults=defaults
                    )
                    created_tarifs += int(created)
                    updated_tarifs += int(not created)
        except (ValueError, TypeError) as exc:
            raise CommandError(f"Import des paiements annulé : {exc}") from exc

        self.stdout.write(
            self.style.SUCCESS(
                "Import terminé : "
                f"{created_modes} mode(s) créé(s), {updated_modes} mis à jour; "
                f"{created_tarifs} tarif(s) créé(s), {updated_tarifs} mis à jour."
            )
        )
