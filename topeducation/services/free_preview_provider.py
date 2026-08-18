from __future__ import annotations

import hashlib
import json
import logging
import os
import random
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone as dt_timezone
from typing import Any, Dict, Iterable, List, Mapping, Optional, Sequence
from urllib.parse import urlparse

import requests
from django.conf import settings
from django.core.cache import cache


logger = logging.getLogger(__name__)


DEFAULT_ENDPOINT = (
    "https://api-colombia.universidad.top/"
    "v1/b2c/free-preview-courses"
)

DEFAULT_COUNTRY_CODE = "CO"
DEFAULT_PAGE_LIMIT = 200
DEFAULT_TIMEOUT_SECONDS = 45
DEFAULT_CACHE_TIMEOUT_SECONDS = 60 * 60 * 6
DEFAULT_MAX_PAGES = 100
DEFAULT_SELECTION_SIZE = 3
MAX_SELECTION_SIZE = 200
MAX_PREVIEW_AGE_DAYS = 30
ALLOWED_PREVIEW_TYPES = {"AUDIT", "COURSE_PREVIEW"}

CACHE_KEY_CURRENT = "topeducation:free-preview:catalog:current:v1"
CACHE_KEY_LAST_VALID = "topeducation:free-preview:catalog:last-valid:v1"
CACHE_KEY_METADATA = "topeducation:free-preview:catalog:metadata:v1"


# =========================================================
# EXCEPCIONES
# =========================================================

class FreePreviewProviderError(Exception):
    """Error base del proveedor del catálogo Free."""


class FreePreviewConfigurationError(FreePreviewProviderError):
    """La integración no posee la configuración mínima requerida."""


class FreePreviewRequestError(FreePreviewProviderError):
    """No fue posible consultar el catálogo remoto."""


class FreePreviewHTTPError(FreePreviewRequestError):
    """El endpoint respondió HTTP no exitoso."""

    def __init__(
        self,
        message: str,
        *,
        status_code: int,
        retryable: bool,
    ):
        super().__init__(message)
        self.status_code = int(status_code)
        self.retryable = bool(retryable)


class FreePreviewResponseError(FreePreviewProviderError):
    """El endpoint devolvió una respuesta inválida."""


class FreePreviewSelectionError(FreePreviewProviderError):
    """No fue posible seleccionar las experiencias Free requeridas."""


# =========================================================
# RESULTADOS
# =========================================================

@dataclass(frozen=True)
class FreePreviewCatalogResult:
    items: List[Dict[str, Any]]
    source: str
    total: int
    pages: int
    stale: bool
    metadata: Dict[str, Any]


# =========================================================
# CONFIGURACIÓN
# =========================================================

def _setting(name: str, default: Any = None) -> Any:
    value = getattr(settings, name, None)

    if value not in (None, ""):
        return value

    value = os.getenv(name)

    if value not in (None, ""):
        return value

    return default


def get_free_preview_endpoint() -> str:
    return str(
        _setting(
            "MX_FREE_PREVIEW_ENDPOINT",
            DEFAULT_ENDPOINT,
        )
    ).strip()


def get_free_preview_api_key() -> str:
    """
    API key del catálogo Free.

    Prioridad:
    1. MX_FREE_PREVIEW_API_KEY
    2. COURSES_EXTERNAL_API_KEY (compatibilidad temporal)

    No se reutiliza MX_B2C_API_KEY porque la credencial B2C y la
    credencial de catálogo son responsabilidades distintas.
    """
    api_key = (
        _setting("MX_FREE_PREVIEW_API_KEY")
        or _setting("COURSES_EXTERNAL_API_KEY")
    )

    return str(api_key or "").strip()


def get_timeout_seconds() -> int:
    try:
        value = int(
            _setting(
                "MX_FREE_PREVIEW_TIMEOUT",
                DEFAULT_TIMEOUT_SECONDS,
            )
        )
    except (TypeError, ValueError):
        value = DEFAULT_TIMEOUT_SECONDS

    return max(5, min(value, 180))


def get_cache_timeout_seconds() -> int:
    try:
        value = int(
            _setting(
                "MX_FREE_PREVIEW_CACHE_TIMEOUT",
                DEFAULT_CACHE_TIMEOUT_SECONDS,
            )
        )
    except (TypeError, ValueError):
        value = DEFAULT_CACHE_TIMEOUT_SECONDS

    return max(60, value)


