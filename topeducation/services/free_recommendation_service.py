from __future__ import annotations

import logging
from typing import Any, Dict, Optional

from django.db.models import QuerySet

from ..models import Certificaciones
from .free_course_hydrator import (
    get_hydrated_free_catalog,
)


logger = logging.getLogger(__name__)


class FreeRecommendationError(Exception):
    pass


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
    """
    Devuelve:

    1. QuerySet de certificaciones locales que están presentes
       en el catálogo Free Tier de MX.
    2. Mapa del catálogo hidratado por certificationId.

    Reglas importantes:
    - El endpoint /v1/b2c/free-preview-courses es la única
      fuente de elegibilidad Free.
    - No se infiere elegibilidad por proveedor, título,
      plataforma ni por pertenecer al catálogo general.
    - idInterno y preview se conservan desde la hidratación.
    - No existe una regla contractual de "exactamente tres".
      La cantidad que Colombia muestre o seleccione es una
      decisión de producto.
    """

    hydration = get_hydrated_free_catalog(
        force_refresh=force_refresh,
        provider=provider,
        language=language,
        country_code=country_code,
    )

    hydrated_by_certification_id: Dict[
        str,
        Dict[str, Any],
    ] = {}

    for course in hydration.courses:
        if not isinstance(course, dict):
            continue

        certification_id = course.get(
            "certificationId"
        )

        if certification_id is None:
            continue

        hydrated_by_certification_id[
            str(certification_id)
        ] = course

    certification_ids = []

    for certification_id in (
        hydrated_by_certification_id.keys()
    ):
        try:
            certification_ids.append(
                int(certification_id)
            )
        except (TypeError, ValueError):
            logger.warning(
                "CertificationId Free no numérico "
                "ignorado: %s",
                certification_id,
            )

    if not certification_ids:
        raise FreeRecommendationError(
            "No existen certificaciones locales elegibles "
            "para el catálogo Free."
        )

    queryset = (
        Certificaciones.objects
        .filter(
            id__in=certification_ids,
            vigente_certificacion=True,
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

    logger.info(
        "Queryset Free preparado. "
        "hidratados=%s queryset=%s "
        "provider=%s language=%s country=%s",
        getattr(
            hydration,
            "total_matched",
            len(
                hydrated_by_certification_id
            ),
        ),
        queryset.count(),
        provider or "*",
        language or "*",
        country_code,
    )

    return (
        queryset,
        hydrated_by_certification_id,
    )