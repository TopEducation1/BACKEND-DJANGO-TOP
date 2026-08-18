from __future__ import annotations

import uuid
from datetime import datetime, timedelta, timezone as dt_timezone
from decimal import Decimal
from typing import Any, Dict, Iterable, Mapping, Optional

from django.conf import settings
from django.utils import timezone


SOURCE_NAME = "colombia-b2c"
DEFAULT_SCHEMA_VERSION = "1.1"

FREE_PACKAGE_CODE = "TOP_EDUCATION_FREE"
FREE_TIER = "FREE"

# MX 1.1 acepta una o más experiencias Free elegibles.
# Colombia puede seguir mostrando 3 por decisión de producto,
# pero el builder no impone un máximo contractual de tres.
DEFAULT_FREE_COURSES = 3
MAX_FREE_COURSES = 200
MAX_FREE_PREVIEW_AGE_DAYS = 30
FREE_PREVIEW_TYPES = {"AUDIT", "COURSE_PREVIEW"}

SUPPORTED_PACKAGES = {
    "TOP_EDUCATION_FREE": {
        "tier": "FREE",
        "billingPeriod": None,
        "trialAllowed": False,
    },
    "TOP_EDUCATION_BASIC_MONTHLY": {
        "tier": "BASIC",
        "billingPeriod": "MONTHLY",
        "trialAllowed": True,
    },
    "TOP_EDUCATION_BASIC_ANNUAL": {
        "tier": "BASIC",
        "billingPeriod": "ANNUAL",
        "trialAllowed": True,
    },
    "TOP_EDUCATION_X_MONTHLY": {
        "tier": "X",
        "billingPeriod": "MONTHLY",
        "trialAllowed": True,
    },
    "TOP_EDUCATION_X_ANNUAL": {
        "tier": "X",
        "billingPeriod": "ANNUAL",
        "trialAllowed": True,
    },
    "TOP_EDUCATION_PLUS_MONTHLY": {
        "tier": "PLUS",
        "billingPeriod": "MONTHLY",
        "trialAllowed": True,
    },
    "TOP_EDUCATION_PLUS_ANNUAL": {
        "tier": "PLUS",
        "billingPeriod": "ANNUAL",
        "trialAllowed": True,
    },
}

UNSET = object()


# =========================================================
# UTILIDADES
# =========================================================

def iso_from_ts(value: Any) -> Optional[str]:
    """
    Convierte timestamps Unix o datetime a ISO 8601 UTC.
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

        return (
            dt.astimezone(dt_timezone.utc)
            .isoformat(timespec="milliseconds")
            .replace("+00:00", "Z")
        )

    try:
        timestamp = int(value)
    except (TypeError, ValueError):
        return None

    return (
        datetime.fromtimestamp(
            timestamp,
            tz=dt_timezone.utc,
        )
        .isoformat(timespec="milliseconds")
        .replace("+00:00", "Z")
    )


def now_iso() -> str:
    return (
        timezone.now()
        .astimezone(dt_timezone.utc)
        .isoformat(timespec="milliseconds")
        .replace("+00:00", "Z")
    )


def parse_iso_datetime(value: Any) -> Optional[datetime]:
    raw = str(value or "").strip()

    if not raw:
        return None

    try:
        if raw.endswith("Z"):
            raw = raw[:-1] + "+00:00"

        parsed = datetime.fromisoformat(raw)
    except (TypeError, ValueError):
        return None

    if parsed.tzinfo is None:
        parsed = parsed.replace(
            tzinfo=dt_timezone.utc
        )

    return parsed.astimezone(
        dt_timezone.utc
    )


def is_recent_free_preview(
    value: Any,
    *,
    max_age_days: int = MAX_FREE_PREVIEW_AGE_DAYS,
) -> bool:
    validated_at = parse_iso_datetime(value)

    if validated_at is None:
        return False

    age = datetime.now(
        dt_timezone.utc
    ) - validated_at

    return (
        timedelta(0)
        <= age
        <= timedelta(days=max_age_days)
    )


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


def normalize_upper(
    value: Any,
    default: Optional[str] = None,
) -> Optional[str]:
    normalized = str(value or "").strip().upper()
    return normalized or default


def safe_get_full_name(user: Any) -> str:
    if not user:
        return ""

    try:
        full_name = user.get_full_name()
    except Exception:
        full_name = ""

    if full_name:
        return str(full_name).strip()

    first_name = str(
        getattr(user, "first_name", "") or ""
    ).strip()

    last_name = str(
        getattr(user, "last_name", "") or ""
    ).strip()

    return f"{first_name} {last_name}".strip()


def compact_dict(value: Any) -> Any:
    """
    Elimina valores None recursivamente.

    Conserva False, 0, strings vacíos y listas vacías.
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


