# certifications/serializers.py
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

        # Serializar relaciones completas
        representation['categoria_blog'] = CategoriesSerializer(instance.categoria_blog).data if instance.categoria_blog else None
        representation['autor_blog'] = AuthorsSerializer(instance.autor_blog).data if instance.autor_blog else None

        # Campos adicionales explícitos (evitando sobrescribir IDs)
        representation['categoria_blog_nombre'] = instance.categoria_blog.nombre_categoria_blog if instance.categoria_blog else None
        representation['autor_blog_nombre'] = instance.autor_blog.nombre_autor if instance.autor_blog else None
        representation['autor_img'] = instance.autor_blog.auto_img.url if instance.autor_blog and instance.autor_blog.auto_img else None

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
        fecha = instance.fecha_creado
        if isinstance(fecha, datetime):
            return fecha.date()
        return fecha
    def to_representation(self, instance):
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

        empresa_instance = instance.empresa_certificacion
        data['empresa_certificacion'] = EmpresaSerializer(empresa_instance).data if empresa_instance else None

        # Procesamiento de módulos
        if isinstance(data['modulos_certificacion'], str):
            
            modulos_raw = data['modulos_certificacion'].split('\n')
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
        if isinstance(data['habilidades_certificacion'], str):
            data['habilidades_certificacion'] = [
                {
                    "id": index +1,
                    "nombre": habilidad.strip()
                }
                for index, habilidad in enumerate(data['habilidades_certificacion'].split('-'))
            ]
            
        # Procesamiento de aprendizajes 
        if isinstance(data['aprendizaje_certificacion'], str):
            data['aprendizaje_certificacion'] = [
                {
                    "id": index+1,
                    "nombre": aprendizaje.strip()
                }
                for index, aprendizaje in enumerate(data['aprendizaje_certificacion'].split('\n'))
                if aprendizaje.strip()
            ]
            
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
       
        data['fecha_creado'] = instance.fecha_creado

        return data


class CertificationSearchSerializer(serializers.ModelSerializer):

    class Meta:
        model = Certificaciones
        fields = '__all__'   
    def get_fecha_certificacion(self, instance):
        fecha = instance.fecha_creado
        if isinstance(fecha, datetime):
            return fecha.date()
        return fecha
    def to_representation(self, instance):
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

        # Procesamiento de módulos
        if isinstance(data['modulos_certificacion'], str):
            
            modulos_raw = data['modulos_certificacion'].split('\n')
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
        if isinstance(data['habilidades_certificacion'], str):
            data['habilidades_certificacion'] = [
                {
                    "id": index +1,
                    "nombre": habilidad.strip()
                }
                for index, habilidad in enumerate(data['habilidades_certificacion'].split('-'))
            ]
            
        # Procesamiento de aprendizajes 
        if isinstance(data['aprendizaje_certificacion'], str):
            data['aprendizaje_certificacion'] = [
                {
                    "id": index+1,
                    "nombre": aprendizaje.strip()
                }
                for index, aprendizaje in enumerate(data['aprendizaje_certificacion'].split('\n'))
                if aprendizaje.strip()
            ]
            
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
       
        data['fecha_creado'] = instance.fecha_creado

        return data