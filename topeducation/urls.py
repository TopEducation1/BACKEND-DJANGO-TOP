from django.contrib import sitemaps
from django.contrib.sitemaps.views import sitemap

from django.urls import path, include
from .views import *
from . import views


from django.contrib.auth.decorators import login_required
from django.conf import settings
from django.conf.urls.static import static

from .sitemaps import CertificacionSitemap, BlogSitemap
from .views import sync_courses_from_external
from .account_views import account_me, account_purchases


sitemaps_dict = {
    'certificaciones': CertificacionSitemap,
    'recursos': BlogSitemap,
}

urlpatterns = [
    path('',login_required(views.dashboard,login_url='/signin/'), name='inicio'),
    path("select2/", include("django_select2.urls")),
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
    
    path('category/',login_required(views.categories,login_url='/signin/'), name='categories'),
    path('category/universities/',login_required(views.universities,login_url='/signin/'), name='universities'),
    path('category/universities/<int:university_id>/update/',login_required(views.updateUniversity,login_url='/signin/'), name='updateUniversity'),
    path('category/universities/create/',login_required(views.createUniversity,login_url='/signin/'), name='createUniversity'),
    path('category/companies/',login_required(views.companies,login_url='/signin/'), name='companies'),
    path('category/companies/<int:company_id>/update/',login_required(views.updateCompany,login_url='/signin/'), name='updateCompany'),
    path('category/companies/create/',login_required(views.createCompany,login_url='/signin/'), name='createCompany'),
    path('category/topics/',login_required(views.topics,login_url='/signin/'), name='topics'),
    path('category/topics/<int:topic_id>/update/',login_required(views.updateTopic,login_url='/signin/'), name='updateTopic'),
    path('category/topics/create/',login_required(views.createTopic,login_url='/signin/'), name='createTopic'),
    path('category/tags/',login_required(views.tags,login_url='/signin/'), name='tags'),
    path('category/tags/<int:tag_id>/update/',login_required(views.updateTag,login_url='/signin/'), name='updateTag'),
    path('category/tags/create/',login_required(views.createTag,login_url='/signin/'), name='createTag'),
    path('category/rankings/',login_required(views.rankings,login_url='/signin/'), name='rankings'),
    path('category/rankings/<int:ranking_id>/update/',login_required(views.updateRanking,login_url='/signin/'), name='updateRanking'),
    path('category/rankings/create/',login_required(views.createRanking,login_url='/signin/'), name='createRanking'),
    path('category/originals/',login_required(views.originals,login_url='/signin/'), name='originals'),
    path('category/originals/<int:original_id>/update/',login_required(views.updateOriginal,login_url='/signin/'), name='updateOriginal'),
    path('category/originals/create/',login_required(views.createOriginal,login_url='/signin/'), name='createOriginal'),
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
    path('api/originals/', OriginalsList.as_view(), name='originals-list'),
    path('api/rankings/', RankingsList.as_view(), name='rankings-list'),
    path('originals/<slug:slug>/', OriginalDetailView.as_view(), name='original-detail'),
    path('ranking/<slug:slug>/', RankingDetailView.as_view(), name='ranking-detail'),
    path('api/latest-certifications/', LatestCertificationsView.as_view(), name='latest_certifications'),
    path("brand/", views.brand_list, name="brand_list"),
    path("brand/new/", views.brand_update, name="brand_create"),
    path("brand/<int:marca_id>/update/", views.brand_update, name="brand_update"),
    path("brand/<int:marca_id>/settings/", views.brand_settings, name="brand_settings"),
    path("api/brand/<slug:slug>/", MarcaPublicBySlugView.as_view(), name="brand_public_slug"),
    path('sitemap.xml', sitemap, {'sitemaps': sitemaps_dict}, name='sitemap'),
    path("ckeditor/", include("ckeditor_uploader.urls")),
    path("inspector/catalog/", views.catalog_inspector, name="catalog_inspector"),
    path("bussines/purchases/", login_required(views.admin_purchases_page, login_url="/signin/"),name="admin_purchases_page"),
    path("api/proxy/", views.proxy_json, name="proxy_json"),
    path("api/proxy/courses/", views.proxy_json, name="proxy_courses"),
    path("api/sync/courses/run/", views.api_run_courses_sync, name="api_run_courses_sync"),
    path("api/sync/courses/", views.sync_courses_from_external, name="sync_courses_from_external"),
    path("api/stripe/create-checkout-session/", views.create_checkout_session, name="create_checkout_session"),
    path('api/stripe/webhook/', views.stripe_webhook, name='stripe_webhook'),
    path("api/stripe/sync-session/", views.stripe_sync_session, name="stripe_sync_session"),
    path("api/account/purchases/", account_purchases, name="account_purchases"),
    path("api/auth/register/", views.auth_register, name="auth_register"),
    path("api/auth/login/", views.auth_login, name="auth_login"),
    path("api/auth/logout/", views.auth_logout, name="auth_logout"),
    path("api/account/me/", views.account_me, name="account_me"),
    path("api/auth/password/reset/", views.auth_password_reset_request, name="auth_password_reset_request"),
    path("api/auth/password/reset/confirm/", views.auth_password_reset_confirm, name="auth_password_reset_confirm"),
    path("api/admin/purchases/",login_required(views.admin_purchases_api, login_url="/signin/"),name="admin_purchases_api"),
    

] + static(settings.STATIC_URL, document_root=settings.STATIC_ROOT)
if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
