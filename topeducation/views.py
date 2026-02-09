from __future__ import annotations

from topeducation.inspectors.courses_inspector import fetch_and_parse_page
from topeducation.models import ExternalSyncState

from datetime import datetime, timedelta, timezone
import pandas as pd
import re
import time
import traceback
import logging

from django.contrib.admin.views.decorators import staff_member_required

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
from rest_framework.decorators import api_view
import json
from django.views.decorators.http import require_http_methods
from django.shortcuts import get_object_or_404
from django.db.models import Q
from django.core.paginator import EmptyPage, PageNotAnInteger
from django.core.paginator import Paginator
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
import requests
from urllib.parse import urlparse, urlencode, parse_qsl, urlunparse

from rest_framework import generics, permissions as drf_permissions
from .models import Marca
from .serializers import MarcaSerializer

from django.contrib.auth.decorators import login_required, user_passes_test
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.db import transaction

from .models import Marca, MarcaPermisos
from .forms import MarcaForm, MarcaPermisosFormSet
from .serializers import MarcaPublicSerializer


from topeducation.services.import_courses import ingest_course_payload

from django.contrib.auth.decorators import login_required
import stripe
from django.contrib.auth import get_user_model
from .models import UserBillingProfile, StripeSubscription, StripePurchase


from django.views.decorators.http import require_POST, require_GET
from django.views.decorators.csrf import ensure_csrf_cookie

from django.contrib.auth.models import User
from django.middleware.csrf import get_token

from .utils.auth import api_login_required


from django.contrib.auth.tokens import default_token_generator
from django.core.mail import send_mail
from django.utils.encoding import force_bytes, force_str
from django.utils.http import urlsafe_base64_encode, urlsafe_base64_decode

from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import AllowAny

import json, time, uuid, traceback

from django.utils import timezone
from datetime import timedelta

from topeducation.services.import_courses import ingest_course_payload


@staff_member_required(login_url="/signin/")
def admin_purchases_page(request):
    # opcional: si quieres solo staff
    if not request.user.is_staff:
        # puedes renderizar un 403 bonito o redirigir
        return render(request, "404.html", status=403)

    return render(request, "bussines/purchases.html", {})

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

    # ✅ Headers upstream
    headers = {"Accept": "application/json"}

    # 1) headers fijos desde settings (por host)
    headers.update(getattr(settings, "PROXY_HEADERS", {}).get(host, {}))

    # 2) ✅ reenviar x-api-key del navegador si viene (case-insensitive)
    api_key = request.headers.get("x-api-key") or request.META.get("HTTP_X_API_KEY")
    if api_key:
        headers["x-api-key"] = api_key

    try:
        resp = requests.get(final_url, headers=headers, timeout=getattr(settings, "PROXY_TIMEOUT", 20))
    except requests.RequestException as e:
        return JsonResponse({"error": "upstream_unreachable", "detail": str(e)}, status=502)

    # si upstream devuelve error real, pásalo tal cual
    if resp.status_code >= 400:
        return JsonResponse(
            {"error": "upstream_error", "status": resp.status_code, "url": final_url, "response": resp.text},
            status=502
        )

    try:
        data = resp.json()
    except ValueError:
        return JsonResponse({"error": "invalid_json_from_upstream", "response": resp.text[:4000]}, status=502)

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



def staff_required(view_func):
    return login_required(user_passes_test(lambda u: u.is_staff)(view_func))


# ------ 1) LISTAR MARCAS ------

@staff_required
def brand_list(request):
    marcas = Marca.objects.all().order_by("-id")
    return render(request, "brand/index.html", {"marcas": marcas})


# ------ 2) CREAR / EDITAR MARCA ------

@staff_required
@transaction.atomic
def brand_update(request, marca_id=None):
    if marca_id:
        marca = get_object_or_404(Marca, pk=marca_id)
    else:
        marca = None

    if request.method == "POST":
        form = MarcaForm(request.POST, request.FILES, instance=marca)
        if form.is_valid():
            marca = form.save()
            return redirect("brand_settings", marca_id=marca.id)
    else:
        form = MarcaForm(instance=marca)

    return render(
        request,
        "brand/form.html",
        {
            "form": form,
            "marca": marca,
        },
    )


# ------ 3) CONFIGURAR PERMISOS/SECCIONES POR MARCA ------

DEFAULT_SECTIONS = [
    ("about_us", "Sección About us"),
    ("explora", "Sección Explora"),
    ("los_mas_top", "Sección Los más top"),
    ("blog", "Sección Blog"),
    ("habilidades", "Sección Habilidades"),
    ("temas", "Sección Temas"),
]


