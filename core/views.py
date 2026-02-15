from django.contrib import messages
from django.contrib.auth import authenticate, login, logout
from django.contrib.auth.decorators import login_required
from django.db import transaction
from django.shortcuts import render, redirect, get_object_or_404
from django.utils import timezone

from .models import Category, Product, TransferOrder, TransferOrderItem, OrderStatus, Branch
from .permissions import require_austin, require_queimados

from django.http import JsonResponse
from django.views.decorators.http import require_GET




# --------------------
# Helpers
# --------------------
def _has_group(user, name: str) -> bool:
    return user.is_authenticated and user.groups.filter(name=name).exists()


# --------------------
# Auth
# --------------------
def login_view(request):
    if request.user.is_authenticated:
        return redirect("home")

    if request.method == "POST":
        username = request.POST.get("username", "").strip()
        password = request.POST.get("password", "").strip()

        user = authenticate(request, username=username, password=password)
        if user is None:
            messages.error(request, "Usuário ou senha inválidos.")
            return redirect("login")

        login(request, user)
        return redirect("home")

    return render(request, "auth/login.html")


def logout_view(request):
    logout(request)
    return redirect("login")


# --------------------
# Home
# --------------------
@login_required
def home(request):
    user = request.user

    if _has_group(user, "QUEIMADOS"):
        return redirect("q_products")

    if _has_group(user, "AUSTIN"):
        return redirect("a_orders")

    messages.error(request, "Usuário sem grupo (AUSTIN/QUEIMADOS).")
    return redirect("/admin/")


# --------------------
# Queimados
# --------------------
def _get_or_create_cart(user):
    cart, _ = TransferOrder.objects.get_or_create(
        created_by=user,
        status=OrderStatus.DRAFT,
        defaults={"from_branch": Branch.QUEIMADOS, "to_branch": Branch.AUSTIN},
    )
    return cart


@require_queimados
def q_products(request):
    cart = _get_or_create_cart(request.user)

    categories = (
        Category.objects.filter(active=True)
        .prefetch_related("products")
        .order_by("name")
    )

    uncategorized = Product.objects.filter(
        active=True,
        category__isnull=True
    ).order_by("name")

    if request.method == "POST":
        product_id = int(request.POST["product_id"])
        qty = int(request.POST["qty"])

        if qty <= 0:
            messages.error(request, "Quantidade inválida.")
            return redirect("q_products")

        product = get_object_or_404(Product, id=product_id, active=True)

        item, created = TransferOrderItem.objects.get_or_create(
            order=cart,
            product=product,
            defaults={"qty_requested": qty},
        )

        if not created:
            item.qty_requested += qty
            item.save()

        if created:
            request.session["animate_cart"] = True

        return redirect("q_products")

    animate = request.session.pop("animate_cart", False)

    return render(
        request,
        "queimados/products.html",
        {
            "cart": cart,
            "categories": categories,
            "uncategorized": uncategorized,
            "animate_cart": animate,
        },
    )


@require_queimados
def q_cart(request):
    cart = _get_or_create_cart(request.user)
    items = cart.items.select_related("product").order_by("product__name")

    if request.method == "POST":
        for item in items:
            field = f"qty_{item.id}"
            if field in request.POST:
                new_qty = int(request.POST[field])
                if new_qty <= 0:
                    item.delete()
                else:
                    item.qty_requested = new_qty
                    item.save()

        messages.success(request, "Carrinho atualizado.")
        return redirect("q_cart")

    return render(request, "queimados/cart.html", {"cart": cart, "items": items})


@require_queimados
@transaction.atomic
def q_submit_order(request):
    cart = _get_or_create_cart(request.user)

    if cart.items.count() == 0:
        messages.error(request, "Carrinho vazio.")
        return redirect("q_cart")

    cart.status = OrderStatus.SUBMITTED
    cart.save()

    messages.success(request, f"Pedido #{cart.id} enviado com sucesso!")

    return redirect("q_cart")


@require_queimados
def q_orders(request):
    orders = (
        TransferOrder.objects
        .filter(created_by=request.user)
        .exclude(status=OrderStatus.DRAFT)
        .order_by("-created_at")
    )
    return render(request, "queimados/orders.html", {"orders": orders})


@require_queimados
def q_order_detail(request, order_id):
    order = get_object_or_404(TransferOrder, id=order_id, created_by=request.user)
    items = order.items.select_related("product").order_by("product__name")
    return render(request, "queimados/order_detail.html", {"order": order, "items": items})


