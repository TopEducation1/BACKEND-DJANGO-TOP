from __future__ import annotations

import hashlib, hmac, json, logging, os, random, re, time, traceback, uuid
from collections import defaultdict
from datetime import datetime, timedelta, timezone
from urllib.parse import parse_qsl, urlencode, urlparse, urlunparse
from django.db import IntegrityError

import pandas as pd
import requests
import stripe

from django.conf import settings
from django.contrib import messages

from django.contrib.admin.views.decorators import staff_member_required
from django.contrib.auth import authenticate, get_backends, get_user_model, login, logout
from django.contrib.auth.decorators import login_required, user_passes_test
from django.contrib.auth.forms import AuthenticationForm, UserCreationForm
from django.contrib.auth.models import User
from django.contrib.auth.password_validation import validate_password
from django.contrib.auth.tokens import default_token_generator
from django.core.cache import cache
from django.core.exceptions import ValidationError
from django.core.mail import send_mail
from django.core.paginator import EmptyPage, PageNotAnInteger, Paginator
from django.db import transaction
from django.db.models import Case, Count, IntegerField, OuterRef, Prefetch, Q, Subquery, Value, When
from django.forms import modelformset_factory
from django.http import FileResponse, Http404, HttpResponse, HttpResponseBadRequest, HttpResponseForbidden, JsonResponse
from django.middleware.csrf import get_token
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.utils import timezone
from django.utils.decorators import method_decorator
from django.utils.encoding import force_bytes, force_str
from django.utils.http import urlsafe_base64_decode, urlsafe_base64_encode
from django.utils.text import slugify
from django.views import View
from django.views.decorators.cache import cache_page
from django.views.decorators.csrf import csrf_exempt, ensure_csrf_cookie
from django.views.decorators.http import require_GET, require_http_methods, require_POST
from datetime import timezone as dt_timezone

from rest_framework import generics, status, viewsets
from rest_framework import permissions as drf_permissions
from rest_framework.decorators import api_view, permission_classes
from rest_framework.pagination import PageNumberPagination
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from rest_framework.views import APIView

from .forms import *
from .models import *
from .serializers import *
from .utils.auth import api_login_required

from topeducation.inspectors.courses_inspector import fetch_and_parse_page
from topeducation.models import ExternalSyncState
from topeducation.services.import_courses import (
    ingest_course_payload,
    ingest_skills_structure_payload,
    ingest_specialization_detail_payload,
    ingest_specializations_payload,
)
from topeducation.services.mx_payload_builder import build_mx_payload_from_stripe_event
from topeducation.services.mx_webhook_sender import send_b2c_access_event_to_mx


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
    certifications = Certificaciones.objects.count()
    edx = Certificaciones.objects.filter(plataforma_certificacion=1).count()
    coursera = Certificaciones.objects.filter(plataforma_certificacion=2).count()
    masterclass = Certificaciones.objects.filter(plataforma_certificacion=3).count()
    cursos = Certificaciones.objects.filter(tipo_certificacion="Curso").count()
    especializaciones = Certificaciones.objects.filter(tipo_certificacion="Especialización").count()
    posts = Blog.objects.count()

    return render(request, "pages/dashboard.html", {
        "certifications": certifications,
        "edx": edx,
        "coursera": coursera,
        "masterclass": masterclass,
        "posts": posts,
        "cursos": cursos,
        "especializaciones": especializaciones,
    })


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
    q = (request.GET.get("q") or "").strip()

    # per_page
    try:
        per_page = int(request.GET.get("per_page", 50))
    except (TypeError, ValueError):
        per_page = 50
    per_page = max(1, min(per_page, 200))

    # page
    try:
        page_number = int(request.GET.get("page", 1))
    except (TypeError, ValueError):
        page_number = 1

    qs = Blog.objects.select_related("categoria_blog", "autor_blog")

    # 🔎 búsqueda
    if q:
        qs = qs.filter(
            Q(nombre_blog__icontains=q)
            | Q(slug__icontains=q)
            | Q(categoria_blog__nombre_categoria_blog__icontains=q)
            | Q(autor_blog__nombre_autor__icontains=q)
        )

    # ⚡ optimiza campos usados
    qs = qs.only(
        "id",
        "nombre_blog",
        "slug",
        "fecha_redaccion_blog",
        "categoria_blog_id",
        "autor_blog_id",
        "categoria_blog__nombre_categoria_blog",
        "autor_blog__nombre_autor",
    ).order_by("-id")

    paginator = Paginator(qs, per_page)
    page_obj = paginator.get_page(page_number)

    current = page_obj.number
    start_page = max(1, current - 3)
    end_page = min(paginator.num_pages, current + 3)
    page_numbers = range(start_page, end_page + 1)

    context = {
        "posts": page_obj.object_list,
        "page_obj": page_obj,
        "paginator": paginator,
        "per_page": per_page,
        "page_numbers": page_numbers,
        "show_inicio": start_page > 1,
        "show_final": end_page < paginator.num_pages,
        "per_page_options": [25, 50, 100, 200],
        "q": q,
    }
    return render(request, "posts/index.html", context)

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
    q = (request.GET.get("q") or "").strip()

    # per_page
    try:
        per_page = int(request.GET.get("per_page", 50))
    except (TypeError, ValueError):
        per_page = 50
    per_page = max(1, min(per_page, 200))

    # page
    try:
        page_number = int(request.GET.get("page", 1))
    except (TypeError, ValueError):
        page_number = 1

    qs = Certificaciones.objects.select_related("plataforma_certificacion", "tema_certificacion")

    # 🔎 búsqueda (ajusta campos si alguno es FK/choice)
    if q:
        qs = qs.filter(
            Q(nombre__icontains=q)
            | Q(slug__icontains=q)
            | Q(plataforma_certificacion__nombre__icontains=q)
            | Q(tema_certificacion__nombre__icontains=q)
            # si estos campos son texto:
            | Q(nivel_certificacion__icontains=q)
            | Q(tipo_certificacion__icontains=q)
            | Q(lenguaje_certificacion__icontains=q)
        )

    # ⚡ optimiza campos usados en el template (incluye los FK ids)
    qs = qs.only(
        "id",
        "nombre",
        "slug",
        "tiempo_certificacion",
        "nivel_certificacion",
        "lenguaje_certificacion",
        "fecha_creado_cert",
        "plataforma_certificacion_id",
        "tema_certificacion_id",
        "plataforma_certificacion__nombre",
        "tema_certificacion__nombre",
    ).order_by("-id")

    paginator = Paginator(qs, per_page)
    page_obj = paginator.get_page(page_number)

    current = page_obj.number
    start_page = max(1, current - 3)
    end_page = min(paginator.num_pages, current + 3)
    page_numbers = range(start_page, end_page + 1)

    context = {
        "certifications": page_obj.object_list,
        "page_obj": page_obj,
        "paginator": paginator,
        "per_page": per_page,
        "page_numbers": page_numbers,
        "show_inicio": start_page > 1,
        "show_final": end_page < paginator.num_pages,
        "per_page_options": [25, 50, 100, 200],
        "q": q,
    }
    return render(request, "certifications/index.html", context)

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
    skills = Skills.objects.all()
    cat_blog = CategoriaBlog.objects.all()
    originals = Original.objects.all()
    rankings = Ranking.objects.all()
    
    return render(request,'category/index.html',{'universities':universities,'companies':companies,'topics':topics,'cat_blog':cat_blog,'originals':originals,'rankings':rankings,'skills':skills})

def universities(request):
    # ✅ búsqueda
    q = (request.GET.get("q") or "").strip()

    # ✅ per_page
    try:
        per_page = int(request.GET.get("per_page", 50))
    except (TypeError, ValueError):
        per_page = 50
    per_page = max(1, min(per_page, 200))

    # ✅ page
    try:
        page_number = int(request.GET.get("page", 1))
    except (TypeError, ValueError):
        page_number = 1

    qs = Universidades.objects.all()

    # ✅ filtro por búsqueda (server-side)
    if q:
        qs = qs.filter(
            Q(nombre__icontains=q)
            # Si región es FK y tienes campo "nombre" en Region, usa esto:
            # | Q(region_universidad__nombre__icontains=q)
            # Si región es texto directo:
            # | Q(region__icontains=q)
            # Estado / top si son texto:
            # | Q(univ_est__icontains=q)
        )

    # ✅ optimiza campos
    qs = qs.only("id", "nombre", "region_universidad_id", "univ_img", "univ_ico", "univ_est", "univ_top").order_by("id")

    paginator = Paginator(qs, per_page)
    page_obj = paginator.get_page(page_number)

    current = page_obj.number
    start_page = max(1, current - 3)
    end_page = min(paginator.num_pages, current + 3)
    page_numbers = range(start_page, end_page + 1)

    context = {
        "universities": page_obj.object_list,
        "page_obj": page_obj,
        "paginator": paginator,
        "per_page": per_page,
        "page_numbers": page_numbers,
        "show_inicio": start_page > 1,
        "show_final": end_page < paginator.num_pages,
        "per_page_options": [25, 50, 100, 200],

        # ✅ para el buscador y mantener estado
        "q": q,
    }
    return render(request, "category/universities/index.html", context)


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
    q = (request.GET.get("q") or "").strip()

    try:
        per_page = int(request.GET.get("per_page", 50))
    except (TypeError, ValueError):
        per_page = 50
    per_page = max(1, min(per_page, 200))

    try:
        page_number = int(request.GET.get("page", 1))
    except (TypeError, ValueError):
        page_number = 1

    qs = Empresas.objects.all()

    if q:
        qs = qs.filter(
            Q(nombre__icontains=q)
            | Q(empr_est__icontains=q)
        )

    qs = (
        qs.only("id", "nombre", "empr_img", "empr_ico", "empr_est", "empr_top")
        .order_by("id")
    )

    paginator = Paginator(qs, per_page)
    page_obj = paginator.get_page(page_number)

    current = page_obj.number
    start_page = max(1, current - 3)
    end_page = min(paginator.num_pages, current + 3)
    page_numbers = range(start_page, end_page + 1)

    context = {
        "companies": page_obj.object_list,
        "page_obj": page_obj,
        "paginator": paginator,
        "per_page": per_page,
        "page_numbers": page_numbers,
        "show_inicio": start_page > 1,
        "show_final": end_page < paginator.num_pages,
        "per_page_options": [25, 50, 100, 200],
        "q": q,
    }
    return render(request, "category/companies/index.html", context)

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

from django.contrib import messages
from django.core.paginator import Paginator
from django.db.models import Q
from django.shortcuts import get_object_or_404, redirect, render

# Ajusta estos imports si tus nombres reales son diferentes
# from .models import Plataformas
# from .forms import PlatformsForm


def platforms(request):
    q = (request.GET.get("q") or "").strip()

    try:
        per_page = int(request.GET.get("per_page", 50))
    except (TypeError, ValueError):
        per_page = 50

    per_page = max(1, min(per_page, 200))

    try:
        page_number = int(request.GET.get("page", 1))
    except (TypeError, ValueError):
        page_number = 1

    qs = Plataformas.objects.all()


    qs = (
        qs.only(
            "id",
            "nombre",
            "plat_img",
            "plat_ico",
        )
        .order_by("id")
    )

    paginator = Paginator(qs, per_page)
    page_obj = paginator.get_page(page_number)

    current = page_obj.number
    start_page = max(1, current - 3)
    end_page = min(paginator.num_pages, current + 3)
    page_numbers = range(start_page, end_page + 1)

    context = {
        "platforms": page_obj.object_list,
        "page_obj": page_obj,
        "paginator": paginator,
        "per_page": per_page,
        "page_numbers": page_numbers,
        "show_inicio": start_page > 1,
        "show_final": end_page < paginator.num_pages,
        "per_page_options": [25, 50, 100, 200],
        "q": q,
    }

    return render(request, "category/platforms/index.html", context)


def updatePlatform(request, platform_id):
    platform = get_object_or_404(Plataformas, pk=platform_id)

    if request.method == "GET":
        form = PlatformsForm(instance=platform)

        return render(
            request,
            "category/platforms/update.html",
            {
                "platform": platform,
                "form": form,
            },
        )

    form = PlatformsForm(request.POST or None, request.FILES or None, instance=platform)

    if form.is_valid():
        form.save()
        messages.success(request, "Plataforma actualizada correctamente!")
        return redirect("platforms")

    messages.warning(request, "No fue posible actualizar la plataforma.")

    return render(
        request,
        "category/platforms/update.html",
        {
            "platform": platform,
            "form": form,
        },
    )


def createPlatform(request):
    if request.method == "GET":
        return render(
            request,
            "category/platforms/create.html",
            {
                "form": PlatformsForm(),
            },
        )

    form = PlatformsForm(request.POST or None, request.FILES or None)

    if form.is_valid():
        form.save()
        messages.success(request, "Plataforma guardada correctamente")
        return redirect("platforms")

    messages.warning(request, "No fue posible crear la plataforma.")

    return render(
        request,
        "category/platforms/create.html",
        {
            "form": form,
        },
    )


def deletePlatform(request, platform_id):
    platform = get_object_or_404(Plataformas, pk=platform_id)

    if request.method == "POST":
        platform.delete()
        messages.success(request, "Plataforma eliminada correctamente.")
        return redirect("platforms")

    return redirect("platforms")

def topics(request):
    q = (request.GET.get("q") or "").strip()

    # per_page
    try:
        per_page = int(request.GET.get("per_page", 50))
    except (TypeError, ValueError):
        per_page = 50
    per_page = max(1, min(per_page, 200))

    # page
    try:
        page_number = int(request.GET.get("page", 1))
    except (TypeError, ValueError):
        page_number = 1

    qs = Temas.objects.all()

    if q:
        qs = qs.filter(
            Q(nombre__icontains=q)
            | Q(tem_type__icontains=q)
            | Q(tem_est__icontains=q)
            | Q(tem_col__icontains=q)
        )

    qs = (
        qs.only("id", "nombre", "tem_type", "tem_img", "tem_col", "tem_est")
        .order_by("id")
    )

    paginator = Paginator(qs, per_page)
    page_obj = paginator.get_page(page_number)

    current = page_obj.number
    start_page = max(1, current - 3)
    end_page = min(paginator.num_pages, current + 3)
    page_numbers = range(start_page, end_page + 1)

    context = {
        "topics": page_obj.object_list,
        "page_obj": page_obj,
        "paginator": paginator,
        "per_page": per_page,
        "page_numbers": page_numbers,
        "show_inicio": start_page > 1,
        "show_final": end_page < paginator.num_pages,
        "per_page_options": [25, 50, 100, 200],
        "q": q,
    }
    return render(request, "category/topics/index.html", context)

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

def skills(request):
    q = (request.GET.get("q") or "").strip()

    # per_page
    try:
        per_page = int(request.GET.get("per_page", 50))
    except (TypeError, ValueError):
        per_page = 50
    per_page = max(1, min(per_page, 200))

    # page
    try:
        page_number = int(request.GET.get("page", 1))
    except (TypeError, ValueError):
        page_number = 1

    qs = Skills.objects.all()

    if q:
        qs = qs.filter(
            Q(nombre__icontains=q)
            | Q(translate__icontains=q)
            | Q(descripcion__icontains=q)
            | Q(skill_type__icontains=q)
            | Q(slug__icontains=q)
        )

    qs = (
        qs.only("id", "nombre", "translate", "descripcion", "slug", "skill_img", "skill_ico", "skill_type", "estado")
        .order_by("id")
    )

    paginator = Paginator(qs, per_page)
    page_obj = paginator.get_page(page_number)

    current = page_obj.number
    start_page = max(1, current - 3)
    end_page = min(paginator.num_pages, current + 3)
    page_numbers = range(start_page, end_page + 1)

    context = {
        "skills": page_obj.object_list,
        "page_obj": page_obj,
        "paginator": paginator,
        "per_page": per_page,
        "page_numbers": page_numbers,
        "show_inicio": start_page > 1,
        "show_final": end_page < paginator.num_pages,
        "per_page_options": [25, 50, 100, 200],
        "q": q,
    }
    return render(request, "category/skills/index.html", context)


def updateSkill(request, skill_id):
    skill = get_object_or_404(Skills, pk=skill_id)

    if request.method == "GET":
        form = SkillsForm(request.POST or None, request.FILES or None, instance=skill)
        return render(
            request,
            "category/skills/update.html",
            {
                "skill": skill,
                "form": form,
            },
        )

    form = SkillsForm(request.POST or None, request.FILES or None, instance=skill)
    if form.is_valid():
        form.save()
        messages.success(request, "Skill actualizada correctamente!")
        return redirect("skills")

    messages.warning(request, "No fue posible actualizar la skill.")
    return render(
        request,
        "category/skills/update.html",
        {
            "skill": skill,
            "form": form,
        },
    )


def createSkill(request):
    if request.method == "GET":
        return render(
            request,
            "category/skills/create.html",
            {
                "form": SkillsForm,
            },
        )

    try:
        form = SkillsForm(request.POST or None, request.FILES or None)
        if form.is_valid():
            form.save()
            messages.success(request, "Skill guardada correctamente")
            return redirect("skills")

        messages.warning(request, "No fue posible guardar la skill.")
        return render(
            request,
            "category/skills/create.html",
            {
                "form": form,
            },
        )

    except Exception as e:
        messages.warning(request, f"{str(e)}")
        return render(
            request,
            "category/skills/create.html",
            {
                "form": SkillsForm(request.POST or None, request.FILES or None),
            },
        )

def tags(request):
    q = (request.GET.get("q") or "").strip()

    # per_page
    try:
        per_page = int(request.GET.get("per_page", 50))
    except (TypeError, ValueError):
        per_page = 50
    per_page = max(1, min(per_page, 200))

    # page
    try:
        page_number = int(request.GET.get("page", 1))
    except (TypeError, ValueError):
        page_number = 1

    qs = CategoriaBlog.objects.all()

    if q:
        qs = qs.filter(
            Q(nombre_categoria_blog__icontains=q)
            | Q(tem_est__icontains=q)
        )

    qs = qs.only("id", "nombre_categoria_blog").order_by("id")

    paginator = Paginator(qs, per_page)
    page_obj = paginator.get_page(page_number)

    current = page_obj.number
    start_page = max(1, current - 3)
    end_page = min(paginator.num_pages, current + 3)
    page_numbers = range(start_page, end_page + 1)

    context = {
        "tags": page_obj.object_list,  # 👈 mantengo el nombre 'tags' para no tocar tu template mucho
        "page_obj": page_obj,
        "paginator": paginator,
        "per_page": per_page,
        "page_numbers": page_numbers,
        "show_inicio": start_page > 1,
        "show_final": end_page < paginator.num_pages,
        "per_page_options": [25, 50, 100, 200],
        "q": q,
    }
    return render(request, "category/tags/index.html", context)


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
    q = (request.GET.get("q") or "").strip()

    # per_page
    try:
        per_page = int(request.GET.get("per_page", 50))
    except (TypeError, ValueError):
        per_page = 50
    per_page = max(1, min(per_page, 200))

    # page
    try:
        page_number = int(request.GET.get("page", 1))
    except (TypeError, ValueError):
        page_number = 1

    qs = Original.objects.all()

    if q:
        qs = qs.filter(
            Q(name__icontains=q)
            | Q(slug__icontains=q)
            | Q(esta__icontains=q)
        )

    qs = qs.only("id", "name", "slug", "image", "esta").order_by("id")

    paginator = Paginator(qs, per_page)
    page_obj = paginator.get_page(page_number)

    current = page_obj.number
    start_page = max(1, current - 3)
    end_page = min(paginator.num_pages, current + 3)
    page_numbers = range(start_page, end_page + 1)

    context = {
        "originals": page_obj.object_list,
        "page_obj": page_obj,
        "paginator": paginator,
        "per_page": per_page,
        "page_numbers": page_numbers,
        "show_inicio": start_page > 1,
        "show_final": end_page < paginator.num_pages,
        "per_page_options": [25, 50, 100, 200],
        "q": q,
    }
    return render(request, "category/originals/index.html", context)

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
    q = (request.GET.get("q") or "").strip()

    # per_page
    try:
        per_page = int(request.GET.get("per_page", 50))
    except (TypeError, ValueError):
        per_page = 50
    per_page = max(1, min(per_page, 200))

    # page
    try:
        page_number = int(request.GET.get("page", 1))
    except (TypeError, ValueError):
        page_number = 1

    qs = Ranking.objects.all()

    if q:
        qs = qs.filter(
            Q(nombre__icontains=q)
            | Q(tipo__icontains=q)
            | Q(estado__icontains=q)
        )

    qs = qs.only("id", "nombre", "tipo", "estado", "fecha").order_by("-id")

    paginator = Paginator(qs, per_page)
    page_obj = paginator.get_page(page_number)

    current = page_obj.number
    start_page = max(1, current - 3)
    end_page = min(paginator.num_pages, current + 3)
    page_numbers = range(start_page, end_page + 1)

    context = {
        "rankings": page_obj.object_list,
        "page_obj": page_obj,
        "paginator": paginator,
        "per_page": per_page,
        "page_numbers": page_numbers,
        "show_inicio": start_page > 1,
        "show_final": end_page < paginator.num_pages,
        "per_page_options": [25, 50, 100, 200],
        "q": q,
    }
    return render(request, "category/rankings/index.html", context)

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
    base_url = "https://api-colombia-dev.universidad.top/course-information"

    return render(
        request,
        "catalog_inspector.html",
        {
            "base_url": base_url,
            "resource": request.GET.get("resource", "courses"),
            "resources": [
                "courses",
                "certifications",
                "skills-structure",
                "specializations",
                "specialization-detail",
            ],
        },
    )


