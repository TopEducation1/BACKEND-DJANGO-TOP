from datetime import datetime, timedelta, timezone
import pandas as pd
import re
from django.shortcuts import render, redirect
from django.contrib import messages
from .forms import UploadFileForm
from .forms import CertificationsForm
from .forms import BlogsForm
from django.db import transaction
from rest_framework import viewsets
from .models import *
from .models import Certificaciones
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
from django.http import HttpResponse
from django.contrib.auth.forms import UserCreationForm, AuthenticationForm
from django.contrib.auth import login, logout, authenticate
from django.http import FileResponse, Http404
from django.conf import settings
import os


def inicio(request):
    return HttpResponse("<h1>Bienvenido a Top.Education</h1>")

def dashboard(request):
    certifications = Certificaciones.objects.all()
    edx = Certificaciones.objects.filter(plataforma_certificacion=1)
    coursera = Certificaciones.objects.filter(plataforma_certificacion=2)
    masterclass = Certificaciones.objects.filter(plataforma_certificacion=3)
    posts = Blog.objects.all()
    return render(request,'pages/dashboard.html',{'certifications':certifications,'edx':edx,'coursera':coursera,'masterclass':masterclass,'posts':posts})

def signout(request):
    logout(request)
    return redirect('signin')

def signin(request):
    if request.method == 'GET':
        return render(request,'pages/signin.html',{
            'form':AuthenticationForm
        })
    else:
        user = authenticate(request, username = request.POST['username'], password=request.POST['password'])
        if user is None:
            return render(request,'pages/signin.html',{
                'form':AuthenticationForm, 
                'error': 'Usuario o password es incorrecto'
            })
        else:
            login(request, user)
            return redirect('dashboard')

def posts(request):
    posts = Blog.objects.all()
    print(posts)
    return render(request,'posts/index.html',{'posts':posts})

def createPost(request):
    if request.method == 'GET':
        return render(request, 'posts/create.html',{
            'form':BlogsForm
        })
    else:
        try:
            form = BlogsForm(request.POST)
            new_post = form.save(commit=False)
            created  = new_post.save()
            messages.success(request, f'Blog: publicada correctamente')
            return redirect('posts')
        except Exception as e:
            messages.warning(request,f"{str(e)}")

def updatePost(request,post_id):
    if request.method == 'GET':
        
        post = get_object_or_404(Blog,pk=post_id)
        form = BlogsForm(request.POST or None, request.FILES or None, instance=post)
        return render(request, 'posts/update.html',{'post':post,
            'form':form
        })
    else:
        try:
            post = get_object_or_404(Blog, pk=post_id)
            form = BlogsForm(request.POST or None,request.FILES or None, instance=post)
            form.save()
            messages.success(request,f"Blog actualizado correctamente")
            return redirect('posts')
        except Exception as e:
            messages.warning(request,f"{str(e)}")

def deletePost(request,post_id):
    post = Blog.objects.get(id = post_id)
    post.delete()
    messages.success(request, f'Blog eliminado correctamente!')
    return redirect('posts') 

def certifications(request):
    certifications = Certificaciones.objects.all()
    return render(request,'certifications/index.html',{'certifications':certifications})

def createCertification(request):
    if request.method == 'GET':
        return render(request, 'certifications/create.html',{
            'form':CertificationsForm
        })
    else:
        try:
            form = CertificationsForm(request.POST)
            new_certification = form.save(commit=False)
            created  = new_certification.save()
            messages.success(request, f'Certificación: publicada correctamente')
            return redirect('certifications')
        except Exception as e:
            messages.warning(request,f"{str(e)}")

def updateCertification(request,certification_id):
    if request.method == 'GET':
        certification = get_object_or_404(Certificaciones,pk=certification_id)
        form = CertificationsForm(request.POST or None,request.FILES or None,instance=certification)
        return render(request, 'certifications/update.html',{'certification':certification,
            'form':form
        })
    else:
        certification = get_object_or_404(Certificaciones, pk=certification_id)
        form = CertificationsForm(request.POST or None,request.FILES or None, instance=certification)
        form.save()
        messages.success(request, f'Certificacion actualizada correctamente!')
        return redirect('certifications')

