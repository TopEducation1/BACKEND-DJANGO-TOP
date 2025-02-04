from django.core.management.base import BaseCommand
from topeducation.models import Blog

class Command(BaseCommand):
    help = 'Regenera slugs para todos los blogs'
    def handle(self, *args, **kwargs):
        for blog in Blog.objects.all():
            blog.save()  # Esto activará el save() corregido
        self.stdout.write(self.style.SUCCESS('Slugs regenerados correctamente'))