def get_max_pages() -> int:
    try:
        value = int(
            _setting(
                "MX_FREE_PREVIEW_MAX_PAGES",
                DEFAULT_MAX_PAGES,
            )
        )
    except (TypeError, ValueError):
        value = DEFAULT_MAX_PAGES

    return max(1, min(value, 1000))


# =========================================================
# UTILIDADES
# =========================================================

def _ensure_mapping(value: Any) -> Dict[str, Any]:
    return dict(value) if isinstance(value, Mapping) else {}


def _normalize_provider(value: Any) -> Optional[str]:
    normalized = str(value or "").strip().upper()
    return normalized or None


def _normalize_language(value: Any) -> Optional[str]:
    normalized = str(value or "").strip().lower()
    return normalized or None


def _normalize_country_code(value: Any) -> str:
    normalized = str(value or DEFAULT_COUNTRY_CODE).strip().upper()
    return normalized[:2] or DEFAULT_COUNTRY_CODE


def _normalize_page_limit(value: Any) -> int:
    try:
        normalized = int(value)
    except (TypeError, ValueError):
        normalized = DEFAULT_PAGE_LIMIT

    return max(1, min(normalized, 200))


def _is_http_url(value: Any) -> bool:
    raw = str(value or "").strip()

    if not raw:
        return False

    try:
        parsed = urlparse(raw)
    except Exception:
        return False

    return (
        parsed.scheme.lower() in {"http", "https"}
        and bool(parsed.netloc)
    )


def _parse_iso_datetime(value: Any) -> Optional[datetime]:
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


def _is_preview_validation_current(
    value: Any,
    *,
    max_age_days: int = MAX_PREVIEW_AGE_DAYS,
) -> bool:
    """
    El contrato MX exige que preview.validatedAt tenga una antigüedad
    máxima de 30 días al momento de provisionar un usuario nuevo.
    """
    validated_at = _parse_iso_datetime(value)

    if validated_at is None:
        return False

    now = datetime.now(
        dt_timezone.utc
    )

    age = now - validated_at

    return (
        timedelta(0)
        <= age
        <= timedelta(days=max_age_days)
    )


def _build_headers() -> Dict[str, str]:
    api_key = get_free_preview_api_key()

    if not api_key:
        raise FreePreviewConfigurationError(
            "No se encontró la API key del catálogo Free. "
            "Configura MX_FREE_PREVIEW_API_KEY."
        )

    return {
        "Accept": "application/json",
        "User-Agent": "TopEducation-Colombia-FreePreview/1.0",
        "x-api-key": api_key,
    }


def _catalog_cache_key(
    *,
    provider: Optional[str],
    language: Optional[str],
    country_code: str,
) -> str:
    raw = "|".join([
        provider or "*",
        language or "*",
        country_code,
    ])

    digest = hashlib.sha256(
        raw.encode("utf-8")
    ).hexdigest()[:20]

    return f"{CACHE_KEY_CURRENT}:{digest}"


def _last_valid_cache_key(
    *,
    provider: Optional[str],
    language: Optional[str],
    country_code: str,
) -> str:
    raw = "|".join([
        provider or "*",
        language or "*",
        country_code,
    ])

    digest = hashlib.sha256(
        raw.encode("utf-8")
    ).hexdigest()[:20]

    return f"{CACHE_KEY_LAST_VALID}:{digest}"


def _metadata_cache_key(
    *,
    provider: Optional[str],
    language: Optional[str],
    country_code: str,
) -> str:
    raw = "|".join([
        provider or "*",
        language or "*",
        country_code,
    ])

    digest = hashlib.sha256(
        raw.encode("utf-8")
    ).hexdigest()[:20]

    return f"{CACHE_KEY_METADATA}:{digest}"


def _extract_response_data(
    payload: Any,
) -> Dict[str, Any]:
    if not isinstance(payload, Mapping):
        raise FreePreviewResponseError(
            "La respuesta del catálogo Free no es un objeto JSON."
        )

    data = payload.get("data")

    if not isinstance(data, Mapping):
        raise FreePreviewResponseError(
            "La respuesta no contiene el objeto data esperado."
        )

    items = data.get("items")

    if not isinstance(items, list):
        raise FreePreviewResponseError(
            "La respuesta no contiene data.items como lista."
        )

    return dict(data)


