from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Any, Dict, Iterable, List, Mapping, Optional, Sequence, Tuple

from django.db.models import Prefetch, QuerySet

from ..models import (
    Certificaciones,
    SkillsCertification,
)


logger = logging.getLogger(__name__)


# =========================================================
# CONFIGURACIÓN
# =========================================================

DEFAULT_QUERY_BATCH_SIZE = 500

EMPTY_VALUES = {
    "",
    "none",
    "null",
    "undefined",
    "n/a",
    "na",
    "-",
}


# =========================================================
# RESULTADOS
# =========================================================

@dataclass(frozen=True)
class FreeCourseHydrationResult:
    """
    Resultado completo de la hidratación del catálogo Free.

    courses:
        Cursos encontrados en Certificaciones y enriquecidos.

    unmatched_id_internos:
        IDs presentes en el catálogo Free que no existen en
        Certificaciones.

    duplicated_id_internos:
        IDs que tienen más de una coincidencia en Certificaciones.

    total_requested:
        Cantidad de IDs únicos recibidos.

    total_matched:
        Cantidad de cursos correctamente hidratados.
    """

    courses: List[Dict[str, Any]]
    unmatched_id_internos: List[str]
    duplicated_id_internos: List[str]
    total_requested: int
    total_matched: int


# =========================================================
# UTILIDADES GENERALES
# =========================================================

def _ensure_mapping(value: Any) -> Dict[str, Any]:
    if isinstance(value, Mapping):
        return dict(value)

    return {}


def _ensure_list(value: Any) -> List[Any]:
    if isinstance(value, list):
        return value

    if isinstance(value, tuple):
        return list(value)

    return []


def _clean_text(
    value: Any,
    *,
    default: str = "",
) -> str:
    """
    Limpia valores de texto y elimina marcadores como NONE o NULL.
    """

    if value is None:
        return default

    normalized = str(value).strip()

    if normalized.lower() in EMPTY_VALUES:
        return default

    return normalized


def _clean_optional_text(value: Any) -> Optional[str]:
    normalized = _clean_text(value)

    return normalized or None


def _normalize_provider(value: Any) -> str:
    return _clean_text(value).upper()


def _normalize_language(value: Any) -> str:
    return _clean_text(value).lower()


def _normalize_id_interno(value: Any) -> Optional[str]:
    """
    Conserva exactamente el idInterno recibido.

    No se transforma, no se convierte a minúsculas y no se reemplazan
    caracteres porque México utiliza este identificador de manera exacta.
    """

    if not isinstance(value, str):
        return None

    if not value.strip():
        return None

    return value


def _unique_preserving_order(
    values: Iterable[str],
) -> List[str]:
    result: List[str] = []
    seen = set()

    for value in values:
        if value in seen:
            continue

        seen.add(value)
        result.append(value)

    return result


def _chunked(
    values: Sequence[str],
    size: int,
) -> Iterable[Sequence[str]]:
    normalized_size = max(1, int(size))

    for index in range(0, len(values), normalized_size):
        yield values[index:index + normalized_size]


def _serialize_json_list(value: Any) -> List[Any]:
    """
    Garantiza que un JSONField que debería ser lista siempre termine
    representado como lista.
    """

    if isinstance(value, list):
        return value

    return []


def _serialize_json_mapping(value: Any) -> Dict[str, Any]:
    if isinstance(value, Mapping):
        return dict(value)

    return {}


def _absolute_url(
    value: Any,
    *,
    request=None,
) -> str:
    """
    Convierte una ruta relativa en una URL absoluta cuando se recibe request.

    Si imagen_final ya contiene una URL absoluta se conserva.
    """

    normalized = _clean_text(value)

    if not normalized:
        return ""

    if normalized.startswith(("http://", "https://")):
        return normalized

    if request is None:
        return normalized

    try:
        if not normalized.startswith("/"):
            normalized = f"/{normalized}"

        return request.build_absolute_uri(normalized)

    except Exception:
        logger.exception(
            "No fue posible construir la URL absoluta para %s.",
            normalized,
        )

        return normalized


