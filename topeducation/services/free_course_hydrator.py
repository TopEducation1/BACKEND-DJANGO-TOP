from __future__ import annotations



import logging
import re

from unidecode import unidecode

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

    exact_matched:

        Coincidencias exactas por idInterno.

    stable_key_matched:

        Coincidencias realizadas por course key cuando el run remoto
        y el run local son diferentes.

    title_matched:

        Coincidencias realizadas por título normalizado cuando México
        y Colombia usan identificadores distintos para el mismo curso.

    """



    courses: List[Dict[str, Any]]

    unmatched_id_internos: List[str]

    duplicated_id_internos: List[str]

    total_requested: int

    total_matched: int

    # Diagnóstico adicional. No cambia la API existente porque
    # estos campos tienen valor por defecto.
    exact_matched: int = 0

    stable_key_matched: int = 0

    title_matched: int = 0





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





def _stable_course_key(value: Any) -> Optional[str]:
    """
    Devuelve la parte estable de un idInterno Open edX eliminando
    únicamente el último segmento (run).

    Ejemplo:
        course-v1:CodeSignal+141+3T2026
        -> course-v1:CodeSignal+141

    IMPORTANTE:
    - El idInterno original nunca se modifica.
    - Este valor se usa solamente como fallback de hidratación cuando
      no existe coincidencia exacta en Certificaciones.
    - Para formatos que no sean course-v1:...+...+run se retorna None.
    """

    id_interno = _normalize_id_interno(value)

    if not id_interno:
        return None

    normalized = id_interno.strip()

    if not normalized.startswith("course-v1:"):
        return None

    stable_key, separator, run = normalized.rpartition("+")

    if not separator or not stable_key or not run:
        return None

    # Deben existir al menos organización + course code antes del run.
    if "+" not in stable_key:
        return None

    return stable_key



def _normalize_title_key(value: Any) -> str:
    """
    Normaliza un título para matching defensivo.

    Está alineado con el slug histórico utilizado por import_courses.py:

        "LLM Server"
        -> "llm-server"

        "Introducción a IA"
        -> "introduccion-a-ia"

    Este valor NO sustituye ningún identificador contractual.
    Solo se utiliza para encontrar metadata local cuando idInterno y
    stable_course_key no coinciden entre México y Colombia.
    """

    title = _clean_text(value)

    if not title:
        return ""

    normalized = unidecode(title)
    normalized = normalized.lower().strip()
    normalized = re.sub(
        r"[^a-z0-9\s-]",
        "",
        normalized,
    )
    normalized = re.sub(
        r"\s+",
        "-",
        normalized,
    )
    normalized = re.sub(
        r"-{2,}",
        "-",
        normalized,
    )

    return normalized.strip("-")



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



def fetch_certifications_by_stable_course_keys(
    stable_keys: Sequence[str],
    *,
    batch_size: int = DEFAULT_QUERY_BATCH_SIZE,
) -> Dict[str, List[Certificaciones]]:
    """
    Busca cursos por stable_course_key INDEXADO.

    IMPORTANTE:
    Esta función NO recorre las ~30k certificaciones ni construye
    cientos de OR/LIKE. El matching por course key se resuelve mediante
    un campo materializado e indexado en Certificaciones.

    Requiere:
        Certificaciones.stable_course_key
    """

    normalized_keys = _unique_preserving_order([
        str(value).strip()
        for value in stable_keys
        if value and str(value).strip()
    ])

    grouped: Dict[str, List[Certificaciones]] = {}

    if not normalized_keys:
        return grouped

    # Defensa durante despliegues escalonados:
    # si el modelo aún no tiene el campo, no hacemos el escaneo costoso.
    field_names = {
        field.name
        for field in Certificaciones._meta.get_fields()
    }

    if "stable_course_key" not in field_names:
        logger.error(
            (
                "Certificaciones.stable_course_key no existe todavía. "
                "Se omite fallback estable para evitar WORKER TIMEOUT."
            )
        )
        return grouped

    base_queryset = (
        get_certifications_hydration_queryset()
    )

    for chunk in _chunked(
        normalized_keys,
        batch_size,
    ):
        certifications = (
            base_queryset
            .filter(
                stable_course_key__in=chunk,
            )
        )

        for certification in certifications:
            stable_key = _clean_text(
                getattr(
                    certification,
                    "stable_course_key",
                    None,
                )
            )

            if not stable_key:
                # Compatibilidad defensiva para registros aún no
                # backfilleados.
                stable_key = (
                    _stable_course_key(
                        certification.id_interno
                    )
                    or ""
                )

            if not stable_key:
                continue

            grouped.setdefault(
                stable_key,
                [],
            ).append(
                certification
            )

    logger.info(
        (
            "Fallback stable key indexado preparado. "
            "solicitadas=%s keys_con_match=%s"
        ),
        len(normalized_keys),
        len(grouped),
    )

    return grouped


def fetch_certifications_by_titles(
    preview_items: Sequence[Mapping[str, Any]],
    *,
    batch_size: int = DEFAULT_QUERY_BATCH_SIZE,
) -> Dict[str, List[Certificaciones]]:
    """
    Tercer fallback de matching, sin LIKE ni búsquedas parciales.

    Utiliza únicamente valores que import_courses.py ya materializa:

        Free.title       -> Certificaciones.slug
        Free.provider    -> Certificaciones.source_provider
        Free.language    -> Certificaciones.language_normalized

    Ejemplo:
        Free:
            title = "LLM Server"
            provider = "EDX"
            language = "en"

        Local:
            slug = "llm-server"
            source_provider = "EDX"
            language_normalized = "en"

    La consulta es por igualdad exacta y puede apoyarse en el índice
    compuesto idx_cert_free_match.

    El idInterno remoto de México nunca se modifica.
    """

    grouped_requests: Dict[
        Tuple[str, str],
        List[str],
    ] = {}

    # title_key -> item remoto, solo para claves únicas.
    title_key_counts: Dict[str, int] = {}

    for preview_item in preview_items or []:
        if not isinstance(preview_item, Mapping):
            continue

        title_key = _normalize_title_key(
            preview_item.get("title")
        )

        if not title_key:
            continue

        title_key_counts[title_key] = (
            title_key_counts.get(title_key, 0)
            + 1
        )

    for preview_item in preview_items or []:
        if not isinstance(preview_item, Mapping):
            continue

        title_key = _normalize_title_key(
            preview_item.get("title")
        )

        if (
            not title_key
            or title_key_counts.get(title_key, 0) != 1
        ):
            continue

        provider = _normalize_provider(
            preview_item.get("provider")
        )

        language = _normalize_language(
            preview_item.get("language")
        )

        group_key = (
            provider,
            language,
        )

        grouped_requests.setdefault(
            group_key,
            [],
        ).append(title_key)

    if not grouped_requests:
        return {}

    candidate_ids_by_key: Dict[
        str,
        List[int],
    ] = {}

    seen_ids_by_key: Dict[
        str,
        set,
    ] = {}

    lightweight_queryset = (
        Certificaciones.objects
        .filter(
            vigente_certificacion=True,
        )
        .order_by()
    )

    def add_candidate(
        title_key: str,
        certification_id: int,
    ) -> None:
        certification_id = int(certification_id)

        seen = seen_ids_by_key.setdefault(
            title_key,
            set(),
        )

        if certification_id in seen:
            return

        seen.add(certification_id)

        candidate_ids_by_key.setdefault(
            title_key,
            [],
        ).append(certification_id)

    # -----------------------------------------------------
    # MATCH EXACTO:
    # source_provider + language_normalized + slug
    # -----------------------------------------------------
    for (
        provider,
        language,
    ), title_keys in grouped_requests.items():

        unique_title_keys = _unique_preserving_order(
            title_keys
        )

        for chunk in _chunked(
            unique_title_keys,
            batch_size,
        ):
            queryset = lightweight_queryset.filter(
                slug__in=chunk,
            )

            if provider:
                queryset = queryset.filter(
                    source_provider=provider,
                )

            if language:
                queryset = queryset.filter(
                    language_normalized=language,
                )

            rows = queryset.values_list(
                "id",
                "slug",
            )

            for certification_id, slug in rows:
                title_key = _clean_text(slug)

                if not title_key:
                    continue

                add_candidate(
                    title_key,
                    certification_id,
                )

    if not candidate_ids_by_key:
        logger.info(
            (
                "Fallback Free por metadata exacta sin candidatos. "
                "items=%s"
            ),
            len(preview_items or []),
        )
        return {}

    # -----------------------------------------------------
    # HIDRATAR SOLO LOS IDs QUE YA HICIERON MATCH EXACTO
    # -----------------------------------------------------
    candidate_ids: List[int] = []
    seen_candidate_ids = set()

    for ids in candidate_ids_by_key.values():
        for certification_id in ids:
            certification_id = int(
                certification_id
            )

            if certification_id in seen_candidate_ids:
                continue

            seen_candidate_ids.add(
                certification_id
            )
            candidate_ids.append(
                certification_id
            )

    certifications_by_id: Dict[
        int,
        Certificaciones,
    ] = {}

    hydration_queryset = (
        get_certifications_hydration_queryset()
    )

    for chunk in _chunked(
        candidate_ids,
        batch_size,
    ):
        for certification in (
            hydration_queryset
            .filter(
                id__in=chunk,
            )
            .order_by("id")
        ):
            certifications_by_id[
                int(certification.id)
            ] = certification

    grouped: Dict[
        str,
        List[Certificaciones],
    ] = {}

    for title_key, ids in candidate_ids_by_key.items():
        matches = [
            certifications_by_id[int(certification_id)]
            for certification_id in ids
            if int(certification_id) in certifications_by_id
        ]

        if matches:
            grouped[title_key] = matches

    logger.info(
        (
            "Fallback Free por metadata exacta preparado. "
            "keys_con_match=%s candidatos_hidratados=%s"
        ),
        len(grouped),
        len(certifications_by_id),
    )

    return grouped


def _choose_title_fallback_certification(
    certifications: Sequence[Certificaciones],
    preview_item: Mapping[str, Any],
) -> Optional[Certificaciones]:
    """
    Selecciona un candidato del fallback por título con protección
    contra asociaciones ambiguas.

    - Si solo existe un candidato local, se acepta.
    - Si existen varios, se usa provider/idioma/metadata.
    - Si los dos mejores tienen la misma puntuación, se considera
      ambiguo y NO se fuerza el match.
    """

    if not certifications:
        return None

    if len(certifications) == 1:
        return certifications[0]

    ranked = sorted(
        certifications,
        key=lambda certification: (
            _certification_match_score(
                certification,
                preview_item,
            )[0],
            certification.id,
        ),
        reverse=True,
    )

    best = ranked[0]

    best_score = _certification_match_score(
        best,
        preview_item,
    )[0]

    second_score = _certification_match_score(
        ranked[1],
        preview_item,
    )[0]

    if best_score == second_score:
        logger.warning(
            (
                "Fallback por título ambiguo; se omite. "
                "remote_title=%s candidatos=%s score=%s"
            ),
            _clean_text(
                preview_item.get("title")
            ),
            [
                certification.id
                for certification in ranked
            ],
            best_score,
        )
        return None

    return best


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

    Estrategia de matching, en orden estricto:

    1. idInterno exacto.
    2. stable_course_key:
       misma organización + course code, ignorando solamente el run.
    3. título normalizado:
       último fallback para casos donde MX y Colombia representan
       el mismo curso con course codes diferentes.

       Ejemplo real:
           MX:
               course-v1:AI+localmodel01x+2T2024

           Colombia:
               course-v1:AI+llmserver01x+2T2024

           Ambos:
               LLM Server

    Reglas de seguridad:

    - El fallback por título solo se evalúa si fallaron exact y stable.
    - Si un mismo título remoto aparece más de una vez en el catálogo,
      no se utiliza como fallback automático.
    - Si existen varios candidatos locales y la puntuación no permite
      distinguir uno claramente, el curso se deja sin match.
    - El idInterno final SIEMPRE es el recibido desde México.
      El registro local únicamente aporta metadata y certificationId.

    Así, si MX entrega N cursos y Colombia puede relacionar solo una
    parte, esos matches siguen disponibles para recommendations sin que
    los demás bloqueen el proceso.
    """

    normalized_items = normalize_free_catalog_items(
        preview_items
    )

    id_internos = [
        item["idInterno"]
        for item in normalized_items
    ]

    # -----------------------------------------------------
    # 1. MATCH EXACTO
    # -----------------------------------------------------
    grouped_exact = fetch_certifications_by_internal_ids(
        id_internos,
        batch_size=batch_size,
    )

    logger.info(
        (
            "Free hydration exact matching terminado. "
            "remote=%s exact_keys=%s"
        ),
        len(id_internos),
        len(grouped_exact),
    )

    # -----------------------------------------------------
    # 2. FALLBACK POR STABLE COURSE KEY
    # -----------------------------------------------------
    stable_keys_to_search: List[str] = []

    for id_interno in id_internos:
        if grouped_exact.get(id_interno):
            continue

        stable_key = _stable_course_key(
            id_interno
        )

        if stable_key:
            stable_keys_to_search.append(
                stable_key
            )

    stable_keys_to_search = _unique_preserving_order(
        stable_keys_to_search
    )

    grouped_stable = (
        fetch_certifications_by_stable_course_keys(
            stable_keys_to_search,
            batch_size=batch_size,
        )
        if stable_keys_to_search
        else {}
    )

    # -----------------------------------------------------
    # 3. FALLBACK POR TÍTULO
    # -----------------------------------------------------
    #
    # Solo preparamos títulos para elementos que siguen sin match
    # después de exact + stable.
    #
    title_key_counts: Dict[str, int] = {}

    for preview_item in normalized_items:
        remote_id = preview_item["idInterno"]

        if grouped_exact.get(remote_id):
            continue

        stable_key = _stable_course_key(
            remote_id
        )

        if (
            stable_key
            and grouped_stable.get(stable_key)
        ):
            continue

        title_key = _normalize_title_key(
            preview_item.get("title")
        )

        if not title_key:
            continue

        title_key_counts[title_key] = (
            title_key_counts.get(
                title_key,
                0,
            )
            + 1
        )

    unique_title_items = [
        preview_item
        for preview_item in normalized_items
        if (
            _normalize_title_key(
                preview_item.get("title")
            )
            and title_key_counts.get(
                _normalize_title_key(
                    preview_item.get("title")
                ),
                0,
            )
            == 1
        )
    ]

    titles_to_search = _unique_preserving_order([
        _clean_text(
            item.get("title")
        )
        for item in unique_title_items
        if _clean_text(
            item.get("title")
        )
    ])

    grouped_title = (
        fetch_certifications_by_titles(
            unique_title_items,
            batch_size=batch_size,
        )
        if unique_title_items
        else {}
    )

    hydrated_courses: List[Dict[str, Any]] = []
    unmatched_ids: List[str] = []
    duplicated_ids: List[str] = []

    exact_matched = 0
    stable_key_matched = 0
    title_matched = 0

    for preview_item in normalized_items:
        remote_id_interno = preview_item[
            "idInterno"
        ]

        matches: Sequence[
            Certificaciones
        ] = []

        match_mode = ""

        # -------------------------------------------------
        # PRIORIDAD 1: ID EXACTO
        # -------------------------------------------------
        matches = grouped_exact.get(
            remote_id_interno,
            [],
        )

        if matches:
            match_mode = "exact"

        # -------------------------------------------------
        # PRIORIDAD 2: MISMO COURSE CODE, OTRO RUN
        # -------------------------------------------------
        if not matches:
            stable_key = _stable_course_key(
                remote_id_interno
            )

            if stable_key:
                matches = grouped_stable.get(
                    stable_key,
                    [],
                )

                if matches:
                    match_mode = (
                        "stable_course_key"
                    )

        # -------------------------------------------------
        # PRIORIDAD 3: SLUG + PROVIDER + LANGUAGE EXACTOS
        # -------------------------------------------------
        if not matches:
            title_key = _normalize_title_key(
                preview_item.get("title")
            )

            # No usamos automáticamente títulos remotos duplicados.
            if (
                title_key
                and title_key_counts.get(
                    title_key,
                    0,
                )
                == 1
            ):
                title_matches = grouped_title.get(
                    title_key,
                    [],
                )

                certification = (
                    _choose_title_fallback_certification(
                        title_matches,
                        preview_item,
                    )
                )

                if certification is not None:
                    matches = [
                        certification
                    ]
                    match_mode = "title"

        # -------------------------------------------------
        # SIN MATCH LOCAL
        # -------------------------------------------------
        if not matches:
            unmatched_ids.append(
                remote_id_interno
            )
            continue

        if (
            match_mode != "title"
            and len(matches) > 1
        ):
            duplicated_ids.append(
                remote_id_interno
            )

        if match_mode == "title":
            certification = matches[0]
        else:
            certification = choose_best_certification(
                matches,
                preview_item,
            )

        if certification is None:
            unmatched_ids.append(
                remote_id_interno
            )
            continue

        # -------------------------------------------------
        # DIAGNÓSTICO DE MATCH
        # -------------------------------------------------
        if match_mode == "exact":
            exact_matched += 1

        elif match_mode == "stable_course_key":
            stable_key_matched += 1

            logger.info(
                (
                    "Free match por stable key. "
                    "remote_id=%s local_id=%s "
                    "stable_key=%s"
                ),
                remote_id_interno,
                certification.id_interno,
                _stable_course_key(
                    remote_id_interno
                ),
            )

        elif match_mode == "title":
            title_matched += 1

            logger.warning(
                (
                    "Free match por título normalizado. "
                    "remote_id=%s local_id=%s "
                    "remote_title=%s local_title=%s "
                    "certification_id=%s"
                ),
                remote_id_interno,
                certification.id_interno,
                _clean_text(
                    preview_item.get("title")
                ),
                _clean_text(
                    certification.nombre
                ),
                certification.id,
            )

        # -------------------------------------------------
        # HIDRATAR
        # -------------------------------------------------
        # hydrate_free_course conserva SIEMPRE el idInterno remoto.
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
            "exactos=%s stable_key=%s titulo=%s "
            "sin_coincidencia=%s duplicados=%s"
        ),
        len(normalized_items),
        len(hydrated_courses),
        exact_matched,
        stable_key_matched,
        title_matched,
        len(unmatched_ids),
        len(duplicated_ids),
    )

    return FreeCourseHydrationResult(
        courses=hydrated_courses,
        unmatched_id_internos=unmatched_ids,
        duplicated_id_internos=duplicated_ids,
        total_requested=len(normalized_items),
        total_matched=len(hydrated_courses),
        exact_matched=exact_matched,
        stable_key_matched=stable_key_matched,
        title_matched=title_matched,
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