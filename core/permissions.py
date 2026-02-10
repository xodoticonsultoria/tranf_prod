from django.shortcuts import redirect

def require_group(name):
    def decorator(view):
        def wrapped(request, *args, **kwargs):
            if request.user.is_authenticated and request.user.groups.filter(name=name).exists():
                return view(request, *args, **kwargs)
            return redirect("home")
        return wrapped
    return decorator

require_austin = require_group("AUSTIN")
require_queimados = require_group("QUEIMADOS")
