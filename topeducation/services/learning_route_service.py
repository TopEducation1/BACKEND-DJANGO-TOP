from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, Iterable, List, Optional, Sequence

from django.db import IntegrityError, transaction
from django.db.models import Max
from django.utils import timezone

from topeducation.models import (
    Certificaciones,
    LearningRouteItem,
    LearningRouteLead,
    LearningRouteSnapshot,
)


from topeducation.services.free_preview_provider import (
    FreePreviewProviderError,
    FreePreviewSelectionError,
    select_free_preview_courses_for_lead,
)

DEFAULT_ROUTE_MODE = "SNAPSHOT"
DEFAULT_ROUTE_SOURCE = "COLOMBIA"
DEFAULT_ROUTE_LEVEL = 1


# =========================================================
# EXCEPCIONES
# =========================================================

class LearningRouteServiceError(Exception):
    """Error base del servicio de rutas de aprendizaje."""


class InvalidLearningRouteError(LearningRouteServiceError):
    """La información suministrada para construir la ruta no es válida."""


class LearningRouteCourseNotFoundError(LearningRouteServiceError):
    """No fue posible identificar un curso solicitado."""


class LearningRouteVersionConflictError(LearningRouteServiceError):
    """Se produjo un conflicto al crear una nueva versión."""


# =========================================================
# ESTRUCTURAS INTERNAS
# =========================================================

@dataclass
class NormalizedRouteCourse:
    id_interno: str
    certification: Optional[Certificaciones]
    title: str
    provider: str
    language: str
    order: int
    route_level: int
    preview_type: Optional[str]
    preview_url: Optional[str]
    preview_validated_at: Optional[Any]
    preview_country_code: Optional[str]
    is_available: bool
    raw_payload: Dict[str, Any]


# =========================================================
# UTILIDADES
# =========================================================

def normalize_string(value: Any) -> str:
    return str(value or "").strip()


def normalize_optional_string(value: Any) -> Optional[str]:
    normalized = normalize_string(value)
    return normalized or None


def normalize_id_interno(value: Any) -> str:
    return normalize_string(value)


def normalize_positive_integer(
    value: Any,
    *,
    default: int = 1,
) -> int:
    try:
        normalized = int(value)
    except (TypeError, ValueError):
        return default

    return normalized if normalized > 0 else default


def normalize_boolean(
    value: Any,
    *,
    default: bool = True,
) -> bool:
    if value is None:
        return default

    if isinstance(value, bool):
        return value

    if isinstance(value, int):
        return value != 0

    normalized = str(value).strip().lower()

    if normalized in {"true", "1", "yes", "si", "sí", "active"}:
        return True

    if normalized in {"false", "0", "no", "inactive"}:
        return False

    return default


def normalize_provider(value: Any) -> str:
    return normalize_string(value)


def normalize_language(value: Any) -> str:
    return normalize_string(value)


def normalize_country_code(value: Any) -> Optional[str]:
    normalized = normalize_string(value).upper()

    if not normalized:
        return None

    return normalized[:2]


def ensure_dict(value: Any) -> Dict[str, Any]:
    return value if isinstance(value, dict) else {}


def get_first_value(
    data: Dict[str, Any],
    *keys: str,
) -> Any:
    for key in keys:
        value = data.get(key)

        if value not in (None, ""):
            return value

    return None


def get_related_provider_name(
    certification: Optional[Certificaciones],
) -> str:
    if certification is None:
        return ""

    source_provider = normalize_string(
        getattr(certification, "source_provider", None)
    )

    if source_provider:
        return source_provider

    plataforma = getattr(
        certification,
        "plataforma_certificacion",
        None,
    )

    if plataforma:
        return normalize_string(
            getattr(plataforma, "nombre", None)
        )

    return ""


def get_certification_language(
    certification: Optional[Certificaciones],
) -> str:
    if certification is None:
        return ""

    return normalize_string(
        getattr(certification, "language_normalized", None)
        or getattr(
            certification,
            "lenguaje_certificacion",
            None,
        )
    )


def get_certification_title(
    certification: Optional[Certificaciones],
) -> str:
    if certification is None:
        return ""

    return normalize_string(
        getattr(certification, "nombre", None)
    )


# =========================================================
# CONSULTAS
# =========================================================

def get_current_route_snapshot(
    lead: LearningRouteLead,
    *,
    for_update: bool = False,
) -> Optional[LearningRouteSnapshot]:
    """
    Retorna el snapshot vigente de un Lead.

    Si por algún error histórico existen varios marcados como actuales,
    toma el de mayor versión.
    """
    queryset = LearningRouteSnapshot.objects.filter(
        lead=lead,
        is_current=True,
    ).order_by(
        "-version",
        "-id",
    )

    if for_update:
        queryset = queryset.select_for_update()

    snapshot = queryset.first()

    if snapshot:
        return snapshot

    fallback = LearningRouteSnapshot.objects.filter(
        lead=lead,
    ).order_by(
        "-version",
        "-id",
    )

    if for_update:
        fallback = fallback.select_for_update()

    return fallback.first()


