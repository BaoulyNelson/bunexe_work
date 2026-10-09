from django.urls import path

from . import views

app_name = "verification"

urlpatterns = [
    path("", views.verify_code, name="verify"),
    path("<str:code>/", views.verify_code, name="verify_code"),
]
