# certifications/serializers.py
from rest_framework import serializers
from .models import *

# CONVIERTE LOS MODELOS EN JSON PARA CONSUMIRLOS DESDE EL FRONT



        

class SkillsSerializer(serializers.ModelSerializer):
    
    class Meta:
        model = Skills
        
        fields = '__all__'
        
class UniverisitiesSerializer(serializers.ModelSerializer):
    
    class Meta:
        model = Universities
        
        fields = '__all__'    


class TopicsSerializer (serializers.ModelSerializer):
    
    class Meta:
        model = Topics
        
        fields = ['id', 'topic_name']

class CertificationSerializer(serializers.ModelSerializer):
    certification_topic = TopicsSerializer(read_only = True)
    class Meta:
        model = Certification
        fields = '__all__'