@staff_required
@transaction.atomic
def brand_settings(request, marca_id):
    marca = get_object_or_404(Marca, pk=marca_id)

    # Si NO hay permisos, crear los iniciales en memoria (solo para el formset inicial)
    if request.method == "GET" and not marca.permisos.exists():
        for index, (key, _) in enumerate(DEFAULT_SECTIONS, start=1):
            # se crean en DB para simplificar el manejo
            MarcaPermisos.objects.create(
                marca=marca,
                nombre_permiso=key,
                visible=True,
                orden=index,
            )

    if request.method == "POST":
        formset = MarcaPermisosFormSet(request.POST, instance=marca)
        if formset.is_valid():
            formset.save()
            return redirect("index")
    else:
        formset = MarcaPermisosFormSet(instance=marca)

    # Para mostrar etiqueta bonita en el template
    section_labels = dict(DEFAULT_SECTIONS)

    return render(
        request,
        "brand/settings.html",
        {
            "marca": marca,
            "formset": formset,
            "section_labels": section_labels,
        },
    )

class MarcaPublicBySlugView(generics.RetrieveAPIView):
    queryset = Marca.objects.filter(estado="activo")
    serializer_class = MarcaPublicSerializer
    permission_classes = [drf_permissions.AllowAny]
    lookup_field = "slug"

@csrf_exempt
@require_POST
def sync_courses_from_external(request):
    try:
        body = json.loads(request.body or "{}")
    except ValueError:
        body = {}

    page = int(body.get("page", 1) or 1)
    page_size = int(body.get("pageSize", 25) or 25)

    base_url = "https://erucsg6yrj.execute-api.us-east-1.amazonaws.com/colombia-endpoint/course-information/courses"

    api_key = getattr(settings, "AWS_COURSES_API_KEY", None) or getattr(settings, "COURSES_EXTERNAL_API_KEY", None)
    if not api_key:
        return JsonResponse(
            {"ok": False, "error": "missing_api_key", "detail": "Define AWS_COURSES_API_KEY o COURSES_EXTERNAL_API_KEY en Railway"},
            status=500,
        )

    params = {"page": page, "pageSize": page_size}
    headers = {"Accept": "application/json", "x-api-key": api_key}

    try:
        resp = requests.get(base_url, headers=headers, params=params, timeout=20)
    except requests.RequestException as e:
        return JsonResponse({"ok": False, "error": "upstream_unreachable", "detail": str(e)}, status=502)

    if resp.status_code != 200:
        return JsonResponse(
            {"ok": False, "error": "upstream_error", "status": resp.status_code, "response": resp.text[:2000]},
            status=502,
        )

    try:
        payload = resp.json()
    except ValueError:
        return JsonResponse({"ok": False, "error": "invalid_json_from_upstream", "response": resp.text[:2000]}, status=502)

    try:
        result = ingest_course_payload(payload)
    except Exception as e:
        return JsonResponse({"ok": False, "error": "ingestion_failed", "detail": str(e)}, status=500)

    items_len = len(payload.get("items", [])) if isinstance(payload.get("items"), list) else None
    return JsonResponse({"ok": True, "page": page, "pageSize": page_size, "items_len": items_len, "summary": result})


## Integración de Stripe
User = get_user_model()
stripe.api_key = settings.STRIPE_SECRET_KEY


def _ts_to_dt(ts):
    """Stripe timestamps (unix) -> datetime aware"""
    if not ts:
        return None
    try:
        return datetime.fromtimestamp(int(ts), tz=timezone.utc)
    except Exception:
        return None


def _safe_get_email(session_obj):
    # checkout.session: customer_details.email (normal) o customer_email (legacy)
    cd = session_obj.get("customer_details") or {}
    return (cd.get("email") or session_obj.get("customer_email") or "").strip() or None


def _find_user_from_session(session_obj):
    """
    Encuentra usuario de forma robusta:
    1) client_reference_id (ideal)
    2) metadata.user_id (si lo mandaste)
    3) email (customer_details.email / customer_email)
    """
    # 1) client_reference_id
    rid = session_obj.get("client_reference_id")
    if rid:
        try:
            return User.objects.filter(id=int(rid)).first()
        except Exception:
            return User.objects.filter(id=rid).first()

    # 2) metadata.user_id
    meta = session_obj.get("metadata") or {}
    mid = meta.get("user_id")
    if mid:
        try:
            return User.objects.filter(id=int(mid)).first()
        except Exception:
            return User.objects.filter(id=mid).first()

    # 3) email
    email = _safe_get_email(session_obj)
    if email:
        # ajusta si tu auth usa username distinto; aquí asumimos email en campo email
        return User.objects.filter(email__iexact=email).first()

    return None


def _get_price_id_from_subscription_obj(sub_obj):
    """
    sub_obj.items.data[0].price.id -> price_id
    """
    try:
        items = (sub_obj.get("items") or {}).get("data") or []
        if not items:
            return None
        price = (items[0].get("price") or {})
        return price.get("id")
    except Exception:
        return None


def _get_interval_from_subscription_obj(sub_obj):
    """
    sub_obj.items.data[0].price.recurring.interval -> month/year
    """
    try:
        items = (sub_obj.get("items") or {}).get("data") or []
        if not items:
            return None
        price = (items[0].get("price") or {})
        recurring = price.get("recurring") or {}
        return recurring.get("interval")
    except Exception:
        return None