def normalize_free_preview_item(
    item: Any,
    *,
    country_code: str = DEFAULT_COUNTRY_CODE,
    require_current_validation: bool = True,
) -> Optional[Dict[str, Any]]:
    """
    Valida y normaliza un elemento del endpoint Free.

    Reglas contractuales:
    - idInterno se conserva EXACTAMENTE como fue recibido;
    - preview.type debe ser elegible;
    - preview.url debe ser HTTP/HTTPS;
    - preview.validatedAt debe estar vigente (<= 30 días)
      para nuevas provisiones;
    - countryCode se conserva si llega y, si no, se completa
      con el país usado en la consulta.
    """
    if not isinstance(item, Mapping):
        return None

    id_interno = item.get("idInterno")

    if (
        not isinstance(id_interno, str)
        or not id_interno.strip()
    ):
        return None

    # Importante: NO hacemos strip sobre el valor que finalmente
    # devolvemos. Solo lo usamos para validar que no esté vacío.
    preview = _ensure_mapping(
        item.get("preview")
    )

    preview_type = str(
        preview.get("type") or ""
    ).strip().upper()

    preview_url = str(
        preview.get("url") or ""
    ).strip()

    validated_at = preview.get(
        "validatedAt"
    )

    preview_country_code = (
        preview.get("countryCode")
        or country_code
        or DEFAULT_COUNTRY_CODE
    )

    preview_country_code = (
        _normalize_country_code(
            preview_country_code
        )
    )

    if (
        not preview_type
        or preview_type
        not in ALLOWED_PREVIEW_TYPES
    ):
        return None

    if not _is_http_url(preview_url):
        return None

    if (
        require_current_validation
        and not _is_preview_validation_current(
            validated_at
        )
    ):
        return None

    return {
        "id": item.get("id"),
        "idInterno": id_interno,
        "title": str(
            item.get("title") or ""
        ).strip(),
        "provider": str(
            item.get("provider") or ""
        ).strip(),
        "language": str(
            item.get("language") or ""
        ).strip(),
        "preview": {
            "type": preview_type,
            "url": preview_url,
            "validatedAt": validated_at,
            "countryCode": (
                preview_country_code
            ),
        },
    }


def normalize_free_preview_items(
    items: Iterable[Any],
    *,
    country_code: str = DEFAULT_COUNTRY_CODE,
    require_current_validation: bool = True,
) -> List[Dict[str, Any]]:
    """
    Elimina registros inválidos y duplicados por idInterno.

    Los duplicados se comparan por el identificador exacto recibido.
    """
    normalized_items: List[Dict[str, Any]] = []
    seen_ids = set()

    for item in items or []:
        normalized = normalize_free_preview_item(
            item,
            country_code=country_code,
            require_current_validation=(
                require_current_validation
            ),
        )

        if normalized is None:
            continue

        id_interno = normalized["idInterno"]

        if id_interno in seen_ids:
            continue

        seen_ids.add(id_interno)
        normalized_items.append(normalized)

    return normalized_items


# =========================================================
# CONSULTA REMOTA
# =========================================================

