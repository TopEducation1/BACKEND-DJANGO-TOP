from datetime import datetime, timedelta, timezone
import pandas as pd
import re
from django.shortcuts import render, redirect
from django.contrib import messages
from .forms import *
from django.db import transaction
from rest_framework import viewsets
from .models import *
from .models import Certificaciones
from .serializers import *
from rest_framework.views import APIView
from rest_framework import generics
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
from django.urls import reverse
import os
from collections import defaultdict
from django.db.models import Count


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
            link = reverse("updatePost", args=[post.id])
            messages.success(request, f'Blog <a class="font-bold" href="{link}">{post.nombre_blog}</a> actualizado correctamente.')
            return redirect('posts')
        except Exception as e:
            messages.warning(request,f"{str(e)}")

def deletePost(request,post_id):
    post = Blog.objects.get(id = post_id)
    post.delete()
    messages.success(request, f'Blog eliminado correctamente!')
    return redirect('posts') 

def certifications(request):
    certifications = Certificaciones.objects.select_related('plataforma_certificacion', 'tema_certificacion').all()
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

def categories(request):
    universities = Universidades.objects.all()
    companies = Empresas.objects.all()
    topics = Temas.objects.all()
    cat_blog = CategoriaBlog.objects.all()
    
    return render(request,'category/index.html',{'universities':universities,'companies':companies,'topics':topics,'cat_blog':cat_blog})

def universities(request):
    universities = Universidades.objects.all()
    return render(request,'category/universities/index.html',{'universities':universities})


def updateUniversity(request,university_id):
    if request.method == 'GET':
        university = get_object_or_404(Universidades,pk=university_id)
        form = UniversitiesForm(request.POST or None,request.FILES or None,instance=university)
        return render(request, 'category/universities/update.html',{'university':university,
            'form':form
        })
    else:
        university = get_object_or_404(Universidades, pk=university_id)
        form = UniversitiesForm(request.POST or None,request.FILES or None, instance=university)
        form.save()
        messages.success(request, f'Universidad actualizada correctamente!')
        return redirect('universities')

def companies(request):
    companies = Empresas.objects.all()
    return render(request,'category/companies/index.html',{'companies':companies})

def updateCompany(request,company_id):
    if request.method == 'GET':
        company = get_object_or_404(Empresas,pk=company_id)
        form = CompaniesForm(request.POST or None,request.FILES or None,instance=company)
        return render(request, 'category/companies/update.html',{'company':company,
            'form':form
        })
    else:
        company = get_object_or_404(Empresas, pk=company_id)
        form = CompaniesForm(request.POST or None,request.FILES or None, instance=company)
        form.save()
        messages.success(request, f'Empresa actualizada correctamente!')
        return redirect('companies')

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

    def get(self, request):
        search_query = request.query_params.get('search', '')
        categoria_nombre = request.query_params.get('categoria_blog', '')

        blogs_queryset = Blog.objects.select_related('autor_blog', 'categoria_blog').all()

        if search_query:
            blogs_queryset = blogs_queryset.filter(
                Q(nombre_blog__icontains=search_query)
            )

        if categoria_nombre:
            try:
                categoria = CategoriaBlog.objects.get(nombre_categoria_blog__iexact=categoria_nombre)
                blogs_queryset = blogs_queryset.filter(categoria_blog=categoria)
            except CategoriaBlog.DoesNotExist:
                blogs_queryset = Blog.objects.none()

        paginator = self.pagination_class()
        paginated_queryset = paginator.paginate_queryset(blogs_queryset, request)
        serializer = BlogSerializer(paginated_queryset, many=True, context={'request': request})

        return paginator.get_paginated_response(serializer.data)


