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


# Estados FUNCIONALES devueltos por MX que deben
# reintentarse con exactamente el mismo eventId y body.
RETRYABLE_MX_STATUSES = {
    "RETRYABLE_ERROR",
}


# Estados FUNCIONALES que MX considera definitivos.
PERMANENT_MX_STATUSES = {
    "PERMANENT_ERROR",
    "REJECTED",
    "FAILED",
}


# Códigos HTTP que deben tratarse como recuperables.
RETRYABLE_HTTP_STATUSES = {
    408,
    425,
    429,
    500,
    502,
    503,
    504,
}


# Códigos HTTP que normalmente representan un error
# permanente del request.
PERMANENT_HTTP_STATUSES = {
    400,
    401,
    403,
    404,
    405,
    409,
    410,
    415,
    422,
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

    # 202 significa que México aceptó el evento para procesamiento,
    # pero todavía no confirmó que haya sido aplicado.
    if http_status == 202:
        return "ACCEPTED"

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

            # Compatibilidad defensiva durante transición de contrato.
            # El nombre canónico sigue siendo magicLink.
            "loginUrl",
            "login_url",
            "accessUrl",
            "access_url",
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


def sanitize_response_for_log(
    response_json: Dict[str, Any],
) -> Dict[str, Any]:
    """
    Devuelve una copia segura para logs/errores.

    magicLink es una credencial persistente y no debe terminar
    expuesta en last_error ni logs visibles.
    """
    if not isinstance(response_json, dict):
        return {}

    def scrub(value):
        if isinstance(value, dict):
            result = {}

            for key, item in value.items():
                normalized_key = str(key).lower()

                if normalized_key in {
                    "magiclink",
                    "magic_link",
                    "loginurl",
                    "login_url",
                    "accessurl",
                    "access_url",
                }:
                    result[key] = "[REDACTED]"
                else:
                    result[key] = scrub(item)

            return result

        if isinstance(value, list):
            return [
                scrub(item)
                for item in value
            ]

        return value

    return scrub(response_json)


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
    Refresca únicamente relaciones auxiliares del log.

    Regla de idempotencia MX:
    - un retry debe reutilizar el MISMO eventId;
    - debe reutilizar también el MISMO body.

    Por eso, si ya existe un log para eventId y el payload cambia,
    se considera un error local en vez de sobrescribir el evento
    previamente registrado.
    """
    incoming_hash = payload_sha256(raw_body)

    if (
        log.payload_hash
        and log.payload_hash != incoming_hash
    ):
        raise ValueError(
            "event_id_payload_mismatch"
        )

    resolved_snapshot = resolve_route_snapshot(
        route=route,
        route_snapshot=route_snapshot,
    )

    update_fields = []

    if user and not log.user_id:
        log.user = user
        update_fields.append("user")

    if route and not log.learning_route_id:
        log.learning_route = route
        update_fields.append(
            "learning_route"
        )

    if (
        resolved_snapshot
        and not log.route_snapshot_id
    ):
        log.route_snapshot = resolved_snapshot
        update_fields.append(
            "route_snapshot"
        )

    route_version = get_route_version(payload)

    if (
        route_version is not None
        and log.route_version is None
    ):
        log.route_version = route_version
        update_fields.append(
            "route_version"
        )

    stripe_event_id = get_stripe_event_id(
        payload
    )

    if (
        stripe_event_id
        and not log.stripe_event_id
    ):
        log.stripe_event_id = stripe_event_id
        update_fields.append(
            "stripe_event_id"
        )

    if update_fields:
        update_fields.append(
            "updated_at"
        )

        log.save(
            update_fields=update_fields
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

    REGLAS IMPORTANTES DE IDEMPOTENCIA MX
    =====================================

    1. Un evento se identifica por eventId.

    2. Si México responde RETRYABLE_ERROR, HTTP 503, HTTP 504
       o ocurre un timeout/error de red, el evento puede volver
       a enviarse.

    3. El retry DEBE utilizar:
       - exactamente el mismo eventId;
       - exactamente el mismo payload/body.

    4. No se reconstruye la learningRoute para un retry.

    5. No se divide una learningRoute SNAPSHOT en varios eventos.

    6. Este método realiza UN SOLO intento HTTP.
       Los siguientes intentos deben ejecutarse mediante el
       mecanismo de retry/cron correspondiente.

    7. APPLIED y DUPLICATE son estados finales exitosos.

    8. RETRYABLE_ERROR es recuperable aunque el HTTP exterior
       sea 200/400/etc., porque la semántica funcional de MX
       tiene prioridad.
    """

    # =========================================================
    # VALIDAR PAYLOAD
    # =========================================================

    if not isinstance(payload, dict):
        raise TypeError(
            "payload debe ser un diccionario."
        )

    event_id = str(
        payload.get("eventId") or ""
    ).strip()

    event_type = str(
        payload.get("eventType") or ""
    ).strip()

    occurred_at = str(
        payload.get("occurredAt") or ""
    ).strip()

    if not event_id:
        raise ValueError(
            "El payload no contiene eventId."
        )

    if not event_type:
        raise ValueError(
            "El payload no contiene eventType."
        )

    if not occurred_at:
        raise ValueError(
            "El payload no contiene occurredAt."
        )

    # =========================================================
    # ENDPOINT MX
    # =========================================================

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
            "No está configurado "
            "MX_B2C_ACCESS_EVENT_URL."
        )

    # =========================================================
    # SERIALIZACIÓN DETERMINISTA
    # =========================================================
    #
    # IMPORTANTE:
    # json_dumps usa sort_keys=True y separators fijos.
    #
    # Esto garantiza que el mismo payload produzca exactamente
    # el mismo raw_body.
    # =========================================================

    raw_body = json_dumps(payload)

    # =========================================================
    # CREAR / RECUPERAR LOG
    # =========================================================

    log, created = create_or_get_log(
        payload=payload,
        raw_body=raw_body,
        user=user,
        route=route,
        route_snapshot=route_snapshot,
    )

    if not created:
        # Esta función valida también que un eventId existente
        # NO esté intentando utilizar otro payload.
        #
        # Si cambia el hash:
        # event_id_payload_mismatch
        refresh_existing_log(
            log=log,
            payload=payload,
            raw_body=raw_body,
            user=user,
            route=route,
            route_snapshot=route_snapshot,
        )

    # =========================================================
    # EVENTO YA FINALIZADO
    # =========================================================

    current_mx_status = str(
        log.mx_status or ""
    ).strip().upper()

    if (
        not force
        and log.send_status == "sent"
        and current_mx_status in SUCCESS_MX_STATUSES
    ):
        duplicate = (
            current_mx_status == "DUPLICATE"
        )

        return {
            "ok": True,
            "accepted": True,
            "duplicate": duplicate,
            "pending": False,
            "retry": False,
            "permanent": False,
            "status": (
                log.mx_status
                or "DUPLICATE"
            ),
            "http_status": log.http_status,
            "mxUserId": log.mx_user_id,
            "magicLink": log.magic_link,
            "entitlementStatus": (
                log.entitlement_status
            ),
            "eventId": event_id,
            "skipped": True,
        }

    # =========================================================
    # EVENTO ACEPTADO PERO TODAVÍA PENDIENTE
    # =========================================================

    if (
        not force
        and log.send_status == "sent"
        and current_mx_status in PENDING_MX_STATUSES
    ):
        return {
            "ok": True,
            "accepted": True,
            "duplicate": False,
            "pending": True,
            "retry": False,
            "permanent": False,
            "status": log.mx_status,
            "http_status": log.http_status,
            "mxUserId": log.mx_user_id,
            "magicLink": log.magic_link,
            "entitlementStatus": (
                log.entitlement_status
            ),
            "eventId": event_id,
            "skipped": True,
        }

    # =========================================================
    # MÁXIMO DE INTENTOS
    # =========================================================

    max_attempts = int(
        getattr(
            settings,
            "MX_B2C_MAX_ATTEMPTS",
            8,
        )
    )

    if (
        not force
        and (log.attempts or 0) >= max_attempts
    ):
        log.send_status = "permanent_failed"
        log.is_retryable = False
        log.next_retry_at = None

        log.last_error = (
            f"Se alcanzó el máximo de "
            f"{max_attempts} intentos."
        )

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
            "status": "MAX_ATTEMPTS_REACHED",
            "eventId": event_id,
            "error": log.last_error,
        }

    # =========================================================
    # IMPORTANTE:
    # FIRMAR EXACTAMENTE EL BODY QUE SE VA A ENVIAR
    # =========================================================

    headers = build_mx_headers(
        raw_body=raw_body,
        event_id=event_id,
        occurred_at=occurred_at,
    )

    # =========================================================
    # MARCAR INTENTO
    # =========================================================

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

    # =========================================================
    # TIMEOUTS
    # =========================================================

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

    # =========================================================
    # ENVÍO
    # =========================================================

    try:
        response = requests.post(
            endpoint,
            data=raw_body.encode("utf-8"),
            headers=headers,
            timeout=(
                connect_timeout,
                timeout,
            ),
        )

        # =====================================================
        # RESPUESTA JSON
        # =====================================================

        try:
            response_json = response.json()

            if not isinstance(
                response_json,
                dict,
            ):
                response_json = {
                    "data": response_json,
                }

        except (
            ValueError,
            json.JSONDecodeError,
        ):
            response_json = {
                "raw": response.text[:10000],
            }

        # =====================================================
        # EXTRAER INFORMACIÓN
        # =====================================================

        response_data = extract_response_data(
            response_json=response_json,
            http_status=response.status_code,
        )

        mx_status = response_data[
            "mx_status"
        ]

        mx_user_id = response_data[
            "mx_user_id"
        ]

        magic_link = response_data[
            "magic_link"
        ]

        entitlement_status = response_data[
            "entitlement_status"
        ]

        response_route_version = response_data[
            "route_version"
        ]

        normalized_status = str(
            mx_status or ""
        ).strip().upper()

        http_status = response.status_code

        # =====================================================
        # CLASIFICACIÓN FUNCIONAL
        # =====================================================

        success_status = (
            normalized_status
            in SUCCESS_MX_STATUSES
        )

        pending_status = (
            normalized_status
            in PENDING_MX_STATUSES
        )

        retryable_mx_status = (
            normalized_status
            in RETRYABLE_MX_STATUSES
        )

        permanent_mx_status = (
            normalized_status
            in PERMANENT_MX_STATUSES
        )

        retryable_http = (
            is_retryable_http_status(
                http_status
            )
        )

        permanent_http = (
            http_status
            in PERMANENT_HTTP_STATUSES
        )

        # =====================================================
        # RESULTADO EXITOSO
        # =====================================================

        accepted = (
            response.ok
            and (
                success_status
                or pending_status
            )
        )

        duplicate = (
            normalized_status
            == "DUPLICATE"
        )

        pending = (
            accepted
            and pending_status
        )

        # =====================================================
        # RETRYABLE
        # =====================================================
        #
        # MUY IMPORTANTE:
        #
        # RETRYABLE_ERROR tiene prioridad sobre el HTTP.
        #
        # Ejemplo:
        #
        # HTTP 200
        # status = RETRYABLE_ERROR
        #
        # => RETRY
        #
        # HTTP 400
        # status = RETRYABLE_ERROR
        #
        # => RETRY
        #
        # HTTP 503
        # => RETRY
        #
        # HTTP 504
        # => RETRY
        # =====================================================

        retryable = (
            not accepted
            and (
                retryable_mx_status
                or retryable_http
            )
        )

        # =====================================================
        # ERROR PERMANENTE
        # =====================================================

        permanent = (
            not accepted
            and not retryable
            and (
                permanent_mx_status
                or permanent_http
                or not response.ok
                or bool(normalized_status)
            )
        )

        # =====================================================
        # ACTUALIZAR LOG
        # =====================================================

        log.response_json = response_json
        log.http_status = http_status
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
            str(
                entitlement_status
            ).upper()
            if entitlement_status is not None
            else None
        )

        # =====================================================
        # ACEPTADO
        # =====================================================

        if accepted:
            log.send_status = "sent"
            log.sent_at = timezone.now()

            log.processed_at = (
                None
                if pending
                else timezone.now()
            )

            log.is_retryable = False
            log.next_retry_at = None
            log.last_error = None

        # =====================================================
        # RETRY
        # =====================================================

        elif retryable:
            can_retry = (
                log.attempts < max_attempts
            )

            if can_retry:
                log.send_status = (
                    "retry_pending"
                )

                log.is_retryable = True

                log.next_retry_at = (
                    parse_retry_after(
                        response
                    )
                    or calculate_next_retry(
                        log.attempts
                    )
                )

                log.processed_at = None

            else:
                log.send_status = (
                    "permanent_failed"
                )

                log.is_retryable = False
                log.next_retry_at = None
                log.processed_at = (
                    timezone.now()
                )

                permanent = True
                retryable = False

            log.sent_at = None

            log.last_error = json.dumps(
                sanitize_response_for_log(
                    response_json
                ),
                ensure_ascii=False,
            )[:10000]

        # =====================================================
        # PERMANENTE
        # =====================================================

        else:
            log.send_status = (
                "permanent_failed"
            )

            log.sent_at = None
            log.processed_at = timezone.now()
            log.is_retryable = False
            log.next_retry_at = None

            log.last_error = json.dumps(
                sanitize_response_for_log(
                    response_json
                ),
                ensure_ascii=False,
            )[:10000]

        # =====================================================
        # GUARDAR LOG
        # =====================================================

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

        # =====================================================
        # ACTUALIZAR LEARNING ROUTE
        # =====================================================
        #
        # Solo actualizamos los datos definitivos del usuario
        # cuando México realmente aceptó el evento.
        # =====================================================

        if accepted:
            update_route_with_mx_response(
                route=route,
                event_id=event_id,
                mx_status=mx_status,
                mx_user_id=mx_user_id,
                magic_link=magic_link,
                entitlement_status=(
                    entitlement_status
                ),
                route_version=(
                    response_route_version
                    or get_route_version(
                        payload
                    )
                ),
                response_json=response_json,
            )

        # =====================================================
        # RESULTADO
        # =====================================================

        return {
            "ok": accepted,
            "accepted": accepted,
            "duplicate": duplicate,
            "pending": pending,
            "retry": retryable,
            "permanent": permanent,
            "status": mx_status,
            "http_status": http_status,
            "mxUserId": mx_user_id,
            "magicLink": magic_link,
            "entitlementStatus": (
                entitlement_status
            ),
            "routeVersion": (
                response_route_version
                or get_route_version(
                    payload
                )
            ),
            "nextRetryAt": (
                log.next_retry_at.isoformat()
                if log.next_retry_at
                else None
            ),
            "eventId": event_id,
            "response": response_json,
        }

    # =========================================================
    # ERROR DE RED / TIMEOUT
    # =========================================================

    except requests.RequestException as exc:
        error_message = str(exc)

        can_retry = (
            log.attempts < max_attempts
        )

        log.http_status = None
        log.response_json = None

        log.mx_status = (
            "RETRYABLE_ERROR"
            if can_retry
            else "MAX_ATTEMPTS_REACHED"
        )

        log.send_status = (
            "retry_pending"
            if can_retry
            else "permanent_failed"
        )

        log.is_retryable = can_retry

        log.next_retry_at = (
            calculate_next_retry(
                log.attempts
            )
            if can_retry
            else None
        )

        log.last_error = (
            error_message[:10000]
        )

        log.sent_at = None

        log.processed_at = (
            None
            if can_retry
            else timezone.now()
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
                "sent_at",
                "processed_at",
                "updated_at",
            ]
        )

        return {
            "ok": False,
            "accepted": False,
            "duplicate": False,
            "pending": False,
            "retry": can_retry,
            "permanent": not can_retry,
            "status": (
                "RETRYABLE_ERROR"
                if can_retry
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

    # =========================================================
    # ERROR INTERNO COLOMBIA
    # =========================================================

    except Exception as exc:
        error_message = str(exc)

        log.send_status = (
            "permanent_failed"
        )

        log.is_retryable = False
        log.next_retry_at = None
        log.last_error = (
            error_message[:10000]
        )

        log.sent_at = None
        log.processed_at = timezone.now()

        log.save(
            update_fields=[
                "send_status",
                "is_retryable",
                "next_retry_at",
                "last_error",
                "sent_at",
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