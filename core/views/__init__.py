# =====================
# AUTH
# =====================
from .auth import (
    login_view,
    logout_view,
    home,
)

# =====================
# QUEIMADOS
# =====================
from .queimados import (
    q_products,
    q_cart,
    q_submit_order,
    q_orders,
    q_order_detail,
    q_receive_order,
    q_remove_item,        # 🔥 ADICIONA ISSO
    q_add_product,
    q_update_item,
    q_remove_item_api,
)
# =====================
# AUSTIN
# =====================
from .austin import (
    a_orders,
    a_order_detail,
    a_start_picking,
    a_dispatch,
)

# =====================
# REPORTS
# =====================
from .reports import (
    a_report,
    a_report_pdf,
    a_report_pdf_single,
    q_report,
    q_report_pdf,
    q_report_pdf_single,
)