# topeducation/services/help_desk.py

import logging

import requests

from django.conf import settings
from requests import exceptions as requests_exc


logger = logging.getLogger(__name__)


class HelpDeskIntegrationError(Exception):

    def __init__(
        self,
        message,
        *,
        status_code=502,
        code="help_desk_error",
        data=None,
    ):
        super().__init__(message)

        self.status_code = status_code
        self.code = code
        self.data = data


class HelpDeskTimeoutError(Exception):
    pass


def get_help_desk_headers():

    token = str(
        getattr(
            settings,
            "MX_HELP_DESK_SERVICE_TOKEN",
            "",
        )
        or ""
    ).strip()

    if not token:

        raise HelpDeskIntegrationError(
            "La integración de mesa de ayuda no está configurada.",
            status_code=503,
            code="help_desk_not_configured",
        )

    return {
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json",
        "Accept": "application/json",
    }


def help_desk_request(
    method,
    path,
    *,
    json=None,
):

    base_url = str(
        settings.MX_HELP_DESK_BASE_URL
        or ""
    ).rstrip("/")

    path = "/" + str(
        path or ""
    ).lstrip("/")

    url = f"{base_url}{path}"

    try:

        response = requests.request(
            method=method,
            url=url,
            headers=get_help_desk_headers(),
            json=json,
            timeout=(
                settings.MX_HELP_DESK_CONNECT_TIMEOUT,
                settings.MX_HELP_DESK_READ_TIMEOUT,
            ),
        )

    # ============================================================
    # TIMEOUT
    # ============================================================

    except requests_exc.Timeout as exc:

        logger.error(
            "[HELP_DESK_TIMEOUT] "
            "method=%s "
            "url=%s "
            "error_type=%s "
            "error=%s",
            method,
            url,
            type(exc).__name__,
            str(exc),
        )

        raise HelpDeskTimeoutError(
            "Timeout en la integración de mesa de ayuda."
        ) from exc

    # ============================================================
    # SSL
    # ============================================================

    except requests_exc.SSLError as exc:

        logger.error(
            "[HELP_DESK_SSL_ERROR] "
            "method=%s "
            "url=%s "
            "error_type=%s "
            "error=%s",
            method,
            url,
            type(exc).__name__,
            str(exc),
        )

        raise HelpDeskIntegrationError(
            (
                "No fue posible validar la conexión "
                "segura con la mesa de ayuda."
            ),
            status_code=502,
            code="help_desk_ssl_error",
        ) from exc

    # ============================================================
    # CONNECTION / DNS
    # ============================================================

    except requests_exc.ConnectionError as exc:

        logger.error(
            "[HELP_DESK_CONNECTION_ERROR] "
            "method=%s "
            "url=%s "
            "error_type=%s "
            "error=%s",
            method,
            url,
            type(exc).__name__,
            str(exc),
        )

        raise HelpDeskIntegrationError(
            "No fue posible conectar con la mesa de ayuda.",
            status_code=502,
            code="help_desk_connection_error",
        ) from exc

    # ============================================================
    # GENERAL REQUESTS ERROR
    # ============================================================

    except requests_exc.RequestException as exc:

        logger.error(
            "[HELP_DESK_REQUEST_ERROR] "
            "method=%s "
            "url=%s "
            "error_type=%s "
            "error=%s",
            method,
            url,
            type(exc).__name__,
            str(exc),
        )

        raise HelpDeskIntegrationError(
            "No fue posible conectar con la mesa de ayuda.",
            status_code=502,
            code="help_desk_request_error",
        ) from exc

    # ============================================================
    # RESPONSE JSON
    # ============================================================

    try:

        data = response.json()

    except ValueError:

        logger.error(
            "[HELP_DESK_INVALID_JSON] "
            "method=%s "
            "url=%s "
            "status=%s "
            "body=%s",
            method,
            url,
            response.status_code,
            response.text[:300],
        )

        data = {
            "ok": False,
            "error": "invalid_external_response",
            "message": (
                "La API central devolvió "
                "una respuesta no válida."
            ),
        }

    return response, data