def get_route_snapshot_by_version(
    lead: LearningRouteLead,
    version: int,
) -> Optional[LearningRouteSnapshot]:
    return (
        LearningRouteSnapshot.objects
        .filter(
            lead=lead,
            version=version,
        )
        .prefetch_related("courses")
        .first()
    )


def get_route_history(
    lead: LearningRouteLead,
):
    return (
        LearningRouteSnapshot.objects
        .filter(lead=lead)
        .prefetch_related("courses")
        .order_by("-version", "-id")
    )


def get_next_route_version(
    lead: LearningRouteLead,
) -> int:
    current_max = (
        LearningRouteSnapshot.objects
        .filter(lead=lead)
        .aggregate(max_version=Max("version"))
        .get("max_version")
    )

    lead_version = normalize_positive_integer(
        getattr(lead, "route_version", 1),
        default=1,
    )

    if current_max is None:
        return lead_version

    return max(int(current_max), lead_version) + 1


# =========================================================
# RESOLUCIÓN DE CERTIFICACIONES
# =========================================================

def find_certification_by_id_interno(
    id_interno: str,
) -> Optional[Certificaciones]:
    normalized = normalize_id_interno(id_interno)

    if not normalized:
        return None

    return (
        Certificaciones.objects
        .select_related("plataforma_certificacion")
        .filter(
            id_interno=normalized,
            vigente_certificacion=True,
        )
        .order_by("-id")
        .first()
    )


def find_certification_from_course_data(
    course_data: Dict[str, Any],
) -> Optional[Certificaciones]:
    """
    Prioridad:
    1. certification_id
    2. id_interno
    """
    certification_id = get_first_value(
        course_data,
        "certification_id",
        "certificacion_id",
        "certificationId",
        "id",
    )

    if certification_id not in (None, ""):
        try:
            certification = (
                Certificaciones.objects
                .select_related("plataforma_certificacion")
                .filter(
                    pk=int(certification_id),
                    vigente_certificacion=True,
                )
                .first()
            )

            if certification:
                return certification
        except (TypeError, ValueError):
            pass

    id_interno = get_first_value(
        course_data,
        "idInterno",
        "id_interno",
        "internalId",
        "internal_id",
    )

    if id_interno:
        return find_certification_by_id_interno(
            str(id_interno)
        )

    return None


# =========================================================
# NORMALIZACIÓN DE CURSOS
# =========================================================