def fetch_free_preview_page(
    *,
    cursor: Optional[str] = None,
    provider: Optional[str] = None,
    language: Optional[str] = None,
    country_code: str = DEFAULT_COUNTRY_CODE,
    limit: int = DEFAULT_PAGE_LIMIT,
    search: Optional[str] = None,
    session: Optional[requests.Session] = None,
) -> Dict[str, Any]:
    endpoint = get_free_preview_endpoint()

    if not endpoint:
        raise FreePreviewConfigurationError(
            "MX_FREE_PREVIEW_ENDPOINT está vacío."
        )

    params: Dict[str, Any] = {
        "countryCode": _normalize_country_code(
            country_code
        ),
        "limit": _normalize_page_limit(limit),
    }

    normalized_provider = _normalize_provider(provider)
    normalized_language = _normalize_language(language)

    if normalized_provider:
        params["provider"] = normalized_provider

    if normalized_language:
        params["language"] = normalized_language

    if search:
        params["search"] = str(search).strip()

    if cursor not in (None, ""):
        params["cursor"] = str(cursor)

    client = session or requests

    try:
        response = client.get(
            endpoint,
            headers=_build_headers(),
            params=params,
            timeout=get_timeout_seconds(),
        )
    except requests.Timeout as exc:
        raise FreePreviewRequestError(
            "El endpoint del catálogo Free superó el tiempo de espera."
        ) from exc
    except requests.RequestException as exc:
        raise FreePreviewRequestError(
            f"No fue posible consultar el catálogo Free: {exc}"
        ) from exc

    if response.status_code < 200 or response.status_code >= 300:
        response_preview = (
            response.text or ""
        )[:1000]

        retryable = (
            response.status_code
            in {500, 502, 503, 504}
        )

        raise FreePreviewHTTPError(
            (
                "El endpoint del catálogo Free respondió "
                f"HTTP {response.status_code}: "
                f"{response_preview}"
            ),
            status_code=response.status_code,
            retryable=retryable,
        )

    try:
        payload = response.json()
    except ValueError as exc:
        logger.error(
            "FREE PREVIEW devolvió una respuesta no JSON. "
            "status=%s content_type=%s body=%s",
            response.status_code,
            response.headers.get("Content-Type"),
            (response.text or "")[:5000],
        )

        raise FreePreviewResponseError(
            "El endpoint del catálogo Free no devolvió JSON válido."
        ) from exc


    data = _extract_response_data(payload)

    logger.info(
        "Free Preview consultado. "
        "status=%s provider=%s language=%s "
        "country=%s items=%s next_cursor=%s total=%s",
        response.status_code,
        params.get("provider"),
        params.get("language"),
        params.get("countryCode"),
        len(data.get("items") or []),
        data.get("nextCursor"),
        data.get("total"),
    )

    return {
        "items": data.get("items") or [],
        "nextCursor": data.get("nextCursor"),
        "total": data.get("total"),
    }


def fetch_complete_free_preview_catalog(
    *,
    provider: Optional[str] = None,
    language: Optional[str] = None,
    country_code: str = DEFAULT_COUNTRY_CODE,
    page_limit: int = DEFAULT_PAGE_LIMIT,
    max_pages: Optional[int] = None,
) -> FreePreviewCatalogResult:
    """
    Recorre la paginación hasta que nextCursor sea null.

    El endpoint es la única fuente de elegibilidad Free. No se consulta
    el catálogo general de certificaciones.
    """
    max_pages = max_pages or get_max_pages()
    max_pages = max(1, int(max_pages))

    all_items: List[Dict[str, Any]] = []
    cursor: Optional[str] = None
    pages = 0
    remote_total = None

    seen_cursors = set()

    with requests.Session() as session:
        while pages < max_pages:
            cursor_key = str(cursor or "__FIRST__")

            if cursor_key in seen_cursors:
                raise FreePreviewResponseError(
                    "El endpoint repitió un cursor y podría producir "
                    "un ciclo infinito."
                )

            seen_cursors.add(cursor_key)

            page = fetch_free_preview_page(
                cursor=cursor,
                provider=provider,
                language=language,
                country_code=country_code,
                limit=page_limit,
                session=session,
            )

            pages += 1
            all_items.extend(page["items"])

            if remote_total is None:
                remote_total = page.get("total")

            next_cursor = page.get("nextCursor")

            if next_cursor in (None, ""):
                break

            cursor = str(next_cursor)
        else:
            raise FreePreviewResponseError(
                "Se alcanzó MX_FREE_PREVIEW_MAX_PAGES antes de "
                "terminar la paginación."
            )

    normalized_items = normalize_free_preview_items(
        all_items,
        country_code=country_code,
        require_current_validation=True,
    )

    metadata = {
        "provider": _normalize_provider(provider),
        "language": _normalize_language(language),
        "countryCode": _normalize_country_code(
            country_code
        ),
        "remoteTotal": remote_total,
        "normalizedTotal": len(normalized_items),
        "pages": pages,
    }

    return FreePreviewCatalogResult(
        items=normalized_items,
        source="remote",
        total=len(normalized_items),
        pages=pages,
        stale=False,
        metadata=metadata,
    )


