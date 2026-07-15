# certifications/serializers.py
from django.conf import settings
from datetime import datetime
from rest_framework import serializers
from .models import Marca, MarcaPermisos
from .models import *
from django.db.models import F
from django.utils.html import escape
import re

# CONVIERTE LOS MODELOS EN JSON PARA CONSUMIRLOS DESDE EL FRONT

class BlogSerializer(serializers.ModelSerializer):
    class Meta:
        model = Blog 
        fields = '__all__'

    def to_representation(self, instance):
        representation = super().to_representation(instance)

        request = self.context.get('request', None)

        # Convertir miniatura a URL absoluta
        if instance.miniatura_blog and request:
            representation['miniatura_blog'] = request.build_absolute_uri(instance.miniatura_blog.url)

        # Convertir las rutas de imagen dentro del contenido
        if instance.contenido and request:
            representation['contenido'] = self._absolutize_images(instance.contenido, request)

        # Serializar categoría
        categoria_instance = instance.categoria_blog
        representation['categoria_blog'] = CategoriesSerializer(categoria_instance).data if categoria_instance else None

        try:
            autor_instance = instance.autor_blog
            categoria = instance.categoria_blog

            representation['categoria_blog_id'] = categoria.nombre_categoria_blog if categoria else None
            representation['autor_blog_id'] = autor_instance.nombre_autor if autor_instance else None

            representation['autor_img'] = autor_instance.auto_img if autor_instance and autor_instance.auto_img else None

            representation['autor_blog'] = AuthorsSerializer(autor_instance).data if autor_instance else None

        except Exception as e:
            print(f"Error serializing blog: {e}")
            representation['categoria_blog_id'] = None
            representation['autor_blog_id'] = None
            representation['autor_img'] = None

        return representation

    def _absolutize_images(self, html, request):
        if not request:
            return html
        return re.sub(
            r'src="(/media/[^"]+)"',
            lambda m: f'src="{request.build_absolute_uri(m.group(1))}"',
            html
        )

            
class AuthorsSerializer(serializers.ModelSerializer):
    class Meta:
        model = Autor
        fields = '__all__'

class CategoriesSerializer(serializers.ModelSerializer):
    class Meta:
        model = CategoriaBlog
        fields = '__all__'

class SkillsSerializer(serializers.ModelSerializer):
    
    class Meta:
        model = Habilidades
        
        fields = '__all__'
        
class UniverisitiesSerializer(serializers.ModelSerializer):
    region_nombre = serializers.SerializerMethodField()
    total_certificaciones = serializers.IntegerField(read_only=True)  # ← nuevo campo

    class Meta:
        model = Universidades
        fields = ['id', 'nombre', 'region_universidad_id','descripcion_institucion', 'univ_img','univ_ico','univ_fla','univ_est','univ_top', 'region_nombre', 'total_certificaciones']

    def get_region_nombre(self, obj):
        return obj.region_universidad.nombre if obj.region_universidad else "No"


class TopicsSerializer (serializers.ModelSerializer):
    
    class Meta:
        model = Temas
        
        fields = ['id', 'nombre', 'translate', 'tem_type','tem_col','tem_img','tem_est']

class PlataformaSerializer (serializers.ModelSerializer):
    
    class Meta:
        model = Plataformas
        
        fields = ['id', 'nombre','plat_img','plat_ico']

class EmpresaSerializer (serializers.ModelSerializer):
    total_certificaciones = serializers.IntegerField(read_only=True)
    #total_certificaciones = serializers.IntegerField()

    class Meta:
        model = Empresas
        
        fields = ['id', 'nombre','empr_img','empr_ico','empr_est','empr_top','total_certificaciones','descripcion_institucion']


class SkillSerializer(serializers.ModelSerializer):
    class Meta:
        model = Skills
        fields = "__all__"
class InstructorSerializer(serializers.ModelSerializer):
    class Meta:
        model = Instructores
        fields = "__all__"

## MINI SERIALIZERS

class SkillMiniSerializer(serializers.ModelSerializer):
    class Meta:
        model = Skills
        fields = [
            "id",
            "nombre",
            "translate",
            "slug",
            "skill_col",
            "skill_img",
            "skill_ico",
            "skill_type",
            "estado",
        ]


class TopicMiniSerializer(serializers.ModelSerializer):
    class Meta:
        model = Temas
        fields = [
            "id",
            "nombre",
            "translate",
            "tem_type",
            "tem_col",
            "tem_img",
            "tem_est",
        ]