def _upsert_subscription(user, subscription_id):
    if not subscription_id:
        return None

    try:
        sub = stripe.Subscription.retrieve(subscription_id, expand=["items.data.price"])
    except Exception as e:
        print("❌ Error retrieving subscription:", subscription_id, str(e))
        return None

    status = sub.get("status") or "incomplete"
    current_period_end = _ts_to_dt(sub.get("current_period_end"))
    cancel_at_period_end = bool(sub.get("cancel_at_period_end") or False)

    price_id = _get_price_id_from_subscription_obj(sub)
    interval = _get_interval_from_subscription_obj(sub)

    try:
        obj, _created = StripeSubscription.objects.update_or_create(
            stripe_subscription_id=subscription_id,
            defaults={
                "user": user,
                "status": status,
                "price_id": price_id,
                "interval": interval,
                "current_period_end": current_period_end,
                "cancel_at_period_end": cancel_at_period_end,
            },
        )
        return obj
    except Exception as e:
        print("❌ Error saving StripeSubscription:", str(e))
        return None


def _ensure_billing_profile(user, customer_id=None):
    profile, _ = UserBillingProfile.objects.get_or_create(user=user)
    if customer_id and profile.stripe_customer_id != customer_id:
        profile.stripe_customer_id = customer_id
        profile.save(update_fields=["stripe_customer_id"])
    return profile


@require_POST
@csrf_exempt
def stripe_webhook(request):
    print("✅ WEBHOOK HIT")
    print("SIG HEADER:", request.META.get("HTTP_STRIPE_SIGNATURE", "")[:30], "...")
    print("PAYLOAD FIRST 200:", (request.body or b"")[:200])
    payload = request.body
    sig_header = request.META.get("HTTP_STRIPE_SIGNATURE", "")

    # 1) Validar firma
    try:
        event = stripe.Webhook.construct_event(
            payload=payload,
            sig_header=sig_header,
            secret=settings.STRIPE_WEBHOOK_SECRET,
        )
    except Exception:
        return HttpResponse(status=400)

    event_type = event.get("type")
    obj = (event.get("data") or {}).get("object") or {}

    # --------------------------------------------
    # A) checkout.session.completed
    # --------------------------------------------
    if event_type == "checkout.session.completed":
        

        session = obj
        # Idempotencia (Stripe reintenta webhooks)
        session_id = session.get("id")
        if session_id and StripePurchase.objects.filter(stripe_checkout_session_id=session_id).exists():
            return HttpResponse(status=200)

        user = _find_user_from_session(session)
        print("session.id:", session.get("id"))
        print("client_reference_id:", session.get("client_reference_id"))
        print("metadata:", session.get("metadata"))
        print("customer_details:", session.get("customer_details"))
        print("customer_email:", session.get("customer_email"))
        print("found user:", user.id if user else None)

        if not user:
            # no bloquees el webhook: solo no guardes
            return HttpResponse(status=200)

        customer_id = session.get("customer")
        subscription_id = session.get("subscription")

        _ensure_billing_profile(user, customer_id=customer_id)

        # Guardar compra base (checkout)
        StripePurchase.objects.create(
            user=user,
            stripe_checkout_session_id=session_id,
            stripe_payment_intent_id=session.get("payment_intent"),
            amount_total=session.get("amount_total") or 0,
            currency=session.get("currency") or "usd",
            status=session.get("payment_status") or "unknown",
            description="Checkout completed",
        )

        # Guardar/actualizar suscripción
        if subscription_id:
            _upsert_subscription(user, subscription_id)

        return HttpResponse(status=200)

    # --------------------------------------------
    # B) invoice paid / payment succeeded
    # (esto es el "historial real" de cobros)
    # --------------------------------------------
    if event_type in ("invoice.paid", "invoice.payment_succeeded"):
        invoice = obj
        invoice_id = invoice.get("id")
        customer_id = invoice.get("customer")
        subscription_id = invoice.get("subscription")

        # buscar user por customer
        profile = (
            UserBillingProfile.objects
            .filter(stripe_customer_id=customer_id)
            .select_related("user")
            .first()
        )
        if not profile:
            return HttpResponse(status=200)

        user = profile.user

        # idempotencia por invoice_id
        if invoice_id and StripePurchase.objects.filter(stripe_invoice_id=invoice_id).exists():
            # aun así actualizamos subs por si cambió
            if subscription_id:
                _upsert_subscription(user, subscription_id)
            return HttpResponse(status=200)

        StripePurchase.objects.update_or_create(
            user=user,
            stripe_invoice_id=invoice_id,
            defaults={
                "stripe_payment_intent_id": invoice.get("payment_intent"),
                "amount_total": invoice.get("amount_paid") or invoice.get("total") or 0,
                "currency": invoice.get("currency") or "usd",
                "status": invoice.get("status") or "unknown",
                "description": (invoice.get("description") or "Invoice paid")[:500],
                "hosted_invoice_url": invoice.get("hosted_invoice_url"),
                "invoice_pdf": invoice.get("invoice_pdf"),
            },
        )

        if subscription_id:
            _upsert_subscription(user, subscription_id)

        return HttpResponse(status=200)

    # --------------------------------------------
    # C) subscription updated/deleted
    # --------------------------------------------
    if event_type in ("customer.subscription.updated", "customer.subscription.deleted"):
        sub_obj = obj
        subscription_id = sub_obj.get("id")
        customer_id = sub_obj.get("customer")

        profile = (
            UserBillingProfile.objects
            .filter(stripe_customer_id=customer_id)
            .select_related("user")
            .first()
        )
        if not profile:
            return HttpResponse(status=200)

        _upsert_subscription(profile.user, subscription_id)
        return HttpResponse(status=200)

    # --------------------------------------------
    # D) ignorar otros eventos (si quieres log)
    # --------------------------------------------
    return HttpResponse(status=200)

