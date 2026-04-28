from django.db import transaction

import json
import re
import traceback
from unidecode import unidecode

from topeducation.models import (
    Universidades,
    Empresas,
    Plataformas,
    Certificaciones,
    Skills,
    SkillsCertification,
    Instructores,
    InstructorCertification,
    Specialization,
    ExternalReconciliationSnapshot,
)

LANGUAGE_NORMALIZATION = {
    "es": {
        "label": "Español",
        "values": ["es", "spanish", "enseñado en español", "español"],
    },
    "en": {
        "label": "Inglés",
        "values": ["en", "english", "enseñado en inglés", "inglés"],
    },
    "ar": {"label": "Árabe", "values": ["ar", "arabic"]},
    "bn": {"label": "Bengalí", "values": ["bn", "bengali"]},
    "ca": {"label": "Catalán", "values": ["ca", "catalan"]},
    "zh": {
        "label": "Chino",
        "values": [
            "zh",
            "zh-cn",
            "zh-tw",
            "chinese - china",
            "chinese - mandarin",
            "chinese - simplified",
            "chinese",
        ],
    },
    "de": {"label": "Alemán", "values": ["de", "german"]},
    "nl": {"label": "Neerlandés", "values": ["nl", "dutch"]},
    "fa": {"label": "Persa", "values": ["fa", "farsi"]},
    "fr": {"label": "Francés", "values": ["fr", "french"]},
    "he": {"label": "Hebreo", "values": ["he", "hebrew"]},
    "hi": {"label": "Hindi", "values": ["hi", "hindi"]},
    "hu": {"label": "Húngaro", "values": ["hu", "hungarian"]},
    "id": {"label": "Indonesio", "values": ["id", "indonesian"]},
    "it": {"label": "Italiano", "values": ["it", "italian"]},
    "ja": {"label": "Japonés", "values": ["ja", "japanese"]},
    "kk": {"label": "Kazajo", "values": ["kk", "kazakh"]},
    "ko": {"label": "Coreano", "values": ["ko", "korean"]},
    "dv": {"label": "Maldivo", "values": ["dv", "maldivian"]},
    "pl": {"label": "Polaco", "values": ["pl", "polish"]},
    "pt": {"label": "Portugués", "values": ["pt", "pt-br", "pt-pt", "portuguese"]},
    "ru": {"label": "Ruso", "values": ["ru", "russian"]},
    "sv": {"label": "Sueco", "values": ["sv", "swedish"]},
    "sw": {"label": "Suajili", "values": ["sw", "swahili"]},
    "th": {"label": "Tailandés", "values": ["th", "thai"]},
    "tr": {"label": "Turco", "values": ["tr", "turkish"]},
    "uk": {"label": "Ucraniano", "values": ["uk", "ukrainian"]},
    "ur": {"label": "Urdu", "values": ["ur", "urdu"]},
}

IGNORED_LANGUAGE_VALUES = {"", "none", "null", "-", "n/a"}


def normalize_language_value(raw_value):
    raw = _norm(raw_value).lower()

    if raw in IGNORED_LANGUAGE_VALUES:
        return None

    for code, config in LANGUAGE_NORMALIZATION.items():
        for value in config.get("values", []):
            v = _norm(value).lower()
            if not v:
                continue

            if raw == v or v in raw:
                return {
                    "code": code,
                    "label": config["label"],
                }

    return None

def _norm(s) -> str:
    return (s or "").strip() if isinstance(s, str) else ("" if s is None else str(s).strip())


def _to_bool(value, default=True):
    if value is None:
        return default
    if isinstance(value, bool):
        return value
    if isinstance(value, (int, float)):
        return bool(value)
    if isinstance(value, str):
        v = value.strip().lower()
        if v in {"true", "1", "yes", "si", "sí"}:
            return True
        if v in {"false", "0", "no"}:
            return False
    return default


def _pick_one(qs, order_by="id"):
    return qs.order_by(order_by).first()


def _model_field_names(model) -> set:
    return {f.name for f in model._meta.get_fields() if getattr(f, "concrete", False)}


def _has_field(model, field_name: str) -> bool:
    return field_name in _model_field_names(model)


def _safe_get_or_create_unique(model, lookup: dict, defaults: dict, *, order_by="id"):
    qs = model.objects.filter(**lookup)
    obj = _pick_one(qs, order_by=order_by)
    if obj:
        return obj, False

    create_data = {}
    create_data.update(lookup or {})
    create_data.update(defaults or {})
    obj = model.objects.create(**create_data)
    return obj, True


def _apply_updates(obj, values: dict) -> list[str]:
    changed_fields = []
    model_fields = _model_field_names(obj.__class__)

    for field, value in (values or {}).items():
        if field not in model_fields:
            continue
        if getattr(obj, field) != value:
            setattr(obj, field, value)
            changed_fields.append(field)

    if changed_fields:
        obj.save(update_fields=changed_fields)

    return changed_fields


def _ensure_list(value):
    if value is None:
        return []
    if isinstance(value, list):
        return value
    return [value]


def safe_slug_from_name(name: str) -> str:
    if not name:
        return ""

    s = unidecode(str(name))
    s = s.lower().strip()
    s = re.sub(r"[^a-z0-9\s-]", "", s)
    s = re.sub(r"\s+", "-", s)
    s = re.sub(r"-{2,}", "-", s)
    s = s.strip("-")
    return s


def build_unique_slug(model, base_name: str, existing_obj=None, max_length: int = 500) -> str:
    base_slug = safe_slug_from_name(base_name) or "certificacion"
    base_slug = base_slug[:max_length]

    slug = base_slug
    index = 2

    while True:
        qs = model.objects.filter(slug=slug)
        if existing_obj is not None and getattr(existing_obj, "pk", None):
            qs = qs.exclude(pk=existing_obj.pk)

        if not qs.exists():
            return slug

        suffix = f"-{index}"
        allowed = max_length - len(suffix)
        slug = f"{base_slug[:allowed]}{suffix}"
        index += 1