# =========================================================
# CACHE Y ÚLTIMO CATÁLOGO VÁLIDO
# =========================================================

def _cache_catalog_result(
    result: FreePreviewCatalogResult,
    *,
    provider: Optional[str],
    language: Optional[str],
    country_code: str,
) -> None:
    current_key = _catalog_cache_key(
        provider=provider,
        language=language,
        country_code=country_code,
    )

    last_valid_key = _last_valid_cache_key(
        provider=provider,
        language=language,
        country_code=country_code,
    )

    metadata_key = _metadata_cache_key(
        provider=provider,
        language=language,
        country_code=country_code,
    )

    payload = {
        "items": result.items,
        "total": result.total,
        "pages": result.pages,
        "metadata": result.metadata,
    }

    cache.set(
        current_key,
        payload,
        timeout=get_cache_timeout_seconds(),
    )

    # Último catálogo válido sin vencimiento lógico.
    cache.set(
        last_valid_key,
        payload,
        timeout=None,
    )

    cache.set(
        metadata_key,
        result.metadata,
        timeout=None,
    )


def _load_cached_catalog(
    *,
    provider: Optional[str],
    language: Optional[str],
    country_code: str,
    stale: bool,
) -> Optional[FreePreviewCatalogResult]:
    key = (
        _last_valid_cache_key(
            provider=provider,
            language=language,
            country_code=country_code,
        )
        if stale
        else _catalog_cache_key(
            provider=provider,
            language=language,
            country_code=country_code,
        )
    )

    payload = cache.get(key)

    if not isinstance(payload, Mapping):
        return None

    items = normalize_free_preview_items(
        payload.get("items") or [],
        country_code=country_code,
        require_current_validation=True,
    )

    if not items:
        return None

    return FreePreviewCatalogResult(
        items=items,
        source="cache-last-valid" if stale else "cache",
        total=len(items),
        pages=int(payload.get("pages") or 0),
        stale=stale,
        metadata=_ensure_mapping(
            payload.get("metadata")
        ),
    )


def get_free_preview_catalog(
    *,
    force_refresh: bool = False,
    provider: Optional[str] = None,
    language: Optional[str] = None,
    country_code: str = DEFAULT_COUNTRY_CODE,
    allow_stale: bool = True,
) -> FreePreviewCatalogResult:
    """
    Retorna el catálogo Free.

    Orden:
    1. cache vigente;
    2. endpoint remoto;
    3. último catálogo válido, si el remoto falla.
    """
    provider = _normalize_provider(provider)
    language = _normalize_language(language)
    country_code = _normalize_country_code(
        country_code
    )

    if not force_refresh:
        cached = _load_cached_catalog(
            provider=provider,
            language=language,
            country_code=country_code,
            stale=False,
        )

        if cached:
            return cached

    try:
        remote = fetch_complete_free_preview_catalog(
            provider=provider,
            language=language,
            country_code=country_code,
        )

        if not remote.items:
            raise FreePreviewResponseError(
                "El endpoint devolvió un catálogo Free vacío."
            )

        _cache_catalog_result(
            remote,
            provider=provider,
            language=language,
            country_code=country_code,
        )

        return remote

    except FreePreviewProviderError as exc:
        logger.exception(
            "Falló la actualización del catálogo Free."
        )

        retryable = (
            isinstance(
                exc,
                (
                    FreePreviewRequestError,
                    FreePreviewResponseError,
                ),
            )
            and (
                not isinstance(
                    exc,
                    FreePreviewHTTPError,
                )
                or exc.retryable
            )
        )

        if (
            not allow_stale
            or not retryable
        ):
            raise

        stale_result = _load_cached_catalog(
            provider=provider,
            language=language,
            country_code=country_code,
            stale=True,
        )

        if stale_result:
            logger.warning(
                "Se utilizará el último catálogo Free válido. "
                "source=%s total=%s",
                stale_result.source,
                stale_result.total,
            )
            return stale_result

        raise


def refresh_free_preview_catalog(
    *,
    provider: Optional[str] = None,
    language: Optional[str] = None,
    country_code: str = DEFAULT_COUNTRY_CODE,
) -> FreePreviewCatalogResult:
    return get_free_preview_catalog(
        force_refresh=True,
        provider=provider,
        language=language,
        country_code=country_code,
        allow_stale=False,
    )


