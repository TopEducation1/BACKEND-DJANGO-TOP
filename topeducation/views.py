from __future__ import annotations

from topeducation.inspectors.courses_inspector import fetch_and_parse_page
from topeducation.models import ExternalSyncState

from django.db.models import Q, Case, When, Value, IntegerField, OuterRef, Subquery, Prefetch
from django.db.models import Q, Case, When, Value, IntegerField, Prefetch

from django.db.models import OuterRef, Subquery, Case, When, Value, IntegerField, Prefetch

from datetime import datetime, timedelta, timezone
import pandas as pd
import re
import time
import traceback
import logging
import random
from django.core.cache import cache

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

from topeducation.services.import_courses import (
    ingest_course_payload,
    ingest_skills_structure_payload,
    ingest_specializations_payload,
    ingest_specialization_detail_payload,
)

from django.core.paginator import Paginator
from django.shortcuts import render


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
    cursos = Certificaciones.objects.filter(tipo_certificacion="Curso")
    especializaciones = Certificaciones.objects.filter(tipo_certificacion="Especialización")
    posts = Blog.objects.all()
    return render(request,'pages/dashboard.html',{'certifications':certifications,'edx':edx,'coursera':coursera,'masterclass':masterclass,'posts':posts,'cursos':cursos,'especializaciones':especializaciones})

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
    base_url = "https://99f51wnzz7.execute-api.us-east-1.amazonaws.com/colombia-endpoint/course-information"

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

    # Parse host
    try:
        parsed = urlparse(url)
        host = (parsed.netloc or "").lower()
        host = host.split(":")[0]  # ✅ quita :443, :80, etc.
    except Exception:
        return HttpResponseBadRequest("Invalid url")

    # ✅ Whitelist por seguridad (opcional pero recomendado)
    allowed_hosts = set((getattr(settings, "PROXY_HEADERS", {}) or {}).keys())
    if host not in allowed_hosts:
        return HttpResponseBadRequest("URL not allowed")

    # Headers base + headers del host
    headers = {"Accept": "application/json"}
    extra = (getattr(settings, "PROXY_HEADERS", {}) or {}).get(host, {}) or {}
    headers.update(extra)

    # ✅ Si la key está vacía, mejor falla claro (evita 403 confuso)
    if "x-api-key" in headers and not headers["x-api-key"]:
        return JsonResponse(
            {"error": "missing_api_key_env", "detail": "AWS_COURSES_API_KEY is empty in this environment"},
            status=500,
        )

    try:
        r = requests.get(url, headers=headers, timeout=60)
        content_type = (r.headers.get("content-type") or "").lower()

        # Si no es JSON, devolvemos el raw para debug
        if "application/json" not in content_type:
            return JsonResponse(
                {
                    "error": "upstream_not_json",
                    "status": r.status_code,
                    "url": url,
                    "raw": (r.text or "")[:4000],
                },
                status=502 if r.status_code >= 400 else 200,
            )

        data = r.json()
        return JsonResponse(data, status=r.status_code, safe=isinstance(data, dict))

    except Exception as e:
        return JsonResponse({"error": "proxy_failed", "detail": str(e)}, status=500)


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

        # Renombrar parent_id -> parent para que el front lo consuma igual
        for item in data:
            item["parent"] = item.pop("parent_id", None)

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
        try:
            if not slug:
                return Response(
                    {'error': 'Se requiere slug de certificación'},
                    status=status.HTTP_400_BAD_REQUEST
                )

            certification = (
                Certificaciones.objects
                .select_related(
                    'tema_certificacion',
                    'plataforma_certificacion',
                    'universidad_certificacion',
                    'empresa_certificacion',
                    'specialization'
                )
                .prefetch_related(
                    Prefetch(
                        'skills_rel',
                        queryset=SkillsCertification.objects.select_related('skill').order_by('orden', 'id'),
                        to_attr='skills_links_ordered'
                    ),
                    Prefetch(
                        'instructor_links',
                        queryset=InstructorCertification.objects.select_related('instructor'),
                        to_attr='instructor_links_prefetched'
                    )
                )
                .get(slug=slug)
            )

            serializer = CertificationSerializer(
                certification,
                context={'request': request}
            )

            return Response(serializer.data)

        except Certificaciones.DoesNotExist:
            return Response(
                {'error': 'Certificación no encontrada'},
                status=status.HTTP_404_NOT_FOUND
            )

        except Exception as e:
            return Response(
                {'error': str(e)},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )


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
            rows = (
                Certificaciones.objects
                .exclude(lenguaje_certificacion__isnull=True)
                .exclude(lenguaje_certificacion__exact="")
                .values_list("lenguaje_certificacion", flat=True)
            )

            grouped = defaultdict(int)

            for raw in rows:
                normalized_codes_in_row = set()

                for item in split_language_values(raw):
                    normalized = normalize_language_value(item)
                    if normalized:
                        normalized_codes_in_row.add(normalized["code"])

                for code in normalized_codes_in_row:
                    grouped[code] += 1

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