# =========================================================
# NORMALIZACIÓN DEL CATÁLOGO FREE
# =========================================================

def normalize_free_catalog_items(
    items: Iterable[Any],
) -> List[Dict[str, Any]]:
    """
    Normaliza los elementos provenientes de free-preview-courses.

    Se conservan:

    - idInterno
    - title
    - provider
    - language
    - preview

    Se eliminan registros inválidos y duplicados.
    """

    normalized_items: List[Dict[str, Any]] = []
    seen_ids = set()

    for item in items or []:
        if not isinstance(item, Mapping):
            continue

        id_interno = _normalize_id_interno(
            item.get("idInterno")
            or item.get("id_interno")
        )

        if not id_interno:
            continue

        if id_interno in seen_ids:
            continue

        seen_ids.add(id_interno)

        preview = _ensure_mapping(
            item.get("preview")
        )

        normalized_items.append({
            "idInterno": id_interno,
            "title": _clean_text(item.get("title")),
            "provider": _clean_text(item.get("provider")),
            "language": _clean_text(item.get("language")),
            "preview": {
                "type": _clean_optional_text(
                    preview.get("type")
                ),
                "url": _clean_optional_text(
                    preview.get("url")
                ),
                "validatedAt": preview.get(
                    "validatedAt"
                ),
                "countryCode": _clean_optional_text(
                    preview.get("countryCode")
                ),
            },
        })

    return normalized_items


# =========================================================
# QUERYSET DE CERTIFICACIONES
# =========================================================

def get_certifications_hydration_queryset() -> QuerySet:
    """
    Queryset optimizado para hidratar cursos Free.

    select_related:
        Evita consultas adicionales para tema, plataforma,
        universidad, empresa y especialización.

    prefetch_related:
        Carga SkillsCertification y Skills en consultas agrupadas.
    """

    skills_prefetch = Prefetch(
        "skills_rel",
        queryset=(
            SkillsCertification.objects
            .select_related("skill")
            .order_by("orden", "id")
        ),
        to_attr="_hydrated_skills_rel",
    )

    return (
        Certificaciones.objects
        .filter(
            vigente_certificacion=True,
            id_interno__isnull=False,
        )
        .exclude(id_interno="")
        .select_related(
            "tema_certificacion",
            "plataforma_certificacion",
            "universidad_certificacion",
            "empresa_certificacion",
            "specialization",
        )
        .prefetch_related(
            skills_prefetch,
        )
        .order_by(
            "id_interno",
            "-id",
        )
    )


def fetch_certifications_by_internal_ids(
    id_internos: Sequence[str],
    *,
    batch_size: int = DEFAULT_QUERY_BATCH_SIZE,
) -> Dict[str, List[Certificaciones]]:
    """
    Consulta Certificaciones en lotes y las agrupa por id_interno.

    Se utiliza una lista porque id_interno actualmente tiene índice,
    pero no posee unique=True. Por tanto, es técnicamente posible que
    existan duplicados.
    """

    normalized_ids = _unique_preserving_order([
        value
        for value in (
            _normalize_id_interno(item)
            for item in id_internos
        )
        if value
    ])

    grouped: Dict[str, List[Certificaciones]] = {}

    if not normalized_ids:
        return grouped

    base_queryset = get_certifications_hydration_queryset()

    for chunk in _chunked(
        normalized_ids,
        batch_size,
    ):
        certifications = base_queryset.filter(
            id_interno__in=chunk,
        )

        for certification in certifications:
            id_interno = _normalize_id_interno(
                certification.id_interno
            )

            if not id_interno:
                continue

            grouped.setdefault(
                id_interno,
                [],
            ).append(certification)

    return grouped


# =========================================================
# SELECCIÓN CUANDO HAY IDs DUPLICADOS
# =========================================================

