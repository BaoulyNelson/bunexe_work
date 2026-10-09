from django.contrib import admin

from .models import AuditEvenement


@admin.register(AuditEvenement)
class AuditEvenementAdmin(admin.ModelAdmin):
    list_display = ("type_evenement", "document", "code_saisi", "ip", "cree_le")
    list_filter = ("type_evenement", "cree_le")
    search_fields = ("code_saisi", "document__code_verification", "ip")
    readonly_fields = (
        "type_evenement",
        "document",
        "code_saisi",
        "ip",
        "user_agent",
        "cree_le",
    )
