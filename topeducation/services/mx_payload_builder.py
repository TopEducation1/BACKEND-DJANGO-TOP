import uuid
from datetime import datetime, timezone as dt_timezone
from decimal import Decimal
from typing import Any, Dict, Optional

from django.utils import timezone


SOURCE_NAME = "colombia-b2c"
DEFAULT_SCHEMA_VERSION = "1.1"


# =========================================================
# UTILIDADES
# =========================================================

def iso_from_ts(value: Any) -> Optional[str]:
    """
    Convierte timestamps Unix o datetime a ISO 8601.

    Stripe normalmente entrega timestamps Unix en segundos.
    """
    if value in (None, ""):
        return None

    if isinstance(value, datetime):
        dt = value

        if timezone.is_naive(dt):
            dt = timezone.make_aware(
                dt,
                timezone.get_current_timezone(),
            )

        return dt.astimezone(dt_timezone.utc).isoformat()

    try:
        timestamp = int(value)
    except (TypeError, ValueError):
        return None

    return datetime.fromtimestamp(
        timestamp,
        tz=dt_timezone.utc,
    ).isoformat()


def now_iso() -> str:
    return timezone.now().astimezone(dt_timezone.utc).isoformat()


def normalize_email(value: Any) -> Optional[str]:
    email = str(value or "").strip().lower()
    return email or None


def normalize_currency(value: Any) -> str:
    currency = str(value or "usd").strip().upper()
    return currency or "USD"


def normalize_amount_cents(value: Any) -> Optional[int]:
    if value in (None, ""):
        return None

    try:
        return int(Decimal(str(value)))
    except (TypeError, ValueError, ArithmeticError):
        return None


def safe_get_full_name(user: Any) -> str:
    if not user:
        return ""

    try:
        full_name = user.get_full_name()
    except Exception:
        full_name = ""

    if full_name:
        return str(full_name).strip()

    first_name = str(getattr(user, "first_name", "") or "").strip()
    last_name = str(getattr(user, "last_name", "") or "").strip()

    return f"{first_name} {last_name}".strip()


def compact_dict(value: Any) -> Any:
    """
    Elimina valores None recursivamente.

    Conserva:
    - False
    - 0
    - strings vacíos cuando son intencionales
    - listas vacías
    """
    if isinstance(value, dict):
        return {
            key: compact_dict(item)
            for key, item in value.items()
            if item is not None
        }

    if isinstance(value, list):
        return [
            compact_dict(item)
            for item in value
            if item is not None
        ]

    return value


def get_first_dict_value(data: Dict[str, Any], *keys: str) -> Any:
    for key in keys:
        value = data.get(key)

        if value not in (None, ""):
            return value

    return None


def get_price_id_from_subscription(subscription: Dict[str, Any]) -> Optional[str]:
    try:
        items = subscription.get("items") or {}
        data = items.get("data") or []

        if not data:
            return None

        first_item = data[0] or {}
        price = first_item.get("price") or {}

        return price.get("id")
    except (AttributeError, IndexError, TypeError):
        return None


def get_invoice_price_id(invoice: Dict[str, Any]) -> Optional[str]:
    try:
        lines = (invoice.get("lines") or {}).get("data") or []

        if not lines:
            return None

        line = lines[0] or {}

        price = line.get("price") or {}
        if price.get("id"):
            return price["id"]

        pricing = line.get("pricing") or {}
        price_details = pricing.get("price_details") or {}

        return price_details.get("price")
    except (AttributeError, IndexError, TypeError):
        return None


def get_subscription_from_user(user: Any):
    """
    Obtiene la suscripción Stripe local más reciente del usuario.

    Se evita importar StripeSubscription directamente para reducir
    acoplamiento y posibles importaciones circulares.
    """
    if not user:
        return None

    manager = getattr(user, "stripe_subscriptions", None)

    if manager is None:
        return None

    try:
        return manager.order_by("-updated_at", "-id").first()
    except Exception:
        return None


