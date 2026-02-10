# topeducation/inspectors/courses_inspector.py
from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, List, Tuple, Optional

import time
import requests
from django.conf import settings

NAME_KEYS = ("nombre", "name", "title")


@dataclass
class MappedCourse:
    external_id: str
    nombre: str
    imagen: str
    skills: List[str]
    raw: Dict[str, Any]


def _has_name_like(obj: Any) -> bool:
    return isinstance(obj, dict) and any(isinstance(obj.get(k), str) for k in NAME_KEYS)


def _has_skills(obj: Any) -> bool:
    if not isinstance(obj, dict):
        return False
    sk = obj.get("skills")
    return isinstance(sk, (list, dict))


def find_courses_array(node: Any) -> List[Dict[str, Any]]:
    """Busca recursivamente un arreglo que parezca lista de cursos."""
    candidates: List[Tuple[int, List[Dict[str, Any]]]] = []

    def walk(n: Any):
        if isinstance(n, list):
            if n and isinstance(n[0], dict) and (_has_name_like(n[0]) or _has_skills(n[0])):
                score = len(n) + (1000 if _has_skills(n[0]) else 0)
                candidates.append((score, n))  # type: ignore[arg-type]
            for v in n:
                walk(v)
        elif isinstance(n, dict):
            for v in n.values():
                walk(v)

    walk(node)
    candidates.sort(key=lambda x: x[0], reverse=True)
    return candidates[0][1] if candidates else []


def extract_skill_names(skills: Any) -> List[str]:
    if not skills:
        return []

    names: List[str] = []

    def walk(n: Any):
        if not n:
            return
        if isinstance(n, list):
            for v in n:
                walk(v)
        elif isinstance(n, dict):
            if isinstance(n.get("name"), str):
                names.append(n["name"])
            for v in n.values():
                walk(v)

    if isinstance(skills, list):
        for s in skills:
            if isinstance(s, dict) and isinstance(s.get("name"), str):
                names.append(s["name"])
            elif isinstance(s, str):
                names.append(s)
    elif isinstance(skills, dict):
        walk(skills)

    out: List[str] = []
    seen = set()
    for n in names:
        n = str(n).strip()
        if n and n not in seen:
            seen.add(n)
            out.append(n)
    return out


def map_course(item: Dict[str, Any]) -> MappedCourse:
    external_id = str(item.get("id") or item.get("courseId") or item.get("slug") or "").strip()
    nombre = str(item.get("nombre") or item.get("name") or item.get("title") or "").strip()
    imagen = str(
        item.get("imagen_final")
        or item.get("image_final")
        or item.get("image")
        or item.get("imageFinal")
        or item.get("thumbnail")
        or ""
    ).strip()
    skills = extract_skill_names(item.get("skills"))
    return MappedCourse(external_id=external_id, nombre=nombre, imagen=imagen, skills=skills, raw=item)


def _build_headers() -> Dict[str, str]:
    """
    ✅ Para API Gateway lo normal es x-api-key.
    Settings:
      - COURSES_EXTERNAL_API_KEY
      - COURSES_EXTERNAL_AUTH_HEADER (default: "x-api-key")
      - COURSES_EXTERNAL_AUTH_PREFIX (default: "")  # solo si Authorization
    """
    headers: Dict[str, str] = {"Accept": "application/json"}

    api_key = getattr(settings, "COURSES_EXTERNAL_API_KEY", None)
    if not api_key:
        return headers

    auth_header = getattr(settings, "COURSES_EXTERNAL_AUTH_HEADER", "x-api-key")
    auth_prefix = getattr(settings, "COURSES_EXTERNAL_AUTH_PREFIX", "")

    if auth_header.lower() == "authorization":
        prefix = auth_prefix or "Bearer "
        headers["Authorization"] = f"{prefix}{api_key}".strip()
    else:
        headers[auth_header] = f"{auth_prefix}{api_key}".strip()

    return headers