class PlataformaMiniSerializer(serializers.ModelSerializer):
    class Meta:
        model = Plataformas
        fields = [
            "id",
            "nombre",
            "plat_img",
            "plat_ico",
        ]


class UniversidadMiniSerializer(serializers.ModelSerializer):
    class Meta:
        model = Universidades
        fields = [
            "id",
            "nombre",
            "descripcion_institucion",
            "univ_img",
            "univ_ico",
            "univ_fla",
            "univ_est",
            "univ_top",
        ]

class EmpresaMiniSerializer(serializers.ModelSerializer):
    class Meta:
        model = Empresas
        fields = [
            "id",
            "nombre",
            "empr_img",
            "empr_ico",
            "empr_est",
            "empr_top",
            "descripcion_institucion",
        ]

class PlatformCardMiniSerializer(serializers.ModelSerializer):
    class Meta:
        model = Plataformas
        fields = ["id", "nombre", "plat_ico"]


class UniversityCardMiniSerializer(serializers.ModelSerializer):
    class Meta:
        model = Universidades
        fields = ["id", "nombre", "univ_ico", "univ_img"]


class CompanyCardMiniSerializer(serializers.ModelSerializer):
    class Meta:
        model = Empresas
        fields = ["id", "nombre", "empr_ico", "empr_img"]

class SkillFilterMiniSerializer(serializers.ModelSerializer):
    class Meta:
        model = Skills
        fields = [
            "id",
            "nombre",
            "translate",
            "slug",
            "skill_ico",
            "skill_img",
            "skill_col",
            "skill_type",
            "estado",
            "parent_id",
        ]


class UniversityFilterMiniSerializer(serializers.ModelSerializer):
    class Meta:
        model = Universidades
        fields = [
            "id",
            "nombre",
            "univ_img",
            "region_universidad_id",
        ]


class CompanyFilterMiniSerializer(serializers.ModelSerializer):
    class Meta:
        model = Empresas
        fields = [
            "id",
            "nombre",
            "empr_ico",
            "empr_img",
        ]


class PlatformFilterMiniSerializer(serializers.ModelSerializer):
    class Meta:
        model = Plataformas
        fields = [
            "id",
            "nombre",
            "plat_ico",
        ]

class CertificationSpecializationCourseSerializer(serializers.ModelSerializer):
    plataforma_certificacion = PlataformaMiniSerializer(read_only=True)
    universidad_certificacion = UniversidadMiniSerializer(read_only=True)
    empresa_certificacion = EmpresaMiniSerializer(read_only=True)

    class Meta:
        model = Certificaciones
        fields = [
            "id",
            "slug",
            "nombre",
            "imagen_final",
            "metadescripcion_certificacion",
            "tipo_certificacion",
            "plataforma_certificacion",
            "universidad_certificacion",
            "empresa_certificacion",
        ]

class CertificationSkillsMixin:
    def _get_ordered_skills(self, instance):
        """
        Devuelve las skills ordenadas.
        Prioridad:
        1) si viene prefetch desde backend en skills_links_ordered
        2) si no, usa la relación intermedia skills_rel
        3) si no, usa instance.skills.all() si existe
        """
        links = getattr(instance, "skills_links_ordered", None)

        if links is not None:
            ordered_skills = []
            for link in links:
                skill = getattr(link, "skill", None)
                if skill:
                    ordered_skills.append(skill)
            if ordered_skills:
                return ordered_skills

        try:
            rel_links = getattr(instance, "skills_rel", None)
            if rel_links is not None:
                ordered_links = rel_links.select_related("skill").all().order_by("orden", "id")
                ordered_skills = [link.skill for link in ordered_links if getattr(link, "skill", None)]
                if ordered_skills:
                    return ordered_skills
        except Exception as e:
            print(f"Error obteniendo skills_rel fallback para cert {getattr(instance, 'id', None)}: {e}")

        try:
            if hasattr(instance, "skills"):
                skills = list(instance.skills.all())
                if skills:
                    return skills
        except Exception as e:
            print(f"Error obteniendo skills fallback para cert {getattr(instance, 'id', None)}: {e}")

        return []
    