def clean_habilidades(value) -> str:
    if value is None:
        return "NONE"

    if isinstance(value, list):
        out = []
        for item in value:
            if isinstance(item, str):
                t = item.strip()
                if t and t.lower() != "[object object]":
                    out.append(t)
            elif isinstance(item, dict):
                t = (
                    item.get("nombre")
                    or item.get("name")
                    or item.get("label")
                    or item.get("skill")
                    or item.get("value")
                    or item.get("subskill_name")
                    or item.get("skill_name")
                )
                if t:
                    out.append(str(t).strip())

        seen = set()
        uniq = []
        for x in out:
            key = x.lower()
            if key not in seen:
                seen.add(key)
                uniq.append(x)
        return ", ".join(uniq) if uniq else "NONE"

    if isinstance(value, dict):
        return clean_habilidades([value])

    s = str(value)

    try:
        maybe = json.loads(s)
        return clean_habilidades(maybe)
    except Exception:
        pass

    s = s.replace("[object Object]", "").replace("[object object]", "")
    s = re.sub(r"\s*,\s*", ", ", s)
    s = re.sub(r"\s+", " ", s).strip(" ,")

    return s if s else "NONE"


def _dedupe_keep_order(values: list[str]) -> list[str]:
    seen = set()
    out = []
    for v in values:
        norm_v = _norm(v)
        key = norm_v.lower()
        if not key:
            continue
        if key not in seen:
            seen.add(key)
            out.append(norm_v)
    return out


def _infer_provider_from_cert(cert: dict | None = None) -> str:
    if not cert:
        return ""
    return _norm(
        cert.get("provider")
        or cert.get("providerId")
        or cert.get("plataforma_certificacion")
        or cert.get("source_provider")
    ).upper()


def _normalize_provider_for_platform(cert: dict | None = None) -> str:
    if not cert:
        return ""
    return _norm(
        cert.get("plataforma_certificacion")
        or cert.get("provider")
        or cert.get("providerId")
    )


def extract_certification_skill_names(item: dict | None = None) -> list[str]:
    out = []

    if item:
        for row in (item.get("temas") or []):
            if not isinstance(row, dict):
                continue

            nombre = _norm(
                row.get("nombre")
                or row.get("name")
                or row.get("label")
                or row.get("skill")
                or row.get("value")
                or row.get("skill_name")
                or row.get("subskill_name")
            )
            if nombre:
                out.append(nombre)

    return _dedupe_keep_order(out)


def _extract_skill_value(raw) -> str:
    if isinstance(raw, dict):
        return _norm(
            raw.get("nombre")
            or raw.get("name")
            or raw.get("label")
            or raw.get("skill")
            or raw.get("value")
            or raw.get("skill_name")
            or raw.get("subskill_name")
            or raw.get("title")
        )

    return _norm(raw)


def _extract_skill_names_from_cert(cert: dict | None = None) -> list[str]:
    if not cert:
        return []

    out = []

    # 1) Nueva estructura principal
    for raw in _ensure_list(cert.get("skills_internal")):
        val = _extract_skill_value(raw)
        if val:
            out.append(val)

    # 2) Nueva estructura subskills
    for raw in _ensure_list(
        cert.get("subskills_internal")
        or cert.get("sub_skills_internal")
        or cert.get("subSkills_internal")
    ):
        val = _extract_skill_value(raw)
        if val:
            out.append(val)

    # 3) Posible array legacy dentro del curso
    for raw in _ensure_list(cert.get("temas")):
        val = _extract_skill_value(raw)
        if val:
            out.append(val)

    # 4) Posible campo texto/array legacy
    raw_habilidades = cert.get("habilidades_certificacion")
    cleaned = clean_habilidades(raw_habilidades)
    if cleaned and cleaned != "NONE":
        out.extend([_norm(x) for x in cleaned.split(",") if _norm(x)])

    out = _dedupe_keep_order(out)

    mapping_status = _norm(cert.get("mapping_status")).lower()
    if not out and mapping_status == "uncategorized":
        out = ["Uncategorized"]

    return _dedupe_keep_order(out)

def extract_instructors_from_cert(cert: dict | None = None) -> list[dict]:
    out = []
    if not cert:
        return out

    rows = cert.get("instructores_detalle_certificacion") or []

    if isinstance(rows, dict):
        rows = [rows]

    if isinstance(rows, str):
        try:
            parsed = json.loads(rows)
            rows = parsed if isinstance(parsed, list) else [parsed]
        except Exception:
            rows = []

    for row in rows:
        if not isinstance(row, dict):
            continue

        nombre = _norm(
            row.get("nombre")
            or row.get("name")
            or row.get("label")
        )
        imagen = row.get("imagen") or row.get("image") or row.get("foto") or row.get("img")

        if not nombre:
            continue

        out.append({
            "nombre": nombre,
            "imagen": imagen or None,
        })

    seen = set()
    uniq = []
    for row in out:
        key = row["nombre"].lower()
        if key in seen:
            continue
        seen.add(key)
        uniq.append(row)

    return uniq


def build_instructores_legacy_text(cert: dict | None = None) -> str:
    rows = extract_instructors_from_cert(cert)
    nombres = [r["nombre"] for r in rows if _norm(r.get("nombre"))]
    nombres = _dedupe_keep_order(nombres)
    return ", ".join(nombres) if nombres else "NONE"


def _build_university_rows_from_cert(cert: dict) -> list[dict]:
    nombre = _norm(cert.get("universidad_certificacion"))
    if not nombre:
        return []
    return [{
        "nombre": nombre,
        "descripcion_institucion": _norm(cert.get("descripcion_institucion_certificacion")),
        "univ_img": cert.get("universidad_imagen") or cert.get("univ_img"),
    }]


