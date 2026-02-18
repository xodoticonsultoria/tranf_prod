from core.models import TransferOrder, OrderStatus

def cart_badge(request):
    if not request.user.is_authenticated:
        return {}

    if request.user.groups.filter(name="QUEIMADOS").exists():

        cart = TransferOrder.objects.filter(
            created_by=request.user,
            status=OrderStatus.DRAFT
        ).first()

        if cart:
            total = sum(item.qty_requested for item in cart.items.all())
        else:
            total = 0

        return {
            "cart_count": total
        }

    return {}
