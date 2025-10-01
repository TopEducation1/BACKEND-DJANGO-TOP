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
from django.forms import modelformset_factory
import os
from collections import defaultdict
from django.db.models import Count
from django.db.models import Prefetch

from django.http import JsonResponse, HttpResponseBadRequest, HttpResponseForbidden
from django.views.decorators.http import require_GET
import requests
from urllib.parse import urlparse, urlencode, parse_qsl, urlunparse


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

def updatePost(request, post_id):
    post = get_object_or_404(Blog, pk=post_id)

    if request.method == "POST":
        form = BlogsForm(request.POST, request.FILES, instance=post)
        if form.is_valid():
            form.save()
            link = reverse("updatePost", args=[post.id])
            messages.success(
                request,
                f'Blog <a class="font-bold" href="{link}">{post.nombre_blog}</a> actualizado correctamente.'
            )
            return redirect('posts')
        else:
            # Útil para depurar si algo invalida el form (incluida la imagen)
            # print("FORM ERRORS:", form.errors.as_json())
            messages.error(request, "Hay errores en el formulario. Revísalos abajo.")
    else:
        form = BlogsForm(instance=post)

    return render(request, "posts/update.html", {"post": post, "form": form})


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
    originals = Original.objects.all()
    rankings = Ranking.objects.all()
    
    return render(request,'category/index.html',{'universities':universities,'companies':companies,'topics':topics,'cat_blog':cat_blog,'originals':originals,'rankings':rankings})

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
        link = reverse("updateUniversity", args=[university.id])
        messages.success(request, f'Universidad: <a class="font-bold" href="{link}">{university.nombre}</a> actualizada correctamente')
        return redirect('universities')

def createUniversity(request):
    if request.method == 'GET':
        return render(request, 'category/universities/create.html',{
            'form':UniversitiesForm
        })
    else:
        try:
            form = UniversitiesForm(request.POST)
            new_post = form.save(commit=False)
            created  = new_post.save()
            messages.success(request, f'Universidad: Guardada correctamente')
            return redirect('universities')
        except Exception as e:
            messages.warning(request,f"{str(e)}")

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

def createCompany(request):
    if request.method == 'GET':
        return render(request, 'category/companies/create.html',{
            'form':CompaniesForm
        })
    else:
        try:
            form = CompaniesForm(request.POST)
            new_post = form.save(commit=False)
            created  = new_post.save()
            messages.success(request, f'Empresa: Guardada correctamente')
            return redirect('companies')
        except Exception as e:
            messages.warning(request,f"{str(e)}")

def topics(request):
    topics = Temas.objects.all()
    return render(request,'category/topics/index.html',{'topics':topics})

def updateTopic(request,topic_id):
    if request.method == 'GET':
        topic = get_object_or_404(Temas,pk=topic_id)
        form = TopicsForm(request.POST or None,request.FILES or None,instance=topic)
        return render(request, 'category/topics/update.html',{'topic':topic,
            'form':form
        })
    else:
        topic = get_object_or_404(Temas, pk=topic_id)
        form = TopicsForm(request.POST or None,request.FILES or None, instance=topic)
        form.save()
        messages.success(request, f'Habilidad/Tema actualizada correctamente!')
        return redirect('topics')

def createTopic(request):
    if request.method == 'GET':
        return render(request, 'category/topics/create.html',{
            'form':TopicsForm
        })
    else:
        try:
            form = TopicsForm(request.POST)
            new_post = form.save(commit=False)
            created  = new_post.save()
            messages.success(request, f'Tema / Habilidad: Guardado correctamente')
            return redirect('topics')
        except Exception as e:
            messages.warning(request,f"{str(e)}")

def tags(request):
    tags = CategoriaBlog.objects.all()
    return render(request,'category/tags/index.html',{'tags':tags})


