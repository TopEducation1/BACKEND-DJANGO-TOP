from django.db import transaction
from django.utils.text import slugify
from django.utils import timezone

import re
import json
import traceback
from unidecode import unidecode

from topeducation.models import Temas, Universidades, Empresas, Plataformas, Certificaciones


def _norm(s: str) -> str:
    return (s or "").strip()


def _pick_one(qs, order_by="id"):
    """
    Devuelve 1 objeto de un queryset (o None) de forma determinística.
    """
    return qs.order_by(order_by).first()


def _safe_get_or_create_unique(model, lookup: dict, defaults: dict, *, order_by="id"):
    """
    Alternativa segura a get_or_create cuando puede haber duplicados.
    - Si existe 1: retorna (obj, False)
    - Si existen varios: retorna (obj_elegido, False) sin reventar
    - Si no existe: crea y retorna (obj, True)
    """
    qs = model.objects.filter(**lookup)
    obj = _pick_one(qs, order_by=order_by)
    if obj:
        return obj, False
    # crear
    obj = model.objects.create(**lookup, **defaults)
    return obj, True


def upsert_tema(item: dict) -> Temas:
    nombre = _norm(item.get("nombre"))
    if not nombre:
        # si te llega vacío, evita crear registros raros
        # (puedes decidir otro comportamiento)
        return Temas.objects.filter(nombre="").first()  # type: ignore[return-value]

    obj, created = _safe_get_or_create_unique(
        Temas,
        lookup={"nombre": nombre},
        defaults={
            "tem_type": item.get("tem_type"),
            "tem_img": item.get("tem_img"),
            "tem_est": "enabled",
            "tem_col": None,
        },
    )

    changed = False
    for field, val in {
        "tem_type": item.get("tem_type"),
        "tem_img": item.get("tem_img"),
        "tem_est": "enabled",
    }.items():
        if val is not None and getattr(obj, field) != val:
            setattr(obj, field, val)
            changed = True

    if changed:
        obj.save(update_fields=["tem_type", "tem_img", "tem_est"])
    return obj


def upsert_universidad(item: dict) -> Universidades:
    nombre = _norm(item.get("nombre"))
    if not nombre:
        return Universidades.objects.filter(nombre="").first()  # type: ignore[return-value]

    obj, created = _safe_get_or_create_unique(
        Universidades,
        lookup={"nombre": nombre},
        defaults={
            "univ_img": item.get("univ_img"),
            "univ_est": item.get("univ_est") or "enabled",
            "region_universidad": None,
            "univ_fla": None,
            "univ_ico": None,
            "univ_top": None,
        },
    )

    new_img = item.get("univ_img")
    new_est = item.get("univ_est") or getattr(obj, "univ_est", "enabled")
    changed = False
    if new_img and getattr(obj, "univ_img", None) != new_img:
        obj.univ_img = new_img
        changed = True
    if new_est and getattr(obj, "univ_est", None) != new_est:
        obj.univ_est = new_est
        changed = True
    if changed:
        obj.save(update_fields=["univ_img", "univ_est"])
    return obj


def upsert_plataforma(item: dict) -> Plataformas:
    nombre = _norm(item.get("nombre"))
    if not nombre:
        return Plataformas.objects.filter(nombre="").first()  # type: ignore[return-value]

    obj, created = _safe_get_or_create_unique(
        Plataformas,
        lookup={"nombre": nombre},
        defaults={
            "plat_img": item.get("plat_img"),
            "plat_ico": None,
        },
    )

    new_img = item.get("plat_img")
    if new_img and getattr(obj, "plat_img", None) != new_img:
        obj.plat_img = new_img
        obj.save(update_fields=["plat_img"])
    return obj


def upsert_empresa_por_nombre(nombre: str) -> Empresas | None:
    nombre = _norm(nombre)
    if not nombre:
        return None

    # también tolerante a duplicados
    obj, _ = _safe_get_or_create_unique(
        Empresas,
        lookup={"nombre": nombre},
        defaults={"empr_est": "enabled"},
    )
    return obj


