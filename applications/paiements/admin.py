from django.contrib import admin

from applications.documents.models import DemandeDocument

from .models import ModePaiement, Tarif


@admin.register(Tarif)
class TarifAdmin(admin.ModelAdmin):
    list_display = ("type_document", "prix", "devise", "actif")
    list_filter = ("actif", "devise")


@admin.register(ModePaiement)
class ModePaiementAdmin(admin.ModelAdmin):
    list_display = ("libelle", "code", "gratuit", "fournisseur", "actif")
    list_filter = ("actif", "gratuit", "fournisseur")


@admin.register(DemandeDocument)
class DemandeDocumentAdmin(admin.ModelAdmin):
    list_display = (
        "transaction_id",
        "candidat",
        "type_document",
        "montant",
        "statut",
        "created_at",
    )
    list_filter = ("statut", "type_document", "candidat__annee", "mode_paiement")
    search_fields = ("transaction_id", "candidat__code", "candidat__nom")
    readonly_fields = ("transaction_id", "created_at", "ip", "user_agent")
    actions = ("export_csv", "annuler_demandes")

    @admin.action(description="Exporter la sélection en CSV")
    def export_csv(self, request, queryset):
        import csv

        from django.http import HttpResponse

        response = HttpResponse(content_type="text/csv; charset=utf-8")
        response["Content-Disposition"] = 'attachment; filename="demandes.csv"'
        writer = csv.writer(response)
        writer.writerow(
            [
                "Transaction",
                "Année",
                "Code",
                "Candidat",
                "Document",
                "Montant",
                "Statut",
            ]
        )
        for demande in queryset.select_related("candidat"):
            writer.writerow(
                [
                    demande.transaction_id,
                    demande.candidat.annee,
                    demande.candidat.code,
                    f"{demande.candidat.nom} {demande.candidat.prenom}",
                    demande.get_type_document_display(),
                    demande.montant,
                    demande.get_statut_display(),
                ]
            )
        return response

    @admin.action(description="Annuler les demandes sélectionnées")
    def annuler_demandes(self, request, queryset):
        queryset.filter(statut=DemandeDocument.Statut.EN_COURS).update(
            statut=DemandeDocument.Statut.ANNULEE
        )