def updateTag(request,tag_id):
    if request.method == 'GET':
        tag = get_object_or_404(CategoriaBlog,pk=tag_id)
        form = TagsForm(request.POST or None,request.FILES or None,instance=tag)
        return render(request, 'category/tags/update.html',{'tag':tag,
            'form':form
        })
    else:
        tag = get_object_or_404(CategoriaBlog, pk=tag_id)
        form = TagsForm(request.POST or None,request.FILES or None, instance=tag)
        form.save()
        messages.success(request, f'Categoria de blog actualizada correctamente!')
        return redirect('tags')

def createTag(request):
    if request.method == 'GET':
        return render(request, 'category/tags/create.html',{
            'form':TagsForm
        })
    else:
        try:
            form = TagsForm(request.POST)
            new_post = form.save(commit=False)
            created  = new_post.save()
            messages.success(request, f'Categoria de blog: Creada correctamente')
            return redirect('tags')
        except Exception as e:
            messages.warning(request,f"{str(e)}")

def originals(request):
    originals = Original.objects.all()
    return render(request,'category/originals/index.html',{'originals':originals})

def createOriginal(request):
    if request.method == 'POST':
        original_form = OriginalsForm(request.POST)
        formset = OriginalCertFormSet(request.POST, prefix='certifications')

        print("TOTAL FORMS:", request.POST.get('certifications-TOTAL_FORMS'))
        print("formset errors:", formset.errors)
        
        if original_form.is_valid() and formset.is_valid():
            original = original_form.save()
            certifications = formset.save(commit=False)
            for certification in certifications:
                certification.original = original
                certification.save()
            messages.success(request, f'Original: Creado correctamente')
            return redirect('updateOriginal', original_id=original.id)
    else:
        original_form = OriginalsForm()
        formset = OriginalCertFormSet(prefix='certifications')

    return render(request, 'category/originals/create.html', {
        'original_form': original_form,
        'formset': formset,
    })

def updateOriginal(request, original_id):
    original = get_object_or_404(Original, id=original_id)

    if request.method == 'POST':
        original_form = OriginalsForm(request.POST,request.FILES, instance=original)
        formset = OriginalCertFormSet(request.POST,request.FILES, instance=original, prefix='certifications')

        if original_form.is_valid() and formset.is_valid():
            original_form.save()
            formset.save()  # aplica altas, bajas y modificaciones
            link = reverse("updateOriginal", args=[original.id])
            messages.success(request, f'Original: <a class="font-bold" href="{link}">{original.name}</a> Actualizado correctamente')
            return redirect('originals')
        else:
            print("Errores en form:", original_form.errors)
            print("Errores en formset:", formset.errors)
    else:
        original_form = OriginalsForm(instance=original)
        formset = OriginalCertFormSet(instance=original, prefix='certifications')

    return render(request, 'category/originals/update.html', {
        'original_form': original_form,
        'formset': formset,
        'original': original,
    })

def rankings(request):
    rankings = Ranking.objects.all()
    return render(request,'category/rankings/index.html',{'rankings':rankings})

def createRanking(request):
    if request.method == 'POST':
        ranking_form = RankingsForm(request.POST)
        formset = RankingEntryFormSet(request.POST, prefix='entries')

        print("TOTAL FORMS:", request.POST.get('entries-TOTAL_FORMS'))
        print("formset errors:", formset.errors)
        
        if ranking_form.is_valid() and formset.is_valid():
            ranking = ranking_form.save()
            entries = formset.save(commit=False)
            for entry in entries:
                entry.ranking = ranking
                entry.save()
            messages.success(request, f'Ranking: Creado correctamente')
            return redirect('updateRanking', ranking_id=ranking.id)
    else:
        ranking_form = RankingsForm()
        formset = RankingEntryFormSet(prefix='entries')

    return render(request, 'category/rankings/create.html', {
        'ranking_form': ranking_form,
        'formset': formset,
    })

