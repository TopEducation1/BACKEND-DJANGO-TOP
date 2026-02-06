from django.db import transaction
from django.utils.text import slugify

import re
import json
from unidecode import unidecode

from topeducation.models import Temas, Universidades, Empresas, Plataformas, Certificaciones

def _norm(s: str) -> str:
    return (s or "").strip()

def upsert_tema(item: dict) -> Temas:
    nombre = _norm(item.get("nombre"))
    obj, _ = Temas.objects.get_or_create(
        nombre=nombre,
        defaults={
            "tem_type": item.get("tem_type"),
            "tem_img": item.get("tem_img"),
            "tem_est": "enabled",
            "tem_col": None,
        },
    )
    # update ligero
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
    obj, _ = Universidades.objects.get_or_create(
        nombre=nombre,
        defaults={
            "univ_img": item.get("univ_img"),
            "univ_est": item.get("univ_est") or "enabled",
            "region_universidad": None,
            "univ_fla": None,
            "univ_ico": None,
            "univ_top": None,
        },
    )
    # update ligero
    new_img = item.get("univ_img")
    new_est = item.get("univ_est") or obj.univ_est
    changed = False
    if new_img and obj.univ_img != new_img:
        obj.univ_img = new_img
        changed = True
    if new_est and obj.univ_est != new_est:
        obj.univ_est = new_est
        changed = True
    if changed:
        obj.save(update_fields=["univ_img", "univ_est"])
    return obj

def upsert_plataforma(item: dict) -> Plataformas:
    nombre = _norm(item.get("nombre"))
    obj, _ = Plataformas.objects.get_or_create(
        nombre=nombre,
        defaults={
            "plat_img": item.get("plat_img"),
            "plat_ico": None,
        },
    )
    new_img = item.get("plat_img")
    if new_img and obj.plat_img != new_img:
        obj.plat_img = new_img
        obj.save(update_fields=["plat_img"])
    return obj

def upsert_empresa_por_nombre(nombre: str) -> Empresas | None:
    nombre = _norm(nombre)
    if not nombre:
        return None
    obj, _ = Empresas.objects.get_or_create(
        nombre=nombre,
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
        # fallback por combinación
        obj = (Certificaciones.objects
               .filter(nombre=_norm(cert.get("nombre")),
                       plataforma_certificacion=plat_fk,
                       universidad_certificacion=univ_fk)
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

    # update (solo campos relevantes)
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

    for item in items:
        # 1) upsert temas / universidades / plataformas por nombre (opcional)
        #    (si tu lógica actual los crea en otra parte, puedes dejarlo)
        temas_map = {}
        for t in (item.get("temas") or []):
            nombre = (t.get("nombre") or "").strip()
            if not nombre:
                continue
            obj, created = Temas.objects.get_or_create(
                nombre=nombre,
                defaults={
                    "tem_img": t.get("tem_img"),
                    "tem_type": t.get("tem_type"),
                    "tem_est": "Active",
                }
            )
            if created:
                created_temas += 1
            temas_map[nombre.lower()] = obj

        unis_map = {}
        for u in (item.get("universidades") or []):
            nombre = (u.get("nombre") or "").strip()
            if not nombre:
                continue
            obj, created = Universidades.objects.get_or_create(
                nombre=nombre,
                defaults={
                    "univ_img": u.get("univ_img"),
                    "univ_est": u.get("univ_est") or "Active",
                    "region_universidad": None,
                }
            )
            if created:
                created_unis += 1
            unis_map[nombre.lower()] = obj

        plats_map = {}
        for p in (item.get("plataformas") or []):
            nombre = (p.get("nombre") or "").strip()
            if not nombre:
                continue
            obj, created = Plataformas.objects.get_or_create(
                nombre=nombre,
                defaults={"plat_img": p.get("plat_img")}
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

            # ✅ SLUG PROPIO (NO usar el del endpoint)
            slug = safe_slug_from_name(nombre)
            if not slug:
                skipped_invalid += 1
                continue

            # ✅ NO DUPLICAR: si existe por slug, no crear
            if Certificaciones.objects.filter(slug=slug).exists():
                skipped_existing += 1
                continue

            # relaciones por nombre
            tema_name = (c.get("tema_certificacion") or "").strip().lower()
            tema_obj = temas_map.get(tema_name) if tema_name else None

            uni_name = (c.get("universidad_certificacion") or "").strip().lower()
            uni_obj = unis_map.get(uni_name) if uni_name else None

            plat_name = (c.get("plataforma_certificacion") or "").strip().lower()
            plat_obj = plats_map.get(plat_name) if plat_name else None

            # empresa (si llega)
            empresa_obj = None
            emp_name = (c.get("empresa_certificacion") or "").strip()
            if emp_name:
                empresa_obj, _ = Empresas.objects.get_or_create(nombre=emp_name)

            # ✅ limpiar habilidades
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

                # si quieres respetar la fecha del endpoint, tendrías que cambiar el field
                # (tu modelo ahora es auto_now_add). Por ahora dejamos que se guarde “hoy”.
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
    }

def safe_slug_from_name(name: str) -> str:
    """
    Convierte el nombre a slug:
    - quita acentos (ñ->n, á->a, etc.)
    - baja a minúscula
    - reemplaza espacios por -
    - elimina símbolos raros
    - colapsa guiones repetidos
    """
    if not name:
        return ""

    s = unidecode(str(name))          # ñ -> n, á -> a
    s = s.lower().strip()
    s = re.sub(r"[^a-z0-9\s-]", "", s) # solo letras/números/espacios/guiones
    s = re.sub(r"\s+", "-", s)        # espacios -> -
    s = re.sub(r"-{2,}", "-", s)      # --- -> -
    s = s.strip("-")
    return s


def clean_habilidades(value) -> str:
    """
    Evita guardar "[object Object]" y normaliza habilidades a texto.
    Soporta:
    - list de strings
    - list de dicts (elige 'nombre'/'name'/'label'/'skill')
    - string con "[object Object]" mezclado
    """
    if value is None:
        return "NONE"

    # Si ya viene como lista/dict (ideal)
    if isinstance(value, list):
        out = []
        for item in value:
            if isinstance(item, str):
                t = item.strip()
                if t and t.lower() != "[object object]":
                    out.append(t)
            elif isinstance(item, dict):
                # intenta sacar un nombre razonable
                t = (
                    item.get("nombre")
                    or item.get("name")
                    or item.get("label")
                    or item.get("skill")
                    or item.get("value")
                )
                if t:
                    out.append(str(t).strip())
        # dedupe conservando orden
        seen = set()
        uniq = []
        for x in out:
            if x.lower() not in seen:
                seen.add(x.lower())
                uniq.append(x)
        return ", ".join(uniq) if uniq else "NONE"

    if isinstance(value, dict):
        # si viene un dict único
        return clean_habilidades([value])

    # Si viene como string (caso típico del endpoint)
    s = str(value)

    # Si parece JSON embebido, intentamos parsearlo
    # (muchos endpoints envían strings con listas/dicts)
    try:
        maybe = json.loads(s)
        return clean_habilidades(maybe)
    except Exception:
        pass

    # Eliminar tokens "[object Object]" y limpiar separadores
    s = s.replace("[object Object]", "").replace("[object object]", "")
    s = re.sub(r"\s*,\s*", ", ", s)  # comas limpias
    s = re.sub(r"\s+", " ", s).strip(" ,")

    return s if s else "NONE"