def normalize_route_course(
    course: Any,
    *,
    default_order: int,
    default_route_level: int = DEFAULT_ROUTE_LEVEL,
    require_certification: bool = False,
) -> NormalizedRouteCourse:
    """
    Admite:
    - instancia de Certificaciones;
    - instancia de LearningRouteItem;
    - diccionario proveniente del frontend;
    - diccionario proveniente de recommended_certifications;
    - diccionario proveniente del catálogo Free.
    """
    if isinstance(course, Certificaciones):
        certification = course
        id_interno = normalize_id_interno(
            certification.id_interno
        )

        if not id_interno:
            raise InvalidLearningRouteError(
                f"La certificación {certification.pk} no tiene id_interno."
            )

        return NormalizedRouteCourse(
            id_interno=id_interno,
            certification=certification,
            title=get_certification_title(certification),
            provider=get_related_provider_name(certification),
            language=get_certification_language(certification),
            order=default_order,
            route_level=default_route_level,
            preview_type=None,
            preview_url=None,
            preview_validated_at=None,
            preview_country_code=None,
            is_available=True,
            raw_payload={
                "certificationId": certification.pk,
                "idInterno": id_interno,
            },
        )

    if isinstance(course, LearningRouteItem):
        return NormalizedRouteCourse(
            id_interno=normalize_id_interno(
                course.id_interno
            ),
            certification=course.certification,
            title=normalize_string(course.title),
            provider=normalize_provider(course.provider),
            language=normalize_language(course.language),
            order=normalize_positive_integer(
                course.order,
                default=default_order,
            ),
            route_level=normalize_positive_integer(
                course.route_level,
                default=default_route_level,
            ),
            preview_type=normalize_optional_string(
                course.preview_type
            ),
            preview_url=normalize_optional_string(
                course.preview_url
            ),
            preview_validated_at=course.preview_validated_at,
            preview_country_code=normalize_country_code(
                course.preview_country_code
            ),
            is_available=bool(course.is_available),
            raw_payload=ensure_dict(course.raw_payload),
        )

    if not isinstance(course, dict):
        raise InvalidLearningRouteError(
            "Cada curso debe ser un diccionario, una certificación "
            "o un LearningRouteItem."
        )

    data = course
    certification = find_certification_from_course_data(data)

    id_interno = normalize_id_interno(
        get_first_value(
            data,
            "idInterno",
            "id_interno",
            "internalId",
            "internal_id",
        )
        or getattr(certification, "id_interno", None)
    )

    if not id_interno:
        raise InvalidLearningRouteError(
            "Uno de los cursos no contiene idInterno."
        )

    if require_certification and certification is None:
        raise LearningRouteCourseNotFoundError(
            f"No se encontró la certificación con idInterno "
            f"'{id_interno}'."
        )

    preview_data = ensure_dict(
        data.get("preview")
    )

    title = normalize_string(
        get_first_value(
            data,
            "title",
            "nombre",
            "name",
        )
        or get_certification_title(certification)
    )

    provider = normalize_provider(
        get_first_value(
            data,
            "provider",
            "source_provider",
            "sourceProvider",
            "plataforma",
        )
        or get_related_provider_name(certification)
    )

    language = normalize_language(
        get_first_value(
            data,
            "language",
            "lenguaje",
            "language_normalized",
        )
        or get_certification_language(certification)
    )

    order = normalize_positive_integer(
        get_first_value(
            data,
            "order",
            "orden",
            "position",
            "positionIndex",
        ),
        default=default_order,
    )

    route_level = normalize_positive_integer(
        get_first_value(
            data,
            "routeLevel",
            "route_level",
            "level",
            "nivel_ruta",
        ),
        default=default_route_level,
    )

    preview_type = normalize_optional_string(
        get_first_value(
            preview_data,
            "type",
            "previewType",
            "preview_type",
        )
        or get_first_value(
            data,
            "previewType",
            "preview_type",
        )
    )

    preview_url = normalize_optional_string(
        get_first_value(
            preview_data,
            "url",
            "previewUrl",
            "preview_url",
        )
        or get_first_value(
            data,
            "previewUrl",
            "preview_url",
        )
    )

    preview_validated_at = (
        get_first_value(
            preview_data,
            "validatedAt",
            "previewValidatedAt",
            "preview_validated_at",
        )
        or get_first_value(
            data,
            "previewValidatedAt",
            "preview_validated_at",
        )
    )

    preview_country_code = normalize_country_code(
        get_first_value(
            preview_data,
            "countryCode",
            "country_code",
        )
        or get_first_value(
            data,
            "previewCountryCode",
            "preview_country_code",
            "countryCode",
        )
    )

    is_available = normalize_boolean(
        get_first_value(
            data,
            "available",
            "is_available",
            "isAvailable",
            "active",
        ),
        default=True,
    )

    return NormalizedRouteCourse(
        id_interno=id_interno,
        certification=certification,
        title=title,
        provider=provider,
        language=language,
        order=order,
        route_level=route_level,
        preview_type=preview_type,
        preview_url=preview_url,
        preview_validated_at=preview_validated_at,
        preview_country_code=preview_country_code,
        is_available=is_available,
        raw_payload=data.copy(),
    )


def normalize_route_courses(
    courses: Iterable[Any],
    *,
    require_certification: bool = False,
) -> List[NormalizedRouteCourse]:
    normalized_courses: List[NormalizedRouteCourse] = []
    seen_ids = set()

    for index, course in enumerate(courses or [], start=1):
        normalized = normalize_route_course(
            course,
            default_order=index,
            require_certification=require_certification,
        )

        if normalized.id_interno in seen_ids:
            raise InvalidLearningRouteError(
                f"El curso '{normalized.id_interno}' está repetido "
                "dentro de la misma ruta."
            )

        seen_ids.add(normalized.id_interno)
        normalized_courses.append(normalized)

    if not normalized_courses:
        raise InvalidLearningRouteError(
            "La ruta debe contener al menos un curso."
        )

    normalized_courses.sort(
        key=lambda item: (
            item.route_level,
            item.order,
            item.id_interno,
        )
    )

    # Normalizamos el orden dentro de cada nivel para evitar
    # colisiones con uq_route_level_order.
    counters_by_level: Dict[int, int] = {}

    for item in normalized_courses:
        level = item.route_level
        counters_by_level[level] = (
            counters_by_level.get(level, 0) + 1
        )
        item.order = counters_by_level[level]

    return normalized_courses


# =========================================================
# SERIALIZACIÓN
# =========================================================

