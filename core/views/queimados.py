from asgiref.sync import async_to_sync
from channels.layers import get_channel_layer
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib import messages
from django.db import transaction
from django.utils import timezone
from django.http import JsonResponse
import json

from django.db import models
from core.models import (
    Category,
    Product,
    TransferOrder,
    TransferOrderItem,
    OrderStatus,
    Branch,
    OrderLog,
)

from core.permissions import require_queimados


# ==========================================================
# CART HELPER
# ==========================================================
def _get_or_create_cart(user):
    carts = TransferOrder.objects.filter(
        created_by=user,
        status=OrderStatus.DRAFT
    ).order_by("id")

    if carts.exists():
        cart = carts.first()
        carts.exclude(id=cart.id).delete()
    else:
        cart = TransferOrder.objects.create(
            created_by=user,
            status=OrderStatus.DRAFT,
            from_branch=Branch.QUEIMADOS,
            to_branch=Branch.AUSTIN,
        )

    return cart


# ==========================================================
# PRODUCTS
# ==========================================================
@require_queimados
def q_products(request):
    cart = _get_or_create_cart(request.user)

    categories = Category.objects.filter(active=True).prefetch_related(
        models.Prefetch(
            "products",
            queryset=Product.objects.filter(active=True).only("id", "name")[:200]
        )
    )
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

        return redirect("q_products")

    return render(request, "queimados/products.html", {
        "cart": cart,
        "categories": categories,
    })


# ==========================================================
# CART
# ==========================================================
@require_queimados
def q_cart(request):
    cart = _get_or_create_cart(request.user)
    items = cart.items.select_related("product").order_by("id")

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

    return render(request, "queimados/cart.html", {
        "cart": cart,
        "items": items,
    })


# ==========================================================
# SUBMIT ORDER
# ==========================================================
@require_queimados
@transaction.atomic
def q_submit_order(request):
    if request.method != "POST":
        return redirect("q_cart")

    cart = _get_or_create_cart(request.user)

    if cart.items.count() == 0:
        messages.error(request, "Carrinho vazio.")
        return redirect("q_cart")

    cart.status = OrderStatus.SUBMITTED
    cart.submitted_at = timezone.now()
    cart.save()

    try:
        channel_layer = get_channel_layer()
        if channel_layer:
            async_to_sync(channel_layer.group_send)(
                "orders_group",
                {
                    "type": "order_update",
                    "order_id": cart.id,
                    "status": cart.status,
                    "status_display": cart.get_status_display(),
                }
            )
    except Exception:
        pass

    OrderLog.objects.create(
        order=cart,
        user=request.user,
        action="Enviou o pedido para Austin",
    )

    messages.success(request, f"Pedido #{cart.id} enviado com sucesso!")
    return redirect("q_cart")


# ==========================================================
# LISTA DE PEDIDOS
# ==========================================================
@require_queimados
def q_orders(request):
    orders = TransferOrder.objects.filter(
        created_by=request.user
    ).exclude(
        status=OrderStatus.DRAFT
    ).order_by("-created_at")

    return render(request, "queimados/orders.html", {
        "orders": orders,
    })


# ==========================================================
# REMOVE ITEM
# ==========================================================
@require_queimados
def q_remove_item(request, item_id):
    item = get_object_or_404(
        TransferOrderItem,
        id=item_id,
        order__created_by=request.user,
        order__status=OrderStatus.DRAFT,
    )

    item.delete()
    messages.success(request, "Produto removido do carrinho.")
    return redirect("q_cart")


# ==========================================================
# DETAIL
# ==========================================================
@require_queimados
def q_order_detail(request, order_id):
    order = get_object_or_404(
        TransferOrder,
        id=order_id,
        created_by=request.user  # 🔥 SEGURANÇA
    )

    items = order.items.select_related("product")

    # 🔥 SOMENTE AJUSTE DE SEGURANÇA

    for item in items:
        item.faltando = max(0, (item.qty_requested or 0) - (item.qty_sent or 0))

    return render(request, "queimados/order_detail.html", {
        "order": order,
        "items": items
    })


# ==========================================================
# RECEIVE ORDER
# ==========================================================
@require_queimados
def q_receive_order(request, order_id):
    order = get_object_or_404(
        TransferOrder,
        id=order_id,
        created_by=request.user  # 🔥 SEGURANÇA
    )

    if order.status != OrderStatus.DISPATCHED:
        messages.error(request, "Pedido ainda não foi despachado.")
        return redirect("q_order_detail", order_id=order.id)

    order.status = OrderStatus.RECEIVED
    order.received_at = timezone.now()
    order.save(update_fields=["status", "received_at"])

    OrderLog.objects.create(
        order=order,
        user=request.user,
        action="Confirmou recebimento"
    )

    messages.success(request, "Recebimento confirmado.")
    return redirect("q_order_detail", order_id=order.id)


# ==========================================================
# API ADD PRODUCT
# ==========================================================
@require_queimados
def q_add_product(request):
    if request.method != "POST":
        return JsonResponse({"success": False, "error": "Método inválido"})

    try:
        data = json.loads(request.body)
        product_id = int(data.get("product_id"))
        qty = int(data.get("qty", 1))

        if qty <= 0:
            return JsonResponse({"success": False, "error": "Quantidade inválida"})

        product = get_object_or_404(Product, id=product_id, active=True)
        cart = _get_or_create_cart(request.user)

        item, created = TransferOrderItem.objects.get_or_create(
            order=cart,
            product=product,
            defaults={"qty_requested": qty},
        )

        if not created:
            item.qty_requested += qty
            item.save()

        return JsonResponse({
            "success": True,
            "cart_total_items": cart.items.count()
        })

    except Exception as e:
        return JsonResponse({"success": False, "error": str(e)})


# ==========================================================
# API UPDATE ITEM
# ==========================================================
@require_queimados
def q_update_item(request):
    if request.method != "POST":
        return JsonResponse({"success": False, "error": "Método inválido"})

    try:
        data = json.loads(request.body)
        item_id = int(data.get("item_id"))
        qty = int(data.get("qty"))

        item = get_object_or_404(
            TransferOrderItem,
            id=item_id,
            order__created_by=request.user,
            order__status=OrderStatus.DRAFT
        )

        if qty <= 0:
            item.delete()
            return JsonResponse({"success": True, "deleted": True})

        item.qty_requested = qty
        item.save()

        return JsonResponse({"success": True})

    except Exception as e:
        return JsonResponse({"success": False, "error": str(e)})


# ==========================================================
# API REMOVE ITEM
# ==========================================================
@require_queimados
def q_remove_item_api(request):
    if request.method != "POST":
        return JsonResponse({"success": False, "error": "Método inválido"})

    try:
        data = json.loads(request.body)
        item_id = int(data.get("item_id"))

        item = get_object_or_404(
            TransferOrderItem,
            id=item_id,
            order__created_by=request.user,
            order__status=OrderStatus.DRAFT
        )

        item.delete()
        return JsonResponse({"success": True})

    except Exception as e:
        return JsonResponse({"success": False, "error": str(e)})