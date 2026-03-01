from asgiref.sync import async_to_sync
from channels.layers import get_channel_layer
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib import messages
from django.db import transaction
from django.utils import timezone

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
    cart, _ = TransferOrder.objects.get_or_create(
        created_by=user,
        status=OrderStatus.DRAFT,
        defaults={
            "from_branch": Branch.QUEIMADOS,
            "to_branch": Branch.AUSTIN,
        },
    )
    return cart


# ==========================================================
# PRODUCTS
# ==========================================================

@require_queimados
def q_products(request):
    cart = _get_or_create_cart(request.user)
    categories = Category.objects.filter(active=True).prefetch_related("products")

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
    items = cart.items.select_related("product")

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
# SUBMIT ORDER (COM WEBSOCKET SEGURO)
# ==========================================================

@require_queimados
@transaction.atomic
def q_submit_order(request):
    cart = _get_or_create_cart(request.user)

    if cart.items.count() == 0:
        messages.error(request, "Carrinho vazio.")
        return redirect("q_cart")

    cart.status = OrderStatus.SUBMITTED
    cart.submitted_at = timezone.now()
    cart.save()

    # 🔥 WebSocket protegido (não derruba sistema se Redis cair)
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
        # Se Redis estiver offline, o sistema continua funcionando
        pass

    OrderLog.objects.create(
        order=cart,
        user=request.user,
        action="Enviou o pedido para Austin",
    )

    messages.success(request, f"Pedido #{cart.id} enviado com sucesso!")
    return redirect("q_cart")


# ==========================================================
# LISTA DE PEDIDOS DO DIA
# ==========================================================

@require_queimados
def q_orders(request):
    today = timezone.localdate()

    orders = (
        TransferOrder.objects
        .filter(created_by=request.user, created_at__date=today)
        .exclude(status__in=[OrderStatus.DRAFT, OrderStatus.RECEIVED])
        .order_by("-created_at")
    )

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
        created_by=request.user,
    )

    items = order.items.select_related("product")

    return render(request, "queimados/order_detail.html", {
        "order": order,
        "items": items,
    })


# ==========================================================
# RECEIVE ORDER (COM WEBSOCKET SEGURO)
# ==========================================================

@require_queimados
def q_receive_order(request, order_id):
    order = get_object_or_404(
        TransferOrder,
        id=order_id,
    )
    print("STATUS REAL NO B:", order.status)

    if order.status != OrderStatus.DISPATCHED:
        messages.error(request, "Só pode confirmar quando Austin despachar.")
        return redirect("q_order_detail", order_id=order.id)

    order.status = OrderStatus.RECEIVED
    order.received_at = timezone.now()
    order.save()

    # 🔥 WebSocket protegido
    try:
        channel_layer = get_channel_layer()
        if channel_layer:
            async_to_sync(channel_layer.group_send)(
                "orders_group",
                {
                    "type": "order_update",
                    "order_id": order.id,
                    "status": order.status,
                    "status_display": order.get_status_display(),
                }
            )
    except Exception:
        pass

    OrderLog.objects.create(
        order=order,
        user=request.user,
        action="Confirmou recebimento do pedido",
    )

    messages.success(request, f"Pedido #{order.id} confirmado.")
    return redirect("q_order_detail", order_id=order.id)


# ==========================================================
# CATEGORIES
# ==========================================================

@require_queimados
def queimados_categories(request):
    categories = Category.objects.filter(active=True).prefetch_related("products")

    return render(
        request,
        "queimados/categories.html",
        {"categories": categories},
    )