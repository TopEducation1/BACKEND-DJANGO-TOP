from django.urls import path, include
from .views import *


urlpatterns = [
    path('certificaciones/', CertificationList.as_view(), name='certifications_list'),
    path('skills/', SkillsList.as_view(), name='skills_list'),
    path('universities/', UniversitiesList.as_view(), name='universities_list'),
    path('topics/', TopicsList.as_view(), name='topics_list'),
    path('api/searchTags/', receive_tags, name='receive_tags'),
    path('certificaciones/<int:id>/', CertificationDetailView.as_view(), name='get-certification'),
    path('certificaciones/filter/', filter_by_tags.as_view()    , name='filter-by-tags'),
    path('certificaciones/busqueda/', filter_by_search.as_view(), name='filter_by_search')
]