PRICE_MAP = {
    "yearly": os.environ.get("STRIPE_PRICE_YEARLY"),
    "monthly": os.environ.get("STRIPE_PRICE_MONTHLY"),
}
@csrf_exempt
@require_POST
def create_checkout_session(request):
    """
    Crea sesión de Checkout (suscripción).
    - Si el usuario está logueado: amarra con client_reference_id y customer_email
    - Si ya existe stripe_customer_id: reusa customer
    - Agrega metadata útil para el webhook/DB
    """
    try:
        body = json.loads(request.body or "{}")
    except ValueError:
        body = {}

    plan = (body.get("plan") or "yearly").lower().strip()
    price_id = PRICE_MAP.get(plan)

    if not price_id or not str(price_id).startswith("price_"):
        return JsonResponse(
            {
                "ok": False,
                "error": "invalid_price_id",
                "detail": f"Price ID inválido para plan={plan}.",
            },
            status=400,
        )

    # valida que exista en Stripe (modo test/live según tu STRIPE_SECRET_KEY)
    try:
        price_obj = stripe.Price.retrieve(price_id)
    except stripe.error.InvalidRequestError as e:
        return JsonResponse(
            {
                "ok": False,
                "error": "price_not_found",
                "detail": str(e),
                "price_id": price_id,
            },
            status=400,
        )

    # -------- Asociar user si hay sesión --------
    user = getattr(request, "user", None)

    client_reference_id = None
    customer_email = None
    existing_customer_id = None

    if user and getattr(user, "is_authenticated", False):
        client_reference_id = str(user.id)
        customer_email = getattr(user, "email", None) or None

        profile = UserBillingProfile.objects.filter(user=user).first()
        existing_customer_id = profile.stripe_customer_id if profile else None
    else:
        # si NO hay sesión, puedes mandar email desde el front
        customer_email = (body.get("email") or "").strip() or None

    # URLs (asegúrate que existan y estén bien)
    success_url = getattr(settings, "STRIPE_SUCCESS_URL", "http://localhost:3000/success?session_id={CHECKOUT_SESSION_ID}")
    cancel_url = getattr(settings, "STRIPE_CANCEL_URL", "http://localhost:3000/cancel")

    # Interval (opcional pero útil para tu UI / DB)
    interval = None
    try:
        # muchas veces viene en price.recurring.interval
        interval = (price_obj.get("recurring") or {}).get("interval")
    except Exception:
        interval = None

    try:
        kwargs = dict(
            mode="subscription",
            line_items=[{"price": price_id, "quantity": 1}],
            success_url=success_url,
            cancel_url=cancel_url,

            # opcionales útiles
            allow_promotion_codes=True,
            # billing_address_collection="auto",  # si quieres capturar address
            # automatic_tax={"enabled": True},     # si vas a manejar impuestos automáticos

            # ✅ metadata que vas a usar en webhooks (debug + DB)
            metadata={
                "plan": plan,
                "price_id": price_id,
                "interval": interval or "",
                "user_id": client_reference_id or "",
                "email": customer_email or "",
            },

            # ✅ metadata también en la suscripción
            subscription_data={
                "metadata": {
                    "plan": plan,
                    "price_id": price_id,
                    "interval": interval or "",
                    "user_id": client_reference_id or "",
                    "email": customer_email or "",
                }
            },
        )

        # ✅ Link con usuario
        if client_reference_id:
            kwargs["client_reference_id"] = client_reference_id

        # ⚠️ Stripe no deja enviar customer_email si envías customer (existing_customer_id)
        # Por eso:
        if existing_customer_id:
            kwargs["customer"] = existing_customer_id
        elif customer_email:
            kwargs["customer_email"] = customer_email

        session = stripe.checkout.Session.create(**kwargs)
        return JsonResponse({"ok": True, "url": session.url, "session_id": session.id})

    except stripe.error.StripeError as e:
        return JsonResponse(
            {"ok": False, "error": "stripe_error", "detail": str(e)},
            status=400,
        )


def _json(request):
    try:
        return json.loads(request.body or "{}")
    except Exception:
        return {}


