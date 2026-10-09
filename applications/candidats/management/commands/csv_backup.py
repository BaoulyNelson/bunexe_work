import csv

from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group, Permission
from django.contrib.contenttypes.models import ContentType

from applications.candidats.models import Candidat, MatiereProgramme, NoteMatiere
from applications.documents.models import DemandeDocument, DocumentEmis
from applications.paiements.models import ModePaiement, Tarif
from applications.verification.models import AuditEvenement

MODEL_ORDER = (
    Group,
    get_user_model(),
    Tarif,
    ModePaiement,
    MatiereProgramme,
    Candidat,
    NoteMatiere,
    DemandeDocument,
    DocumentEmis,
    AuditEvenement,
)


def model_filename(model):
    return f"{model._meta.label_lower.replace('.', '_')}.csv"


def model_fields(model):
    return model._meta.concrete_fields


def relation_fields():
    relations = []
    for model in (get_user_model(), Group):
        for field in model._meta.many_to_many:
            relations.append((model, field))
    return relations


def relation_filename(model, field):
    return f"{model._meta.label_lower.replace('.', '_')}__{field.name}.csv"


def relation_target_columns(field):
    if field.remote_field.model is Permission:
        return ("app_label", "model", "codename")
    return ("target_id",)


def write_model_csv(directory, model):
    fields = model_fields(model)
    path = directory / model_filename(model)
    with path.open("w", encoding="utf-8-sig", newline="") as output:
        writer = csv.writer(output)
        writer.writerow(field.attname for field in fields)
        for obj in model.objects.all().iterator():
            writer.writerow(
                [
                    (
                        ""
                        if getattr(obj, field.attname) is None
                        else getattr(obj, field.attname)
                    )
                    for field in fields
                ]
            )


def write_relation_csv(directory, model, field):
    target_columns = relation_target_columns(field)
    path = directory / relation_filename(model, field)
    with path.open("w", encoding="utf-8-sig", newline="") as output:
        writer = csv.writer(output)
        writer.writerow(("source_id", *target_columns))
        for source in model.objects.all().iterator():
            targets = list(getattr(source, field.name).all())
            if not targets:
                writer.writerow((source.pk, *([""] * len(target_columns))))
                continue
            for target in targets:
                if isinstance(target, Permission):
                    writer.writerow(
                        (
                            source.pk,
                            target.content_type.app_label,
                            target.content_type.model,
                            target.codename,
                        )
                    )
                else:
                    writer.writerow((source.pk, target.pk))


def read_csv(path):
    source = path.open(encoding="utf-8-sig", newline="")
    reader = csv.DictReader(source)
    return source, reader


def field_value(field, value):
    if value == "" and field.null:
        return None
    target_field = field.target_field if field.is_relation else field
    return target_field.to_python(value)


def import_model_csv(path, model):
    expected_columns = [field.attname for field in model_fields(model)]
    source, reader = read_csv(path)
    with source:
        if reader.fieldnames != expected_columns:
            raise ValueError(
                f"Colonnes invalides dans {path.name}; attendu : {', '.join(expected_columns)}"
            )
        imported = 0
        for row_number, row in enumerate(reader, start=2):
            try:
                values = {
                    field.attname: field_value(field, row[field.attname])
                    for field in model_fields(model)
                }
                primary_key = values[model._meta.pk.attname]
                queryset = model.objects.filter(pk=primary_key)
                if model is Candidat:
                    obj = queryset.first() or model()
                    for key, value in values.items():
                        setattr(obj, key, value)
                    obj.save()
                elif queryset.exists():
                    queryset.update(
                        **{
                            key: value
                            for key, value in values.items()
                            if key != model._meta.pk.attname
                        }
                    )
                else:
                    model(**values).save_base(raw=True, force_insert=True)
            except Exception as exc:
                raise ValueError(f"{path.name}, ligne {row_number} : {exc}") from exc
            imported += 1
    return imported


def import_relation_csv(path, model, field):
    target_columns = relation_target_columns(field)
    expected_columns = ("source_id", *target_columns)
    source, reader = read_csv(path)
    with source:
        if reader.fieldnames != list(expected_columns):
            raise ValueError(
                f"Colonnes invalides dans {path.name}; attendu : {', '.join(expected_columns)}"
            )
        targets_by_source = {}
        for row_number, row in enumerate(reader, start=2):
            source_id = field_value(model._meta.pk, row["source_id"])
            targets_by_source.setdefault(source_id, [])
            if not any(row[column] for column in target_columns):
                continue
            try:
                if field.remote_field.model is Permission:
                    content_type = ContentType.objects.get(
                        app_label=row["app_label"], model=row["model"]
                    )
                    target = Permission.objects.get(
                        content_type=content_type, codename=row["codename"]
                    )
                else:
                    target_id = field_value(
                        field.remote_field.model._meta.pk, row["target_id"]
                    )
                    target = field.remote_field.model.objects.get(pk=target_id)
            except Exception as exc:
                raise ValueError(f"{path.name}, ligne {row_number} : {exc}") from exc
            targets_by_source[source_id].append(target)

    for source_id, targets in targets_by_source.items():
        source = model.objects.get(pk=source_id)
        getattr(source, field.name).set(targets)
    return len(targets_by_source)