def serialize_route_item(
    item: LearningRouteItem,
) -> Dict[str, Any]:
    data = {
        "idInterno": item.id_interno,
        "order": item.order,
        "routeLevel": item.route_level,
        "title": item.title,
        "provider": item.provider,
        "language": item.language,
        "available": item.is_available,
    }

    if (
        item.preview_type
        or item.preview_url
        or item.preview_validated_at
        or item.preview_country_code
    ):
        data["preview"] = {
            "type": item.preview_type,
            "url": item.preview_url,
            "validatedAt": (
                item.preview_validated_at.isoformat()
                if item.preview_validated_at
                else None
            ),
            "countryCode": item.preview_country_code,
        }

    return data


def serialize_route_snapshot(
    snapshot: LearningRouteSnapshot,
) -> Dict[str, Any]:
    items = (
        snapshot.courses
        .select_related("certification")
        .order_by(
            "route_level",
            "order",
            "id",
        )
    )

    return {
        "id": snapshot.pk,
        "leadId": snapshot.lead_id,
        "version": snapshot.version,
        "mode": snapshot.mode,
        "isCurrent": snapshot.is_current,
        "source": snapshot.source,
        "changeReason": snapshot.change_reason,
        "createdByEventId": snapshot.created_by_event_id,
        "metadata": snapshot.metadata or {},
        "courses": [
            serialize_route_item(item)
            for item in items
        ],
        "createdAt": snapshot.created_at.isoformat(),
        "updatedAt": snapshot.updated_at.isoformat(),
    }


# =========================================================
# PERSISTENCIA
# =========================================================

def create_route_items(
    *,
    snapshot: LearningRouteSnapshot,
    normalized_courses: Sequence[NormalizedRouteCourse],
) -> List[LearningRouteItem]:
    items = [
        LearningRouteItem(
            route=snapshot,
            certification=course.certification,
            id_interno=course.id_interno,
            title=course.title,
            provider=course.provider,
            language=course.language,
            order=course.order,
            route_level=course.route_level,
            preview_type=course.preview_type,
            preview_url=course.preview_url,
            preview_validated_at=course.preview_validated_at,
            preview_country_code=course.preview_country_code,
            is_available=course.is_available,
            raw_payload=course.raw_payload,
        )
        for course in normalized_courses
    ]

    return LearningRouteItem.objects.bulk_create(
        items,
        batch_size=100,
    )


def build_legacy_recommendations(
    normalized_courses: Sequence[NormalizedRouteCourse],
) -> List[Dict[str, Any]]:
    """
    Mantiene temporalmente recommended_certifications sincronizado
    para no romper las vistas antiguas.
    """
    result = []

    for course in normalized_courses:
        result.append({
            "idInterno": course.id_interno,
            "id_interno": course.id_interno,
            "certification_id": (
                course.certification.pk
                if course.certification
                else None
            ),
            "title": course.title,
            "nombre": course.title,
            "provider": course.provider,
            "language": course.language,
            "order": course.order,
            "routeLevel": course.route_level,
            "preview": {
                "type": course.preview_type,
                "url": course.preview_url,
                "validatedAt": (
                    course.preview_validated_at.isoformat()
                    if hasattr(
                        course.preview_validated_at,
                        "isoformat",
                    )
                    else course.preview_validated_at
                ),
                "countryCode": course.preview_country_code,
            },
            "available": course.is_available,
        })

    return result


