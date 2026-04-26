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
from django.http import JsonResponse
from django.shortcuts import get_object_or_404

# =====================================================
# LISTA DE PEDIDOS (CORRIGIDA)
# =====================================================

@require_austin
def a_orders(request):

    # 🔥 MESMA REGRA DA API (ESSENCIAL)
    orders = TransferOrder.objects.exclude(
        status=OrderStatus.DRAFT
    ).select_related("from_branch").order_by("-created_at")[:5]

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

    total_pedido = sum(i.qty_requested for i in items)
    total_enviado_total = sum(i.qty_sent for i in items)
    faltando_total = max(0, total_pedido - total_enviado_total)

    logs = order.logs.all().order_by('created_at')

    # 🔥 MELHORADO
    despachos = order.despachos.filter(
        is_complementar=True
    ).prefetch_related("itens")

    contador = 0
    enviado_acumulado = 0
    logs_processados = []

    for log in logs:

        if "Envio complementar despachado" in log.action:
            contador += 1

            if contador <= len(despachos):
                despacho = despachos[contador - 1]

                total_envio = sum(i.qty_sent_now for i in despacho.itens.all())
                enviado_acumulado += total_envio

                faltante = max(0, total_pedido - enviado_acumulado)
                progresso = int((enviado_acumulado / total_pedido) * 100) if total_pedido else 0

                log.display_action = f"Envio complementar {contador} — {total_envio} itens enviados"
                log.faltante = faltante
                log.progresso = progresso

            else:
                log.display_action = f"Envio complementar {contador}"
                log.faltante = 0
                log.progresso = 100

        else:
            log.display_action = log.action
            log.faltante = None
            log.progresso = None

        logs_processados.append(log)

    logs_processados = list(reversed(logs_processados))

    return render(request, "austin/order_detail.html", {
        "order": order,
        "items": items,
        "logs": logs_processados,
        "faltando": faltando_total,
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
# DESPACHO PRINCIPAL
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
        try:
            enviar = int(request.POST.get(f"sent_{item.id}", 0))
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
# API LISTA AUSTIN (TEMPO REAL)
# =====================================================

@require_austin
def a_orders_api(request):

    try:
        orders = (
            TransferOrder.objects
            .exclude(status=OrderStatus.DRAFT)
            .select_related("from_branch")
            .order_by("-created_at")[:5]
        )

        data = [
            {
                "id": o.id,
                "status": o.status,
                "status_display": o.get_status_display(),
                "created_at": o.created_at.strftime("%d/%m/%Y %H:%M"),
                "from_branch": str(o.from_branch) if o.from_branch else "-"
            }
            for o in orders
        ]

        return JsonResponse({"orders": data})

    except Exception as e:
        print("🔥 ERRO API:", e)
        return JsonResponse({"error": str(e)}, status=500)




# =====================================================
# BADGE (VOLTA PRA NÃO QUEBRAR IMPORT)
# =====================================================
# =====================================================
# POLL STATUS (NECESSÁRIO PRO IMPORT)
# =====================================================

# =====================================================
# BADGE (NECESSÁRIO PRO IMPORT)
# =====================================================

from django.views.decorators.http import require_GET

@require_GET
def austin_badge(request):
    count = TransferOrder.objects.filter(
        status=OrderStatus.SUBMITTED
    ).count()

    return JsonResponse({
        "count": count
    })