class CertificationSerializer(CertificationSkillsMixin, serializers.ModelSerializer):
    skills = serializers.SerializerMethodField()
    primary_skill = serializers.SerializerMethodField()
    instructores_detalle_certificacion = serializers.SerializerMethodField()
    specialization_courses = serializers.SerializerMethodField()
    specialization_detail = serializers.SerializerMethodField()

    class Meta:
        model = Certificaciones
        fields = '__all__'

    def get_skills(self, instance):
        ordered_skills = self._get_ordered_skills(instance)
        return SkillSerializer(ordered_skills, many=True).data

    def get_primary_skill(self, instance):
        ordered_skills = self._get_ordered_skills(instance)
        if not ordered_skills:
            return None
        return SkillSerializer(ordered_skills[0]).data
    def _resolve_specialization(self, instance):
        specialization = getattr(instance, "specialization", None)

        if specialization:
            return specialization

        specialization_name = (
            getattr(instance, "specialization_name_external", None)
            or getattr(instance, "nombre", None)
        )

        if not specialization_name:
            return None

        return (
            Specialization.objects
            .filter(specialization_name__iexact=specialization_name)
            .first()
        )

    def _is_specialization_type(self, instance):
        tipo = (getattr(instance, "tipo_certificacion", "") or "").strip().lower()
        return tipo in ["especialización", "especializacion", "specialization"]

    def _resolve_specialization(self, instance):
        """
        Prioridad:
        1. FK directa Certificaciones.specialization
        2. specialization_id_external contra Specialization.specialization_id
        3. specialization_name_external / nombre como fallback
        """
        specialization = getattr(instance, "specialization", None)
        if specialization:
            return specialization

        specialization_id_external = (
            getattr(instance, "specialization_id_external", None) or ""
        ).strip()

        if specialization_id_external:
            specialization = (
                Specialization.objects
                .filter(specialization_id=specialization_id_external)
                .only("id", "specialization_id", "specialization_name", "provider")
                .first()
            )
            if specialization:
                return specialization

        specialization_name = (
            getattr(instance, "specialization_name_external", None)
            or getattr(instance, "nombre", None)
            or ""
        ).strip()

        if not specialization_name:
            return None

        qs = Specialization.objects.filter(
            specialization_name__iexact=specialization_name
        )

        provider = (
            getattr(instance, "source_provider", None)
            or getattr(getattr(instance, "plataforma_certificacion", None), "nombre", None)
            or ""
        ).strip()

        if provider:
            qs = qs.filter(provider__iexact=provider)

        return (
            qs.only("id", "specialization_id", "specialization_name", "provider")
            .first()
        )


    def get_specialization_detail(self, instance):
        if not self._is_specialization_type(instance):
            return None

        specialization = self._resolve_specialization(instance)

        if specialization:
            return {
                "id": specialization.id,
                "specialization_id": specialization.specialization_id,
                "specialization_name": specialization.specialization_name,
                "provider": specialization.provider,
            }

        external_id = getattr(instance, "specialization_id_external", None)

        if external_id:
            return {
                "id": None,
                "specialization_id": external_id,
                "specialization_name": getattr(instance, "specialization_name_external", None) or instance.nombre,
                "provider": getattr(instance, "source_provider", None),
            }

        return None

    def get_specialization_courses(self, instance):
        if not self._is_specialization_type(instance):
            return []

        filters = {
            "vigente_certificacion": 0
        }

        internal_specialization_id = getattr(instance, "specialization_id", None)

        external_id = (
            getattr(instance, "specialization_id_external", None)
            or getattr(getattr(instance, "specialization", None), "specialization_id", None)
            or ""
        ).strip()

        if internal_specialization_id:
            filters["specialization_id"] = internal_specialization_id

        elif external_id:
            filters["specialization_id_external"] = external_id

        else:
            return []

        qs = (
            Certificaciones.objects
            .filter(**filters)
            .exclude(id=instance.id)
            .select_related(
                "plataforma_certificacion",
                "universidad_certificacion",
                "empresa_certificacion",
            )
            .only(
                "id",
                "slug",
                "nombre",
                "imagen_final",
                "metadescripcion_certificacion",
                "tipo_certificacion",
                "plataforma_certificacion_id",
                "universidad_certificacion_id",
                "empresa_certificacion_id",
                "plataforma_certificacion__id",
                "plataforma_certificacion__nombre",
                "plataforma_certificacion__plat_img",
                "plataforma_certificacion__plat_ico",
                "universidad_certificacion__id",
                "universidad_certificacion__nombre",
                "universidad_certificacion__univ_img",
                "universidad_certificacion__univ_ico",
                "empresa_certificacion__id",
                "empresa_certificacion__nombre",
                "empresa_certificacion__empr_img",
                "empresa_certificacion__empr_ico",
            )
            .order_by("id")[:20]
        )

        return CertificationSpecializationCourseSerializer(
            qs,
            many=True,
            context=self.context,
        ).data
    
    def get_instructores_detalle_certificacion(self, instance):
        links = getattr(instance, "instructor_links_prefetched", None)

        if links is not None:
            ordered_instructors = []
            for link in links:
                instructor = getattr(link, "instructor", None)
                if instructor:
                    ordered_instructors.append(instructor)
            return InstructorSerializer(ordered_instructors, many=True).data

        links = instance.instructor_links.select_related("instructor").all()
        instructors = [link.instructor for link in links if link.instructor]
        return InstructorSerializer(instructors, many=True).data
    
    def get_fecha_certificacion(self, instance):
        fecha = instance.fecha_creado_cert
        if isinstance(fecha, datetime):
            return fecha.date()
        return fecha

    def to_representation(self, instance):
        data = super().to_representation(instance)

        # Procesamiento de contenido_certificacion
        contenido_mod = data.get('contenido_certificacion') or ''
        contenido_mod = contenido_mod if isinstance(contenido_mod, str) else ''
        cantidad_modulos = contenido_mod.split('\n')[0] if '\n' in contenido_mod else contenido_mod
        contenido_certificacion = contenido_mod.split('\n')[1:] if '\n' in contenido_mod else []

        data['contenido_certificacion'] = {
            "cantidad_modulos": cantidad_modulos,
            "contenido_certificacion": contenido_certificacion
        }

        # Relaciones legacy/directas
        data['plataforma_certificacion'] = (
            PlataformaSerializer(instance.plataforma_certificacion).data
            if instance.plataforma_certificacion else None
        )
        data['universidad_certificacion'] = (
            UniverisitiesSerializer(instance.universidad_certificacion).data
            if instance.universidad_certificacion else None
        )
        data['empresa_certificacion'] = (
            EmpresaSerializer(instance.empresa_certificacion).data
            if instance.empresa_certificacion else None
        )

        # mantener tema_certificacion solo si todavía existe el campo
        if hasattr(instance, 'tema_certificacion'):
            data['tema_certificacion'] = (
                TopicsSerializer(instance.tema_certificacion).data
                if instance.tema_certificacion else None
            )
        else:
            data['tema_certificacion'] = None

        # skills reales y ordenadas
        data['skills'] = self.get_skills(instance)

        # primera skill real
        data['primary_skill'] = self.get_primary_skill(instance)

        # Procesamiento de módulos
        modulos_raw_str = data.get('modulos_certificacion', '')
        if isinstance(modulos_raw_str, str) and modulos_raw_str.strip():
            modulos_raw = modulos_raw_str.split('\n')
            modulos_procesados = []
            current_module = None

            for linea in modulos_raw:
                if linea is None:
                    continue
                linea = linea.strip()
                if not linea:
                    continue

                if 'Módulo' in linea:
                    if current_module:
                        modulos_procesados.append(current_module)

                    titulo_y_duracion = linea.split(' | Duración:')
                    if len(titulo_y_duracion) > 1:
                        titulo = titulo_y_duracion[0].split(':')[1].strip() if ':' in titulo_y_duracion[0] else ''
                        duracion = titulo_y_duracion[1].strip()
                    else:
                        titulo = ''
                        duracion = ''

                    current_module = {
                        'titulo': titulo,
                        'duracion': duracion,
                        'incluye': [],
                        'contenido': []
                    }

                elif current_module:
                    if 'Incluye' in linea:
                        continue
                    elif linea[:2].strip().isdigit():
                        current_module['incluye'].append(linea)
                    else:
                        current_module['contenido'].append(linea)

            if current_module:
                modulos_procesados.append(current_module)

            data['modulos_certificacion'] = modulos_procesados

        # Procesamiento de habilidades texto legacy
        habilidades_raw = data.get('habilidades_certificacion', '')
        if isinstance(habilidades_raw, str):
            data['habilidades_certificacion'] = [
                {
                    "id": index + 1,
                    "nombre": habilidad.strip()
                }
                for index, habilidad in enumerate(habilidades_raw.split('-'))
                if habilidad and habilidad.strip()
            ]

        # Procesamiento de aprendizajes
        aprendizajes_raw = data.get('aprendizaje_certificacion', '')
        if isinstance(aprendizajes_raw, str):
            data['aprendizaje_certificacion'] = [
                {
                    "id": index + 1,
                    "nombre": aprendizaje.strip()
                }
                for index, aprendizaje in enumerate(aprendizajes_raw.split('\n'))
                if aprendizaje and aprendizaje.strip()
            ]

        # Procesamiento de instructores
        instructores_raw = data.get('instructores_certificacion', '')
        if isinstance(instructores_raw, str):
            t = instructores_raw.strip()
            if not t or t.lower() in ['none', 'null']:
                data['instructores_certificacion'] = instructores_raw
            else:
                t = re.sub(r'\s*(?:&| and | y )\s*', ',', t, flags=re.IGNORECASE)
                parts = [p.strip() for p in t.split(',') if p and p.strip()]

                data['instructores_certificacion'] = [
                    {"id": idx + 1, "name": name}
                    for idx, name in enumerate(parts)
                ]

        # Procesamiento del video
        video_url_raw = data.get('video_certificacion')
        video_url = video_url_raw.strip() if isinstance(video_url_raw, str) else ''
        data['video_certificacion'] = {"url": video_url} if video_url else None

        # Agregar fecha
        data['fecha_creado_cert'] = instance.fecha_creado_cert
        data['cert_top'] = instance.cert_top

        return data


