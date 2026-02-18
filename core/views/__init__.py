from .auth import *
from .queimados import *
from .austin import *
from .reports import *

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
    queimados_categories,
)

# =====================
# AUSTIN
# =====================
from .austin import (
    a_orders,
    a_order_detail,
    a_start_picking,
    a_dispatch,
    a_item_ok,
    austin_badge,
    austin_poll,
)

# =====================
# REPORTS (AUSTIN + QUEIMADOS)
# =====================
from .reports import (
    a_report,
    a_report_pdf,
    a_report_pdf_single,
    q_report,
    q_report_pdf,
    q_report_pdf_single,
)

# =====================
# API
# =====================
from .austin import (
    order_status_poll,
)
