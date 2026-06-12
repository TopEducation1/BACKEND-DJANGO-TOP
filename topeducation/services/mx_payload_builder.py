from django.utils import timezone


def iso_from_ts(ts):
    if not ts:
        return None

    return timezone.datetime.fromtimestamp(
        ts,
        tz=timezone.get_current_timezone()
    ).isoformat()


def get_price_id_from_subscription(subscription):
    try:
        return subscription["items"]["data"][0]["price"]["id"]
    except Exception:
        return None


def build_mx_payload_from_stripe_event(
    event,
    event_type,
    stripe_object,
    user=None,
    route=None,
):
    obj = stripe_object or {}

    stripe_event_id = event.get("id")
    occurred_at = iso_from_ts(event.get("created")) or timezone.now().isoformat()

    customer_details = obj.get("customer_details") or {}

    customer_email = (
        getattr(user, "email", None)
        or customer_details.get("email")
        or obj.get("customer_email")
        or obj.get("customer_email_address")
    )

    full_name = user.get_full_name() if user else ""

    name = getattr(user, "first_name", "") or ""
    last_name = getattr(user, "last_name", "") or ""

    stripe_customer_id = obj.get("customer")
    stripe_subscription_id = obj.get("subscription") or obj.get("id")

    price_id = None
    amount_cents = (
        obj.get("amount_paid")
        or obj.get("amount_total")
        or obj.get("amount_due")
    )

    currency = (obj.get("currency") or "usd").upper()

    period_start = None
    period_end = None
    paid_at = None

    if event_type.startswith("invoice."):
        stripe_subscription_id = obj.get("subscription")
        paid_at = occurred_at
        period_start = iso_from_ts(obj.get("period_start"))
        period_end = iso_from_ts(obj.get("period_end"))

        lines = obj.get("lines", {}).get("data", [])
        if lines:
            price_id = lines[0].get("price", {}).get("id")

    elif event_type.startswith("customer.subscription."):
        price_id = get_price_id_from_subscription(obj)
        period_start = iso_from_ts(obj.get("current_period_start"))
        period_end = iso_from_ts(obj.get("current_period_end"))

    elif event_type == "checkout.session.completed":
        price_id = (obj.get("metadata") or {}).get("price_id")

    return {
        "eventId": f"colombia-b2c:{event_type}:{stripe_event_id}",
        "eventType": event_type,
        "occurredAt": occurred_at,
        "source": "colombia-b2c",
        "customer": {
            "email": customer_email,
            "name": name,
            "lastName": last_name,
            "fullName": full_name,
        },
        "subscription": {
            "billingPeriod": "MONTHLY",
            "stripeCustomerId": stripe_customer_id,
            "stripeSubscriptionId": stripe_subscription_id,
            "stripePriceId": price_id,
            "currency": currency,
            "amountCents": amount_cents,
            "paidAt": paid_at,
            "periodStart": period_start,
            "periodEnd": period_end,
        },
        "metadata": {
            "traceId": stripe_event_id,
            "routeId": str(route.id) if route else None,
            "checkoutSessionId": (
                obj.get("id") if event_type == "checkout.session.completed" else None
            ),
        },
    }