@transaction.atomic
def create_learning_route_snapshot(
    *,
    lead: LearningRouteLead,
    courses: Iterable[Any],
    mode: str = DEFAULT_ROUTE_MODE,
    source: str = DEFAULT_ROUTE_SOURCE,
    change_reason: str = "",
    created_by_event_id: Optional[str] = None,
    metadata: Optional[Dict[str, Any]] = None,
    version: Optional[int] = None,
    require_certification: bool = False,
    sync_legacy_field: bool = True,
) -> LearningRouteSnapshot:
    """
    Crea una nueva versión completa de la ruta.

    No modifica los items del snapshot anterior.
    """
    if not isinstance(lead, LearningRouteLead):
        raise InvalidLearningRouteError(
            "lead debe ser una instancia de LearningRouteLead."
        )

    if not lead.pk:
        raise InvalidLearningRouteError(
            "El LearningRouteLead debe estar guardado."
        )

    normalized_courses = normalize_route_courses(
        courses,
        require_certification=require_certification,
    )

    locked_lead = (
        LearningRouteLead.objects
        .select_for_update()
        .get(pk=lead.pk)
    )

    existing_snapshots = (
        LearningRouteSnapshot.objects
        .select_for_update()
        .filter(lead=locked_lead)
    )

    current_max = existing_snapshots.aggregate(
        max_version=Max("version")
    ).get("max_version")

    if version is None:
        if current_max is None:
            version = max(
                1,
                normalize_positive_integer(
                    locked_lead.route_version,
                    default=1,
                ),
            )
        else:
            version = int(current_max) + 1
    else:
        version = normalize_positive_integer(
            version,
            default=1,
        )

        if existing_snapshots.filter(
            version=version
        ).exists():
            raise LearningRouteVersionConflictError(
                f"La ruta {locked_lead.pk} ya tiene "
                f"la versión {version}."
            )

    existing_snapshots.filter(
        is_current=True
    ).update(
        is_current=False,
        updated_at=timezone.now(),
    )

    try:
        snapshot = LearningRouteSnapshot.objects.create(
            lead=locked_lead,
            version=version,
            mode=normalize_string(mode) or DEFAULT_ROUTE_MODE,
            is_current=True,
            source=normalize_string(source)
            or DEFAULT_ROUTE_SOURCE,
            change_reason=normalize_string(change_reason),
            created_by_event_id=normalize_optional_string(
                created_by_event_id
            ),
            metadata=metadata or {},
        )
    except IntegrityError as exc:
        raise LearningRouteVersionConflictError(
            "No fue posible crear la versión de la ruta "
            "por un conflicto de concurrencia."
        ) from exc

    create_route_items(
        snapshot=snapshot,
        normalized_courses=normalized_courses,
    )

    locked_lead.route_version = version

    update_fields = [
        "route_version",
        "updated_at",
    ]

    if sync_legacy_field:
        locked_lead.recommended_certifications = (
            build_legacy_recommendations(
                normalized_courses
            )
        )
        update_fields.append(
            "recommended_certifications"
        )

    locked_lead.save(
        update_fields=update_fields
    )

    return (
        LearningRouteSnapshot.objects
        .prefetch_related("courses")
        .get(pk=snapshot.pk)
    )


# =========================================================
# OPERACIONES DE NEGOCIO
# =========================================================

def create_initial_learning_route(
    *,
    lead: LearningRouteLead,
    courses: Iterable[Any],
    source: str = DEFAULT_ROUTE_SOURCE,
    change_reason: str = "INITIAL_ROUTE",
    created_by_event_id: Optional[str] = None,
    metadata: Optional[Dict[str, Any]] = None,
    require_certification: bool = False,
) -> LearningRouteSnapshot:
    existing = (
        LearningRouteSnapshot.objects
        .filter(lead=lead)
        .exists()
    )

    if existing:
        raise LearningRouteVersionConflictError(
            "El Lead ya tiene una ruta creada. "
            "Utiliza update_learning_route()."
        )

    return create_learning_route_snapshot(
        lead=lead,
        courses=courses,
        version=1,
        source=source,
        change_reason=change_reason,
        created_by_event_id=created_by_event_id,
        metadata=metadata,
        require_certification=require_certification,
    )


def update_learning_route(
    *,
    lead: LearningRouteLead,
    courses: Iterable[Any],
    source: str = DEFAULT_ROUTE_SOURCE,
    change_reason: str = "ROUTE_UPDATED",
    created_by_event_id: Optional[str] = None,
    metadata: Optional[Dict[str, Any]] = None,
    require_certification: bool = False,
) -> LearningRouteSnapshot:
    return create_learning_route_snapshot(
        lead=lead,
        courses=courses,
        source=source,
        change_reason=change_reason,
        created_by_event_id=created_by_event_id,
        metadata=metadata,
        require_certification=require_certification,
    )


def replace_current_learning_route(
    *,
    lead: LearningRouteLead,
    courses: Iterable[Any],
    change_reason: str = "ROUTE_REPLACED",
    source: str = DEFAULT_ROUTE_SOURCE,
    created_by_event_id: Optional[str] = None,
    metadata: Optional[Dict[str, Any]] = None,
) -> LearningRouteSnapshot:
    """
    No sobrescribe físicamente la ruta actual.

    "Replace" significa generar un nuevo snapshot completo,
    porque el contrato trabaja con snapshots versionados.
    """
    return update_learning_route(
        lead=lead,
        courses=courses,
        source=source,
        change_reason=change_reason,
        created_by_event_id=created_by_event_id,
        metadata=metadata,
    )


def clone_current_learning_route(
    *,
    lead: LearningRouteLead,
    change_reason: str = "ROUTE_CLONED",
    source: str = DEFAULT_ROUTE_SOURCE,
    created_by_event_id: Optional[str] = None,
    metadata: Optional[Dict[str, Any]] = None,
) -> LearningRouteSnapshot:
    current = get_current_route_snapshot(lead)

    if current is None:
        raise InvalidLearningRouteError(
            "El Lead no tiene una ruta actual para clonar."
        )

    items = (
        current.courses
        .select_related("certification")
        .order_by(
            "route_level",
            "order",
            "id",
        )
    )

    return create_learning_route_snapshot(
        lead=lead,
        courses=list(items),
        source=source,
        change_reason=change_reason,
        created_by_event_id=created_by_event_id,
        metadata=metadata,
    )


