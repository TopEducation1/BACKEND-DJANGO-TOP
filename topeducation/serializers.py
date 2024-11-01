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
            'imagen_final',
            'aprendizaje_certificacion'

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
        
        
        #Procesamiento de las habilidades
        if isinstance(data['habilidades_certificacion'], str):
            data['habilidades_certificacion'] = [
                {
                    "id": index +1,
                    "nombre": habilidad.strip()
                }
                
                for index, habilidad in enumerate(data['habilidades_certificacion'].split('-'))
            ]
            
            
        
        #Procesamiento de aprendizajes 
        if isinstance(data['aprendizaje_certificacion'], str):
            data['aprendizaje_certificacion'] = [
                {
                    "id": index+1,
                    "nombre": aprendizaje.strip()
                }
                
                for index, aprendizaje in enumerate(data['aprendizaje_certificacion'].split('\n'))
            ]
            
            

        # Modificar la representación final de los datos
        data['contenido_certificacion'] = all_content
        data['cantidad_modulos'] = content_modules
        data['imagen_final'] = data['url_imagen_universidad_certificacion'] or data['url_imagen_empresa_certificacion']

        return data



class CertificationSearchSerializer(serializers.ModelSerializer):

    class Meta:
        model = Certificaciones
        fields = ['id', 'nombre', 'url_imagen_universidad_certificacion']

    
