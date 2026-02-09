from django.shortcuts import render, redirect, get_object_or_404
from django.utils import timezone
from django.db import transaction
from django.contrib import messages

from .models import Product, TransferOrder, TransferOrderItem, OrderStatus, Branch
from .permissions import require_austin, require_queimados


# -------- QUEIMADOS --------

def _get_or_create_cart(user):
    cart, _ = TransferOrder.objects.get_or_create(
        created_by=user,
        status=OrderStatus.DRAFT,
        defaults={"from_branch": Branch.QUEIMADOS, "to_branch": Branch.AUSTIN},
    )
    return cart

@require_queimados
def q_products(request):
    products = Product.objects.filter(active=True).order_by("name")
    cart = _get_or_create_cart(request.user)

    if request.method == "POST":
        product_id = int(request.POST["product_id"])
        qty = int(request.POST["qty"])
        if qty <= 0:
            messages.error(request, "Quantidade inválida.")
            return redirect("q_products")

        product = get_object_or_404(Product, id=product_id)
        item, created = TransferOrderItem.objects.get_or_create(
            order=cart, product=product,
            defaults={"qty_requested": qty}
        )
        if not created:
            item.qty_requested += qty
            item.save()

        messages.success(request, f"Adicionado ao carrinho: {product.name} (+{qty})")
        return redirect("q_products")

    return render(request, "queimados/products.html", {"products": products, "cart": cart})

@require_queimados
def q_cart(request):
    cart = _get_or_create_cart(request.user)
    items = cart.items.select_related("product").order_by("product__name")

    if request.method == "POST":
        # atualizar quantidades no carrinho
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
        messages.error(request, "Seu carrinho está vazio.")
        return redirect("q_cart")

    cart.status = OrderStatus.SUBMITTED
    cart.save()
    messages.success(request, f"Pedido #{cart.id} enviado para Austin.")
    return redirect("q_orders")

@require_queimados
def q_orders(request):
    orders = TransferOrder.objects.filter(
        created_by=request.user
    ).exclude(status=OrderStatus.DRAFT).order_by("-created_at")
    return render(request, "queimados/orders.html", {"orders": orders})

@require_queimados
def q_order_detail(request, order_id):
    order = get_object_or_404(
        TransferOrder,
        id=order_id,
        created_by=request.user,
    )
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


# -------- AUSTIN --------

@require_austin
def a_orders(request):
    orders = TransferOrder.objects.exclude(status=OrderStatus.DRAFT).order_by("-created_at")
    return render(request, "austin/orders.html", {"orders": orders})

@require_austin
def a_order_detail(request, order_id):
    order = get_object_or_404(TransferOrder, id=order_id)
    items = order.items.select_related("product").order_by("product__name")

    if request.method == "POST":
        # atualizar qty_sent por item (somente em separação)
        if order.status != OrderStatus.PICKING:
            messages.error(request, "Você só pode alterar quantidades quando o pedido está em separação.")
            return redirect("a_order_detail", order_id=order.id)

        for item in items:
            field = f"sent_{item.id}"
            if field in request.POST:
                val = int(request.POST[field])
                if val < 0:
                    val = 0
                item.qty_sent = val
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

    # regra simples: exige que todo item tenha qty_sent definido (>=0 já tem por default)
    order.status = OrderStatus.DISPATCHED
    order.dispatched_at = timezone.now()
    order.save()

    messages.success(request, f"Pedido #{order.id} despachado para Queimados.")
    return redirect("a_order_detail", order_id=order.id)
