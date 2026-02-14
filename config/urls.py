from django.contrib import admin
from django.urls import path, include
from django.contrib.auth import views as auth_views
from django.conf import settings
from django.conf.urls.static import static

from django.views.generic import RedirectView

from core.views import home, logout_view


urlpatterns = [
    path("admin/", admin.site.urls),

    # LOGIN (usa template custom)
    path(
        "login/",
        auth_views.LoginView.as_view(
            template_name="auth/login.html",
            redirect_authenticated_user=True,
        ),
        name="login",
    ),

    path("logout/", logout_view, name="logout"),

    # HOME
    path("", home, name="home"),

    # APPS
    path("", include("core.urls")),

    # ✅ favicon SEM manifest lookup (não quebra static)
    path(
        "favicon.ico",
        RedirectView.as_view(url="/static/favicon.ico"),
    ),
]

# MEDIA
urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
