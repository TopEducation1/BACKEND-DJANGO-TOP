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
        
        try:
            
            auto = Autor.objects.get(id = instance.autor_blog_id)
            categoria = CategoriaBlog.objects.get(id = instance.categoria_blog_id)
            representation['categoria_blog_id'] = categoria.nombre_categoria_blog
            representation['autor_blog_id'] = auto.nombre_autor
            
        except CategoriaBlog.DoesNotExist:
            representation['categoria_blog_id'] = None
            representation['autor_blog_id'] = None
        
        return representation
            
        

class SkillsSerializer(serializers.ModelSerializer):
    
    class Meta:
        model = Habilidades
        
        fields = '__all__'
        
class UniverisitiesSerializer(serializers.ModelSerializer):
    
    class Meta:
        model = Universidades
        
        fields = '__all__'    


class TopicsSerializer (serializers.ModelSerializer):
    
    class Meta:
        model = Temas
        
        fields = ['id', 'nombre']
        
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
        data['imagen_final'] = data['url_imagen_universidad_certificacion'] or data['url_imagen_empresa_certificacion']
        
        data['plataforma_certificacion_id'] = instance.plataforma_certificacion_id

        return data



class CertificationSearchSerializer(serializers.ModelSerializer):

    class Meta:
        model = Certificaciones
        fields = ['id', 'nombre', 'url_imagen_universidad_certificacion', 'slug']

    
