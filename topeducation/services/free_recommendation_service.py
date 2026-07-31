from __future__ import annotations

import logging
from typing import Any, Dict, List, Optional

from django.db.models import QuerySet

from ..models import Certificaciones, LearningRouteLead
from .free_course_hydrator import get_hydrated_free_catalog


logger = logging.getLogger(__name__)


FREE_COURSES_REQUIRED = 3


class FreeRecommendationError(Exception):
    pass


def get_free_eligible_queryset(
    *,
    force_refresh: bool = False,
    provider: Optional[str] = None,
    language: Optional[str] = None,
    country_code: str = "CO",
) -> tuple[QuerySet, Dict[str, Dict[str, Any]]]:
    """
    Devuelve:

    1. QuerySet de certificaciones elegibles para Free.
    2. Mapa del catálogo hidratado por certificationId.

    El mapa permite recuperar después los datos del preview sin
    tener que consultar nuevamente el endpoint de México.
    """

    hydration = get_hydrated_free_catalog(
        force_refresh=force_refresh,
        provider=provider,
        language=language,
        country_code=country_code,
    )

    hydrated_by_certification_id: Dict[str, Dict[str, Any]] = {
        str(course["certificationId"]): course
        for course in hydration.courses
        if course.get("certificationId") is not None
    }

    certification_ids = [
        int(certification_id)
        for certification_id in hydrated_by_certification_id.keys()
    ]

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
        "Queryset Free preparado. hidratados=%s queryset=%s",
        hydration.total_matched,
        queryset.count(),
    )

    return queryset, hydrated_by_certification_id