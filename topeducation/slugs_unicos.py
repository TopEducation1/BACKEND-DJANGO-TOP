from django.utils.text  import slugify

from models import Certificaciones

certificaciones = Certificaciones.objects.all()


for cert in certificaciones:
    if not cert.slug or cert.slug == 'default-slug':
        cert.slug = slice(cert.nombre)
        cert.save()