class filter_by_tags(APIView):
    pagination_class = CustomPagination

    def get(self, request):
        try:
            params = request.query_params.copy()

            tema_slugs = []
            habilidad_slugs = []
            plataforma_values = []
            empresa_values = []
            universidad_values = []
            idioma_codes = []

            for key, value_list in params.lists():
                if key in ["page", "page_size"]:
                    continue

                if key in ["Tema", "temas"]:
                    for value in value_list:
                        if not isinstance(value, str):
                            continue
                        for v in value.split(","):
                            cleaned = v.strip()
                            if cleaned:
                                tema_slugs.append(cleaned)

                elif key in ["Habilidad", "habilidades"]:
                    for value in value_list:
                        if not isinstance(value, str):
                            continue
                        for v in value.split(","):
                            cleaned = v.strip()
                            if cleaned:
                                habilidad_slugs.append(cleaned)

                elif key in ["Plataforma", "plataforma", "Aliados", "aliados"]:
                    for value in value_list:
                        if not isinstance(value, str):
                            continue
                        for v in value.split(","):
                            cleaned = v.strip()
                            if cleaned:
                                plataforma_values.append(cleaned)

                elif key in ["Empresa", "empresas", "Empresas"]:
                    for value in value_list:
                        if not isinstance(value, str):
                            continue
                        for v in value.split(","):
                            cleaned = v.strip()
                            if cleaned:
                                empresa_values.append(cleaned)

                elif key in ["Universidad", "universidades", "Universidades"]:
                    for value in value_list:
                        if not isinstance(value, str):
                            continue
                        for v in value.split(","):
                            cleaned = v.strip()
                            if cleaned:
                                universidad_values.append(cleaned)

                elif key in ["Idioma", "idioma"]:
                    for value in value_list:
                        if not isinstance(value, str):
                            continue
                        for v in value.split(","):
                            cleaned = v.strip().lower()
                            if cleaned:
                                idioma_codes.append(cleaned)

            tema_slugs = list(dict.fromkeys(tema_slugs))
            habilidad_slugs = list(dict.fromkeys(habilidad_slugs))
            plataforma_values = list(dict.fromkeys(plataforma_values))
            empresa_values = list(dict.fromkeys(empresa_values))
            universidad_values = list(dict.fromkeys(universidad_values))
            idioma_codes = list(dict.fromkeys(idioma_codes))

            skill_slugs = tema_slugs + habilidad_slugs

            first_skill_slug_subquery = SkillsCertification.objects.filter(
                certificacion_id=OuterRef("pk")
            ).order_by("orden", "id").values("skill__slug")[:1]

            queryset = (
                Certificaciones.objects
                .select_related(
                    "plataforma_certificacion",
                    "empresa_certificacion",
                    "universidad_certificacion",
                    "tema_certificacion",
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

            if plataforma_values:
                q_plataforma = Q()
                for value in plataforma_values:
                    q_plataforma |= Q(plataforma_certificacion__nombre__iexact=value)
                queryset = queryset.filter(q_plataforma)

            if empresa_values:
                q_empresa = Q()
                for value in empresa_values:
                    q_empresa |= Q(empresa_certificacion__nombre__iexact=value)
                queryset = queryset.filter(q_empresa)

            if universidad_values:
                q_universidad = Q()
                for value in universidad_values:
                    q_universidad |= Q(universidad_certificacion__nombre__iexact=value)
                queryset = queryset.filter(q_universidad)

            # Idioma optimizado por campo normalizado
            if idioma_codes:
                queryset = queryset.filter(language_normalized__in=idioma_codes)
            else:
                queryset = queryset.filter(language_normalized__in=["es", "en"])

            if skill_slugs:
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

            serializer = CertificationSearchSerializer(
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
            return Response(
                {
                    "results": [],
                    "count": 0,
                },
                status=status.HTTP_200_OK
            )

        idioma_values = filters.get("idioma", [])
        plataforma_values = filters.get("Plataforma", [])
        empresa_values = filters.get("Empresa", [])
        universidad_values = filters.get("Universidad", [])
        tema_values = filters.get("Tema", [])
        habilidad_values = filters.get("Habilidad", [])

        skill_slugs = tema_values + habilidad_values

        try:
            queryset = (
                Certificaciones.objects
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
                .filter(
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
            )

            # Plataforma
            if plataforma_values:
                q_plataforma = Q()
                for value in plataforma_values:
                    q_plataforma |= Q(plataforma_certificacion__nombre__iexact=value)
                queryset = queryset.filter(q_plataforma)

            # Empresa
            if empresa_values:
                q_empresa = Q()
                for value in empresa_values:
                    q_empresa |= Q(empresa_certificacion__nombre__iexact=value)
                queryset = queryset.filter(q_empresa)

            # Universidad
            if universidad_values:
                q_universidad = Q()
                for value in universidad_values:
                    q_universidad |= Q(universidad_certificacion__nombre__iexact=value)
                queryset = queryset.filter(q_universidad)

            # Idioma
            if idioma_values:
                q_idioma = Q()

                for value in idioma_values:
                    lang = (value or "").strip().lower()

                    if lang == "es":
                        q_idioma |= Q(lenguaje_certificacion__iexact="es")
                        q_idioma |= Q(lenguaje_certificacion__iexact="spanish")
                        q_idioma |= Q(lenguaje_certificacion__iexact="español")
                        q_idioma |= Q(lenguaje_certificacion__icontains="español")
                        q_idioma |= Q(lenguaje_certificacion__icontains="spanish")
                        q_idioma |= Q(lenguaje_certificacion__icontains="enseñado en español")

                    elif lang == "en":
                        q_idioma |= Q(lenguaje_certificacion__iexact="en")
                        q_idioma |= Q(lenguaje_certificacion__iexact="english")
                        q_idioma |= Q(lenguaje_certificacion__iexact="inglés")
                        q_idioma |= Q(lenguaje_certificacion__icontains="english")
                        q_idioma |= Q(lenguaje_certificacion__icontains="inglés")
                        q_idioma |= Q(lenguaje_certificacion__icontains="enseñado en inglés")

                    else:
                        q_idioma |= Q(lenguaje_certificacion__iexact=value)
                        q_idioma |= Q(lenguaje_certificacion__icontains=value)

                queryset = queryset.filter(q_idioma)

            # Skills / temas activos
            if skill_slugs:
                q_skills = Q()
                for value in skill_slugs:
                    q_skills |= Q(skills_rel__skill__slug__iexact=value)
                    q_skills |= Q(skills_rel__skill__nombre__iexact=value)
                    q_skills |= Q(skills_rel__skill__translate__iexact=value)
                    q_skills |= Q(tema_certificacion__nombre__iexact=value)
                    q_skills |= Q(tema_certificacion__translate__iexact=value)

                queryset = queryset.filter(q_skills)

            queryset = (
                queryset
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
                .distinct()
                .order_by("search_priority", "nombre")[:limit]
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
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )

        serializer = CertificationSearchSerializer(
            results,
            many=True,
            context={"request": request}
        )

        return Response(
            {
                "results": serializer.data,
                "count": len(results),
            },
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


logger = logging.getLogger(__name__)

#ACTUALIZACIÓN DE ENDPOINT 20 DE ABRIL

BASE_EXTERNAL_URL = "https://99f51wnzz7.execute-api.us-east-1.amazonaws.com/colombia-endpoint/course-information"
LOCK_TTL_SECONDS = 14 * 60


def _get_external_api_key():
    return (
        getattr(settings, "AWS_COURSES_API_KEY", None)
        or getattr(settings, "COURSES_EXTERNAL_API_KEY", None)
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
    if resource == "courses":
        return f"{BASE_EXTERNAL_URL}/courses"
    if resource == "certifications":
        return f"{BASE_EXTERNAL_URL}/certifications"
    if resource == "skills-structure":
        return f"{BASE_EXTERNAL_URL}/skills-structure"
    if resource == "specializations":
        return f"{BASE_EXTERNAL_URL}/specializations"
    if resource == "specialization-detail":
        return f"{BASE_EXTERNAL_URL}/specializations/{specialization_id}"
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
    MAX_HTTP_SECONDS = 240

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
    max_pages_per_run = max(1, min(max_pages_per_run, 1))
    page_size = max(1, min(page_size, 50))
    timeout = max(5, min(timeout, 120))

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

        ExternalSyncLog.objects.create(
            key=state_key,
            run_id=run_id,
            page=page if uses_cursor else None,
            page_size=page_size if uses_cursor else None,
            ok=True,
            took_ms=int((time.time() - t0) * 1000),
            detail=(
                f"RUN_STARTED resource={resource} provider={provider or '-'} "
                f"endpoint={endpoint} page={page} page_size={page_size} "
                f"max_pages_per_run={max_pages_per_run}"
            ),
        )

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

            ExternalSyncLog.objects.create(
                key=state_key,
                run_id=run_id,
                page=page if uses_cursor else None,
                page_size=page_size if uses_cursor else None,
                ok=True,
                took_ms=int((time.time() - t0) * 1000),
                detail=(
                    f"FETCH_START resource={resource} provider={provider or '-'} "
                    f"page={page} page_size={page_size} params={json.dumps(params, default=str)[:1500]}"
                ),
            )

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

            ExternalSyncLog.objects.create(
                key=state_key,
                run_id=run_id,
                page=page if uses_cursor else None,
                page_size=page_size if uses_cursor else None,
                ok=True,
                items_len=items_len,
                received=items_len,
                took_ms=int((time.time() - t0) * 1000),
                detail=(
                    f"FETCH_OK_BEFORE_INGEST resource={resource} "
                    f"provider={provider or '-'} page={page} "
                    f"items_len={items_len} total_pages={total_pages}"
                ),
            )

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

            ExternalSyncLog.objects.create(
                key=state_key,
                run_id=run_id,
                page=page if uses_cursor else None,
                page_size=page_size if uses_cursor else None,
                ok=True,
                items_len=items_len,
                received=items_len,
                took_ms=int((time.time() - t0) * 1000),
                detail=(
                    f"INGEST_OK resource={resource} provider={provider or '-'} "
                    f"page={page} summary={json.dumps(summary, default=str)[:1500]}"
                ),
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
CACHE_KEY = "home_skills_grid_v1"
CACHE_TIMEOUT = 60 * 30  # 30 minutos


def normalize_media_url(request, value):
    if not value:
        return ""

    value = str(value).strip()
    if not value:
        return ""

    low = value.lower()
    if low in {"none", "null", "false"}:
        return ""

    # Ya es absoluta
    if value.startswith("http://") or value.startswith("https://"):
        return value

    # Assets del frontend
    if value.startswith("/assets/") or value.startswith("assets/"):
        frontend_url = getattr(settings, "FRONTEND_URL", "").rstrip("/")
        clean_path = value if value.startswith("/") else f"/{value}"
        return f"{frontend_url}{clean_path}"

    # Media/archivos del backend
    return request.build_absolute_uri(value)


def normalize_skill_type_for_filter(skill_type):
    value = str(skill_type or "").strip().lower()

    if value == "tema":
        return "Temas"

    if value == "habilidad":
        return "Habilidades"

    return "Skills"

def build_cert_link(cert):
    slug = getattr(cert, "slug", "") or ""
    slug = str(slug).strip()

    if not slug:
        return None

    plataforma = getattr(cert, "plataforma_certificacion", None)
    plataforma_slug = getattr(plataforma, "slug", "") if plataforma else ""
    plataforma_slug = str(plataforma_slug or "").strip()

    if plataforma_slug:
        return f"/certificacion/{plataforma_slug}/{slug}"

    return f"/certificacion/{slug}"


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
    """
    Fallback mínimo si instructores_certificacion viene como string.
    Solo devuelve nombres; sin imagen no nos sirve para el home,
    pero se deja por robustez.
    """
    if not raw or not isinstance(raw, str):
        return []

    text = raw.strip()
    if not text or text.lower() in {"none", "null", "[]"}:
        return []

    parts = (
        text.replace(" y ", ",")
        .replace(" and ", ",")
        .split(",")
    )

    return [{"name": p.strip(), "img": ""} for p in parts if p.strip()]


def get_certification_instructors(cert):
    """
    Unifica instructores sin importar si vienen:
    - en un JSON/lista dentro de instructores_certificacion
    - en una relación instructoresCertificacion
    - o en otros formatos mixtos
    """
    normalized = []

    # Caso 1: cert.instructores_certificacion ya viene como lista/json
    raw = getattr(cert, "instructores_certificacion", None)
    if isinstance(raw, list):
        for item in raw:
            if isinstance(item, dict):
                normalized.append({
                    "name": normalize_instructor_name(item),
                    "img": normalize_instructor_image(item),
                })

    # Caso 2: cert.instructores_certificacion viene como string
    elif isinstance(raw, str):
        normalized.extend(parse_instructors_text(raw))

    # Caso 3: relación aparte tipo instructoresCertificacion
    related = getattr(cert, "instructoresCertificacion", None)
    if related is not None:
        try:
            for ins in related.all():
                name = (
                    getattr(ins, "nombre", None)
                    or getattr(ins, "name", None)
                    or ""
                )
                img = (
                    getattr(ins, "foto", None)
                    or getattr(ins, "image", None)
                    or getattr(ins, "img", None)
                    or ""
                )

                normalized.append({
                    "name": str(name).strip(),
                    "img": str(img).strip() if img else "",
                })
        except Exception:
            pass

    # Limpieza
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


class HomeSkillsGridAPIView(APIView):
    permission_classes = []

    def get(self, request, *args, **kwargs):
        cached = cache.get(CACHE_KEY)
        if cached:
            return Response(cached)

        skills = (
            Skills.objects.filter(
                parent__isnull=True,
                estado=True,
            )
            .exclude(Q(skill_ico__isnull=True) | Q(skill_ico__exact=""))
            .order_by("id")
        )

        response_data = []

        for skill in skills:
            certs = (
                Certificaciones.objects.filter(
                    skills_rel__skill=skill
                )
                .select_related(
                    "universidad_certificacion",
                    "empresa_certificacion",
                    "plataforma_certificacion",
                )
                .distinct()
            )

            related_items = []

            seen_universities = set()
            seen_companies = set()
            seen_certs = set()

            # Universidades
            for cert in certs:
                uni = getattr(cert, "universidad_certificacion", None)
                if not uni:
                    continue

                uni_name = getattr(uni, "nombre", "") or ""
                uni_icon = getattr(uni, "univ_ico", "") or ""

                if not uni_name or not uni_icon:
                    continue

                key = f"uni-{getattr(uni, 'id', uni_name)}"
                if key in seen_universities:
                    continue

                seen_universities.add(key)
                related_items.append({
                    "name": uni_name,
                    "type": "Universidades",
                    "img": normalize_media_url(request, uni_icon),
                })

            # Empresas
            for cert in certs:
                emp = getattr(cert, "empresa_certificacion", None)
                if not emp:
                    continue

                emp_name = getattr(emp, "nombre", "") or ""
                emp_icon = getattr(emp, "empr_ico", "") or ""

                if not emp_name or not emp_icon:
                    continue

                key = f"emp-{getattr(emp, 'id', emp_name)}"
                if key in seen_companies:
                    continue

                seen_companies.add(key)
                related_items.append({
                    "name": emp_name,
                    "type": "Empresas",
                    "img": normalize_media_url(request, emp_icon),
                })

            # Certificaciones solo si la skill es habilidad
            if str(skill.skill_type or "").strip().lower() == "habilidad":
                for cert in certs:
                    cert_name = getattr(cert, "nombre", "") or ""
                    cert_link = build_cert_link(cert)
                    instructor_img = pick_first_instructor_image(cert, request)

                    if not cert_name or not cert_link or not instructor_img:
                        continue

                    key = f"cert-{getattr(cert, 'id', cert_name)}"
                    if key in seen_certs:
                        continue

                    seen_certs.add(key)
                    related_items.append({
                        "name": cert_name,
                        "type": "Certificacion",
                        "img": instructor_img,
                        "link": cert_link,
                    })

            random.shuffle(related_items)
            related_items = related_items[:MAX_ITEMS_PER_SKILL]

            response_data.append({
                "id": skill.id,
                "name": (skill.translate or skill.nombre or "").strip(),
                "type": normalize_skill_type_for_filter(skill.skill_type),
                "img": normalize_media_url(request, skill.skill_img),
                "color": COLOR_MAP.get(skill.skill_col, "#034694"),
                "description": (skill.descripcion or "").strip(),
                "universities": related_items,
            })

        random.shuffle(response_data)

        cache.set(CACHE_KEY, response_data, CACHE_TIMEOUT)
        return Response(response_data)