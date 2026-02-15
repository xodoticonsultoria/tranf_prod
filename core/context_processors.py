from .models import TransferOrder, OrderStatus

def cart_badge(request):
    if not request.user.is_authenticated:
        return {}

    cart = TransferOrder.objects.filter(
        created_by=request.user,
        status=OrderStatus.DRAFT
    ).first()

    count = 0
    if cart:
        count = cart.items.count()

    return {
        "cart_count": count
    }

