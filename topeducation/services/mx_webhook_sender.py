import hashlib
import hmac
import json
from datetime import timedelta
from email.utils import parsedate_to_datetime
from typing import Any, Dict, Optional

import requests

from django.conf import settings
from django.db import IntegrityError, transaction
from django.utils import timezone

from topeducation.models import MxAccessEventLog


SUCCESS_MX_STATUSES = {
    "APPLIED",
    "DUPLICATE",
    "READY",
}

PENDING_MX_STATUSES = {
    "ACCEPTED",
    "PENDING",
    "PROCESSING",
    "QUEUED",
}

RETRYABLE_HTTP_STATUSES = {
    408,
    425,
    429,
    500,
    502,
    503,
    504,
}


# =========================================================
# SERIALIZACIÓN Y FIRMA
# =========================================================

def json_dumps(payload: Dict[str, Any]) -> str:
    """
    Serialización determinista.

    La misma cadena debe utilizarse:
    - para calcular el HMAC;
    - para enviarse en el body;
    - para calcular payload_hash.
    """
    return json.dumps(
        payload,
        separators=(",", ":"),
        ensure_ascii=False,
        sort_keys=True,
    )


def payload_sha256(raw_body: str) -> str:
    return hashlib.sha256(
        raw_body.encode("utf-8")
    ).hexdigest()


def build_mx_headers(
    raw_body: str,
    event_id: str,
    occurred_at: str,
) -> Dict[str, str]:
    secret = str(
        getattr(
            settings,
            "MX_B2C_ACCESS_EVENT_HMAC_SECRET",
            "",
        )
        or ""
    ).strip()

    if not secret:
        raise RuntimeError(
            "No está configurado "
            "MX_B2C_ACCESS_EVENT_HMAC_SECRET."
        )

    signature = hmac.new(
        secret.encode("utf-8"),
        raw_body.encode("utf-8"),
        hashlib.sha256,
    ).hexdigest()

    return {
        "Content-Type": "application/json; charset=utf-8",
        "Accept": "application/json",
        "X-Top-Signature": f"hmac-sha256={signature}",
        "X-Top-Timestamp": occurred_at,
        "X-Event-Id": event_id,
        "User-Agent": "TopEducation-Colombia-B2C/1.1",
    }


# =========================================================
# RESPUESTAS DE MÉXICO
# =========================================================

def response_value(
    response_json: Dict[str, Any],
    *keys: str,
) -> Any:
    """
    Busca el valor tanto en la raíz como dentro de data/result.
    """
    containers = [
        response_json,
        response_json.get("data") or {},
        response_json.get("result") or {},
    ]

    for container in containers:
        if not isinstance(container, dict):
            continue

        for key in keys:
            value = container.get(key)

            if value not in (None, ""):
                return value

    return None


def normalize_mx_status(
    response_json: Dict[str, Any],
    http_status: int,
) -> Optional[str]:
    status = response_value(
        response_json,
        "status",
        "mxStatus",
        "resultStatus",
    )

    if status:
        return str(status).strip().upper()

    if 200 <= http_status < 300:
        return "APPLIED"

    return None


def is_retryable_http_status(http_status: int) -> bool:
    return (
        http_status in RETRYABLE_HTTP_STATUSES
        or 500 <= http_status <= 599
    )


def parse_retry_after(response) -> Optional[timezone.datetime]:
    value = response.headers.get("Retry-After")

    if not value:
        return None

    try:
        seconds = max(0, int(value))
        return timezone.now() + timedelta(seconds=seconds)
    except (TypeError, ValueError):
        pass

    try:
        parsed = parsedate_to_datetime(value)

        if timezone.is_naive(parsed):
            parsed = timezone.make_aware(
                parsed,
                timezone.get_current_timezone(),
            )

        return parsed
    except Exception:
        return None


