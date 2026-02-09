from django.contrib import admin
from django.urls import path, include
from core import views as core_views

urlpatterns = [
    path("admin/", admin.site.urls),

    path("login/", core_views.login_view, name="login"),
    path("logout/", core_views.logout_view, name="logout"),
    path("", core_views.home, name="home"),

    path("", include("core.urls")),
]