def resolve_route_snapshot(route=None, route_snapshot=None):
    """
    Obtiene el snapshot explícito o el snapshot actual del Lead.

    route:
        LearningRouteLead

    route_snapshot:
        LearningRouteSnapshot
    """
    if route_snapshot is not None:
        return route_snapshot

    if route is None:
        return None

    snapshots = getattr(route, "route_snapshots", None)

    if snapshots is None:
        return None

    try:
        current = snapshots.filter(is_current=True).order_by("-version").first()

        if current:
            return current

        return snapshots.order_by("-version").first()
    except Exception:
        return None


# =========================================================
# CUSTOMER
# =========================================================

def build_customer_snapshot(
    *,
    user=None,
    route=None,
    stripe_object=None,
) -> Dict[str, Any]:
    obj = stripe_object or {}
    customer_details = obj.get("customer_details") or {}

    email = normalize_email(
        getattr(user, "email", None)
        or getattr(route, "email", None)
        or customer_details.get("email")
        or obj.get("customer_email")
        or obj.get("customer_email_address")
        or (obj.get("receipt_email") if isinstance(obj, dict) else None)
    )

    first_name = (
        getattr(user, "first_name", None)
        or getattr(route, "first_name", None)
        or ""
    )

    last_name = (
        getattr(user, "last_name", None)
        or getattr(route, "last_name", None)
        or ""
    )

    full_name = safe_get_full_name(user)

    if not full_name:
        full_name = f"{first_name} {last_name}".strip()

    phone = (
        getattr(route, "phone_e164", None)
        or customer_details.get("phone")
    )

    country = (
        getattr(route, "country", None)
        or ((customer_details.get("address") or {}).get("country"))
    )

    customer = {
        "userId": str(user.pk) if user and getattr(user, "pk", None) else None,
        "email": email,
        "name": str(first_name or "").strip(),
        "lastName": str(last_name or "").strip(),
        "fullName": full_name,
        "phone": phone,
        "country": country,
    }

    return compact_dict(customer)


# =========================================================
# PLAN Y ACCESO
# =========================================================

def infer_billing_period_from_interval(interval: Any) -> Optional[str]:
    normalized = str(interval or "").strip().lower()

    if normalized in {"month", "monthly"}:
        return "MONTHLY"

    if normalized in {"year", "annual", "yearly"}:
        return "ANNUAL"

    return None


def build_plan_snapshot(
    *,
    route=None,
    local_subscription=None,
) -> Dict[str, Any]:
    package_code = getattr(
        route,
        "package_code",
        None,
    ) or getattr(
        local_subscription,
        "package_code",
        None,
    ) or "TOP_EDUCATION_FREE"

    tier = getattr(
        route,
        "tier",
        None,
    ) or getattr(
        local_subscription,
        "tier",
        None,
    ) or "FREE"

    billing_period = getattr(
        route,
        "billing_period",
        None,
    ) or getattr(
        local_subscription,
        "billing_period",
        None,
    ) or infer_billing_period_from_interval(
        getattr(local_subscription, "interval", None)
    )

    access_status = getattr(
        route,
        "access_status",
        None,
    ) or getattr(
        local_subscription,
        "access_status",
        None,
    ) or "ALLOWED"

    lifecycle_status = getattr(
        route,
        "lifecycle_status",
        None,
    ) or getattr(
        local_subscription,
        "lifecycle_status",
        None,
    ) or "FREE"

    pending_action = getattr(
        route,
        "pending_action",
        None,
    ) or getattr(
        local_subscription,
        "pending_action",
        None,
    ) or "NONE"

    plan = compact_dict({
        "packageCode": package_code,
        "tier": tier,
        "billingPeriod": billing_period,
        "accessStatus": access_status,
        "lifecycleStatus": lifecycle_status,
        "pendingAction": pending_action,
    })

    # Contrato MX:
    # TOP_EDUCATION_FREE no tiene periodo de facturación,
    # pero la propiedad debe enviarse explícitamente como null.
    if str(package_code or "").strip().upper() == "TOP_EDUCATION_FREE":
        plan["billingPeriod"] = None

    return plan


