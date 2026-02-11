from .models import TransferOrderItem, OrderStatus

def cart_badge(request):
    if not request.user.is_authenticated:
        return {"cart_count": 0}

    count = TransferOrderItem.objects.filter(
        order__created_by=request.user,
        order__status=OrderStatus.DRAFT
    ).count()

    return {"cart_count": count}