def _build_platform_rows_from_cert(cert: dict) -> list[dict]:
    nombre = _normalize_provider_for_platform(cert)
    if not nombre:
        return []
    return [{
        "nombre": nombre,
        "plat_img": cert.get("plataforma_imagen") or cert.get("plat_img"),
        "source_provider": _infer_provider_from_cert(cert) or nombre.upper(),
    }]


def _normalize_item_to_legacy_shape(item: dict) -> dict:
    if not isinstance(item, dict):
        return {
            "certificaciones": [],
            "temas": [],
            "universidades": [],
            "plataformas": [],
        }

    if any(k in item for k in ("certificaciones", "temas", "universidades", "plataformas")):
        return {
            "certificaciones": _ensure_list(item.get("certificaciones")),
            "temas": _ensure_list(item.get("temas")),
            "universidades": _ensure_list(item.get("universidades")),
            "plataformas": _ensure_list(item.get("plataformas")),
        }

    cert = dict(item)

    temas = [{"nombre": x} for x in _extract_skill_names_from_cert(cert)]
    universidades = _build_university_rows_from_cert(cert)
    plataformas = _build_platform_rows_from_cert(cert)

    return {
        "certificaciones": [cert],
        "temas": temas,
        "universidades": universidades,
        "plataformas": plataformas,
    }


def upsert_skill(item: dict) -> tuple[Skills | None, bool]:
    nombre = _norm(
        item.get("nombre")
        or item.get("name")
        or item.get("label")
        or item.get("skill")
        or item.get("value")
        or item.get("skill_name")
        or item.get("subskill_name")
    )
    if not nombre:
        return None, False

    lookup = {"nombre": nombre}

    defaults = {}
    if _has_field(Skills, "translate"):
        defaults["translate"] = _norm(item.get("translate"))
    if _has_field(Skills, "descripcion"):
        defaults["descripcion"] = _norm(item.get("descripcion"))
    if _has_field(Skills, "slug"):
        defaults["slug"] = safe_slug_from_name(nombre)[:300] or None
    if _has_field(Skills, "skill_img"):
        defaults["skill_img"] = item.get("skill_img") or item.get("tem_img")
    if _has_field(Skills, "skill_ico"):
        defaults["skill_ico"] = item.get("skill_ico") or item.get("tem_ico")
    if _has_field(Skills, "skill_type"):
        defaults["skill_type"] = _norm(item.get("skill_type") or item.get("tem_type"))
    if _has_field(Skills, "skill_col"):
        defaults["skill_col"] = _norm(item.get("skill_col"))
    if _has_field(Skills, "estado"):
        defaults["estado"] = True
    if _has_field(Skills, "external_skill_id"):
        defaults["external_skill_id"] = _norm(item.get("external_skill_id") or item.get("skill_id") or item.get("subskill_id")) or None
    if _has_field(Skills, "source_provider"):
        defaults["source_provider"] = _norm(item.get("source_provider") or item.get("provider")) or None
    if _has_field(Skills, "raw_payload"):
        defaults["raw_payload"] = item if isinstance(item, dict) else {}

    obj, created = _safe_get_or_create_unique(
        Skills,
        lookup=lookup,
        defaults=defaults,
    )

    updates = {}
    if _has_field(Skills, "translate"):
        new_translate = _norm(item.get("translate"))
        if new_translate:
            updates["translate"] = new_translate

    if _has_field(Skills, "descripcion"):
        new_desc = _norm(item.get("descripcion"))
        if new_desc:
            updates["descripcion"] = new_desc

    if _has_field(Skills, "skill_img"):
        new_img = item.get("skill_img") or item.get("tem_img")
        ##if new_img:
        ##    updates["skill_img"] = new_img

    if _has_field(Skills, "skill_ico"):
        new_ico = item.get("skill_ico") or item.get("tem_ico")
        ##if new_ico:
        ##    updates["skill_ico"] = new_ico

    if _has_field(Skills, "skill_col"):
        new_col = _norm(item.get("skill_col"))
        if new_col:
            updates["skill_col"] = new_col

    if _has_field(Skills, "estado"):
        updates["estado"] = True

    if _has_field(Skills, "external_skill_id"):
        ext_id = _norm(item.get("external_skill_id") or item.get("skill_id") or item.get("subskill_id"))
        if ext_id:
            updates["external_skill_id"] = ext_id

    if _has_field(Skills, "source_provider"):
        provider = _norm(item.get("source_provider") or item.get("provider"))
        if provider:
            updates["source_provider"] = provider

    if _has_field(Skills, "raw_payload") and isinstance(item, dict) and item:
        updates["raw_payload"] = item

    _apply_updates(obj, updates)
    return obj, created