def upsert_certificacion(cert: dict, temas_map: dict, univ_map: dict, plat_map: dict) -> Certificaciones:
    # FKs por nombre
    tema_name = _norm(cert.get("tema_certificacion"))
    univ_name = _norm(cert.get("universidad_certificacion"))
    plat_name = _norm(cert.get("plataforma_certificacion"))
    empresa_name = _norm(cert.get("empresa_certificacion"))

    tema_fk = temas_map.get(tema_name)
    univ_fk = univ_map.get(univ_name) if univ_name else None
    plat_fk = plat_map.get(plat_name) if plat_name else None
    empresa_fk = upsert_empresa_por_nombre(empresa_name) if empresa_name else None

    # llave única lógica
    url_original = _norm(cert.get("url_certificacion_original"))

    obj = None
    if url_original:
        obj = Certificaciones.objects.filter(url_certificacion_original=url_original).first()

    if not obj:
        obj = (Certificaciones.objects
               .filter(
                    nombre=_norm(cert.get("nombre")),
                    plataforma_certificacion=plat_fk,
                    universidad_certificacion=univ_fk
                )
               .first())

    defaults = {
        "nombre": _norm(cert.get("nombre")),
        "slug": slugify(_norm(cert.get("nombre")))[:500] or "default-slug",
        "tema_certificacion": tema_fk,
        "palabra_clave_certificacion": cert.get("palabra_clave_certificacion") or "NONE",
        "metadescripcion_certificacion": cert.get("metadescripcion_certificacion") or "NONE",
        "instructores_certificacion": cert.get("instructores_certificacion") or "NONE",
        "nivel_certificacion": cert.get("nivel_certificacion") or "NONE",
        "tiempo_certificacion": cert.get("tiempo_certificacion") or "NONE",
        "lenguaje_certificacion": cert.get("lenguaje_certificacion") or "NONE",
        "aprendizaje_certificacion": cert.get("aprendizaje_certificacion") or "NONE",
        "habilidades_certificacion": cert.get("habilidades_certificacion") or "NONE",
        "experiencia_certificacion": cert.get("experiencia_certificacion") or "NONE",
        "testimonios_certificacion": cert.get("testimonios_certificacion") or "NONE",
        "contenido_certificacion": cert.get("contenido_certificacion") or "NONE",
        "modulos_certificacion": cert.get("modulos_certificacion") or "NONE",
        "universidad_certificacion": univ_fk,
        "empresa_certificacion": empresa_fk,
        "plataforma_certificacion": plat_fk,
        "url_certificacion_original": url_original or "Null",
        "video_certificacion": cert.get("video_certificacion") or "Null",
        "imagen_final": cert.get("imagen_final") or "",
    }

    if obj is None:
        obj = Certificaciones.objects.create(**defaults)
        return obj

    changed_fields = []
    for k, v in defaults.items():
        if getattr(obj, k) != v:
            setattr(obj, k, v)
            changed_fields.append(k)

    if changed_fields:
        obj.save(update_fields=changed_fields)
    return obj


def _safe_str(v):
    return (v or "").strip() if isinstance(v, str) else ("" if v is None else str(v))