def calculate_next_retry(
    attempts: int,
) -> timezone.datetime:
    """
    Backoff controlado:

    intento 1: 1 minuto
    intento 2: 5 minutos
    intento 3: 15 minutos
    intento 4: 60 minutos
    intentos posteriores: 6 horas
    """
    delays = {
        1: 1,
        2: 5,
        3: 15,
        4: 60,
    }

    minutes = delays.get(attempts, 360)

    return timezone.now() + timedelta(minutes=minutes)


def extract_response_data(
    response_json: Dict[str, Any],
    http_status: int,
) -> Dict[str, Any]:
    return {
        "mx_status": normalize_mx_status(
            response_json,
            http_status,
        ),
        "mx_user_id": response_value(
            response_json,
            "mxUserId",
            "userId",
            "id",
        ),
        "magic_link": response_value(
            response_json,
            "magicLink",
            "magic_link",
        ),
        "entitlement_status": response_value(
            response_json,
            "entitlementStatus",
            "entitlement_status",
        ),
        "route_version": response_value(
            response_json,
            "routeVersion",
            "route_version",
        ),
    }


# =========================================================
# LOG
# =========================================================

def get_payload_metadata(payload: Dict[str, Any]) -> Dict[str, Any]:
    metadata = payload.get("metadata") or {}

    if not isinstance(metadata, dict):
        return {}

    return metadata


def get_stripe_event_id(payload: Dict[str, Any]) -> Optional[str]:
    metadata = get_payload_metadata(payload)

    stripe_event_id = metadata.get("stripeEventId")

    if stripe_event_id:
        return str(stripe_event_id)

    trace_id = metadata.get("traceId")

    if trace_id and str(trace_id).startswith("evt_"):
        return str(trace_id)

    return None


def get_route_version(payload: Dict[str, Any]) -> Optional[int]:
    learning_route = payload.get("learningRoute") or {}

    value = learning_route.get("version")

    if value is None:
        value = get_payload_metadata(payload).get("routeVersion")

    try:
        return int(value) if value is not None else None
    except (TypeError, ValueError):
        return None


def resolve_route_snapshot(route=None, route_snapshot=None):
    if route_snapshot is not None:
        return route_snapshot

    if route is None:
        return None

    manager = getattr(route, "route_snapshots", None)

    if manager is None:
        return None

    try:
        current = manager.filter(
            is_current=True
        ).order_by(
            "-version"
        ).first()

        if current:
            return current

        return manager.order_by("-version").first()
    except Exception:
        return None


def create_or_get_log(
    *,
    payload: Dict[str, Any],
    raw_body: str,
    user=None,
    route=None,
    route_snapshot=None,
):
    event_id = str(payload["eventId"])
    event_type = str(payload["eventType"])

    resolved_snapshot = resolve_route_snapshot(
        route=route,
        route_snapshot=route_snapshot,
    )

    defaults = {
        "schema_version": str(
            get_payload_metadata(payload).get(
                "schemaVersion",
                "1.1",
            )
        ),
        "user": user,
        "learning_route": route,
        "route_snapshot": resolved_snapshot,
        "route_version": get_route_version(payload),
        "stripe_event_id": get_stripe_event_id(payload),
        "event_type": event_type,
        "event_source": str(
            payload.get("source")
            or "colombia-b2c"
        ),
        "payload_json": payload,
        "raw_body": raw_body,
        "payload_hash": payload_sha256(raw_body),
        "send_status": "pending",
        "is_retryable": False,
        "attempts": 0,
    }

    try:
        with transaction.atomic():
            log, created = MxAccessEventLog.objects.get_or_create(
                event_id=event_id,
                defaults=defaults,
            )

            return log, created

    except IntegrityError:
        log = MxAccessEventLog.objects.get(
            event_id=event_id
        )

        return log, False