def upsert_skill_by_name(
    nombre: str,
    skill_type: str | None = None,
    parent_obj: Skills | None = None,
    external_skill_id: str | None = None,
    source_provider: str | None = None,
    raw_payload: dict | None = None,
) -> tuple[Skills | None, bool]:
    nombre = _norm(nombre)
    if not nombre:
        return None, False

    defaults = {}
    if _has_field(Skills, "slug"):
        defaults["slug"] = safe_slug_from_name(nombre)[:300] or None
    if _has_field(Skills, "estado"):
        defaults["estado"] = True
    if _has_field(Skills, "skill_type") and skill_type:
        defaults["skill_type"] = skill_type
    if _has_field(Skills, "external_skill_id") and external_skill_id:
        defaults["external_skill_id"] = external_skill_id
    if _has_field(Skills, "source_provider") and source_provider:
        defaults["source_provider"] = source_provider
    if _has_field(Skills, "raw_payload") and raw_payload:
        defaults["raw_payload"] = raw_payload

    obj, created = _safe_get_or_create_unique(
        Skills,
        lookup={"nombre": nombre},
        defaults=defaults,
    )

    updates = {}
    if _has_field(Skills, "estado"):
        updates["estado"] = True

    if _has_field(Skills, "skill_type") and skill_type and not getattr(obj, "skill_type", None):
        updates["skill_type"] = skill_type

    if _has_field(Skills, "parent") and parent_obj:
        if getattr(obj, "parent_id", None) != parent_obj.id:
            updates["parent"] = parent_obj

    if _has_field(Skills, "external_skill_id") and external_skill_id:
        if getattr(obj, "external_skill_id", None) != external_skill_id:
            updates["external_skill_id"] = external_skill_id

    if _has_field(Skills, "source_provider") and source_provider:
        if getattr(obj, "source_provider", None) != source_provider:
            updates["source_provider"] = source_provider

    if _has_field(Skills, "raw_payload") and raw_payload:
        updates["raw_payload"] = raw_payload

    _apply_updates(obj, updates)

    return obj, created


def upsert_instructor(item: dict) -> tuple[Instructores | None, bool]:
    nombre = _norm(
        item.get("nombre")
        or item.get("name")
        or item.get("label")
    )
    if not nombre:
        return None, False

    lookup = {"nombre": nombre}
    defaults = {}

    if _has_field(Instructores, "imagen"):
        defaults["imagen"] = item.get("imagen") or item.get("image") or item.get("foto") or item.get("img")

    if _has_field(Instructores, "estado"):
        defaults["estado"] = True

    obj, created = _safe_get_or_create_unique(
        Instructores,
        lookup=lookup,
        defaults=defaults,
    )

    updates = {}
    if _has_field(Instructores, "imagen"):
        new_img = item.get("imagen") or item.get("image") or item.get("foto") or item.get("img")
        if new_img:
            updates["imagen"] = new_img

    if _has_field(Instructores, "estado"):
        updates["estado"] = True

    _apply_updates(obj, updates)
    return obj, created


def upsert_universidad(item: dict) -> tuple[Universidades | None, bool]:
    nombre = _norm(item.get("nombre"))
    if not nombre:
        return None, False

    defaults = {
        "univ_img": item.get("univ_img"),
        "univ_est": item.get("univ_est") or "enabled",
    }

    if _has_field(Universidades, "descripcion_institucion"):
        defaults["descripcion_institucion"] = _norm(item.get("descripcion_institucion"))

    if _has_field(Universidades, "region_universidad"):
        defaults["region_universidad"] = None
    if _has_field(Universidades, "univ_fla"):
        defaults["univ_fla"] = None
    if _has_field(Universidades, "univ_ico"):
        defaults["univ_ico"] = None
    if _has_field(Universidades, "univ_top"):
        defaults["univ_top"] = None

    obj, created = _safe_get_or_create_unique(
        Universidades,
        lookup={"nombre": nombre},
        defaults=defaults,
    )

    updates = {}
    new_desc = _norm(item.get("descripcion_institucion"))

    if new_desc and _has_field(Universidades, "descripcion_institucion"):
        updates["descripcion_institucion"] = new_desc

    new_img = item.get("univ_img")
    ##if new_img and _has_field(Universidades, "univ_img"):
    ##    updates["univ_img"] = new_img

    _apply_updates(obj, updates)
    return obj, created


def upsert_plataforma(item: dict) -> tuple[Plataformas | None, bool]:
    nombre = _norm(item.get("nombre"))
    if not nombre:
        return None, False

    defaults = {"plat_img": item.get("plat_img")}
    if _has_field(Plataformas, "plat_ico"):
        defaults["plat_ico"] = None
    if _has_field(Plataformas, "source_provider"):
        defaults["source_provider"] = _norm(item.get("source_provider")) or None

    obj, created = _safe_get_or_create_unique(
        Plataformas,
        lookup={"nombre": nombre},
        defaults=defaults,
    )

    updates = {}
    new_img = item.get("plat_img")
    ##if new_img and _has_field(Plataformas, "plat_img"):
    ##    updates["plat_img"] = new_img

    if _has_field(Plataformas, "source_provider"):
        source_provider = _norm(item.get("source_provider"))
        if source_provider:
            updates["source_provider"] = source_provider

    _apply_updates(obj, updates)
    return obj, created


def upsert_empresa_por_nombre(nombre: str, descripcion_institucion: str | None = None) -> tuple[Empresas | None, bool, bool]:
    nombre = _norm(nombre)
    descripcion_institucion = _norm(descripcion_institucion)

    if not nombre:
        return None, False, False

    defaults = {"empr_est": "enabled"}
    if _has_field(Empresas, "descripcion_institucion"):
        defaults["descripcion_institucion"] = descripcion_institucion or None

    obj, created = _safe_get_or_create_unique(
        Empresas,
        lookup={"nombre": nombre},
        defaults=defaults,
    )

    updated_description = False
    updates = {"empr_est": "enabled"}

    if descripcion_institucion and _has_field(Empresas, "descripcion_institucion"):
        if getattr(obj, "descripcion_institucion", None) != descripcion_institucion:
            updates["descripcion_institucion"] = descripcion_institucion
            updated_description = True

    _apply_updates(obj, updates)
    return obj, created, updated_description


