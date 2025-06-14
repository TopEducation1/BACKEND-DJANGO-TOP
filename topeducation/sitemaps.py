# certificaciones/sitemaps.py
from django.contrib.sitemaps import Sitemap
from .models import Certificaciones
from .models import Blog

class CertificacionSitemap(Sitemap):
    changefreq = "weekly"
    priority = 0.8

    def items(self):
        return Certificaciones.objects.all()

    def lastmod(self, obj):
        return obj.fecha_creado

    def location(self, obj):
        return f"/certificacion/{obj.plataforma_certificacion.nombre.lower()}/{obj.slug}"

class BlogSitemap(Sitemap):
    changefreq = "weekly"
    priority = 0.7

    def items(self):
        return Blog.objects.all()
    
    def lastmod(self, obj):
        return obj.fecha_redaccion_blog
    
    def location(self, obj):
        return f"/recursos/{obj.slug}"
