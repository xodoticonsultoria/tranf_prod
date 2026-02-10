from django.contrib import admin
from django.urls import path, include
from django.contrib.auth import views as auth_views
from core.views import home

urlpatterns = [
    path("admin/", admin.site.urls),

    path(
        "login/",
        auth_views.LoginView.as_view(
            template_name="auth/login.html",
            redirect_authenticated_user=True,
        ),
        name="login",
    ),
    path("logout/", auth_views.LogoutView.as_view(), name="logout"),

    # 👇 HOME
    path("", home, name="home"),

    # 👇 ESSA LINHA FALTAVA — CRÍTICA
    path("", include("core.urls")),
]
