# certifications/serializers.py
from rest_framework import serializers
from .models import *

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
        
        fields = ['id', 'name']

class CertificationSerializer(serializers.ModelSerializer):
    certification_topic = TopicsSerializer(read_only = True)
    class Meta:
        model = Certificaciones
        fields = '__all__'
        