class CertificationSearchSerializer(CertificationSkillsMixin, serializers.ModelSerializer):
    tema_certificacion = serializers.SerializerMethodField()
    plataforma_certificacion = serializers.SerializerMethodField()
    universidad_certificacion = serializers.SerializerMethodField()
    empresa_certificacion = serializers.SerializerMethodField()
    primary_skill = serializers.SerializerMethodField()
    skills = serializers.SerializerMethodField()

    class Meta:
        model = Certificaciones
        fields = [
            "id",
            "slug",
            "nombre",
            "metadescripcion_certificacion",
            "imagen_final",
            "tipo_certificacion",
            "plataforma_certificacion_id",
            "tema_certificacion",
            "plataforma_certificacion",
            "universidad_certificacion",
            "empresa_certificacion",
            "primary_skill",
            "skills",
        ]

    def get_skills(self, instance):
        ordered_skills = self._get_ordered_skills(instance)
        if not ordered_skills:
            return []
        return SkillMiniSerializer(ordered_skills, many=True, context=self.context).data

    def get_primary_skill(self, instance):
        ordered_skills = self._get_ordered_skills(instance)
        if not ordered_skills:
            return None
        return SkillMiniSerializer(ordered_skills[0], context=self.context).data

    def get_tema_certificacion(self, instance):
        if not getattr(instance, "tema_certificacion", None):
            return None
        return TopicMiniSerializer(instance.tema_certificacion, context=self.context).data

    def get_plataforma_certificacion(self, instance):
        if not getattr(instance, "plataforma_certificacion", None):
            return None
        return PlataformaMiniSerializer(instance.plataforma_certificacion, context=self.context).data

    def get_universidad_certificacion(self, instance):
        if not getattr(instance, "universidad_certificacion", None):
            return None
        return UniversidadMiniSerializer(instance.universidad_certificacion, context=self.context).data

    def get_empresa_certificacion(self, instance):
        if not getattr(instance, "empresa_certificacion", None):
            return None
        return EmpresaMiniSerializer(instance.empresa_certificacion, context=self.context).data