@csrf_exempt
@require_POST
def auth_register(request):
    data = _json(request)

    email = (data.get("email") or "").strip().lower()
    password = data.get("password") or ""
    full_name = (data.get("full_name") or "").strip()

    if not email or not password:
        return JsonResponse({"ok": False, "error": "missing_fields"}, status=400)

    # username: usamos email para simplificar
    username = email

    if User.objects.filter(username=username).exists():
        return JsonResponse({"ok": False, "error": "user_exists"}, status=400)

    user = User.objects.create_user(
        username=username,
        email=email,
        password=password,
    )

    # guardamos nombre en first_name / last_name rápido
    if full_name:
        parts = full_name.split(" ", 1)
        user.first_name = parts[0]
        if len(parts) > 1:
            user.last_name = parts[1]
        user.save()

    return JsonResponse({
        "ok": True,
        "user": {
            "id": user.id,
            "email": user.email,
            "full_name": (user.first_name + " " + user.last_name).strip(),
        }
    })


@csrf_exempt
@require_POST
def auth_login(request):
    body = json.loads(request.body or "{}")
    email = body.get("email")
    password = body.get("password")

    user = authenticate(request, username=email, password=password)  # depende de tu auth
    if not user:
        return JsonResponse({"ok": False, "error": "invalid_credentials"}, status=400)

    login(request, user)  # ✅ esto crea sessionid
    return JsonResponse({"ok": True})



@csrf_exempt
@require_POST
def auth_logout(request):
    logout(request)
    return JsonResponse({"ok": True})


@api_login_required
def account_me(request):
    u = request.user

    billing = UserBillingProfile.objects.filter(user=u).first()
    sub = StripeSubscription.objects.filter(user=u).order_by("-updated_at").first()

    return JsonResponse({
        "ok": True,
        "data": {
            "id": u.id,
            "email": u.email,
            "full_name": u.get_full_name() or u.username,
            "stripe_customer_id": getattr(billing, "stripe_customer_id", None),
            "subscription_status": getattr(sub, "status", None),
            "plan": getattr(sub, "interval", None),
            "price_id": getattr(sub, "price_id", None),
            "current_period_end": sub.current_period_end.isoformat() if sub and sub.current_period_end else None,
            "cancel_at_period_end": bool(sub.cancel_at_period_end) if sub else False,
        }
    })

@api_login_required
def account_purchases(request):
    qs = StripePurchase.objects.filter(user=request.user).order_by("-created_at")[:100]

    items = []
    for p in qs:
        items.append({
            "id": p.id,
            "created_at": p.created_at.isoformat() if p.created_at else None,
            "type": "invoice" if p.stripe_invoice_id else "checkout",
            "amount": p.amount_total,
            "currency": p.currency,
            "status": p.status,
            "session_id": p.stripe_checkout_session_id,
            "invoice_id": p.stripe_invoice_id,
            "payment_intent": p.stripe_payment_intent_id,
            "hosted_invoice_url": p.hosted_invoice_url,
            "invoice_pdf": p.invoice_pdf,
            "description": p.description,
        })

    return JsonResponse({"ok": True, "data": items})



@require_GET
@csrf_exempt
def stripe_sync_session(request):
    """
    Se llama desde el frontend en /success?session_id=...
    GUARDA compra + suscripción en DB en el acto.
    Esto resuelve el caso donde el webhook no llega (localhost, firewalls, etc.)
    """
    session_id = (request.GET.get("session_id") or "").strip()
    if not session_id:
        return JsonResponse({"ok": False, "error": "missing_session_id"}, status=400)

    try:
        # Expandimos para tener todo lo necesario
        session = stripe.checkout.Session.retrieve(
            session_id,
            expand=["customer_details", "subscription", "payment_intent"]
        )
    except Exception as e:
        return JsonResponse({"ok": False, "error": "stripe_retrieve_failed", "detail": str(e)}, status=400)

    # Encontrar usuario por client_reference_id / metadata / email
    user = _find_user_from_session(session)
    if not user:
        return JsonResponse({"ok": False, "error": "user_not_found_from_session"}, status=200)

    customer_id = session.get("customer")
    subscription_id = session.get("subscription")
    payment_intent = session.get("payment_intent")

    # billing profile
    _ensure_billing_profile(user, customer_id=customer_id)

    # idempotencia por checkout session id
    if not StripePurchase.objects.filter(stripe_checkout_session_id=session_id).exists():
        StripePurchase.objects.create(
            user=user,
            stripe_checkout_session_id=session_id,
            stripe_payment_intent_id=payment_intent if isinstance(payment_intent, str) else (payment_intent or {}).get("id"),
            amount_total=session.get("amount_total") or 0,
            currency=session.get("currency") or "usd",
            status=session.get("payment_status") or "unknown",
            description="Checkout success (sync)",
        )

    # suscripción
    if subscription_id:
        # a veces viene expandida como dict
        if isinstance(subscription_id, dict):
            sub_id = subscription_id.get("id")
        else:
            sub_id = subscription_id
        if sub_id:
            _upsert_subscription(user, sub_id)

    return JsonResponse({"ok": True})