def updateRanking(request, ranking_id):
    ranking = get_object_or_404(Ranking, id=ranking_id)
    prefix = 'entries'

    if request.method == 'POST':
        ranking_form = RankingsForm(request.POST, request.FILES, instance=ranking)
        formset = RankingEntryFormSet(request.POST, request.FILES, instance=ranking, prefix=prefix)

        if ranking_form.is_valid() and formset.is_valid():
            with transaction.atomic():
                ranking = ranking_form.save()
                formset.save()  # aplica altas, bajas y modificaciones
            link = reverse("updateRanking", args=[ranking.id])
            messages.success(request, f'Ranking: <a class="font-bold underline" href="{link}">{ranking.nombre}</a> actualizado correctamente')
            return redirect('rankings')
        else:
            # Debug opcional
            print("Errores ranking_form:", ranking_form.errors)
            print("Errores formset (forms):", [f.errors for f in formset.forms])
            print("Errores formset (no form):", formset.non_form_errors())
    else:
        ranking_form = RankingsForm(instance=ranking)
        formset = RankingEntryFormSet(instance=ranking, prefix=prefix)

    return render(request, 'category/rankings/update.html', {
        'ranking_form': ranking_form,
        'formset': formset,
        'ranking': ranking,
        'prefix': prefix,
    })



def catalog_inspector(request):
    """
    Vista para inspeccionar recursos del nuevo API.
    Permite elegir el recurso (certifications, topics, etc.) y probar parámetros.
    """
    base_url = "https://rgudwgvtgk.execute-api.us-east-1.amazonaws.com/raul/course-information"
    # recurso por defecto
    default_resource = request.GET.get("resource", "certifications")

    return render(
        request,
        "catalog_inspector.html",
        {
            "base_url": base_url,
            "resource": default_resource,
            "resources": [
                "certifications",
                "topics",
                "companies",
                "universities",
                "platforms",
                "regions",
            ],
        },
    )

@require_GET
def proxy_json(request):
    """
    Proxy seguro (GET) con whitelist por host.
    Acepta ?url=https://... y reencadena el resto de params (?q, ?page, etc.)
    """
    raw_url = request.GET.get("url", "").strip()
    if not raw_url:
        return HttpResponseBadRequest("Missing 'url' param.")

    parsed = urlparse(raw_url)
    if parsed.scheme not in ("http", "https"):
        return HttpResponseBadRequest("Invalid scheme. Only http/https allowed.")

    host = parsed.netloc
    if host not in getattr(settings, "PROXY_WHITELIST", set()):
        return HttpResponseForbidden("Upstream host not allowed.")

    # Combinar query original + params del cliente (excepto 'url')
    upstream_qs = dict(parse_qsl(parsed.query, keep_blank_values=True))
    for k in request.GET.keys():
        if k == "url":
            continue
        vals = request.GET.getlist(k)
        upstream_qs[k] = vals if len(vals) > 1 else vals[0]

    final_query = urlencode(upstream_qs, doseq=True)
    final_url = urlunparse(parsed._replace(query=final_query))

    headers = {"Accept": "application/json"}
    headers.update(getattr(settings, "PROXY_HEADERS", {}).get(host, {}))

    try:
        resp = requests.get(final_url, headers=headers, timeout=getattr(settings, "PROXY_TIMEOUT", 15))
    except requests.RequestException as e:
        return JsonResponse({"error": "upstream_unreachable", "detail": str(e)}, status=502)

    if resp.status_code >= 400:
        return JsonResponse({"error": "upstream_error", "status": resp.status_code, "url": final_url}, status=502)

    try:
        data = resp.json()
    except ValueError:
        return JsonResponse({"error": "invalid_json_from_upstream"}, status=502)

    return JsonResponse(data, safe=not isinstance(data, list))



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
        categorias_param = request.query_params.get('categoria_blog', '')

        blogs_queryset = Blog.objects.select_related('autor_blog', 'categoria_blog').all()

        if search_query:
            blogs_queryset = blogs_queryset.filter(
                Q(nombre_blog__icontains=search_query)
            )

        if categorias_param:
            # Dividir por coma y limpiar espacios
            categorias = [c.strip() for c in categorias_param.split(',') if c.strip()]
            
            # Obtener las categorías que existen en base a nombre
            categorias_objs = CategoriaBlog.objects.filter(
                nombre_categoria_blog__in=categorias
            )

            if categorias_objs.exists():
                blogs_queryset = blogs_queryset.filter(categoria_blog__in=categorias_objs)
            else:
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

