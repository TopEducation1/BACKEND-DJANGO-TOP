from django.contrib.sitemaps import Sitemap
from .models import Certificaciones
from .models import Blog


class CertificacionSitemap(Sitemap):
    def items(self):
        return Certificaciones.objects.select_related(
            "plataforma_certificacion"
        ).order_by("id")  # también resuelve el warning de paginación

    def location(self, obj):
         # Diccionario como switch
        plataforma_slug = {
            1: "edx",
            2: "coursera",
            3: "masterclass"
        }

        plataform = plataforma_slug.get(obj.plataforma_certificacion_id, "otro")
        return f"/certificaciones/{plataform}/{obj.slug}/"

    def lastmod(self, obj):
        return obj.fecha_creado
    
    def get_urls(self, page=1, site=None, protocol="https"):
        # Crear objeto falso de "site" con el dominio deseado
        class FakeSite:
            domain = "top.education"
        return super().get_urls(page=page, site=FakeSite(), protocol=protocol)


class BlogSitemap(Sitemap):
    changefreq = "weekly"
    priority = 0.7

    def items(self):
        return Blog.objects.all()
    
    def lastmod(self, obj):
        return obj.fecha_redaccion_blog
    
    def location(self, obj):
        return f"/recursos/{obj.slug}"
    
    def get_urls(self, page=1, site=None, protocol="https"):
        # Crear objeto falso de "site" con el dominio deseado
        class FakeSite:
            domain = "top.education"
        return super().get_urls(page=page, site=FakeSite(), protocol=protocol)
