# certifications/serializers.py
from django.conf import settings
from datetime import datetime
from rest_framework import serializers
from .models import *
from django.db.models import F


# CONVIERTE LOS MODELOS EN JSON PARA CONSUMIRLOS DESDE EL FRONT

class BlogSerializer(serializers.ModelSerializer):
    class Meta:
        model = Blog 
        fields = '__all__'

    def to_representation(self, instance):
        representation = super().to_representation(instance)

        request = self.context.get('request')  # importante para URL absoluta

        # Imagen del blog
        if instance.miniatura_blog and request:
            representation['miniatura_blog'] = request.build_absolute_uri(instance.miniatura_blog.url)
        else:
            representation['miniatura_blog'] = "Test"

        # Serializar categoría
        categoria_instance = instance.categoria_blog
        representation['categoria_blog'] = CategoriesSerializer(categoria_instance).data if categoria_instance else None

        try:
            autor_instance = instance.autor_blog
            categoria = instance.categoria_blog

            representation['categoria_blog_id'] = categoria.nombre_categoria_blog if categoria else None
            representation['autor_blog_id'] = autor_instance.nombre_autor if autor_instance else None

            # Si el autor tiene imagen, hazla absoluta también
            if autor_instance and autor_instance.auto_img and request:
                representation['autor_img'] = request.build_absolute_uri(autor_instance.auto_img.url)
            else:
                representation['autor_img'] = None

            representation['autor_blog'] = AuthorsSerializer(autor_instance).data if autor_instance else None

        except Exception as e:
            print(f"Error serializing blog: {e}")
            representation['categoria_blog_id'] = None
            representation['autor_blog_id'] = None
            representation['autor_img'] = None

        return representation


 
            
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

    class Meta:
        model = Universidades
        fields = ['id', 'nombre', 'region_universidad_id', 'univ_img','univ_ico','univ_fla','univ_est', 'region_nombre']

    def get_region_nombre(self, obj):
        return obj.region_universidad.nombre if obj.region_universidad else "No"


class TopicsSerializer (serializers.ModelSerializer):
    
    class Meta:
        model = Temas
        
        fields = ['id', 'nombre','tem_type','tem_col','tem_img']

class PlataformaSerializer (serializers.ModelSerializer):
    
    class Meta:
        model = Plataformas
        
        fields = ['id', 'nombre','plat_img','plat_ico']

class EmpresaSerializer (serializers.ModelSerializer):
    
    class Meta:
        model = Empresas
        
        fields = ['id', 'nombre','empr_img','empr_ico','empr_est']


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
            
            contenido_mod = data['contenido_certificacion']
            cantidad_modulos = contenido_mod.split('\n')[0]
            contenido_certificacion = contenido_mod.split('\n')[1:]
            
            data['contenido_certificacion'] = {
                
                "cantidad_modulos": cantidad_modulos,
                "contenido_certificacion" : contenido_certificacion
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
                
                modulos_raw = data.get('modulos_certificacion')
                if isinstance(modulos_raw, str):
                    modulos_raw = modulos_raw.strip().split('\n')
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
                            
                        titulo_y_duracion = linea.split(' | Duración:')
                        if len(titulo_y_duracion) > 1:
                            titulo = titulo_y_duracion[0].split(':')[1].strip()
                            duracion = titulo_y_duracion[1].strip()
                        else:
                            titulo = ''
                            duracion = ''
                            
                        current_module = {
                            'titulo': modulos_raw[0],
                            'duracion': modulos_raw[1],
                            'incluye': [],
                            'contenido': []
                        }
                    elif current_module:
                        if 'Incluye' in linea:
                            continue
                        elif linea.startswith(('1 ', '2 ', '3 ', '4 ', '5 ', '6 ', '7 ', '8 ', '9 ')):
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
            'certification_title',
            'certification_slug',
            'source_type',
            'source_object',
            'certification_image_url',
            'certification_detail',  # ← lo agregamos a los campos
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
    certifications = OriginalCertificationSerializer(many=True, read_only=True)

    class Meta:
        model = Original
        fields = [
            'id',
            'name',
            'slug',
            'image',
            'biog',
            'certifications',
        ]

