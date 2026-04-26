from asgiref.sync import async_to_sync
from channels.layers import get_channel_layer
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib import messages
from django.utils import timezone
from django.views.decorators.http import require_GET
from django.http import JsonResponse
from django.db.models import F
from django.contrib.auth.decorators import login_required
from django.db import transaction

from core.models import (
    TransferOrder,
    OrderStatus,
    OrderLog,
    Despacho,
    DespachoItem,
)

from core.permissions import require_austin


# =====================================================
# LISTA DE PEDIDOS (CORRIGIDA)
# =====================================================

@require_austin
def a_orders(request):

    # 🔥 MESMA REGRA DA API (ESSENCIAL)
    orders = TransferOrder.objects.exclude(
        status=OrderStatus.DRAFT
    ).order_by("-created_at")

    return render(request, "austin/orders.html", {
        "orders": orders
    })


# =====================================================
# DETALHE DO PEDIDO
# =====================================================
@require_austin
def a_order_detail(request, order_id):
    order = get_object_or_404(TransferOrder, id=order_id)
    items = order.items.select_related("product")

    for item in items:
        item.missing_qty = max(0, item.qty_requested - item.qty_sent)

    # 🔥 ESSA LINHA FALTAVA
    logs = order.logs.all().order_by('-created_at')

    return render(request, "austin/order_detail.html", {
        "order": order,
        "items": items,
        "logs": logs  # 👈 ESSENCIAL
    })


# =====================================================
# INICIAR SEPARAÇÃO
# =====================================================

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

    OrderLog.objects.create(
        order=order,
        user=request.user,
        action="Iniciou separação"
    )

    return redirect("a_order_detail", order_id=order.id)


# =====================================================
# DESPACHO PRINCIPAL (CORRETO)
# =====================================================
@require_austin
def a_dispatch(request, order_id):

    if request.method != "POST":
        return redirect("a_order_detail", order_id=order_id)

    order = get_object_or_404(TransferOrder, id=order_id)
    items = order.items.select_related("product")

    if order.status != OrderStatus.PICKING:
        messages.error(request, "Só pode despachar durante separação.")
        return redirect("a_order_detail", order_id=order.id)

    itens_enviados = []

    for item in items:
        field = f"sent_{item.id}"

        try:
            enviar = int(request.POST.get(field, 0))
        except:
            continue

        falta = max(0, item.qty_requested - item.qty_sent)

        if enviar <= 0:
            continue

        enviar = min(enviar, falta)

        if enviar > 0:
            itens_enviados.append((item, enviar))

    if not itens_enviados:
        messages.error(request, "Nenhum item válido para envio.")
        return redirect("a_order_detail", order_id=order.id)

    try:
        with transaction.atomic():

            despacho = Despacho.objects.create(
                order=order,
                created_by=request.user,
                is_complementar=False
            )

            for item, enviar in itens_enviados:
                DespachoItem.objects.create(
                    despacho=despacho,
                    order_item=item,
                    qty_sent_now=enviar
                )

            order.status = OrderStatus.DISPATCHED
            order.dispatched_at = timezone.now()
            order.save(update_fields=["status", "dispatched_at"])

            OrderLog.objects.create(
                order=order,
                user=request.user,
                action="Despachou o pedido"
            )

    except Exception as e:
        print("💣 ERRO:", e)
        messages.error(request, f"Erro: {str(e)}")
        return redirect("a_order_detail", order_id=order.id)

    messages.success(request, "Pedido despachado com sucesso!")
    return redirect("a_order_detail", order_id=order.id)


# =====================================================
# LISTA DE ENVIO COMPLEMENTAR
# =====================================================

# 🔥 SOMENTE ALTERAÇÃO: remove return duplicado

@require_austin
def lista_envio_complementar(request):

    pedidos = TransferOrder.objects.filter(
        status__in=[OrderStatus.DISPATCHED, OrderStatus.RECEIVED]
    ).prefetch_related("items").order_by("-id")

    pedidos_com_info = []

    for pedido in pedidos:
        total = sum(i.qty_requested for i in pedido.items.all())
        enviado = sum(i.qty_sent for i in pedido.items.all())

        if total == 0:
            continue

        if enviado < total:
            progresso = int((enviado / total) * 100)

            pedidos_com_info.append({
                "pedido": pedido,
                "total": total,
                "enviado": enviado,
                "progresso": progresso,
                "faltando": total - enviado
            })

    return render(request, "austin/lista_envio_complementar.html", {
        "pedidos": pedidos_com_info
    })

# =====================================================
# ENVIO COMPLEMENTAR (CORRETO)
# =====================================================

@require_austin
def envio_complementar(request, order_id):

    order = get_object_or_404(TransferOrder, id=order_id)

    items = order.items.filter(
        qty_requested__gt=F("qty_sent")
    ).select_related("product")

    for item in items:
        item.faltando = item.qty_requested - item.qty_sent

    if request.method == "POST":

        with transaction.atomic():

            despacho = Despacho.objects.create(
                order=order,
                created_by=request.user,
                is_complementar=True
            )

            for item in items:

                try:
                    enviar = int(request.POST.get(f"qty_{item.id}", 0))
                except:
                    continue

                if enviar <= 0:
                    continue

                enviar = min(enviar, item.faltando)

                if enviar > 0:
                    DespachoItem.objects.create(
                        despacho=despacho,
                        order_item=item,
                        qty_sent_now=enviar
                    )

        order.status = OrderStatus.DISPATCHED
        order.dispatched_at = timezone.now()
        order.save(update_fields=["status", "dispatched_at"])

        OrderLog.objects.create(
            order=order,
            user=request.user,
            action="Envio complementar despachado"
        )

        messages.success(request, "Envio complementar realizado.")
        return redirect("lista_envio_complementar")

    return render(request, "austin/envio_complementar.html", {
        "order": order,
        "items": items
    })


# =====================================================
# HISTÓRICO
# =====================================================

@require_austin
def historico_despacho(request, order_id):
    order = get_object_or_404(TransferOrder, id=order_id)

    despachos = order.despachos.prefetch_related(
        "itens__order_item__product"
    )

    return render(request, "austin/historico_despacho.html", {
        "order": order,
        "despachos": despachos
    })


# =====================================================
# BADGE
# =====================================================

@require_GET
def austin_badge(request):
    count = TransferOrder.objects.filter(
        status=OrderStatus.SUBMITTED
    ).count()

    return JsonResponse({"count": count})


# =====================================================
# POLL STATUS
# =====================================================

@login_required
def order_status_poll(request, order_id):
    order = get_object_or_404(TransferOrder, id=order_id)

    return JsonResponse({
        "status": order.status,
        "status_display": order.get_status_display(),
    })


# =====================================================
# API LISTA AUSTIN (TEMPO REAL)
# =====================================================
@login_required
def a_orders_api(request):

    try:
        orders = TransferOrder.objects.exclude(
            status=OrderStatus.DRAFT
        ).order_by("-created_at")

        data = []

        for o in orders:
            data.append({
                "id": o.id,
                "status": o.status,
                "status_display": o.get_status_display(),
                "created_at": o.created_at.strftime("%d/%m/%Y %H:%M"),
                "from_branch": str(o.from_branch) if o.from_branch else "-"
            })

        return JsonResponse({"orders": data})

    except Exception as e:
        print("🔥 ERRO API:", e)
        return JsonResponse({"error": str(e)}, status=500)