# =========================================================
# BILLING / STRIPE
# =========================================================

def extract_stripe_billing_data(
    *,
    event_type: str,
    stripe_object: Optional[Dict[str, Any]],
    occurred_at: str,
) -> Dict[str, Any]:
    obj = stripe_object or {}
    metadata = obj.get("metadata") or {}

    stripe_customer_id = obj.get("customer")
    stripe_subscription_id = obj.get("subscription")

    price_id = None
    period_start = None
    period_end = None
    paid_at = None
    trial_start = None
    trial_end = None
    cancel_at_period_end = None

    amount_cents = get_first_dict_value(
        obj,
        "amount_paid",
        "amount_total",
        "amount_due",
        "amount",
    )

    currency = normalize_currency(obj.get("currency"))

    if event_type.startswith("invoice."):
        stripe_subscription_id = obj.get("subscription")
        price_id = get_invoice_price_id(obj)

        period_start = iso_from_ts(obj.get("period_start"))
        period_end = iso_from_ts(obj.get("period_end"))

        if event_type in {
            "invoice.paid",
            "invoice.payment_succeeded",
        }:
            paid_at = occurred_at

        status_transitions = obj.get("status_transitions") or {}
        paid_at = (
            iso_from_ts(status_transitions.get("paid_at"))
            or paid_at
        )

    elif event_type.startswith("customer.subscription."):
        stripe_subscription_id = obj.get("id")
        price_id = get_price_id_from_subscription(obj)

        period_start = iso_from_ts(obj.get("current_period_start"))
        period_end = iso_from_ts(obj.get("current_period_end"))

        trial_start = iso_from_ts(obj.get("trial_start"))
        trial_end = iso_from_ts(obj.get("trial_end"))

        cancel_at_period_end = bool(
            obj.get("cancel_at_period_end", False)
        )

    elif event_type == "checkout.session.completed":
        stripe_subscription_id = obj.get("subscription")

        price_id = (
            metadata.get("price_id")
            or metadata.get("stripe_price_id")
        )

    elif event_type.startswith("payment_intent."):
        stripe_customer_id = obj.get("customer")
        paid_at = occurred_at if event_type == "payment_intent.succeeded" else None

    return compact_dict({
        "stripeCustomerId": stripe_customer_id,
        "stripeSubscriptionId": stripe_subscription_id,
        "stripePriceId": price_id,
        "currency": currency,
        "amountCents": normalize_amount_cents(amount_cents),
        "paidAt": paid_at,
        "periodStart": period_start,
        "periodEnd": period_end,
        "trialStart": trial_start,
        "trialEnd": trial_end,
        "cancelAtPeriodEnd": cancel_at_period_end,
    })


def build_billing_snapshot(
    *,
    event_type: str,
    stripe_object=None,
    route=None,
    local_subscription=None,
    occurred_at: str,
) -> Dict[str, Any]:
    stripe_data = extract_stripe_billing_data(
        event_type=event_type,
        stripe_object=stripe_object,
        occurred_at=occurred_at,
    )

    stripe_data["stripeCustomerId"] = (
        stripe_data.get("stripeCustomerId")
        or getattr(route, "stripe_customer_id", None)
        or getattr(local_subscription, "stripe_customer_id", None)
    )

    stripe_data["stripeSubscriptionId"] = (
        stripe_data.get("stripeSubscriptionId")
        or getattr(route, "stripe_subscription_id", None)
        or getattr(local_subscription, "stripe_subscription_id", None)
    )

    stripe_data["stripePriceId"] = (
        stripe_data.get("stripePriceId")
        or getattr(local_subscription, "price_id", None)
    )

    stripe_data["periodEnd"] = (
        stripe_data.get("periodEnd")
        or iso_from_ts(getattr(local_subscription, "current_period_end", None))
    )

    stripe_data["trialStart"] = (
        stripe_data.get("trialStart")
        or iso_from_ts(getattr(route, "trial_start", None))
        or iso_from_ts(getattr(local_subscription, "trial_start", None))
    )

    stripe_data["trialEnd"] = (
        stripe_data.get("trialEnd")
        or iso_from_ts(getattr(route, "trial_end", None))
        or iso_from_ts(getattr(local_subscription, "trial_end", None))
    )

    if stripe_data.get("cancelAtPeriodEnd") is None:
        stripe_data["cancelAtPeriodEnd"] = bool(
            getattr(
                local_subscription,
                "cancel_at_period_end",
                False,
            )
        )

    return compact_dict(stripe_data)