class SuggestedCertificationSerializer(serializers.ModelSerializer):
    plataforma_certificacion = PlatformCardMiniSerializer(read_only=True)
    universidad_certificacion = UniversityCardMiniSerializer(read_only=True)
    empresa_certificacion = CompanyCardMiniSerializer(read_only=True)
    primary_skill = serializers.SerializerMethodField()

    class Meta:
        model = Certificaciones
        fields = [
            "id",
            "slug",
            "nombre",
            "imagen_final",
            "tipo_certificacion",
            "nivel_certificacion",
            "tiempo_certificacion",
            "plataforma_certificacion",
            "universidad_certificacion",
            "empresa_certificacion",
            "primary_skill",
        ]

    def get_primary_skill(self, obj):
        links = getattr(obj, "skills_links_ordered", None)

        if links is None:
            links = obj.skills_rel.select_related("skill").order_by("orden", "id")

        first_link = next(iter(links), None)

        if not first_link or not first_link.skill:
            return None

        skill = first_link.skill

        return {
            "id": skill.id,
            "nombre": skill.nombre,
            "translate": skill.translate,
            "slug": skill.slug,
            "skill_col": skill.skill_col,
            "skill_type": skill.skill_type,
            "skill_ico": skill.skill_ico,
            "skill_img": skill.skill_img,
        }

