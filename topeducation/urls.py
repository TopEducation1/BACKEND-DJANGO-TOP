from django.urls import path, include
from .views import *
from rest_framework import routers


urlpatterns = [
    path('certificaciones/', CertificationList.as_view(), name='certifications_list'),
    path('skills/', SkillsList.as_view(), name='skills_list'),
    path('universities/', UniversitiesList.as_view(), name='universities_list'),
    path('topics/', TopicsList.as_view(), name='topics_list'),
    path('api/searchTags/', receive_tags, name='receive_tags'),
    path('certificaciones/<int:id>/', get_certification, name='get-certification'),
    path('certificaciones/filter/', filter_by_tags, name='filter-by-tags')
]