def _certification_match_score(
    certification: Certificaciones,
    preview_item: Mapping[str, Any],
) -> Tuple[int, int]:
    """
    Calcula cuál certificación es la mejor coincidencia cuando existen
    registros duplicados con el mismo id_interno.

    Criterios:

    1. proveedor coincidente;
    2. idioma coincidente;
    3. mapping_status válido;
    4. imagen disponible;
    5. mayor ID como desempate.
    """

    score = 0

    preview_provider = _normalize_provider(
        preview_item.get("provider")
    )

    certification_provider = _normalize_provider(
        certification.source_provider
        or (
            certification.plataforma_certificacion.nombre
            if certification.plataforma_certificacion
            else ""
        )
    )

    if (
        preview_provider
        and certification_provider
        and preview_provider == certification_provider
    ):
        score += 100

    preview_language = _normalize_language(
        preview_item.get("language")
    )

    certification_language = _normalize_language(
        certification.language_normalized
        or certification.lenguaje_certificacion
    )

    if (
        preview_language
        and certification_language
        and preview_language == certification_language
    ):
        score += 50

    mapping_status = _clean_text(
        certification.mapping_status
    ).lower()

    if mapping_status not in {
        "",
        "uncategorized",
        "unmapped",
        "pending",
    }:
        score += 20

    if _clean_text(certification.imagen_final):
        score += 10

    if certification.tema_certificacion_id:
        score += 5

    if certification.plataforma_certificacion_id:
        score += 5

    return score, certification.id


def choose_best_certification(
    certifications: Sequence[Certificaciones],
    preview_item: Mapping[str, Any],
) -> Optional[Certificaciones]:
    if not certifications:
        return None

    return max(
        certifications,
        key=lambda certification: (
            _certification_match_score(
                certification,
                preview_item,
            )
        ),
    )


# =========================================================
# SERIALIZACIÓN DE RELACIONES
# =========================================================

def serialize_topic(
    certification: Certificaciones,
) -> Optional[Dict[str, Any]]:
    topic = certification.tema_certificacion

    if topic is None:
        return None

    return {
        "id": topic.id,
        "name": _clean_text(topic.nombre),
        "translation": _clean_text(topic.translate),
        "type": _clean_text(topic.tem_type),
        "color": _clean_text(topic.tem_col),
        "image": _clean_text(topic.tem_img),
        "status": _clean_text(topic.tem_est),
        "parentId": topic.parent_id,
    }


def serialize_platform(
    certification: Certificaciones,
    *,
    request=None,
) -> Optional[Dict[str, Any]]:
    platform = certification.plataforma_certificacion

    if platform is None:
        return None

    return {
        "id": platform.id,
        "name": _clean_text(platform.nombre),
        "image": _absolute_url(
            platform.plat_img,
            request=request,
        ),
        "icon": _absolute_url(
            platform.plat_ico,
            request=request,
        ),
    }


def serialize_university(
    certification: Certificaciones,
    *,
    request=None,
) -> Optional[Dict[str, Any]]:
    university = certification.universidad_certificacion

    if university is None:
        return None

    return {
        "id": university.id,
        "name": _clean_text(university.nombre),
        "image": _absolute_url(
            university.univ_img,
            request=request,
        ),
        "icon": _absolute_url(
            university.univ_ico,
            request=request,
        ),
        "flag": _absolute_url(
            university.univ_fla,
            request=request,
        ),
        "ranking": _clean_text(
            university.univ_top
        ),
        "description": _clean_text(
            university.descripcion_institucion
        ),
    }


def serialize_company(
    certification: Certificaciones,
    *,
    request=None,
) -> Optional[Dict[str, Any]]:
    company = certification.empresa_certificacion

    if company is None:
        return None

    return {
        "id": company.id,
        "name": _clean_text(company.nombre),
        "image": _absolute_url(
            company.empr_img,
            request=request,
        ),
        "icon": _absolute_url(
            company.empr_ico,
            request=request,
        ),
        "ranking": _clean_text(
            company.empr_top
        ),
        "description": _clean_text(
            company.descripcion_institucion
        ),
    }


