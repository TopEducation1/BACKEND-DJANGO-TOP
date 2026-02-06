from functools import wraps
from django.http import JsonResponse

def api_login_required(view_func):
    @wraps(view_func)
    def _wrapped(request, *args, **kwargs):
        if not request.user.is_authenticated:
            return JsonResponse(
                {"ok": False, "error": "not_authenticated"},
                status=401
            )
        return view_func(request, *args, **kwargs)
    return _wrapped