def upload(request):
    if request.method == "POST":
        plataforma = request.POST.get("plataforma")
        excel_file = request.FILES["file-upload"]
        file_data = pd.read_excel(excel_file)
        if plataforma == "1":
            print(f'Plataforma es EdX')
        if plataforma == "2":
            print(f'Plataforma es Coursera')
        if plataforma == "3":
            print(f'Plataforma es MasterClass')
        #file_data.to_csv('C:/Users/andre/OneDrive/Documentos/GitHub/BACKEND-DJANGO-TOP/topeducation/templates/test.csv')
        print(file_data.head())
        file_data.columns = file_data.columns.str.strip()
        error =''
        alert = ''
        auxE = 0
        auxA = 0
        auxR = 0
        print("Columnas en el DataFrame después de limpiar:")
        for col in file_data.columns:
            print(f"-> {col}")
        for index, row in file_data.iterrows():
            try:
                with transaction.atomic():
                    print(f"\nProcesando fila {index + 2}:")
                    
                    #AUTOMATIZACIÓN PARA CARGAR DATOS DE LAS DIFERENTES PLATAFORMAS
                    if plataforma == "3":
                        imagen_final = row['Imagen']
                        video = row['Video']
                        nivel = "None"
                        modulos = "None"
                        idioma = "None"
                        habilidades = "None"
                        enterprise_id = 0
                        university_id = 0
                        descripcion_testimonios = row['Descripción']
                        contenido = row['Lecciones']
                        experiencia_acercade= row['Acerca de']
                    else:
                        imagen_final = None
                        video = None
                        nivel = row['Nivel']
                        modulos = row['Modulos']
                        idioma = row['Idioma']
                        habilidades = row['Habilidades']
                        enterprise_id = row['Empresa']
                        university_id = row['Universidad']
                        descripcion_testimonios = row['Testimonios']
                        contenido = row['Contenido']
                        experiencia_acercade= row['Experiencia']

                    topic_id = row['Tema/Habilidad']
                    certification_tema = Temas.objects.get(id=topic_id)

                    platform_id = row['Plataforma']
                    certification_platform = Plataformas.objects.get(id=platform_id)
                    
                    
                    if enterprise_id == 0:
                        certification_enterprise = None
                    else:
                        certification_enterprise = Empresas.objects.get(id=enterprise_id)
                    
                    
                    if university_id == 0:
                        certification_university = None
                    else:
                        certification_university = Universidades.objects.get(id=university_id)
                    
                    # Crear la certificación con los campos correctos del modelo
                    created = Certificaciones.objects.get_or_create(
                        nombre=row['Titulo'],
                        slug=row['Slug'].lower(),
                        tema_certificacion=certification_tema,
                        palabra_clave_certificacion=row['KW'],
                        plataforma_certificacion=certification_platform,
                        url_certificacion_original=row['Link'],
                        metadescripcion_certificacion=row['Meta D'],
                        instructores_certificacion=row['Instructor/es'],
                        nivel_certificacion=nivel,
                        tiempo_certificacion=row['Tiempo'],
                        lenguaje_certificacion=idioma,
                        aprendizaje_certificacion=row['Aprendizaje'],
                        habilidades_certificacion=habilidades,
                        experiencia_certificacion=experiencia_acercade,
                        contenido_certificacion=contenido,
                        modulos_certificacion=modulos,
                        testimonios_certificacion=descripcion_testimonios,
                        universidad_certificacion=certification_university,
                        empresa_certificacion=certification_enterprise,
                        imagen_final=imagen_final,
                        video_certificacion = video,
                    )
                    
                    if created:
                        auxA += 1
                    else:
                        messages.warning(request, f' R{index + 2}: Certificación que ya existe')
                        auxR += 1
            except KeyError as e:
                messages.warning(request, f"Error de columna en fila {index + 2}: {str(e)}")
                auxE += 1

            except Exception as e:
                messages.warning(request,f"Error al procesar fila {index + 2}: {str(e)}")
                auxE += 1

        if auxE>0:
            messages.warning(request, f"{auxE}: Certificaciones con error al importar")
        if auxA>0:
            messages.success(request, f'{auxA}: Certificaciones importadas correctamente!')
        print('Proceso de importación completado')
        return render(request,'certifications/upload.html',{'error':error,'alert':alert})
    return render(request,'certifications/upload.html')

