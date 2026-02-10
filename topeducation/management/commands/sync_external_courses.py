# topeducation/management/commands/sync_external_courses.py
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
from topeducation.services.import_courses import ingest_course_payload

logger = logging.getLogger(__name__)

LOCK_TTL_SECONDS = 14 * 60  # ~14 min para cron de 15 min


def _get_courses_endpoint() -> str:
    return getattr(settings, "COURSES_EXTERNAL_ENDPOINT", None) or \
           "https://erucsg6yrj.execute-api.us-east-1.amazonaws.com/colombia-endpoint/course-information/courses"


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


def _compute_next_page(page: int, page_size: int, payload: dict) -> int:
    items = payload.get("items", [])
    items_len = len(items) if isinstance(items, list) else 0
    total_pages = _extract_total_pages(payload)

    if isinstance(total_pages, int) and total_pages > 0:
        return 1 if page >= total_pages else (page + 1)

    return 1 if items_len == 0 else (page + 1)


class Command(BaseCommand):
    help = "Sincroniza cursos/certificaciones desde endpoint externo (paginado: page + pageSize) con cursor y logs."

    def add_arguments(self, parser):
        parser.add_argument("--page-size", type=int, default=50)
        parser.add_argument("--timeout", type=int, default=30)
        parser.add_argument("--max-pages", type=int, default=1)
        parser.add_argument("--state-key", type=str, default="courses_sync")

    def handle(self, *args, **opts):
        t0 = time.time()
        run_id = uuid.uuid4().hex[:16]
        state_key = str(opts["state_key"])

        endpoint = _get_courses_endpoint()
        headers = _build_external_headers()

        page_size = int(opts["page_size"])
        timeout = int(opts["timeout"])
        max_pages = max(1, min(int(opts["max_pages"]), 10))

        if "Authorization" not in headers and "x-api-key" not in {k.lower(): v for k, v in headers.items()}:
            self.stderr.write(self.style.ERROR("missing_api_key: COURSES_EXTERNAL_API_KEY / AWS_COURSES_API_KEY"))
            return

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
            try:
                page = max(1, int(state.cursor_value or "1"))
            except Exception:
                page = 1

            self.stdout.write(f"[{timezone.now()}] Sync start page={page} pageSize={page_size} endpoint={endpoint}")

            processed_pages = 0

            for _ in range(max_pages):
                params = {"page": page, "pageSize": page_size}

                try:
                    resp = requests.get(endpoint, headers=headers, params=params, timeout=timeout)
                    resp.raise_for_status()
                    payload = resp.json()
                    if not isinstance(payload, dict):
                        payload = {"data": payload}
                except Exception as e:
                    took_ms = int((time.time() - t0) * 1000)
                    ExternalSyncLog.objects.create(
                        key=state_key, run_id=run_id, page=page, page_size=page_size,
                        ok=False, took_ms=took_ms,
                        error="fetch_failed", detail=str(e), trace=traceback.format_exc()[:8000],
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
                    summary = ingest_course_payload(payload)
                except Exception as e:
                    took_ms = int((time.time() - t0) * 1000)
                    ExternalSyncLog.objects.create(
                        key=state_key, run_id=run_id, page=page, page_size=page_size,
                        ok=False, items_len=items_len, received=items_len, took_ms=took_ms,
                        error="ingestion_failed", detail=str(e), trace=traceback.format_exc()[:8000],
                    )
                    ExternalSyncState.objects.filter(key=state_key).update(
                        last_error_at=timezone.now(),
                        last_error=f"ingestion_failed: {e}",
                    )
                    self.stderr.write(self.style.ERROR(f"ingestion_failed: {e}"))
                    return

                next_page = _compute_next_page(page, page_size, payload)

                ExternalSyncState.objects.filter(key=state_key).update(
                    cursor_value=str(next_page),
                    last_ok_at=timezone.now(),
                    last_error="",
                    updated_at=timezone.now(),
                )

                ExternalSyncLog.objects.create(
                    key=state_key, run_id=run_id, page=page, page_size=page_size,
                    ok=True, items_len=items_len, received=items_len,
                    took_ms=int((time.time() - t0) * 1000),
                    detail=f"items_len={items_len} total_pages={total_pages} next_page={next_page} summary={json.dumps(summary)[:1500]}",
                )

                processed_pages += 1
                self.stdout.write(self.style.SUCCESS(
                    f"OK page={page} items={items_len} total_pages={total_pages} next={next_page}"
                ))

                page = next_page
                if next_page == 1:
                    break

            self.stdout.write(self.style.SUCCESS(f"Done. processed_pages={processed_pages} took_ms={int((time.time()-t0)*1000)}"))

        finally:
            try:
                ExternalSyncState.objects.filter(
                    key=state_key,
                    running=True,
                    locked_at=locked_at_value,
                ).update(
                    running=False,
                    locked_at=None,
                    updated_at=timezone.now(),
                )
            except Exception:
                pass
