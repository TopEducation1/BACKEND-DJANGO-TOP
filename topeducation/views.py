import re
from django.shortcuts import render
from rest_framework import viewsets
from .models import *
from .serializers import *
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
from django.views.decorators.csrf import csrf_exempt
from rest_framework.response import Response
from rest_framework.decorators import api_view
import json
from django.http import JsonResponse
from django.views.decorators.http import require_http_methods
from django.shortcuts import get_object_or_404





# EndPoint to get the certifications
class CertificationList(APIView):
    
    # DEFINIR EL METODO GET QUE SE REALIZA DESDE EL FRONT    
    def get(self, request):
        
        # Queryset de las certificaciones
        certifications_queryset = Certificaciones.objects.all()
        serializer = CertificationSerializer(certifications_queryset, many = True)
        # RETORNA LOS DATOS EN JSON
        #(serializer.data)
        return Response(serializer.data)
    
    

@csrf_exempt
@api_view(['POST'])
def receive_tags(request):
    if request.method == 'POST':
        tags = request.data.get('tags', [])
        if not isinstance(tags, list):
            return Response({"Error": "Formato de datos invalido"}, status=status.HTTP_400_BAD_REQUEST)
        
        
        if not all(isinstance(tag, str) for tag in tags):
            return Response({"Error": "Cada tag debe ser una cadena de texto"}, status=status.HTTP_400_BAD_REQUEST)
        
        print(f"Tags recibidos: {tags}")
        
        
        return Response({"message": "Tags recibidos correctamente"}, status = status.HTTP_200_OK)
    
    return Response({"error": "Metodo no permitido"}, status=status.HTTP_405_METHOD_NOT_ALLOWED)




    
  
  
#EndPoint to get the skills  
class SkillsList (APIView):
    
    def get(self, request):
        
        #Queryset of the skills
        skills = Habilidades.objects.all()
        skills_serializer = SkillsSerializer(skills, many= True)
        
        return Response (skills_serializer.data)
    

# EndPoint to get the Universities
class UniversitiesList (APIView):
    
    def get(self, request):
        
        #Queryset of the Universities
        universities = Universidades.objects.all()
        universities_serializer = UniverisitiesSerializer(universities, many= True)
        
        return Response(universities_serializer.data)


class TopicsList (APIView):
    
    def get(self, request):
        
        #Queryset of the Topics
        topics =  Temas.objects.all()
        topics_serializer = TopicsSerializer(topics, many = True)
        
        return Response(topics_serializer.data)
    


# Esta función obtiene el id de la certificación que el usuario quiere ver en vista especifica y retorna toda su información
@api_view(['GET'])
def get_certification(request, id):
    try:
        # Validar que el id existe
        if not id:
            return Response(
                {'Error': 'Se requiere el ID de la certificación'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        # Obtener la certificación   
        certification = Certificaciones.objects.get(id=id)
        
        # Separar cada instructor y formatear para mayor facilidad de mostrar en el front
        certification_instructors = certification.certification_instructors.split('\n')
        instructor_links = []
        
        # regex para separar link del nombre
        regex = re.compile(r'^([^,]+),\s*(https?:\/\/[^\s,]+),')
            
        
        for line in certification_instructors:
            match = regex.match(line)
            if match:
                name = match.group(1)
                link = match.group(2)
                
                # Diccionario con nombre y link
                instructor_links.append({
                    'name': name,
                    'link': link
                })
        
        # Serializar y retornar
        serializer = CertificationSerializer(certification)
        data = serializer.data
        
        
        
        data['certification_instructors'] = instructor_links
        
    
        #Separar items de aprendizaje
        certification_learnings = certification.certification_learnings.split('\n')        
        
        data['certification_learnings'] = certification_learnings
        
        
        #Separar habilidades
        certification_skills = certification.certification_skills.split('-')
        
        data['certification_skills'] = certification_skills
        
        # Retornar los datos de la certificación
        return Response(data)
        

        
    except Certificaciones.DoesNotExist:
        return Response(
            {'error': 'Certificación no encontrada'},
            status=status.HTTP_404_NOT_FOUND
        )
    except ValueError:
        return Response(
            {'error': 'ID Invalido'},
            status=status.HTTP_400_BAD_REQUEST
        )


# Esta funcion sirve para recibir los tags por los cuales el ususario quiere filtrar las busquedas y retornar el queryset con las certificaciones filtradas
class filter_by_tags(APIView):
    def get(self, request):
        
        params = dict(request.GET)

        print(params)
        
        
        return Response({
            'message': 'Parametros recibidos'
        })    
        
        
        
            
        