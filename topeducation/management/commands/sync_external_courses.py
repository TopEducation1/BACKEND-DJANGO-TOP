from __future__ import annotations

import json
import time
import uuid
import traceback
import logging

import requests
from django.core.management.base import BaseCommand
from django.utils import timezone
from django.conf import settings
from datetime import timedelta

from topeducation.models import ExternalSyncState, ExternalSyncLog
from topeducation.services.import_courses import (
    ingest_course_payload,
    ingest_skills_structure_payload,
    ingest_specializations_payload,
    ingest_specialization_detail_payload,
)

logger = logging.getLogger(__name__)

LOCK_TTL_SECONDS = 14 * 60  # ~14 min para cron de 15 min
BASE_EXTERNAL_URL = "https://99f51wnzz7.execute-api.us-east-1.amazonaws.com/colombia-endpoint/course-information"


def _is_sync_paused() -> bool:
    raw = getattr(settings, "COLOMBIA_SYNC_PAUSED", False)
    return str(raw).strip().lower() in ("1", "true", "yes", "on")


def _get_resource_endpoint(resource: str, specialization_id: str | None = None) -> str:
    custom_endpoint = getattr(settings, "COURSES_EXTERNAL_ENDPOINT", None)

    # Compatibilidad: si solo tienes configurado un endpoint custom, lo respetamos para courses
    if custom_endpoint and resource == "courses":
        return custom_endpoint

    if resource == "courses":
        return f"{BASE_EXTERNAL_URL}/courses"
    if resource == "certifications":
        return f"{BASE_EXTERNAL_URL}/certifications"
    if resource == "skills-structure":
        return f"{BASE_EXTERNAL_URL}/skills-structure"
    if resource == "specializations":
        return f"{BASE_EXTERNAL_URL}/specializations"
    if resource == "specialization-detail":
        return f"{BASE_EXTERNAL_URL}/specializations/{specialization_id}"

    raise ValueError(f"Unsupported resource: {resource}")


def _build_external_headers() -> dict:
    headers = {"Accept": "application/json"}
    api_key = getattr(settings, "COURSES_EXTERNAL_API_KEY", None) or getattr(settings, "AWS_COURSES_API_KEY", None)
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


def _extract_total_pages(payload: dict) -> int | None:
    for k in ("totalPages", "total_pages", "totalPage", "pages"):
        v = payload.get(k)
        if isinstance(v, int) and v > 0:
            return v
        if isinstance(v, str) and v.isdigit():
            vv = int(v)
            if vv > 0:
                return vv

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


def _compute_next_page(page: int, payload: dict) -> int:
    items = payload.get("items", [])
    items_len = len(items) if isinstance(items, list) else 0
    total_pages = _extract_total_pages(payload)

    if isinstance(total_pages, int) and total_pages > 0:
        return 1 if page >= total_pages else (page + 1)

    return 1 if items_len == 0 else (page + 1)


def _normalize_provider(provider: str | None) -> str | None:
    if not provider:
        return None
    provider = str(provider).strip()
    return provider.upper() if provider else None


def _validate_specialization_id(specialization_id: str | None) -> bool:
    if not specialization_id or ":" not in specialization_id:
        return False
    provider, raw_id = specialization_id.split(":", 1)
    return bool(provider.strip() and raw_id.strip())


def _build_params(resource: str, page: int, page_size: int, provider: str | None) -> dict:
    params = {}

    if resource in ("courses", "certifications", "specializations"):
        params["page"] = page
        params["pageSize"] = page_size

    if provider and resource in ("courses", "certifications", "specializations"):
        # el endpoint documentado soporta provider o providerId
        params["provider"] = provider
        params["providerId"] = provider

    return params


def _ingest_by_resource(resource: str, payload: dict, provider: str | None = None, specialization_id: str | None = None):
    if resource in ("courses", "certifications"):
        return ingest_course_payload(payload, resource=resource, provider_filter=provider)

    if resource == "skills-structure":
        return ingest_skills_structure_payload(payload, provider_filter=provider)

    if resource == "specializations":
        return ingest_specializations_payload(payload, provider_filter=provider)

    if resource == "specialization-detail":
        return ingest_specialization_detail_payload(
            payload,
            specialization_id=specialization_id,
            provider_filter=provider,
        )

    raise ValueError(f"Unsupported ingestion resource: {resource}")


