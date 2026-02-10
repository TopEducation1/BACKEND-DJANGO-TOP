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
        fields = ['id', 'nombre', 'region_universidad_id', 'univ_img','univ_ico','univ_fla','univ_est','univ_top', 'region_nombre', 'total_certificaciones']

    def get_region_nombre(self, obj):
        return obj.region_universidad.nombre if obj.region_universidad else "No"


class TopicsSerializer (serializers.ModelSerializer):
    
    class Meta:
        model = Temas
        
        fields = ['id', 'nombre','tem_type','tem_col','tem_img','tem_est']

class PlataformaSerializer (serializers.ModelSerializer):
    
    class Meta:
        model = Plataformas
        
        fields = ['id', 'nombre','plat_img','plat_ico']

class EmpresaSerializer (serializers.ModelSerializer):
    total_certificaciones = serializers.IntegerField(read_only=True)
    #total_certificaciones = serializers.IntegerField()

    class Meta:
        model = Empresas
        
        fields = ['id', 'nombre','empr_img','empr_ico','empr_est','empr_top','total_certificaciones']


class CertificationSerializer(serializers.ModelSerializer):
    
    class Meta:
        model = Certificaciones
        fields = '__all__'

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

        # Relaciones
        data['tema_certificacion'] = TopicsSerializer(instance.tema_certificacion).data if instance.tema_certificacion else None
        data['plataforma_certificacion'] = PlataformaSerializer(instance.plataforma_certificacion).data if instance.plataforma_certificacion else None
        data['universidad_certificacion'] = UniverisitiesSerializer(instance.universidad_certificacion).data if instance.universidad_certificacion else None
        data['empresa_certificacion'] = EmpresaSerializer(instance.empresa_certificacion).data if instance.empresa_certificacion else None

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

        # Procesamiento de habilidades
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

        # Procesamiento de instructores (string -> lista)
        instructores_raw = data.get('instructores_certificacion', '')
        if isinstance(instructores_raw, str):
            t = instructores_raw.strip()
            if not t or t.lower() in ['none', 'null']:
                data['instructores_certificacion'] = instructores_raw
            else:
                import re
                # convierte "&", "and", "y" en coma y separa por coma
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




class CertificationSearchSerializer(serializers.ModelSerializer):

    class Meta:
        model = Certificaciones
        fields = '__all__'   
    def get_fecha_certificacion(self, instance):
        fecha = instance.fecha_creado_cert
        if isinstance(fecha, datetime):
            return fecha.date()
        return fecha
    def to_representation(self, instance):
        try:
            data = super().to_representation(instance)
            content = data['contenido_certificacion']
            
            contenido_mod = data.get('contenido_certificacion', '')
            lineas = contenido_mod.split('\n') if isinstance(contenido_mod, str) else []
            cantidad_modulos = lineas[0] if len(lineas) > 0 else ''
            contenido_certificacion = lineas[1:] if len(lineas) > 1 else []

            data['contenido_certificacion'] = {
                "cantidad_modulos": cantidad_modulos,
                "contenido_certificacion": contenido_certificacion
            }

            
            tema_instance = instance.tema_certificacion
            data['tema_certificacion'] = TopicsSerializer(tema_instance).data if tema_instance else None
            plataforma_instance = instance.plataforma_certificacion
            data['plataforma_certificacion'] = PlataformaSerializer(plataforma_instance).data if plataforma_instance else None
            universidad_instance = instance.universidad_certificacion
            data['universidad_certificacion'] = UniverisitiesSerializer(universidad_instance).data if universidad_instance else None
            data['empresa_certificacion'] = EmpresaSerializer(instance.empresa_certificacion).data if instance.empresa_certificacion else None
            # Procesamiento de módulos
            if isinstance(data['modulos_certificacion'], str):
                modulos_raw = data['modulos_certificacion'].strip().split('\n') if data['modulos_certificacion'].strip() else []
            else:
                modulos_raw = []

            modulos_procesados = []
            current_module = None

            for linea in modulos_raw:
                linea = linea.strip()
                if not linea:
                    continue

                if 'Módulo' in linea:
                    if current_module:
                        modulos_procesados.append(current_module)

                    # Evitar error por índice inexistente
                    titulo = modulos_raw[0] if len(modulos_raw) > 0 else ''
                    duracion = modulos_raw[1] if len(modulos_raw) > 1 else ''

                    current_module = {
                        'titulo': titulo,
                        'duracion': duracion,
                        'incluye': [],
                        'contenido': []
                    }
                elif current_module:
                    if 'Incluye' in linea:
                        continue
                    elif linea[:2].isdigit():  # Si empieza con número
                        current_module['incluye'].append(linea)
                    else:
                        current_module['contenido'].append(linea)

            if current_module:
                modulos_procesados.append(current_module)

            data['modulos_certificacion'] = modulos_procesados
                #print(modulos_procesados)
            # Procesamiento de las habilidades
            habilidades_raw = data.get('habilidades_certificacion')
            if isinstance(habilidades_raw, str):
                data['habilidades_certificacion'] = [
                    {"id": i+1, "nombre": h.strip()} for i, h in enumerate(habilidades_raw.split('-')) if h.strip()
                ]
            else:
                data['habilidades_certificacion'] = []

                
            # Procesamiento de aprendizajes 
            aprendizajes_raw = data.get('aprendizaje_certificacion')
            if isinstance(aprendizajes_raw, str):
                data['aprendizaje_certificacion'] = [
                    {"id": i+1, "nombre": a.strip()} for i, a in enumerate(aprendizajes_raw.split('\n')) if a.strip()
                ]
            else:
                data['aprendizaje_certificacion'] = []

                
            # Procesamiento del video
            if isinstance(data.get('video_certificacion'), str):
                video_url = data['video_certificacion'].strip()
                if video_url:
                    data['video_certificacion'] = {
                        "url": video_url
                    }
                else:
                    data['video_certificacion'] = None

            # Modificar la representación final de los datos
            #data['imagen_final'] = data['url_imagen_universidad_certificacion'] or data['url_imagen_empresa_certificacion']
            #data['plataforma_certificacion_id'] = instance.plataforma_certificacion_id
        
            data['fecha_creado_cert'] = instance.fecha_creado_cert
            return data
        except Exception as e:
            print("Error al procesar certificación:", instance.id)
            print("Contenido:", data)
            raise e
        


