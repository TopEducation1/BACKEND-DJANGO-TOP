from django.contrib import sitemaps
from django.contrib.sitemaps.views import sitemap

from django.urls import path, include
from .views import *
from . import views


from django.contrib.auth.decorators import login_required
from django.conf import settings
from django.conf.urls.static import static

from .sitemaps import CertificacionSitemap, BlogSitemap

sitemaps_dict = {
    'certificaciones': CertificacionSitemap,
    'recursos': BlogSitemap,
}

urlpatterns = [
    path('',login_required(views.dashboard,login_url='/signin/'), name='inicio'),
    path('dashboard/',login_required(views.dashboard,login_url='/signin/'), name='dashboard'),
    path('signin/',views.signin, name='signin'),
    path('logout/',views.signout, name='logout'),
    path('certifications/',login_required(views.certifications,login_url='/signin/'), name='certifications'),
    path('certifications/upload/',login_required(views.upload,login_url='/signin/'), name='upload'),
    path('certifications/create/',views.createCertification, name='createCertification'),
    path('certifications/<int:certification_id>/update/',login_required(views.updateCertification,login_url='/signin/'), name='updateCertification'),
    path('certifications/<int:certification_id>/delete/',login_required(views.deleteCertification,login_url='/signin/'), name='deleteCertification'),
    path('posts/create/',login_required(views.createPost,login_url='/signin/'), name='createPost'),
    path('posts/',login_required(views.posts,login_url='/signin/'), name='posts'),
    path('posts/<int:post_id>/update/',login_required(views.updatePost,login_url='/signin/'), name='updatePost'),
    path('posts/<int:post_id>/delete/',login_required(views.deletePost,login_url='/signin/'), name='deletePost'),
    path('certificaciones/', CertificationList.as_view(), name='certifications_list'),
    path('skills/', SkillsList.as_view(), name='skills_list'),
    path('universities/', UniversitiesList.as_view(), name='universities_list'),
    path('topics/', TopicsList.as_view(), name='topics_list'),
    path('api/searchTags/', receive_tags, name='receive_tags'),
    path('certificacion/<slug:slug>/', CertificationDetailView.as_view(), name='get-certification'),
    path('certificaciones/filter/', filter_by_tags.as_view()    , name='filter-by-tags'),
    path('certificaciones/busqueda/', filter_by_search.as_view(), name='filter_by_search'),
    path('certificacionesInterest/', CertificationsCafam.as_view(), name="certificaciones_interest"),
    path('cafam/certificacion/<slug:slug>/', CertificationDetailView.as_view(), name='get-certification'),
    path('blogs/', BlogList.as_view(), name="blog-list"),
    path('blog/<slug:slug>/', BlogDetailView.as_view(), name="get-blog"),
    path('masterclass-certificaciones-grid/', MasterclassCertificationsGrids.as_view(), name="masterclass-certificaciones-grid/"),
    path('documents/<str:nombre_archivo>/', views.descargar_excel, name='descargar_excel'),
    path('error-404/', error_404),
    path('api/universities/', UniversitiesList.as_view(), name='universities-list'),
    path('api/universities-by-region/', UniversitiesByRegion.as_view(), name='universities-by-region'),
    path('api/topics/', TopicsList.as_view(), name='topics-list'),
    path('api/platforms/', PlatformsList.as_view(), name='platforms-list'),
    path('api/companies/', CompaniesList.as_view(), name='companies-list'),
    path('originals/<slug:slug>/', OriginalDetailView.as_view(), name='original-detail'),
    path('api/latest-certifications/', LatestCertificationsView.as_view(), name='latest_certifications'),
    path('sitemap.xml', sitemap, {'sitemaps': sitemaps_dict}, name='sitemap'),

] + static(settings.STATIC_URL, document_root=settings.STATIC_ROOT)
if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
