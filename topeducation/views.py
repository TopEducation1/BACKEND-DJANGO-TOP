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
        params = dict(request.GET)
        
        
        # Extraer datos de paginacion
        page = params.pop('page', [1])[0]
        page_size = params.pop('page_size', [12])[0]
        
        #Limpiar y validar parametros
        cleaned_params = {}
        
        
        # Convertir los valores de params de listas a valores individuales si es necesario
        for key, values in params.items():
            if isinstance(values, list):
                cleaned_params[key] = [tag.strip() for tag in values[0].split(',') if tag.strip()]
            else:
                cleaned_params[key] = [values.strip()] if values.strip() else []
                
        category_to_model = {
            'tema': Temas,
            'universidad': Universidades,
            'empresa': Empresas,
            'plataforma': Plataformas,
            'habilidad': Habilidades
        }
        
        queryset = Certificaciones.objects.all().select_related(
            'tema_certificacion'
        )
        
        
        
        # Para depuración
        print("Parámetros recibidos:", params)
        
        for category, tags in cleaned_params.items():
            if category in category_to_model and tags:
                model = category_to_model[category]
                category_q = Q()
                
                # Construir query para tags dentro de la categoría (OR)
                for tag in tags:
                    # Obtener el ID del tag
                    try:
                        tag_obj = model.objects.get(nombre=tag)
                        field_name = f"{category}_certificacion"
                        category_q |= Q(**{f"{field_name}": tag_obj})
                    except model.DoesNotExist:
                        print(f"Tag no encontrado: {tag} en categoría {category}")
                        continue
                
                # Aplicar el filtro de esta categoría
                if category_q:
                    queryset = queryset.filter(category_q)
                    # Para depuración
                    print(f"Cantidad de resultados después de filtrar {category}:", queryset.count())
                    print("Query SQL:", queryset.query)
                    
        paginator = self.pagination_class()
        paginated_queryset = paginator.paginate_queryset(queryset, request)
        
        
        
        serializer = CertificationSerializer(paginated_queryset, many=True)
        print(serializer.data)
        return paginator.get_paginated_response(serializer.data)
    
    


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