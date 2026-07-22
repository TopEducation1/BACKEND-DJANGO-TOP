from types import SimpleNamespace

from django.contrib.sitemaps import Sitemap
from django.utils.text import slugify

from .models import Blog, Certificaciones


# =========================================================
# CONFIGURACIÓN GENERAL
# =========================================================

# Debe coincidir exactamente con el dominio canónico usado
# por el componente Seo.jsx del frontend.
SITE_DOMAIN = "www.top.education"
SITE_PROTOCOL = "https"

# Cantidad máxima de URLs por archivo.
# Django generará las páginas necesarias cuando se utilice
# un índice de sitemaps.
SITEMAP_LIMIT = 1000


class TopEducationSitemap(Sitemap):
    """
    Clase base para generar todas las URLs con el mismo
    dominio y protocolo canónicos.
    """

    protocol = SITE_PROTOCOL
    limit = SITEMAP_LIMIT

    def get_urls(self, page=1, site=None, protocol=None):
        canonical_site = SimpleNamespace(domain=SITE_DOMAIN)

        return super().get_urls(
            page=page,
            site=canonical_site,
            protocol=protocol or self.protocol,
        )


# =========================================================
# PÁGINAS ESTÁTICAS
# =========================================================

class StaticPageSitemap(TopEducationSitemap):
    """
    Páginas públicas que sí deben indexarse.

    No se incluyen rutas privadas o funcionales como:
    /account, /login, /register y /forgot-password.
    """

    changefreq = "weekly"

    PAGES = {
        "/": {
            "priority": 1.0,
            "changefreq": "weekly",
        },
        "/explora": {
            "priority": 0.9,
            "changefreq": "daily",
        },
        "/blog": {
            "priority": 0.8,
            "changefreq": "weekly",
        },
        "/empieza-ahora": {
            "priority": 0.8,
            "changefreq": "weekly",
        },
        "/para-equipos": {
            "priority": 0.7,
            "changefreq": "monthly",
        },
        "/lo-mas-top": {
            "priority": 0.7,
            "changefreq": "weekly",
        },
    }

    def items(self):
        return list(self.PAGES.keys())

    def location(self, item):
        return item

    def priority(self, item):
        return self.PAGES.get(item, {}).get("priority", 0.6)

    def changefreq(self, item):
        return self.PAGES.get(item, {}).get("changefreq", "weekly")


# =========================================================
# CERTIFICACIONES
# =========================================================

class CertificacionSitemap(TopEducationSitemap):
    changefreq = "weekly"
    priority = 0.8

    def items(self):
        """
        Incluye únicamente certificaciones que tengan:

        - slug válido;
        - plataforma relacionada;
        - nombre de plataforma válido.

        Si tu modelo cuenta con un campo de publicación o estado,
        agrega aquí el filtro correspondiente, por ejemplo:

            .filter(estado=True)

        No se agrega automáticamente porque el nombre y tipo exactos
        del campo deben coincidir con el modelo real.
        """

        return (
            Certificaciones.objects
            .select_related("plataforma_certificacion")
            .filter(
                slug__isnull=False,
                plataforma_certificacion__isnull=False,
                plataforma_certificacion__nombre__isnull=False,
            )
            .exclude(slug="")
            .exclude(plataforma_certificacion__nombre="")
            .only(
                "id",
                "slug",
                "fecha_creado_cert",
                "plataforma_certificacion__id",
                "plataforma_certificacion__nombre",
            )
            .order_by("id")
        )

    def location(self, obj):
        """
        Debe coincidir con la ruta y canonical del frontend:

        /certificacion/{plataforma}/{slug}
        """

        platform_name = (
            obj.plataforma_certificacion.nombre
            if obj.plataforma_certificacion
            else ""
        )

        platform_slug = slugify(platform_name)
        certification_slug = str(obj.slug or "").strip().strip("/")

        return (
            f"/certificacion/{platform_slug}/"
            f"{certification_slug}"
        )

    def lastmod(self, obj):
        """
        Por ahora utiliza la fecha de creación porque es el campo
        confirmado en el modelo.

        Cuando exista un campo real de actualización, conviene cambiarlo
        por algo como:

            return obj.fecha_actualizado_cert or obj.fecha_creado_cert
        """

        return obj.fecha_creado_cert


# =========================================================
# BLOGS
# =========================================================

class BlogSitemap(TopEducationSitemap):
    changefreq = "weekly"
    priority = 0.7

    def items(self):
        """
        Incluye únicamente blogs con slug válido.

        Si Blog tiene un campo de publicación o estado, agrega aquí
        el filtro real, por ejemplo:

            .filter(estado_blog=True)
        """

        return (
            Blog.objects
            .filter(slug__isnull=False)
            .exclude(slug="")
            .only(
                "id",
                "slug",
                "fecha_redaccion_blog",
            )
            .order_by("-id")
        )

    def location(self, obj):
        """
        Debe coincidir con la ruta y canonical del frontend:

        /recursos/{slug}
        """

        blog_slug = str(obj.slug or "").strip().strip("/")

        return f"/recursos/{blog_slug}"

    def lastmod(self, obj):
        """
        Por ahora utiliza fecha_redaccion_blog porque es el campo
        confirmado en el modelo.

        Cuando exista una fecha real de actualización, conviene usar:

            return (
                obj.fecha_actualizacion_blog
                or obj.fecha_redaccion_blog
            )
        """

        return obj.fecha_redaccion_blog


# =========================================================
# REGISTRO DE SITEMAPS
# =========================================================

# Este diccionario puede importarse directamente desde urls.py.
#
# Ejemplo:
#
# from django.contrib.sitemaps import views as sitemap_views
# from django.urls import path
# from .sitemaps import sitemaps
#
# urlpatterns = [
#     path(
#         "sitemap.xml",
#         sitemap_views.index,
#         {"sitemaps": sitemaps},
#         name="sitemap-index",
#     ),
#     path(
#         "sitemap-<section>.xml",
#         sitemap_views.sitemap,
#         {"sitemaps": sitemaps},
#         name="sitemap-section",
#     ),
# ]

sitemaps = {
    "pages": StaticPageSitemap,
    "certificaciones": CertificacionSitemap,
    "blogs": BlogSitemap,
}