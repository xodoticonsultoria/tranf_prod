from django.urls import path
from . import views

urlpatterns = [
    # Queimados
    path("queimados/produtos/", views.q_products, name="q_products"),
    path("queimados/carrinho/", views.q_cart, name="q_cart"),
    path("queimados/carrinho/enviar/", views.q_submit_order, name="q_submit_order"),
    path("queimados/pedidos/", views.q_orders, name="q_orders"),
    path("queimados/pedidos/<int:order_id>/", views.q_order_detail, name="q_order_detail"),
    path("queimados/pedidos/<int:order_id>/receber/", views.q_receive_order, name="q_receive_order"),

    # 🔥 categorias (layout novo)
    path("queimados/categorias/", views.queimados_categories, name="q_categories"),

    # Austin
    path("austin/pedidos/", views.a_orders, name="a_orders"),
    path("austin/pedidos/<int:order_id>/", views.a_order_detail, name="a_order_detail"),
    path("austin/pedidos/<int:order_id>/iniciar-separacao/", views.a_start_picking, name="a_start_picking"),
    path("austin/pedidos/<int:order_id>/despachar/", views.a_dispatch, name="a_dispatch"),
    path("austin/pedidos/<int:order_id>/item/<int:item_id>/ok/", views.a_item_ok, name="a_item_ok"),
]
