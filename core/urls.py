from django.shortcuts import render
from django.urls import path
from django.http import HttpResponse
from . import views
from .views import envio_complementar, lista_envio_complementar

# 🔥 TESTE DE VIDA
def teste(request):
    return HttpResponse("OK")

urlpatterns = [


    # =====================
    # QUEIMADOS
    # =====================

    path("queimados/produtos/", views.q_products, name="q_products"),
    path("queimados/carrinho/", views.q_cart, name="q_cart"),
    path("queimados/carrinho/enviar/", views.q_submit_order, name="q_submit_order"),

    path("queimados/pedidos/", views.q_orders, name="q_orders"),

    # 🔥 ESPECÍFICA PRIMEIRO
    path("queimados/pedidos/<int:order_id>/receber/", views.q_receive_order, name="q_receive_order"),

    # 🔥 GENÉRICA DEPOIS
    path("queimados/pedidos/<int:order_id>/", views.q_order_detail, name="q_order_detail"),

    # 🔥 RELATÓRIO
    path("queimados/relatorio/", views.q_report, name="q_report"),
    path("queimados/relatorio/pdf/", views.q_report_pdf, name="q_report_pdf"),
    path("queimados/relatorio/pdf/<int:order_id>/", views.q_report_pdf_single, name="q_report_pdf_single"),

    # REMOVER ITEM
    path("queimados/carrinho/remover/<int:item_id>/", views.q_remove_item, name="q_remove_item"),

    # APIs
    path("q/add-product/", views.q_add_product, name="q_add_product"),
    path("q/update-item/", views.q_update_item),
    path("q/remove-item/", views.q_remove_item_api),
    path("austin/api/orders/", views.a_orders_api, name="a_orders_api"),





    # =====================
    # AUSTIN
    # =====================

    path("austin/pedidos/", views.a_orders, name="a_orders"),
    path("austin/pedidos/<int:order_id>/", views.a_order_detail, name="a_order_detail"),
    path("austin/pedidos/<int:order_id>/iniciar-separacao/", views.a_start_picking, name="a_start_picking"),
    path("austin/pedidos/<int:order_id>/despachar/", views.a_dispatch, name="a_dispatch"),

    path("austin/relatorio/", views.a_report, name="a_report"),
    path("austin/relatorio/pdf/", views.a_report_pdf, name="a_report_pdf"),
    path("austin/relatorio/pdf/<int:order_id>/", views.a_report_pdf_single, name="a_report_pdf_single"),

    path("pedido/<int:order_id>/historico/", views.historico_despacho, name="historico_despacho"),

    # ENVIO COMPLEMENTAR
    path("austin/envio-complementar/", lista_envio_complementar, name="lista_envio_complementar"),
    path("austin/envio-complementar/<int:order_id>/", envio_complementar, name="envio_complementar"),

    # =====================
    # API
    # =====================

    path("austin/api/badge/", views.austin_badge, name="austin_badge"),

    # =====================
    # TESTE EXTRA
    # =====================

    path("teste/", lambda r: render(r, "test.html")),
    path("pedido/<int:order_id>/poll/", views.order_status_poll, name="order_status_poll"),
]