class OriginalCertificationDetailMiniSerializer(serializers.ModelSerializer):
    plataforma_certificacion = serializers.SerializerMethodField()
    tema_certificacion = serializers.SerializerMethodField()
    skills = serializers.SerializerMethodField()
    primary_skill = serializers.SerializerMethodField()

    class Meta:
        model = Certificaciones
        fields = [
            "id",
            "nombre",
            "slug",
            "imagen_final",
            "plataforma_certificacion",
            "tema_certificacion",
            "skills",
            "primary_skill",
        ]

    def get_plataforma_certificacion(self, obj):
        plat = getattr(obj, "plataforma_certificacion", None)

        if not plat:
            return None

        return {
            "id": plat.id,
            "nombre": plat.nombre,
            "slug": self._platform_slug(plat.nombre),
            "plat_img": self._url(plat.plat_img),
            "plat_ico": self._url(plat.plat_ico),
        }

    def get_tema_certificacion(self, obj):
        tema = getattr(obj, "tema_certificacion", None)

        if not tema:
            return None

        return {
            "id": tema.id,
            "nombre": tema.nombre,
            "translate": tema.translate,
            "tem_col": tema.tem_col,
        }

    def get_skills(self, obj):
        links = list(obj.skills_rel.all())

        return [
            {
                "id": link.skill.id,
                "nombre": link.skill.nombre,
                "translate": link.skill.translate,
                "slug": link.skill.slug,
                "skill_col": link.skill.skill_col,
                "skill_ico": self._url(link.skill.skill_ico),
            }
            for link in links
            if link.skill
        ]

    def get_primary_skill(self, obj):
        skills = self.get_skills(obj)
        return skills[0] if skills else None

    def _platform_slug(self, name):
        name = (name or "").strip().lower()

        mapping = {
            "coursera": "coursera",
            "edx": "edx",
            "ed x": "edx",
            "masterclass": "masterclass",
            "master class": "masterclass",
        }

        return mapping.get(name, name.replace(" ", "-"))

    def _url(self, value):
        if not value:
            return None

        request = self.context.get("request")
        url = value.url if hasattr(value, "url") else str(value)

        if url.startswith("http://") or url.startswith("https://"):
            return url

        return request.build_absolute_uri(url) if request else url


class OriginalCertificationSerializer(serializers.ModelSerializer):
    certification_title = serializers.CharField(
        source="certification.nombre",
        read_only=True,
    )
    certification_slug = serializers.CharField(
        source="certification.slug",
        read_only=True,
    )
    certification_image_url = serializers.SerializerMethodField()
    certification_detail = serializers.SerializerMethodField()
    platform_slug = serializers.SerializerMethodField()

    class Meta:
        model = OriginalCertification
        fields = [
            "title",
            "hist",
            "fondo",
            "certification_title",
            "certification_slug",
            "platform_slug",
            "certification_image_url",
            "certification_detail",
            "posicion",
        ]

    def get_platform_slug(self, obj):
        platform = getattr(obj.certification, "plataforma_certificacion", None)

        if not platform:
            return None

        name = (platform.nombre or "").strip().lower()

        mapping = {
            "coursera": "coursera",
            "edx": "edx",
            "ed x": "edx",
            "masterclass": "masterclass",
            "master class": "masterclass",
        }

        return mapping.get(name, name.replace(" ", "-"))

    def get_certification_image_url(self, obj):
        cert = obj.certification
        request = self.context.get("request")

        return self._build_url(cert.imagen_final, request)

    def get_certification_detail(self, obj):
        request = self.context.get("request")

        return OriginalCertificationDetailMiniSerializer(
            obj.certification,
            context={"request": request},
        ).data

    def _build_url(self, value, request):
        if not value:
            return None

        url = value.url if hasattr(value, "url") else str(value)

        if url.startswith("http://") or url.startswith("https://"):
            return url

        return request.build_absolute_uri(url) if request else url