def serialize_specialization(
    certification: Certificaciones,
) -> Optional[Dict[str, Any]]:
    specialization = certification.specialization

    if specialization is not None:
        return {
            "id": specialization.id,
            "externalId": _clean_text(
                specialization.specialization_id
            ),
            "name": _clean_text(
                specialization.specialization_name
            ),
            "provider": _clean_text(
                specialization.provider
            ),
        }

    external_id = _clean_text(
        certification.specialization_id_external
    )

    external_name = _clean_text(
        certification.specialization_name_external
    )

    if not external_id and not external_name:
        return None

    return {
        "id": None,
        "externalId": external_id,
        "name": external_name,
        "provider": _clean_text(
            certification.source_provider
        ),
    }


def serialize_skills(
    certification: Certificaciones,
    *,
    request=None,
) -> List[Dict[str, Any]]:
    result: List[Dict[str, Any]] = []

    links = getattr(
        certification,
        "_hydrated_skills_rel",
        [],
    )

    seen_skill_ids = set()

    for link in links:
        skill = link.skill

        if skill is None:
            continue

        if skill.id in seen_skill_ids:
            continue

        seen_skill_ids.add(skill.id)

        result.append({
            "id": skill.id,
            "name": _clean_text(skill.nombre),
            "translation": _clean_text(
                skill.translate
            ),
            "description": _clean_text(
                skill.descripcion
            ),
            "slug": _clean_text(skill.slug),
            "color": _clean_text(
                skill.skill_col
            ),
            "type": _clean_text(
                skill.skill_type
            ),
            "image": _absolute_url(
                skill.skill_img,
                request=request,
            ),
            "icon": _absolute_url(
                skill.skill_ico,
                request=request,
            ),
            "parentId": skill.parent_id,
            "externalId": _clean_text(
                skill.external_skill_id
            ),
            "sourceProvider": _clean_text(
                skill.source_provider
            ),
            "order": link.orden,
        })

    return result


# =========================================================
# HIDRATACIÓN DE UN CURSO
# =========================================================