def add_courses_to_learning_route(
    *,
    lead: LearningRouteLead,
    courses: Iterable[Any],
    change_reason: str = "COURSES_ADDED",
    source: str = DEFAULT_ROUTE_SOURCE,
    created_by_event_id: Optional[str] = None,
    metadata: Optional[Dict[str, Any]] = None,
) -> LearningRouteSnapshot:
    current = get_current_route_snapshot(lead)

    current_courses: List[Any] = []

    if current:
        current_courses = list(
            current.courses
            .select_related("certification")
            .order_by(
                "route_level",
                "order",
                "id",
            )
        )

    combined = current_courses + list(courses or [])

    return create_learning_route_snapshot(
        lead=lead,
        courses=combined,
        source=source,
        change_reason=change_reason,
        created_by_event_id=created_by_event_id,
        metadata=metadata,
    )


def remove_courses_from_learning_route(
    *,
    lead: LearningRouteLead,
    id_internos: Iterable[str],
    change_reason: str = "COURSES_REMOVED",
    source: str = DEFAULT_ROUTE_SOURCE,
    created_by_event_id: Optional[str] = None,
    metadata: Optional[Dict[str, Any]] = None,
) -> LearningRouteSnapshot:
    current = get_current_route_snapshot(lead)

    if current is None:
        raise InvalidLearningRouteError(
            "El Lead no tiene una ruta actual."
        )

    to_remove = {
        normalize_id_interno(value)
        for value in id_internos or []
        if normalize_id_interno(value)
    }

    if not to_remove:
        raise InvalidLearningRouteError(
            "No se indicaron cursos para remover."
        )

    remaining_items = [
        item
        for item in (
            current.courses
            .select_related("certification")
            .order_by(
                "route_level",
                "order",
                "id",
            )
        )
        if item.id_interno not in to_remove
    ]

    if not remaining_items:
        raise InvalidLearningRouteError(
            "La operación dejaría la ruta sin cursos."
        )

    return create_learning_route_snapshot(
        lead=lead,
        courses=remaining_items,
        source=source,
        change_reason=change_reason,
        created_by_event_id=created_by_event_id,
        metadata=metadata,
    )


def reorder_learning_route(
    *,
    lead: LearningRouteLead,
    ordered_courses: Iterable[Dict[str, Any]],
    change_reason: str = "ROUTE_REORDERED",
    source: str = DEFAULT_ROUTE_SOURCE,
    created_by_event_id: Optional[str] = None,
    metadata: Optional[Dict[str, Any]] = None,
) -> LearningRouteSnapshot:
    """
    ordered_courses ejemplo:

    [
        {
            "idInterno": "COURSE-1",
            "routeLevel": 1,
            "order": 1
        },
        {
            "idInterno": "COURSE-2",
            "routeLevel": 1,
            "order": 2
        }
    ]
    """
    current = get_current_route_snapshot(lead)

    if current is None:
        raise InvalidLearningRouteError(
            "El Lead no tiene una ruta actual."
        )

    current_items = {
        item.id_interno: item
        for item in (
            current.courses
            .select_related("certification")
            .all()
        )
    }

    reordered = []
    received_ids = set()

    for index, item_data in enumerate(
        ordered_courses or [],
        start=1,
    ):
        if not isinstance(item_data, dict):
            raise InvalidLearningRouteError(
                "Cada posición debe ser un diccionario."
            )

        id_interno = normalize_id_interno(
            get_first_value(
                item_data,
                "idInterno",
                "id_interno",
            )
        )

        if not id_interno:
            raise InvalidLearningRouteError(
                "Cada posición debe contener idInterno."
            )

        if id_interno in received_ids:
            raise InvalidLearningRouteError(
                f"El curso '{id_interno}' está repetido."
            )

        current_item = current_items.get(id_interno)

        if current_item is None:
            raise LearningRouteCourseNotFoundError(
                f"El curso '{id_interno}' no pertenece "
                "a la ruta actual."
            )

        received_ids.add(id_interno)

        reordered.append({
            "idInterno": current_item.id_interno,
            "certification_id": (
                current_item.certification_id
            ),
            "title": current_item.title,
            "provider": current_item.provider,
            "language": current_item.language,
            "routeLevel": get_first_value(
                item_data,
                "routeLevel",
                "route_level",
            ) or current_item.route_level,
            "order": get_first_value(
                item_data,
                "order",
                "orden",
            ) or index,
            "previewType": current_item.preview_type,
            "previewUrl": current_item.preview_url,
            "previewValidatedAt": (
                current_item.preview_validated_at
            ),
            "previewCountryCode": (
                current_item.preview_country_code
            ),
            "available": current_item.is_available,
        })

    missing_ids = (
        set(current_items.keys()) - received_ids
    )

    if missing_ids:
        raise InvalidLearningRouteError(
            "La nueva organización no incluye todos los cursos. "
            f"Faltan: {', '.join(sorted(missing_ids))}"
        )

    return create_learning_route_snapshot(
        lead=lead,
        courses=reordered,
        source=source,
        change_reason=change_reason,
        created_by_event_id=created_by_event_id,
        metadata=metadata,
    )