# =========================================================
# LEARNING ROUTE
# =========================================================

def serialize_route_item(item: Any) -> Dict[str, Any]:
    id_interno = (
        getattr(item, "id_interno", None)
        or getattr(
            getattr(item, "certification", None),
            "id_interno",
            None,
        )
    )

    preview = compact_dict({
        "type": getattr(item, "preview_type", None),
        "url": getattr(item, "preview_url", None),
        "validatedAt": iso_from_ts(
            getattr(item, "preview_validated_at", None)
        ),
        "countryCode": getattr(
            item,
            "preview_country_code",
            None,
        ),
    })

    course = {
        "idInterno": id_interno,
        "order": getattr(item, "order", 1),
        "routeLevel": getattr(item, "route_level", 1),
        "title": getattr(item, "title", "") or "",
        "provider": getattr(item, "provider", "") or "",
        "language": getattr(item, "language", "") or "",
        "available": bool(
            getattr(item, "is_available", True)
        ),
    }

    if preview:
        course["preview"] = preview

    return compact_dict(course)


def serialize_legacy_recommendations(route) -> list:
    """
    Compatibilidad temporal mientras existen registros antiguos
    en recommended_certifications.
    """
    if route is None:
        return []

    recommendations = getattr(
        route,
        "recommended_certifications",
        None,
    ) or []

    result = []

    for index, item in enumerate(recommendations, start=1):
        if not isinstance(item, dict):
            continue

        id_interno = (
            item.get("idInterno")
            or item.get("id_interno")
            or item.get("internalId")
        )

        if not id_interno:
            continue

        result.append(
            compact_dict({
                "idInterno": str(id_interno),
                "order": item.get("order") or index,
                "routeLevel": item.get("routeLevel")
                or item.get("route_level")
                or 1,
                "title": item.get("title")
                or item.get("nombre")
                or "",
                "provider": item.get("provider")
                or item.get("source_provider")
                or "",
                "language": item.get("language")
                or item.get("lenguaje")
                or "",
            })
        )

    return result


def build_learning_route_snapshot(
    *,
    route=None,
    route_snapshot=None,
) -> Dict[str, Any]:
    snapshot = resolve_route_snapshot(
        route=route,
        route_snapshot=route_snapshot,
    )

    courses = []
    version = getattr(route, "route_version", 1) if route else 1
    mode = "SNAPSHOT"
    snapshot_id = None

    if snapshot is not None:
        version = getattr(snapshot, "version", version)
        mode = getattr(snapshot, "mode", "SNAPSHOT")
        snapshot_id = getattr(snapshot, "pk", None)

        manager = getattr(snapshot, "courses", None)

        if manager is not None:
            try:
                items = manager.select_related(
                    "certification"
                ).order_by(
                    "route_level",
                    "order",
                    "id",
                )

                courses = [
                    serialize_route_item(item)
                    for item in items
                ]
            except Exception:
                courses = []

    if not courses:
        courses = serialize_legacy_recommendations(route)

    return compact_dict({
        "version": int(version or 1),
        "mode": mode or "SNAPSHOT",
        "courses": courses,
        "metadata": {
            "leadId": str(route.pk)
            if route and getattr(route, "pk", None)
            else None,
            "snapshotId": str(snapshot_id)
            if snapshot_id
            else None,
        },
    })


# =========================================================
# EVENTO CANÓNICO
# =========================================================

