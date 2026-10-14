from __future__ import annotations

from django.core.management.base import BaseCommand

from topeducation.models import Certificaciones


BATCH_SIZE = 1000


def stable_course_key(value):
    if not isinstance(value, str):
        return None

    value = value.strip()

    if not value:
        return None

    if not value.startswith("course-v1:"):
        return None

    stable_key, separator, run = (
        value.rpartition("+")
    )

    if (
        not separator
        or not stable_key
        or not run
        or "+" not in stable_key
    ):
        return None

    return stable_key


class Command(BaseCommand):
    help = (
        "Backfill de Certificaciones.stable_course_key "
        "a partir de id_interno."
    )

    def handle(self, *args, **options):
        queryset = (
            Certificaciones.objects
            .filter(
                id_interno__isnull=False,
            )
            .exclude(
                id_interno=""
            )
            .only(
                "id",
                "id_interno",
                "stable_course_key",
            )
            .order_by("id")
        )

        pending = []
        scanned = 0
        updated = 0

        for certification in queryset.iterator(
            chunk_size=BATCH_SIZE
        ):
            scanned += 1

            new_value = stable_course_key(
                certification.id_interno
            )

            if (
                certification.stable_course_key
                == new_value
            ):
                continue

            certification.stable_course_key = (
                new_value
            )
            pending.append(certification)

            if len(pending) >= BATCH_SIZE:
                Certificaciones.objects.bulk_update(
                    pending,
                    ["stable_course_key"],
                    batch_size=BATCH_SIZE,
                )

                updated += len(pending)
                pending = []

                self.stdout.write(
                    f"Procesados={scanned} "
                    f"actualizados={updated}"
                )

        if pending:
            Certificaciones.objects.bulk_update(
                pending,
                ["stable_course_key"],
                batch_size=BATCH_SIZE,
            )
            updated += len(pending)

        self.stdout.write(
            self.style.SUCCESS(
                "Backfill completado. "
                f"procesados={scanned} "
                f"actualizados={updated}"
            )
        )