def upsert_specialization(cert: dict | None = None) -> tuple[Specialization | None, bool]:
    if not cert:
        return None, False

    specialization_id = _norm(cert.get("specialization_id"))
    specialization_name = _norm(cert.get("specialization_name"))
    provider = _infer_provider_from_cert(cert)

    if not specialization_id:
        return None, False

    defaults = {
        "specialization_name": specialization_name or specialization_id,
        "provider": provider or None,
        "raw_payload": cert if isinstance(cert, dict) else {},
        "estado": True,
    }

    obj, created = _safe_get_or_create_unique(
        Specialization,
        lookup={"specialization_id": specialization_id},
        defaults=defaults,
    )

    updates = {}
    if specialization_name:
        updates["specialization_name"] = specialization_name
    if provider:
        updates["provider"] = provider
    if isinstance(cert, dict) and cert:
        updates["raw_payload"] = cert
    if _has_field(Specialization, "estado"):
        updates["estado"] = True

    _apply_updates(obj, updates)
    return obj, created


def _find_existing_certificacion(cert: dict, plat_fk=None, univ_fk=None, empresa_fk=None):
    url_original = _norm(cert.get("url_certificacion_original"))
    nombre = _norm(cert.get("nombre"))

    if url_original and url_original.lower() != "null":
        obj = Certificaciones.objects.filter(url_certificacion_original=url_original).order_by("id").first()
        if obj:
            return obj

    qs = Certificaciones.objects.filter(nombre=nombre)

    if plat_fk is not None and _has_field(Certificaciones, "plataforma_certificacion"):
        qs = qs.filter(plataforma_certificacion=plat_fk)

    if univ_fk is not None and _has_field(Certificaciones, "universidad_certificacion"):
        qs = qs.filter(universidad_certificacion=univ_fk)

    if empresa_fk is not None and _has_field(Certificaciones, "empresa_certificacion"):
        qs = qs.filter(empresa_certificacion=empresa_fk)

    obj = qs.order_by("id").first()
    if obj:
        return obj

    slug = safe_slug_from_name(nombre)
    if slug:
        return Certificaciones.objects.filter(slug=slug).order_by("id").first()

    return None


def upsert_certificacion(cert: dict, univ_map: dict, plat_map: dict, reconciliation_snapshot: dict | None = None) -> tuple[Certificaciones, bool]:
    nombre = _norm(cert.get("nombre"))
    if not nombre:
        raise ValueError("Certificación sin nombre")

    univ_name = _norm(cert.get("universidad_certificacion")).lower()
    plat_name = _normalize_provider_for_platform(cert).lower()
    empresa_name = _norm(cert.get("empresa_certificacion"))
    descripcion_inst = _norm(cert.get("descripcion_institucion_certificacion"))

    univ_fk = univ_map.get(univ_name) if univ_name else None
    plat_fk = plat_map.get(plat_name) if plat_name else None
    empresa_fk, _, _ = (
        upsert_empresa_por_nombre(
            empresa_name,
            descripcion_institucion=descripcion_inst,
        )
        if empresa_name else (None, False, False)
    )

    specialization_obj, _ = upsert_specialization(cert)

    obj = _find_existing_certificacion(cert, plat_fk=plat_fk, univ_fk=univ_fk, empresa_fk=empresa_fk)
    slug_value = build_unique_slug(Certificaciones, nombre, existing_obj=obj, max_length=500)

    merged_skill_names = _extract_skill_names_from_cert(cert)
    habilidades_value = ", ".join(merged_skill_names) if merged_skill_names else clean_habilidades(cert.get("habilidades_certificacion"))
    instructores_legacy = build_instructores_legacy_text(cert)
    lenguaje_value = (
        _norm(cert.get("lenguaje_certificacion"))
        or _norm(cert.get("language"))
        or _norm(cert.get("language_normalized"))
        or "NONE"
    )

    normalized_language = normalize_language_value(
        cert.get("language_normalized")
        or cert.get("lenguaje_certificacion")
        or cert.get("language")
        or lenguaje_value
    )

    language_normalized_value = (
        normalized_language["code"]
        if normalized_language
        else None
    )

    defaults = {
        "nombre": nombre,
        "slug": slug_value,
        "palabra_clave_certificacion": cert.get("palabra_clave_certificacion") or "NONE",
        "metadescripcion_certificacion": cert.get("metadescripcion_certificacion") or "NONE",
        "instructores_certificacion": cert.get("instructores_certificacion") or instructores_legacy or "NONE",
        "nivel_certificacion": cert.get("nivel_certificacion") or "NONE",
        "tiempo_certificacion": cert.get("tiempo_certificacion") or "NONE",
        "lenguaje_certificacion": lenguaje_value,
        "aprendizaje_certificacion": cert.get("aprendizaje_certificacion") or "NONE",
        "habilidades_certificacion": habilidades_value or "NONE",
        "experiencia_certificacion": cert.get("experiencia_certificacion") or "NONE",
        "testimonios_certificacion": cert.get("testimonios_certificacion") or "NONE",
        "contenido_certificacion": cert.get("contenido_certificacion") or "NONE",
        "modulos_certificacion": cert.get("modulos_certificacion") or "NONE",
        "tipo_certificacion": _norm(cert.get("tipo_certificacion")) or "NONE",
        "vigente_certificacion": _to_bool(cert.get("vigente_certificacion"), True),
        "universidad_certificacion": univ_fk,
        "empresa_certificacion": empresa_fk,
        "plataforma_certificacion": plat_fk,
        "url_certificacion_original": _norm(cert.get("url_certificacion_original")) or "Null",
        "video_certificacion": cert.get("video_certificacion") or "Null",
        "imagen_final": cert.get("imagen_final") or "",
    }

    if _has_field(Certificaciones, "tema_certificacion"):
        tema_val = cert.get("tema_certificacion")
        if tema_val is None:
            defaults["tema_certificacion"] = getattr(obj, "tema_certificacion", None) if obj else None

    if _has_field(Certificaciones, "source_provider"):
        defaults["source_provider"] = _infer_provider_from_cert(cert) or None

    if _has_field(Certificaciones, "specialization"):
        defaults["specialization"] = specialization_obj

    if _has_field(Certificaciones, "specialization_id_external"):
        defaults["specialization_id_external"] = _norm(cert.get("specialization_id")) or None

    if _has_field(Certificaciones, "specialization_name_external"):
        defaults["specialization_name_external"] = _norm(cert.get("specialization_name")) or None

    if _has_field(Certificaciones, "country"):
        defaults["country"] = _norm(cert.get("country")) or "Global"

    if _has_field(Certificaciones, "region"):
        defaults["region"] = _norm(cert.get("region")) or "Global"

    if _has_field(Certificaciones, "mapping_status"):
        defaults["mapping_status"] = _norm(cert.get("mapping_status")) or "uncategorized"

    if _has_field(Certificaciones, "language_normalized"):
        defaults["language_normalized"] = language_normalized_value

    if _has_field(Certificaciones, "skills_internal_json"):
        defaults["skills_internal_json"] = _ensure_list(cert.get("skills_internal"))

    if _has_field(Certificaciones, "subskills_internal_json"):
        defaults["subskills_internal_json"] = _ensure_list(cert.get("subskills_internal"))

    if _has_field(Certificaciones, "reconciliation_snapshot"):
        defaults["reconciliation_snapshot"] = reconciliation_snapshot or {}

    if _has_field(Certificaciones, "raw_payload"):
        defaults["raw_payload"] = cert if isinstance(cert, dict) else {}

    if obj is None:
        obj = Certificaciones.objects.create(**defaults)
        return obj, True

    _apply_updates(obj, defaults)
    return obj, False