@transaction.atomic
def ingest_course_payload(payload: dict) -> dict:
    """
    payload esperado:
    { "items": [ { "certificaciones": [...], "temas": [...], "universidades": [...], "plataformas": [...] }, ... ] }
    """

    items = payload.get("items") or []
    created_temas = 0
    created_unis = 0
    created_plats = 0
    processed = 0
    skipped_existing = 0
    skipped_invalid = 0
    duplicates_detected = 0

    for item in items:
        temas_map = {}
        for t in (item.get("temas") or []):
            nombre = (t.get("nombre") or "").strip()
            if not nombre:
                continue

            # ✅ tolerante a duplicados
            obj, created = _safe_get_or_create_unique(
                Temas,
                lookup={"nombre": nombre},
                defaults={
                    "tem_img": t.get("tem_img"),
                    "tem_type": t.get("tem_type"),
                    "tem_est": "disabled",
                },
            )
            if created:
                created_temas += 1
            temas_map[nombre.lower()] = obj

        unis_map = {}
        for u in (item.get("universidades") or []):
            nombre = (u.get("nombre") or "").strip()
            if not nombre:
                continue

            # ✅ tolerante a duplicados
            qs = Universidades.objects.filter(nombre=nombre)
            if qs.count() > 1:
                duplicates_detected += 1

            obj = _pick_one(qs, "id")
            if obj:
                created = False
            else:
                obj = Universidades.objects.create(
                    nombre=nombre,
                    univ_img=u.get("univ_img"),
                    univ_est=u.get("univ_est") or "disabled",
                    region_universidad=None,
                )
                created = True

            if created:
                created_unis += 1

            # update ligero (si quieres)
            new_img = u.get("univ_img")
            new_est = u.get("univ_est")
            to_update = []
            if new_img and getattr(obj, "univ_img", None) != new_img:
                obj.univ_img = new_img
                to_update.append("univ_img")
            if new_est and getattr(obj, "univ_est", None) != new_est:
                obj.univ_est = new_est
                to_update.append("univ_est")
            if to_update:
                obj.save(update_fields=to_update)

            unis_map[nombre.lower()] = obj

        plats_map = {}
        for p in (item.get("plataformas") or []):
            nombre = (p.get("nombre") or "").strip()
            if not nombre:
                continue

            obj, created = _safe_get_or_create_unique(
                Plataformas,
                lookup={"nombre": nombre},
                defaults={"plat_img": p.get("plat_img")},
            )
            if created:
                created_plats += 1
            plats_map[nombre.lower()] = obj

        # 2) procesar certificaciones
        for c in (item.get("certificaciones") or []):
            nombre = (c.get("nombre") or "").strip()
            if not nombre:
                skipped_invalid += 1
                continue

            slug = safe_slug_from_name(nombre)
            if not slug:
                skipped_invalid += 1
                continue

            if Certificaciones.objects.filter(slug=slug).exists():
                skipped_existing += 1
                continue

            tema_name = (c.get("tema_certificacion") or "").strip().lower()
            tema_obj = temas_map.get(tema_name) if tema_name else None

            uni_name = (c.get("universidad_certificacion") or "").strip().lower()
            uni_obj = unis_map.get(uni_name) if uni_name else None

            plat_name = (c.get("plataforma_certificacion") or "").strip().lower()
            plat_obj = plats_map.get(plat_name) if plat_name else None

            empresa_obj = None
            emp_name = (c.get("empresa_certificacion") or "").strip()
            if emp_name:
                # ✅ tolerante a duplicados
                empresa_obj, _ = _safe_get_or_create_unique(
                    Empresas,
                    lookup={"nombre": emp_name},
                    defaults={"empr_est": "enabled"},
                )

            habilidades_limpias = clean_habilidades(c.get("habilidades_certificacion"))

            Certificaciones.objects.create(
                nombre=nombre,
                slug=slug,
                tema_certificacion=tema_obj,

                palabra_clave_certificacion=c.get("palabra_clave_certificacion") or "NONE",
                metadescripcion_certificacion=c.get("metadescripcion_certificacion") or "NONE",
                instructores_certificacion=c.get("instructores_certificacion") or "NONE",
                nivel_certificacion=c.get("nivel_certificacion") or "NONE",
                tiempo_certificacion=c.get("tiempo_certificacion") or "NONE",
                lenguaje_certificacion=c.get("lenguaje_certificacion") or "NONE",
                aprendizaje_certificacion=c.get("aprendizaje_certificacion") or "NONE",
                habilidades_certificacion=habilidades_limpias,
                experiencia_certificacion=c.get("experiencia_certificacion") or "NONE",
                testimonios_certificacion=c.get("testimonios_certificacion") or "NONE",
                contenido_certificacion=c.get("contenido_certificacion") or "NONE",
                modulos_certificacion=c.get("modulos_certificacion") or "NONE",

                universidad_certificacion=uni_obj,
                empresa_certificacion=empresa_obj,
                plataforma_certificacion=plat_obj,

                url_certificacion_original=c.get("url_certificacion_original") or "Null",
                video_certificacion=c.get("video_certificacion") or "Null",
                imagen_final=c.get("imagen_final") or "",
            )

            processed += 1

    return {
        "temas": created_temas,
        "universidades": created_unis,
        "plataformas": created_plats,
        "certificaciones_procesadas": processed,
        "skipped_existing": skipped_existing,
        "skipped_invalid": skipped_invalid,
        "duplicates_detected": duplicates_detected,  # útil para monitorear
    }


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
                )
                if t:
                    out.append(str(t).strip())

        seen = set()
        uniq = []
        for x in out:
            if x.lower() not in seen:
                seen.add(x.lower())
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
