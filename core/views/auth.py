from django.shortcuts import render, redirect
from django.contrib import messages
from django.contrib.auth import authenticate, login, logout
from django.contrib.auth.decorators import login_required

def _has_group(user, name: str) -> bool:
    return user.is_authenticated and user.groups.filter(name=name).exists()


def login_view(request):
    if request.user.is_authenticated:
        return redirect("home")

    if request.method == "POST":
        user = authenticate(
            request,
            username=request.POST.get("username", "").strip(),
            password=request.POST.get("password", "").strip(),
        )

        if user is None:
            messages.error(request, "Usuário ou senha inválidos.")
            return redirect("login")

        login(request, user)
        return redirect("home")

    return render(request, "auth/login.html")


def logout_view(request):
    logout(request)
    return redirect("login")


@login_required
def home(request):
    if _has_group(request.user, "QUEIMADOS"):
        return redirect("q_products")

    if _has_group(request.user, "AUSTIN"):
        return redirect("a_orders")

    messages.error(request, "Usuário sem grupo.")
    return redirect("/admin/")