def refresh_existing_log(
    *,
    log,
    payload: Dict[str, Any],
    raw_body: str,
    user=None,
    route=None,
    route_snapshot=None,
):
    """
    Actualiza el snapshot del log si el evento todavía no fue aceptado.

    Un evento ya enviado no debe modificarse.
    """
    if log.send_status == "sent":
        return

    resolved_snapshot = resolve_route_snapshot(
        route=route,
        route_snapshot=route_snapshot,
    )

    log.user = user or log.user
    log.learning_route = route or log.learning_route
    log.route_snapshot = (
        resolved_snapshot or log.route_snapshot
    )
    log.route_version = (
        get_route_version(payload)
        or log.route_version
    )
    log.event_type = payload["eventType"]
    log.event_source = (
        payload.get("source")
        or "colombia-b2c"
    )
    log.payload_json = payload
    log.raw_body = raw_body
    log.payload_hash = payload_sha256(raw_body)

    stripe_event_id = get_stripe_event_id(payload)

    if stripe_event_id and not log.stripe_event_id:
        log.stripe_event_id = stripe_event_id

    log.save(
        update_fields=[
            "user",
            "learning_route",
            "route_snapshot",
            "route_version",
            "event_type",
            "event_source",
            "payload_json",
            "raw_body",
            "payload_hash",
            "stripe_event_id",
            "updated_at",
        ]
    )


# =========================================================
# ACTUALIZACIÓN DEL LEAD
# =========================================================

def update_route_with_mx_response(
    *,
    route,
    event_id: str,
    mx_status: Optional[str],
    mx_user_id: Optional[str],
    magic_link: Optional[str],
    entitlement_status: Optional[str],
    route_version: Optional[Any],
    response_json: Dict[str, Any],
):
    if route is None:
        return

    update_fields = []

    route.mx_event_id = event_id
    update_fields.append("mx_event_id")

    if mx_status:
        route.mx_status = mx_status
        update_fields.append("mx_status")

    if mx_user_id:
        route.mx_user_id = str(mx_user_id)
        update_fields.append("mx_user_id")

    if magic_link:
        route.mx_magic_link = str(magic_link)
        update_fields.append("mx_magic_link")

    if entitlement_status:
        route.mx_entitlement_status = str(
            entitlement_status
        ).upper()
        update_fields.append("mx_entitlement_status")

    if route_version is not None:
        try:
            route.mx_route_version = int(route_version)
            update_fields.append("mx_route_version")
        except (TypeError, ValueError):
            pass

    route.mx_response = response_json
    route.mx_last_sync_at = timezone.now()

    update_fields.extend([
        "mx_response",
        "mx_last_sync_at",
        "updated_at",
    ])

    route.save(
        update_fields=list(dict.fromkeys(update_fields))
    )


# =========================================================
# ENVÍO
# =========================================================

