from .views import _get_or_create_cart

def cart_context(request):
    if request.user.is_authenticated:
        try:
            return {"cart": _get_or_create_cart(request.user)}
        except:
            return {"cart": None}
    return {"cart": None}
