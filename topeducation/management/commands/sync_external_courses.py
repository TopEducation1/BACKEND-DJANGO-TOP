from __future__ import annotations

import time
import logging
from django.core.management.base import BaseCommand
from django.utils import timezone
from django.conf import settings

from topeducation.inspectors.courses_inspector import fetch_and_parse_page
from topeducation.models import ExternalSyncState

logger = logging.getLogger(__name__)


class Command(BaseCommand):
    help = "Sincroniza cursos/certificaciones desde un endpoint externo (paginado: page + page_size)."

    def add_arguments(self, parser):
        parser.add_argument("--endpoint", type=str, required=False, help="URL del endpoint externo")
        parser.add_argument("--page-size", type=int, default=50, help="Cantidad por página")
        parser.add_argument("--retries", type=int, default=3)
        parser.add_argument("--timeout", type=int, default=60)
        parser.add_argument("--state-key", type=str, default="courses_sync", help="Clave del cursor en BD")

    def handle(self, *args, **opts):
        endpoint = opts.get("endpoint") or getattr(settings, "COURSES_EXTERNAL_ENDPOINT", None)
        page_size = int(opts["page_size"])
        retries = int(opts["retries"])
        timeout = int(opts["timeout"])
        state_key = str(opts["state_key"])

        if not endpoint:
            self.stderr.write(self.style.ERROR("Falta endpoint. Usa --endpoint o settings.COURSES_EXTERNAL_ENDPOINT"))
            return

        # 👇 ahora usamos cursor_value
        state, _ = ExternalSyncState.objects.get_or_create(
            key=state_key,
            defaults={"cursor_value": "1"},
        )

        try:
            page = max(1, int(state.cursor_value or "1"))
        except (TypeError, ValueError):
            page = 1

        self.stdout.write(
            f"[{timezone.now()}] Sync start: page={page} page_size={page_size} endpoint={endpoint}"
        )

        last_err = None
        for attempt in range(1, retries + 1):
            try:
                t0 = time.time()

                courses = fetch_and_parse_page(
                    endpoint,
                    page=page,
                    page_size=page_size,
                    timeout=timeout,
                )

                elapsed = round(time.time() - t0, 2)
                self.stdout.write(
                    self.style.SUCCESS(f"OK: recibidos={len(courses)} en {elapsed}s (page={page})")
                )

                # ======================================================
                # PERSISTENCIA (AJUSTA A TU MODELO REAL)
                # ======================================================
                # EJEMPLO:
                # from apps.certifications.models import Certification
                # for c in courses:
                #     obj, created = Certification.objects.update_or_create(
                #         external_id=c.external_id,
                #         defaults={
                #             "nombre": c.nombre,
                #             "imagen_final": c.imagen,
                #             # "raw_external": c.raw,  # si tienes JSONField
                #         }
                #     )
                #
                #     # Skills: si tienes M2M, aquí harías upsert de skills + set()

                # ======================================================
                # Avanzar cursor:
                # - Si viene menos de page_size => probablemente fin del catálogo => reinicia a 1
                # - Si viene exactamente page_size => sigue a page+1
                # ======================================================
                next_page = 1 if len(courses) < page_size else (page + 1)
                state.cursor_value = str(next_page)
                state.save(update_fields=["cursor_value", "updated_at"])

                self.stdout.write(self.style.SUCCESS(f"Cursor actualizado: {page} -> {next_page}"))
                return

            except Exception as e:
                last_err = e
                logger.exception("Error syncing courses attempt=%s page=%s", attempt, page)
                self.stderr.write(self.style.WARNING(f"Intento {attempt}/{retries} falló: {e}"))
                time.sleep(min(5 * attempt, 20))

        self.stderr.write(self.style.ERROR(f"Sync failed after {retries} attempts: {last_err}"))
