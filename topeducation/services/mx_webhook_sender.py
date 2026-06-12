import hashlib
import hmac
import json
import requests

from django.conf import settings

from topeducation.models import MxWebhookDeliveryLog


def sign_payload(payload_str):
    secret = settings.STRIPE_B2C_WEBHOOK_SECRET

    return hmac.new(
        secret.encode("utf-8"),
        payload_str.encode("utf-8"),
        hashlib.sha256
    ).hexdigest()


def send_stripe_event_to_mx(
    event_id,
    event_type,
    payload,
    stripe_event_id=None,
    stripe_object_id=None,
):
    payload_json = json.dumps(
        payload,
        separators=(",", ":"),
        ensure_ascii=False,
    )

    signature = sign_payload(payload_json)

    headers = {
        "Content-Type": "application/json",
        "X-Signature": signature,
    }

    success = False
    status_code = None
    response_body = ""

    try:
        response = requests.post(
            settings.MX_STRIPE_B2C_WEBHOOK_URL,
            data=payload_json.encode("utf-8"),
            headers=headers,
            timeout=30,
        )

        status_code = response.status_code
        response_body = response.text[:5000]

        success = response.ok

    except Exception as e:
        response_body = str(e)

    log = MxWebhookDeliveryLog.objects.create(
        event_id=event_id,
        event_type=event_type,
        stripe_event_id=stripe_event_id,
        stripe_object_id=stripe_object_id,
        payload=payload,
        success=success,
        status_code=status_code,
        response_body=response_body,
    )

    return {
        "success": success,
        "status_code": status_code,
        "response_body": response_body,
        "log_id": log.id,
    }