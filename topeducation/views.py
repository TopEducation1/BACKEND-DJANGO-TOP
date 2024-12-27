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
from django.db.models import Q
from django.core.paginator import EmptyPage, PageNotAnInteger
from rest_framework.pagination import PageNumberPagination
from django.views import View



class CustomPagination(PageNumberPagination):
    page_size = 12
    page_size_query_param = 'page_size'
    max_page_size = 100
    
    
    def get_paginated_response(self, data):
        return Response({
            'count': self.page.paginator.count,
            'next': self.get_next_link(),
            'previous': self.get_previous_link(),
            'total_page': self.page.paginator.num_pages,
            'results': data
        })




# EndPoint to get the certifications
class CertificationList(APIView):
    
    pagination_class = CustomPagination
    
    # DEFINIR EL METODO GET QUE SE REALIZA DESDE EL FRONT    
    def get(self, request):
        
        
        
        # Queryset de las certificaciones
        certifications_queryset = Certificaciones.objects.all().select_related(
            'tema_certificacion'
        )
        
        
        
        paginator = self.pagination_class()
        paginated_queryset = paginator.paginate_queryset(certifications_queryset, request)
        
        
        serializer = CertificationSerializer(paginated_queryset, many = True)

        return paginator.get_paginated_response(serializer.data)

class CertificationsCafam(APIView):
    
    def get(self, request):
        
        #Recibir el parametro de la cantidad de certificaciones
        amount = int(request.query_params.get('amount', 7))
        
        #Consultar las certificaciones limitando la cantidad
        certificationsCafam_queryset = Certificaciones.objects.all()[:amount]
        
        
        serializer = CertificationSerializer(certificationsCafam_queryset, many = True)
        
        return Response(serializer.data, status=status.HTTP_200_OK)
    
    

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
class CertificationDetailView(APIView):
    def get(self, request, id):
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
            certification_instructors = certification.instructores_certificacion.split('\n')
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
            
            
            
            data['instructores_certificacion'] = instructor_links
            

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

class filter_by_tags(APIView):
    pagination_class = CustomPagination
    
    def get(self, request):
        try:
            # Obtener los parámetros de la request
            params = request.query_params.dict()
            print(params)
            
            # Extraer parámetros de paginación
            page = params.pop('page', '1')
            page_size = params.pop('page_size', '12')
            
            # Iniciar el queryset base
            queryset = Certificaciones.objects.all()
            
            if 'plataforma' in params:
                platform_name = params['plataforma']
                print(platform_name)
                platform_mapping = {
                    'EdX': 1,
                    "Coursera": 2,
                    'MasterClass': 3
                }
                
                platform_id = platform_mapping.get(platform_name)
                print(platform_id)
                if platform_id:
                    queryset = queryset.filter(plataforma_certificacion_id = platform_id)
                    print(queryset)
                
                
            
            # Mapeo de parámetros del frontend a campos del modelo
            field_mapping = {
                'temas': 'tema_certificacion__nombre',
                'universidad': 'universidad_certificacion__nombre',
                'empresa': 'empresa_certificacion__nombre',
            }
            
            
            
            # Aplicar filtros
            for param, values in params.items():
                if param in field_mapping and param != 'plataforma':
                    field_name = field_mapping[param]
                    # Si el valor viene como lista separada por comas
                    if ',' in values:
                        tags = [tag.strip() for tag in values.split(',')]
                        queryset = queryset.filter(**{f"{field_name}__in": tags})
                    else:
                        queryset = queryset.filter(**{f"{field_name}": values})
                        print(queryset)
                        
            # Aplicar paginación
            paginator = self.pagination_class()
            paginated_queryset = paginator.paginate_queryset(queryset, request)
            
            # Serializar resultados
            serializer = CertificationSerializer(paginated_queryset, many=True)
            
            # Retornar respuesta paginada
            return paginator.get_paginated_response(serializer.data)
            
        except Exception as e:
            print(f"Error en filter_by_tags: {str(e)}")
            return Response(
                {'error': 'Error al filtrar certificaciones'},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )
    


class filter_by_search(APIView):
    # Esta función es para filtrar en los resultados por medio de la barra de búsqueda
    def post(self, request):
        
        query_string = request.data.get('data', "")
        
        print("DATOS RECIBIDOS: ", query_string)
        
        # Filtrar por tema
        tema = Temas.objects.filter(nombre__icontains=query_string).first()
        
        #Filtrar por nombre
        nombre = Certificaciones.objects.filter(nombre__icontains=query_string).first()
        
        # Filtrar por universidad
        universidad = Universidades.objects.filter(nombre__icontains=query_string).first()
        
        # Filtrar por empresa
        empresa = Empresas.objects.filter(nombre__icontains=query_string).first()
        
        # Inicializar lista de resultados
        filtered_results = Certificaciones.objects.none()
        
        # Filtrar por tema
        if tema:
            tema_results = Certificaciones.objects.filter(tema_certificacion_id=tema.id)
            filtered_results = filtered_results | tema_results
        
        # Filtrar por universidad
        if universidad:
            universidad_results = Certificaciones.objects.filter(universidad_certificacion_id=universidad.id)
            filtered_results = filtered_results | universidad_results
        
        # Filtrar por empresa
        if empresa:
            empresa_results = Certificaciones.objects.filter(empresa_certificacion=empresa.id)
            filtered_results = filtered_results | empresa_results
        
        if nombre:
            nombre_results = Certificaciones.objects.filter(nombre__icontains = query_string)
            filtered_results = filtered_results | nombre_results
            
        # Serializar resultados
        serializer = CertificationSearchSerializer(filtered_results.distinct(), many=True)
        
        # Devolver la respuesta con los datos serializados
        return Response(
            serializer.data,
            status=status.HTTP_200_OK
        )