# =========================================================
# RUTAS FREE TIER
# =========================================================

def build_free_route_metadata(
    *,
    courses: Sequence[Dict[str, Any]],
    catalog_source: str = "MX_FREE_PREVIEW",
    extra_metadata: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    """
    Construye metadata común para snapshots creados desde el catálogo Free.
    """
    metadata = {
        "catalog": catalog_source,
        "countryCode": "CO",
        "courseCount": len(courses),
        "isFreeTier": True,
        "selectionSource": "free-preview-courses",
        "selectedIdInternos": [
            normalize_id_interno(course.get("idInterno"))
            for course in courses
            if isinstance(course, dict)
            and normalize_id_interno(course.get("idInterno"))
        ],
        "selectedAt": timezone.now().isoformat(),
    }

    if extra_metadata:
        metadata.update(extra_metadata)

    return metadata


def select_free_courses_for_learning_route(
    *,
    lead: LearningRouteLead,
    amount: int = 3,
    excluded_id_internos: Optional[Iterable[str]] = None,
    force_catalog_refresh: bool = False,
) -> List[Dict[str, Any]]:
    """
    Selecciona experiencias elegibles exclusivamente desde el endpoint
    Free Tier y valida que puedan persistirse como LearningRouteItem.
    """
    if not isinstance(lead, LearningRouteLead):
        raise InvalidLearningRouteError(
            "lead debe ser una instancia de LearningRouteLead."
        )

    if not lead.pk:
        raise InvalidLearningRouteError(
            "El LearningRouteLead debe estar guardado."
        )

    try:
        courses = select_free_preview_courses_for_lead(
            lead,
            amount=amount,
            excluded_id_internos=excluded_id_internos,
            force_refresh=force_catalog_refresh,
        )
    except (FreePreviewSelectionError, FreePreviewProviderError) as exc:
        raise InvalidLearningRouteError(
            f"No fue posible construir la ruta Free: {exc}"
        ) from exc

    normalized = normalize_route_courses(
        courses,
        require_certification=False,
    )

    if len(normalized) != amount:
        raise InvalidLearningRouteError(
            "La ruta Free debe contener exactamente "
            f"{amount} experiencias elegibles."
        )

    result: List[Dict[str, Any]] = []

    for course in normalized:
        if not course.preview_type or not course.preview_url:
            raise InvalidLearningRouteError(
                "Cada experiencia Free debe incluir preview.type "
                "y preview.url."
            )

        result.append({
            "idInterno": course.id_interno,
            "title": course.title,
            "provider": course.provider,
            "language": course.language,
            "order": course.order,
            "routeLevel": course.route_level,
            "preview": {
                "type": course.preview_type,
                "url": course.preview_url,
                "validatedAt": course.preview_validated_at,
                "countryCode": (
                    course.preview_country_code or "CO"
                ),
            },
            "available": course.is_available,
        })

    return result


def create_free_learning_route(
    *,
    lead: LearningRouteLead,
    change_reason: str = "FREE_PLAN_CREATED",
    created_by_event_id: Optional[str] = None,
    force_catalog_refresh: bool = False,
    metadata: Optional[Dict[str, Any]] = None,
) -> LearningRouteSnapshot:
    """
    Crea la primera ruta Free del Lead.

    Debe utilizarse solamente cuando el Lead todavía no tenga snapshots.
    """
    courses = select_free_courses_for_learning_route(
        lead=lead,
        amount=3,
        force_catalog_refresh=force_catalog_refresh,
    )

    return create_initial_learning_route(
        lead=lead,
        courses=courses,
        source="MX_FREE_PREVIEW",
        change_reason=change_reason,
        created_by_event_id=created_by_event_id,
        metadata=build_free_route_metadata(
            courses=courses,
            extra_metadata=metadata,
        ),
        require_certification=False,
    )


def update_to_free_learning_route(
    *,
    lead: LearningRouteLead,
    change_reason: str = "SUBSCRIPTION_EXPIRED_TO_FREE",
    created_by_event_id: Optional[str] = None,
    force_catalog_refresh: bool = False,
    preserve_current_free_route: bool = True,
    metadata: Optional[Dict[str, Any]] = None,
) -> LearningRouteSnapshot:
    """
    Crea una nueva versión de la ruta cuando el usuario pasa a Free.

    Si la ruta actual ya es una ruta Free válida y
    preserve_current_free_route=True, retorna el snapshot vigente para
    evitar versiones innecesarias e impedir cambios arbitrarios de cursos.
    """
    current = get_current_route_snapshot(lead)

    if current is not None and preserve_current_free_route:
        current_metadata = current.metadata or {}
        current_items = list(
            current.courses.order_by(
                "route_level",
                "order",
                "id",
            )
        )

        current_is_free = bool(
            current_metadata.get("isFreeTier")
            or current_metadata.get("catalog") == "MX_FREE_PREVIEW"
            or current.source == "MX_FREE_PREVIEW"
        )

        current_is_valid = (
            len(current_items) == 3
            and len({item.id_interno for item in current_items}) == 3
            and all(
                item.preview_type
                and item.preview_url
                and item.is_available
                for item in current_items
            )
        )

        if current_is_free and current_is_valid:
            return current

    courses = select_free_courses_for_learning_route(
        lead=lead,
        amount=3,
        force_catalog_refresh=force_catalog_refresh,
    )

    return update_learning_route(
        lead=lead,
        courses=courses,
        source="MX_FREE_PREVIEW",
        change_reason=change_reason,
        created_by_event_id=created_by_event_id,
        metadata=build_free_route_metadata(
            courses=courses,
            extra_metadata=metadata,
        ),
        require_certification=False,
    )


def ensure_free_learning_route(
    *,
    lead: LearningRouteLead,
    change_reason: str = "FREE_ROUTE_ENSURED",
    created_by_event_id: Optional[str] = None,
    force_catalog_refresh: bool = False,
    preserve_current_free_route: bool = True,
    metadata: Optional[Dict[str, Any]] = None,
) -> LearningRouteSnapshot:
    """
    Punto de entrada recomendado para aprovisionar una ruta Free.

    - Si no existe ruta, crea la versión inicial.
    - Si ya existe, crea una nueva versión Free.
    - Si la ruta actual ya es Free y válida, puede reutilizarla.
    """
    existing = LearningRouteSnapshot.objects.filter(
        lead=lead
    ).exists()

    if not existing:
        return create_free_learning_route(
            lead=lead,
            change_reason=change_reason,
            created_by_event_id=created_by_event_id,
            force_catalog_refresh=force_catalog_refresh,
            metadata=metadata,
        )

    return update_to_free_learning_route(
        lead=lead,
        change_reason=change_reason,
        created_by_event_id=created_by_event_id,
        force_catalog_refresh=force_catalog_refresh,
        preserve_current_free_route=preserve_current_free_route,
        metadata=metadata,
    )


# =========================================================
# MIGRACIÓN DE RUTAS ANTIGUAS
# =========================================================

def migrate_legacy_recommended_certifications(
    *,
    lead: LearningRouteLead,
    change_reason: str = "LEGACY_ROUTE_MIGRATION",
    source: str = "LEGACY_COLOMBIA",
) -> Optional[LearningRouteSnapshot]:
    """
    Convierte recommended_certifications en un snapshot inicial.

    No crea nada si el Lead ya posee snapshots.
    """
    if LearningRouteSnapshot.objects.filter(
        lead=lead
    ).exists():
        return get_current_route_snapshot(lead)

    legacy_courses = (
        lead.recommended_certifications
        if isinstance(
            lead.recommended_certifications,
            list,
        )
        else []
    )

    if not legacy_courses:
        return None

    return create_learning_route_snapshot(
        lead=lead,
        courses=legacy_courses,
        version=max(
            1,
            normalize_positive_integer(
                lead.route_version,
                default=1,
            ),
        ),
        source=source,
        change_reason=change_reason,
        metadata={
            "migratedFrom": "recommended_certifications",
            "migratedAt": timezone.now().isoformat(),
        },
        require_certification=False,
    )


def migrate_all_legacy_routes(
    *,
    batch_size: int = 100,
) -> Dict[str, int]:
    """
    Función administrativa para migrar rutas existentes.

    Para grandes volúmenes es mejor convertirla después en
    un management command.
    """
    totals = {
        "processed": 0,
        "created": 0,
        "skipped": 0,
        "errors": 0,
    }

    queryset = (
        LearningRouteLead.objects
        .filter(
            recommended_certifications__isnull=False,
        )
        .order_by("id")
    )

    for lead in queryset.iterator(
        chunk_size=batch_size
    ):
        totals["processed"] += 1

        try:
            snapshot = (
                migrate_legacy_recommended_certifications(
                    lead=lead
                )
            )

            if snapshot:
                totals["created"] += 1
            else:
                totals["skipped"] += 1

        except Exception:
            totals["errors"] += 1

    return totals