def sync_certification_skills(cert_obj: Certificaciones, skill_names: list[str]) -> dict:
    skill_names = _dedupe_keep_order(skill_names)

    created_skills = 0
    linked = 0
    unlinked = 0

    desired_skill_ids = []

    for order, skill_name in enumerate(skill_names, start=1):
        skill_obj, created = upsert_skill_by_name(skill_name)
        if not skill_obj:
            continue

        if created:
            created_skills += 1

        desired_skill_ids.append(skill_obj.id)

        rel, rel_created = SkillsCertification.objects.get_or_create(
            certificacion_id=cert_obj.id,
            skill_id=skill_obj.id,
            defaults={"orden": order},
        )

        if rel_created:
            linked += 1
        elif rel.orden != order:
            rel.orden = order
            rel.save(update_fields=["orden"])

    current_qs = SkillsCertification.objects.filter(certificacion_id=cert_obj.id)

    if desired_skill_ids:
        to_delete_qs = current_qs.exclude(skill_id__in=desired_skill_ids)
    else:
        to_delete_qs = current_qs

    deleted_count, _ = to_delete_qs.delete()
    unlinked += int(deleted_count or 0)

    return {
        "skills_created": created_skills,
        "skills_linked": linked,
        "skills_unlinked": unlinked,
        "certification_skill_count": len(desired_skill_ids),
    }


def sync_certification_instructors(cert_obj: Certificaciones, instructor_rows: list[dict]) -> dict:
    created_instructors = 0
    linked = 0
    unlinked = 0

    desired_instructor_ids = []

    for row in instructor_rows or []:
        instructor_obj, created = upsert_instructor(row)
        if not instructor_obj:
            continue

        if created:
            created_instructors += 1

        desired_instructor_ids.append(instructor_obj.id)

        _, rel_created = InstructorCertification.objects.get_or_create(
            certificacion_id=cert_obj.id,
            instructor_id=instructor_obj.id,
        )

        if rel_created:
            linked += 1

    current_qs = InstructorCertification.objects.filter(certificacion_id=cert_obj.id)

    if desired_instructor_ids:
        to_delete_qs = current_qs.exclude(instructor_id__in=desired_instructor_ids)
    else:
        to_delete_qs = current_qs

    deleted_count, _ = to_delete_qs.delete()
    unlinked += int(deleted_count or 0)

    return {
        "instructors_created": created_instructors,
        "instructors_linked": linked,
        "instructors_unlinked": unlinked,
        "certification_instructor_count": len(desired_instructor_ids),
    }


def update_institution_description_from_cert(cert: dict, cert_obj: Certificaciones) -> dict:
    descripcion = _norm(cert.get("descripcion_institucion_certificacion"))
    if not descripcion:
        return {
            "institutions_updated": 0,
            "companies_updated": 0,
            "universities_updated": 0,
        }

    institutions_updated = 0
    companies_updated = 0
    universities_updated = 0

    if getattr(cert_obj, "universidad_certificacion_id", None) and _has_field(Universidades, "descripcion_institucion"):
        uni = cert_obj.universidad_certificacion
        if uni and getattr(uni, "descripcion_institucion", None) != descripcion:
            uni.descripcion_institucion = descripcion
            uni.save(update_fields=["descripcion_institucion"])
            institutions_updated += 1
            universities_updated += 1

    if getattr(cert_obj, "empresa_certificacion_id", None) and _has_field(Empresas, "descripcion_institucion"):
        emp = cert_obj.empresa_certificacion
        if emp and getattr(emp, "descripcion_institucion", None) != descripcion:
            emp.descripcion_institucion = descripcion
            emp.save(update_fields=["descripcion_institucion"])
            institutions_updated += 1
            companies_updated += 1

    return {
        "institutions_updated": institutions_updated,
        "companies_updated": companies_updated,
        "universities_updated": universities_updated,
    }


def save_reconciliation_snapshot(payload: dict, resource: str = "courses", provider_filter: str | None = None, page: int = 1, page_size: int = 20):
    reconciliation = payload.get("reconciliation")
    if not isinstance(reconciliation, dict):
        return None

    snapshot = ExternalReconciliationSnapshot.objects.create(
        resource=resource,
        provider_filter=provider_filter or None,
        page=page or 1,
        page_size=page_size or 20,
        payload=reconciliation,
    )
    return snapshot


