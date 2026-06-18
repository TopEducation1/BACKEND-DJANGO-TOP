# topeducation/services/cv_analysis_client.py

import base64
import requests
from django.conf import settings


def analyze_cv_with_provider(file_obj, language="es-CO"):
    file_bytes = file_obj.read()

    payload = {
        "language": language or "es-CO",
        "cvFile": {
            "filename": file_obj.name or "cv.pdf",
            "mimeType": getattr(file_obj, "content_type", None) or "application/octet-stream",
            "base64": base64.b64encode(file_bytes).decode("utf-8"),
        },
    }

    response = requests.post(
        settings.CV_ANALYSIS_URL,
        json=payload,
        timeout=settings.CV_ANALYSIS_TIMEOUT,
    )

    try:
        data = response.json()
    except Exception:
        data = {
            "ok": False,
            "message": response.text,
            "errorCode": "invalid_provider_response",
        }

    return response.status_code, data