def admin_purchases_api(request):
    # opcional: solo staff
    if not request.user.is_staff:
        return JsonResponse({"ok": False, "error": "forbidden"}, status=403)

    q = (request.GET.get("q") or "").strip()
    status = (request.GET.get("status") or "").strip()
    page = int(request.GET.get("page") or 1)
    page_size = int(request.GET.get("page_size") or 25)

    qs = StripePurchase.objects.select_related("user").all().order_by("-created_at")

    if status:
        qs = qs.filter(status__iexact=status)

    if q:
        qs = qs.filter(
            Q(user__email__icontains=q) |
            Q(user__username__icontains=q) |
            Q(user__first_name__icontains=q) |
            Q(user__last_name__icontains=q) |
            Q(stripe_invoice_id__icontains=q) |
            Q(stripe_checkout_session_id__icontains=q) |
            Q(stripe_payment_intent_id__icontains=q)
        )

    paginator = Paginator(qs, page_size)
    page_obj = paginator.get_page(page)

    items = []
    for p in page_obj.object_list:
        u = p.user
        items.append({
            "id": p.id,
            "created_at": p.created_at.isoformat() if p.created_at else None,
            "amount_total": p.amount_total,
            "currency": p.currency,
            "status": p.status,
            "invoice_id": p.stripe_invoice_id,
            "session_id": p.stripe_checkout_session_id,
            "payment_intent": p.stripe_payment_intent_id,
            "hosted_invoice_url": p.hosted_invoice_url,
            "invoice_pdf": p.invoice_pdf,
            "description": p.description,
            "user": {
                "id": u.id,
                "email": u.email,
                "username": u.username,
                "full_name": (u.get_full_name() or "").strip(),
            }
        })

    return JsonResponse({
        "ok": True,
        "total": paginator.count,
        "page": page_obj.number,
        "page_size": page_size,
        "items": items,
    })


User = get_user_model()

# ---------------------------------------------------------
# POST /api/auth/password/reset/   { "email": "..." }
# ---------------------------------------------------------
@api_view(["POST"])
@permission_classes([AllowAny])
def auth_password_reset_request(request):
    print("EMAIL_BACKEND:", settings.EMAIL_BACKEND)
    print("EMAIL_HOST:", getattr(settings, "EMAIL_HOST", None))
    print("EMAIL_PORT:", getattr(settings, "EMAIL_PORT", None))
    email = (request.data.get("email") or "").strip().lower()
    if not email:
        return Response({"ok": False, "error": "Email es obligatorio"}, status=status.HTTP_400_BAD_REQUEST)

    # ✅ Responder SIEMPRE ok para no revelar si existe o no el usuario
    try:
        user = User.objects.get(email=email)
    except User.DoesNotExist:
        return Response({"ok": True})

    uid = urlsafe_base64_encode(force_bytes(user.pk))
    token = default_token_generator.make_token(user)

    frontend_url = getattr(settings, "FRONTEND_URL", "").rstrip("/")
    reset_link = f"{frontend_url}/reset-password?uid={uid}&token={token}"

    subject = "Restablecer contraseña"
    message = (
        "Hola,\n\n"
        "Recibimos una solicitud para restablecer tu contraseña.\n"
        "Abre este enlace para crear una nueva contraseña:\n\n"
        f"{reset_link}\n\n"
        "Si no solicitaste esto, ignora este correo.\n"
    )

    send_mail(
        subject=subject,
        message=message,
        from_email=getattr(settings, "DEFAULT_FROM_EMAIL", None),
        recipient_list=[email],
        fail_silently=False,
    )

    return Response({"ok": True})


# ---------------------------------------------------------
# POST /api/auth/password/reset/confirm/
# { "uid": "...", "token": "...", "new_password": "..." }
# ---------------------------------------------------------
@api_view(["POST"])
@permission_classes([AllowAny])
def auth_password_reset_confirm(request):
    uidb64 = request.data.get("uid") or ""
    token = request.data.get("token") or ""
    new_password = request.data.get("new_password") or ""

    if not uidb64 or not token or not new_password:
        return Response(
            {"ok": False, "error": "uid, token y new_password son obligatorios"},
            status=status.HTTP_400_BAD_REQUEST,
        )

    if len(new_password) < 8:
        return Response({"ok": False, "error": "Contraseña muy corta (mín 8)"}, status=status.HTTP_400_BAD_REQUEST)

    try:
        uid = force_str(urlsafe_base64_decode(uidb64))
        user = User.objects.get(pk=uid)
    except Exception:
        return Response({"ok": False, "error": "Link inválido"}, status=status.HTTP_400_BAD_REQUEST)

    if not default_token_generator.check_token(user, token):
        return Response({"ok": False, "error": "Token inválido o expirado"}, status=status.HTTP_400_BAD_REQUEST)

    user.set_password(new_password)
    user.save()

    return Response({"ok": True})


