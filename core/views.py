from django.contrib import messages
from django.contrib.auth import authenticate, login, logout
from django.db import transaction
from django.shortcuts import render, redirect
from django.utils import timezone
from django.views.decorators.http import require_GET

from django.http import JsonResponse
from django.shortcuts import get_object_or_404
from django.contrib.auth.decorators import login_required

from .models import (
    Category,
    Product,
    TransferOrder,
    TransferOrderItem,
    OrderStatus,
    Branch,
    OrderLog,
)

from .permissions import require_austin, require_queimados

import io
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle
from reportlab.lib.styles import getSampleStyleSheet
from reportlab.lib import colors
from reportlab.lib.units import inch
from django.http import HttpResponse


# =====================
# Helpers
# =====================
def _has_group(user, name: str) -> bool:
    return user.is_authenticated and user.groups.filter(name=name).exists()


# =====================
# Auth
# =====================
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


# =====================
# Home
# =====================
@login_required
def home(request):
    user = request.user

    if _has_group(user, "QUEIMADOS"):
        return redirect("q_products")

    if _has_group(user, "AUSTIN"):
        return redirect("a_orders")

    messages.error(request, "Usuário sem grupo (AUSTIN/QUEIMADOS).")
    return redirect("/admin/")


# =====================
# QUEIMADOS
# =====================
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

    return render(
        request,
        "queimados/products.html",
        {"cart": cart, "categories": categories},
    )


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

    OrderLog.objects.create(
        order=cart,
        user=request.user,
        action="Enviou o pedido para Austin"
    )

    messages.success(request, f"Pedido #{cart.id} enviado com sucesso!")
    return redirect("q_cart")


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
        created_by=request.user
    )
    items = order.items.select_related("product")

    return render(
        request,
        "queimados/order_detail.html",
        {"order": order, "items": items},
    )


@require_queimados
def q_receive_order(request, order_id):
    order = get_object_or_404(
        TransferOrder,
        id=order_id,
        created_by=request.user
    )

    if order.status != OrderStatus.DISPATCHED:
        messages.error(request, "Só pode confirmar quando Austin despachar.")
        return redirect("q_order_detail", order_id=order.id)

    order.status = OrderStatus.RECEIVED
    order.received_at = timezone.now()
    order.save()

    OrderLog.objects.create(
        order=order,
        user=request.user,
        action="Confirmou recebimento do pedido"
    )

    messages.success(request, f"Pedido #{order.id} confirmado.")
    return redirect("q_order_detail", order_id=order.id)


# =====================
# AUSTIN
# =====================

