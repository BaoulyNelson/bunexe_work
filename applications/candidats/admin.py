from django.contrib import admin
from django.db.models import Sum

from .models import Candidat, MatiereProgramme, NoteMatiere


class NoteMatiereInline(admin.TabularInline):
    model = NoteMatiere
    extra = 1
    fields = ("matiere", "note", "coefficient")


@admin.register(MatiereProgramme)
class MatiereProgrammeAdmin(admin.ModelAdmin):
    list_display = ("examen", "serie", "ordre", "matiere", "coefficient")
    list_filter = ("examen", "serie")
    search_fields = ("matiere", "serie")
    ordering = ("examen", "serie", "ordre", "matiere")


@admin.register(Candidat)
class CandidatAdmin(admin.ModelAdmin):
    inlines = (NoteMatiereInline,)
    readonly_fields = ("statut",)
    list_display = (
        "type_resultat",
        "annee",
        "code",
        "nom",
        "prenom",
        "total_points",
        "statut",
        "ecole",
    )
    list_filter = ("type_resultat", "annee", "statut", "serie")
    search_fields = ("code", "nom", "prenom", "ecole")
    ordering = ("-annee", "nom", "prenom")

    def save_formset(self, request, form, formset, change):
        super().save_formset(request, form, formset, change)
        if formset.model is not NoteMatiere:
            return

        candidat = form.instance
        totals = candidat.notes_matieres.aggregate(
            points=Sum("note"), coefficients=Sum("coefficient")
        )
        if totals["coefficients"] == candidat.total_sur:
            candidat.total_points = totals["points"] or 0
            candidat.save(update_fields=["total_points"])