# EndPoint to get the certifications
class CertificationList(APIView):
    
    pagination_class = CustomPagination
    
    # DEFINIR EL METODO GET QUE SE REALIZA DESDE EL FRONT    
    def get(self, request):

        # Queryset de las certificaciones
        certifications_queryset = Certificaciones.objects.all().select_related(
            'tema_certificacion',
            'plataforma_certificacion'
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
        
        universities = Universidades.objects.annotate(
            total_certificaciones=Count('certificaciones')
        )
        #Queryset of the Universities
        
        #universities = Universidades.objects.all()
        universities_serializer = UniverisitiesSerializer(universities, many= True)
        
        return Response(universities_serializer.data)


class TopicsList (APIView):
    
    def get(self, request):
        
        #Queryset of the Topics
        topics =  Temas.objects.all()
        topics_serializer = TopicsSerializer(topics, many = True)
        
        return Response(topics_serializer.data)

class PlatformsList (APIView):
    
    def get(self, request):
        
        #Queryset of the Platforms
        platforms =  Plataformas.objects.all()
        platforms_serializer = PlataformaSerializer(platforms, many = True)
        
        return Response(platforms_serializer.data)

class CompaniesList (APIView):
    
    def get(self, request):
        
        companies = Empresas.objects.annotate(
            total_certificaciones=Count('certificaciones')
        )
        
        #Queryset of the Companies
        #companies =  Empresas.objects.all()
        companies_serializer = EmpresaSerializer(companies, many = True)
        
        return Response(companies_serializer.data)  


class UniversitiesByRegion(APIView):
    def get(self, request):
        universities = Universidades.objects.select_related('region_universidad').filter(univ_est="enabled")
        grouped = defaultdict(list)

        for uni in universities:
            region_name = uni.region_universidad.nombre if uni.region_universidad else "Sin región"
            grouped[region_name].append({
                'id': uni.id,
                'nombre': uni.nombre,
                'univ_img': uni.univ_ico if uni.univ_ico else uni.univ_img,
            })

        return Response(grouped)


class BlogDetailView(APIView):
    
    def get(self, request, slug):
        try:
            if not slug:
                return Response(
                    {'Error': 'Se requiere el nombre de el blog'},
                    status=status.HTTP_400_BAD_REQUEST
                )
                
            blog = Blog.objects.get(slug = slug)
            
            serializer = BlogSerializer(blog, context={'request': request})

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
            params = request.query_params.copy()
            page = params.pop('page', ['1'])[0]
            page_size = params.pop('page_size', ['12'])[0]

            queryset = Certificaciones.objects.all().order_by('id')

            field_mapping = {
                'plataforma': 'plataforma_certificacion__nombre__iexact',
                'empresas': 'empresa_certificacion__nombre__iexact',
                'universidades': 'universidad_certificacion__nombre__iexact',
                'temas': 'tema_certificacion__nombre__iexact',
                'habilidades': 'tema_certificacion__nombre__iexact',
            }

            for key, value_list in params.lists():
                if key in field_mapping:
                    field_name = field_mapping[key]
                    q_objects = Q()
                    for value in value_list:
                        print(f"DEBUG: key={key}, raw value={value} (type={type(value)})")
                        if value is None:
                            print("DEBUG: value is None, skipping")
                            continue
                        if not isinstance(value, str):
                            print("DEBUG: value is not string, skipping")
                            continue
                        # Aquí ocurre el split y strip
                        split_values = value.split(',') if value else []
                        for val in split_values:
                            print(f"DEBUG: val before strip: {val} (type={type(val)})")
                            if val is None:
                                print("DEBUG: val is None, skipping")
                                continue
                            cleaned_val = val.strip()
                            print(f"DEBUG: cleaned_val: '{cleaned_val}'")
                            if cleaned_val:
                                q_objects |= Q(**{field_name: cleaned_val})
                    if q_objects:
                        queryset = queryset.filter(q_objects)

            paginator = self.pagination_class()
            paginated_queryset = paginator.paginate_queryset(queryset, request)
            serializer = CertificationSerializer(paginated_queryset, many=True)

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

class LatestCertificationsView(APIView):
    def get(self, request):
        try:
            certifications = Certificaciones.objects.all().order_by('-fecha_creado_cert')[:32]
            serializer = CertificationSerializer(certifications, many=True)
            return Response(serializer.data)
        except Exception as e:
            import traceback
            print("🔥 Error en LatestCertificationsView:", e)
            traceback.print_exc()
            return Response({'error': str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)




class OriginalDetailView(APIView):
    def get(self, request, slug):
        try:
            original = Original.objects.get(slug=slug)
        except Original.DoesNotExist:
            return Response({"detail": "No encontrado"}, status=status.HTTP_404_NOT_FOUND)

        serializer = OriginalSerializer(
            original,
            context={'request': request}   # <–– aquí el context
        )
        return Response(serializer.data)