@require_queimados
def q_receive_order(request, order_id):
    order = get_object_or_404(TransferOrder, id=order_id, created_by=request.user)

    if order.status != OrderStatus.DISPATCHED:
        messages.error(request, "Só dá pra confirmar recebimento quando Austin despacha.")
        return redirect("q_order_detail", order_id=order.id)

    order.status = OrderStatus.RECEIVED
    order.received_at = timezone.now()
    order.save()

    messages.success(request, f"Pedido #{order.id} confirmado como recebido.")
    return redirect("q_order_detail", order_id=order.id)


# --------------------
# Austin
# --------------------
@require_austin
def a_orders(request):
    orders = TransferOrder.objects.exclude(status=OrderStatus.DRAFT).order_by("-created_at")
    return render(request, "austin/orders.html", {"orders": orders})


@require_austin
def a_order_detail(request, order_id):
    order = get_object_or_404(TransferOrder, id=order_id)
    items = order.items.select_related("product").order_by("product__name")

    if request.method == "POST":
        if order.status != OrderStatus.PICKING:
            messages.error(request, "Você só pode alterar quantidades quando o pedido está em separação.")
            return redirect("a_order_detail", order_id=order.id)

        for item in items:
            field = f"sent_{item.id}"
            if field in request.POST:
                val = int(request.POST[field])
                item.qty_sent = max(0, val)
                item.save()

        order.notes_from_austin = request.POST.get("notes_from_austin", "")
        order.save()

        messages.success(request, "Quantidades atualizadas.")
        return redirect("a_order_detail", order_id=order.id)

    return render(request, "austin/order_detail.html", {"order": order, "items": items})


@require_austin
def a_start_picking(request, order_id):
    order = get_object_or_404(TransferOrder, id=order_id)

    if order.status != OrderStatus.SUBMITTED:
        messages.error(request, "Só dá pra iniciar separação quando o pedido está enviado.")
        return redirect("a_order_detail", order_id=order.id)

    order.status = OrderStatus.PICKING
    order.picking_by = request.user
    order.picking_at = timezone.now()
    order.save()

    messages.success(request, f"Pedido #{order.id} em separação.")
    return redirect("a_order_detail", order_id=order.id)


@require_austin
def a_item_ok(request, order_id, item_id):
    order = get_object_or_404(TransferOrder, id=order_id)
    item = get_object_or_404(TransferOrderItem, id=item_id, order=order)

    if order.status != OrderStatus.PICKING:
        messages.error(request, "Só dá pra marcar OK durante a separação.")
        return redirect("a_order_detail", order_id=order.id)

    item.qty_sent = item.qty_requested
    item.save()

    messages.success(request, f"OK: {item.product.name}")
    return redirect("a_order_detail", order_id=order.id)


@require_austin
def a_dispatch(request, order_id):
    order = get_object_or_404(TransferOrder, id=order_id)

    if order.status != OrderStatus.PICKING:
        messages.error(request, "Só dá pra despachar quando está em separação.")
        return redirect("a_order_detail", order_id=order.id)

    order.status = OrderStatus.DISPATCHED
    order.dispatched_at = timezone.now()
    order.save()

    messages.success(request, f"Pedido #{order.id} despachado para Queimados.")
    return redirect("a_order_detail", order_id=order.id)


@login_required
def queimados_categories(request):
    categories = Category.objects.filter(active=True).prefetch_related("products")

    return render(
        request,
        "queimados/categories.html",
        {"categories": categories},
    )

@require_austin
@require_GET
def austin_badge(request):
    # "Novos" = pedidos SUBMITTED (aguardando iniciar separação)
    count = TransferOrder.objects.filter(status=OrderStatus.SUBMITTED).count()
    return JsonResponse({"count": count})


@require_austin
@require_GET
def austin_poll(request):
    """
    Retorna:
      - count: total de SUBMITTED
      - newest_id: maior id entre SUBMITTED (pra detectar novidade)
    O front guarda o last_id e toca som/mostra toast quando aumenta.
    """
    qs = TransferOrder.objects.filter(status=OrderStatus.SUBMITTED)
    count = qs.count()
    newest = qs.order_by("-id").first()
    newest_id = newest.id if newest else 0
    return JsonResponse({"count": count, "newest_id": newest_id})