def send_b2c_access_event_to_mx(
    *,
    payload: Dict[str, Any],
    user=None,
    route=None,
    route_snapshot=None,
    force: bool = False,
) -> Dict[str, Any]:
    """
    Envía un único intento hacia México.

    No implementa un bucle de reintentos dentro de la petición web.
    Si el error es recuperable, deja next_retry_at listo para que un
    cron o comando de gestión lo reprocese posteriormente.
    """
    if not isinstance(payload, dict):
        raise TypeError("payload debe ser un diccionario.")

    event_id = str(payload.get("eventId") or "").strip()
    event_type = str(payload.get("eventType") or "").strip()
    occurred_at = str(payload.get("occurredAt") or "").strip()

    if not event_id:
        raise ValueError("El payload no contiene eventId.")

    if not event_type:
        raise ValueError("El payload no contiene eventType.")

    if not occurred_at:
        raise ValueError("El payload no contiene occurredAt.")

    endpoint = str(
        getattr(
            settings,
            "MX_B2C_ACCESS_EVENT_URL",
            "",
        )
        or ""
    ).strip()

    if not endpoint:
        raise RuntimeError(
            "No está configurado MX_B2C_ACCESS_EVENT_URL."
        )

    raw_body = json_dumps(payload)

    headers = build_mx_headers(
        raw_body=raw_body,
        event_id=event_id,
        occurred_at=occurred_at,
    )

    log, created = create_or_get_log(
        payload=payload,
        raw_body=raw_body,
        user=user,
        route=route,
        route_snapshot=route_snapshot,
    )

    if not created:
        refresh_existing_log(
            log=log,
            payload=payload,
            raw_body=raw_body,
            user=user,
            route=route,
            route_snapshot=route_snapshot,
        )

    if not force and log.send_status == "sent":
        duplicate = (
            str(log.mx_status or "").upper()
            == "DUPLICATE"
        )

        pending = (
            str(log.mx_status or "").upper()
            in PENDING_MX_STATUSES
        )

        return {
            "ok": True,
            "accepted": True,
            "duplicate": duplicate,
            "pending": pending,
            "retry": False,
            "permanent": False,
            "status": log.mx_status or "DUPLICATE",
            "http_status": log.http_status,
            "mxUserId": log.mx_user_id,
            "magicLink": log.magic_link,
            "entitlementStatus": log.entitlement_status,
            "eventId": event_id,
            "skipped": True,
        }

    max_attempts = int(
        getattr(
            settings,
            "MX_B2C_MAX_ATTEMPTS",
            8,
        )
    )

    if not force and log.attempts >= max_attempts:
        log.send_status = "permanent_failed"
        log.is_retryable = False
        log.next_retry_at = None
        log.last_error = (
            f"Se alcanzó el máximo de "
            f"{max_attempts} intentos."
        )

        log.save(
            update_fields=[
                "send_status",
                "is_retryable",
                "next_retry_at",
                "last_error",
                "updated_at",
            ]
        )

        return {
            "ok": False,
            "accepted": False,
            "duplicate": False,
            "pending": False,
            "retry": False,
            "permanent": True,
            "status": "MAX_ATTEMPTS_REACHED",
            "eventId": event_id,
            "error": log.last_error,
        }

    log.send_status = "processing"
    log.attempts = (log.attempts or 0) + 1
    log.is_retryable = False
    log.next_retry_at = None
    log.last_error = None

    log.save(
        update_fields=[
            "send_status",
            "attempts",
            "is_retryable",
            "next_retry_at",
            "last_error",
            "updated_at",
        ]
    )

    timeout = int(
        getattr(
            settings,
            "MX_B2C_TIMEOUT",
            20,
        )
    )

    connect_timeout = int(
        getattr(
            settings,
            "MX_B2C_CONNECT_TIMEOUT",
            min(timeout, 8),
        )
    )

    try:
        response = requests.post(
            endpoint,
            data=raw_body.encode("utf-8"),
            headers=headers,
            timeout=(connect_timeout, timeout),
        )

        try:
            response_json = response.json()

            if not isinstance(response_json, dict):
                response_json = {
                    "data": response_json,
                }

        except (ValueError, json.JSONDecodeError):
            response_json = {
                "raw": response.text[:10000],
            }

        response_data = extract_response_data(
            response_json=response_json,
            http_status=response.status_code,
        )

        mx_status = response_data["mx_status"]
        mx_user_id = response_data["mx_user_id"]
        magic_link = response_data["magic_link"]
        entitlement_status = response_data[
            "entitlement_status"
        ]
        response_route_version = response_data[
            "route_version"
        ]

        normalized_status = str(
            mx_status or ""
        ).upper()

        accepted = (
            response.ok
            and normalized_status
            in (
                SUCCESS_MX_STATUSES
                | PENDING_MX_STATUSES
            )
        )

        duplicate = (
            normalized_status == "DUPLICATE"
        )

        pending = (
            normalized_status in PENDING_MX_STATUSES
        )

        retryable = (
            not accepted
            and is_retryable_http_status(
                response.status_code
            )
        )

        permanent = (
            not accepted
            and not retryable
        )

        log.response_json = response_json
        log.http_status = response.status_code
        log.mx_status = mx_status
        log.mx_user_id = (
            str(mx_user_id)
            if mx_user_id is not None
            else None
        )
        log.magic_link = (
            str(magic_link)
            if magic_link is not None
            else None
        )
        log.entitlement_status = (
            str(entitlement_status).upper()
            if entitlement_status is not None
            else None
        )

        if accepted:
            log.send_status = "sent"
            log.sent_at = timezone.now()
            log.processed_at = (
                timezone.now()
                if not pending
                else None
            )
            log.is_retryable = False
            log.next_retry_at = None
            log.last_error = None

        elif retryable:
            log.send_status = "retry_pending"
            log.sent_at = None
            log.processed_at = None
            log.is_retryable = True
            log.next_retry_at = (
                parse_retry_after(response)
                or calculate_next_retry(log.attempts)
            )
            log.last_error = json.dumps(
                response_json,
                ensure_ascii=False,
            )[:10000]

        else:
            log.send_status = "permanent_failed"
            log.sent_at = None
            log.processed_at = timezone.now()
            log.is_retryable = False
            log.next_retry_at = None
            log.last_error = json.dumps(
                response_json,
                ensure_ascii=False,
            )[:10000]

        log.save(
            update_fields=[
                "response_json",
                "http_status",
                "mx_status",
                "mx_user_id",
                "magic_link",
                "entitlement_status",
                "send_status",
                "sent_at",
                "processed_at",
                "is_retryable",
                "next_retry_at",
                "last_error",
                "updated_at",
            ]
        )

        if accepted:
            update_route_with_mx_response(
                route=route,
                event_id=event_id,
                mx_status=mx_status,
                mx_user_id=mx_user_id,
                magic_link=magic_link,
                entitlement_status=entitlement_status,
                route_version=(
                    response_route_version
                    or get_route_version(payload)
                ),
                response_json=response_json,
            )

        return {
            "ok": accepted,
            "accepted": accepted,
            "duplicate": duplicate,
            "pending": pending,
            "retry": retryable,
            "permanent": permanent,
            "status": mx_status,
            "http_status": response.status_code,
            "mxUserId": mx_user_id,
            "magicLink": magic_link,
            "entitlementStatus": entitlement_status,
            "routeVersion": (
                response_route_version
                or get_route_version(payload)
            ),
            "nextRetryAt": (
                log.next_retry_at.isoformat()
                if log.next_retry_at
                else None
            ),
            "eventId": event_id,
            "response": response_json,
        }

    except requests.RequestException as exc:
        error_message = str(exc)

        retryable = log.attempts < max_attempts

        log.http_status = None
        log.response_json = None
        log.mx_status = "RETRYABLE_ERROR"
        log.send_status = (
            "retry_pending"
            if retryable
            else "permanent_failed"
        )
        log.is_retryable = retryable
        log.next_retry_at = (
            calculate_next_retry(log.attempts)
            if retryable
            else None
        )
        log.last_error = error_message
        log.processed_at = (
            None if retryable else timezone.now()
        )

        log.save(
            update_fields=[
                "http_status",
                "response_json",
                "mx_status",
                "send_status",
                "is_retryable",
                "next_retry_at",
                "last_error",
                "processed_at",
                "updated_at",
            ]
        )

        return {
            "ok": False,
            "accepted": False,
            "duplicate": False,
            "pending": False,
            "retry": retryable,
            "permanent": not retryable,
            "status": (
                "RETRYABLE_ERROR"
                if retryable
                else "MAX_ATTEMPTS_REACHED"
            ),
            "http_status": None,
            "eventId": event_id,
            "nextRetryAt": (
                log.next_retry_at.isoformat()
                if log.next_retry_at
                else None
            ),
            "error": error_message,
        }

    except Exception as exc:
        error_message = str(exc)

        log.send_status = "permanent_failed"
        log.is_retryable = False
        log.next_retry_at = None
        log.last_error = error_message
        log.processed_at = timezone.now()

        log.save(
            update_fields=[
                "send_status",
                "is_retryable",
                "next_retry_at",
                "last_error",
                "processed_at",
                "updated_at",
            ]
        )

        return {
            "ok": False,
            "accepted": False,
            "duplicate": False,
            "pending": False,
            "retry": False,
            "permanent": True,
            "status": "INTERNAL_ERROR",
            "http_status": None,
            "eventId": event_id,
            "error": error_message,
        }