def hydrate_free_course(
    preview_item: Mapping[str, Any],
    certification: Certificaciones,
    *,
    request=None,
) -> Dict[str, Any]:
    """
    Une el elemento de free-preview-courses con Certificaciones.

    El resultado es la representación canónica que luego puede utilizarse
    para:

    - mostrar recomendaciones en frontend;
    - guardar LearningRouteItem;
    - crear el snapshot;
    - construir el payload hacia México.
    """

    preview = _ensure_mapping(
        preview_item.get("preview")
    )

    platform = serialize_platform(
        certification,
        request=request,
    )

    university = serialize_university(
        certification,
        request=request,
    )

    company = serialize_company(
        certification,
        request=request,
    )

    topic = serialize_topic(certification)

    skills = serialize_skills(
        certification,
        request=request,
    )

    # Para Free, el provider del catálogo Free es la referencia
    # contractual. La información local se utiliza únicamente
    # como respaldo para visualización/hidratación.
    source_provider = (
        _clean_text(preview_item.get("provider"))
        or _clean_text(certification.source_provider)
        or (
            platform.get("name")
            if platform
            else ""
        )
    )

    language = (
        _clean_text(certification.language_normalized)
        or _clean_text(
            certification.lenguaje_certificacion
        )
        or _clean_text(
            preview_item.get("language")
        )
    )

    title = (
        _clean_text(certification.nombre)
        or _clean_text(preview_item.get("title"))
    )

    return {
        # =================================================
        # IDENTIFICADORES
        # =================================================
        "certificationId": certification.id,

        # El identificador contractual debe conservarse exactamente
        # como llegó desde /v1/b2c/free-preview-courses.
        # La certificación local sirve para encontrar/enriquecer
        # el registro, pero no reemplaza el identificador de MX.
        "idInterno": _normalize_id_interno(
            preview_item.get("idInterno")
        ),
        "slug": _clean_text(certification.slug),

        # =================================================
        # INFORMACIÓN PRINCIPAL
        # =================================================
        "title": title,
        "description": _clean_text(
            certification.metadescripcion_certificacion
        ),
        "keywords": _clean_text(
            certification.palabra_clave_certificacion
        ),
        "image": _absolute_url(
            certification.imagen_final,
            request=request,
        ),
        "video": _clean_text(
            certification.video_certificacion
        ),
        "originalUrl": _clean_text(
            certification.url_certificacion_original
        ),

        # =================================================
        # CLASIFICACIÓN
        # =================================================
        "level": _clean_text(
            certification.nivel_certificacion
        ),
        "duration": _clean_text(
            certification.tiempo_certificacion
        ),
        "language": language,
        "type": _clean_text(
            certification.tipo_certificacion
        ),
        "country": _clean_text(
            certification.country,
            default="Global",
        ),
        "region": _clean_text(
            certification.region,
            default="Global",
        ),
        "mappingStatus": _clean_text(
            certification.mapping_status
        ),
        "isActive": bool(
            certification.vigente_certificacion
        ),

        # =================================================
        # PROVEEDOR Y ENTIDADES
        # =================================================
        "provider": source_provider,
        "platform": platform,
        "university": university,
        "company": company,
        "specialization": serialize_specialization(
            certification
        ),

        # =================================================
        # TEMAS Y HABILIDADES
        # =================================================
        "topic": topic,
        "topics": [topic] if topic else [],
        "skills": skills,
        "skillsInternal": _serialize_json_list(
            certification.skills_internal_json
        ),
        "subskillsInternal": _serialize_json_list(
            certification.subskills_internal_json
        ),

        # =================================================
        # CONTENIDO ACADÉMICO
        # =================================================
        "learning": _clean_text(
            certification.aprendizaje_certificacion
        ),
        "experience": _clean_text(
            certification.experiencia_certificacion
        ),
        "content": _clean_text(
            certification.contenido_certificacion
        ),
        "modules": _clean_text(
            certification.modulos_certificacion
        ),
        "instructors": _clean_text(
            certification.instructores_certificacion
        ),
        "testimonials": _clean_text(
            certification.testimonios_certificacion
        ),

        # =================================================
        # PREVIEW FREE
        # =================================================
        "preview": {
            "type": _clean_optional_text(
                preview.get("type")
            ),
            "url": _clean_optional_text(
                preview.get("url")
            ),
            "validatedAt": preview.get(
                "validatedAt"
            ),
            "countryCode": _clean_optional_text(
                preview.get("countryCode")
            ),
            "available": bool(
                preview.get("url")
            ),
        },

        # =================================================
        # DATOS ORIGINALES PARA AUDITORÍA
        # =================================================
        "freeCatalog": {
            "idInterno": _normalize_id_interno(
                preview_item.get("idInterno")
            ),
            "title": _clean_text(
                preview_item.get("title")
            ),
            "provider": _clean_text(
                preview_item.get("provider")
            ),
            "language": _clean_text(
                preview_item.get("language")
            ),
            "preview": {
                "type": _clean_optional_text(
                    preview.get("type")
                ),
                "url": _clean_optional_text(
                    preview.get("url")
                ),
                "validatedAt": preview.get(
                    "validatedAt"
                ),
                "countryCode": _clean_optional_text(
                    preview.get("countryCode")
                ),
            },
        },
        "reconciliation": _serialize_json_mapping(
            certification.reconciliation_snapshot
        ),
    }


# =========================================================
# HIDRATACIÓN MASIVA
# =========================================================

