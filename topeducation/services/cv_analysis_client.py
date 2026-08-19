# topeducation/services/cv_analysis_client.py

import base64
import logging

import requests
from django.conf import settings


logger = logging.getLogger(__name__)


# ============================================================
# HELPERS
# ============================================================

def _get_cv_analysis_url():
    """
    Obtiene y valida el endpoint configurado para análisis de CV.
    """
    url = str(
        getattr(settings, "CV_ANALYSIS_URL", "") or ""
    ).strip()

    if not url:
        raise RuntimeError(
            "CV_ANALYSIS_URL no está configurado."
        )

    return url


def _get_cv_analysis_timeout():
    """
    Retorna:
        (connect_timeout, read_timeout)

    El análisis de CV puede tardar considerablemente más que
    una petición HTTP convencional debido al procesamiento
    del documento y análisis posterior.
    """
    read_timeout = int(
        getattr(
            settings,
            "CV_ANALYSIS_TIMEOUT",
            180,
        )
        or 180
    )

    connect_timeout = int(
        getattr(
            settings,
            "CV_ANALYSIS_CONNECT_TIMEOUT",
            10,
        )
        or 10
    )

    # Evitamos configuraciones accidentales demasiado pequeñas.
    connect_timeout = max(3, connect_timeout)
    read_timeout = max(30, read_timeout)

    return connect_timeout, read_timeout


def _build_headers():
    """
    Construye headers para el proveedor.

    No se registra nunca la API key en logs.

    Si producción exige x-api-key, se toma desde
    CV_ANALYSIS_API_KEY.

    Se mantiene compatibilidad si el endpoint actualmente
    no requiere autenticación.
    """
    headers = {
        "Accept": "application/json",
        "Content-Type": "application/json",
    }

    api_key = str(
        getattr(
            settings,
            "CV_ANALYSIS_API_KEY",
            "",
        )
        or ""
    ).strip()

    if api_key:
        headers["x-api-key"] = api_key

    return headers


def _safe_provider_response(response):
    """
    Convierte la respuesta del proveedor a dict.

    Nunca asumimos que un 502/503/504 devolverá JSON.
    """
    try:
        data = response.json()

        if isinstance(data, dict):
            return data

        return {
            "ok": False,
            "data": data,
            "message": (
                "El proveedor devolvió una respuesta "
                "con formato inesperado."
            ),
            "errorCode": "invalid_provider_response",
        }

    except (ValueError, requests.exceptions.JSONDecodeError):
        raw_response = (
            response.text or ""
        ).strip()

        # Evitamos guardar/devolver páginas HTML gigantes
        # provenientes de gateways/proxies.
        if len(raw_response) > 3000:
            raw_response = (
                raw_response[:3000]
                + "..."
            )

        return {
            "ok": False,
            "data": None,
            "message": (
                raw_response
                or "El proveedor no devolvió una respuesta JSON válida."
            ),
            "errorCode": "invalid_provider_response",
        }


# ============================================================
# ANALIZAR CV
# ============================================================

def analyze_cv_with_provider(
    file_obj,
    language="es-CO",
):
    """
    Envía un CV al servicio externo de análisis.

    Contrato actual:
    {
        "language": "es-CO",
        "cvFile": {
            "filename": "...",
            "mimeType": "...",
            "base64": "..."
        }
    }

    Retorna:
        (http_status, response_dict)

    Importante:
    - conserva exactamente el contrato JSON/Base64;
    - soporta x-api-key de producción;
    - usa timeout separado de conexión/lectura;
    - requests.Timeout se propaga para que la view
      existente pueda manejarlo;
    - nunca registra contenido del CV ni API keys.
    """

    # ========================================================
    # CONFIGURACIÓN
    # ========================================================

    url = _get_cv_analysis_url()

    connect_timeout, read_timeout = (
        _get_cv_analysis_timeout()
    )

    headers = _build_headers()

    # ========================================================
    # ARCHIVO
    # ========================================================

    # Nos aseguramos de leer desde el inicio.
    try:
        file_obj.seek(0)
    except Exception:
        pass

    file_bytes = file_obj.read()

    if not file_bytes:
        raise ValueError(
            "El archivo de CV está vacío."
        )

    filename = (
        getattr(file_obj, "name", None)
        or "cv.pdf"
    )

    mime_type = (
        getattr(
            file_obj,
            "content_type",
            None,
        )
        or "application/octet-stream"
    )

    normalized_language = (
        str(language or "es-CO").strip()
        or "es-CO"
    )

    # ========================================================
    # PAYLOAD
    # ========================================================

    encoded_file = base64.b64encode(
        file_bytes
    ).decode("utf-8")

    payload = {
        "language": normalized_language,
        "cvFile": {
            "filename": filename,
            "mimeType": mime_type,
            "base64": encoded_file,
        },
    }

    # ========================================================
    # LOG SEGURO
    # ========================================================

    logger.info(
        (
            "CV analysis request: "
            "url=%s filename=%s mime=%s "
            "language=%s file_size=%s "
            "encoded_size=%s timeout=(%s,%s)"
        ),
        url,
        filename,
        mime_type,
        normalized_language,
        len(file_bytes),
        len(encoded_file),
        connect_timeout,
        read_timeout,
    )

    # ========================================================
    # REQUEST
    # ========================================================

    try:
        response = requests.post(
            url,
            json=payload,
            headers=headers,
            timeout=(
                connect_timeout,
                read_timeout,
            ),
        )

    except requests.Timeout:
        logger.warning(
            (
                "CV analysis timeout: "
                "url=%s filename=%s "
                "timeout=(%s,%s)"
            ),
            url,
            filename,
            connect_timeout,
            read_timeout,
        )

        # IMPORTANTE:
        # La view actual ya captura requests.Timeout.
        raise

    except requests.ConnectionError as exc:
        logger.exception(
            "CV analysis connection error: url=%s error=%s",
            url,
            str(exc),
        )

        return 502, {
            "ok": False,
            "data": None,
            "message": (
                "No fue posible conectar con "
                "el servicio de análisis de CV."
            ),
            "errorCode": "provider_connection_error",
        }

    except requests.RequestException as exc:
        logger.exception(
            "CV analysis request error: url=%s error=%s",
            url,
            str(exc),
        )

        return 502, {
            "ok": False,
            "data": None,
            "message": (
                "Ocurrió un error comunicándose con "
                "el servicio de análisis de CV."
            ),
            "errorCode": "provider_request_error",
        }

    # ========================================================
    # RESPONSE
    # ========================================================

    data = _safe_provider_response(
        response
    )

    logger.info(
        (
            "CV analysis response: "
            "url=%s status=%s "
            "provider_ok=%s "
            "error_code=%s"
        ),
        url,
        response.status_code,
        data.get("ok"),
        data.get("errorCode"),
    )

    # Para errores podemos registrar el mensaje,
    # pero nunca el CV ni información sensible.
    if response.status_code >= 400:
        logger.warning(
            (
                "CV analysis provider error: "
                "status=%s error_code=%s "
                "message=%s"
            ),
            response.status_code,
            data.get("errorCode"),
            str(
                data.get("message") or ""
            )[:1000],
        )

    return response.status_code, data