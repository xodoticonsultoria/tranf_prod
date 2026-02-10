from django.contrib import admin
from django.urls import path, include
from django.contrib.auth import views as auth_views
from django.conf import settings
from django.conf.urls.static import static

from django.views.generic import RedirectView
from django.templatetags.static import static as static_file

from core.views import home, logout_view


urlpatterns = [
    path("admin/", admin.site.urls),

    # auth
    path(
        "login/",
        auth_views.LoginView.as_view(
            template_name="auth/login.html",
            redirect_authenticated_user=True,
        ),
        name="login",
    ),

    path("logout/", logout_view, name="logout"),

    # home
    path("", home, name="home"),

    # apps
    path("", include("core.urls")),

    # favicon (corrige erro 404 e quirks mode aviso)
    path(
        "favicon.ico",
        RedirectView.as_view(url=static_file("favicon.ico")),
        name="favicon",
    ),
]

# media (uploads)
urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