class OriginalSerializer(serializers.ModelSerializer):
    image = serializers.SerializerMethodField()
    certifications = serializers.SerializerMethodField()

    class Meta:
        model = Original
        fields = [
            "id",
            "name",
            "slug",
            "extr",
            "esta",
            "image",
            "biog",
            "certifications",
        ]

    def get_certifications(self, obj):
        qs = getattr(obj, "prefetched_certifications", None)

        if qs is None:
            qs = obj.certifications.all().order_by("posicion")

        return OriginalCertificationSerializer(
            qs,
            many=True,
            context=self.context,
        ).data

    def get_image(self, obj):
        return self._abs_url(obj.image)

    def _abs_url(self, value):
        if not value:
            return None

        request = self.context.get("request")
        url = value.url if hasattr(value, "url") else str(value)

        if url.startswith("http://") or url.startswith("https://"):
            return url

        return request.build_absolute_uri(url) if request else url
    
class OriginalSliderSerializer(serializers.ModelSerializer):
    image = serializers.SerializerMethodField()

    class Meta:
        model = Original
        fields = [
            "id",
            "name",
            "slug",
            "extr",
            "esta",
            "image",
        ]

    def get_image(self, obj):
        return self._abs_url(obj.image)

    def _abs_url(self, value):
        if not value:
            return None

        request = self.context.get("request")
        url = value.url if hasattr(value, "url") else str(value)

        if url.startswith("http://") or url.startswith("https://"):
            return url

        return request.build_absolute_uri(url) if request else url

class PersonalizedRecommendationSerializer(serializers.ModelSerializer):

    class Meta:
        model = Certificaciones
        fields = [
            "id",
            "slug",
            "nombre",
            "imagen_final",
            "nivel_certificacion",
            "tiempo_certificacion",
        ]

class PersonalizedLeadRecommendationSerializer(
    serializers.ModelSerializer
):
    id_interno = serializers.CharField(
        read_only=True,
        allow_null=True,
        default="",
    )

    platform_id = serializers.IntegerField(
        source="plataforma_certificacion_id",
        read_only=True,
        allow_null=True,
    )

    provider = serializers.SerializerMethodField()
    platform_logo = serializers.SerializerMethodField()

    universidad_nombre = serializers.SerializerMethodField()
    empresa_nombre = serializers.SerializerMethodField()

    class Meta:
        model = Certificaciones

        fields = [
            "id",
            "id_interno",
            "slug",
            "nombre",
            "imagen_final",
            "nivel_certificacion",
            "tiempo_certificacion",

            # Plataforma
            "platform_id",
            "provider",
            "platform_logo",

            # Institución
            "universidad_nombre",
            "empresa_nombre",
        ]

    def get_provider(self, obj):
        platform = getattr(
            obj,
            "plataforma_certificacion",
            None,
        )

        if not platform:
            return ""

        return str(
            getattr(platform, "nombre", "") or ""
        ).strip()

    def get_platform_logo(self, obj):
        """
        plat_ico es un campo texto.

        Devolvemos la ruta prácticamente igual a como está en BD.
        No utilizamos request.build_absolute_uri porque los assets
        pueden pertenecer al frontend y no al servidor Django.
        """

        platform = getattr(
            obj,
            "plataforma_certificacion",
            None,
        )

        if not platform:
            return ""

        raw_logo = (
            getattr(platform, "plat_ico", None)
            or getattr(platform, "plat_img", None)
            or ""
        )

        logo = str(raw_logo or "").strip()

        if not logo:
            return ""

        if logo.lower() in {
            "none",
            "null",
            "undefined",
        }:
            return ""

        # Normalizar rutas guardadas desde Windows.
        logo = logo.replace("\\", "/")

        # Una URL externa se conserva.
        if logo.startswith(("http://", "https://")):
            return logo

        # Ruta del public/assets del frontend.
        if logo.startswith("assets/"):
            return f"/{logo}"

        # Ya es una ruta absoluta relativa al dominio.
        if logo.startswith("/"):
            return logo

        # Cualquier otra ruta relativa.
        return f"/{logo}"

    def get_universidad_nombre(self, obj):
        university = getattr(
            obj,
            "universidad_certificacion",
            None,
        )

        if not university:
            return ""

        return str(
            getattr(university, "nombre", "") or ""
        ).strip()

    def get_empresa_nombre(self, obj):
        company = getattr(
            obj,
            "empresa_certificacion",
            None,
        )

        if not company:
            return ""

        return str(
            getattr(company, "nombre", "") or ""
        ).strip()
        
