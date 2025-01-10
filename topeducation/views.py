from datetime import timedelta, timezone
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
            
            if 'empresas' in params:
                empresa_nombre = params['empresas']
                print(empresa_nombre)
                empresa_mapping = {
                    'Capitals Coalition': 1,
                    'DeepLearning.AI': 2,
                    'Big Interview': 3,
                    'UBITS': 4,
                    'HubSpot Academy': 5,
                    'SV Academy': 6,
                    'Pathstream': 7,
                    'Salesforce': 8,
                    'The Museum of Modern Art': 9,
                    'Banco Interamericano de Desarrollo': 10,
                    'Yad Vashem': 11,
                    'Google': 12 ,
                    'Microsoft': 13,
                    'Google Cloud': 21,
                    'Salesforce, SV Academy': 22,
                    'HPE Aruba Networking': 23,
                    'Deep Teaching Solutions': 24,
                    'edX': 25,
                    'IBM': 26,
                    'Qualtrics XMI':27,
                    'Intuit': 28,
                    'EIT_Food': 29,
                    'RedHat': 30,
                    'LTTx': 31,
                    'Statistics.com': 32,
                    'Banco Estatal de la India': 33,
                    'AWS': 34,
                    'IIM Bangalore Marketing': 35,
                    'HP': 36,
                    'Xccelerate': 37,
                    'ArmEducation': 38,
                    'LinuxFoundation': 39,
                    'Fundación Raspberry Pi': 40,
                    'Asociación Estadounidense de Psicología': 41,
                    'MindEdge': 42,
                    'NEMIC': 43,
                    'Smithsonian': 44,
                    'Catalyst': 45,
                    'Logyca': 46  
                }
                
                empresa_id = empresa_mapping.get(empresa_nombre)
                print(empresa_id)
                if empresa_id:
                    queryset = queryset.filter(empresa_certificacion = empresa_id)
                    print(queryset)
                
            if 'universidades' in params:
                universidad_nombre = params['universidades']
                # Mapping de universidades para el filtrado
                universidad_mapping = {
                    'Macquarie University': 1,
                    'IE Business School': 2,
                    'Universidad Autónoma de Barcelona': 3,
                    'Universidad Carlos III de Madrid': 4,
                    'Universidad Nacional de Colombia': 5,
                    'University of New Mexico': 6,
                    'University of Michigan': 7,
                    'University of Virginia': 8,
                    'Harvard University': 9,
                    'Yale University': 10,
                    'Universidad Austral': 11,
                    'Universidad de Palermo': 19,
                    'Pontificia Universidad Catolica de Chile': 20,
                    'SAE-México': 21,
                    'Universidad Anáhuac': 22,
                    'Berklee College of Music': 23,
                    'Yad Vashem': 24,
                    'Universidad de los Andes': 25,
                    'UNAM': 26,
                    'Universitat de Barcelona': 28,
                    'Pontificia Universidad Catolica de Peru': 29,
                    'Duke University': 30,
                    'California Institute of Arts': 31,
                    'Wesleyan University': 32,
                    'University of Colorado Boulder': 33,
                    'Northwestern University': 34,
                    'The University of North Carolina at Chapel Hill': 35,
                    'University of California, Irvine': 36,
                    'Tecnológico de Monterrey': 37,
                    'University of Illinois Urbana-Champaign': 38,
                    'Museum of Modern Art': 39,
                    'Parsons School of Design, The New School': 40,
                    'The Chinese University of Hong Kong': 41,
                    'University of Cape Town': 42,
                    'IESE Business School': 43,
                    'Universidad Autónoma Metropolitana': 73,
                    'University of Maryland, College Park': 74,
                    'University of Florida': 75,
                    'Princeton University': 76,
                    'Università di Napoli Federico II': 77,
                    'The State University of New York': 78,
                    'University of Minnesota': 79,
                    'Stanford University': 80,
                    'Columbia University': 81,
                    'University Carlos III of Madrid': 82,
                    'Massachusetts Institute of Technology': 83,
                    'The University of Chicago': 84,
                    'University of Toronto': 85,
                    'Peking University': 86,
                    'Universitat Politècnica de València': 87,
                    'Universidad de Maryland Estados Unidos': 88,
                    'Universidad del Rosario': 89,
                    'Universidad y centro de investigación de Wageningen': 90,
                    'Rochester Institute of Technology': 91,
                    'Universidad de los Estudios de Nápoles Federico II': 92,
                    'New York Institute of Finance': 93,
                    'Universidad de Waseda': 94,
                    'LCI Education': 95,
                    'Universidad Tecnológica de Delft': 96,
                    'Babson College': 97,
                    'Pontificia Universidad Javeriana': 98,
                    'University of California, Davis': 99,
                    'HEC Montreal': 100,
                    'SDG Academy': 101,
                    'University of Maryland, Baltimore County': 102,
                    'Universidad Católica de Lovaina': 103,
                    'Instituto Orfeo': 104,
                    'Universidad de Alaska Fairbanks': 105,
                    'Universidad Nacional de Córdoba': 106,
                    'National University of Singapore': 107,
                    'RWTH Aachen University': 108,
                    'EdimburgoX': 109,
                    'The University of Adelaide': 110,
                    'Universidad Autónoma de Madrid': 111,
                    'Universidad de Tel Aviv': 112,
                    'Universidad Técnica de Múnich': 113,
                    'Davidson College': 114,
                    'Universidad de Maryland': 115,
                    'Academia de Mar X': 116,
                    'Imperial College de Londres': 117,
                    'Universidad Politécnica de Hong Kong': 118,
                    'Universidad Côte d\'Azur': 119,
                    'Universidad de Doane': 120,
                    'Escuela Politécnica Federal de Lausana': 121,
                    'Universidad de Curtin': 122,
                    'Universidad de Washington': 123,
                    'Universidad de Massachusetts Estados Unidos': 124,
                    'Universidad Nacional de Singapur': 125,
                    'Escuela de Negocios Sauder de la UBC': 127,
                    'EdX': 176
                }
                universidad_id = universidad_mapping.get(universidad_nombre)
                if universidad_id:
                    queryset = queryset.filter(universidad_certificacion_id = universidad_id)
                    print(universidad_id)
                else:
                    print("FALLO ID")
        
                
            
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
        
        
@api_view(['GET'])
def latest_certifications(request):
    try:
        page = int(request.GET.get('page', 1))
        page_size = int(request.GET.get('page_size', 16))
        
        # Obtener certificaciones de los últimos 10 días
        limit_date = datetime.now() - timedelta(days=10)
        
        # Obtener y ordenar las certificaciones
        queryset = Certificaciones.objects.filter(
            fecha_creado__gte=limit_date
        ).order_by('-fecha_creado')
        
        # Crear el paginador
        paginator = CustomPagination()
        paginator.page_size = page_size
        
        # Paginar el queryset
        paginated_queryset = paginator.paginate_queryset(queryset, request)
        
        # Serializar los resultados
        serializer = CertificationSerializer(paginated_queryset, many=True)
        
        print(serializer.data)
        
        # Usar el método de paginación personalizada
        return paginator.get_paginated_response(serializer.data)
        
    except Exception as e:
        print(e)
        return Response(
            {'error': f'Error al obtener las certificaciones recientes: {str(e)}'},
            status=status.HTTP_500_INTERNAL_SERVER_ERROR
        )