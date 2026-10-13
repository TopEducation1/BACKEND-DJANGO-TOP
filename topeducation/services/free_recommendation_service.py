from __future__ import annotations

import json
import logging
from typing import Any, Dict, Optional

from django.db.models import QuerySet

from ..models import Certificaciones

from .free_course_hydrator import (
    get_hydrated_free_catalog,
)

from .free_preview_provider import (
    get_free_preview_last_attempt_diagnostics,
    get_last_free_preview_remote_response,
)


logger = logging.getLogger(__name__)


class FreeRecommendationError(Exception):
    pass


def _get_free_provider_debug(
    *,
    provider: Optional[str] = None,
    language: Optional[str] = None,
    country_code: str = "CO",
) -> Dict[str, Any]:
    """
    Recupera la última respuesta REAL recibida desde
    el endpoint Free de MX junto con el diagnóstico
    de normalización.

    Se usa únicamente para diagnóstico.
    """

    # ========================================================
    # RESPUESTA CON LOS MISMOS FILTROS
    # ========================================================

    provider_response = (
        get_last_free_preview_remote_response(
            provider=provider,
            language=language,
            country_code=country_code,
        )
    )

    diagnostics = (
        get_free_preview_last_attempt_diagnostics(
            provider=provider,
            language=language,
            country_code=country_code,
        )
    )

    # ========================================================
    # FALLBACK
    # Algunas rutas consultan el catálogo general sin language.
    # ========================================================

    if not provider_response:

        provider_response = (
            get_last_free_preview_remote_response(
                provider=provider,
                language=None,
                country_code=country_code,
            )
        )

    if not diagnostics:

        diagnostics = (
            get_free_preview_last_attempt_diagnostics(
                provider=provider,
                language=None,
                country_code=country_code,
            )
        )

    # ========================================================
    # SEGUNDO FALLBACK
    # Catálogo completamente general.
    # ========================================================

    if not provider_response:

        provider_response = (
            get_last_free_preview_remote_response(
                provider=None,
                language=None,
                country_code=country_code,
            )
        )

    if not diagnostics:

        diagnostics = (
            get_free_preview_last_attempt_diagnostics(
                provider=None,
                language=None,
                country_code=country_code,
            )
        )

    return {
        "provider_response":
            provider_response
            or None,

        "diagnostics":
            diagnostics
            or None,
    }


def get_free_eligible_queryset(
    *,
    force_refresh: bool = False,
    provider: Optional[str] = None,
    language: Optional[str] = None,
    country_code: str = "CO",
) -> tuple[
    QuerySet,
    Dict[str, Dict[str, Any]],
]:

    # ========================================================
    # HIDRATAR CATÁLOGO FREE
    # ========================================================

    hydration = (
        get_hydrated_free_catalog(
            force_refresh=
                force_refresh,

            provider=
                provider,

            language=
                language,

            country_code=
                country_code,
        )
    )

    # ========================================================
    # INDEXAR CURSOS HIDRATADOS
    # ========================================================

    hydrated_by_certification_id: Dict[
        str,
        Dict[str, Any],
    ] = {}

    for course in (
        hydration.courses
        or []
    ):

        if not isinstance(
            course,
            dict,
        ):
            continue

        certification_id = (
            course.get(
                "certificationId"
            )
        )

        if certification_id is None:
            continue

        certification_id_str = str(
            certification_id
        ).strip()

        if not certification_id_str:
            continue

        hydrated_by_certification_id[
            certification_id_str
        ] = course

    # ========================================================
    # IDS DE CERTIFICACIONES LOCALES
    # ========================================================

    certification_ids = []

    for certification_id in (
        hydrated_by_certification_id.keys()
    ):

        try:

            certification_ids.append(
                int(
                    certification_id
                )
            )

        except (
            TypeError,
            ValueError,
        ):

            logger.warning(
                (
                    "CertificationId Free "
                    "no numérico ignorado: %s"
                ),
                certification_id,
            )

    # ========================================================
    # NO HAY CERTIFICACIONES LOCALES
    # ========================================================

    if not certification_ids:

        provider_debug = (
            _get_free_provider_debug(
                provider=
                    provider,

                language=
                    language,

                country_code=
                    country_code,
            )
        )

        # ----------------------------------------------------
        # LOG COMPLETO
        # ----------------------------------------------------

        logger.error(
            (
                "No existen certificaciones locales "
                "elegibles para el catálogo Free. "
                "provider=%s "
                "language=%s "
                "country=%s "
                "hydration_courses=%s "
                "provider_debug=%s"
            ),
            provider or "*",
            language or "*",
            country_code,
            len(
                hydration.courses
                or []
            ),
            json.dumps(
                provider_debug,
                ensure_ascii=False,
                default=str,
            ),
        )

        # ----------------------------------------------------
        # RESPUESTA QUE LLEGARÁ AL NETWORK
        # ----------------------------------------------------

        error_payload = {
            "error":
                "free_catalog_without_local_matches",

            "message":
                (
                    "No existen certificaciones locales "
                    "elegibles para el catálogo Free."
                ),

            "provider":
                provider
                or None,

            "language":
                language
                or None,

            "countryCode":
                country_code,

            "hydrationCourses":
                len(
                    hydration.courses
                    or []
                ),

            # Respuesta REAL del endpoint MX
            "providerDebug":
                provider_debug,
        }

        raise FreeRecommendationError(
            json.dumps(
                error_payload,
                ensure_ascii=False,
                default=str,
            )
        )

    # ========================================================
    # QUERYSET LOCAL
    # ========================================================

    queryset = (
        Certificaciones.objects
        .filter(
            id__in=
                certification_ids,

            vigente_certificacion=
                True,
        )
        .select_related(
            "tema_certificacion",
            "plataforma_certificacion",
            "universidad_certificacion",
            "empresa_certificacion",
            "specialization",
        )
        .prefetch_related(
            "skills_rel__skill",
        )
    )

    # ========================================================
    # LOG
    # ========================================================

    logger.info(
        (
            "Queryset Free preparado. "
            "hidratados=%s "
            "ids_locales=%s "
            "provider=%s "
            "language=%s "
            "country=%s"
        ),
        getattr(
            hydration,
            "total_matched",
            len(
                hydrated_by_certification_id
            ),
        ),
        len(
            certification_ids
        ),
        provider or "*",
        language or "*",
        country_code,
    )

    # ========================================================
    # RESPONSE
    # ========================================================

    return (
        queryset,
        hydrated_by_certification_id,
    )