@require_GET
def proxy_json(request):
    url = (request.GET.get("url") or "").strip()
    if not url:
        return HttpResponseBadRequest("Missing url")

    try:
        parsed = urlparse(url)
        host = (parsed.netloc or "").lower().split(":")[0]
    except Exception:
        return HttpResponseBadRequest("Invalid url")

    allowed_hosts = set((getattr(settings, "PROXY_HEADERS", {}) or {}).keys())
    if host not in allowed_hosts:
        return HttpResponseBadRequest("URL not allowed")

    headers = {
        "Accept": "application/json",
        "User-Agent": "TopEducation-Django-Proxy/1.0",
    }
    extra = (getattr(settings, "PROXY_HEADERS", {}) or {}).get(host, {}) or {}
    headers.update(extra)

    if "x-api-key" in headers and not headers["x-api-key"]:
        return JsonResponse(
            {
                "error": "missing_api_key_env",
                "detail": "COURSES_EXTERNAL_API_KEY  is empty in this environment",
            },
            status=500,
        )

    try:
        timeout = int(request.GET.get("timeout") or 180)

        r = requests.get(
            url,
            headers=headers,
            timeout=timeout,
        )

        content_type = (r.headers.get("content-type") or "").lower()
        text_preview = (r.text or "")[:8000]

        if "application/json" not in content_type:
            return JsonResponse(
                {
                    "error": "upstream_not_json",
                    "status": r.status_code,
                    "url": url,
                    "content_type": content_type,
                    "headers_sent": list(headers.keys()),
                    "has_api_key": bool(headers.get("x-api-key")),
                    "raw": text_preview,
                },
                status=502 if r.status_code >= 400 else 200,
            )

        data = r.json()
        return JsonResponse(
            data,
            status=r.status_code,
            safe=not isinstance(data, list),
        )

    except requests.exceptions.Timeout:
        return JsonResponse(
            {
                "error": "proxy_timeout",
                "detail": f"El proxy esperó {timeout}s y el endpoint no respondió.",
                "url": url,
            },
            status=504,
        )

    except requests.exceptions.RequestException as e:
        return JsonResponse(
            {
                "error": "proxy_request_failed",
                "detail": str(e),
                "url": url,
            },
            status=502,
        )

    except Exception as e:
        return JsonResponse(
            {
                "error": "proxy_failed",
                "detail": str(e),
                "url": url,
            },
            status=500,
        )
    
class FastNoCountPagination:
    page_size = 16
    page_size_query_param = "page_size"
    max_page_size = 50

    def paginate_queryset(self, queryset, request):
        self.request = request

        try:
            self.page = max(1, int(request.query_params.get("page", 1)))
        except Exception:
            self.page = 1

        try:
            self.page_size = int(request.query_params.get(self.page_size_query_param, self.page_size))
        except Exception:
            self.page_size = 16

        self.page_size = max(1, min(self.page_size, self.max_page_size))

        start = (self.page - 1) * self.page_size
        end = start + self.page_size + 1

        rows = list(queryset[start:end])

        self.has_next = len(rows) > self.page_size
        self.has_previous = self.page > 1

        return rows[:self.page_size]

    def get_paginated_response(self, data):
        return Response({
            "count": None,
            "current_page": self.page,
            "page_size": self.page_size,
            "has_next": self.has_next,
            "has_previous": self.has_previous,
            "results": data,
        })