# =========================================================
# SELECCIÓN DE EXPERIENCIAS
# =========================================================

def _stable_shuffle(
    items: Sequence[Dict[str, Any]],
    *,
    seed: Any,
) -> List[Dict[str, Any]]:
    """
    Orden pseudoaleatorio estable para que el mismo Lead reciba la
    misma selección mientras el catálogo no cambie.
    """
    copied = list(items)

    seed_text = str(seed or "topeducation-free")
    seed_digest = hashlib.sha256(
        seed_text.encode("utf-8")
    ).hexdigest()

    rng = random.Random(seed_digest)
    rng.shuffle(copied)

    return copied


def select_free_preview_courses(
    *,
    amount: int = DEFAULT_SELECTION_SIZE,
    seed: Any = None,
    excluded_id_internos: Optional[
        Iterable[str]
    ] = None,
    provider: Optional[str] = None,
    language: Optional[str] = None,
    country_code: str = DEFAULT_COUNTRY_CODE,
    force_refresh: bool = False,
) -> List[Dict[str, Any]]:
    """
    Selecciona experiencias elegibles del catálogo Free.

    - No usa el catálogo general.
    - No repite idInterno.
    - Conserva idInterno exactamente.
    - Agrega order y routeLevel para el contrato de la ruta.
    - DEFAULT_SELECTION_SIZE=3 es una decisión de producto por defecto,
      no una restricción contractual de MX.
    - El contrato permite de 1 a MAX_SELECTION_SIZE experiencias.
    """
    try:
        amount = int(amount)
    except (TypeError, ValueError):
        amount = DEFAULT_SELECTION_SIZE

    amount = max(1, min(amount, MAX_SELECTION_SIZE))

    catalog = get_free_preview_catalog(
        force_refresh=force_refresh,
        provider=provider,
        language=language,
        country_code=country_code,
        allow_stale=True,
    )

    excluded = {
        str(value)
        for value in excluded_id_internos or []
        if value not in (None, "")
    }

    available = [
        item
        for item in catalog.items
        if item["idInterno"] not in excluded
    ]

    if seed is not None:
        available = _stable_shuffle(
            available,
            seed=seed,
        )

    if len(available) < amount:
        raise FreePreviewSelectionError(
            "No existen suficientes experiencias Free elegibles. "
            f"Solicitadas: {amount}; disponibles: {len(available)}."
        )

    selected = []

    for index, item in enumerate(
        available[:amount],
        start=1,
    ):
        selected.append({
            "idInterno": item["idInterno"],
            "title": item.get("title") or "",
            "provider": item.get("provider") or "",
            "language": item.get("language") or "",
            "order": index,
            "routeLevel": 1,
            "preview": {
                "type": (
                    item.get("preview") or {}
                ).get("type"),
                "url": (
                    item.get("preview") or {}
                ).get("url"),
                "validatedAt": (
                    item.get("preview") or {}
                ).get("validatedAt"),
                "countryCode": (
                    item.get("preview") or {}
                ).get(
                    "countryCode",
                    _normalize_country_code(
                        country_code
                    ),
                ),
            },
            "available": True,
        })

    return selected


def select_free_preview_courses_for_lead(
    lead,
    *,
    amount: int = DEFAULT_SELECTION_SIZE,
    excluded_id_internos: Optional[
        Iterable[str]
    ] = None,
    force_refresh: bool = False,
) -> List[Dict[str, Any]]:
    """
    Atajo para una selección estable por Lead.
    """
    if lead is None:
        raise FreePreviewSelectionError(
            "lead es obligatorio para seleccionar la ruta Free."
        )

    seed = (
        getattr(lead, "pk", None)
        or getattr(lead, "email", None)
    )

    if seed in (None, ""):
        raise FreePreviewSelectionError(
            "El Lead debe estar guardado o tener email."
        )

    return select_free_preview_courses(
        amount=amount,
        seed=f"lead:{seed}",
        excluded_id_internos=excluded_id_internos,
        country_code=DEFAULT_COUNTRY_CODE,
        force_refresh=force_refresh,
    )