def _build_external_headers() -> dict:
    headers = {"Accept": "application/json"}
    api_key = getattr(settings, "COURSES_EXTERNAL_API_KEY", None)
    if not api_key:
        return headers

    auth_header = getattr(settings, "COURSES_EXTERNAL_AUTH_HEADER", "x-api-key")
    auth_prefix = getattr(settings, "COURSES_EXTERNAL_AUTH_PREFIX", "")

    # Si el header es Authorization, puede llevar prefix Bearer
    if auth_header.lower() == "authorization":
        prefix = auth_prefix or "Bearer "
        headers["Authorization"] = f"{prefix}{api_key}".strip()
        return headers

    # Para x-api-key u otros, NO le pongas Bearer
    headers[auth_header] = f"{auth_prefix}{api_key}".strip()
    return headers



def _is_allowed_external_url(url: str) -> bool:
    """
    Muy recomendado: whitelist por dominio para que tu proxy no sea open-proxy.
    Ajusta el host permitido al tuyo real.
    """
    try:
        host = urlparse(url).netloc.lower()
    except Exception:
        return False

    allowed = getattr(settings, "COURSES_EXTERNAL_ALLOWED_HOSTS", [])
    if not allowed:
        # si no configuras whitelist, por lo menos bloquea vacío
        return bool(host)

    return host in [h.lower() for h in allowed]


@require_GET
def api_proxy_courses(request):
    url = (request.GET.get("url") or "").strip()
    if not url:
        return HttpResponseBadRequest("Missing url")
    if not _is_allowed_external_url(url):
        return HttpResponseBadRequest("URL not allowed")

    try:
        r = requests.get(url, headers=_build_external_headers(), timeout=60)
        return JsonResponse(r.json(), status=r.status_code, safe=isinstance(r.json(), dict))
    except Exception as e:
        return JsonResponse({"error": str(e)}, status=500)



def _build_external_headers() -> dict:
    headers = {"Accept": "application/json"}
    api_key = getattr(settings, "COURSES_EXTERNAL_API_KEY", None)
    if not api_key:
        return headers

    auth_header = getattr(settings, "COURSES_EXTERNAL_AUTH_HEADER", "Authorization")
    auth_prefix = getattr(settings, "COURSES_EXTERNAL_AUTH_PREFIX", "Bearer ")

    if auth_header.lower() == "authorization":
        headers["Authorization"] = f"{auth_prefix}{api_key}".strip()
    else:
        headers[auth_header] = str(api_key).strip()
    return headers


def _is_allowed_external_url(url: str) -> bool:
    try:
        host = urlparse(url).netloc.lower()
    except Exception:
        return False

    allowed = getattr(settings, "COURSES_EXTERNAL_ALLOWED_HOSTS", [])
    if not allowed:
        return bool(host)
    return host in [h.lower() for h in allowed]


@staff_member_required
@require_GET
def api_proxy_courses(request):
    url = (request.GET.get("url") or "").strip()
    if not url:
        return HttpResponseBadRequest("Missing url")
    if not _is_allowed_external_url(url):
        return HttpResponseBadRequest("URL not allowed")

    try:
        r = requests.get(url, headers=_build_external_headers(), timeout=60)
        # devolvemos el JSON del externo
        return JsonResponse(r.json(), status=r.status_code, safe=isinstance(r.json(), dict))
    except Exception as e:
        return JsonResponse({"error": str(e)}, status=500)


LOCK_TTL_SECONDS = 14 * 60  # ~14 min para cron de 15 min

def _get_courses_endpoint():
    # puedes moverlo a settings si quieres
    return getattr(settings, "COURSES_EXTERNAL_ENDPOINT", None) or \
           "https://erucsg6yrj.execute-api.us-east-1.amazonaws.com/colombia-endpoint/course-information/courses"

def _get_courses_api_key():
    return getattr(settings, "AWS_COURSES_API_KEY", None) or getattr(settings, "COURSES_EXTERNAL_API_KEY", None)