def deleteCertification(request,certification_id):
    certification = Certificaciones.objects.get(pk = certification_id)
    certification.delete()
    messages.success(request, f'Certificación eliminada correctamente!')
    return redirect('certifications') 


def descargar_excel(request, nombre_archivo):
    ruta_base = os.path.join(settings.BASE_DIR, 'documents')
    ruta_archivo = os.path.join(ruta_base, nombre_archivo)

    if os.path.exists(ruta_archivo):
        return FileResponse(open(ruta_archivo, 'rb'), as_attachment=True, filename=nombre_archivo)
    else:
        raise Http404("Archivo no encontrado")

def error_404(request):
    raise Http404('Página no encontrada')

def get_certifications(request):
    certifications = Certificaciones.objects.values('slug')
    return JsonResponse(list(certifications), safe=False)

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


#Api config to get the blogs
class BlogList(APIView):
    
    pagination_class = CustomPagination
    
    #GET METHOD REQUESTED BY THE FRONT
    
    def get(self, request):
        
        blogs_queryset = Blog.objects.all()
        paginator = self.pagination_class()
        paginated_queryset = paginator.paginate_queryset(blogs_queryset, request)
        serializer = BlogSerializer(paginated_queryset, many = True)
        
        return paginator.get_paginated_response(serializer.data)


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
    
    
#This view is to send the Masterclass certifications to display a masterclasss slider in frontend    
class MasterclassCertificationsGrids(APIView):
    
    def get(self, request):
        
        amount = int(request.query_params.get('amount', 3))
        
        masterclass_certifications_queryset = Certificaciones.objects.filter(plataforma_certificacion_id = 3)[:amount]
        
        serializer = CertificationSerializer(masterclass_certifications_queryset, many = True)
        
        return Response (serializer.data, status=status.HTTP_200_OK)     




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

class CategoriesList (APIView):
    def get(self,request):
        categories = CategoriaBlog.objects.all()
        categories_serializer = CategoriesSerializer(categories, many= True)
        return Response(CategoriesSerializer.data)

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
    

class BlogDetailView(APIView):
    
    def get(self, request, slug):
        try:
            if not slug:
                return Response(
                    {'Error': 'Se requiere el nombre de el blog'},
                    status=status.HTTP_400_BAD_REQUEST
                )
                
            blog = Blog.objects.get(slug = slug)
            
            serializer = BlogSerializer(blog)
            data = serializer.data
            
            return Response(data)
        
        except Certificaciones.DoesNotExist:
            
            return Response(
                {'error': 'Blog no encontrado'},
                status=status.HTTP_404_NOT_FOUND
            )
            
        except ValueError:
            return Response(
                {'error': 'Nombre invalido'},
                status=status.HTTP_400_BAD_REQUEST
            ) 

# Esta función obtiene el id de la certificación que el usuario quiere ver en vista especifica y retorna toda su información
class CertificationDetailView(APIView):
    def get(self, request, slug):
        try:
            if not slug:
                return Response(
                    {'Error': 'Se requiere el nombre de la certificación'},
                    status=status.HTTP_400_BAD_REQUEST
                )
            
            # Obtener la certificación   
            certification = Certificaciones.objects.get(slug=slug)
            
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
                
                empresa_nombre = params['empresas'].strip()
                print(f"EMPRESA RECIBIDA{empresa_nombre}")
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
                    'Google': 12,
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
                    'Stanford University': 128,
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
                    'Universidad de Washington': 171,
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
                'habilidades': 'tema_certificacion__nombre'
            }           
            
            # Aplicar filtros
            for param, values in params.items():
                if param in field_mapping and param != 'plataforma':
                    field_name = field_mapping[param]
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