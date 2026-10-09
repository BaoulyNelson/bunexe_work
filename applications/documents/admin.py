from django.contrib import admin
from django.utils import timezone

from .models import DocumentEmis


@admin.register(DocumentEmis)
class DocumentEmisAdmin(admin.ModelAdmin):
    list_display = (
        "code_verification",
        "type_document",
        "demande",
        "date_emission",
        "nb_impressions",
        "annule",
    )
    list_filter = ("type_document", "annule", "date_emission")
    search_fields = ("code_verification", "demande__candidat__code")
    readonly_fields = (
        "code_verification",
        "date_emission",
        "nb_impressions",
        "annule_le",
    )
    actions = ("annuler_documents", "preparer_regeneration")

    @admin.action(description="Annuler les documents sélectionnés")
    def annuler_documents(self, request, queryset):
        queryset.filter(annule=False).update(annule=True, annule_le=timezone.now())

    @admin.action(description="Régénérer le PDF à la prochaine impression")
    def preparer_regeneration(self, request, queryset):
        for document in queryset:
            if document.annule:
                continue
            if document.fichier_pdf:
                document.fichier_pdf.delete(save=False)
            document.fichier_pdf = ""
            document.save(update_fields=["fichier_pdf"])
