import hashlib
import hmac
import json
import requests

from django.conf import settings
from django.utils import timezone

from topeducation.models import MxAccessEventLog


def json_dumps(payload):
    return json.dumps(
        payload,
        separators=(",", ":"),
        ensure_ascii=False,
    )


def build_mx_headers(raw_body, event_id, occurred_at):
    secret = settings.MX_B2C_ACCESS_EVENT_HMAC_SECRET

    signature = hmac.new(
        secret.encode("utf-8"),
        raw_body.encode("utf-8"),
        hashlib.sha256,
    ).hexdigest()

    return {
        "Content-Type": "application/json",
        "X-Top-Signature": f"hmac-sha256={signature}",
        "X-Top-Timestamp": occurred_at,
        "X-Event-Id": event_id,
    }


def send_b2c_access_event_to_mx(*, payload, user=None, route=None):
    event_id = payload["eventId"]
    event_type = payload["eventType"]
    occurred_at = payload["occurredAt"]

    raw_body = json_dumps(payload)
    headers = build_mx_headers(raw_body, event_id, occurred_at)

    log, created = MxAccessEventLog.objects.get_or_create(
        stripe_event_id=event_id,
        defaults={
            "user": user,
            "learning_route_id": route.id if route else None,
            "event_type": event_type,
            "event_source": "colombia_b2c",
            "payload_json": payload,
            "send_status": "pending",
            "attempts": 0,
        },
    )

    if not created and log.send_status == "sent":
        return {
            "ok": True,
            "status": log.mx_status or "DUPLICATE",
            "mxUserId": log.mx_user_id,
            "magicLink": log.magic_link,
            "skipped": True,
        }

    log.send_status = "processing"
    log.attempts = (log.attempts or 0) + 1
    log.save(update_fields=["send_status", "attempts", "updated_at"])

    try:
        response = requests.post(
            settings.MX_B2C_ACCESS_EVENT_URL,
            data=raw_body.encode("utf-8"),
            headers=headers,
            timeout=getattr(settings, "MX_B2C_TIMEOUT", 15),
        )

        try:
            response_json = response.json()
        except Exception:
            response_json = {"raw": response.text[:3000]}

        mx_status = response_json.get("status")
        mx_user_id = response_json.get("mxUserId")
        magic_link = response_json.get("magicLink")

        ok = response.ok and mx_status in ["APPLIED", "DUPLICATE"]

        log.response_json = response_json
        log.mx_status = mx_status
        log.mx_user_id = mx_user_id
        log.magic_link = magic_link
        log.send_status = "sent" if ok else "failed"
        log.sent_at = timezone.now() if ok else None
        log.last_error = None if ok else json.dumps(response_json, ensure_ascii=False)
        log.save(update_fields=[
            "response_json",
            "mx_status",
            "mx_user_id",
            "magic_link",
            "send_status",
            "sent_at",
            "last_error",
            "updated_at",
        ])

        return {
            "ok": ok,
            "status": mx_status,
            "http_status": response.status_code,
            "mxUserId": mx_user_id,
            "magicLink": magic_link,
            "response": response_json,
        }

    except Exception as e:
        log.send_status = "failed"
        log.last_error = str(e)
        log.save(update_fields=["send_status", "last_error", "updated_at"])

        return {
            "ok": False,
            "status": "RETRYABLE_ERROR",
            "error": str(e),
        }