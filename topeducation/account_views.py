from django.contrib.auth.decorators import login_required
from django.http import JsonResponse

from .models import UserBillingProfile, StripeSubscription, StripePurchase


@login_required
def account_me(request):
    user = request.user
    profile = getattr(user, "billing", None)

    active_sub = StripeSubscription.objects.filter(user=user).order_by("-updated_at").first()

    return JsonResponse({
        "ok": True,
        "user": {
            "id": user.id,
            "email": user.email,
            "username": getattr(user, "username", ""),
            "first_name": user.first_name,
            "last_name": user.last_name,
        },
        "billing": {
            "stripe_customer_id": profile.stripe_customer_id if profile else None,
        },
        "subscription": {
            "status": active_sub.status if active_sub else None,
            "interval": active_sub.interval if active_sub else None,
            "price_id": active_sub.price_id if active_sub else None,
            "current_period_end": active_sub.current_period_end.isoformat() if active_sub and active_sub.current_period_end else None,
            "cancel_at_period_end": active_sub.cancel_at_period_end if active_sub else None,
        }
    })


@login_required
def account_purchases(request):
    user = request.user
    qs = StripePurchase.objects.filter(user=user).values(
        "id", "amount_total", "currency", "status", "description",
        "hosted_invoice_url", "invoice_pdf", "created_at"
    )[:50]

    return JsonResponse({
        "ok": True,
        "items": list(qs),
    })