class FastCachedCountPagination:
    page_size = 16
    page_size_query_param = "page_size"
    max_page_size = 50
    count_cache_timeout = 60 * 15  # 15 minutos

    def paginate_queryset(self, queryset, request):
        self.request = request

        try:
            self.page = max(1, int(request.query_params.get("page", 1)))
        except Exception:
            self.page = 1

        try:
            self.page_size = int(request.query_params.get(self.page_size_query_param, self.page_size))
        except Exception:
            self.page_size = 16

        self.page_size = max(1, min(self.page_size, self.max_page_size))

        cache_raw_key = f"cert_count:{request.get_full_path()}"
        cache_key = hashlib.md5(cache_raw_key.encode("utf-8")).hexdigest()
        cache_key = f"cert_count:{cache_key}"

        cached_count = cache.get(cache_key)

        if cached_count is None:
            cached_count = queryset.count()
            cache.set(cache_key, cached_count, self.count_cache_timeout)

        self.count = cached_count
        self.total_pages = max(1, (self.count + self.page_size - 1) // self.page_size)

        start = (self.page - 1) * self.page_size
        end = start + self.page_size

        return list(queryset[start:end])

    def get_paginated_response(self, data):
        return Response({
            "count": self.count,
            "current_page": self.page,
            "page_size": self.page_size,
            "total_pages": self.total_pages,
            "has_next": self.page < self.total_pages,
            "has_previous": self.page > 1,
            "results": data,
        })

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


class CertificationList(APIView):
    pagination_class = CustomPagination

    def get(self, request):
        tema_slugs = [s.strip() for s in request.GET.getlist("Tema") if s and s.strip()]
        habilidad_slugs = [s.strip() for s in request.GET.getlist("Habilidad") if s and s.strip()]

        # Compatibilidad opcional por si más adelante llega en minúscula
        if not tema_slugs:
            tema_slugs = [s.strip() for s in request.GET.getlist("temas") if s and s.strip()]

        if not habilidad_slugs:
            habilidad_slugs = [s.strip() for s in request.GET.getlist("habilidades") if s and s.strip()]

        skill_slugs = tema_slugs + habilidad_slugs

        # Primera skill de la certificación según el orden de la tabla intermedia
        first_skill_slug_subquery = SkillsCertification.objects.filter(
            certificacion_id=OuterRef("pk")
        ).order_by("orden", "id").values("skill__slug")[:1]

        certifications_queryset = (
            Certificaciones.objects.all()
            .select_related(
                "tema_certificacion",
                "plataforma_certificacion",
                "universidad_certificacion",
                "empresa_certificacion",
            )
            .prefetch_related(
                Prefetch(
                    "skills_rel",
                    queryset=SkillsCertification.objects.select_related("skill").order_by("orden", "id"),
                    to_attr="skills_links_ordered",
                )
            )
            .annotate(
                first_skill_slug=Subquery(first_skill_slug_subquery)
            )
        )

        if skill_slugs:
            # Trae todas las certificaciones relacionadas con cualquiera de los slugs seleccionados
            certifications_queryset = certifications_queryset.filter(
                skills_rel__skill__slug__in=skill_slugs
            ).distinct()

            # Si solo viene una skill, priorizamos las que la tienen de primera
            if len(skill_slugs) == 1:
                priority_slug = skill_slugs[0]

                certifications_queryset = certifications_queryset.annotate(
                    skill_priority=Case(
                        When(first_skill_slug=priority_slug, then=Value(0)),
                        default=Value(1),
                        output_field=IntegerField(),
                    )
                ).order_by("skill_priority", "-fecha_creado_cert", "-id")
            else:
                certifications_queryset = certifications_queryset.order_by("-fecha_creado_cert", "-id")
        else:
            certifications_queryset = certifications_queryset.order_by("-fecha_creado_cert", "-id")

        paginator = self.pagination_class()
        paginated_queryset = paginator.paginate_queryset(certifications_queryset, request)
        serializer = CertificationSerializer(paginated_queryset, many=True)

        return paginator.get_paginated_response(serializer.data)
    
#This view is to send the Masterclass certifications to display a masterclasss slider in frontend    
class MasterclassCertificationsGrids(APIView):
    
    def get(self, request):
        
        amount = int(request.query_params.get('amount', 3))
        masterclass_certifications_queryset = Certificaciones.objects.filter(plataforma_certificacion_id = 3)[:amount]
        serializer = CertificationSerializer(masterclass_certifications_queryset, many = True)
        return Response (serializer.data, status=status.HTTP_200_OK)     

class SuggestedCertificationsGrid(APIView):

    def get(self, request):
        amount = int(request.query_params.get("amount", 6))

        qs = (
            Certificaciones.objects
            .filter(vigente_certificacion=True)
            .select_related(
                "plataforma_certificacion",
                "universidad_certificacion",
                "empresa_certificacion",
            )
            .prefetch_related(
                Prefetch(
                    "skills_rel",
                    queryset=(
                        SkillsCertification.objects
                        .select_related("skill")
                        .only(
                            "id",
                            "certificacion_id",
                            "skill_id",
                            "orden",
                            "skill__id",
                            "skill__nombre",
                            "skill__translate",
                            "skill__slug",
                            "skill__skill_col",
                            "skill__skill_type",
                            "skill__skill_ico",
                            "skill__skill_img",
                        )
                        .order_by("orden", "id")
                    ),
                    to_attr="skills_links_ordered",
                )
            )
            .only(
                "id",
                "slug",
                "nombre",
                "imagen_final",
                "tipo_certificacion",
                "nivel_certificacion",
                "tiempo_certificacion",
                "vigente_certificacion",

                "plataforma_certificacion_id",
                "plataforma_certificacion__id",
                "plataforma_certificacion__nombre",
                "plataforma_certificacion__plat_ico",

                "universidad_certificacion_id",
                "universidad_certificacion__id",
                "universidad_certificacion__nombre",
                "universidad_certificacion__univ_ico",

                "empresa_certificacion_id",
                "empresa_certificacion__id",
                "empresa_certificacion__nombre",
                "empresa_certificacion__empr_ico",
            )
            .order_by("-id")[:amount]
        )

        serializer = SuggestedCertificationSerializer(
            qs,
            many=True,
            context={"request": request}
        )

        return Response(serializer.data, status=status.HTTP_200_OK)

class CertificationsCafam(APIView):
    
    def get(self, request):
        #Recibir el parametro de la cantidad de certificaciones
        amount = int(request.query_params.get('amount', 7))
        #Consultar las certificaciones limitando la cantidad
        certificationsCafam_queryset = Certificaciones.objects.all()[:amount]
        serializer = CertificationSerializer(certificationsCafam_queryset, many = True)
        
        return Response(serializer.data, status=status.HTTP_200_OK)
    

class RelatedCertificationsGrid(APIView):

    def get(self, request, slug):
        amount = int(request.query_params.get("amount", 9))

        try:
            current_certification = (
                Certificaciones.objects
                .prefetch_related(
                    Prefetch(
                        "skills_rel",
                        queryset=SkillsCertification.objects.select_related("skill").only(
                            "id",
                            "certificacion_id",
                            "skill_id",
                            "orden",
                            "skill__id",
                            "skill__slug",
                        ).order_by("orden", "id"),
                        to_attr="skills_links_ordered",
                    )
                )
                .select_related(
                    "plataforma_certificacion",
                    "universidad_certificacion",
                    "empresa_certificacion",
                )
                .only(
                    "id",
                    "slug",
                    "universidad_certificacion_id",
                    "empresa_certificacion_id",
                    "plataforma_certificacion_id",
                )
                .get(slug=slug)
            )
        except Certificaciones.DoesNotExist:
            return Response(
                {"detail": "Certificación no encontrada"},
                status=status.HTTP_404_NOT_FOUND
            )

        skill_ids = [
            link.skill_id
            for link in getattr(current_certification, "skills_links_ordered", [])
            if link.skill_id
        ]

        related_filter = Q(vigente_certificacion=True) & ~Q(id=current_certification.id)

        if skill_ids:
            related_filter &= Q(skills_rel__skill_id__in=skill_ids)

        qs = (
            Certificaciones.objects
            .filter(related_filter)
            .select_related(
                "plataforma_certificacion",
                "universidad_certificacion",
                "empresa_certificacion",
            )
            .prefetch_related(
                Prefetch(
                    "skills_rel",
                    queryset=(
                        SkillsCertification.objects
                        .select_related("skill")
                        .only(
                            "id",
                            "certificacion_id",
                            "skill_id",
                            "orden",
                            "skill__id",
                            "skill__nombre",
                            "skill__translate",
                            "skill__slug",
                            "skill__skill_col",
                            "skill__skill_type",
                            "skill__skill_ico",
                            "skill__skill_img",
                        )
                        .order_by("orden", "id")
                    ),
                    to_attr="skills_links_ordered",
                )
            )
            .only(
                "id",
                "slug",
                "nombre",
                "imagen_final",
                "tipo_certificacion",
                "nivel_certificacion",
                "tiempo_certificacion",
                "vigente_certificacion",

                "plataforma_certificacion_id",
                "plataforma_certificacion__id",
                "plataforma_certificacion__nombre",
                "plataforma_certificacion__plat_ico",

                "universidad_certificacion_id",
                "universidad_certificacion__id",
                "universidad_certificacion__nombre",
                "universidad_certificacion__univ_ico",

                "empresa_certificacion_id",
                "empresa_certificacion__id",
                "empresa_certificacion__nombre",
                "empresa_certificacion__empr_ico",
            )
            .annotate(
                related_score=Count(
                    "skills_rel",
                    filter=Q(skills_rel__skill_id__in=skill_ids),
                    distinct=True,
                )
            )
            .order_by("-related_score", "-id")
            .distinct()[:amount]
        )

        if not qs:
            qs = (
                Certificaciones.objects
                .filter(vigente_certificacion=True)
                .exclude(id=current_certification.id)
                .select_related(
                    "plataforma_certificacion",
                    "universidad_certificacion",
                    "empresa_certificacion",
                )
                .prefetch_related(
                    Prefetch(
                        "skills_rel",
                        queryset=(
                            SkillsCertification.objects
                            .select_related("skill")
                            .only(
                                "id",
                                "certificacion_id",
                                "skill_id",
                                "orden",
                                "skill__id",
                                "skill__nombre",
                                "skill__translate",
                                "skill__slug",
                                "skill__skill_col",
                                "skill__skill_type",
                                "skill__skill_ico",
                                "skill__skill_img",
                            )
                            .order_by("orden", "id")
                        ),
                        to_attr="skills_links_ordered",
                    )
                )
                .only(
                    "id",
                    "slug",
                    "nombre",
                    "imagen_final",
                    "tipo_certificacion",
                    "nivel_certificacion",
                    "tiempo_certificacion",
                    "vigente_certificacion",
                    "plataforma_certificacion_id",
                    "plataforma_certificacion__id",
                    "plataforma_certificacion__nombre",
                    "plataforma_certificacion__plat_ico",
                    "universidad_certificacion_id",
                    "universidad_certificacion__id",
                    "universidad_certificacion__nombre",
                    "universidad_certificacion__univ_ico",
                    "empresa_certificacion_id",
                    "empresa_certificacion__id",
                    "empresa_certificacion__nombre",
                    "empresa_certificacion__empr_ico",
                )
                .order_by("-id")[:amount]
            )

        serializer = SuggestedCertificationSerializer(
            qs,
            many=True,
            context={"request": request}
        )

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

class SkillsList(APIView):

    def get(self, request):
        q = (request.GET.get("q") or "").strip()

        skills_queryset = Skills.objects.all()

        if q:
            skills_queryset = skills_queryset.filter(
                Q(nombre__icontains=q) |
                Q(translate__icontains=q) |
                Q(skill_type__icontains=q)
            )

        skills_queryset = skills_queryset.order_by("parent_id", "nombre")

        data = list(
            skills_queryset.values(
                "id",
                "nombre",
                "translate",
                "slug",
                "skill_img",
                "skill_ico",
                "skill_col",
                "skill_type",
                "estado",
                "parent_id",
            )
        )

        for item in data:
            item["parent"] = item.get("parent_id")

        return Response(data, status=status.HTTP_200_OK)

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

class OriginalsSliderView(APIView):

    def get(self, request):
        originals = (
            Original.objects
            .all()
            .only("id", "name", "slug", "extr", "esta", "image")
            .order_by("id")
        )

        serializer = OriginalSliderSerializer(
            originals,
            many=True,
            context={"request": request},
        )

        return Response(serializer.data, status=status.HTTP_200_OK)
    
@method_decorator(cache_page(60 * 60), name="dispatch")
class UniversitiesByRegion(APIView):
    def get(self, request):
        universities = Universidades.objects.select_related('region_universidad').filter(univ_est="enabled")
        grouped = defaultdict(list)

        for uni in universities:
            region_name = uni.region_universidad.nombre if uni.region_universidad else "Sin región"
            grouped[region_name].append({
                'id': uni.id,
                'nombre': uni.nombre,
                'descripcion_institucion': uni.descripcion_institucion,
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

class CertificationDetailView(APIView):
    def get(self, request, slug):
        if not slug:
            return Response(
                {"error": "Se requiere slug de certificación"},
                status=status.HTTP_400_BAD_REQUEST
            )

        try:
            certification = (
                Certificaciones.objects
                .select_related(
                    "tema_certificacion",
                    "plataforma_certificacion",
                    "universidad_certificacion",
                    "empresa_certificacion",
                    "specialization",
                )
                .prefetch_related(
                    Prefetch(
                        "skills_rel",
                        queryset=(
                            SkillsCertification.objects
                            .select_related("skill")
                            .order_by("orden", "id")
                        ),
                        to_attr="skills_links_ordered",
                    ),
                    Prefetch(
                        "instructor_links",
                        queryset=(
                            InstructorCertification.objects
                            .select_related("instructor")
                        ),
                        to_attr="instructor_links_prefetched",
                    ),
                )
                .get(slug=slug)
            )

            serializer = CertificationSerializer(
                certification,
                context={"request": request}
            )

            return Response(serializer.data, status=status.HTTP_200_OK)

        except Certificaciones.DoesNotExist:
            return Response(
                {"error": "Certificación no encontrada"},
                status=status.HTTP_404_NOT_FOUND
            )

        except Exception as e:
            print(f"Error en CertificationDetailView: {str(e)}")
            return Response(
                {"error": "Error al cargar la certificación"},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )
        
@method_decorator(cache_page(60 * 60), name="dispatch")
class SkillsFilterMiniView(APIView):
    def get(self, request):
        qs = (
            Skills.objects
            .filter(estado=True)
            .only(
                "id",
                "nombre",
                "translate",
                "slug",
                "skill_ico",
                "skill_img",
                "skill_col",
                "skill_type",
                "estado",
                "parent_id",
            )
            .order_by("parent_id", "nombre")
        )

        serializer = SkillFilterMiniSerializer(qs, many=True)
        return Response(serializer.data)

@method_decorator(cache_page(60 * 60), name="dispatch")
class CompaniesFilterMiniView(APIView):
    def get(self, request):
        qs = (
            Empresas.objects
            .filter(empr_est="enabled")
            .only("id", "nombre", "empr_ico", "empr_img")
            .order_by("nombre")
        )

        serializer = CompanyFilterMiniSerializer(qs, many=True)
        return Response(serializer.data)

@method_decorator(cache_page(60 * 60), name="dispatch")
class PlatformsFilterMiniView(APIView):
    def get(self, request):
        qs = (
            Plataformas.objects
            .only("id", "nombre", "plat_ico")
            .order_by("nombre")
        )

        serializer = PlatformFilterMiniSerializer(qs, many=True)
        return Response(serializer.data)

class UniversitiesByRegionMiniView(APIView):
    def get(self, request):
        universidades = (
            Universidades.objects
            .filter(univ_est="enabled")
            .select_related("region_universidad")
            .only(
                "id",
                "nombre",
                "univ_ico",
                "univ_img",
                "region_universidad_id",
                "region_universidad__id",
                "region_universidad__nombre",
            )
            .order_by("region_universidad__nombre", "nombre")
        )

        grouped = {}

        for uni in universidades:
            region = (
                uni.region_universidad.nombre
                if uni.region_universidad
                else "Del mundo"
            )

            grouped.setdefault(region, []).append({
                "id": uni.id,
                "nombre": uni.nombre,
                "univ_ico": uni.univ_ico,
                "univ_img": uni.univ_img,
                "region_universidad_id": uni.region_universidad_id,
            })

        return Response(grouped)

@method_decorator(csrf_exempt, name="dispatch")
class PersonalizedRecommendations(APIView):

    authentication_classes = []
    permission_classes = []

    def post(self, request):
        topics = request.data.get("topics", []) or []
        goal = request.data.get("goal", "") or ""
        amount = int(request.data.get("amount", 6))

        search_terms = list(topics)

        if goal:
            search_terms.append(goal)

        qs = Certificaciones.objects.filter(
            vigente_certificacion=True
        ).select_related(
            "plataforma_certificacion",
            "universidad_certificacion",
            "empresa_certificacion",
        ).prefetch_related(
            "skills_rel__skill"
        )

        topic_q = Q()

        for term in search_terms:
            clean_term = str(term).strip()

            if not clean_term:
                continue

            topic_q |= Q(skills_rel__skill__nombre__icontains=clean_term)
            topic_q |= Q(skills_rel__skill__translate__icontains=clean_term)
            topic_q |= Q(skills_rel__skill__slug__icontains=slugify(clean_term))

        if topic_q:
            qs = qs.filter(topic_q).distinct()

        if not qs.exists():
            qs = (
                Certificaciones.objects
                .filter(vigente_certificacion=True)
                .select_related(
                    "plataforma_certificacion",
                    "universidad_certificacion",
                    "empresa_certificacion",
                )
                .order_by("-id")
            )

        qs = qs[:amount]

        serializer = PersonalizedRecommendationSerializer(
            qs,
            many=True,
            context={"request": request}
        )

        return Response(serializer.data, status=status.HTTP_200_OK)

LANGUAGE_NORMALIZATION = {
    "es": {
        "label": "Español",
        "values": ["es", "spanish", "enseñado en español", "español"],
    },
    "en": {
        "label": "Inglés",
        "values": ["en", "english", "enseñado en inglés (22 idiomas disponibles)", "inglés"],
    },
    "ar": {
        "label": "Árabe",
        "values": ["ar", "arabic"],
    },
    "bn": {
        "label": "Bengalí",
        "values": ["bn", "bengali"],
    },
    "ca": {
        "label": "Catalán",
        "values": ["ca", "catalan"],
    },
    "zh": {
        "label": "Chino",
        "values": [
            "zh",
            "zh-cn",
            "zh-tw",
            "chinese - china",
            "chinese - mandarin",
            "chinese - simplified",
            "chinese",
        ],
    },
    "de": {
        "label": "Alemán",
        "values": ["de", "german"],
    },
    "nl": {
        "label": "Neerlandés",
        "values": ["nl", "dutch"],
    },
    "fa": {
        "label": "Persa",
        "values": ["fa", "farsi"],
    },
    "fr": {
        "label": "Francés",
        "values": ["fr", "french"],
    },
    "he": {
        "label": "Hebreo",
        "values": ["he", "hebrew"],
    },
    "hi": {
        "label": "Hindi",
        "values": ["hi", "hindi"],
    },
    "hu": {
        "label": "Húngaro",
        "values": ["hu", "hungarian"],
    },
    "id": {
        "label": "Indonesio",
        "values": ["id", "indonesian"],
    },
    "it": {
        "label": "Italiano",
        "values": ["it", "italian"],
    },
    "ja": {
        "label": "Japonés",
        "values": ["ja", "japanese"],
    },
    "kk": {
        "label": "Kazajo",
        "values": ["kk", "kazakh"],
    },
    "ko": {
        "label": "Coreano",
        "values": ["ko", "korean"],
    },
    "dv": {
        "label": "Maldivo",
        "values": ["dv", "maldivian"],
    },
    "pl": {
        "label": "Polaco",
        "values": ["pl", "polish"],
    },
    "pt": {
        "label": "Portugués",
        "values": ["pt", "pt-br", "pt-pt", "portuguese"],
    },
    "ru": {
        "label": "Ruso",
        "values": ["ru", "russian"],
    },
    "sv": {
        "label": "Sueco",
        "values": ["sv", "swedish"],
    },
    "sw": {
        "label": "Suajili",
        "values": ["sw", "swahili"],
    },
    "th": {
        "label": "Tailandés",
        "values": ["th", "thai"],
    },
    "tr": {
        "label": "Turco",
        "values": ["tr", "turkish"],
    },
    "uk": {
        "label": "Ucraniano",
        "values": ["uk", "ukrainian"],
    },
    "ur": {
        "label": "Urdu",
        "values": ["ur", "urdu"],
    },
}

IGNORED_LANGUAGE_VALUES = {"", "none", "null", "-", "n/a"}


def normalize_language_value(raw_value):
    raw = (raw_value or "").strip().lower()

    if raw in IGNORED_LANGUAGE_VALUES:
        return None

    for code, config in LANGUAGE_NORMALIZATION.items():
        values = config.get("values", [])

        for value in values:
            v = str(value or "").strip().lower()

            if not v:
                continue

            if raw == v or v in raw:
                return {
                    "code": code,
                    "label": config["label"],
                }

    return None


def split_language_values(raw_value):
    if not raw_value:
        return []

    return [
        item.strip()
        for item in str(raw_value).split(",")
        if item and item.strip()
    ]

class CertificationLanguagesList(APIView):
    def get(self, request):
        try:
            cache_key = "certification_languages_v2"
            cached = cache.get(cache_key)

            if cached is not None:
                return Response(cached, status=status.HTTP_200_OK)

            rows = (
                Certificaciones.objects
                .exclude(language_normalized__isnull=True)
                .exclude(language_normalized__exact="")
                .values("language_normalized")
                .annotate(count=Count("id"))
                .order_by("language_normalized")
            )

            grouped = {
                row["language_normalized"]: row["count"]
                for row in rows
                if row["language_normalized"] in LANGUAGE_NORMALIZATION
            }

            ordered_codes = ["es", "en"] + sorted(
                [code for code in grouped.keys() if code not in {"es", "en"}]
            )

            data = [
                {
                    "code": code,
                    "label": LANGUAGE_NORMALIZATION[code]["label"],
                    "count": grouped[code],
                    "checked_by_default": code in {"es", "en"},
                }
                for code in ordered_codes
                if code in grouped
            ]

            cache.set(cache_key, data, 60 * 60 * 6)

            return Response(data, status=status.HTTP_200_OK)

        except Exception as e:
            print(f"Error en CertificationLanguagesList: {str(e)}")
            return Response(
                {"error": "Error al cargar idiomas"},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )
        
def get_language_values_by_codes(codes):
    values = []

    for code in codes:
        config = LANGUAGE_NORMALIZATION.get(code, {})
        values.extend(config.get("values", []))

    return list(dict.fromkeys(values))

@method_decorator(cache_page(60 * 15), name="dispatch")
class filter_by_tags(APIView):
    pagination_class = FastCachedCountPagination

    def get(self, request):
        try:
            params = request.query_params.copy()

            tema_slugs = []
            habilidad_slugs = []
            plataforma_values = []
            empresa_values = []
            universidad_values = []
            plataforma_ids = []
            empresa_ids = []
            universidad_ids = []
            idioma_codes = []

            def append_clean_values(target, value_list, lower=False, only_int=False):
                for value in value_list:
                    if not isinstance(value, str):
                        continue

                    for v in value.split(","):
                        cleaned = v.strip()
                        if not cleaned:
                            continue

                        if lower:
                            cleaned = cleaned.lower()

                        if only_int:
                            try:
                                target.append(int(cleaned))
                            except (TypeError, ValueError):
                                continue
                        else:
                            target.append(cleaned)

            for key, value_list in params.lists():
                if key in ["page", "page_size"]:
                    continue

                if key in ["Tema", "temas"]:
                    append_clean_values(tema_slugs, value_list)

                elif key in ["Habilidad", "habilidades"]:
                    append_clean_values(habilidad_slugs, value_list)

                elif key in ["Plataforma", "plataforma", "Aliados", "aliados"]:
                    append_clean_values(plataforma_values, value_list)

                elif key in ["Empresa", "empresas", "Empresas"]:
                    append_clean_values(empresa_values, value_list)

                elif key in ["Universidad", "universidades", "Universidades"]:
                    append_clean_values(universidad_values, value_list)

                elif key in ["plataforma_id", "Plataforma_id", "platform_id"]:
                    append_clean_values(plataforma_ids, value_list, only_int=True)

                elif key in ["empresa_id", "Empresa_id", "company_id"]:
                    append_clean_values(empresa_ids, value_list, only_int=True)

                elif key in ["universidad_id", "Universidad_id", "university_id"]:
                    append_clean_values(universidad_ids, value_list, only_int=True)

                elif key in ["Idioma", "idioma"]:
                    append_clean_values(idioma_codes, value_list, lower=True)

            tema_slugs = list(dict.fromkeys(tema_slugs))
            habilidad_slugs = list(dict.fromkeys(habilidad_slugs))
            plataforma_values = list(dict.fromkeys(plataforma_values))
            empresa_values = list(dict.fromkeys(empresa_values))
            universidad_values = list(dict.fromkeys(universidad_values))
            plataforma_ids = list(dict.fromkeys(plataforma_ids))
            empresa_ids = list(dict.fromkeys(empresa_ids))
            universidad_ids = list(dict.fromkeys(universidad_ids))
            idioma_codes = list(dict.fromkeys(idioma_codes))

            skill_slugs = tema_slugs + habilidad_slugs

            queryset = (
                Certificaciones.objects
                .select_related(
                    "plataforma_certificacion",
                    "universidad_certificacion",
                    "empresa_certificacion",
                )
                .prefetch_related(
                    Prefetch(
                        "skills_rel",
                        queryset=(
                            SkillsCertification.objects
                            .select_related("skill")
                            .only(
                                "id",
                                "certificacion_id",
                                "skill_id",
                                "orden",
                                "skill__id",
                                "skill__nombre",
                                "skill__translate",
                                "skill__slug",
                                "skill__skill_col",
                                "skill__skill_type",
                                "skill__skill_ico",
                                "skill__skill_img",
                            )
                            .order_by("orden", "id")
                        ),
                        to_attr="skills_links_ordered",
                    )
                )
                .only(
                    "id",
                    "slug",
                    "nombre",
                    "imagen_final",
                    "tipo_certificacion",
                    "nivel_certificacion",
                    "tiempo_certificacion",
                    "language_normalized",
                    "fecha_creado_cert",
                    "vigente_certificacion",

                    "plataforma_certificacion_id",
                    "plataforma_certificacion__id",
                    "plataforma_certificacion__nombre",
                    "plataforma_certificacion__plat_ico",

                    "universidad_certificacion_id",
                    "universidad_certificacion__id",
                    "universidad_certificacion__nombre",
                    "universidad_certificacion__univ_ico",
                    "universidad_certificacion__univ_img",

                    "empresa_certificacion_id",
                    "empresa_certificacion__id",
                    "empresa_certificacion__nombre",
                    "empresa_certificacion__empr_ico",
                    "empresa_certificacion__empr_img",
                )
            )

            if plataforma_ids:
                queryset = queryset.filter(
                    plataforma_certificacion_id__in=plataforma_ids
                )
            elif plataforma_values:
                q_plataforma = Q()
                for value in plataforma_values:
                    q_plataforma |= Q(plataforma_certificacion__nombre__iexact=value)
                queryset = queryset.filter(q_plataforma)

            if empresa_ids:
                queryset = queryset.filter(
                    empresa_certificacion_id__in=empresa_ids
                )
            elif empresa_values:
                q_empresa = Q()
                for value in empresa_values:
                    q_empresa |= Q(empresa_certificacion__nombre__iexact=value)
                queryset = queryset.filter(q_empresa)

            if universidad_ids:
                queryset = queryset.filter(
                    universidad_certificacion_id__in=universidad_ids
                )
            elif universidad_values:
                q_universidad = Q()
                for value in universidad_values:
                    q_universidad |= Q(universidad_certificacion__nombre__iexact=value)
                queryset = queryset.filter(q_universidad)

            if idioma_codes:
                queryset = queryset.filter(language_normalized__in=idioma_codes)
            else:
                queryset = queryset.filter(language_normalized__in=["es"])

            if skill_slugs:
                first_skill_slug_subquery = (
                    SkillsCertification.objects
                    .filter(certificacion_id=OuterRef("pk"))
                    .order_by("orden", "id")
                    .values("skill__slug")[:1]
                )

                queryset = queryset.annotate(
                    first_skill_slug=Subquery(first_skill_slug_subquery)
                )

                queryset = queryset.filter(
                    skills_rel__skill__slug__in=skill_slugs
                )

                if len(skill_slugs) == 1:
                    priority_slug = skill_slugs[0]

                    queryset = queryset.annotate(
                        skill_priority=Case(
                            When(first_skill_slug=priority_slug, then=Value(0)),
                            default=Value(1),
                            output_field=IntegerField(),
                        )
                    ).order_by("skill_priority", "-fecha_creado_cert", "-id")
                else:
                    queryset = queryset.order_by("-fecha_creado_cert", "-id")

                queryset = queryset.distinct()
            else:
                queryset = queryset.order_by("-fecha_creado_cert", "-id")

            paginator = self.pagination_class()
            paginated_queryset = paginator.paginate_queryset(queryset, request)

            serializer = SuggestedCertificationSerializer(
                paginated_queryset,
                many=True,
                context={"request": request}
            )

            return paginator.get_paginated_response(serializer.data)

        except Exception as e:
            print(f"Error en filter_by_tags: {str(e)}")
            return Response(
                {"error": "Error al filtrar certificaciones"},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )

class filter_by_search(APIView):
    def post(self, request):
        query_string = (request.data.get("data") or "").strip()
        limit = request.data.get("limit", 12)
        filters = request.data.get("filters", {}) or {}

        try:
            limit = int(limit)
        except (TypeError, ValueError):
            limit = 12

        limit = max(1, min(limit, 24))

        if not query_string or len(query_string) < 3:
            return Response({"results": [], "count": 0}, status=status.HTTP_200_OK)

        idioma_values = filters.get("idioma", []) or []
        plataforma_values = filters.get("Plataforma", []) or []
        empresa_values = filters.get("Empresa", []) or []
        universidad_values = filters.get("Universidad", []) or []
        tema_values = filters.get("Tema", []) or []
        habilidad_values = filters.get("Habilidad", []) or []

        skill_slugs = tema_values + habilidad_values

        try:
            search_filter = (
                Q(nombre__icontains=query_string) |
                Q(metadescripcion_certificacion__icontains=query_string) |
                Q(slug__icontains=query_string) |
                Q(tema_certificacion__nombre__icontains=query_string) |
                Q(tema_certificacion__translate__icontains=query_string) |
                Q(universidad_certificacion__nombre__icontains=query_string) |
                Q(empresa_certificacion__nombre__icontains=query_string) |
                Q(plataforma_certificacion__nombre__icontains=query_string) |
                Q(skills_rel__skill__nombre__icontains=query_string) |
                Q(skills_rel__skill__translate__icontains=query_string) |
                Q(habilidades_certificacion__icontains=query_string)
            )

            ids_queryset = Certificaciones.objects.filter(search_filter)

            if plataforma_values:
                q_plataforma = Q()
                for value in plataforma_values:
                    q_plataforma |= Q(plataforma_certificacion__nombre__iexact=value)
                ids_queryset = ids_queryset.filter(q_plataforma)

            if empresa_values:
                q_empresa = Q()
                for value in empresa_values:
                    q_empresa |= Q(empresa_certificacion__nombre__iexact=value)
                ids_queryset = ids_queryset.filter(q_empresa)

            if universidad_values:
                q_universidad = Q()
                for value in universidad_values:
                    q_universidad |= Q(universidad_certificacion__nombre__iexact=value)
                ids_queryset = ids_queryset.filter(q_universidad)

            if idioma_values:
                normalized_langs = []

                for value in idioma_values:
                    lang = (value or "").strip().lower()

                    if lang in ["es", "spanish", "español"]:
                        normalized_langs.append("es")
                    elif lang in ["en", "english", "inglés", "ingles"]:
                        normalized_langs.append("en")
                    elif lang:
                        normalized_langs.append(lang)

                if normalized_langs:
                    ids_queryset = ids_queryset.filter(
                        language_normalized__in=list(dict.fromkeys(normalized_langs))
                    )
            else:
                ids_queryset = ids_queryset.filter(language_normalized__in=["es"])

            if skill_slugs:
                q_skills = Q()

                for value in skill_slugs:
                    q_skills |= Q(skills_rel__skill__slug__iexact=value)
                    q_skills |= Q(skills_rel__skill__nombre__iexact=value)
                    q_skills |= Q(skills_rel__skill__translate__iexact=value)
                    q_skills |= Q(tema_certificacion__nombre__iexact=value)
                    q_skills |= Q(tema_certificacion__translate__iexact=value)

                ids_queryset = ids_queryset.filter(q_skills)

            ids_queryset = (
                ids_queryset
                .annotate(
                    search_priority=Case(
                        When(nombre__istartswith=query_string, then=Value(1)),
                        When(skills_rel__skill__nombre__istartswith=query_string, then=Value(2)),
                        When(skills_rel__skill__translate__istartswith=query_string, then=Value(2)),
                        When(tema_certificacion__nombre__istartswith=query_string, then=Value(3)),
                        When(tema_certificacion__translate__istartswith=query_string, then=Value(3)),
                        When(universidad_certificacion__nombre__istartswith=query_string, then=Value(4)),
                        When(empresa_certificacion__nombre__istartswith=query_string, then=Value(5)),
                        default=Value(99),
                        output_field=IntegerField(),
                    )
                )
                .values("id", "search_priority", "nombre")
                .order_by("search_priority", "nombre")
                .distinct()[:limit]
            )

            rows = list(ids_queryset)
            ids = [row["id"] for row in rows]

            if not ids:
                return Response({"results": [], "count": 0}, status=status.HTTP_200_OK)

            preserved_order = Case(
                *[When(id=pk, then=pos) for pos, pk in enumerate(ids)],
                output_field=IntegerField(),
            )

            queryset = (
                Certificaciones.objects
                .filter(id__in=ids)
                .select_related(
                    "tema_certificacion",
                    "plataforma_certificacion",
                    "universidad_certificacion",
                    "empresa_certificacion",
                )
                .prefetch_related(
                    Prefetch(
                        "skills_rel",
                        queryset=(
                            SkillsCertification.objects
                            .select_related("skill")
                            .only(
                                "id",
                                "certificacion_id",
                                "skill_id",
                                "orden",
                                "skill__id",
                                "skill__nombre",
                                "skill__translate",
                                "skill__slug",
                                "skill__skill_col",
                                "skill__skill_type",
                                "skill__skill_ico",
                                "skill__skill_img",
                            )
                            .order_by("orden", "id")
                        ),
                        to_attr="skills_links_ordered",
                    )
                )
                .only(
                    "id",
                    "slug",
                    "nombre",
                    "imagen_final",
                    "tipo_certificacion",
                    "nivel_certificacion",
                    "tiempo_certificacion",
                    "language_normalized",
                    "fecha_creado_cert",
                    "vigente_certificacion",

                    "plataforma_certificacion_id",
                    "plataforma_certificacion__id",
                    "plataforma_certificacion__nombre",
                    "plataforma_certificacion__plat_ico",

                    "universidad_certificacion_id",
                    "universidad_certificacion__id",
                    "universidad_certificacion__nombre",
                    "universidad_certificacion__univ_ico",
                    "universidad_certificacion__univ_img",

                    "empresa_certificacion_id",
                    "empresa_certificacion__id",
                    "empresa_certificacion__nombre",
                    "empresa_certificacion__empr_ico",
                    "empresa_certificacion__empr_img",

                    "tema_certificacion_id",
                    "tema_certificacion__id",
                    "tema_certificacion__nombre",
                    "tema_certificacion__translate",
                    "tema_certificacion__tem_img",
                )
                .order_by(preserved_order)
            )

            results = list(queryset)

        except Exception as e:
            print("Error en filter_by_search:", e)
            return Response(
                {
                    "error": str(e),
                    "results": [],
                    "count": 0,
                },
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )

        serializer = CertificationSearchSerializer(
            results,
            many=True,
            context={"request": request},
        )

        return Response(
            {
                "results": serializer.data,
                "count": len(results),
            },
            status=status.HTTP_200_OK,
        )
        
class QuickCertificationSearchAPIView(APIView):
    permission_classes = []

    def post(self, request):
        query_string = (request.data.get("data") or "").strip()
        limit = request.data.get("limit", 8)

        try:
            limit = int(limit)
        except (TypeError, ValueError):
            limit = 8

        limit = max(1, min(limit, 12))

        if not query_string or len(query_string) < 3:
            return Response({"results": [], "count": 0}, status=status.HTTP_200_OK)

        search_filter = (
            Q(nombre__icontains=query_string) |
            Q(slug__icontains=query_string) |
            Q(universidad_certificacion__nombre__icontains=query_string) |
            Q(empresa_certificacion__nombre__icontains=query_string) |
            Q(plataforma_certificacion__nombre__icontains=query_string) |
            Q(skills_rel__skill__nombre__icontains=query_string) |
            Q(skills_rel__skill__translate__icontains=query_string)
        )

        rows = list(
            Certificaciones.objects
            .filter(search_filter)
            .filter(language_normalized__in=["es"])
            .annotate(
                search_priority=Case(
                    When(nombre__istartswith=query_string, then=Value(1)),
                    When(skills_rel__skill__nombre__istartswith=query_string, then=Value(2)),
                    When(skills_rel__skill__translate__istartswith=query_string, then=Value(2)),
                    When(universidad_certificacion__nombre__istartswith=query_string, then=Value(3)),
                    When(empresa_certificacion__nombre__istartswith=query_string, then=Value(4)),
                    When(plataforma_certificacion__nombre__istartswith=query_string, then=Value(5)),
                    default=Value(99),
                    output_field=IntegerField(),
                )
            )
            .values("id", "search_priority", "nombre")
            .order_by("search_priority", "nombre")
            .distinct()[:limit]
        )

        ids = [row["id"] for row in rows]

        if not ids:
            return Response({"results": [], "count": 0}, status=status.HTTP_200_OK)

        preserved_order = Case(
            *[When(id=pk, then=pos) for pos, pk in enumerate(ids)],
            output_field=IntegerField(),
        )

        certs = (
            Certificaciones.objects
            .filter(id__in=ids)
            .select_related(
                "plataforma_certificacion",
                "universidad_certificacion",
                "empresa_certificacion",
            )
            .only(
                "id",
                "nombre",
                "slug",
                "imagen_final",

                "plataforma_certificacion_id",
                "plataforma_certificacion__id",
                "plataforma_certificacion__nombre",
                "plataforma_certificacion__plat_ico",
                "plataforma_certificacion__plat_img",

                "universidad_certificacion_id",
                "universidad_certificacion__id",
                "universidad_certificacion__nombre",
                "universidad_certificacion__univ_ico",
                "universidad_certificacion__univ_img",

                "empresa_certificacion_id",
                "empresa_certificacion__id",
                "empresa_certificacion__nombre",
                "empresa_certificacion__empr_ico",
                "empresa_certificacion__empr_img",
            )
            .order_by(preserved_order)
        )

        results = []

        for cert in certs:
            plataforma = cert.plataforma_certificacion
            universidad = cert.universidad_certificacion
            empresa = cert.empresa_certificacion

            platform_name = getattr(plataforma, "nombre", "") or ""
            platform_slug = platform_name.strip().lower()

            if platform_slug == "edx.org":
                platform_slug = "edx"

            image = (
                getattr(universidad, "univ_ico", None)
                or getattr(universidad, "univ_img", None)
                or getattr(empresa, "empr_ico", None)
                or getattr(empresa, "empr_img", None)
                or getattr(plataforma, "plat_ico", None)
                or getattr(plataforma, "plat_img", None)
                or cert.imagen_final
                or ""
            )

            results.append({
                "id": cert.id,
                "nombre": cert.nombre,
                "slug": cert.slug,
                "image": image,
                "url": (
                    f"/certificacion/{platform_slug}/{cert.slug}"
                    if platform_slug
                    else f"/certificacion/{cert.slug}"
                ),
                "plataforma_certificacion": {
                    "id": getattr(plataforma, "id", None),
                    "nombre": platform_name,
                } if plataforma else None,
                "universidad_certificacion": {
                    "id": getattr(universidad, "id", None),
                    "nombre": getattr(universidad, "nombre", ""),
                    "univ_ico": getattr(universidad, "univ_ico", ""),
                    "univ_img": getattr(universidad, "univ_img", ""),
                } if universidad else None,
                "empresa_certificacion": {
                    "id": getattr(empresa, "id", None),
                    "nombre": getattr(empresa, "nombre", ""),
                    "empr_ico": getattr(empresa, "empr_ico", ""),
                    "empr_img": getattr(empresa, "empr_img", ""),
                } if empresa else None,
            })

        return Response(
            {
                "results": results,
                "count": len(results),
            },
            status=status.HTTP_200_OK,
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
            original = (
                Original.objects
                .filter(esta="enabled")
                .only(
                    "id",
                    "name",
                    "slug",
                    "extr",
                    "image",
                    "biog",
                    "esta",
                )
                .prefetch_related(
                    Prefetch(
                        "certifications",
                        queryset=(
                            OriginalCertification.objects
                            .select_related(
                                "certification",
                                "certification__plataforma_certificacion",
                                "certification__tema_certificacion",
                            )
                            .only(
                                "id",
                                "original_id",
                                "certification_id",
                                "title",
                                "posicion",
                                "hist",
                                "fondo",

                                "certification__id",
                                "certification__nombre",
                                "certification__slug",
                                "certification__imagen_final",
                                "certification__tema_certificacion_id",
                                "certification__plataforma_certificacion_id",

                                "certification__tema_certificacion__id",
                                "certification__tema_certificacion__nombre",
                                "certification__tema_certificacion__translate",
                                "certification__tema_certificacion__tem_col",

                                "certification__plataforma_certificacion__id",
                                "certification__plataforma_certificacion__nombre",
                                "certification__plataforma_certificacion__plat_img",
                                "certification__plataforma_certificacion__plat_ico",
                            )
                            .prefetch_related(
                                Prefetch(
                                    "certification__skills_rel",
                                    queryset=(
                                        SkillsCertification.objects
                                        .select_related("skill")
                                        .only(
                                            "id",
                                            "certificacion_id",
                                            "skill_id",
                                            "orden",
                                            "skill__id",
                                            "skill__nombre",
                                            "skill__translate",
                                            "skill__slug",
                                            "skill__skill_col",
                                            "skill__skill_ico",
                                        )
                                        .order_by("orden", "id")
                                    ),
                                )
                            )
                            .order_by("posicion")
                        ),
                        to_attr="prefetched_certifications",
                    )
                )
                .get(slug=slug)
            )

        except Original.DoesNotExist:
            return Response(
                {"detail": "No encontrado"},
                status=status.HTTP_404_NOT_FOUND,
            )

        serializer = OriginalSerializer(
            original,
            context={"request": request},
        )

        return Response(serializer.data)
    
class RankingsList(APIView):

    def get(self, request):
        rankings = Ranking.objects.filter(estado="enabled").order_by("-id")

        data = []

        for ranking in rankings:
            entradas = (
                ranking.entradas
                .select_related("universidad", "empresa")
                .order_by("posicion")[:5]
            )

            entradas_preview = []

            for entrada in entradas:
                if entrada.universidad:
                    entradas_preview.append({
                        "id": entrada.id,
                        "posicion": entrada.posicion,
                        "nombre": entrada.universidad.nombre,
                        "icono": entrada.universidad.univ_ico,
                        "entidad_id": entrada.universidad.id,
                        "entidad_tipo": "universidad",
                    })

                elif entrada.empresa:
                    entradas_preview.append({
                        "id": entrada.id,
                        "posicion": entrada.posicion,
                        "nombre": entrada.empresa.nombre,
                        "icono": entrada.empresa.empr_ico,
                        "entidad_id": entrada.empresa.id,
                        "entidad_tipo": "empresa",
                    })

            data.append({
                "id": ranking.id,
                "nombre": ranking.nombre,
                "descripcion": ranking.descripcion,
                "image": request.build_absolute_uri(ranking.image.url) if ranking.image else None,
                "tipo": ranking.tipo,
                "estado": ranking.estado,
                "entradas_preview": entradas_preview,
            })

        return Response(data, status=status.HTTP_200_OK)

class RankingDetailView(APIView):

    def get(self, request, slug):
        try:
            ranking = (
                Ranking.objects
                .prefetch_related("entradas__universidad", "entradas__empresa")
                .get(nombre__iexact=slug.replace("-", " "))
            )
        except Ranking.DoesNotExist:
            return Response(
                {"detail": "No encontrado"},
                status=status.HTTP_404_NOT_FOUND
            )

        entradas = list(
            ranking.entradas
            .select_related("universidad", "empresa")
            .annotate(
                total_certificaciones=Case(
                    When(
                        universidad__isnull=False,
                        then=Count("universidad__certificaciones", distinct=True),
                    ),
                    When(
                        empresa__isnull=False,
                        then=Count("empresa__certificaciones", distinct=True),
                    ),
                    default=Value(0),
                    output_field=IntegerField(),
                )
            )
            .order_by("posicion")
        )

        universidad_ids = [
            entrada.universidad_id
            for entrada in entradas
            if entrada.universidad_id
        ]

        empresa_ids = [
            entrada.empresa_id
            for entrada in entradas
            if entrada.empresa_id
        ]

        skills_by_universidad = defaultdict(list)
        skills_by_empresa = defaultdict(list)

        if universidad_ids:
            university_skills = (
                SkillsCertification.objects
                .filter(
                    certificacion__universidad_certificacion_id__in=universidad_ids,
                    certificacion__vigente_certificacion=True,
                    skill__estado=True,
                )
                .values(
                    "certificacion__universidad_certificacion_id",
                    "skill_id",
                    "skill__nombre",
                    "skill__translate",
                    "skill__slug",
                    "skill__skill_type",
                    "skill__skill_ico",
                    "skill__skill_img",
                    "skill__skill_col",
                )
                .annotate(total_certificaciones=Count("certificacion_id", distinct=True))
                .order_by(
                    "certificacion__universidad_certificacion_id",
                    "-total_certificaciones",
                    "skill__nombre",
                )
            )

            for item in university_skills:
                universidad_id = item["certificacion__universidad_certificacion_id"]

                if len(skills_by_universidad[universidad_id]) >= 10:
                    continue

                skills_by_universidad[universidad_id].append({
                    "skill_id": item["skill_id"],
                    "skill_nombre": item["skill__nombre"],
                    "skill_translate": item["skill__translate"],
                    "skill_slug": item["skill__slug"],
                    "skill_type": item["skill__skill_type"],
                    "skill_ico": item["skill__skill_ico"],
                    "skill_img": item["skill__skill_img"],
                    "skill_col": item["skill__skill_col"],
                    "total_certificaciones": item["total_certificaciones"],
                })

        if empresa_ids:
            company_skills = (
                SkillsCertification.objects
                .filter(
                    certificacion__empresa_certificacion_id__in=empresa_ids,
                    certificacion__vigente_certificacion=True,
                    skill__estado=True,
                )
                .values(
                    "certificacion__empresa_certificacion_id",
                    "skill_id",
                    "skill__nombre",
                    "skill__translate",
                    "skill__slug",
                    "skill__skill_type",
                    "skill__skill_ico",
                    "skill__skill_img",
                    "skill__skill_col",
                )
                .annotate(total_certificaciones=Count("certificacion_id", distinct=True))
                .order_by(
                    "certificacion__empresa_certificacion_id",
                    "-total_certificaciones",
                    "skill__nombre",
                )
            )

            for item in company_skills:
                empresa_id = item["certificacion__empresa_certificacion_id"]

                if len(skills_by_empresa[empresa_id]) >= 10:
                    continue

                skills_by_empresa[empresa_id].append({
                    "skill_id": item["skill_id"],
                    "skill_nombre": item["skill__nombre"],
                    "skill_translate": item["skill__translate"],
                    "skill_slug": item["skill__slug"],
                    "skill_type": item["skill__skill_type"],
                    "skill_ico": item["skill__skill_ico"],
                    "skill_img": item["skill__skill_img"],
                    "skill_col": item["skill__skill_col"],
                    "total_certificaciones": item["total_certificaciones"],
                })

        for entrada in entradas:
            if entrada.universidad_id:
                entrada.temas_certificaciones = skills_by_universidad.get(
                    entrada.universidad_id,
                    []
                )
            elif entrada.empresa_id:
                entrada.temas_certificaciones = skills_by_empresa.get(
                    entrada.empresa_id,
                    []
                )
            else:
                entrada.temas_certificaciones = []

        ranking.entradas_cache = entradas

        serializer = RankingSerializer(
            ranking,
            context={"request": request}
        )

        data = serializer.data

        for idx, entrada in enumerate(entradas):
            if idx < len(data.get("entradas", [])):
                data["entradas"][idx]["temas_certificaciones"] = entrada.temas_certificaciones

        return Response(data)

class RankingPreviewView(APIView):

    def get(self, request, slug):
        try:
            ranking = Ranking.objects.only(
                "id",
                "nombre",
                "descripcion",
                "image",
                "tipo",
                "estado",
            ).get(nombre__iexact=slug.replace("-", " "))
        except Ranking.DoesNotExist:
            return Response(
                {"detail": "No encontrado"},
                status=status.HTTP_404_NOT_FOUND
            )

        entradas = (
            ranking.entradas
            .select_related("universidad", "empresa")
            .only(
                "id",
                "posicion",
                "universidad_id",
                "empresa_id",
                "universidad__id",
                "universidad__nombre",
                "universidad__univ_ico",
                "empresa__id",
                "empresa__nombre",
                "empresa__empr_ico",
            )
            .order_by("posicion")[:5]
        )

        entradas_preview = []

        for entrada in entradas:
            if entrada.universidad_id and entrada.universidad:
                entradas_preview.append({
                    "id": entrada.id,
                    "posicion": entrada.posicion,
                    "nombre": entrada.universidad.nombre,
                    "icono": entrada.universidad.univ_ico,
                    "entidad_id": entrada.universidad.id,
                    "entidad_tipo": "universidad",
                })

            elif entrada.empresa_id and entrada.empresa:
                entradas_preview.append({
                    "id": entrada.id,
                    "posicion": entrada.posicion,
                    "nombre": entrada.empresa.nombre,
                    "icono": entrada.empresa.empr_ico,
                    "entidad_id": entrada.empresa.id,
                    "entidad_tipo": "empresa",
                })

        data = {
            "id": ranking.id,
            "nombre": ranking.nombre,
            "descripcion": ranking.descripcion,
            "image": request.build_absolute_uri(ranking.image.url) if ranking.image else None,
            "tipo": ranking.tipo,
            "estado": ranking.estado,
            "entradas_preview": entradas_preview,
        }

        return Response(data, status=status.HTTP_200_OK)
    
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


def _find_route_from_stripe_object(obj, user=None):
    metadata = obj.get("metadata") or {}
    route_id = metadata.get("route_id")

    if route_id:
        route = LearningRouteLead.objects.filter(id=route_id).first()
        if route:
            return route

    email = None

    customer_details = obj.get("customer_details") or {}
    if customer_details:
        email = customer_details.get("email")

    email = email or obj.get("customer_email")

    if not email and user:
        email = user.email

    if email:
        return (
            LearningRouteLead.objects
            .filter(email=email)
            .order_by("-created_at")
            .first()
        )

    return None

def _send_current_stripe_event_to_mx(event, event_type, obj, user=None):
    route = _find_route_from_stripe_object(obj, user=user)

    payload = build_mx_payload_from_stripe_event(
        event=event,
        event_type=event_type,
        stripe_object=obj,
        user=user,
        route=route,
    )

    result = send_stripe_event_to_mx(
        event_id=payload["eventId"],
        event_type=payload["eventType"],
        payload=payload,
        stripe_event_id=event.get("id"),
        stripe_object_id=obj.get("id"),
    )

    print("MX delivery result:", result)
    return result

@require_POST
@csrf_exempt
def stripe_webhook(request):
    print("✅ WEBHOOK HIT")

    payload = request.body
    sig_header = request.META.get("HTTP_STRIPE_SIGNATURE", "")

    try:
        event = stripe.Webhook.construct_event(
            payload=payload,
            sig_header=sig_header,
            secret=settings.STRIPE_WEBHOOK_SECRET,
        )
    except Exception as e:
        print("❌ Stripe signature error:", str(e))
        return HttpResponse(status=400)

    stripe_event_id = event.get("id")
    stripe_event_type = event.get("type")
    obj = (event.get("data") or {}).get("object") or {}

    def get_user_from_customer(customer_id):
        if not customer_id:
            return None

        profile = (
            UserBillingProfile.objects
            .filter(stripe_customer_id=customer_id)
            .select_related("user")
            .first()
        )

        return profile.user if profile else None

    def get_route_for_user(user):
        if not user:
            return None

        return (
            LearningRouteLead.objects
            .filter(user=user)
            .order_by("-updated_at", "-id")
            .first()
        )

    def get_subscription_for_user(user, subscription_id=None):
        qs = StripeSubscription.objects.filter(user=user)

        if subscription_id:
            found = qs.filter(stripe_subscription_id=subscription_id).first()
            if found:
                return found

        return qs.order_by("-updated_at", "-id").first()

    def build_plan_value(route, subscription):
        if route and getattr(route, "selected_paid_plan", None):
            return route.selected_paid_plan

        if route and route.selected_plan and subscription and subscription.interval:
            if route.selected_plan == "free":
                return "free"
            return f"{subscription.interval}_{route.selected_plan}"

        return "free"

    def send_access_event_to_mx_safe(
        *,
        user,
        route,
        subscription,
        mx_event_type,
        lifecycle_status,
        access_status,
        pending_action="NONE",
    ):
        if not user or not route:
            print("⚠️ No se envía a MX: falta user o route")
            return None

        try:
            event_id = (
                f"evt_col_stripe_{mx_event_type.lower()}_"
                f"route_{route.id}_user_{user.id}_{stripe_event_id or uuid.uuid4()}"
            )

            plan_value = build_plan_value(route, subscription)

            payload = build_learning_route_mx_payload(
                event_id=event_id,
                event_type=mx_event_type,
                user=user,
                route=route,
                subscription=subscription,
                plan_value=plan_value,
                lifecycle_status_override=lifecycle_status,
                access_status_override=access_status,
                pending_action_override=pending_action,
            )

            mx_result = send_b2c_access_event_to_mx(
                payload=payload,
                user=user,
                route=route,
            )

            route.mx_status = mx_result.get("status") or route.mx_status
            route.mx_response = mx_result

            magic_link = (
                mx_result.get("magicLink")
                or mx_result.get("response", {}).get("magicLink")
            )

            mx_user_id = (
                mx_result.get("mxUserId")
                or mx_result.get("response", {}).get("mxUserId")
            )

            if magic_link:
                route.mx_magic_link = magic_link

            if mx_user_id:
                route.mx_user_id = mx_user_id

            route.save(
                update_fields=[
                    "mx_status",
                    "mx_response",
                    "mx_magic_link",
                    "mx_user_id",
                    "updated_at",
                ]
            )

            print("✅ Evento enviado a MX:", mx_event_type, mx_result.get("status"))
            return mx_result

        except Exception as e:
            print("⚠️ Error enviando evento de acceso a MX:", str(e))
            return {
                "ok": False,
                "error": str(e),
                "status": "RETRYABLE_ERROR",
            }

    # --------------------------------------------
    # A) checkout.session.completed
    # Mantener por compatibilidad si aún llega algún checkout viejo.
    # --------------------------------------------
    if stripe_event_type == "checkout.session.completed":
        session = obj
        session_id = session.get("id")

        user = _find_user_from_session(session)

        if not user:
            return HttpResponse(status=200)

        customer_id = session.get("customer")
        subscription_id = session.get("subscription")

        _ensure_billing_profile(user, customer_id=customer_id)

        already_exists = (
            session_id and
            StripePurchase.objects.filter(
                stripe_checkout_session_id=session_id
            ).exists()
        )

        if not already_exists:
            StripePurchase.objects.create(
                user=user,
                stripe_checkout_session_id=session_id,
                stripe_payment_intent_id=session.get("payment_intent"),
                amount_total=session.get("amount_total") or 0,
                currency=session.get("currency") or "usd",
                status=session.get("payment_status") or "unknown",
                description="Checkout completed",
            )

        if subscription_id:
            _upsert_subscription(user, subscription_id)

        return HttpResponse(status=200)

    # --------------------------------------------
    # B) invoice.paid / invoice.payment_succeeded
    # Pago exitoso o renovación exitosa.
    # MX: USER_ACCESS_UPDATED / ACTIVE / ALLOWED / NONE
    # --------------------------------------------
    if stripe_event_type in ("invoice.paid", "invoice.payment_succeeded"):
        invoice = obj
        invoice_id = invoice.get("id")
        customer_id = invoice.get("customer")
        subscription_id = invoice.get("subscription")

        user = get_user_from_customer(customer_id)

        if not user:
            return HttpResponse(status=200)

        already_exists = (
            invoice_id and
            StripePurchase.objects.filter(
                stripe_invoice_id=invoice_id
            ).exists()
        )

        if not already_exists:
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

        route = get_route_for_user(user)
        subscription = get_subscription_for_user(user, subscription_id)

        if route:
            route.status = "active"
            route.save(update_fields=["status", "updated_at"])

        send_access_event_to_mx_safe(
            user=user,
            route=route,
            subscription=subscription,
            mx_event_type="USER_ACCESS_UPDATED",
            lifecycle_status="ACTIVE",
            access_status="ALLOWED",
            pending_action="NONE",
        )

        return HttpResponse(status=200)

    # --------------------------------------------
    # C) invoice.payment_failed
    # Pago fallido.
    # MX: USER_ACCESS_UPDATED / PAST_DUE / RESTRICTED / NONE
    # --------------------------------------------
    if stripe_event_type == "invoice.payment_failed":
        invoice = obj
        customer_id = invoice.get("customer")
        subscription_id = invoice.get("subscription")

        user = get_user_from_customer(customer_id)

        if not user:
            return HttpResponse(status=200)

        if subscription_id:
            _upsert_subscription(user, subscription_id)

        route = get_route_for_user(user)
        subscription = get_subscription_for_user(user, subscription_id)

        if route:
            route.status = "past_due"
            route.save(update_fields=["status", "updated_at"])

        send_access_event_to_mx_safe(
            user=user,
            route=route,
            subscription=subscription,
            mx_event_type="USER_ACCESS_UPDATED",
            lifecycle_status="PAST_DUE",
            access_status="RESTRICTED",
            pending_action="NONE",
        )

        return HttpResponse(status=200)

    # --------------------------------------------
    # D) customer.subscription.updated
    # Si cancel_at_period_end=True, NO se revoca.
    # MX: USER_ACCESS_UPDATED / ACTIVE|TRIALING / ALLOWED / CANCEL_AT_PERIOD_END
    # --------------------------------------------
    if stripe_event_type == "customer.subscription.updated":
        sub_obj = obj
        subscription_id = sub_obj.get("id")
        customer_id = sub_obj.get("customer")
        status_raw = str(sub_obj.get("status") or "").lower()
        cancel_at_period_end = bool(sub_obj.get("cancel_at_period_end", False))

        user = get_user_from_customer(customer_id)

        if not user:
            return HttpResponse(status=200)

        if subscription_id:
            _upsert_subscription(user, subscription_id)

        route = get_route_for_user(user)
        subscription = get_subscription_for_user(user, subscription_id)

        if route:
            route.status = (
                "cancel_at_period_end"
                if cancel_at_period_end
                else status_raw or route.status
            )
            route.save(update_fields=["status", "updated_at"])

        if status_raw == "trialing":
            lifecycle_status = "TRIALING"
            access_status = "ALLOWED"
        elif status_raw in ["active"]:
            lifecycle_status = "ACTIVE"
            access_status = "ALLOWED"
        elif status_raw in ["past_due", "unpaid"]:
            lifecycle_status = "PAST_DUE"
            access_status = "RESTRICTED"
        elif status_raw in ["canceled", "cancelled"]:
            lifecycle_status = "EXPIRED"
            access_status = "RESTRICTED"
        else:
            lifecycle_status = "ACTIVE"
            access_status = "ALLOWED"

        send_access_event_to_mx_safe(
            user=user,
            route=route,
            subscription=subscription,
            mx_event_type="USER_ACCESS_UPDATED",
            lifecycle_status=lifecycle_status,
            access_status=access_status,
            pending_action=(
                "CANCEL_AT_PERIOD_END"
                if cancel_at_period_end and access_status == "ALLOWED"
                else "NONE"
            ),
        )

        return HttpResponse(status=200)

    # --------------------------------------------
    # E) customer.subscription.deleted
    # La suscripción ya terminó realmente.
    # MX: USER_ACCESS_EXPIRED / EXPIRED / RESTRICTED / NONE
    # --------------------------------------------
    if stripe_event_type == "customer.subscription.deleted":
        sub_obj = obj
        subscription_id = sub_obj.get("id")
        customer_id = sub_obj.get("customer")

        user = get_user_from_customer(customer_id)

        if not user:
            return HttpResponse(status=200)

        if subscription_id:
            _upsert_subscription(user, subscription_id)

        route = get_route_for_user(user)
        subscription = get_subscription_for_user(user, subscription_id)

        if route:
            route.status = "expired"
            route.save(update_fields=["status", "updated_at"])

        send_access_event_to_mx_safe(
            user=user,
            route=route,
            subscription=subscription,
            mx_event_type="USER_ACCESS_EXPIRED",
            lifecycle_status="EXPIRED",
            access_status="RESTRICTED",
            pending_action="NONE",
        )

        return HttpResponse(status=200)

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
    success_url = settings.STRIPE_SUCCESS_URL
    cancel_url = settings.STRIPE_CANCEL_URL

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

    identifier = (body.get("email") or "").strip()
    password = body.get("password", "")

    if not identifier or not password:
        return JsonResponse(
            {"ok": False, "error": "missing_credentials"},
            status=400
        )

    # Buscar primero por email
    user_obj = User.objects.filter(email__iexact=identifier).first()

    # Si no existe, buscar por username
    if not user_obj:
        user_obj = User.objects.filter(username__iexact=identifier).first()

    if not user_obj:
        return JsonResponse(
            {"ok": False, "error": "invalid_credentials"},
            status=400
        )

    # Django autentica usando el username
    user = authenticate(
        request,
        username=user_obj.username,
        password=password
    )

    if not user:
        return JsonResponse(
            {"ok": False, "error": "invalid_credentials"},
            status=400
        )

    login(request, user)

    return JsonResponse({
        "ok": True,
        "user": {
            "id": user.id,
            "username": user.username,
            "email": user.email,
            "first_name": user.first_name,
            "last_name": user.last_name,
        }
    })

@csrf_exempt
@require_POST
def auth_logout(request):
    logout(request)
    return JsonResponse({"ok": True})

@api_login_required
def account_me(request):
    u = request.user

    billing = UserBillingProfile.objects.filter(user=u).first()
    sub = (
        StripeSubscription.objects
        .filter(user=u)
        .order_by("-updated_at", "-id")
        .first()
    )

    route = (
        LearningRouteLead.objects
        .filter(user=u)
        .order_by("-updated_at", "-id")
        .first()
    )

    selected_plan = getattr(route, "selected_plan", None) or "free"
    selected_paid_plan = getattr(route, "selected_paid_plan", None) or None

    return JsonResponse({
        "ok": True,
        "data": {
            "id": u.id,
            "email": u.email,
            "full_name": u.get_full_name() or u.username,

            "stripe_customer_id": getattr(billing, "stripe_customer_id", None),
            "stripe_subscription_id": getattr(sub, "stripe_subscription_id", None),

            "subscription_status": getattr(sub, "status", None),
            "selected_plan": selected_plan,
            "selected_paid_plan": selected_paid_plan,
            "billing_variant": selected_paid_plan,
            "interval": getattr(sub, "interval", None),
            "price_id": getattr(sub, "price_id", None),

            "current_period_end": (
                sub.current_period_end.isoformat()
                if sub and sub.current_period_end else None
            ),
            "cancel_at_period_end": bool(sub.cancel_at_period_end) if sub else False,

            "trial_start": (
                route.trial_start.isoformat()
                if route and getattr(route, "trial_start", None) else None
            ),
            "trial_end": (
                route.trial_end.isoformat()
                if route and getattr(route, "trial_end", None) else None
            ),

            "mx_status": getattr(route, "mx_status", None),
            "mx_user_id": getattr(route, "mx_user_id", None),
            "mx_magic_link": getattr(route, "mx_magic_link", None),

            "mx_access_status": (
                "RESTRICTED"
                if getattr(sub, "status", None) in ["past_due", "unpaid", "canceled", "cancelled"]
                else "ALLOWED"
            ),
            "lifecycle_status": (
                "EXPIRED"
                if getattr(sub, "status", None) in ["canceled", "cancelled"]
                else str(getattr(sub, "status", "") or selected_plan).upper()
            ),

            "learning_streak_days": getattr(route, "learning_streak_days", 0) if route else 0,
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
@login_required
def billing_invoices_list(request):
    billing = UserBillingProfile.objects.filter(user=request.user).first()

    if not billing or not billing.stripe_customer_id:
        return JsonResponse({"ok": True, "data": []})

    invoices = stripe.Invoice.list(
        customer=billing.stripe_customer_id,
        limit=50,
    )

    return JsonResponse({
        "ok": True,
        "data": [
            {
                "id": inv.get("id"),
                "number": inv.get("number"),
                "status": inv.get("status"),
                "amount": inv.get("amount_paid") or inv.get("total") or 0,
                "amount_due": inv.get("amount_due") or 0,
                "currency": inv.get("currency") or "usd",
                "created_at": timezone.datetime.fromtimestamp(
                    inv.get("created"),
                    tz=timezone.get_current_timezone(),
                ).isoformat() if inv.get("created") else None,
                "hosted_invoice_url": inv.get("hosted_invoice_url"),
                "invoice_pdf": inv.get("invoice_pdf"),
                "attempt_count": inv.get("attempt_count"),
                "next_payment_attempt": inv.get("next_payment_attempt"),
            }
            for inv in invoices.get("data", [])
        ],
    })

@require_POST
@csrf_exempt
@login_required
def billing_portal_session(request):
    billing = UserBillingProfile.objects.filter(user=request.user).first()

    if not billing or not billing.stripe_customer_id:
        return JsonResponse(
            {"ok": False, "error": "missing_stripe_customer"},
            status=400,
        )

    return_url = getattr(
        settings,
        "STRIPE_BILLING_PORTAL_RETURN_URL",
        "https://top.education/account?tab=license",
    )

    session = stripe.billing_portal.Session.create(
        customer=billing.stripe_customer_id,
        return_url=return_url,
    )

    return JsonResponse({
        "ok": True,
        "data": {
            "url": session.url,
        },
    })

@csrf_exempt
@login_required
def mx_magic_link_refresh(request):
    if request.method == "OPTIONS":
        response = HttpResponse(status=204)
        response["Access-Control-Allow-Origin"] = "https://top.education"
        response["Access-Control-Allow-Credentials"] = "true"
        response["Access-Control-Allow-Methods"] = "POST, OPTIONS"
        response["Access-Control-Allow-Headers"] = "Content-Type, X-CSRFToken"
        return response

    if request.method != "POST":
        return JsonResponse({"ok": False, "error": "method_not_allowed"}, status=405)

    user = request.user

    route = (
        LearningRouteLead.objects
        .filter(user=user)
        .order_by("-updated_at", "-id")
        .first()
    )

    subscription = (
        StripeSubscription.objects
        .filter(user=user)
        .order_by("-updated_at", "-id")
        .first()
    )

    if not route:
        return JsonResponse({"ok": False, "error": "learning_route_not_found"}, status=404)

    status = str(getattr(subscription, "status", "") or "").lower()

    if status in ["past_due", "unpaid", "canceled", "cancelled"]:
        return JsonResponse({
            "ok": False,
            "error": "access_inactive",
            "message": "Tu acceso está inactivo o suspendido.",
        }, status=403)

    plan_value = (
        getattr(route, "selected_paid_plan", None)
        or (
            f"{subscription.interval}_{route.selected_plan}"
            if subscription and route.selected_plan != "free"
            else "free"
        )
    )

    event_id = f"evt_col_magic_refresh_route_{route.id}_user_{user.id}_{uuid.uuid4()}"

    payload = build_learning_route_mx_payload(
        event_id=event_id,
        event_type="USER_ACCESS_UPDATED",
        user=user,
        route=route,
        subscription=subscription,
        plan_value=plan_value,
    )

    result = send_b2c_access_event_to_mx(
        payload=payload,
        user=user,
        route=route,
    )

    if not result.get("ok"):
        return JsonResponse(result, status=400)

    magic_link = result.get("magicLink") or result.get("response", {}).get("magicLink")
    mx_user_id = result.get("mxUserId") or result.get("response", {}).get("mxUserId")

    route.mx_magic_link = magic_link
    route.mx_status = result.get("status") or "APPLIED"
    route.mx_response = {
        **result,
        "mxUserId": mx_user_id,
        "magicLink": magic_link,
    }

    route.save(update_fields=[
        "mx_magic_link",
        "mx_status",
        "mx_response",
        "updated_at",
    ])

    return JsonResponse({
        "ok": True,
        "data": {
            "magic_link": magic_link,
            "mx_user_id": mx_user_id,
            "mx_status": route.mx_status,
        },
    })

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


logger = logging.getLogger(__name__)

#ACTUALIZACIÓN DE ENDPOINT

def _get_base_external_url():
    return f"{settings.COURSES_EXTERNAL_ENDPOINT.rstrip('/')}/course-information"

LOCK_TTL_SECONDS = 10 * 60


def _get_external_api_key():
    return (
        getattr(settings, "COURSES_EXTERNAL_API_KEY", None)
        or getattr(settings, "AWS_COURSES_API_KEY", None)
    )


def _is_sync_paused() -> bool:
    raw = getattr(settings, "COLOMBIA_SYNC_PAUSED", False)
    return str(raw).strip().lower() in ("1", "true", "yes", "on")


def _normalize_provider(provider: str | None) -> str | None:
    if not provider:
        return None
    provider = str(provider).strip()
    return provider.upper() if provider else None


def _validate_specialization_id(specialization_id: str | None) -> bool:
    if not specialization_id or ":" not in specialization_id:
        return False
    provider, raw_id = specialization_id.split(":", 1)
    return bool(provider.strip() and raw_id.strip())


def _get_resource_endpoint(resource: str, specialization_id: str | None = None) -> str:
    base_url = _get_base_external_url()

    if resource == "courses":
        return f"{base_url}/courses"
    if resource == "certifications":
        return f"{base_url}/certifications"
    if resource == "skills-structure":
        return f"{base_url}/skills-structure"
    if resource == "specializations":
        return f"{base_url}/specializations"
    if resource == "specialization-detail":
        return f"{base_url}/specializations/{specialization_id}"

    raise ValueError(f"Unsupported resource: {resource}")


def _extract_total_pages(payload: dict) -> int | None:
    for k in ("totalPages", "total_pages", "totalPage", "pages"):
        v = payload.get(k)
        if isinstance(v, int) and v > 0:
            return v
        if isinstance(v, str) and v.isdigit():
            vv = int(v)
            if vv > 0:
                return vv

    meta = payload.get("meta") if isinstance(payload.get("meta"), dict) else None
    if meta:
        for k in ("totalPages", "total_pages", "pages"):
            v = meta.get(k)
            if isinstance(v, int) and v > 0:
                return v
            if isinstance(v, str) and v.isdigit():
                vv = int(v)
                if vv > 0:
                    return vv

    return None


def _compute_next_page(page: int, payload: dict) -> int | None:
    items = payload.get("items", [])
    items_len = len(items) if isinstance(items, list) else 0
    total_pages = _extract_total_pages(payload)

    if isinstance(total_pages, int) and total_pages > 0:
        return 1 if page >= total_pages else (page + 1)

    return 1 if items_len == 0 else (page + 1)


def _acquire_lock(state_key: str, run_id: str):
    now = timezone.now()
    stale_before = now - timedelta(seconds=LOCK_TTL_SECONDS)

    state, _ = ExternalSyncState.objects.get_or_create(
        key=state_key,
        defaults={"cursor_value": "1", "running": False},
    )

    if state.running and state.locked_at and state.locked_at > stale_before:
        return None

    locked_at_value = now
    ExternalSyncState.objects.filter(key=state_key).update(
        running=True,
        locked_at=locked_at_value,
        updated_at=now,
    )
    state.refresh_from_db()
    state._locked_at_value = locked_at_value
    state._run_id = run_id
    return state


def _release_lock(state_key: str):
    try:
        ExternalSyncState.objects.filter(
            key=state_key,
            running=True,
        ).update(
            running=False,
            locked_at=None,
            updated_at=timezone.now(),
        )
    except Exception:
        pass


def _build_params(resource: str, page: int, page_size: int, provider: str | None) -> dict:
    params = {}

    if resource in ("courses", "certifications", "specializations"):
        params["page"] = page
        params["pageSize"] = page_size

    if provider and resource in ("courses", "certifications", "specializations"):
        params["provider"] = provider
        params["providerId"] = provider

    return params


def _ingest_by_resource(resource: str, payload: dict, provider: str | None = None, specialization_id: str | None = None):
    if resource in ("courses", "certifications"):
        return ingest_course_payload(payload, resource=resource, provider_filter=provider)

    if resource == "skills-structure":
        return ingest_skills_structure_payload(payload, provider_filter=provider)

    if resource == "specializations":
        return ingest_specializations_payload(payload, provider_filter=provider)

    if resource == "specialization-detail":
        return ingest_specialization_detail_payload(
            payload,
            specialization_id=specialization_id,
            provider_filter=provider,
        )

    raise ValueError(f"Unsupported ingestion resource: {resource}")


@csrf_exempt
@require_POST
def api_run_courses_sync(request):
    """
    POST /api/sync/courses/run/

    Body:
    {
      "resource": "courses|certifications|skills-structure|specializations|specialization-detail",
      "provider": "COURSERA|EDX|MASTERCLASS",
      "specialization_id": "coursera:Specialization~ABC",
      "page": 1,
      "pageSize": 100,
      "timeout": 30,
      "maxPagesPerRun": 1,
      "resetCursor": false
    }
    """
    t0 = time.time()
    run_id = uuid.uuid4().hex[:16]

    # Tiempo máximo seguro para responder antes de Cloudflare.
    # Ajusta si tu Cloudflare/origen permite más.
    MAX_HTTP_SECONDS = 480

    if _is_sync_paused():
        return JsonResponse(
            {
                "ok": False,
                "error": "sync_paused",
                "detail": "COLOMBIA_SYNC_PAUSED está activo. La sincronización fue bloqueada por hardening.",
            },
            status=423,
        )

    try:
        body = json.loads(request.body or "{}")
        if not isinstance(body, dict):
            body = {}
    except Exception:
        body = {}

    resource = str(body.get("resource") or "courses").strip().lower()
    provider = _normalize_provider(body.get("provider") or body.get("providerId"))
    specialization_id = str(body.get("specialization_id") or body.get("id") or "").strip()

    allowed_resources = {
        "courses",
        "certifications",
        "skills-structure",
        "specializations",
        "specialization-detail",
    }

    if resource not in allowed_resources:
        return JsonResponse(
            {
                "ok": False,
                "error": "invalid_resource",
                "detail": f"resource inválido: {resource}",
            },
            status=400,
        )

    if resource == "specialization-detail" and not _validate_specialization_id(specialization_id):
        return JsonResponse(
            {
                "ok": False,
                "error": "invalid_specialization_id",
                "detail": "El id de especialización debe tener formato <provider>:<rawId>.",
            },
            status=400,
        )

    uses_cursor = resource in ("courses", "certifications", "specializations")
    state_key = str(body.get("stateKey") or f"{resource}_sync").strip()

    api_key = _get_external_api_key()
    if not api_key:
        ExternalSyncLog.objects.create(
            key=state_key,
            run_id=run_id,
            page=0,
            page_size=0,
            ok=False,
            took_ms=0,
            error="missing_api_key",
            detail="AWS_COURSES_API_KEY / COURSES_EXTERNAL_API_KEY no configurada",
            trace="",
        )
        return JsonResponse({"ok": False, "error": "missing_api_key"}, status=500)

    try:
        endpoint = _get_resource_endpoint(
            resource,
            specialization_id=specialization_id or None,
        )
    except ValueError as e:
        ExternalSyncLog.objects.create(
            key=state_key,
            run_id=run_id,
            page=0,
            page_size=0,
            ok=False,
            took_ms=int((time.time() - t0) * 1000),
            error="invalid_endpoint",
            detail=str(e),
            trace="",
        )
        return JsonResponse({"ok": False, "error": str(e)}, status=400)

    try:
        page_size = int(body.get("pageSize", 50) or 50)
    except Exception:
        page_size = 50

    try:
        timeout = int(body.get("timeout", 120) or 120)
    except Exception:
        timeout = 120

    try:
        max_pages_per_run = int(body.get("maxPagesPerRun", 3) or 3)
    except Exception:
        max_pages_per_run = 3

    reset_cursor = bool(body.get("resetCursor", False))

    # Límites más seguros para ejecución por inspector/HTTP.
    # El cron puede correr más veces, pero cada request debe ser corto.
    max_pages_per_run = max(1, min(max_pages_per_run, 3))
    page_size = max(1, min(page_size, 60))
    timeout = max(5, min(timeout, 180))

    state, _ = ExternalSyncState.objects.get_or_create(
        key=state_key,
        defaults={"cursor_value": "1", "running": False},
    )

    if reset_cursor and uses_cursor:
        ExternalSyncState.objects.filter(key=state_key).update(
            cursor_value="1",
            updated_at=timezone.now(),
        )

    state = _acquire_lock(state_key, run_id)
    if not state:
        return JsonResponse(
            {
                "ok": True,
                "message": "Lock activo, ya hay una ejecución en curso",
                "run_id": run_id,
                "locked": False,
                "state_key": state_key,
                "lock_ttl_seconds": LOCK_TTL_SECONDS,
            },
            status=200,
        )

    processed_pages = 0
    last_result = None
    page = 1

    try:
        if uses_cursor:
            try:
                page = max(1, int(state.cursor_value or "1"))
            except Exception:
                page = 1
        else:
            page = 1

        headers = {
            "Accept": "application/json",
            "x-api-key": api_key,
        }


        for _ in range(max_pages_per_run):
            elapsed = time.time() - t0
            if elapsed >= MAX_HTTP_SECONDS:
                ExternalSyncLog.objects.create(
                    key=state_key,
                    run_id=run_id,
                    page=page if uses_cursor else None,
                    page_size=page_size if uses_cursor else None,
                    ok=False,
                    took_ms=int(elapsed * 1000),
                    error="http_time_budget_exceeded",
                    detail=(
                        f"Se detuvo antes del timeout HTTP. "
                        f"elapsed={round(elapsed, 2)}s max={MAX_HTTP_SECONDS}s"
                    ),
                    trace="",
                )

                return JsonResponse(
                    {
                        "ok": True,
                        "partial": True,
                        "run_id": run_id,
                        "resource": resource,
                        "provider": provider,
                        "state_key": state_key,
                        "processed_pages": processed_pages,
                        "next_page": page if uses_cursor else None,
                        "message": "Ejecución detenida antes del timeout HTTP. Reintenta para continuar.",
                    },
                    status=200,
                )

            params = _build_params(resource, page, page_size, provider)

            try:
                resp = requests.get(
                    endpoint,
                    headers=headers,
                    params=params,
                    timeout=timeout,
                )

                response_text_preview = ""
                try:
                    response_text_preview = (resp.text or "")[:3000]
                except Exception:
                    response_text_preview = ""

                if resp.status_code in (502, 503, 504):
                    took_ms = int((time.time() - t0) * 1000)

                    next_page = page + 1 if uses_cursor else None

                    ExternalSyncLog.objects.create(
                        key=state_key,
                        run_id=run_id,
                        page=page if uses_cursor else None,
                        page_size=page_size if uses_cursor else None,
                        ok=False,
                        took_ms=took_ms,
                        error="external_api_bad_gateway_skipped",
                        detail=(
                            f"HTTP {resp.status_code}. Página omitida para no detener cron. "
                            f"url={getattr(resp, 'url', endpoint)} "
                            f"body={response_text_preview}"
                        ),
                        trace="",
                    )

                    if uses_cursor and next_page:
                        ExternalSyncState.objects.filter(key=state_key).update(
                            cursor_value=str(next_page),
                            last_error_at=timezone.now(),
                            last_error=f"Página {page} omitida por HTTP {resp.status_code}",
                            updated_at=timezone.now(),
                        )

                    page = next_page

                    continue

                if resp.status_code >= 400:
                    took_ms = int((time.time() - t0) * 1000)

                    ExternalSyncLog.objects.create(
                        key=state_key,
                        run_id=run_id,
                        page=page if uses_cursor else None,
                        page_size=page_size if uses_cursor else None,
                        ok=False,
                        took_ms=took_ms,
                        error="fetch_failed",
                        detail=(
                            f"HTTP {resp.status_code}. "
                            f"url={getattr(resp, 'url', endpoint)} "
                            f"body={response_text_preview}"
                        ),
                        trace="",
                    )

                    ExternalSyncState.objects.filter(key=state_key).update(
                        last_error_at=timezone.now(),
                        last_error=f"fetch_failed HTTP {resp.status_code}",
                    )

                    return JsonResponse(
                        {
                            "ok": False,
                            "error": "fetch_failed",
                            "status_code": resp.status_code,
                            "detail": response_text_preview,
                            "url": getattr(resp, "url", endpoint),
                        },
                        status=502,
                    )

                try:
                    payload = resp.json()
                except Exception as e:
                    took_ms = int((time.time() - t0) * 1000)

                    ExternalSyncLog.objects.create(
                        key=state_key,
                        run_id=run_id,
                        page=page if uses_cursor else None,
                        page_size=page_size if uses_cursor else None,
                        ok=False,
                        took_ms=took_ms,
                        error="invalid_json",
                        detail=(
                            f"No se pudo parsear JSON. "
                            f"url={getattr(resp, 'url', endpoint)} "
                            f"body={response_text_preview}"
                        ),
                        trace=traceback.format_exc()[:8000],
                    )

                    ExternalSyncState.objects.filter(key=state_key).update(
                        last_error_at=timezone.now(),
                        last_error=f"invalid_json: {e}",
                    )

                    return JsonResponse(
                        {
                            "ok": False,
                            "error": "invalid_json",
                            "detail": str(e),
                            "body": response_text_preview,
                        },
                        status=502,
                    )

                if not isinstance(payload, dict):
                    payload = {"data": payload}

            except requests.RequestException as e:
                took_ms = int((time.time() - t0) * 1000)

                ExternalSyncLog.objects.create(
                    key=state_key,
                    run_id=run_id,
                    page=page if uses_cursor else None,
                    page_size=page_size if uses_cursor else None,
                    ok=False,
                    took_ms=took_ms,
                    error="fetch_failed",
                    detail=str(e),
                    trace=traceback.format_exc()[:8000],
                )

                ExternalSyncState.objects.filter(key=state_key).update(
                    last_error_at=timezone.now(),
                    last_error=f"fetch_failed: {e}",
                )

                return JsonResponse(
                    {
                        "ok": False,
                        "error": "fetch_failed",
                        "detail": str(e),
                    },
                    status=502,
                )

            items = payload.get("items", [])
            items_len = len(items) if isinstance(items, list) else 0
            total_pages = _extract_total_pages(payload)

            elapsed = time.time() - t0
            if elapsed >= MAX_HTTP_SECONDS:
                ExternalSyncLog.objects.create(
                    key=state_key,
                    run_id=run_id,
                    page=page if uses_cursor else None,
                    page_size=page_size if uses_cursor else None,
                    ok=False,
                    items_len=items_len,
                    received=items_len,
                    took_ms=int(elapsed * 1000),
                    error="http_time_budget_exceeded_before_ingest",
                    detail=(
                        f"Fetch terminó, pero no se inicia ingesta para evitar 504. "
                        f"elapsed={round(elapsed, 2)}s max={MAX_HTTP_SECONDS}s"
                    ),
                    trace="",
                )

                return JsonResponse(
                    {
                        "ok": True,
                        "partial": True,
                        "run_id": run_id,
                        "resource": resource,
                        "provider": provider,
                        "state_key": state_key,
                        "processed_pages": processed_pages,
                        "next_page": page if uses_cursor else None,
                        "message": "Fetch completado, ingesta omitida para evitar timeout. Reintenta.",
                    },
                    status=200,
                )

            try:
                summary = _ingest_by_resource(
                    resource,
                    payload,
                    provider=provider,
                    specialization_id=specialization_id or None,
                )

            except Exception as e:
                took_ms = int((time.time() - t0) * 1000)

                ExternalSyncLog.objects.create(
                    key=state_key,
                    run_id=run_id,
                    page=page if uses_cursor else None,
                    page_size=page_size if uses_cursor else None,
                    ok=False,
                    items_len=items_len,
                    received=items_len,
                    took_ms=took_ms,
                    error="ingestion_failed",
                    detail=str(e),
                    trace=traceback.format_exc()[:8000],
                )

                ExternalSyncState.objects.filter(key=state_key).update(
                    last_error_at=timezone.now(),
                    last_error=f"ingestion_failed: {e}",
                )

                return JsonResponse(
                    {
                        "ok": False,
                        "error": "ingestion_failed",
                        "detail": str(e),
                    },
                    status=500,
                )


            if uses_cursor:
                next_page = _compute_next_page(page, payload)

                ExternalSyncState.objects.filter(key=state_key).update(
                    cursor_value=str(next_page),
                    last_ok_at=timezone.now(),
                    last_error="",
                    updated_at=timezone.now(),
                )
            else:
                next_page = None

                ExternalSyncState.objects.filter(key=state_key).update(
                    last_ok_at=timezone.now(),
                    last_error="",
                    updated_at=timezone.now(),
                )

            took_ms = int((time.time() - t0) * 1000)

            ExternalSyncLog.objects.create(
                key=state_key,
                run_id=run_id,
                page=page if uses_cursor else None,
                page_size=page_size if uses_cursor else None,
                ok=True,
                items_len=items_len,
                received=items_len,
                took_ms=took_ms,
                detail=(
                    f"PAGE_DONE resource={resource} provider={provider or '-'} "
                    f"items_len={items_len} total_pages={total_pages} "
                    f"next_page={next_page} summary={json.dumps(summary, default=str)[:1500]}"
                ),
            )

            processed_pages += 1

            last_result = {
                "ok": True,
                "run_id": run_id,
                "resource": resource,
                "provider": provider,
                "specialization_id": specialization_id or None,
                "page": page if uses_cursor else None,
                "page_size": page_size if uses_cursor else None,
                "items_len": items_len,
                "received": items_len,
                "total_pages": total_pages,
                "next_page": next_page,
                "processed_pages": processed_pages,
                "summary": summary,
                "reconciliation": payload.get("reconciliation")
                if isinstance(payload.get("reconciliation"), dict)
                else None,
            }

            if not uses_cursor:
                break

            page = next_page

            if next_page == 1:
                break

        if not last_result:
            last_result = {
                "ok": True,
                "run_id": run_id,
                "resource": resource,
                "provider": provider,
                "specialization_id": specialization_id or None,
                "processed_pages": processed_pages,
            }

        return JsonResponse(last_result)

    finally:
        _release_lock(state_key)


COLOR_MAP = {
    "tag-verde": "#5CC781",
    "tag-azul": "#034694",
    "tag-rojo": "#D33B3E",
}

MAX_ITEMS_PER_SKILL = 8
CACHE_KEY = "home_skills_grid_v4"
CACHE_TIMEOUT = 60 * 30  # 30 minutos

MAX_SKILLS_ON_HOME = 12
MAX_CERTS_PER_SKILL_SCAN = 30


def normalize_media_url(request, value):
    if not value:
        return ""

    value = str(value).strip()
    if not value:
        return ""

    low = value.lower()
    if low in {"none", "null", "false"}:
        return ""

    if value.startswith("http://") or value.startswith("https://"):
        return value

    if value.startswith("/assets/") or value.startswith("assets/"):
        frontend_url = getattr(settings, "FRONTEND_URL", "").rstrip("/")
        clean_path = value if value.startswith("/") else f"/{value}"
        return f"{frontend_url}{clean_path}"

    return request.build_absolute_uri(value)


def normalize_skill_type_for_filter(skill_type):
    value = str(skill_type or "").strip().lower()

    if value == "tema":
        return "Temas"

    if value == "habilidad":
        return "Habilidades"

    return "Skills"

def build_cert_link(cert):
    platform = getattr(cert, "plataforma_certificacion", None)
    platform_name = (getattr(platform, "nombre", "") or "").strip().lower()

    platform_slug_map = {
        "coursera": "coursera",
        "edx": "edx",
        "edx.org": "edx",
        "masterclass": "masterclass",
    }

    platform_slug = platform_slug_map.get(platform_name)

    if platform_slug:
        return f"/certificacion/{platform_slug}/{cert.slug}"

    return f"/certificacion/{cert.slug}"


def normalize_instructor_name(item):
    if not isinstance(item, dict):
        return ""

    return (
        item.get("name")
        or item.get("nombre")
        or item.get("title")
        or item.get("label")
        or ""
    ).strip()


def normalize_instructor_image(item):
    if not isinstance(item, dict):
        return ""

    return (
        item.get("foto")
        or item.get("photo")
        or item.get("image")
        or item.get("img")
        or item.get("imagen")
        or item.get("instructor_img")
        or ""
    ).strip()


def parse_instructors_text(raw):
    if not raw or not isinstance(raw, str):
        return []

    text = raw.strip()
    if not text or text.lower() in {"none", "null", "[]"}:
        return []

    parts = text.replace(" y ", ",").replace(" and ", ",").split(",")

    return [{"name": p.strip(), "img": ""} for p in parts if p.strip()]


def get_certification_instructors(cert):
    normalized = []

    raw = getattr(cert, "instructores_certificacion", None)

    if isinstance(raw, list):
        for item in raw:
            if isinstance(item, dict):
                normalized.append({
                    "name": normalize_instructor_name(item),
                    "img": normalize_instructor_image(item),
                })

    elif isinstance(raw, str):
        normalized.extend(parse_instructors_text(raw))

    related = getattr(cert, "instructor_links", None)

    if related is not None:
        try:
            for link in related.all():
                instructor = getattr(link, "instructor", None)
                if not instructor:
                    continue

                name = getattr(instructor, "nombre", "") or ""
                img = getattr(instructor, "imagen", "") or ""

                normalized.append({
                    "name": str(name).strip(),
                    "img": str(img).strip() if img else "",
                })
        except Exception:
            pass

    clean = []
    seen = set()

    for item in normalized:
        name = str(item.get("name") or "").strip()
        img = str(item.get("img") or "").strip()

        key = f"{name.lower()}|{img}"
        if key in seen:
            continue

        seen.add(key)

        if name or img:
            clean.append({
                "name": name,
                "img": img,
            })

    return clean


def pick_first_instructor_image(cert, request):
    instructors = get_certification_instructors(cert)

    for ins in instructors:
        img = str(ins.get("img") or "").strip()
        if img:
            return normalize_media_url(request, img)

    return ""

def get_initial(value):
    value = (value or "").strip()
    return value[:1].upper() if value else "T"

class HomeSkillsGridAPIView(APIView):
    permission_classes = []

    def get(self, request, *args, **kwargs):
        cached = cache.get(CACHE_KEY)
        if cached:
            return Response(cached)

        skills = list(
            Skills.objects
            .filter(
                parent__isnull=True,
                estado=True,
            )
            .exclude(Q(skill_ico__isnull=True) | Q(skill_ico__exact=""))
            .only(
                "id",
                "nombre",
                "translate",
                "descripcion",
                "skill_type",
                "skill_img",
                "skill_ico",
                "skill_col",
                "slug",
            )
            .order_by("id")[:MAX_SKILLS_ON_HOME]
        )

        skill_ids = [skill.id for skill in skills]

        links = list(
            SkillsCertification.objects
            .filter(skill_id__in=skill_ids)
            .select_related(
                "certificacion",
                "certificacion__universidad_certificacion",
                "certificacion__empresa_certificacion",
                "certificacion__plataforma_certificacion",
            )
            .only(
                "id",
                "skill_id",
                "certificacion_id",

                "certificacion__id",
                "certificacion__nombre",
                "certificacion__slug",
                "certificacion__universidad_certificacion_id",
                "certificacion__empresa_certificacion_id",
                "certificacion__plataforma_certificacion_id",

                "certificacion__universidad_certificacion__id",
                "certificacion__universidad_certificacion__nombre",
                "certificacion__universidad_certificacion__univ_ico",
                "certificacion__universidad_certificacion__univ_img",

                "certificacion__empresa_certificacion__id",
                "certificacion__empresa_certificacion__nombre",
                "certificacion__empresa_certificacion__empr_ico",
                "certificacion__empresa_certificacion__empr_img",

                "certificacion__plataforma_certificacion__id",
                "certificacion__plataforma_certificacion__nombre",
                "certificacion__plataforma_certificacion__plat_ico",
                "certificacion__plataforma_certificacion__plat_img",
            )
            .order_by("skill_id", "-certificacion_id")
        )

        grouped_links = {}

        for link in links:
            grouped_links.setdefault(link.skill_id, [])

            if len(grouped_links[link.skill_id]) < MAX_CERTS_PER_SKILL_SCAN:
                grouped_links[link.skill_id].append(link)

        response_data = []

        for skill in skills:
            related_items = []
            seen_universities = set()
            seen_companies = set()
            seen_certs = set()

            skill_type_raw = (skill.skill_type or "").strip()
            skill_type = skill_type_raw.lower()

            is_topic = skill_type == "tema"
            filter_key = "tema_id" if is_topic else "habilidad_id"
            item_type = "topic" if is_topic else "skill"

            skill_links = grouped_links.get(skill.id, [])

            for link in skill_links:
                cert = link.certificacion
                if not cert:
                    continue

                uni = getattr(cert, "universidad_certificacion", None)

                if uni and uni.id not in seen_universities:
                    seen_universities.add(uni.id)

                    uni_img = (
                        normalize_media_url(request, getattr(uni, "univ_ico", None))
                        or normalize_media_url(request, getattr(uni, "univ_img", None))
                    )

                    related_items.append({
                        "id": uni.id,
                        "name": uni.nombre,
                        "type": "university",
                        "img": uni_img,
                        "initial": get_initial(uni.nombre),
                        "filter": {
                            filter_key: skill.id,
                            "universidad_id": uni.id,
                        },
                    })

                emp = getattr(cert, "empresa_certificacion", None)

                if emp and emp.id not in seen_companies:
                    seen_companies.add(emp.id)

                    emp_img = (
                        normalize_media_url(request, getattr(emp, "empr_ico", None))
                        or normalize_media_url(request, getattr(emp, "empr_img", None))
                    )

                    related_items.append({
                        "id": emp.id,
                        "name": emp.nombre,
                        "type": "company",
                        "img": emp_img,
                        "initial": get_initial(emp.nombre),
                        "filter": {
                            filter_key: skill.id,
                            "empresa_id": emp.id,
                        },
                    })

                plataforma = getattr(cert, "plataforma_certificacion", None)
                platform_name = (getattr(plataforma, "nombre", "") or "").strip().lower()

                if "masterclass" in platform_name and cert.id not in seen_certs:
                    seen_certs.add(cert.id)

                    platform_img = (
                        normalize_media_url(request, getattr(plataforma, "plat_ico", None))
                        or normalize_media_url(request, getattr(plataforma, "plat_img", None))
                    )

                    related_items.append({
                        "id": cert.id,
                        "name": cert.nombre,
                        "type": "certification",
                        "img": platform_img,
                        "initial": get_initial(cert.nombre),
                        "link": build_cert_link(cert),
                    })

            random.shuffle(related_items)
            related_items = related_items[:MAX_ITEMS_PER_SKILL]

            response_data.append({
                "id": skill.id,
                "name": (skill.translate or skill.nombre or "").strip(),
                "slug": skill.slug,
                "skill_type": skill_type_raw,
                "type": item_type,
                "filter": {
                    filter_key: skill.id,
                },
                "img": (
                    normalize_media_url(request, skill.skill_ico)
                    or normalize_media_url(request, skill.skill_img)
                ),
                "color": COLOR_MAP.get(skill.skill_col, "#034694"),
                "description": (skill.descripcion or "").strip(),
                "items": related_items,
                "universities": related_items,
            })

        random.shuffle(response_data)

        cache.set(CACHE_KEY, response_data, CACHE_TIMEOUT)
        return Response(response_data)
        
def get_stripe_price_for_plan(plan):
    plan_normalized = str(plan or "monthly_x").strip().lower()

    mapping = {
        "monthly_basic": {
            "price_id": getattr(settings, "STRIPE_PRICE_BASIC_MONTHLY", None),
            "selected_plan": "basic",
            "interval": "monthly",
        },
        "yearly_basic": {
            "price_id": getattr(settings, "STRIPE_PRICE_BASIC_YEARLY", None),
            "selected_plan": "basic",
            "interval": "yearly",
        },
        "monthly_x": {
            "price_id": getattr(settings, "STRIPE_PRICE_X_MONTHLY", None),
            "selected_plan": "x",
            "interval": "monthly",
        },
        "yearly_x": {
            "price_id": getattr(settings, "STRIPE_PRICE_X_YEARLY", None),
            "selected_plan": "x",
            "interval": "yearly",
        },
        "monthly_plus": {
            "price_id": getattr(settings, "STRIPE_PRICE_PLUS_MONTHLY", None),
            "selected_plan": "plus",
            "interval": "monthly",
        },
        "yearly_plus": {
            "price_id": getattr(settings, "STRIPE_PRICE_PLUS_YEARLY", None),
            "selected_plan": "plus",
            "interval": "yearly",
        },
    }

    config = mapping.get(plan_normalized)

    if not config:
        return None, None, None, f"invalid_plan_{plan_normalized}"

    if not config["price_id"]:
        return None, None, None, f"missing_price_id_for_{plan_normalized}"

    return (
        config["price_id"],
        config["selected_plan"],
        config["interval"],
        None,
    )

def _get_or_create_user_from_onboarding(request):
    body = _json_body(request)

    route_id = body.get("route_id")
    email = (body.get("email") or "").strip().lower()
    name = (body.get("name") or "").strip()

    route = None

    if route_id:
        route = LearningRouteLead.objects.filter(id=route_id).first()
        if route:
            email = route.email

    if not email:
        return None, route, "missing_email"

    user = User.objects.filter(email=email).first()

    if not user:
        username_base = slugify(email.split("@")[0]) or "user"
        username = username_base
        counter = 1

        while User.objects.filter(username=username).exists():
            counter += 1
            username = f"{username_base}-{counter}"

        first_name = ""
        last_name = ""

        if route:
            first_name = route.first_name or ""
            last_name = route.last_name or ""
        elif name:
            parts = name.split(" ", 1)
            first_name = parts[0]
            last_name = parts[1] if len(parts) > 1 else ""

        user = User.objects.create_user(
            username=username,
            email=email,
            first_name=first_name,
            last_name=last_name,
            password=None,
            is_active=True,
        )

    if route and route.user_id != user.id:
        route.user = user
        route.save(update_fields=["user"])

    return user, route, None

@method_decorator(csrf_exempt, name="dispatch")
class LearningRouteCreateView(APIView):
    authentication_classes = []
    permission_classes = []

    def post(self, request):
        email = (request.data.get("email") or "").strip().lower()
        existing_user = User.objects.filter(email__iexact=email).first()

        if existing_user:
            return Response(
                {
                    "ok": False,
                    "error": "email_already_registered",
                    "message": "Ya existe una cuenta con este correo.",
                    "redirect": "/login",
                    "email": email,
                },
                status=409,
            )
        first_name = (request.data.get("first_name") or "").strip()
        last_name = (request.data.get("last_name") or "").strip()

        phone_country_code = (request.data.get("phone_country_code") or "").strip()
        phone_number = (request.data.get("phone_number") or "").strip()
        phone_e164 = (request.data.get("phone_e164") or "").strip()

        age = request.data.get("age")
        gender = (request.data.get("gender") or "").strip()
        country = (request.data.get("country") or "").strip()

        topics = request.data.get("topics") or []
        goal = (request.data.get("goal") or "").strip()
        recommended = request.data.get("recommended_certifications") or []

        if not email:
            return Response({"error": "email es obligatorio"}, status=400)

        if not first_name:
            return Response({"error": "first_name es obligatorio"}, status=400)

        if not phone_country_code:
            return Response({"error": "phone_country_code es obligatorio"}, status=400)

        if not phone_number:
            return Response({"error": "phone_number es obligatorio"}, status=400)

        if not phone_e164:
            phone_e164 = f"{phone_country_code}{''.join(filter(str.isdigit, phone_number))}"

        if not goal:
            return Response({"error": "goal es obligatorio"}, status=400)

        user = User.objects.filter(email=email).first()

        route = LearningRouteLead.objects.create(
            user=user,
            email=email,
            first_name=first_name,
            last_name=last_name,
            phone_country_code=phone_country_code,
            phone_number=phone_number,
            phone_e164=phone_e164,
            age=age,
            gender=gender,
            country=country,
            topics=topics,
            goal=goal,
            recommended_certifications=recommended,
            status="route_created",
            mx_status="pending",
            mx_response=None,
        )

        return Response(
            {
                "id": route.id,
                "email": route.email,
                "first_name": route.first_name,
                "last_name": route.last_name,
                "phone_country_code": route.phone_country_code,
                "phone_number": route.phone_number,
                "phone_e164": route.phone_e164,
                "status": route.status,
            },
            status=201,
        )
    
class LearningRouteFreeSignupView(APIView):
    authentication_classes = []
    permission_classes = []

    @transaction.atomic
    def post(self, request):
        route_id = request.data.get("route_id")
        email = (request.data.get("email") or "").strip().lower()
        password = request.data.get("password") or ""

        if not route_id or not email or not password:
            return Response(
                {"error": "route_id, email y password son obligatorios"},
                status=status.HTTP_400_BAD_REQUEST,
            )

        try:
            route = LearningRouteLead.objects.select_for_update().get(
                id=route_id,
                email=email,
            )
        except LearningRouteLead.DoesNotExist:
            return Response(
                {"error": "Ruta no encontrada"},
                status=status.HTTP_404_NOT_FOUND,
            )

        user, created = User.objects.get_or_create(
            email=email,
            defaults={
                "username": email,
                "first_name": route.first_name,
                "last_name": route.last_name or "",
            },
        )

        if created:
            user.set_password(password)
            user.save()
        else:
            return Response(
                {"error": "Ya existe una cuenta con este correo. Inicia sesión."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        route.user = user
        route.selected_plan = "free"
        route.status = "free_active"
        route.save(update_fields=["user", "selected_plan", "status", "updated_at"])

        login(request, user)

        return Response({
            "ok": True,
            "user_id": user.id,
            "route_id": route.id,
            "redirect": "/account",
        })

@method_decorator(csrf_exempt, name="dispatch")
class LearningRouteCompleteSignupView(APIView):
    permission_classes = [AllowAny]
    authentication_classes = []

    @transaction.atomic
    def post(self, request):
        route_id = request.data.get("route_id")
        password = request.data.get("password")
        selected_plan = request.data.get("selected_plan") or "free"

        if not route_id:
            return Response(
                {"ok": False, "error": "route_id requerido"},
                status=status.HTTP_400_BAD_REQUEST,
            )

        if not password:
            return Response(
                {"ok": False, "error": "password requerido"},
                status=status.HTTP_400_BAD_REQUEST,
            )

        route = (
            LearningRouteLead.objects
            .select_for_update()
            .select_related("user")
            .filter(id=route_id)
            .first()
        )

        if not route:
            return Response(
                {"ok": False, "error": "ruta no encontrada"},
                status=status.HTTP_404_NOT_FOUND,
            )

        user = route.user

        if not user:
            user, _, error = _get_or_create_user_from_onboarding(request)

            if error:
                return Response(
                    {"ok": False, "error": error},
                    status=status.HTTP_400_BAD_REQUEST,
                )

            route.user = user

        try:
            validate_password(password, user)
        except ValidationError as e:
            return Response(
                {
                    "ok": False,
                    "error": "password_invalido",
                    "messages": e.messages,
                },
                status=status.HTTP_400_BAD_REQUEST,
            )

        user.set_password(password)
        user.is_active = True
        user.save(update_fields=["password", "is_active"])

        # Login directo sin depender de username/email authenticate
        backend = get_backends()[0]
        user.backend = f"{backend.__module__}.{backend.__class__.__name__}"
        login(request, user)

        subscription = (
            StripeSubscription.objects
            .filter(user=user)
            .order_by("-id")
            .first()
        )

        route.selected_plan = selected_plan
        route.status = "account_pending_mx"

        if subscription:
            route.stripe_subscription_id = subscription.stripe_subscription_id
            route.trial_end = route.trial_end or subscription.current_period_end

        route.save(
            update_fields=[
                "user",
                "selected_plan",
                "status",
                "stripe_subscription_id",
                "trial_end",
                "updated_at",
            ]
        )

        event_type = "USER_ACCESS_PROVISION"

        plan_value = (
            selected_plan
            if selected_plan == "free"
            else request.data.get("selected_paid_plan") or selected_plan
        )

        event_id = f"evt_col_provision_route_{route.id}_user_{user.id}_{uuid.uuid4()}"

        payload = build_learning_route_mx_payload(
            event_id=event_id,
            event_type=event_type,
            user=user,
            route=route,
            subscription=subscription,
            plan_value=plan_value,
        )

        mx_result = send_b2c_access_event_to_mx(
            payload=payload,
            user=user,
            route=route,
        )

        route.mx_status = mx_result.get("status") or "unknown"
        route.mx_response = mx_result

        if mx_result.get("magicLink"):
            route.mx_magic_link = mx_result.get("magicLink")

        route.status = "account_created" if mx_result.get("ok") else "mx_error"

        route.save(
            update_fields=[
                "mx_status",
                "mx_response",
                "mx_magic_link",
                "status",
                "updated_at",
            ]
        )

        redirect_url = (
            "/account?tab=cv"
            if selected_plan == "free"
            else "/account?tab=license"
        )

        if not mx_result.get("ok"):
            return Response(
                {
                    "ok": True,
                    "warning": "mx_user_creation_failed",
                    "mx_sent": False,
                    "mx_status": route.mx_status,
                    "mx_response": mx_result,
                    "redirect": redirect_url,
                },
                status=status.HTTP_200_OK,
            )

        return Response(
            {
                "ok": True,
                "user_id": user.id,
                "route_id": route.id,
                "mx_sent": True,
                "mx_status": route.mx_status,
                "mx_response": mx_result,
                "redirect": redirect_url,
            },
            status=status.HTTP_200_OK,
        )
    
def _json_body(request):
    try:
        return json.loads(request.body.decode("utf-8") or "{}")
    except Exception:
        return {}


def _ensure_billing_profile(user, customer_id=None):
    profile, _ = UserBillingProfile.objects.get_or_create(user=user)

    if customer_id and profile.stripe_customer_id != customer_id:
        profile.stripe_customer_id = customer_id
        profile.save(update_fields=["stripe_customer_id"])

    return profile


def _get_or_create_stripe_customer(user, email=None, name=None):
    profile = _ensure_billing_profile(user)

    if profile.stripe_customer_id:
        return profile.stripe_customer_id

    customer = stripe.Customer.create(
        email=email or user.email,
        name=name or user.get_full_name() or user.username,
        metadata={
            "user_id": str(user.id),
            "source": "top-education-colombia",
        },
    )

    profile.stripe_customer_id = customer.id
    profile.save(update_fields=["stripe_customer_id"])

    return customer.id

@require_POST
@csrf_exempt
@login_required
def billing_subscription_change_plan(request):
    body = _json_body(request)
    plan = (body.get("plan") or "").strip().lower()

    if not plan:
        return JsonResponse({"ok": False, "error": "missing_plan"}, status=400)

    if plan == "free":
        return JsonResponse({
            "ok": False,
            "error": "free_downgrade_requires_cancel_flow",
        }, status=400)

    price_id, selected_plan, interval, price_error = get_stripe_price_for_plan(plan)

    if price_error:
        return JsonResponse(
            {"ok": False, "error": price_error},
            status=400 if price_error.startswith("invalid") else 500,
        )

    subscription = (
        StripeSubscription.objects
        .filter(user=request.user)
        .exclude(status__in=["canceled", "cancelled"])
        .order_by("-id")
        .first()
    )

    if not subscription:
        return JsonResponse(
            {"ok": False, "error": "subscription_not_found"},
            status=404,
        )

    try:
        stripe_sub = stripe.Subscription.retrieve(subscription.stripe_subscription_id)
        item_id = stripe_sub["items"]["data"][0]["id"]

        updated = stripe.Subscription.modify(
            subscription.stripe_subscription_id,
            items=[{
                "id": item_id,
                "price": price_id,
            }],
            proration_behavior="create_prorations",
            metadata={
                "plan": selected_plan,
                "interval": interval,
                "source": "top-education-colombia",
            },
        )

        current_period_end = (
            timezone.datetime.fromtimestamp(
                updated.get("current_period_end"),
                tz=timezone.get_current_timezone(),
            )
            if updated.get("current_period_end")
            else subscription.current_period_end
        )

        subscription.price_id = price_id
        subscription.interval = interval
        subscription.status = updated.get("status") or subscription.status
        subscription.current_period_end = current_period_end
        subscription.cancel_at_period_end = bool(updated.get("cancel_at_period_end", False))
        subscription.save(update_fields=[
            "price_id",
            "interval",
            "status",
            "current_period_end",
            "cancel_at_period_end",
        ])

        LearningRouteLead.objects.filter(user=request.user).update(
            selected_plan=selected_plan,
            status=f"{selected_plan}_{updated.get('status') or 'active'}",
        )

        return JsonResponse({
            "ok": True,
            "data": {
                "selected_plan": selected_plan,
                "interval": interval,
                "price_id": price_id,
                "status": subscription.status,
                "current_period_end": current_period_end.isoformat() if current_period_end else None,
            },
        })

    except Exception as e:
        return JsonResponse(
            {"ok": False, "error": str(e)},
            status=400,
        )

@require_POST
@csrf_exempt
def billing_setup_intent(request):
    user, route, error = _get_or_create_user_from_onboarding(request)

    if error:
        return JsonResponse({"ok": False, "error": error}, status=400)

    customer_id = _get_or_create_stripe_customer(user)

    setup_intent = stripe.SetupIntent.create(
        customer=customer_id,
        usage="off_session",
        payment_method_types=["card"],
        metadata={
            "user_id": str(user.id),
            "route_id": str(route.id) if route else "",
            "source": "top-education-colombia",
        },
    )

    return JsonResponse({
        "ok": True,
        "client_secret": setup_intent.client_secret,
        "customer_id": customer_id,
    })

@require_GET
@login_required
def billing_payment_methods_list(request):
    qs = StripePaymentMethod.objects.filter(user=request.user).order_by(
        "-is_default",
        "-created_at",
    )

    return JsonResponse({
        "ok": True,
        "data": [
            {
                "id": item.id,
                "stripe_payment_method_id": item.stripe_payment_method_id,
                "brand": item.brand,
                "last4": item.last4,
                "exp_month": item.exp_month,
                "exp_year": item.exp_year,
                "is_default": item.is_default,
            }
            for item in qs
        ],
    })


@require_POST
@csrf_exempt
def billing_payment_methods_create(request):
    body = _json_body(request)
    payment_method_id = body.get("payment_method_id")

    if not payment_method_id:
        return JsonResponse(
            {"ok": False, "error": "missing_payment_method_id"},
            status=400,
        )

    user, route, error = _get_or_create_user_from_onboarding(request)

    if error:
        return JsonResponse({"ok": False, "error": error}, status=400)

    customer_id = _get_or_create_stripe_customer(user)

    payment_method = stripe.PaymentMethod.retrieve(payment_method_id)

    if payment_method.customer and payment_method.customer != customer_id:
        return JsonResponse(
            {"ok": False, "error": "payment_method_belongs_to_other_customer"},
            status=400,
        )

    if not payment_method.customer:
        stripe.PaymentMethod.attach(
            payment_method_id,
            customer=customer_id,
        )

    card = payment_method.card

    has_default = StripePaymentMethod.objects.filter(
        user=user,
        is_default=True,
    ).exists()

    local_pm, _ = StripePaymentMethod.objects.update_or_create(
        stripe_payment_method_id=payment_method_id,
        defaults={
            "user": user,
            "stripe_customer_id": customer_id,
            "brand": card.brand,
            "last4": card.last4,
            "exp_month": card.exp_month,
            "exp_year": card.exp_year,
            "is_default": not has_default,
        },
    )

    if local_pm.is_default:
        stripe.Customer.modify(
            customer_id,
            invoice_settings={
                "default_payment_method": payment_method_id,
            },
        )

    return JsonResponse({
        "ok": True,
        "data": {
            "id": local_pm.id,
            "brand": local_pm.brand,
            "last4": local_pm.last4,
            "exp_month": local_pm.exp_month,
            "exp_year": local_pm.exp_year,
            "is_default": local_pm.is_default,
        },
    })

@require_POST
@csrf_exempt
@login_required
def billing_payment_method_set_default(request, method_id):
    try:
        local_pm = StripePaymentMethod.objects.get(
            id=method_id,
            user=request.user,
        )
    except StripePaymentMethod.DoesNotExist:
        return JsonResponse(
            {"ok": False, "error": "payment_method_not_found"},
            status=404,
        )

    stripe.Customer.modify(
        local_pm.stripe_customer_id,
        invoice_settings={
            "default_payment_method": local_pm.stripe_payment_method_id,
        },
    )

    StripePaymentMethod.objects.filter(user=request.user).update(is_default=False)
    local_pm.is_default = True
    local_pm.save(update_fields=["is_default"])

    return JsonResponse({"ok": True})

@require_POST
@csrf_exempt
@login_required
def billing_payment_method_delete(request, method_id):

    try:
        local_pm = StripePaymentMethod.objects.get(
            id=method_id,
            user=request.user
        )
    except StripePaymentMethod.DoesNotExist:
        return JsonResponse(
            {"ok": False},
            status=404
        )

    stripe.PaymentMethod.detach(
        local_pm.stripe_payment_method_id
    )

    local_pm.delete()

    return JsonResponse({
        "ok": True
    })

@require_POST
@csrf_exempt
def billing_subscription_create(request):
    body = _json_body(request)

    route_id = body.get("route_id")
    payment_method_id = body.get("payment_method_id")
    plan = body.get("plan", "monthly_x")

    user, route, error = _get_or_create_user_from_onboarding(request)

    if error:
        return JsonResponse({"ok": False, "error": error}, status=400)

    plan_normalized = str(plan or "monthly_x").strip().lower()

    price_id, selected_plan, interval, price_error = get_stripe_price_for_plan(
        plan_normalized
    )

    if price_error:
        return JsonResponse(
            {"ok": False, "error": price_error},
            status=400 if price_error.startswith("invalid") else 500,
        )

    if not payment_method_id:
        return JsonResponse(
            {"ok": False, "error": "missing_payment_method_id"},
            status=400,
        )

    if not price_id:
        return JsonResponse(
            {"ok": False, "error": f"missing_price_id_for_{plan_normalized}"},
            status=500,
        )

    customer_id = _get_or_create_stripe_customer(user)

    local_pm = StripePaymentMethod.objects.filter(
        user=user,
        stripe_payment_method_id=payment_method_id,
    ).first()

    if not local_pm:
        return JsonResponse(
            {"ok": False, "error": "payment_method_not_registered"},
            status=400,
        )

    stripe.Customer.modify(
        customer_id,
        invoice_settings={
            "default_payment_method": payment_method_id,
        },
    )

    subscription = stripe.Subscription.create(
        customer=customer_id,
        items=[{"price": price_id}],
        default_payment_method=payment_method_id,
        trial_period_days=7,
        metadata={
            "user_id": str(user.id),
            "route_id": str(route_id or ""),
            "source": "top-education-colombia",
            "plan": selected_plan,
            "selected_paid_plan": plan_normalized,
            "billing_variant": plan_normalized,
            "interval": interval,
        },
        expand=["latest_invoice.payment_intent"],
    )

    subscription_id = subscription.get("id")
    subscription_status = subscription.get("status") or "unknown"

    trial_start = timezone.now()
    trial_end_ts = subscription.get("trial_end")

    trial_end = (
        timezone.datetime.fromtimestamp(
            trial_end_ts,
            tz=timezone.get_current_timezone(),
        )
        if trial_end_ts
        else trial_start + timedelta(days=7)
    )

    current_period_end_ts = (
        subscription.get("current_period_end")
        or subscription.get("trial_end")
    )

    current_period_end = (
        timezone.datetime.fromtimestamp(
            current_period_end_ts,
            tz=timezone.get_current_timezone(),
        )
        if current_period_end_ts
        else None
    )

    StripeSubscription.objects.update_or_create(
        stripe_subscription_id=subscription_id,
        defaults={
            "user": user,
            "status": subscription_status,
            "price_id": price_id,
            "interval": interval,
            "current_period_end": current_period_end,
            "cancel_at_period_end": bool(
                subscription.get("cancel_at_period_end", False)
            ),
        },
    )

    if route_id:
        update_fields = {
            "user": user,
            "selected_plan": selected_plan,
            "status": "pro_trialing",
            "stripe_customer_id": customer_id,
            "stripe_subscription_id": subscription_id,
            "trial_start": trial_start,
            "trial_end": trial_end,
        }

        # Solo si ya agregaste este campo al modelo LearningRouteLead
        if hasattr(LearningRouteLead, "selected_paid_plan"):
            update_fields["selected_paid_plan"] = plan_normalized

        LearningRouteLead.objects.filter(
            id=route_id,
            email=user.email,
        ).update(**update_fields)

    return JsonResponse({
        "ok": True,
        "data": {
            "stripe_customer_id": customer_id,
            "stripe_subscription_id": subscription_id,
            "status": subscription_status,
            "selected_plan": selected_plan,
            "selected_paid_plan": plan_normalized,
            "billing_variant": plan_normalized,
            "interval": interval,
            "trial_start": trial_start.isoformat(),
            "trial_end": trial_end.isoformat(),
            "redirect": "/account?tab=license",
        },
    })

#ENVIO INFORMACIÓN STRIPE MEXICO
@require_POST
@csrf_exempt
@login_required
def billing_subscription_cancel(request):
    body = _json_body(request)
    reason = (body.get("reason") or "").strip()

    if not reason:
        return JsonResponse(
            {"ok": False, "error": "missing_cancel_reason"},
            status=400,
        )

    subscription = (
        StripeSubscription.objects
        .filter(user=request.user)
        .exclude(status__in=["canceled", "cancelled"])
        .order_by("-id")
        .first()
    )

    if not subscription:
        return JsonResponse(
            {"ok": False, "error": "subscription_not_found"},
            status=404,
        )

    if not subscription.stripe_subscription_id:
        return JsonResponse(
            {"ok": False, "error": "missing_stripe_subscription_id"},
            status=400,
        )

    route = (
        LearningRouteLead.objects
        .filter(user=request.user)
        .order_by("-updated_at", "-id")
        .first()
    )

    if not route:
        return JsonResponse(
            {"ok": False, "error": "learning_route_not_found"},
            status=404,
        )

    try:
        stripe_subscription = stripe.Subscription.modify(
            subscription.stripe_subscription_id,
            cancel_at_period_end=True,
            metadata={
                "cancel_reason": reason,
                "cancel_requested_by": str(request.user.id),
                "cancel_requested_from": "top-education-colombia",
            },
        )

        current_period_end = (
            timezone.datetime.fromtimestamp(
                stripe_subscription.get("current_period_end"),
                tz=timezone.get_current_timezone(),
            )
            if stripe_subscription.get("current_period_end")
            else subscription.current_period_end
        )

        subscription.cancel_at_period_end = True
        subscription.status = stripe_subscription.get("status") or subscription.status
        subscription.current_period_end = current_period_end

        subscription.save(
            update_fields=[
                "cancel_at_period_end",
                "status",
                "current_period_end",
                "updated_at",
            ]
        )

        route.status = "cancel_at_period_end"
        route.save(update_fields=["status", "updated_at"])

        plan_value = (
            getattr(route, "selected_paid_plan", None)
            or f"{subscription.interval}_{route.selected_plan}"
            or "monthly_x"
        )

        event_id = (
            f"evt_col_cancel_at_period_end_"
            f"route_{route.id}_user_{request.user.id}_{uuid.uuid4()}"
        )

        payload = build_learning_route_mx_payload(
            event_id=event_id,
            event_type="USER_ACCESS_UPDATED",
            user=request.user,
            route=route,
            subscription=subscription,
            plan_value=plan_value,
            lifecycle_status_override="ACTIVE",
            access_status_override="ALLOWED",
            pending_action_override="CANCEL_AT_PERIOD_END",
        )

        mx_result = send_b2c_access_event_to_mx(
            payload=payload,
            user=request.user,
            route=route,
        )

        route.mx_status = mx_result.get("status") or route.mx_status

        magic_link = mx_result.get("magicLink") or mx_result.get("response", {}).get("magicLink")
        mx_user_id = mx_result.get("mxUserId") or mx_result.get("response", {}).get("mxUserId")

        route.mx_response = {
            **mx_result,
            "mxUserId": mx_user_id,
            "magicLink": magic_link,
        }

        if magic_link:
            route.mx_magic_link = magic_link

        route.save(
            update_fields=[
                "mx_status",
                "mx_response",
                "mx_magic_link",
                "updated_at",
            ]
        )

        return JsonResponse({
            "ok": True,
            "message": "subscription_will_cancel_at_period_end",
            "cancel_at_period_end": True,
            "current_period_end": (
                subscription.current_period_end.isoformat()
                if subscription.current_period_end
                else None
            ),
            "mx_sent": bool(mx_result.get("ok")),
            "mx_status": mx_result.get("status"),
            "mx_response": mx_result,
        })

    except Exception as e:
        print("CANCEL ERROR:", str(e))

        return JsonResponse(
            {
                "ok": False,
                "error": str(e),
            },
            status=400,
        )

@require_POST
@csrf_exempt
@login_required
def billing_subscription_reactivate(request):
    subscription = (
        StripeSubscription.objects
        .filter(user=request.user)
        .exclude(status__in=["canceled", "cancelled"])
        .order_by("-id")
        .first()
    )

    if not subscription:
        return JsonResponse({"ok": False, "error": "subscription_not_found"}, status=404)

    stripe_subscription = stripe.Subscription.modify(
        subscription.stripe_subscription_id,
        cancel_at_period_end=False,
    )

    subscription.cancel_at_period_end = False
    subscription.status = stripe_subscription.get("status") or subscription.status
    subscription.save(update_fields=["cancel_at_period_end", "status", "updated_at"])

    return JsonResponse({"ok": True})

def _mx_iso_now():
    return (
        timezone.now()
        .astimezone(dt_timezone.utc)
        .isoformat(timespec="milliseconds")
        .replace("+00:00", "Z")
    )


def _json_dumps(payload):
    return json.dumps(payload, separators=(",", ":"), ensure_ascii=False)


def _build_mx_headers(raw_body, event_id, occurred_at):
    secret = (settings.MX_B2C_ACCESS_EVENT_HMAC_SECRET or "").strip()
    print("SECRET_LEN:", len(secret))
    print("SECRET_PREFIX:", secret[:8])
    print("SECRET_SUFFIX:", secret[-8:])

    signature = hmac.new(
        secret.encode("utf-8"),
        raw_body.encode("utf-8"),
        hashlib.sha256,
    ).hexdigest()

    return {
        "Content-Type": "application/json",
        "X-Top-Signature": f"hmac-sha256={signature}",
        "X-Top-Timestamp": occurred_at,
        "X-Event-Id": event_id,
    }

def get_mx_package_code(plan_value):
    plan_value = str(plan_value or "free").strip().lower()

    mapping = {
        "free": "TOP_EDUCATION_FREE",

        "monthly_basic": "TOP_EDUCATION_BASIC_MONTHLY",
        "yearly_basic": "TOP_EDUCATION_BASIC_ANNUAL",

        "monthly_x": "TOP_EDUCATION_X_MONTHLY",
        "yearly_x": "TOP_EDUCATION_X_ANNUAL",

        "monthly_plus": "TOP_EDUCATION_PLUS_MONTHLY",
        "yearly_plus": "TOP_EDUCATION_PLUS_ANNUAL",
    }

    return mapping.get(plan_value)

def send_stripe_event_to_mx(
    *,
    event_id,
    event_type,
    payload,
    stripe_event_id=None,
    stripe_object_id=None,
):
    """
    Envía evento normalizado Colombia -> MX.
    Idempotente por event_id.
    """

    if not getattr(settings, "MX_STRIPE_B2C_WEBHOOK_URL", None):
        return {
            "ok": False,
            "skipped": True,
            "error": "missing_MX_STRIPE_B2C_WEBHOOK_URL",
        }

    log, created = MxWebhookDeliveryLog.objects.get_or_create(
        event_id=event_id,
        defaults={
            "event_type": event_type,
            "stripe_event_id": stripe_event_id,
            "stripe_object_id": stripe_object_id,
            "status": "pending",
            "request_payload": payload,
        },
    )

    if not created and log.status in ["applied", "duplicate", "permanent_error"]:
        return {
            "ok": True,
            "skipped": True,
            "status": log.status,
            "event_id": event_id,
        }

    raw_body = _json_dumps(payload)
    headers = _build_mx_headers(raw_body, payload["eventId"], payload["occurredAt"])

    response = requests.post(
        settings.MX_B2C_ACCESS_EVENT_URL,
        data=raw_body.encode("utf-8"),
        headers=headers,
        timeout=getattr(settings, "MX_B2C_TIMEOUT", 15),
    )

    log.attempts = (log.attempts or 0) + 1
    log.last_attempt_at = timezone.now()
    log.status = "sending"
    log.request_payload = payload
    log.save(
        update_fields=[
            "attempts",
            "last_attempt_at",
            "status",
            "request_payload",
            "updated_at",
        ]
    )

    try:
        response = requests.post(
            settings.MX_B2C_ACCESS_EVENT_URL,
            data=raw_body.encode("utf-8"),
            headers=headers,
            timeout=getattr(settings, "MX_B2C_TIMEOUT", 15),
        )

        try:
            response_json = response.json()
        except Exception:
            response_json = {"raw": response.text[:2000]}

        data_block = response_json.get("data") if isinstance(response_json, dict) else None

        if not isinstance(data_block, dict):
            data_block = {}

        mx_status = data_block.get("status")

        mx_error = response_json.get("error") if isinstance(response_json, dict) else None

        if response.status_code >= 500:
            final_status = "retryable_error"
        elif response.status_code in [400, 401]:
            final_status = "permanent_error"
        elif mx_status == "APPLIED":
            final_status = "applied"
        elif mx_status == "DUPLICATE":
            final_status = "duplicate"
        elif mx_status == "RETRYABLE_ERROR":
            final_status = "retryable_error"
        elif mx_status == "PERMANENT_ERROR":
            final_status = "permanent_error"
        elif response.ok:
            final_status = "applied"
        else:
            final_status = "retryable_error"

        log.status = final_status
        log.http_status = response.status_code
        log.mx_status = mx_status
        log.response_body = response_json
        log.error_message = json.dumps(mx_error, ensure_ascii=False) if mx_error else None
        log.save(
            update_fields=[
                "status",
                "http_status",
                "mx_status",
                "response_body",
                "error_message",
                "updated_at",
            ]
        )

        return {
            "ok": final_status in ["applied", "duplicate"],
            "status": final_status,
            "http_status": response.status_code,
            "mx_status": mx_status,
            "response": response_json,
        }

    except requests.Timeout as e:
        log.status = "retryable_error"
        log.error_message = f"timeout: {str(e)}"
        log.save(update_fields=["status", "error_message", "updated_at"])

        return {
            "ok": False,
            "status": "retryable_error",
            "error": "timeout",
        }

    except Exception as e:
        log.status = "retryable_error"
        log.error_message = str(e)
        log.save(update_fields=["status", "error_message", "updated_at"])

        return {
            "ok": False,
            "status": "retryable_error",
            "error": str(e),
        }


def build_mx_event_id(stripe_event_id, event_type):
    base = stripe_event_id or str(uuid.uuid4())
    return f"colombia-b2c:{event_type}:{base}"

def _get_plan_amount_cents(price_id=None, selected_plan=None, interval=None):
    price_id = str(price_id or "")
    selected_plan = str(selected_plan or "").lower()
    interval = str(interval or "monthly").lower()

    price_map = {
        getattr(settings, "STRIPE_PRICE_BASIC_MONTHLY", None): 1900,
        getattr(settings, "STRIPE_PRICE_BASIC_YEARLY", None): 19000,
        getattr(settings, "STRIPE_PRICE_X_MONTHLY", None): 2900,
        getattr(settings, "STRIPE_PRICE_X_YEARLY", None): 29900,
        getattr(settings, "STRIPE_PRICE_PLUS_MONTHLY", None): 4900,
        getattr(settings, "STRIPE_PRICE_PLUS_YEARLY", None): 49900,
    }

    if price_id in price_map:
        return price_map[price_id]

    fallback = {
        ("basic", "monthly"): 1900,
        ("basic", "yearly"): 19000,
        ("x", "monthly"): 2900,
        ("x", "yearly"): 29900,
        ("plus", "monthly"): 4900,
        ("plus", "yearly"): 49900,
    }

    return fallback.get((selected_plan, interval), 0)

def build_learning_route_mx_payload(
    *,
    event_id,
    event_type,
    user,
    route,
    subscription=None,
    plan_value="free",
    lifecycle_status_override=None,
    access_status_override=None,
    pending_action_override=None,
):
    occurred_at = _mx_iso_now()

    plan_value = str(plan_value or "free").strip().lower()
    package_code = get_mx_package_code(plan_value)

    if not package_code:
        raise ValueError(f"unsupported_mx_package_code_for_{plan_value}")

    selected_plan = str(route.selected_plan or "free").lower()

    if plan_value == "free":
        tier = "FREE"
        billing_period = "MONTHLY"
        lifecycle_status = "FREE"
        access_status = "ALLOWED"
        pending_action = "NONE"
        is_trial = False
    else:
        tier = "PLUS" if "plus" in plan_value else "X"
        billing_period = "ANNUAL" if "yearly" in plan_value else "MONTHLY"
        status_raw = str(subscription.status if subscription else "").lower()

        if status_raw == "trialing":
            lifecycle_status = "TRIALING"
            is_trial = True
        elif status_raw in ["active", "paid"]:
            lifecycle_status = "ACTIVE"
            is_trial = False
        elif status_raw in ["past_due", "unpaid"]:
            lifecycle_status = "PAST_DUE"
            is_trial = False
        elif status_raw in ["canceled", "cancelled"]:
            lifecycle_status = "CANCELLED"
            is_trial = False
        else:
            lifecycle_status = "TRIALING" if route.trial_start and route.trial_end else "ACTIVE"
            is_trial = lifecycle_status == "TRIALING"

        access_status = "RESTRICTED" if lifecycle_status in ["PAST_DUE", "CANCELLED", "EXPIRED"] else "ALLOWED"

        pending_action = (
            "CANCEL_AT_PERIOD_END"
            if subscription and subscription.cancel_at_period_end
            else "NONE"
        )

    if lifecycle_status_override:
        lifecycle_status = lifecycle_status_override

    if access_status_override:
        access_status = access_status_override

    if pending_action_override:
        pending_action = pending_action_override

    is_trial = lifecycle_status == "TRIALING"

    trial_start = route.trial_start
    trial_end = route.trial_end or (
        subscription.current_period_end if subscription else None
    )

    recommended_courses = []

    for index, course in enumerate(route.recommended_certifications or [], start=1):
        recommended_courses.append({
            "idInterno": (
                course.get("idInterno")
                or course.get("id_interno")
                or course.get("idInternoMx")
                or course.get("id_interno_mx")
                or course.get("external_id")
                or str(course.get("id") or "")
            ),
            "colombiaCertificationId": (
                course.get("colombiaCertificationId")
                or course.get("id")
                or course.get("certification_id")
            ),
            "title": (
                course.get("title")
                or course.get("nombre")
                or course.get("name")
                or ""
            ),
            "level": (
                course.get("level")
                or course.get("nivel_certificacion")
                or course.get("nivel")
                or ""
            ),
            "provider": (
                course.get("provider")
                or course.get("plataforma")
                or course.get("platform")
                or ""
            ),
            "order": course.get("order") or index,
            "routeLevel": (
                course.get("routeLevel")
                or course.get("route_level")
                or course.get("level_route")
                or 1
            ),
        })

    stripe_subscription_id = (
        subscription.stripe_subscription_id
        if subscription
        else route.stripe_subscription_id
    )

    stripe_customer_id = route.stripe_customer_id
    stripe_price_id = subscription.price_id if subscription else None

    current_period_end = (
        subscription.current_period_end
        if subscription and subscription.current_period_end
        else None
    )

    return {
        "schemaVersion": "1.0",
        "eventId": event_id,
        "eventType": event_type,
        "traceId": f"col-startnow-route-{route.id}-user-{user.id}",
        "occurredAt": occurred_at,

        "customer": {
            "email": user.email,
            "emailNormalized": user.email.lower(),
            "name": user.first_name or route.first_name or "",
            "lastName": user.last_name or route.last_name or "",
            "phoneCountryCode": route.phone_country_code,
            "phoneNumber": route.phone_number,
            "phoneE164": route.phone_e164,
            "age": route.age,
            "gender": route.gender,
            "country": route.country or "Colombia",
        },

        "learningProfile": {
            "topics": route.topics or [],
            "goal": route.goal or "",
        },

        "recommendedCourses": recommended_courses,

        "plan": {
            "packageCode": package_code,
            "tier": tier,
            "billingPeriod": billing_period,
            "accessStatus": access_status,
            "lifecycleStatus": lifecycle_status,
            "pendingAction": pending_action,
            "trial": {
                "isTrial": is_trial,
                "trialStart": trial_start.isoformat() if trial_start else None,
                "trialEnd": trial_end.isoformat() if trial_end else None,
                "trialDays": 7 if is_trial else 0,
            },
        },

        "billing": {
            "source": "COLOMBIA",
            "stripeCustomerId": stripe_customer_id,
            "stripeSubscriptionId": stripe_subscription_id,
            "stripePaymentMethodId": None,
            "status": subscription.status if subscription else None,
            "currentPeriodEnd": current_period_end.isoformat() if current_period_end else None,
        },

        "redirects": {
            "subscriptionManagementUrl": settings.MX_B2C_SUBSCRIPTION_MANAGEMENT_URL,
            "colombiaAccountUrl": settings.MX_B2C_COLOMBIA_ACCOUNT_URL,
        },

        "metadata": {
            "routeId": route.id,
            "selectedPaidPlan": plan_value,
            "selectedPlan": selected_plan,
            "createdFrom": "startNow",
            "stripePriceId": stripe_price_id,
            "colombiaUserId": user.id,
        },
    }

def send_b2c_access_event_to_mx(*, payload, user=None, route=None):
    event_id = payload["eventId"]
    event_type = payload["eventType"]
    occurred_at = payload["occurredAt"]

    raw_body = _json_dumps(payload)
    headers = _build_mx_headers(raw_body, event_id, occurred_at)

    log, created = MxAccessEventLog.objects.get_or_create(
        stripe_event_id=event_id,
        defaults={
            "user": user,
            "learning_route_id": route.id if route else None,
            "event_type": event_type,
            "event_source": "colombia_b2c",
            "payload_json": payload,
            "send_status": "pending",
            "attempts": 0,
        },
    )

    if not created and log.send_status == "sent":
        return {
            "ok": True,
            "status": log.mx_status or "DUPLICATE",
            "mxUserId": log.mx_user_id,
            "magicLink": log.magic_link,
            "skipped": True,
        }

    log.send_status = "processing"
    log.attempts = (log.attempts or 0) + 1
    log.save(update_fields=["send_status", "attempts", "updated_at"])

    try:
        response = requests.post(
            settings.MX_B2C_ACCESS_EVENT_URL,
            data=raw_body.encode("utf-8"),
            headers=headers,
            timeout=getattr(settings, "MX_B2C_TIMEOUT", 15),
        )

        try:
            response_json = response.json()
        except Exception:
            response_json = {"raw": response.text[:3000]}

        mx_status = response_json.get("status")
        mx_user_id = response_json.get("mxUserId")
        magic_link = response_json.get("magicLink")

        ok = response.ok and mx_status in ["APPLIED", "DUPLICATE"]

        log.response_json = response_json
        log.mx_status = mx_status
        log.mx_user_id = mx_user_id
        log.magic_link = magic_link
        log.send_status = "sent" if ok else "failed"
        log.sent_at = timezone.now() if ok else None
        log.last_error = None if ok else json.dumps(response_json, ensure_ascii=False)
        log.save(update_fields=[
            "response_json",
            "mx_status",
            "mx_user_id",
            "magic_link",
            "send_status",
            "sent_at",
            "last_error",
            "updated_at",
        ])

        return {
            "ok": ok,
            "status": mx_status,
            "http_status": response.status_code,
            "mxUserId": mx_user_id,
            "magicLink": magic_link,
            "response": response_json,
        }

    except Exception as e:
        log.send_status = "failed"
        log.last_error = str(e)
        log.save(update_fields=["send_status", "last_error", "updated_at"])

        return {
            "ok": False,
            "status": "RETRYABLE_ERROR",
            "error": str(e),
        }

MAX_PER_LEVEL = 3

LEVEL_RULES = {
    "level_1": {
        "label": "Nivel 1",
        "subtitle": "Fundamentos",
        "badge": "DISPONIBLE",
        "platform_ids": [2],  # Coursera
        "nivel": "BEGINNER",
    },
    "level_2": {
        "label": "Nivel 2",
        "subtitle": "Especialización",
        "badge": "PLAN X / PLUS",
        "platform_ids": [1, 3],  # EdX + MasterClass
        "nivel": "INTERMEDIATE",
    },
    "level_3": {
        "label": "Nivel 3",
        "subtitle": "Certificación",
        "badge": "PLAN PLUS",
        "platform_ids": [1, 2, 3],  # EdX + Coursera + MasterClass
        "nivel": "ADVANCED",
    },
}


def normalize_text(value):
    return (value or "").strip().lower()


def normalize_media_url(request, value):
    if not value:
        return ""

    value = str(value).strip()

    if not value or value.lower() in ["null", "none", "undefined"]:
        return ""

    if value.startswith("http://") or value.startswith("https://"):
        return value

    if value.startswith("/"):
        return request.build_absolute_uri(value)

    return request.build_absolute_uri(f"/media/{value}")


def get_cert_image(request, cert):
    image = cert.imagen_final or ""

    if not image:
        return ""

    if image.startswith("http://") or image.startswith("https://"):
        return image

    return request.build_absolute_uri(image)

def get_cert_institution(cert):
    if cert.universidad_certificacion:
        return cert.universidad_certificacion.nombre

    if cert.empresa_certificacion:
        return cert.empresa_certificacion.nombre

    return "Top Education"

def get_cert_provider(cert):
    if cert.plataforma_certificacion:
        return cert.plataforma_certificacion.nombre

    return ""

def get_cert_platform_logo(cert):
    platform = getattr(cert, "plataforma_certificacion", None)

    if not platform:
        return ""

    return (
        getattr(platform, "plat_ico", None)
        or getattr(platform, "icon", None)
        or ""
    )


def get_cert_main_skill(cert):
    skill = cert.skills.first()

    if not skill:
        return {
            "name": "",
            "icon": "",
        }

    return {
        "name": skill.translate or skill.nombre or "",
        "icon": skill.skill_ico or skill.skill_img or "",
    }

def serialize_recommended_cert(request, cert):
    main_skill = get_cert_main_skill(cert)

    return {
        "id": cert.id,
        "idInterno": cert.id_interno or "",
        "colombiaCertificationId": cert.id,
        "title": cert.nombre,
        "level": cert.nivel_certificacion,
        "hours": cert.tiempo_certificacion,
        "institution": get_cert_institution(cert),
        "provider": get_cert_provider(cert),
        "platform_logo": get_cert_platform_logo(cert),
        "main_skill": main_skill["name"],
        "main_skill_icon": main_skill["icon"],
        "image": get_cert_image(request, cert),
        "slug": cert.slug,
    }


def get_topic_skill_ids(topics):
    if not topics:
        return []

    clean_topics = [normalize_text(topic) for topic in topics if normalize_text(topic)]

    if not clean_topics:
        return []

    query = Q()

    for topic in clean_topics:
        query |= Q(nombre__icontains=topic)
        query |= Q(translate__icontains=topic)
        query |= Q(slug__icontains=topic.replace(" ", "-"))

    return list(
        Skills.objects.filter(query, estado=True)
        .values_list("id", flat=True)
        .distinct()
    )


def get_cert_ids_by_skills(skill_ids):
    if not skill_ids:
        return []

    return list(
        SkillsCertification.objects.filter(skill_id__in=skill_ids)
        .values_list("certificacion_id", flat=True)
        .distinct()
    )


def build_level_recommendations(request, cert_ids, rule):
    base_qs = (
        Certificaciones.objects
        .filter(
            plataforma_certificacion_id__in=rule["platform_ids"],
            nivel_certificacion=rule["nivel"],
        )
        .select_related(
            "plataforma_certificacion",
            "universidad_certificacion",
            "empresa_certificacion",
        )
        .order_by("?")
    )

    if cert_ids:
        matched_qs = base_qs.filter(id__in=cert_ids)
    else:
        matched_qs = base_qs

    selected = []
    selected_ids = set()

    # 1. Intentar traer mínimo 1 por proveedor
    for platform_id in rule["platform_ids"]:
        cert = matched_qs.filter(plataforma_certificacion_id=platform_id).first()

        if cert and cert.id not in selected_ids:
            selected.append(cert)
            selected_ids.add(cert.id)

        if len(selected) >= MAX_PER_LEVEL:
            break

    # 2. Completar hasta máximo 3
    if len(selected) < MAX_PER_LEVEL:
        extra_qs = matched_qs.exclude(id__in=selected_ids)[: MAX_PER_LEVEL - len(selected)]

        for cert in extra_qs:
          if cert.id not in selected_ids:
              selected.append(cert)
              selected_ids.add(cert.id)

    # 3. Fallback si no hubo suficientes por temas seleccionados
    if len(selected) < MAX_PER_LEVEL and cert_ids:
        fallback_qs = base_qs.exclude(id__in=selected_ids)[: MAX_PER_LEVEL - len(selected)]

        for cert in fallback_qs:
            if cert.id not in selected_ids:
                selected.append(cert)
                selected_ids.add(cert.id)

    return [serialize_recommended_cert(request, cert) for cert in selected[:MAX_PER_LEVEL]]


@method_decorator(csrf_exempt, name="dispatch")
class LearningRouteRecommendationsAPIView(APIView):
    authentication_classes = []
    permission_classes = []

    def post(self, request, *args, **kwargs):
        topics = request.data.get("topics") or []
        goal = request.data.get("goal") or ""

        if not isinstance(topics, list):
            return Response(
                {
                    "ok": False,
                    "error": "topics debe ser una lista.",
                },
                status=status.HTTP_400_BAD_REQUEST,
            )

        skill_ids = get_topic_skill_ids(topics)
        cert_ids = get_cert_ids_by_skills(skill_ids)

        data = {}

        for level_key, rule in LEVEL_RULES.items():
            data[level_key] = {
                "label": rule["label"],
                "subtitle": rule["subtitle"],
                "badge": rule["badge"],
                "platform_ids": rule["platform_ids"],
                "nivel": rule["nivel"],
                "items": build_level_recommendations(request, cert_ids, rule),
            }

        return Response(
            {
                "ok": True,
                "data": data,
                "meta": {
                    "topics": topics,
                    "goal": goal,
                    "skill_ids": skill_ids,
                    "matched_certification_ids_count": len(cert_ids),
                },
            },
            status=status.HTTP_200_OK,
        )

#ANALISIS DE CV
from django.utils.dateparse import parse_datetime   
from topeducation.models import CVAnalysis
from topeducation.services.cv_analysis_client import analyze_cv_with_provider


@method_decorator(csrf_exempt, name="dispatch")
class AccountCVAnalysisAPIView(APIView):
    authentication_classes = []
    permission_classes = []

    def post(self, request):
        file_obj = request.FILES.get("file") or request.FILES.get("cvFile")

        if not file_obj:
            return Response(
                {
                    "ok": False,
                    "data": None,
                    "message": "Debes enviar un archivo de CV.",
                    "errorCode": "cv_file_required",
                },
                status=status.HTTP_400_BAD_REQUEST,
            )

        max_size = 5 * 1024 * 1024

        if file_obj.size > max_size:
            return Response(
                {
                    "ok": False,
                    "data": None,
                    "message": "El archivo no puede superar los 5MB.",
                    "errorCode": "cv_file_too_large",
                },
                status=status.HTTP_400_BAD_REQUEST,
            )

        allowed_types = [
            "application/pdf",
            "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
            "application/msword",
        ]

        mime_type = getattr(file_obj, "content_type", "")

        if mime_type not in allowed_types:
            return Response(
                {
                    "ok": False,
                    "data": None,
                    "message": "Solo se permiten archivos PDF o Word.",
                    "errorCode": "cv_file_invalid_type",
                },
                status=status.HTTP_400_BAD_REQUEST,
            )

        language = (
            request.data.get("language")
            or request.data.get("locale")
            or request.data.get("outputLanguage")
            or "es-CO"
        )

        email = request.data.get("email") or ""
        route_id = request.data.get("route_id") or None

        try:
            provider_status, provider_data = analyze_cv_with_provider(
                file_obj,
                language=language,
            )

            if provider_status >= 400 or provider_data.get("ok") is False:
                return Response(
                    provider_data,
                    status=provider_status if provider_status < 500 else status.HTTP_502_BAD_GATEWAY,
                )

            data = provider_data.get("data") or {}
            score = data.get("score") or {}

            CVAnalysis.objects.create(
                user_email=email,
                route_id=route_id,
                filename=data.get("filename") or file_obj.name,
                mime_type=mime_type,
                language=data.get("language") or language,
                status=data.get("status") or "completed",
                score_value=score.get("value"),
                score_percentage=score.get("percentage"),
                score_label=score.get("label") or "",
                summary=data.get("summary") or "",
                recommendations=data.get("recommendations") or [],
                report=data.get("report") or {},
                raw_response=provider_data,
                analyzed_at=parse_datetime(data.get("analyzedAt")) if data.get("analyzedAt") else None,
            )

            return Response(provider_data, status=status.HTTP_200_OK)

        except requests.Timeout:
            return Response(
                {
                    "ok": False,
                    "data": None,
                    "message": "El análisis tardó demasiado. Intenta nuevamente.",
                    "errorCode": "openai_timeout",
                },
                status=status.HTTP_504_GATEWAY_TIMEOUT,
            )

        except Exception as e:
            return Response(
                {
                    "ok": False,
                    "data": None,
                    "message": "No se pudo analizar el CV.",
                    "errorCode": "cv_analysis_failed",
                    "details": {
                        "error": str(e),
                    },
                },
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )
        

class AccountCVLastAnalysisAPIView(APIView):
    authentication_classes = []
    permission_classes = []

    def get(self, request):
        email = request.GET.get("email") or ""

        if not email:
            return Response(
                {
                    "ok": False,
                    "data": None,
                    "message": "Email requerido.",
                },
                status=status.HTTP_400_BAD_REQUEST,
            )

        analysis = CVAnalysis.objects.filter(user_email=email).first()

        if not analysis:
            return Response(
                {
                    "ok": True,
                    "data": None,
                    "message": "No hay análisis previos.",
                },
                status=status.HTTP_200_OK,
            )

        return Response(
            {
                "ok": True,
                "data": {
                    "status": analysis.status,
                    "filename": analysis.filename,
                    "analyzedAt": analysis.analyzed_at,
                    "language": analysis.language,
                    "score": {
                        "value": float(analysis.score_value or 0),
                        "max": 10,
                        "percentage": analysis.score_percentage,
                        "label": analysis.score_label,
                    },
                    "summary": analysis.summary,
                    "recommendations": analysis.recommendations,
                    "report": analysis.report,
                },
            },
            status=status.HTTP_200_OK,
        )