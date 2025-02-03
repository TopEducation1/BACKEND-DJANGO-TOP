from django.core.management.base import BaseCommand
from topeducation.models import Certificaciones

class Command(BaseCommand):
    help = 'Regenera slugs para todas las certificaciones'

    def handle(self, *args, **kwargs):
        for cert in Certificaciones.objects.all():
            cert.save()  # Esto activará el save() corregido
        self.stdout.write(self.style.SUCCESS('Slugs regenerados correctamente'))