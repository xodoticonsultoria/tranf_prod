from asgiref.sync import async_to_sync
from channels.layers import get_channel_layer
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib import messages
from django.utils import timezone
from django.views.decorators.http import require_GET
from django.http import JsonResponse

from core.models import TransferOrder, OrderStatus, TransferOrderItem, OrderLog
from core.permissions import require_austin


@require_austin
def a_orders(request):
    orders = TransferOrder.objects.filter(
        status__in=[OrderStatus.SUBMITTED, OrderStatus.PICKING]
    ).order_by("-created_at")

    return render(request, "austin/orders.html", {"orders": orders})


@require_austin
def a_order_detail(request, order_id):
    order = get_object_or_404(TransferOrder, id=order_id)
    items = order.items.select_related("product")

    if request.method == "POST":
        if order.status != OrderStatus.PICKING:
            messages.error(request, "Só pode alterar durante separação.")
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

    return render(request, "austin/order_detail.html", {
        "order": order,
        "items": items
    })


@require_austin
def a_start_picking(request, order_id):
    order = get_object_or_404(TransferOrder, id=order_id)

    if order.status != OrderStatus.SUBMITTED:
        messages.error(request, "Só pode iniciar quando enviado.")
        return redirect("a_order_detail", order_id=order.id)

    order.status = OrderStatus.PICKING
    order.picking_by = request.user
    order.picking_at = timezone.now()
    order.save()

    channel_layer = get_channel_layer()

    async_to_sync(channel_layer.group_send)(
        "orders_group",
        {
            "type": "order_update",
            "order_id": order.id,
            "status": order.status,
            "status_display": order.get_status_display(),
        }
    )

    OrderLog.objects.create(
        order=order,
        user=request.user,
        action="Iniciou separação"
    )

    return redirect("a_order_detail", order_id=order.id)


@require_austin
def a_dispatch(request, order_id):

    if request.method != "POST":
        return redirect("a_order_detail", order_id=order_id)

    order = get_object_or_404(TransferOrder, id=order_id)

    if order.status != OrderStatus.PICKING:
        messages.error(request, "Só pode despachar durante separação.")
        return redirect("a_order_detail", order_id=order.id)

    # 🔥 SALVAR QUANTIDADES ENVIADAS
    for item in order.items.all():
        field = f"sent_{item.id}"

        if field in request.POST:
            try:
                val = int(request.POST.get(field))
                item.qty_sent = max(0, val)
                item.save()
            except (ValueError, TypeError):
                pass

    # 🔥 SALVAR OBSERVAÇÃO
    order.notes_from_austin = request.POST.get("notes_from_austin", "")

    order.status = OrderStatus.DISPATCHED
    order.dispatched_at = timezone.now()
    order.save()

    log = OrderLog.objects.create(
        order=order,
        user=request.user,
        action="Despachou o pedido"
    )

    channel_layer = get_channel_layer()

    async_to_sync(channel_layer.group_send)(
        "orders_group",
        {
            "type": "order_update",
            "order_id": order.id,
            "status": order.status,
            "status_display": order.get_status_display(),
            "log": {
                "created_at": log.created_at.strftime("%d/%m/%Y %H:%M:%S"),
                "user": log.user.username,
                "action": log.action,
            }
        }
    )

    return redirect("a_order_detail", order_id=order.id)

@require_austin
def a_item_ok(request, order_id, item_id):
    order = get_object_or_404(TransferOrder, id=order_id)
    item = get_object_or_404(TransferOrderItem, id=item_id, order=order)

    if order.status != OrderStatus.PICKING:
        messages.error(request, "Só pode marcar OK durante separação.")
        return redirect("a_order_detail", order_id=order.id)

    item.qty_sent = item.qty_requested
    item.save()

    channel_layer = get_channel_layer()

    async_to_sync(channel_layer.group_send)(
            "orders_group",
            {
                "type": "order_update",
                "order_id": order.id,
                "status": order.status,
                "status_display": order.get_status_display(),
            }
        )

    OrderLog.objects.create(
        order=order,
        user=request.user,
        action=f"Marcou OK para {item.product.name}"
    )

    return redirect("a_order_detail", order_id=order.id)
@require_austin
@require_GET
def austin_badge(request):
    count = TransferOrder.objects.filter(
        status=OrderStatus.SUBMITTED
    ).count()

    return JsonResponse({"count": count})


from django.contrib.auth.decorators import login_required

@login_required
def order_status_poll(request, order_id):
    order = get_object_or_404(TransferOrder, id=order_id)

    return JsonResponse({
        "status": order.status,
        "status_display": order.get_status_display(),
    })
