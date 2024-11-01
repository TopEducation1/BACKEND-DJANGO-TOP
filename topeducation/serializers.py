# certifications/serializers.py
from rest_framework import serializers
from .models import *
from django.db.models import F


# CONVIERTE LOS MODELOS EN JSON PARA CONSUMIRLOS DESDE EL FRONT

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
    tema_certificacion = TopicsSerializer(read_only=True)

    class Meta:
        model = Certificaciones
        fields = [
            'id',
            'nombre',
            'tema_certificacion',
            'url_imagen_empresa_certificacion',
            'url_imagen_universidad_certificacion',
            'url_imagen_plataforma_certificacion',
            'url_certificacion_original',
            'metadescripcion_certificacion',
            'lenguaje_certificacion',
            'nivel_certificacion',
            'tiempo_certificacion',
            'contenido_certificacion',
            'habilidades_certificacion',
            'imagen_final'

        ]

    #Representación de los datos
    def to_representation(self, instance):
        data = super().to_representation(instance)

        # Acceder a los valores procesados en la vista y pasarlos correctamente
        content = data['contenido_certificacion']
        
        # Separar los módulos y el contenido
        modules = content.split('\n', 1)
        content_modules = modules[0].strip()
        all_content = modules[1].replace('\n', ' ').strip() if len(modules) > 1 else ''

        # Modificar la representación final de los datos
        data['aprendizaje_certificacion'] = instance.aprendizaje_certificacion.split('\n')  # Si ya fue procesado en la vista
        data['contenido_certificacion'] = all_content
        data['cantidad_modulos'] = content_modules
        data['imagen_final'] = data['url_imagen_universidad_certificacion'] or data['url_imagen_empresa_certificacion']

        return data



class CertificationSearchSerializer(serializers.ModelSerializer):

    class Meta:
        model = Certificaciones
        fields = ['id', 'nombre', 'url_imagen_universidad_certificacion']

    