class OriginalCertificationSerializer(serializers.ModelSerializer):
    certification_title     = serializers.CharField(source='certification.nombre', read_only=True)
    certification_slug      = serializers.CharField(source='certification.slug', read_only=True)
    source_type             = serializers.SerializerMethodField()
    source_object           = serializers.SerializerMethodField()
    certification_image_url = serializers.SerializerMethodField()
    certification_detail    = serializers.SerializerMethodField()  # ← Nuevo campo

    class Meta:
        model = OriginalCertification
        fields = [
            'title',
            'hist',
            'fondo',
            'certification_title',
            'certification_slug',
            'source_type',
            'source_object',
            'certification_image_url',
            'certification_detail',  # ← lo agregamos a los campos
            'posicion',
        ]

    def _build_url(self, value, request, use_media=False):
        if not value:
            return None
        if isinstance(value, str):
            return value if not use_media else (
                value if value.startswith('http')
                else request.build_absolute_uri(settings.MEDIA_URL + value.lstrip('/'))
            )
        if hasattr(value, 'url'):
            return value.url if not use_media else request.build_absolute_uri(value.url)
        return None

    def get_source_type(self, obj):
        cert = obj.certification
        if getattr(cert, 'universidad_certificacion', None):
            return 'universidad'
        if getattr(cert, 'empresa_certificacion', None):
            return 'empresa'
        return 'certificación'

    def get_source_object(self, obj):
        cert = obj.certification
        request = self.context.get('request')

        uni = getattr(cert, 'universidad_certificacion', None)
        if uni:
            return UniverisitiesSerializer(uni, context={'request': request}).data

        emp = getattr(cert, 'empresa_certificacion', None)
        if emp:
            return EmpresaSerializer(emp, context={'request': request}).data

        return {}

    def get_certification_image_url(self, obj):
        cert = obj.certification
        request = self.context.get('request')

        uni = getattr(cert, 'universidad_certificacion', None)
        if uni:
            return self._build_url(uni.univ_img, request)

        emp = getattr(cert, 'empresa_certificacion', None)
        if emp:
            return self._build_url(emp.empr_img, request)

        if hasattr(cert, 'imagen_final'):
            return self._build_url(cert.imagen_final, request, use_media=False)

        return None
    
    def get_certification_detail(self, obj):
        request = self.context.get('request')
        return CertificationSerializer(obj.certification, context={'request': request}).data



class OriginalSerializer(serializers.ModelSerializer):
    image = serializers.SerializerMethodField()
    certifications = serializers.SerializerMethodField()

    class Meta:
        model = Original
        fields = ['id','name','slug','extr','esta','image','biog','certifications']

    def get_certifications(self, obj):
        rel = getattr(obj, 'certifications', None)  # related_name si existe
        qs = (rel.all() if rel is not None else obj.originalcertification_set.all()).order_by('posicion')
        return OriginalCertificationSerializer(qs, many=True, context=self.context).data

    def get_image(self, obj):
        return self._abs_url(obj.image)

    def _abs_url(self, value):
        if not value:
            return None
        request = self.context.get('request')
        url = value.url if hasattr(value, 'url') else str(value)

        # Si ya es absoluta, devuélvela tal cual
        if url.startswith('http://') or url.startswith('https://'):
            return url

        # Si es relativa (/media/...), construye absoluta cuando haya request
        return request.build_absolute_uri(url) if request else url



class RankingEntrySerializer(serializers.ModelSerializer):
    universidad = UniverisitiesSerializer(read_only=True)
    empresa = EmpresaSerializer(read_only=True)
    total_certificaciones = serializers.SerializerMethodField()

    class Meta:
        model = RankingEntry
        fields = ['id', 'ranking','posicion', 'universidad', 'empresa','total_certificaciones']
    
    def get_total_certificaciones(self, obj):
        if obj.universidad:
            return obj.universidad.certificaciones.count()
        elif obj.empresa:
            return obj.empresa.certificaciones.count()
        return 0

class RankingSerializer(serializers.ModelSerializer):
    entradas = RankingEntrySerializer(many=True)

    class Meta:
        model = Ranking
        fields = ['id', 'nombre', 'descripcion','image', 'fecha', 'tipo', 'estado', 'entradas']


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