def get_first_dict_value(
    data: Mapping[str, Any],
    *keys: str,
) -> Any:
    for key in keys:
        value = data.get(key)

        if value not in (None, ""):
            return value

    return None


def mapping_or_empty(value: Any) -> Dict[str, Any]:
    return dict(value) if isinstance(value, Mapping) else {}


def get_price_id_from_subscription(
    subscription: Mapping[str, Any],
) -> Optional[str]:
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


def get_invoice_price_id(
    invoice: Mapping[str, Any],
) -> Optional[str]:
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
    """
    if not user:
        return None

    manager = getattr(user, "stripe_subscriptions", None)

    if manager is None:
        return None

    try:
        return manager.order_by(
            "-updated_at",
            "-id",
        ).first()
    except Exception:
        return None


def resolve_route_snapshot(
    route=None,
    route_snapshot=None,
):
    """
    Obtiene el snapshot explícito o el snapshot actual del Lead.
    """
    if route_snapshot is not None:
        return route_snapshot

    if route is None:
        return None

    snapshots = getattr(route, "route_snapshots", None)

    if snapshots is None:
        return None

    try:
        current = (
            snapshots
            .filter(is_current=True)
            .order_by("-version")
            .first()
        )

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
    obj = mapping_or_empty(stripe_object)
    customer_details = mapping_or_empty(
        obj.get("customer_details")
    )

    email = normalize_email(
        getattr(user, "email", None)
        or getattr(route, "email", None)
        or customer_details.get("email")
        or obj.get("customer_email")
        or obj.get("customer_email_address")
        or obj.get("receipt_email")
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

    address = mapping_or_empty(
        customer_details.get("address")
    )

    country = (
        getattr(route, "country", None)
        or address.get("country")
    )

    customer = {
        "userId": (
            str(user.pk)
            if user and getattr(user, "pk", None)
            else None
        ),
        "mxUserId": getattr(route, "mx_user_id", None),
        "email": email,
        "emailNormalized": email,
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

def infer_billing_period_from_interval(
    interval: Any,
) -> Optional[str]:
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
    package_code_override=UNSET,
    tier_override=UNSET,
    billing_period_override=UNSET,
    lifecycle_status_override=UNSET,
    access_status_override=UNSET,
    pending_action_override=UNSET,
) -> Dict[str, Any]:
    package_code = (
        package_code_override
        if package_code_override is not UNSET
        else (
            getattr(route, "package_code", None)
            or getattr(
                local_subscription,
                "package_code",
                None,
            )
            or FREE_PACKAGE_CODE
        )
    )

    tier = (
        tier_override
        if tier_override is not UNSET
        else (
            getattr(route, "tier", None)
            or getattr(local_subscription, "tier", None)
            or FREE_TIER
        )
    )

    if billing_period_override is not UNSET:
        billing_period = billing_period_override
    else:
        billing_period = (
            getattr(route, "billing_period", None)
            or getattr(
                local_subscription,
                "billing_period",
                None,
            )
            or infer_billing_period_from_interval(
                getattr(
                    local_subscription,
                    "interval",
                    None,
                )
            )
        )

    access_status = (
        access_status_override
        if access_status_override is not UNSET
        else (
            getattr(route, "access_status", None)
            or getattr(
                local_subscription,
                "access_status",
                None,
            )
            or "ALLOWED"
        )
    )

    lifecycle_status = (
        lifecycle_status_override
        if lifecycle_status_override is not UNSET
        else (
            getattr(route, "lifecycle_status", None)
            or getattr(
                local_subscription,
                "lifecycle_status",
                None,
            )
            or "FREE"
        )
    )

    pending_action = (
        pending_action_override
        if pending_action_override is not UNSET
        else (
            getattr(route, "pending_action", None)
            or getattr(
                local_subscription,
                "pending_action",
                None,
            )
            or "NONE"
        )
    )

    package_code = normalize_upper(
        package_code,
        FREE_PACKAGE_CODE,
    )

    tier = normalize_upper(tier, FREE_TIER)
    access_status = normalize_upper(
        access_status,
        "ALLOWED",
    )
    lifecycle_status = normalize_upper(
        lifecycle_status,
        "FREE",
    )
    pending_action = normalize_upper(
        pending_action,
        "NONE",
    )

    if billing_period is not None:
        billing_period = normalize_upper(billing_period)

    expected = SUPPORTED_PACKAGES.get(package_code)

    if expected is None:
        raise ValueError(f"unsupported_package_code:{package_code}")

    # El contrato 1.1 exige que packageCode, tier y billingPeriod
    # describan exactamente el mismo paquete. Se canonizan aquí
    # para impedir combinaciones inconsistentes provenientes de
    # registros legacy o de Stripe.
    tier = expected["tier"]
    billing_period = expected["billingPeriod"]

    trial_start = iso_from_ts(
        getattr(route, "trial_start", None)
        or getattr(local_subscription, "trial_start", None)
    )
    trial_end = iso_from_ts(
        getattr(route, "trial_end", None)
        or getattr(local_subscription, "trial_end", None)
    )

    is_trial = bool(
        expected["trialAllowed"]
        and lifecycle_status == "TRIALING"
        and trial_end
    )

    if not expected["trialAllowed"]:
        trial_start = None
        trial_end = None
        is_trial = False

    trial_days = 0
    if is_trial and trial_start and trial_end:
        try:
            start_dt = datetime.fromisoformat(
                trial_start.replace("Z", "+00:00")
            )
            end_dt = datetime.fromisoformat(
                trial_end.replace("Z", "+00:00")
            )
            duration_seconds = max(
                0,
                (end_dt - start_dt).total_seconds(),
            )

            trial_days = max(
                0,
                int(
                    (duration_seconds + 86399)
                    // 86400
                ),
            )
        except (TypeError, ValueError):
            trial_days = 0

    return {
        "packageCode": package_code,
        "tier": tier,
        "billingPeriod": billing_period,
        "accessStatus": access_status,
        "lifecycleStatus": lifecycle_status,
        "pendingAction": pending_action,
        "trial": {
            "isTrial": is_trial,
            "trialStart": trial_start,
            "trialEnd": trial_end,
            "trialDays": trial_days,
        },
    }


# =========================================================
# BILLING / STRIPE
# =========================================================

def extract_stripe_billing_data(
    *,
    stripe_event_type: str,
    stripe_object: Optional[Dict[str, Any]],
    occurred_at: str,
) -> Dict[str, Any]:
    obj = mapping_or_empty(stripe_object)
    metadata = mapping_or_empty(obj.get("metadata"))

    stripe_event_type = str(
        stripe_event_type or ""
    ).strip()

    stripe_customer_id = obj.get("customer")
    stripe_subscription_id = obj.get("subscription")

    price_id = None
    current_period_start = None
    current_period_end = None
    paid_at = None
    cancel_at_period_end = None

    amount_cents = get_first_dict_value(
        obj,
        "amount_paid",
        "amount_total",
        "amount_due",
        "amount",
    )

    currency = normalize_currency(obj.get("currency"))

    if stripe_event_type.startswith("invoice."):
        stripe_subscription_id = obj.get("subscription")
        price_id = get_invoice_price_id(obj)

        current_period_start = iso_from_ts(
            obj.get("period_start")
        )
        current_period_end = iso_from_ts(
            obj.get("period_end")
        )

        if stripe_event_type in {
            "invoice.paid",
            "invoice.payment_succeeded",
        }:
            paid_at = occurred_at

        status_transitions = mapping_or_empty(
            obj.get("status_transitions")
        )

        paid_at = (
            iso_from_ts(
                status_transitions.get("paid_at")
            )
            or paid_at
        )

    elif stripe_event_type.startswith(
        "customer.subscription."
    ):
        stripe_subscription_id = obj.get("id")
        price_id = get_price_id_from_subscription(obj)

        current_period_start = iso_from_ts(
            obj.get("current_period_start")
        )
        current_period_end = iso_from_ts(
            obj.get("current_period_end")
        )

        trial_start = iso_from_ts(
            obj.get("trial_start")
        )
        trial_end = iso_from_ts(
            obj.get("trial_end")
        )

        cancel_at_period_end = bool(
            obj.get("cancel_at_period_end", False)
        )

    elif stripe_event_type == "checkout.session.completed":
        stripe_subscription_id = obj.get("subscription")

        price_id = (
            metadata.get("price_id")
            or metadata.get("stripe_price_id")
        )

    elif stripe_event_type.startswith("payment_intent."):
        stripe_customer_id = obj.get("customer")

        paid_at = (
            occurred_at
            if stripe_event_type
            == "payment_intent.succeeded"
            else None
        )

    return compact_dict({
        "stripeCustomerId": stripe_customer_id,
        "stripeSubscriptionId": stripe_subscription_id,
        "stripePriceId": price_id,
        "currency": currency,
        "amountCents": normalize_amount_cents(
            amount_cents
        ),
        "paidAt": paid_at,
        "currentPeriodStart": current_period_start,
        "currentPeriodEnd": current_period_end,
        "cancelAtPeriodEnd": cancel_at_period_end,
    })


def build_billing_snapshot(
    *,
    stripe_event_type: str,
    stripe_object=None,
    route=None,
    local_subscription=None,
    occurred_at: str,
) -> Dict[str, Any]:
    stripe_data = extract_stripe_billing_data(
        stripe_event_type=stripe_event_type,
        stripe_object=stripe_object,
        occurred_at=occurred_at,
    )

    stripe_data["stripeCustomerId"] = (
        stripe_data.get("stripeCustomerId")
        or getattr(route, "stripe_customer_id", None)
        or getattr(
            local_subscription,
            "stripe_customer_id",
            None,
        )
    )

    stripe_data["stripeSubscriptionId"] = (
        stripe_data.get("stripeSubscriptionId")
        or getattr(
            route,
            "stripe_subscription_id",
            None,
        )
        or getattr(
            local_subscription,
            "stripe_subscription_id",
            None,
        )
    )

    stripe_data["stripePriceId"] = (
        stripe_data.get("stripePriceId")
        or getattr(local_subscription, "price_id", None)
    )

    stripe_data["currentPeriodStart"] = (
        stripe_data.get("currentPeriodStart")
        or iso_from_ts(
            getattr(
                local_subscription,
                "current_period_start",
                None,
            )
        )
    )

    stripe_data["currentPeriodEnd"] = (
        stripe_data.get("currentPeriodEnd")
        or iso_from_ts(
            getattr(
                local_subscription,
                "current_period_end",
                None,
            )
        )
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
    certification = getattr(
        item,
        "certification",
        None,
    )

    id_interno = (
        getattr(item, "id_interno", None)
        or getattr(certification, "id_interno", None)
    )

    preview = compact_dict({
        "type": normalize_upper(
            getattr(item, "preview_type", None)
        ),
        "url": getattr(item, "preview_url", None),
        "validatedAt": iso_from_ts(
            getattr(
                item,
                "preview_validated_at",
                None,
            )
        ),
        "countryCode": getattr(
            item,
            "preview_country_code",
            None,
        ),
    })

    course = {
        "idInterno": (
            str(id_interno)
            if id_interno not in (None, "")
            else None
        ),
        "order": getattr(item, "order", 1),
        "routeLevel": getattr(
            item,
            "route_level",
            1,
        ),
        "title": (
            getattr(item, "title", None)
            or getattr(certification, "nombre", None)
            or ""
        ),
        "provider": (
            getattr(item, "provider", None)
            or getattr(
                certification,
                "source_provider",
                None,
            )
            or ""
        ),
        "language": (
            getattr(item, "language", None)
            or getattr(
                certification,
                "lenguaje_certificacion",
                None,
            )
            or ""
        ),
        "available": bool(
            getattr(item, "is_available", True)
        ),
    }

    if preview:
        course["preview"] = preview

    return compact_dict(course)


def serialize_legacy_recommendations(route) -> list:
    """
    Compatibilidad temporal para registros históricos.
    No determina por sí sola la elegibilidad Free.
    """
    if route is None:
        return []

    recommendations = getattr(
        route,
        "recommended_certifications",
        None,
    ) or []

    result = []

    for index, item in enumerate(
        recommendations,
        start=1,
    ):
        if not isinstance(item, dict):
            continue

        id_interno = (
            item.get("idInterno")
            or item.get("id_interno")
            or item.get("internalId")
        )

        if not id_interno:
            continue

        preview_data = mapping_or_empty(
            item.get("preview")
        )

        preview_type = (
            preview_data.get("type")
            or item.get("previewType")
            or item.get("preview_type")
        )

        preview_url = (
            preview_data.get("url")
            or item.get("previewUrl")
            or item.get("preview_url")
        )

        result.append(
            compact_dict({
                "idInterno": str(id_interno),
                "order": item.get("order") or index,
                "routeLevel": (
                    item.get("routeLevel")
                    or item.get("route_level")
                    or 1
                ),
                "title": (
                    item.get("title")
                    or item.get("nombre")
                    or ""
                ),
                "provider": (
                    item.get("provider")
                    or item.get("source_provider")
                    or ""
                ),
                "language": (
                    item.get("language")
                    or item.get("lenguaje")
                    or ""
                ),
                "preview": compact_dict({
                    "type": normalize_upper(
                        preview_type
                    ),
                    "url": preview_url,
                    "validatedAt": (
                        preview_data.get("validatedAt")
                        or item.get(
                            "preview_validated_at"
                        )
                    ),
                    "countryCode": (
                        preview_data.get("countryCode")
                        or item.get(
                            "preview_country_code"
                        )
                    ),
                }),
            })
        )

    return result


def serialize_free_preview_item(
    item: Mapping[str, Any],
    *,
    order: int,
) -> Optional[Dict[str, Any]]:
    """
    Serializa únicamente elementos provenientes del catálogo Free.

    idInterno se conserva exactamente como se recibe.
    """
    if not isinstance(item, Mapping):
        return None

    id_interno = item.get("idInterno")

    if id_interno in (None, ""):
        return None

    preview = mapping_or_empty(item.get("preview"))
    preview_type = normalize_upper(
        preview.get("type")
    )
    preview_url = preview.get("url")

    # Un registro Free debe incluir una experiencia aprobada.
    if not preview_type or not preview_url:
        return None

    return compact_dict({
        "idInterno": str(id_interno),
        "title": item.get("title") or "",
        "provider": item.get("provider") or "",
        "language": item.get("language") or "",
        "order": order,
        "routeLevel": item.get("routeLevel") or 1,
        "preview": {
            "type": preview_type,
            "url": preview_url,
            "validatedAt": preview.get(
                "validatedAt"
            ),
            "countryCode": (
                preview.get("countryCode")
                or "CO"
            ),
        },
    })


def normalize_free_preview_courses(
    items: Optional[Iterable[Mapping[str, Any]]],
    *,
    limit: Optional[int] = None,
) -> list:
    """
    Elimina duplicados y conserva experiencias Free elegibles.

    MX 1.1 acepta una o más experiencias. El límite opcional existe
    solamente para decisiones de producto de Colombia y nunca se
    interpreta como una restricción contractual de tres cursos.
    """
    result = []
    used_ids = set()

    normalized_limit = None

    if limit is not None:
        try:
            normalized_limit = int(limit)
        except (TypeError, ValueError):
            normalized_limit = None

        if normalized_limit is not None:
            normalized_limit = max(
                1,
                min(
                    normalized_limit,
                    MAX_FREE_COURSES,
                ),
            )

    for item in items or []:
        serialized = serialize_free_preview_item(
            item,
            order=len(result) + 1,
        )

        if not serialized:
            continue

        id_interno = serialized["idInterno"]

        if id_interno in used_ids:
            continue

        used_ids.add(id_interno)
        result.append(serialized)

        if (
            normalized_limit is not None
            and len(result) >= normalized_limit
        ):
            break

    return result


def get_free_courses_from_route(route) -> list:
    """
    Busca una selección Free previamente persistida en la ruta.

    Se aceptan varios nombres durante la migración, pero el dato debe
    haber sido obtenido originalmente del endpoint Free Tier.
    """
    if route is None:
        return []

    for attr_name in (
        "free_preview_courses",
        "free_courses",
        "free_catalog_selection",
    ):
        value = getattr(route, attr_name, None)

        if isinstance(value, list):
            return normalize_free_preview_courses(value)

    return []


def serialize_snapshot_courses(snapshot: Any) -> list:
    """Serializa, en orden estable, los cursos persistidos en un snapshot."""
    if snapshot is None:
        return []

    manager = getattr(snapshot, "courses", None)
    if manager is None:
        return []

    try:
        items = (
            manager
            .select_related("certification")
            .order_by("route_level", "order", "id")
        )
        return [serialize_route_item(item) for item in items]
    except Exception:
        return []


def build_learning_route_snapshot(
    *,
    route=None,
    route_snapshot=None,
    package_code: Optional[str] = None,
    free_courses: Optional[
        Iterable[Mapping[str, Any]]
    ] = None,
    strict_free_courses: bool = False,
) -> Dict[str, Any]:
    snapshot = resolve_route_snapshot(
        route=route,
        route_snapshot=route_snapshot,
    )

    version = (
        getattr(route, "route_version", 1)
        if route
        else 1
    )

    mode = "SNAPSHOT"
    snapshot_id = None
    courses = []

    package_code = normalize_upper(
        package_code,
        FREE_PACKAGE_CODE,
    )

    # FREE usa la selección persistida que originalmente provino
    # del catálogo Free Tier. free_courses permite un override
    # explícito; de lo contrario se reutiliza el snapshot actual.
    # MX 1.1 acepta una o más experiencias elegibles.
    if package_code == FREE_PACKAGE_CODE:
        if snapshot is not None:
            version = getattr(snapshot, "version", version)
            mode = getattr(snapshot, "mode", "SNAPSHOT")
            snapshot_id = getattr(snapshot, "pk", None)

        selected_free_courses = (
            list(free_courses)
            if free_courses is not None
            else serialize_snapshot_courses(snapshot)
        )

        if not selected_free_courses:
            selected_free_courses = get_free_courses_from_route(route)

        courses = normalize_free_preview_courses(
            selected_free_courses
        )

        if strict_free_courses and len(courses) < 1:
            raise ValueError(
                "free_plan_requires_at_least_one_course"
            )

    else:
        if snapshot is not None:
            version = getattr(
                snapshot,
                "version",
                version,
            )
            mode = getattr(
                snapshot,
                "mode",
                "SNAPSHOT",
            )
            snapshot_id = getattr(snapshot, "pk", None)

            courses = serialize_snapshot_courses(snapshot)

        if not courses:
            courses = serialize_legacy_recommendations(
                route
            )

    return compact_dict({
        "version": int(version or 1),
        "mode": normalize_upper(
            mode,
            "SNAPSHOT",
        ),
        "courses": courses,
        "metadata": {
            "leadId": (
                str(route.pk)
                if route
                and getattr(route, "pk", None)
                else None
            ),
            "snapshotId": (
                str(snapshot_id)
                if snapshot_id
                else None
            ),
        },
    })


def build_redirects_snapshot() -> Dict[str, str]:
    """URLs de Colombia exigidas por el contrato B2C 1.1."""
    account_url = str(
        getattr(
            settings,
            "B2C_COLOMBIA_ACCOUNT_URL",
            "https://top.education/account",
        )
    ).strip()

    subscription_url = str(
        getattr(
            settings,
            "B2C_SUBSCRIPTION_MANAGEMENT_URL",
            f"{account_url}?tab=license",
        )
    ).strip()

    return {
        "subscriptionManagementUrl": subscription_url,
        "colombiaAccountUrl": account_url,
    }


def validate_contract_payload(payload: Mapping[str, Any]) -> None:
    """Validaciones locales de las reglas obligatorias del contrato 1.1."""
    if payload.get("schemaVersion") != DEFAULT_SCHEMA_VERSION:
        raise ValueError("invalid_schema_version")

    customer = mapping_or_empty(payload.get("customer"))
    email = normalize_email(customer.get("email"))
    email_normalized = normalize_email(customer.get("emailNormalized"))
    if not email or email != email_normalized:
        raise ValueError("customer_email_normalization_mismatch")

    plan = mapping_or_empty(payload.get("plan"))
    package_code = normalize_upper(plan.get("packageCode"))
    expected = SUPPORTED_PACKAGES.get(package_code)
    if expected is None:
        raise ValueError(f"unsupported_package_code:{package_code}")
    if normalize_upper(plan.get("tier")) != expected["tier"]:
        raise ValueError("package_tier_mismatch")
    if plan.get("billingPeriod") != expected["billingPeriod"]:
        raise ValueError("package_billing_period_mismatch")

    trial = mapping_or_empty(plan.get("trial"))

    if (
        not expected["trialAllowed"]
        and bool(trial.get("isTrial"))
    ):
        raise ValueError(
            "trial_not_allowed_for_package"
        )

    if (
        normalize_upper(
            plan.get("lifecycleStatus")
        ) == "TRIALING"
    ):
        if not expected["trialAllowed"]:
            raise ValueError(
                "trialing_not_allowed_for_package"
            )

        if not bool(trial.get("isTrial")):
            raise ValueError(
                "trialing_requires_trial_block"
            )

        if (
            not trial.get("trialStart")
            or not trial.get("trialEnd")
        ):
            raise ValueError(
                "trial_dates_required"
            )

        if int(trial.get("trialDays") or 0) != 7:
            raise ValueError(
                "trial_days_must_be_seven"
            )

    learning_route = mapping_or_empty(payload.get("learningRoute"))
    if normalize_upper(learning_route.get("mode")) != "SNAPSHOT":
        raise ValueError("learning_route_mode_must_be_snapshot")
    if int(learning_route.get("version") or 0) < 1:
        raise ValueError("learning_route_version_must_start_at_one")

    courses = learning_route.get("courses") or []
    if not isinstance(courses, list):
        raise ValueError("learning_route_courses_must_be_list")

    internal_ids = [
        str(item.get("idInterno") or "")
        for item in courses
        if isinstance(item, Mapping)
    ]
    if any(not item for item in internal_ids):
        raise ValueError("course_id_interno_required")
    if len(internal_ids) != len(set(internal_ids)):
        raise ValueError("duplicate_course_id_interno")
    if package_code == FREE_PACKAGE_CODE:
        if len(courses) < 1:
            raise ValueError(
                "free_plan_requires_at_least_one_course"
            )

        for item in courses:
            if not isinstance(item, Mapping):
                raise ValueError(
                    "free_course_must_be_object"
                )

            preview = mapping_or_empty(
                item.get("preview")
            )

            preview_type = normalize_upper(
                preview.get("type")
            )

            if (
                preview_type
                not in FREE_PREVIEW_TYPES
            ):
                raise ValueError(
                    "invalid_free_preview_type"
                )

            if not preview.get("url"):
                raise ValueError(
                    "free_preview_url_required"
                )

            if not is_recent_free_preview(
                preview.get("validatedAt")
            ):
                raise ValueError(
                    "free_preview_validation_expired"
                )

            country_code = normalize_upper(
                preview.get("countryCode")
            )

            if country_code != "CO":
                raise ValueError(
                    "free_preview_country_code_must_be_co"
                )

    billing = mapping_or_empty(
        payload.get("billing")
    )

    if "periodEnd" in billing:
        raise ValueError(
            "billing_period_end_is_not_supported"
        )

    if (
        "trialStart" in billing
        or "trialEnd" in billing
    ):
        raise ValueError(
            "billing_trial_fields_are_not_supported"
        )

    redirects = mapping_or_empty(payload.get("redirects"))
    if not redirects.get("subscriptionManagementUrl"):
        raise ValueError("subscription_management_url_required")
    if not redirects.get("colombiaAccountUrl"):
        raise ValueError("colombia_account_url_required")


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
    extra_metadata: Optional[
        Dict[str, Any]
    ] = None,
    package_code_override=UNSET,
    tier_override=UNSET,
    billing_period_override=UNSET,
    lifecycle_status_override=UNSET,
    access_status_override=UNSET,
    pending_action_override=UNSET,
    free_courses: Optional[
        Iterable[Mapping[str, Any]]
    ] = None,
    strict_free_courses: bool = False,
) -> Dict[str, Any]:
    """
    Construye el evento canónico B2C v1.1 para México.
    """
    stripe_event = mapping_or_empty(stripe_event)
    stripe_object = mapping_or_empty(stripe_object)

    event_type = str(event_type or "").strip().upper()

    if not event_type:
        raise ValueError("event_type_is_required")

    stripe_event_id = stripe_event.get("id")
    stripe_event_type = str(
        stripe_event.get("type") or ""
    ).strip()

    stripe_created = stripe_event.get("created")

    occurred_at = (
        occurred_at
        or iso_from_ts(stripe_created)
        or now_iso()
    )

    if not event_id:
        if stripe_event_id:
            event_id = (
                f"{SOURCE_NAME}:"
                f"{event_type}:"
                f"{stripe_event_id}"
            )
        else:
            event_id = (
                f"{SOURCE_NAME}:"
                f"{event_type}:"
                f"{uuid.uuid4()}"
            )

    local_subscription = get_subscription_from_user(
        user
    )

    customer = build_customer_snapshot(
        user=user,
        route=route,
        stripe_object=stripe_object,
    )

    plan = build_plan_snapshot(
        route=route,
        local_subscription=local_subscription,
        package_code_override=package_code_override,
        tier_override=tier_override,
        billing_period_override=(
            billing_period_override
        ),
        lifecycle_status_override=(
            lifecycle_status_override
        ),
        access_status_override=(
            access_status_override
        ),
        pending_action_override=(
            pending_action_override
        ),
    )

    billing = build_billing_snapshot(
        stripe_event_type=stripe_event_type,
        stripe_object=stripe_object,
        route=route,
        local_subscription=local_subscription,
        occurred_at=occurred_at,
    )

    # Trazabilidad comercial canónica del contrato. El bloque plan, no
    # billing, determina el acceso en México.
    billing["source"] = "COLOMBIA"
    billing["status"] = (
        "free"
        if plan.get("packageCode") == FREE_PACKAGE_CODE
        else str(
            getattr(local_subscription, "status", None)
            or plan.get("lifecycleStatus")
            or "active"
        ).strip().lower()
    )
    learning_route = build_learning_route_snapshot(
        route=route,
        route_snapshot=route_snapshot,
        package_code=plan.get("packageCode"),
        free_courses=free_courses,
        strict_free_courses=strict_free_courses,
    )

    obj_metadata = mapping_or_empty(
        stripe_object.get("metadata")
    )

    metadata = {
        "schemaVersion": DEFAULT_SCHEMA_VERSION,
        "traceId": stripe_event_id or event_id,
        "stripeEventId": stripe_event_id,
        "stripeEventType": stripe_event_type or None,
        "leadId": (
            str(route.pk)
            if route and getattr(route, "pk", None)
            else None
        ),
        "routeVersion": learning_route.get(
            "version"
        ),
        "checkoutSessionId": (
            stripe_object.get("id")
            if stripe_event_type
            == "checkout.session.completed"
            else obj_metadata.get(
                "checkout_session_id"
            )
        ),
    }

    if extra_metadata:
        metadata.update(extra_metadata)

    payload = {
        "schemaVersion": DEFAULT_SCHEMA_VERSION,
        "eventId": str(event_id),
        "eventType": event_type,
        "traceId": stripe_event_id or str(event_id),
        "occurredAt": occurred_at,
        "source": SOURCE_NAME,
        "customer": customer,
        "plan": plan,
        "billing": billing,
        "learningRoute": learning_route,
        "redirects": build_redirects_snapshot(),
        "metadata": compact_dict(metadata),
    }

    payload = compact_dict(payload)

    # compact_dict elimina None, pero el contrato exige varios null
    # explícitos. Se restauran después de compactar.
    payload.setdefault("plan", {})["billingPeriod"] = (
        SUPPORTED_PACKAGES[
            payload["plan"]["packageCode"]
        ]["billingPeriod"]
    )

    trial = payload.setdefault("plan", {}).setdefault("trial", {})
    if not trial.get("isTrial"):
        trial["isTrial"] = False
        trial["trialStart"] = None
        trial["trialEnd"] = None
        trial["trialDays"] = 0

    if payload["plan"]["packageCode"] == FREE_PACKAGE_CODE:
        payload.setdefault("billing", {})["currentPeriodEnd"] = None

    validate_contract_payload(payload)
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
    package_code_override=UNSET,
    tier_override=UNSET,
    billing_period_override=UNSET,
    lifecycle_status_override=UNSET,
    access_status_override=UNSET,
    pending_action_override=UNSET,
    free_courses=None,
    strict_free_courses=False,
):
    """
    Wrapper compatible con el código existente.

    También lee temporalmente `_colombiaMxState` agregado por la vista,
    hasta que el webhook pase los overrides como argumentos explícitos.
    """
    stripe_object = mapping_or_empty(stripe_object)

    injected_state = mapping_or_empty(
        stripe_object.get("_colombiaMxState")
    )

    if (
        lifecycle_status_override is UNSET
        and injected_state.get("lifecycleStatus")
        is not None
    ):
        lifecycle_status_override = (
            injected_state["lifecycleStatus"]
        )

    if (
        access_status_override is UNSET
        and injected_state.get("accessStatus")
        is not None
    ):
        access_status_override = (
            injected_state["accessStatus"]
        )

    if (
        pending_action_override is UNSET
        and injected_state.get("pendingAction")
        is not None
    ):
        pending_action_override = (
            injected_state["pendingAction"]
        )

    if (
        package_code_override is UNSET
        and injected_state.get("packageCode")
        is not None
    ):
        package_code_override = (
            injected_state["packageCode"]
        )

    if (
        tier_override is UNSET
        and injected_state.get("tier")
        is not None
    ):
        tier_override = injected_state["tier"]

    if (
        billing_period_override is UNSET
        and "billingPeriod" in injected_state
    ):
        billing_period_override = (
            injected_state.get("billingPeriod")
        )

    return build_mx_access_payload(
        stripe_event=event,
        stripe_object=stripe_object,
        event_type=event_type,
        user=user,
        route=route,
        route_snapshot=route_snapshot,
        extra_metadata=extra_metadata,
        package_code_override=(
            package_code_override
        ),
        tier_override=tier_override,
        billing_period_override=(
            billing_period_override
        ),
        lifecycle_status_override=(
            lifecycle_status_override
        ),
        access_status_override=(
            access_status_override
        ),
        pending_action_override=(
            pending_action_override
        ),
        free_courses=free_courses,
        strict_free_courses=strict_free_courses,
    )