def build_mx_access_payload(
    *,
    event_type: str,
    user=None,
    route=None,
    route_snapshot=None,
    stripe_event=None,
    stripe_object=None,
    event_id: Optional[str] = None,
    occurred_at: Optional[str] = None,
    extra_metadata: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    """
    Construye el evento canónico B2C para México.

    Puede utilizarse para:
    - eventos de Stripe;
    - aprovisionamiento inicial;
    - actualización de acceso;
    - actualización de ruta;
    - expiración o revocación.
    """
    stripe_event = stripe_event or {}
    stripe_object = stripe_object or {}

    stripe_event_id = stripe_event.get("id")
    stripe_created = stripe_event.get("created")

    occurred_at = (
        occurred_at
        or iso_from_ts(stripe_created)
        or now_iso()
    )

    if not event_id:
        if stripe_event_id:
            event_id = (
                f"{SOURCE_NAME}:{event_type}:{stripe_event_id}"
            )
        else:
            event_id = (
                f"{SOURCE_NAME}:{event_type}:{uuid.uuid4()}"
            )

    local_subscription = get_subscription_from_user(user)

    customer = build_customer_snapshot(
        user=user,
        route=route,
        stripe_object=stripe_object,
    )

    plan = build_plan_snapshot(
        route=route,
        local_subscription=local_subscription,
    )

    billing = build_billing_snapshot(
        event_type=event_type,
        stripe_object=stripe_object,
        route=route,
        local_subscription=local_subscription,
        occurred_at=occurred_at,
    )

    learning_route = build_learning_route_snapshot(
        route=route,
        route_snapshot=route_snapshot,
    )

    obj_metadata = stripe_object.get("metadata") or {}

    metadata = {
        "schemaVersion": DEFAULT_SCHEMA_VERSION,
        "traceId": stripe_event_id or event_id,
        "stripeEventId": stripe_event_id,
        "stripeEventType": (
            stripe_event.get("type")
            or event_type
            if stripe_event_id
            else None
        ),
        "leadId": (
            str(route.pk)
            if route and getattr(route, "pk", None)
            else None
        ),
        "routeVersion": learning_route.get("version"),
        "checkoutSessionId": (
            stripe_object.get("id")
            if (
                stripe_event.get("type")
                == "checkout.session.completed"
                or event_type == "checkout.session.completed"
            )
            else obj_metadata.get("checkout_session_id")
        ),
    }

    if extra_metadata:
        metadata.update(extra_metadata)

    payload = {
        "schemaVersion": DEFAULT_SCHEMA_VERSION,
        "eventId": event_id,
        "eventType": event_type,
        "occurredAt": occurred_at,
        "source": SOURCE_NAME,
        "customer": customer,
        "plan": plan,
        "billing": billing,
        "learningRoute": learning_route,
        "metadata": compact_dict(metadata),
    }

    payload = compact_dict(payload)

    # Para FREE se debe preservar explícitamente el null.
    if (
        str(
            payload.get("plan", {}).get("packageCode") or ""
        ).strip().upper()
        == "TOP_EDUCATION_FREE"
    ):
        payload.setdefault("plan", {})["billingPeriod"] = None

    return payload


# =========================================================
# COMPATIBILIDAD CON LA IMPLEMENTACIÓN ACTUAL
# =========================================================

def build_mx_payload_from_stripe_event(
    event,
    event_type,
    stripe_object,
    user=None,
    route=None,
    route_snapshot=None,
    extra_metadata=None,
):
    """
    Wrapper compatible con el código existente.

    Más adelante event_type debería ser un evento de negocio:
    - USER_ACCESS_PROVISION
    - USER_ACCESS_UPDATED
    - USER_LEARNING_ROUTE_UPDATED
    - USER_ACCESS_EXPIRED
    - USER_ACCESS_REVOKED

    Mientras actualizamos los webhooks, también acepta los nombres
    originales de eventos Stripe.
    """
    return build_mx_access_payload(
        stripe_event=event,
        stripe_object=stripe_object,
        event_type=event_type,
        user=user,
        route=route,
        route_snapshot=route_snapshot,
        extra_metadata=extra_metadata,
    )