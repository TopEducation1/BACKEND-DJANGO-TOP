from django.urls import path, include
from .views import *


urlpatterns = [
    path('certificaciones/', CertificationList.as_view(), name='certifications_list'),
    path('skills/', SkillsList.as_view(), name='skills_list'),
    path('universities/', UniversitiesList.as_view(), name='universities_list'),
    path('topics/', TopicsList.as_view(), name='topics_list'),
    path('api/searchTags/', receive_tags, name='receive_tags'),
    path('certificacion/<slug:slug>/', CertificationDetailView.as_view(), name='get-certification'),
    path('certificaciones/filter/', filter_by_tags.as_view()    , name='filter-by-tags'),
    path('certificaciones/busqueda/', filter_by_search.as_view(), name='filter_by_search'),
    path('certificacionesInterest/', CertificationsCafam.as_view(), name="certificaciones_interest"),
    path('ultimasCertificaciones/', latest_certifications, name="last_certifications"),
    path('blogs/', BlogList.as_view(), name="blog-list"),
    path('blog/<slug:slug>/', BlogDetailView.as_view(), name="get-blog"),
    path('masterclass-certificaciones-grid/', MasterclassCertificationsGrids.as_view(), name="masterclass-certificaciones-grid/")
]