@require_austin
def a_orders(request):
    # 🔥 MOSTRA SOMENTE pedidos ATIVOS
    orders = TransferOrder.objects.filter(
        status__in=[
            OrderStatus.SUBMITTED,
            OrderStatus.PICKING,
        ]
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

    return render(
        request,
        "austin/order_detail.html",
        {"order": order, "items": items},
    )


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


@require_austin
def a_dispatch(request, order_id):
    order = get_object_or_404(TransferOrder, id=order_id)

    if order.status != OrderStatus.PICKING:
        messages.error(request, "Só pode despachar durante separação.")
        return redirect("a_order_detail", order_id=order.id)

    order.status = OrderStatus.DISPATCHED
    order.dispatched_at = timezone.now()
    order.save()

    OrderLog.objects.create(
        order=order,
        user=request.user,
        action="Despachou o pedido para Queimados"
    )

    return redirect("a_order_detail", order_id=order.id)


@require_austin
@require_GET
def austin_poll(request):
    qs = TransferOrder.objects.filter(status=OrderStatus.SUBMITTED)
    newest = qs.order_by("-id").first()

    return JsonResponse({
        "count": qs.count(),
        "newest_id": newest.id if newest else 0
    })


# ============================
# TEMPO REAL — STATUS PEDIDO
# ============================

@login_required
def order_status_poll(request, order_id):
    order = get_object_or_404(TransferOrder, id=order_id)

    return JsonResponse({
        "status": order.status,
        "status_display": order.get_status_display(),
    })


# =====================
# RELATÓRIOS
# =====================

@require_queimados
def q_report(request):
    orders = TransferOrder.objects.exclude(status=OrderStatus.DRAFT)
    return render(request, "queimados/report.html", {"orders": orders})


@require_austin
def a_report(request):
    orders = TransferOrder.objects.exclude(status=OrderStatus.DRAFT)
    return render(request, "austin/report.html", {"orders": orders})


@require_queimados
def queimados_categories(request):
    categories = Category.objects.filter(active=True).prefetch_related("products")
    return render(
        request,
        "queimados/categories.html",
        {"categories": categories},
    )

@require_austin
def a_item_ok(request, order_id, item_id):
    order = get_object_or_404(TransferOrder, id=order_id)
    item = get_object_or_404(TransferOrderItem, id=item_id, order=order)

    if order.status != OrderStatus.PICKING:
        messages.error(request, "Só pode marcar OK durante separação.")
        return redirect("a_order_detail", order_id=order.id)

    item.qty_sent = item.qty_requested
    item.save()

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

    return JsonResponse({
        "count": count
    })

@require_austin
def a_report(request):
    return render(request, "austin/report.html")




@require_austin
def a_report_pdf(request):

    orders = TransferOrder.objects.exclude(
        status=OrderStatus.DRAFT
    ).select_related("picking_by").prefetch_related("items__product")

    start = request.GET.get("start")
    end = request.GET.get("end")
    branch = request.GET.get("branch")

    if start:
        orders = orders.filter(created_at__date__gte=start)

    if end:
        orders = orders.filter(created_at__date__lte=end)

    if branch:
        orders = orders.filter(from_branch=branch)

    response = HttpResponse(content_type='application/pdf')
    response['Content-Disposition'] = 'attachment; filename="relatorio_austin_detalhado.pdf"'

    buffer = io.BytesIO()
    doc = SimpleDocTemplate(buffer)
    elements = []

    styles = getSampleStyleSheet()

    elements.append(Paragraph("<b>RELATÓRIO AUSTIN</b>", styles["Title"]))
    elements.append(Spacer(1, 0.3 * inch))

    for order in orders:

        elements.append(Paragraph(f"<b>Pedido #{order.id}</b>", styles["Heading2"]))
        elements.append(Spacer(1, 0.2 * inch))

        elements.append(Paragraph(f"Data do Pedido: {order.created_at.strftime('%d/%m/%Y %H:%M')}", styles["Normal"]))

        elements.append(Paragraph(
            f"Operador: {order.picking_by.username if order.picking_by else '-'}",
            styles["Normal"]
        ))

        elements.append(Paragraph(
            f"Início Separação: {order.picking_at.strftime('%d/%m/%Y %H:%M') if order.picking_at else '-'}",
            styles["Normal"]
        ))

        elements.append(Paragraph(
            f"Despacho: {order.dispatched_at.strftime('%d/%m/%Y %H:%M') if order.dispatched_at else '-'}",
            styles["Normal"]
        ))

        elements.append(Spacer(1, 0.2 * inch))

        elements.append(Paragraph("<b>Produtos:</b>", styles["Heading3"]))
        elements.append(Spacer(1, 0.1 * inch))

        data = [["Produto", "Pedido", "Enviado"]]

        for item in order.items.all():
            data.append([
                item.product.name,
                str(item.qty_requested),
                str(item.qty_sent if item.qty_sent else 0)
            ])

        table = Table(data, colWidths=[200, 80, 80])
        table.setStyle(TableStyle([
            ('BACKGROUND', (0,0), (-1,0), colors.red),
            ('TEXTCOLOR', (0,0), (-1,0), colors.white),
            ('GRID', (0,0), (-1,-1), 0.5, colors.grey),
            ('ALIGN', (1,1), (-1,-1), 'CENTER'),
        ]))

        elements.append(table)
        elements.append(Spacer(1, 0.2 * inch))

        elements.append(Paragraph("<b>Observação:</b>", styles["Heading3"]))
        elements.append(Spacer(1, 0.1 * inch))

        elements.append(Paragraph(
            order.notes_from_austin if order.notes_from_austin else "Sem observações.",
            styles["Normal"]
        ))

        elements.append(Spacer(1, 0.5 * inch))

    doc.build(elements)
    pdf = buffer.getvalue()
    buffer.close()
    response.write(pdf)

    return response