class RankingEntrySerializer(serializers.ModelSerializer):
    universidad = UniversidadMiniSerializer(read_only=True)
    empresa = EmpresaMiniSerializer(read_only=True)
    total_certificaciones = serializers.IntegerField(read_only=True)

    class Meta:
        model = RankingEntry
        fields = [
            "id",
            "ranking",
            "posicion",
            "universidad",
            "empresa",
            "total_certificaciones",
        ]

class RankingSerializer(serializers.ModelSerializer):
    entradas = serializers.SerializerMethodField()

    class Meta:
        model = Ranking
        fields = [
            "id",
            "nombre",
            "descripcion",
            "image",
            "fecha",
            "tipo",
            "estado",
            "entradas",
        ]

    def get_entradas(self, obj):
        entradas = getattr(obj, "entradas_cache", None)

        if entradas is None:
            entradas = obj.entradas.select_related("universidad", "empresa").all()

        return RankingEntrySerializer(
            entradas,
            many=True,
            context=self.context
        ).data

class RankingPreviewEntrySerializer(serializers.Serializer):
    id = serializers.IntegerField()
    posicion = serializers.IntegerField()
    nombre = serializers.CharField()
    icono = serializers.CharField(allow_null=True)
    entidad_id = serializers.IntegerField()
    entidad_tipo = serializers.CharField()


class RankingPreviewSerializer(serializers.Serializer):
    id = serializers.IntegerField()
    nombre = serializers.CharField()
    descripcion = serializers.CharField(allow_null=True)
    image = serializers.ImageField(allow_null=True)
    tipo = serializers.CharField()
    entradas_preview = serializers.ListField()

class MarcaPermisosSerializer(serializers.ModelSerializer):
    class Meta:
        model = MarcaPermisos
        fields = ("id", "nombre_permiso", "visible", "orden")


class MarcaSerializer(serializers.ModelSerializer):
    permisos = MarcaPermisosSerializer(many=True, required=False)

    class Meta:
        model = Marca
        fields = (
            "id",
            "nombre",
            "slug",
            "descripcion",
            "logo",
            "color_principal",
            "color_secundario",
            "phrase",
            "about_us",
            "banner",
            "estado",
            "permisos",
        )

    def create(self, validated_data):
        permisos_data = validated_data.pop("permisos", [])
        marca = Marca.objects.create(**validated_data)
        for idx, p in enumerate(permisos_data):
            MarcaPermisos.objects.create(
                marca=marca,
                nombre_permiso=p.get("nombre_permiso"),
                visible=p.get("visible", True),
                orden=p.get("orden", idx),
            )
        return marca

    def update(self, instance, validated_data):
        permisos_data = validated_data.pop("permisos", None)

        # Campos básicos
        for attr, value in validated_data.items():
            setattr(instance, attr, value)
        instance.save()

        # Permisos (borramos y recreamos para simplificar)
        if permisos_data is not None:
            MarcaPermisos.objects.filter(marca=instance).delete()
            for idx, p in enumerate(permisos_data):
                MarcaPermisos.objects.create(
                    marca=instance,
                    nombre_permiso=p.get("nombre_permiso"),
                    visible=p.get("visible", True),
                    orden=p.get("orden", idx),
                )

        return instance

class MarcaPermisosPublicSerializer(serializers.ModelSerializer):
    class Meta:
        model = MarcaPermisos
        fields = ("id", "nombre_permiso", "visible", "orden")


class MarcaPublicSerializer(serializers.ModelSerializer):
    permisos = MarcaPermisosPublicSerializer(many=True)

    class Meta:
        model = Marca
        fields = (
            "id",
            "nombre",
            "slug",
            "descripcion",
            "logo",
            "color_principal",
            "color_secundario",
            "estado",
            "phrase",
            "about_us",
            "banner",
            "permisos",
        )

class LearningRouteLeadSerializer(serializers.ModelSerializer):
    class Meta:
        model = LearningRouteLead
        fields = [
            "id",
            "user",
            "email",
            "first_name",
            "last_name",
            "topics",
            "goal",
            "selected_plan",
            "status",
            "recommended_certifications",
            "stripe_customer_id",
            "stripe_subscription_id",
            "trial_start",
            "trial_end",
            "created_at",
            "updated_at",
        ]
        read_only_fields = [
            "id",
            "user",
            "status",
            "stripe_customer_id",
            "stripe_subscription_id",
            "trial_start",
            "trial_end",
            "created_at",
            "updated_at",
        ]