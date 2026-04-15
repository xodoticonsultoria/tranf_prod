import os
import io

from django.shortcuts import render, get_object_or_404
from django.http import HttpResponse
from django.utils import timezone

from config import settings
from reportlab.platypus import (
    SimpleDocTemplate,
    Paragraph,
    Spacer,
    Table,
    TableStyle,
    Image,
)
from reportlab.lib.styles import getSampleStyleSheet
from reportlab.lib import colors
from reportlab.lib.units import inch

from core.models import TransferOrder, OrderStatus
from core.permissions import require_austin, require_queimados


# =========================================================
# HELPER DATA FORMAT
# =========================================================

def _fmt(dt):
    if not dt:
        return "-"
    return timezone.localtime(dt).strftime("%d/%m/%Y %H:%M")


# =========================================================
# ====================== AUSTIN ===========================
# =========================================================

@require_austin
def a_report(request):

    start = request.GET.get("start")
    end = request.GET.get("end")

    orders = None

    if start and end:
        orders = TransferOrder.objects.exclude(
            status=OrderStatus.DRAFT
        ).filter(
            created_at__date__gte=start,
            created_at__date__lte=end
        ).select_related("picking_by").order_by("-created_at")

    return render(request, "austin/report.html", {
        "orders": orders,
        "start": start,
        "end": end,
    })


@require_austin
def a_report_pdf(request):

    start = request.GET.get("start")
    end = request.GET.get("end")

    orders = TransferOrder.objects.exclude(
        status=OrderStatus.DRAFT
    ).select_related("picking_by").prefetch_related("items__product")

    if start:
        orders = orders.filter(created_at__date__gte=start)

    if end:
        orders = orders.filter(created_at__date__lte=end)

    return _generate_pdf_response(
        orders,
        "relatorio_austin.pdf",
        "RELATÓRIO AUSTIN",
        operator_field="picking_by"
    )


@require_austin
def a_report_pdf_single(request, order_id):

    order = get_object_or_404(
        TransferOrder.objects.select_related("picking_by")
        .prefetch_related("items__product"),
        id=order_id
    )

    return _generate_pdf_response(
        [order],
        f"pedido_{order.id}.pdf",
        "RELATÓRIO AUSTIN",
        operator_field="picking_by"
    )


# =========================================================
# ===================== QUEIMADOS =========================
# =========================================================

@require_queimados
def q_report(request):

    start = request.GET.get("start")
    end = request.GET.get("end")

    orders = None

    if start and end:
        orders = TransferOrder.objects.exclude(
            status=OrderStatus.DRAFT
        ).filter(
            created_at__date__gte=start,
            created_at__date__lte=end
        ).select_related("created_by").order_by("-created_at")

    return render(request, "queimados/report.html", {
        "orders": orders,
        "start": start,
        "end": end,
    })


@require_queimados
def q_report_pdf(request):

    start = request.GET.get("start")
    end = request.GET.get("end")

    orders = TransferOrder.objects.exclude(
        status=OrderStatus.DRAFT
    ).select_related("created_by").prefetch_related("items__product")

    if start:
        orders = orders.filter(created_at__date__gte=start)

    if end:
        orders = orders.filter(created_at__date__lte=end)

    return _generate_pdf_response(
        orders,
        "relatorio_queimados.pdf",
        "RELATÓRIO QUEIMADOS",
        operator_field="created_by"
    )


@require_queimados
def q_report_pdf_single(request, order_id):

    order = get_object_or_404(
        TransferOrder.objects.select_related("created_by")
        .prefetch_related("items__product"),
        id=order_id
    )

    return _generate_pdf_response(
        [order],
        f"pedido_queimados_{order.id}.pdf",
        "RELATÓRIO QUEIMADOS",
        operator_field="created_by"
    )


# =========================================================
# ====================== GERADOR PDF ======================
# =========================================================

def _generate_pdf_response(orders, filename, title, operator_field):

    response = HttpResponse(content_type="application/pdf")
    response["Content-Disposition"] = f'attachment; filename="{filename}"'

    buffer = io.BytesIO()

    # 🔥 MENOS ESPAÇO NO TOPO
    doc = SimpleDocTemplate(
        buffer,
        topMargin=10,
        bottomMargin=20,
        leftMargin=30,
        rightMargin=30
    )

    elements = []
    styles = getSampleStyleSheet()

    # LOGO
    logo_path = os.path.join(settings.BASE_DIR, "static", "xodo.png")

    if os.path.exists(logo_path):
        logo = Image(logo_path, width=100, height=70)
        logo.hAlign = "RIGHT"
        elements.append(logo)
        elements.append(Spacer(1, 0.1 * inch))

    # TÍTULO
    elements.append(Paragraph(f"<b>{title}</b>", styles["Title"]))
    elements.append(Spacer(1, 0.05 * inch))

    # PEDIDOS
    for order in orders:

        operator = getattr(order, operator_field)
        operator_name = operator.username if operator else "-"

        elements.append(Paragraph(f"<b>Pedido #{order.id}</b>", styles["Heading2"]))
        elements.append(Spacer(1, 0.1 * inch))

        elements.append(Paragraph(f"Operador: {operator_name}", styles["Normal"]))
        elements.append(Paragraph(f"Data Pedido: {_fmt(order.created_at)}", styles["Normal"]))
        elements.append(Paragraph(f"Início Separação: {_fmt(order.picking_at)}", styles["Normal"]))
        elements.append(Paragraph(f"Despacho: {_fmt(order.dispatched_at)}", styles["Normal"]))

        elements.append(Spacer(1, 0.1 * inch))

        data = [["Produto", "Pedido", "Enviado"]]

        for item in order.items.all():
            data.append([
                item.product.name,
                str(item.qty_requested),
                str(item.qty_sent or 0)
            ])

        table = Table(data, colWidths=[250, 80, 80])
        table.setStyle(TableStyle([

            ("BACKGROUND", (0, 0), (-1, 0), colors.red),
            ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),

            ("GRID", (0, 0), (-1, -1), 0.3, colors.grey),

            ("ALIGN", (1, 1), (-1, -1), "CENTER"),

            # 🔥 FONTE MENOR
            ("FONTSIZE", (0, 0), (-1, -1), 7),

            # 🔥 LINHAS MAIS FINAS
            ("TOPPADDING", (0, 0), (-1, -1), 2),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 2),

            ("LEFTPADDING", (0, 0), (-1, -1), 4),
            ("RIGHTPADDING", (0, 0), (-1, -1), 4),

        ]))

        elements.append(table)
        elements.append(Spacer(1, 0.3 * inch))

    doc.build(elements)

    pdf = buffer.getvalue()
    buffer.close()
    response.write(pdf)

    return response