def hydrate_free_preview_courses(
    preview_items: Iterable[Any],
    *,
    request=None,
    batch_size: int = DEFAULT_QUERY_BATCH_SIZE,
) -> FreeCourseHydrationResult:
    """
    Hidrata masivamente los cursos del catálogo Free.

    Realiza consultas en lote; no ejecuta una consulta por curso.
    """

    normalized_items = normalize_free_catalog_items(
        preview_items
    )

    id_internos = [
        item["idInterno"]
        for item in normalized_items
    ]

    grouped_certifications = (
        fetch_certifications_by_internal_ids(
            id_internos,
            batch_size=batch_size,
        )
    )

    hydrated_courses: List[Dict[str, Any]] = []
    unmatched_ids: List[str] = []
    duplicated_ids: List[str] = []

    for preview_item in normalized_items:
        id_interno = preview_item["idInterno"]

        matches = grouped_certifications.get(
            id_interno,
            [],
        )

        if not matches:
            unmatched_ids.append(id_interno)
            continue

        if len(matches) > 1:
            duplicated_ids.append(id_interno)

        certification = choose_best_certification(
            matches,
            preview_item,
        )

        if certification is None:
            unmatched_ids.append(id_interno)
            continue

        hydrated_courses.append(
            hydrate_free_course(
                preview_item,
                certification,
                request=request,
            )
        )

    duplicated_ids = _unique_preserving_order(
        duplicated_ids
    )

    unmatched_ids = _unique_preserving_order(
        unmatched_ids
    )

    logger.info(
        (
            "Catálogo Free hidratado. "
            "solicitados=%s coincidentes=%s "
            "sin_coincidencia=%s duplicados=%s"
        ),
        len(normalized_items),
        len(hydrated_courses),
        len(unmatched_ids),
        len(duplicated_ids),
    )

    return FreeCourseHydrationResult(
        courses=hydrated_courses,
        unmatched_id_internos=unmatched_ids,
        duplicated_id_internos=duplicated_ids,
        total_requested=len(normalized_items),
        total_matched=len(hydrated_courses),
    )


# =========================================================
# FUNCIONES DE CONVENIENCIA
# =========================================================

def hydrate_free_preview_catalog_result(
    catalog_result,
    *,
    request=None,
    batch_size: int = DEFAULT_QUERY_BATCH_SIZE,
) -> FreeCourseHydrationResult:
    """
    Permite pasar directamente el FreePreviewCatalogResult retornado
    por get_free_preview_catalog().
    """

    items = getattr(
        catalog_result,
        "items",
        [],
    )

    return hydrate_free_preview_courses(
        items,
        request=request,
        batch_size=batch_size,
    )


def get_hydrated_free_catalog(
    *,
    force_refresh: bool = False,
    provider: Optional[str] = None,
    language: Optional[str] = None,
    country_code: str = "CO",
    request=None,
) -> FreeCourseHydrationResult:
    """
    Consulta el catálogo Free y devuelve los cursos enriquecidos.

    La importación interna evita dependencias circulares.
    """

    from .free_preview_provider import (
        get_free_preview_catalog,
    )

    catalog = get_free_preview_catalog(
        force_refresh=force_refresh,
        provider=provider,
        language=language,
        country_code=country_code,
        allow_stale=True,
    )

    return hydrate_free_preview_catalog_result(
        catalog,
        request=request,
    )


def get_free_eligible_certification_ids(
    preview_items: Iterable[Any],
) -> List[int]:
    """
    Devuelve solamente los IDs locales de Certificaciones disponibles
    para el catálogo Free.
    """

    result = hydrate_free_preview_courses(
        preview_items
    )

    return [
        int(course["certificationId"])
        for course in result.courses
        if course.get("certificationId") is not None
    ]


def get_free_eligible_internal_ids(
    preview_items: Iterable[Any],
) -> List[str]:
    """
    Devuelve los idInterno que existen tanto en el catálogo Free
    como en Certificaciones.
    """

    result = hydrate_free_preview_courses(
        preview_items
    )

    return [
        course["idInterno"]
        for course in result.courses
        if course.get("idInterno")
    ]