class OriginalsList (APIView):
    
    def get(self, request):
        
        #Queryset of the Platforms
        originals =  Original.objects.all().filter(esta="enabled")
        originals_serializer = OriginalSerializer(originals, many = True, context={'request': request})
        
        return Response(originals_serializer.data) 

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
    def post(self, request):
        query_string = request.data.get('data', "").strip()
        if not query_string or len(query_string) < 2:
            return Response([], status=200)

        try:
            filtered_results = Certificaciones.objects.filter(
                Q(nombre__icontains=query_string) |
                Q(tema_certificacion__nombre__icontains=query_string) |
                Q(universidad_certificacion__nombre__icontains=query_string) |
                Q(empresa_certificacion__nombre__icontains=query_string)
            ).distinct()

            print("Resultados encontrados:", filtered_results.count())

        except Exception as e:
            print("Error en la consulta:", e)
            return Response({"error": str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

        # Si el queryset está vacío, devolvemos una lista vacía sin serializar
        if not filtered_results.exists():
            return Response([], status=status.HTTP_200_OK)

        serializer = CertificationSearchSerializer(filtered_results, many=True)
        return Response(serializer.data, status=status.HTTP_200_OK)

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
            original = Original.objects.filter(esta="enabled").prefetch_related(
                Prefetch(
                    'certifications',  # o 'certifications' si tienes related_name
                    queryset=OriginalCertification.objects.all().order_by('posicion')
                )
            ).get(slug=slug)

        except Original.DoesNotExist:
            return Response({"detail": "No encontrado"}, status=status.HTTP_404_NOT_FOUND)

        serializer = OriginalSerializer(
            original,
            context={'request': request}   # <–– aquí el context
        )
        return Response(serializer.data)

class RankingsList (APIView):
    
    def get(self, request):
        
        #Queryset of the Platforms
        rankings =  Ranking.objects.all().filter(estado="enabled")
        rankings_serializer = RankingSerializer(rankings, many = True, context={'request': request})
        
        return Response(rankings_serializer.data) 

class RankingDetailView(APIView):
    def get(self, request, slug):
        try:
            ranking = Ranking.objects.get(nombre__iexact=slug.replace('-', ' '))
        except Ranking.DoesNotExist:
            return Response({"detail": "No encontrado"}, status=status.HTTP_404_NOT_FOUND)

        # Obtenemos las entradas del ranking
        entradas = ranking.entradas.select_related('universidad', 'empresa').all()

        # Agregamos las certificaciones por tema para cada entrada
        for entrada in entradas:
            if entrada.universidad:
                temas = entrada.universidad.certificaciones.values(
                    'tema_certificacion__id',
                    'tema_certificacion__nombre',
                    'tema_certificacion__tem_type',
                    'tema_certificacion__tem_img'
                ).annotate(total_certificaciones=Count('id'))
                entrada.temas_certificaciones = list(temas)
            elif entrada.empresa:
                temas = entrada.empresa.certificaciones.values(
                    'tema_certificacion__id',
                    'tema_certificacion__nombre',
                    'tema_certificacion__tem_type',
                    'tema_certificacion__tem_img'
                ).annotate(total_certificaciones=Count('id'))
                entrada.temas_certificaciones = list(temas)
            else:
                entrada.temas_certificaciones = []

        serializer = RankingSerializer(
            ranking,
            context={'request': request}
        )
        # Adjuntamos manualmente los datos de temas_certificaciones
        data = serializer.data
        for idx, entrada in enumerate(entradas):
            data['entradas'][idx]['temas_certificaciones'] = entrada.temas_certificaciones

        return Response(data)