@transaction.atomic
def ingest_course_payload(payload: dict, resource: str = "courses", provider_filter: str | None = None) -> dict:
    items = payload.get("items") or []
    page = payload.get("page") or 1
    page_size = payload.get("pageSize") or payload.get("page_size") or 20
    reconciliation = payload.get("reconciliation") if isinstance(payload.get("reconciliation"), dict) else {}

    save_reconciliation_snapshot(
        payload=payload,
        resource=resource,
        provider_filter=provider_filter,
        page=page,
        page_size=page_size,
    )

    created_skills_catalog = 0
    created_unis = 0
    created_plats = 0
    created_companies = 0
    created_instructors = 0
    created_specializations = 0

    created_certs = 0
    updated_certs = 0
    skipped_invalid = 0
    duplicates_detected = 0

    skills_created = 0
    skills_linked = 0
    skills_unlinked = 0

    instructors_linked = 0
    instructors_unlinked = 0
    certifications_without_skills = 0
    certifications_without_instructors = 0

    institutions_updated = 0
    companies_updated = 0
    universities_updated = 0

    for raw_item in items:
        item = _normalize_item_to_legacy_shape(raw_item)

        skills_map = {}

        for s in (item.get("temas") or []):
            if not isinstance(s, dict):
                continue

            skill_obj, created = upsert_skill(s)
            if not skill_obj:
                continue

            if created:
                created_skills_catalog += 1

            skills_map[_norm(skill_obj.nombre).lower()] = skill_obj

        unis_map = {}
        for u in (item.get("universidades") or []):
            if not isinstance(u, dict):
                continue

            nombre = _norm(u.get("nombre"))
            if not nombre:
                continue

            qs = Universidades.objects.filter(nombre=nombre)
            if qs.count() > 1:
                duplicates_detected += 1

            obj, created = upsert_universidad(u)
            if not obj:
                continue

            if created:
                created_unis += 1

            unis_map[nombre.lower()] = obj

        plats_map = {}
        for p in (item.get("plataformas") or []):
            if not isinstance(p, dict):
                continue

            nombre = _norm(p.get("nombre"))
            if not nombre:
                continue

            obj, created = upsert_plataforma(p)
            if not obj:
                continue

            if created:
                created_plats += 1

            plats_map[nombre.lower()] = obj

        legacy_item_skill_names = extract_certification_skill_names(item=item)

        for c in (item.get("certificaciones") or []):
            if not isinstance(c, dict):
                skipped_invalid += 1
                continue

            nombre = _norm(c.get("nombre"))
            if not nombre:
                skipped_invalid += 1
                continue

            try:
                with transaction.atomic():
                    spec_obj, spec_created = upsert_specialization(c)
                    if spec_created:
                        created_specializations += 1

                    cert_obj, cert_created = upsert_certificacion(
                        c,
                        univ_map=unis_map,
                        plat_map=plats_map,
                        reconciliation_snapshot=reconciliation,
                    )

                    if cert_created:
                        created_certs += 1
                    else:
                        updated_certs += 1

                    empresa_name = _norm(c.get("empresa_certificacion"))
                    descripcion_inst = _norm(c.get("descripcion_institucion_certificacion"))
                    if empresa_name:
                        _, company_created, company_desc_updated = upsert_empresa_por_nombre(
                            empresa_name,
                            descripcion_institucion=descripcion_inst,
                        )
                        if company_created:
                            created_companies += 1
                        if company_desc_updated:
                            institutions_updated += 1
                            companies_updated += 1

                    inst_res = update_institution_description_from_cert(c, cert_obj)
                    institutions_updated += inst_res["institutions_updated"]
                    companies_updated += inst_res["companies_updated"]
                    universities_updated += inst_res["universities_updated"]

                    cert_skill_names = _extract_skill_names_from_cert(c)
                    if not cert_skill_names:
                        cert_skill_names = legacy_item_skill_names

                    normalized_names = []
                    for skill_name in cert_skill_names:
                        skill_name = _norm(skill_name)
                        if not skill_name:
                            continue

                        catalog_skill = skills_map.get(skill_name.lower())
                        if catalog_skill:
                            normalized_names.append(catalog_skill.nombre)
                        else:
                            normalized_names.append(skill_name)

                    normalized_names = _dedupe_keep_order(normalized_names)

                    if not normalized_names:
                        certifications_without_skills += 1

                    sync_res = sync_certification_skills(cert_obj, normalized_names)
                    skills_created += sync_res["skills_created"]
                    skills_linked += sync_res["skills_linked"]
                    skills_unlinked += sync_res["skills_unlinked"]

                    instructor_rows = extract_instructors_from_cert(c)
                    if not instructor_rows:
                        certifications_without_instructors += 1

                    instructor_sync_res = sync_certification_instructors(cert_obj, instructor_rows)
                    created_instructors += instructor_sync_res["instructors_created"]
                    instructors_linked += instructor_sync_res["instructors_linked"]
                    instructors_unlinked += instructor_sync_res["instructors_unlinked"]

            except Exception as e:
                skipped_invalid += 1
                print(f"ERROR en certificación '{nombre}': {str(e)}")
                print(traceback.format_exc())
                continue

    return {
        "created": created_certs,
        "updated": updated_certs,
        "skipped": 0,
        "errors": skipped_invalid,

        "skills_catalog_created": created_skills_catalog,
        "skills_created": skills_created,
        "skills_linked": skills_linked,
        "skills_unlinked": skills_unlinked,

        "instructors_created": created_instructors,
        "instructors_linked": instructors_linked,
        "instructors_unlinked": instructors_unlinked,

        "universities_created": created_unis,
        "platforms_created": created_plats,
        "companies_created": created_companies,
        "specializations_created": created_specializations,

        "institutions_updated": institutions_updated,
        "companies_updated": companies_updated,
        "universities_updated": universities_updated,

        "certifications_without_skills": certifications_without_skills,
        "certifications_without_instructors": certifications_without_instructors,
        "duplicates_detected": duplicates_detected,
        "received_items": len(items),
        "reconciliation_saved": bool(reconciliation),
        "resource": resource,
        "provider_filter": provider_filter,
    }