def _extract_items_from_payload(data: Any) -> List[Dict[str, Any]]:
    """
    ✅ Soporta:
    - payload["items"] (tu endpoint nuevo)
    - data->coursParsed (tu inspector anterior)
    - fallback recursivo
    """
    if isinstance(data, dict) and isinstance(data.get("items"), list):
        return data["items"]

    if (
        isinstance(data, dict)
        and isinstance(data.get("data"), dict)
        and isinstance(data["data"].get("coursParsed"), list)
    ):
        return data["data"]["coursParsed"]

    if isinstance(data, dict) and isinstance(data.get("coursParsed"), list):
        return data["coursParsed"]

    arr = find_courses_array(data)
    return arr if isinstance(arr, list) else []


def _extract_total_pages(payload: Any) -> Optional[int]:
    if not isinstance(payload, dict):
        return None

    for k in ("totalPages", "total_pages", "totalPage", "pages", "total_pages_count"):
        v = payload.get(k)
        if isinstance(v, int) and v > 0:
            return v
        if isinstance(v, str) and v.isdigit():
            vv = int(v)
            if vv > 0:
                return vv

    # a veces viene dentro de meta/pagination
    meta = payload.get("meta") if isinstance(payload.get("meta"), dict) else None
    if meta:
        for k in ("totalPages", "total_pages", "pages"):
            v = meta.get(k)
            if isinstance(v, int) and v > 0:
                return v
            if isinstance(v, str) and v.isdigit():
                vv = int(v)
                if vv > 0:
                    return vv

    return None


def _request_json(
    session: requests.Session,
    endpoint: str,
    headers: Dict[str, str],
    params: Dict[str, Any],
    timeout: int,
) -> Any:
    r = session.get(endpoint, headers=headers, params=params, timeout=timeout)
    if r.status_code >= 400:
        body = (r.text or "")[:800]
        raise requests.HTTPError(
            f"External HTTP {r.status_code} {r.reason}. Body: {body}",
            response=r,
        )
    return r.json()


def fetch_payload_page(
    endpoint: str,
    page: int,
    page_size: int,
    timeout: int = 60,
    extra_params: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    """
    Trae el payload completo del endpoint.
    ✅ Usa page + pageSize (camelCase).
    """
    session = requests.Session()
    headers = _build_headers()

    params: Dict[str, Any] = {"page": int(page), "pageSize": int(page_size)}
    if extra_params:
        params.update(extra_params)

    retries = 2
    for attempt in range(1, retries + 2):
        try:
            data = _request_json(session, endpoint, headers, params, timeout)
            if not isinstance(data, dict):
                # normalizamos a dict para que el caller no explote
                return {"data": data}
            return data
        except requests.HTTPError as e:
            status = getattr(e.response, "status_code", None)
            if status in (429, 500, 502, 503, 504) and attempt <= retries:
                time.sleep(0.8 * attempt)
                continue
            raise


def fetch_and_parse_page(
    endpoint: str,
    page: int,
    page_size: int,
    timeout: int = 60,
    extra_params: Optional[Dict[str, Any]] = None,
) -> List[MappedCourse]:
    """
    Trae y parsea UNA página del endpoint a lista de MappedCourse.
    """
    payload = fetch_payload_page(endpoint, page, page_size, timeout, extra_params=extra_params)
    items = _extract_items_from_payload(payload)

    mapped: List[MappedCourse] = []
    for it in items:
        if isinstance(it, dict):
            mapped.append(map_course(it))
    return mapped


def get_pagination_meta(payload: Dict[str, Any]) -> Dict[str, Any]:
    """
    Devuelve meta útil para decidir next_page.
    """
    items = _extract_items_from_payload(payload)
    total_pages = _extract_total_pages(payload)
    return {
        "items_len": len(items) if isinstance(items, list) else 0,
        "total_pages": total_pages,
    }
