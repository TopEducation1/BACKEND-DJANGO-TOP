from django.contrib.sitemaps import Sitemap
from .models import Certificaciones, Blog


# =========================
# CERTIFICACIONES
# =========================
class CertificacionSitemap(Sitemap):
    changefreq = "weekly"
    priority = 0.8
    limit = 1000  # clave para evitar cargas gigantes

    def items(self):
        # ⚠️ SOLO campos necesarios → evita consultas pesadas
        return Certificaciones.objects.only(
            "id",
            "slug",
            "plataforma_certificacion_id",
            "fecha_creado_cert"
        ).order_by("id")

    def location(self, obj):
        plataforma_slug = {
            1: "edx",
            2: "coursera",
            3: "masterclass"
        }

        plataforma = plataforma_slug.get(
            obj.plataforma_certificacion_id,
            "otro"
        )

        return f"/certificaciones/{plataforma}/{obj.slug}/"

    def lastmod(self, obj):
        return obj.fecha_creado_cert

    def get_urls(self, page=1, site=None, protocol="https"):
        class FakeSite:
            domain = "top.education"

        return super().get_urls(page=page, site=FakeSite(), protocol=protocol)


# =========================
# BLOG
# =========================
class BlogSitemap(Sitemap):
    changefreq = "weekly"
    priority = 0.7
    limit = 1000  # también aquí por seguridad

    def items(self):
        return Blog.objects.only(
            "id",
            "slug",
            "fecha_redaccion_blog"
        ).order_by("-id")

    def lastmod(self, obj):
        return obj.fecha_redaccion_blog

    def location(self, obj):
        return f"/recursos/{obj.slug}"

    def get_urls(self, page=1, site=None, protocol="https"):
        class FakeSite:
            domain = "top.education"

        return super().get_urls(page=page, site=FakeSite(), protocol=protocol)