@transaction.atomic
def ingest_skills_structure_payload(payload: dict, provider_filter: str | None = None) -> dict:
    items = payload.get("items") or []

    skills_created = 0
    subskills_created = 0
    parent_links_updated = 0

    for row in items:
        if not isinstance(row, dict):
            continue

        skill_name = _norm(row.get("skill_name") or row.get("nombre") or row.get("name"))
        skill_id = _norm(row.get("skill_id"))
        if not skill_name:
            continue

        parent_obj, parent_created = upsert_skill_by_name(
            skill_name,
            skill_type="tema",
            external_skill_id=skill_id or None,
            source_provider=provider_filter,
            raw_payload=row,
        )
        if not parent_obj:
            continue

        if parent_created:
            skills_created += 1

        for sub in (row.get("subskills") or []):
            if not isinstance(sub, dict):
                continue

            subskill_name = _norm(sub.get("subskill_name") or sub.get("nombre") or sub.get("name"))
            subskill_id = _norm(sub.get("subskill_id"))
            if not subskill_name:
                continue

            before_parent_id = None
            existing_child = Skills.objects.filter(nombre=subskill_name).order_by("id").first()
            if existing_child is not None:
                before_parent_id = getattr(existing_child, "parent_id", None)

            child_obj, child_created = upsert_skill_by_name(
                subskill_name,
                skill_type="habilidad",
                parent_obj=parent_obj,
                external_skill_id=subskill_id or None,
                source_provider=provider_filter,
                raw_payload=sub,
            )
            if not child_obj:
                continue

            if child_created:
                subskills_created += 1

            if before_parent_id != parent_obj.id and getattr(child_obj, "parent_id", None) == parent_obj.id:
                parent_links_updated += 1

    return {
        "skills_created": skills_created,
        "subskills_created": subskills_created,
        "parent_links_updated": parent_links_updated,
        "received_items": len(items),
        "total_skills": payload.get("total_skills"),
        "total_subskills": payload.get("total_subskills"),
        "provider_filter": provider_filter,
    }


@transaction.atomic
def ingest_specializations_payload(payload: dict, provider_filter: str | None = None) -> dict:
    items = payload.get("items") or []

    processed = 0
    skipped = 0
    created = 0
    updated = 0

    for row in items:
        if not isinstance(row, dict):
            skipped += 1
            continue

        specialization_id = _norm(row.get("specialization_id"))
        specialization_name = _norm(row.get("specialization_name"))
        provider = _norm(row.get("provider")) or provider_filter

        if not specialization_id or not specialization_name:
            skipped += 1
            continue

        obj, was_created = _safe_get_or_create_unique(
            Specialization,
            lookup={"specialization_id": specialization_id},
            defaults={
                "specialization_name": specialization_name,
                "provider": provider or None,
                "raw_payload": row,
                "estado": True,
            },
        )

        updates = {
            "specialization_name": specialization_name,
            "provider": provider or None,
            "raw_payload": row,
            "estado": True,
        }
        changed = _apply_updates(obj, updates)

        if was_created:
            created += 1
        elif changed:
            updated += 1

        processed += 1

    return {
        "processed": processed,
        "created": created,
        "updated": updated,
        "skipped": skipped,
        "received_items": len(items),
        "page": payload.get("page"),
        "pageSize": payload.get("pageSize"),
        "total": payload.get("total"),
        "totalPages": payload.get("totalPages"),
        "provider_filter": provider_filter,
    }


@transaction.atomic
def ingest_specialization_detail_payload(payload: dict, specialization_id: str | None = None, provider_filter: str | None = None) -> dict:
    specialization = payload.get("specialization") if isinstance(payload.get("specialization"), dict) else {}
    items = payload.get("items") or []

    effective_specialization_id = specialization_id or _norm(specialization.get("specialization_id"))
    specialization_name = _norm(specialization.get("specialization_name"))
    provider = _norm(specialization.get("provider")) or provider_filter

    spec_obj = None
    if effective_specialization_id:
        spec_obj, _ = _safe_get_or_create_unique(
            Specialization,
            lookup={"specialization_id": effective_specialization_id},
            defaults={
                "specialization_name": specialization_name or effective_specialization_id,
                "provider": provider or None,
                "raw_payload": specialization or {},
                "estado": True,
            },
        )

        _apply_updates(spec_obj, {
            "specialization_name": specialization_name or effective_specialization_id,
            "provider": provider or None,
            "raw_payload": specialization or {},
            "estado": True,
        })

    patched_items = []
    for row in items:
        if not isinstance(row, dict):
            continue
        row_copy = dict(row)

        if effective_specialization_id and not row_copy.get("specialization_id"):
            row_copy["specialization_id"] = effective_specialization_id

        if specialization_name and not row_copy.get("specialization_name"):
            row_copy["specialization_name"] = specialization_name

        if provider and not row_copy.get("provider"):
            row_copy["provider"] = provider

        patched_items.append(row_copy)

    summary = ingest_course_payload(
        {"items": patched_items, "reconciliation": payload.get("reconciliation") or {}},
        resource="specialization-detail",
        provider_filter=provider_filter,
    )

    return {
        "specialization_db_id": getattr(spec_obj, "id", None),
        "specialization_id": effective_specialization_id,
        "specialization_name": specialization_name,
        "courses_summary": summary,
        "total": payload.get("total"),
        "received_items": len(items),
        "provider_filter": provider_filter,
    }