class Command(BaseCommand):
    help = "Sincroniza recursos desde endpoint externo de Top Education con cursor, logs y soporte multi-resource."

    def add_arguments(self, parser):
        parser.add_argument("--resource", type=str, default="courses")
        parser.add_argument("--provider", type=str, default="")
        parser.add_argument("--page-size", type=int, default=50)
        parser.add_argument("--timeout", type=int, default=30)
        parser.add_argument("--max-pages", type=int, default=1)
        parser.add_argument("--state-key", type=str, default="")
        parser.add_argument("--specialization-id", type=str, default="")

    def handle(self, *args, **opts):
        t0 = time.time()
        run_id = uuid.uuid4().hex[:16]

        resource = str(opts["resource"]).strip().lower()
        provider = _normalize_provider(opts.get("provider"))
        specialization_id = str(opts.get("specialization_id") or "").strip()

        allowed_resources = {
            "courses",
            "certifications",
            "skills-structure",
            "specializations",
            "specialization-detail",
        }

        if resource not in allowed_resources:
            self.stderr.write(self.style.ERROR(f"invalid_resource: {resource}"))
            return

        if _is_sync_paused():
            self.stdout.write(self.style.WARNING("COLOMBIA_SYNC_PAUSED activo. Sync abortada."))
            return

        if resource == "specialization-detail" and not _validate_specialization_id(specialization_id):
            self.stderr.write(self.style.ERROR(
                "invalid_specialization_id: debe tener formato <provider>:<rawId>"
            ))
            return

        state_key = str(opts["state_key"]).strip() or f"{resource}_sync"
        endpoint = _get_resource_endpoint(resource, specialization_id=specialization_id)
        headers = _build_external_headers()

        page_size = max(1, min(int(opts["page_size"]), 100))
        timeout = int(opts["timeout"])
        max_pages = max(1, min(int(opts["max_pages"]), 10))

        lower_headers = {k.lower(): v for k, v in headers.items()}
        if "authorization" not in lower_headers and "x-api-key" not in lower_headers:
            self.stderr.write(self.style.ERROR("missing_api_key: COURSES_EXTERNAL_API_KEY / AWS_COURSES_API_KEY"))
            return

        uses_cursor = resource in ("courses", "certifications", "specializations")

        state, _ = ExternalSyncState.objects.get_or_create(
            key=state_key,
            defaults={"cursor_value": "1", "running": False},
        )

        now = timezone.now()
        stale_before = now - timedelta(seconds=LOCK_TTL_SECONDS)

        if state.running and state.locked_at and state.locked_at > stale_before:
            self.stdout.write(self.style.WARNING("Lock activo, ya hay una ejecución en curso"))
            return

        locked_at_value = now
        ExternalSyncState.objects.filter(key=state_key).update(
            running=True,
            locked_at=locked_at_value,
            updated_at=now,
        )

        try:
            state = ExternalSyncState.objects.get(key=state_key)

            if uses_cursor:
                try:
                    page = max(1, int(state.cursor_value or "1"))
                except Exception:
                    page = 1
            else:
                page = 1

            self.stdout.write(
                f"[{timezone.now()}] Sync start resource={resource} page={page} "
                f"pageSize={page_size} provider={provider or '-'} endpoint={endpoint}"
            )

            processed_pages = 0

            for _ in range(max_pages):
                params = _build_params(resource, page, page_size, provider)

                try:
                    resp = requests.get(endpoint, headers=headers, params=params, timeout=timeout)
                    resp.raise_for_status()
                    payload = resp.json()
                    if not isinstance(payload, dict):
                        payload = {"data": payload}
                except Exception as e:
                    took_ms = int((time.time() - t0) * 1000)
                    ExternalSyncLog.objects.create(
                        key=state_key,
                        run_id=run_id,
                        page=page if uses_cursor else None,
                        page_size=page_size if uses_cursor else None,
                        ok=False,
                        took_ms=took_ms,
                        error="fetch_failed",
                        detail=str(e),
                        trace=traceback.format_exc()[:8000],
                    )
                    ExternalSyncState.objects.filter(key=state_key).update(
                        last_error_at=timezone.now(),
                        last_error=f"fetch_failed: {e}",
                    )
                    self.stderr.write(self.style.ERROR(f"fetch_failed: {e}"))
                    return

                items = payload.get("items", [])
                items_len = len(items) if isinstance(items, list) else 0
                total_pages = _extract_total_pages(payload)

                try:
                    summary = _ingest_by_resource(
                        resource,
                        payload,
                        provider=provider,
                        specialization_id=specialization_id or None,
                    )
                except Exception as e:
                    took_ms = int((time.time() - t0) * 1000)
                    ExternalSyncLog.objects.create(
                        key=state_key,
                        run_id=run_id,
                        page=page if uses_cursor else None,
                        page_size=page_size if uses_cursor else None,
                        ok=False,
                        items_len=items_len,
                        received=items_len,
                        took_ms=took_ms,
                        error="ingestion_failed",
                        detail=str(e),
                        trace=traceback.format_exc()[:8000],
                    )
                    ExternalSyncState.objects.filter(key=state_key).update(
                        last_error_at=timezone.now(),
                        last_error=f"ingestion_failed: {e}",
                    )
                    self.stderr.write(self.style.ERROR(f"ingestion_failed: {e}"))
                    return

                if uses_cursor:
                    next_page = _compute_next_page(page, payload)
                    ExternalSyncState.objects.filter(key=state_key).update(
                        cursor_value=str(next_page),
                        last_ok_at=timezone.now(),
                        last_error="",
                        updated_at=timezone.now(),
                    )
                else:
                    next_page = None
                    ExternalSyncState.objects.filter(key=state_key).update(
                        last_ok_at=timezone.now(),
                        last_error="",
                        updated_at=timezone.now(),
                    )

                ExternalSyncLog.objects.create(
                    key=state_key,
                    run_id=run_id,
                    page=page if uses_cursor else None,
                    page_size=page_size if uses_cursor else None,
                    ok=True,
                    items_len=items_len,
                    received=items_len,
                    took_ms=int((time.time() - t0) * 1000),
                    detail=(
                        f"resource={resource} provider={provider or '-'} "
                        f"items_len={items_len} total_pages={total_pages} "
                        f"next_page={next_page} summary={json.dumps(summary, default=str)[:1500]}"
                    ),
                )

                processed_pages += 1

                if uses_cursor:
                    self.stdout.write(self.style.SUCCESS(
                        f"OK resource={resource} page={page} items={items_len} total_pages={total_pages} next={next_page}"
                    ))
                    page = next_page
                    if next_page == 1:
                        break
                else:
                    self.stdout.write(self.style.SUCCESS(
                        f"OK resource={resource} items={items_len}"
                    ))
                    break

            self.stdout.write(self.style.SUCCESS(
                f"Done. resource={resource} processed_pages={processed_pages} took_ms={int((time.time()-t0)*1000)}"
            ))

        finally:
            try:
                ExternalSyncState.objects.filter(
                    key=state_key,
                    running=True,
                ).update(
                    running=False,
                    locked_at=None,
                    updated_at=timezone.now(),
                )
            except Exception:
                pass