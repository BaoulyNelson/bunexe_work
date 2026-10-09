from django.contrib import admin
from django.conf.urls.i18n import set_language
from django.urls import include, path

urlpatterns = [
    path("admin/", admin.site.urls),
    path("i18n/setlang/", set_language, name="set_language"),
    path("", include("applications.core.urls")),
    path("", include("applications.documents.urls")),
    path("verification/", include("applications.verification.urls")),
]