@csrf_exempt
@require_POST
def api_run_courses_sync(request):
    t0 = time.time()
    run_id = uuid.uuid4().hex[:16]
    state_key = "courses_sync"

    endpoint = _get_courses_endpoint()
    api_key = _get_courses_api_key()

    if not api_key:
        return JsonResponse({"ok": False, "error": "missing_api_key"}, status=500)

    # body opcional: pageSize, maxPagesPerRun, timeout
    try:
        body = json.loads(request.body or "{}")
    except Exception:
        body = {}

    page_size = int(body.get("pageSize", 50) or 50)
    timeout = int(body.get("timeout", 30) or 30)

    # 🔥 si quieres que en un solo cron procese más de una página:
    max_pages_per_run = int(body.get("maxPagesPerRun", 1) or 1)
    max_pages_per_run = max(1, min(max_pages_per_run, 10))  # cap de seguridad

    # 1) asegurar state
    state, _ = ExternalSyncState.objects.get_or_create(
        key=state_key,
        defaults={"cursor_value": "1", "running": False},
    )

    # 2) adquirir lock con TTL
    now = timezone.now()
    stale_before = now - timedelta(seconds=LOCK_TTL_SECONDS)

    # si está corriendo y el lock no está stale: salimos OK sin hacer nada
    if state.running and state.locked_at and state.locked_at > stale_before:
        return JsonResponse({
            "ok": True,
            "message": "Lock activo, ya hay una ejecución en curso",
            "run_id": run_id,
            "locked": False,
            "state_key": state_key,
        }, status=200)

    # tomar lock
    state.running = True
    state.locked_at = now
    state.updated_at = now
    state.save(update_fields=["running", "locked_at", "updated_at"])

    processed_pages = 0
    last_result = None

    try:
        # cursor actual
        try:
            page = max(1, int(state.cursor_value or "1"))
        except Exception:
            page = 1

        headers = {"Accept": "application/json", "x-api-key": api_key}

        for _ in range(max_pages_per_run):
            params = {"page": page, "pageSize": page_size}

            # 3) pedir payload al externo (igual que tu sync manual)
            try:
                resp = requests.get(endpoint, headers=headers, params=params, timeout=timeout)
            except requests.RequestException as e:
                took_ms = int((time.time() - t0) * 1000)
                ExternalSyncLog.objects.create(
                    key=state_key, run_id=run_id, page=page, page_size=page_size,
                    ok=False, took_ms=took_ms,
                    error="upstream_unreachable", detail=str(e), trace=traceback.format_exc()[:8000],
                )
                state.last_error_at = timezone.now()
                state.last_error = f"upstream_unreachable: {e}"
                state.save(update_fields=["last_error_at", "last_error"])
                return JsonResponse({"ok": False, "error": "upstream_unreachable", "detail": str(e)}, status=502)

            if resp.status_code != 200:
                took_ms = int((time.time() - t0) * 1000)
                ExternalSyncLog.objects.create(
                    key=state_key, run_id=run_id, page=page, page_size=page_size,
                    ok=False, took_ms=took_ms,
                    error="upstream_error",
                    detail=f"HTTP {resp.status_code}: {resp.text[:2000]}",
                )
                state.last_error_at = timezone.now()
                state.last_error = f"upstream_error HTTP {resp.status_code}"
                state.save(update_fields=["last_error_at", "last_error"])
                return JsonResponse({"ok": False, "error": "upstream_error", "status": resp.status_code}, status=502)

            try:
                payload = resp.json()
            except Exception:
                took_ms = int((time.time() - t0) * 1000)
                ExternalSyncLog.objects.create(
                    key=state_key, run_id=run_id, page=page, page_size=page_size,
                    ok=False, took_ms=took_ms,
                    error="invalid_json_from_upstream",
                    detail=resp.text[:2000],
                )
                state.last_error_at = timezone.now()
                state.last_error = "invalid_json_from_upstream"
                state.save(update_fields=["last_error_at", "last_error"])
                return JsonResponse({"ok": False, "error": "invalid_json_from_upstream"}, status=502)

            items = payload.get("items", [])
            items_len = len(items) if isinstance(items, list) else 0

            # 4) ingestar a BD
            try:
                summary = ingest_course_payload(payload)
            except Exception as e:
                took_ms = int((time.time() - t0) * 1000)
                ExternalSyncLog.objects.create(
                    key=state_key, run_id=run_id, page=page, page_size=page_size,
                    ok=False, items_len=items_len, took_ms=took_ms,
                    error="ingestion_failed", detail=str(e), trace=traceback.format_exc()[:8000],
                )
                state.last_error_at = timezone.now()
                state.last_error = f"ingestion_failed: {e}"
                state.save(update_fields=["last_error_at", "last_error"])
                return JsonResponse({"ok": False, "error": "ingestion_failed", "detail": str(e)}, status=500)

            # 5) avanzar cursor
            next_page = 1 if items_len < page_size else (page + 1)
            state.cursor_value = str(next_page)
            state.last_ok_at = timezone.now()
            state.last_error = ""
            state.save(update_fields=["cursor_value", "last_ok_at", "last_error", "updated_at"])

            processed_pages += 1
            last_result = {
                "page": page,
                "page_size": page_size,
                "items_len": items_len,
                "next_page": next_page,
                "summary": summary,
            }

            # log ok
            ExternalSyncLog.objects.create(
                key=state_key, run_id=run_id, page=page, page_size=page_size,
                ok=True, items_len=items_len, received=items_len,
                took_ms=int((time.time() - t0) * 1000),
            )

            page = next_page

            # si llegamos al final (reinició a 1), cortamos
            if next_page == 1:
                break

        return JsonResponse({
            "ok": True,
            "run_id": run_id,
            "state_key": state_key,
            "processed_pages": processed_pages,
            "cursor_next": state.cursor_value,
            "took_ms": int((time.time() - t0) * 1000),
            "last": last_result,
        }, status=200)

    finally:
        # liberar lock siempre
        try:
            ExternalSyncState.objects.filter(key=state_key).update(
                running=False,
                locked_at=None,
                updated_at=timezone.now(),
            )
        except Exception:
            pass


