from django.urls import path

from . import views

app_name = "documents"

urlpatterns = [
    path(
        "documents/<uuid:transaction_id>/<str:document_type>/",
        views.download_document,
        name="download",
    ),
]
