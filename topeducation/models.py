from django.db import models
from django.utils.text import slugify
from django.utils import timezone
from ckeditor_uploader.fields import RichTextUploadingField
from django.conf import settings
import uuid

class Habilidades (models.Model):
    nombre = models.CharField(max_length=250)
    def __str__(self):
        return self.nombre
    
    class Meta:
        db_table = 'Habilidades'
        

class Temas(models.Model):
    nombre = models.CharField(max_length=250, null=True)
    translate = models.CharField(max_length=250, null=True)
    tem_type = models.CharField(max_length=50, null=True)
    tem_col = models.CharField(max_length=10, null=True)
    tem_img = models.CharField(max_length=200, null=True)
    tem_est = models.CharField(max_length=20, null=True)

    # ✅ NUEVO: relación a sí mismo (padre)
    parent = models.ForeignKey(
        "self",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="children",
        db_column="parent_id",  # opcional (si quieres que la columna se llame así)
    )

    def __str__(self):
        return self.nombre or f"Tema {self.pk}"

    class Meta:
        db_table = "Temas"
        
class Skills(models.Model):
    nombre = models.CharField(max_length=250, null=True, blank=True)
    translate = models.CharField(max_length=250, null=True, blank=True)
    descripcion = models.TextField(null=True, blank=True)
    slug = models.SlugField(max_length=300, null=True, blank=True, unique=True)
    skill_col = models.CharField(max_length=10, null=True)
    skill_type = models.CharField(max_length=50, null=True)
    skill_img = models.CharField(max_length=200, null=True, blank=True)
    skill_ico = models.CharField(max_length=200, null=True, blank=True)
    estado = models.BooleanField(default=True)

    parent = models.ForeignKey(
        "self",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="children",
        db_column="parent_id",
    )

    # NUEVO
    external_skill_id = models.CharField(max_length=255, null=True, blank=True, db_index=True)
    source_provider = models.CharField(max_length=50, null=True, blank=True, db_index=True)
    raw_payload = models.JSONField(default=dict, blank=True)

    class Meta:
        db_table = 'Skills'

    def __str__(self):
        return self.nombre or ''


class SkillsCertification(models.Model):
    certificacion = models.ForeignKey(
        "Certificaciones",
        on_delete=models.CASCADE,
        related_name="skills_rel",
    )

    skill = models.ForeignKey(
        "Skills",
        on_delete=models.CASCADE,
        related_name="certificaciones_rel",
    )

    orden = models.PositiveIntegerField(
        default=1,
        db_index=True,
    )

    created_at = models.DateTimeField(
        auto_now_add=True,
    )

    class Meta:
        db_table = "SkillsCertification"

        constraints = [
            models.UniqueConstraint(
                fields=[
                    "certificacion",
                    "skill",
                ],
                name="uq_certificacion_skill",
            ),
        ]

        indexes = [
            models.Index(
                fields=[
                    "skill",
                    "certificacion",
                ],
                name="idx_skill_cert",
            ),
        ]

        ordering = [
            "orden",
            "id",
        ]

    def __str__(self):
        return (
            f"{self.certificacion_id} - "
            f"{self.skill_id} ({self.orden})"
        )

class Regiones(models.Model):
    nombre = models.CharField(max_length=100, null=True)

    def __str__(self):
        return str(self.id) + " - " + self.nombre

    class Meta:
        db_table = 'Regiones'


class Universidades(models.Model):
    nombre = models.CharField(max_length=500, null=False, verbose_name='Nombre')
    region_universidad = models.ForeignKey(Regiones, on_delete=models.SET_NULL, null=True, related_name='universidades')
    univ_img = models.CharField(max_length=300, null=True, verbose_name='Imagen')
    univ_fla = models.CharField(max_length=200, null=True, verbose_name='Bandera')
    univ_ico = models.CharField(max_length=100, null=True, verbose_name='Icono')
    univ_est = models.CharField(max_length=50, null=True, verbose_name='Estado')
    univ_top = models.CharField(max_length=5, null=True, blank=True, verbose_name='Ranking global')
    descripcion_institucion = models.TextField(null=True, blank=True)

    def __str__(self):
        return str(self.id) + " - " + self.nombre

    class Meta:
        db_table = 'Universidades'


class Empresas(models.Model):
    nombre = models.CharField(max_length=500, null=False, verbose_name='Nombre')
    empr_img = models.CharField(max_length=200, null=True, verbose_name='Imagen')
    empr_ico = models.CharField(max_length=100, null=True, verbose_name='Icono')
    empr_est = models.CharField(max_length=50, null=True, verbose_name='Estado')
    empr_top = models.CharField(max_length=5, blank=True, null=True, verbose_name='Ranking global')
    descripcion_institucion = models.TextField(null=True, blank=True)

    def __str__(self):
        return str(self.id) + " - " + self.nombre

    class Meta:
        db_table = 'Empresas'


class Plataformas(models.Model):
    nombre = models.CharField(max_length=500, null=False)
    plat_img = models.CharField(max_length=200, null=True)
    plat_ico = models.CharField(max_length=100, null=True)

    def __str__(self):
        return self.nombre

    class Meta:
        db_table = 'Plataformas'


class Specialization(models.Model):
    specialization_id = models.CharField(max_length=255, unique=True, db_index=True)
    specialization_name = models.CharField(max_length=500)
    provider = models.CharField(max_length=50, null=True, blank=True, db_index=True)

    raw_payload = models.JSONField(default=dict, blank=True)
    estado = models.BooleanField(default=True)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'Specializations'
        ordering = ['specialization_name']

    def __str__(self):
        return f"{self.specialization_id} - {self.specialization_name}"


class Certificaciones(models.Model):
    nombre = models.CharField(max_length=500)
    slug = models.SlugField(max_length=500, default="default-slug")
    tema_certificacion = models.ForeignKey(Temas, on_delete=models.SET_NULL, null=True)

    palabra_clave_certificacion = models.TextField()
    metadescripcion_certificacion = models.TextField(default="NONE")
    instructores_certificacion = models.TextField(default="NONE")
    nivel_certificacion = models.CharField(max_length=255, default="NONE")
    tiempo_certificacion = models.CharField(max_length=255, default="NONE")
    lenguaje_certificacion = models.CharField(max_length=255, default="NONE")
    aprendizaje_certificacion = models.TextField(default="NONE")
    habilidades_certificacion = models.TextField(default="NONE")
    experiencia_certificacion = models.TextField(default="NONE")
    testimonios_certificacion = models.TextField(default="NONE")
    contenido_certificacion = models.TextField(blank=True, verbose_name='Contenido', default="NONE")
    modulos_certificacion = models.TextField(default="NONE")

    tipo_certificacion = models.CharField(max_length=100, null=True, blank=True, default="NONE")
    vigente_certificacion = models.BooleanField(
        default=True,
        db_index=False,
    )

    universidad_certificacion = models.ForeignKey(
        Universidades,
        related_name="certificaciones",
        on_delete=models.SET_NULL,
        null=True,
        blank=True
    )
    empresa_certificacion = models.ForeignKey(
        Empresas,
        related_name="certificaciones",
        on_delete=models.SET_NULL,
        null=True,
        blank=True
    )
    plataforma_certificacion = models.ForeignKey(Plataformas, on_delete=models.CASCADE, null=True, blank=True)

    # NUEVOS
    source_provider = models.CharField(
        max_length=50,
        null=True,
        blank=True,
        db_index=True
    )

    id_interno = models.CharField(
        max_length=255,
        null=True,
        blank=True,
        db_index=True,
        help_text="Identificador interno utilizado por la plataforma Mexico"
    )

    specialization = models.ForeignKey(
        Specialization,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='certificaciones'
    )
    specialization_id_external = models.CharField(max_length=255, null=True, blank=True, db_index=True)
    specialization_name_external = models.CharField(max_length=500, null=True, blank=True)

    country = models.CharField(max_length=120, null=True, blank=True, default="Global")
    region = models.CharField(max_length=120, null=True, blank=True, default="Global")

    mapping_status = models.CharField(max_length=50, null=True, blank=True, default="uncategorized", db_index=True)
    language_normalized = models.CharField(max_length=120, null=True, blank=True)

    skills_internal_json = models.JSONField(default=list, blank=True)
    subskills_internal_json = models.JSONField(default=list, blank=True)

    reconciliation_snapshot = models.JSONField(default=dict, blank=True)
    raw_payload = models.JSONField(default=dict, blank=True)

    fecha_creado_cert = models.DateField(auto_now_add=True, null=False)
    url_certificacion_original = models.CharField(max_length=300, default="Null")
    video_certificacion = models.CharField(default='Null', null=True, blank=True, max_length=1000)
    imagen_final = models.CharField(default='', null=True, blank=True, max_length=255)
    cert_top = models.CharField(max_length=5, blank=True, null=True, verbose_name='Ranking global')

    skills = models.ManyToManyField(
        'Skills',
        through='SkillsCertification',
        related_name='certificaciones',
        blank=True
    )

    def save(self, *args, **kwargs):
        if not self.slug or self.slug.startswith("slice"):
            self.slug = slugify(self.nombre)
            base_slug = self.slug
            counter = 1
            while Certificaciones.objects.filter(slug=self.slug).exists():
                self.slug = f"{base_slug}-{counter}"
                counter += 1
        super().save(*args, **kwargs)

    def __str__(self):
        return str(self.id) + " - " + self.nombre

    class Meta:
        db_table = "Certificaciones"

        indexes = [
            models.Index(
                fields=["tipo_certificacion"],
                name="cert_tipo_idx",
            ),
            models.Index(
                fields=["nivel_certificacion"],
                name="cert_nivel_idx",
            ),
            models.Index(
                fields=["language_normalized"],
                name="cert_language_idx",
            ),
            models.Index(
                fields=["plataforma_certificacion"],
                name="cert_plat_idx",
            ),

            # Recomendaciones por plataforma y nivel.
            models.Index(
                fields=[
                    "vigente_certificacion",
                    "plataforma_certificacion",
                    "nivel_certificacion",
                    "id",
                ],
                name="idx_rec_platform_level",
            ),

            # Explora: filtra por estado e idioma y ordena/pagina por id.
            models.Index(
                fields=[
                    "vigente_certificacion",
                    "language_normalized",
                    "id",
                ],
                name="idx_cert_active_lang",
            ),
        ]


class Instructores(models.Model):
    nombre = models.CharField(max_length=250, null=True, blank=True)
    imagen = models.TextField(null=True, blank=True)
    estado = models.BooleanField(default=True)

    def __str__(self):
        return self.nombre or f"Instructor {self.pk}"

    class Meta:
        db_table = 'Instructores'


class InstructorCertification(models.Model):
    certificacion = models.ForeignKey(
        'Certificaciones',
        on_delete=models.CASCADE,
        related_name='instructor_links'
    )
    instructor = models.ForeignKey(
        'Instructores',
        on_delete=models.CASCADE,
        related_name='certification_links'
    )

    class Meta:
        db_table = 'InstructorCertification'
        unique_together = ('certificacion', 'instructor')


class ExternalReconciliationSnapshot(models.Model):
    resource = models.CharField(max_length=50, db_index=True)  # courses / certifications
    provider_filter = models.CharField(max_length=50, null=True, blank=True, db_index=True)
    page = models.PositiveIntegerField(default=1)
    page_size = models.PositiveIntegerField(default=20)

    payload = models.JSONField(default=dict, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = 'ExternalReconciliationSnapshot'
        ordering = ['-created_at']

    def __str__(self):
        return f"{self.resource} - {self.provider_filter or 'ALL'} - {self.created_at}"
    
class Autor(models.Model):
    nombre_autor = models.CharField(max_length=255)
    auto_img = models.CharField(max_length=500, blank=True, null=True)

    def __str__(self):
        return self.nombre_autor

    class Meta:
        managed = False  # Para evitar que Django gestione la tabla
        db_table = 'autores'

class CategoriaBlog(models.Model):
    nombre_categoria_blog = models.CharField(max_length=255)

    def __str__(self):
        return self.nombre_categoria_blog

    class Meta:
        managed = False
        db_table = 'categorias_blog'

class Blog(models.Model):
    nombre_blog = models.CharField(max_length=255,verbose_name='Título')
    slug = models.SlugField(max_length=500, default="default-slug",verbose_name='Slug')
    fecha_redaccion_blog = models.DateField(auto_now_add=True,verbose_name='Fecha')
    miniatura_blog = models.ImageField(upload_to='blogs/banners/', null=True, blank=True,verbose_name='Imagen')
    palabra_clave_blog = models.CharField(max_length=255,verbose_name='Palabra clave')
    metadescripcion_blog = models.TextField(null=True,verbose_name='Metadescripción')
    objetivo_blog = models.TextField(null=True,verbose_name='Objetivo')
    contenido = models.TextField(blank=True,verbose_name='Contenido')
    contenido = RichTextUploadingField(verbose_name='Contenido', blank=True)
    autor_blog = models.ForeignKey(Autor, on_delete=models.CASCADE, db_column='autor_blog_id',verbose_name='Autor')
    categoria_blog = models.ForeignKey(CategoriaBlog, on_delete=models.CASCADE, db_column='categoria_blog_id',verbose_name='Categoria')
    url_img_cta = models.ImageField(upload_to='blogs/cita/', null=True, blank=True,verbose_name='Imagen cita')
    
    def save(self, *args, **kwargs):
        if not self.slug or self.slug.startswith("slice") or self.slug == 'default-slug':  
            self.slug = slugify(self.nombre_blog) 
            base_slug = self.slug
            counter = 1
            while Blog.objects.filter(slug=self.slug).exists():
                self.slug = f"{base_slug}-{counter}"
                counter += 1
        super().save(*args, **kwargs)

    def __str__(self):
        return str(self.id) +" - "+ self.nombre_blog

    class Meta:
        managed = False
        db_table = 'blogs'

class Original(models.Model):
    name = models.CharField(max_length=255,verbose_name='Nombre')
    slug = models.CharField(max_length=150,verbose_name='Slug')
    extr = models.CharField(max_length=250,verbose_name='Descripción')
    image = models.ImageField(upload_to='originals/autores/banner/', null=True, blank=True,verbose_name='Imagen')
    biog = models.TextField(blank=True, null=True,verbose_name='Biografia')
    esta = models.CharField(
        max_length=50,
        choices=[
            ("enabled", "Enabled"),
            ("disabled", "Disabled")
        ],
        verbose_name='Estado'
    )

    def __str__(self):
        return self.name
    
    class Meta:
        managed = False
        db_table = 'Original'


class OriginalCertification(models.Model):
    original = models.ForeignKey('Original', on_delete=models.CASCADE, related_name='certifications')
    certification = models.ForeignKey('Certificaciones', on_delete=models.CASCADE, verbose_name='Certificación')
    title = models.CharField(max_length=255,verbose_name='Titulo')
    posicion = models.PositiveIntegerField(verbose_name='Posición')
    hist = models.TextField(verbose_name='Historia')
    fondo = models.ImageField(upload_to='originals/autores/history/', null=True, blank=True,verbose_name='Fondo')
    
    class Meta:
        unique_together = ('original', 'certification')
        db_table = 'Original_certification'
    def __str__(self):
        return f"{self.original.name} - {self.certification.nombre}"

class Ranking(models.Model):
    nombre = models.CharField(max_length=255)
    descripcion = models.TextField(blank=True, null=True)
    image = models.ImageField(upload_to='rankings/images/', null=True, blank=True,verbose_name='Imagen')
    fecha = models.DateField(auto_now_add=True)
    tipo = models.CharField(
        max_length=50,
        choices=[
            ("universidad", "Universidad"),
            ("empresa", "Empresa")
        ]
    )
    estado = models.CharField(
        max_length=50,
        choices=[
            ("enabled", "Enabled"),
            ("disabled", "Disabled")
        ]
    )

    class Meta:
        db_table = 'Ranking'

    def __str__(self):
        return self.nombre
    
class RankingEntry(models.Model):
    ranking = models.ForeignKey(Ranking, on_delete=models.CASCADE, related_name="entradas")
    universidad = models.ForeignKey(Universidades, on_delete=models.CASCADE, null=True, blank=True)
    empresa = models.ForeignKey(Empresas, on_delete=models.CASCADE, null=True, blank=True)
    posicion = models.PositiveIntegerField()

    class Meta:
        unique_together = ('ranking', 'posicion')  # Una posición única por ranking
        ordering = ['posicion']
        db_table = 'Ranking_entry'

    def clean(self):
        from django.core.exceptions import ValidationError

        if not self.universidad and not self.empresa:
            raise ValidationError("Debe asignar una universidad o una empresa.")
        if self.universidad and self.empresa:
            raise ValidationError("Solo puede asignar una universidad o una empresa, no ambas.")

        # Validar que el tipo del ranking coincida con el tipo de entidad asociada
        if self.ranking.tipo == "universidad" and not self.universidad:
            raise ValidationError("Este ranking es de universidades. Debe asignar una universidad.")
        if self.ranking.tipo == "empresa" and not self.empresa:
            raise ValidationError("Este ranking es de empresas. Debe asignar una empresa.")

    def __str__(self):
        entidad = self.universidad if self.universidad else self.empresa
        return f"{self.ranking.nombre} - {entidad} (Posición {self.posicion})"


class Marca(models.Model):
    ESTADO_CHOICES = (
        ('activo', 'Activo'),
        ('inactivo', 'Inactivo'),
    )

    nombre = models.CharField(max_length=150)
    slug = models.SlugField(max_length=150, unique=True)
    descripcion = models.TextField(blank=True, null=True)
    logo = models.ImageField(upload_to='brand/logos/', null=True, blank=True,verbose_name='Logo')
    color_principal = models.CharField(max_length=7, default='#0F090B')
    color_secundario = models.CharField(max_length=7, default='#F6F4EF')
    phrase = models.CharField(max_length=255)
    about_us = models.TextField(blank=True, null=True)
    banner = models.ImageField(upload_to='brand/banners/', null=True, blank=True,verbose_name='Banner')
    estado = models.CharField(max_length=10, choices=ESTADO_CHOICES, default='activo')
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'marca'
        managed = False
        verbose_name = 'Marca blanca'
        verbose_name_plural = 'Marcas blancas'

    def __str__(self):
        return self.nombre


class MarcaPermisos(models.Model):
    marca = models.ForeignKey(
        Marca,
        on_delete=models.DO_NOTHING,
        db_column='marca_id',
        related_name='permisos',
    )
    nombre_permiso = models.CharField(max_length=100)
    visible = models.BooleanField(default=True)
    orden = models.PositiveIntegerField(default=0)

    class Meta:
        db_table = 'marca_permisos'
        managed = False
        verbose_name = 'Permiso de marca'
        verbose_name_plural = 'Permisos de marca'
        ordering = ['orden']

    def __str__(self):
        return f"{self.marca.nombre} · {self.nombre_permiso}"


class UserBillingProfile(models.Model):
    user = models.OneToOneField(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="billing")
    stripe_customer_id = models.CharField(max_length=255, blank=True, null=True, db_index=True)

    # opcional: datos de facturación
    country = models.CharField(max_length=2, blank=True, null=True)
    phone = models.CharField(max_length=50, blank=True, null=True)

    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"BillingProfile({self.user_id})"


class StripeSubscription(models.Model):
    STATUS_CHOICES = (
        ("incomplete", "incomplete"),
        ("incomplete_expired", "incomplete_expired"),
        ("trialing", "trialing"),
        ("active", "active"),
        ("past_due", "past_due"),
        ("canceled", "canceled"),
        ("unpaid", "unpaid"),
        ("paused", "paused"),
    )

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="stripe_subscriptions",
    )

    stripe_subscription_id = models.CharField(
        max_length=255,
        unique=True,
        db_index=True,
    )

    status = models.CharField(
        max_length=50,
        choices=STATUS_CHOICES,
        default="incomplete",
    )

    price_id = models.CharField(
        max_length=255,
        blank=True,
        null=True,
    )

    interval = models.CharField(
        max_length=20,
        blank=True,
        null=True,
    )

    current_period_end = models.DateTimeField(
        blank=True,
        null=True,
    )

    cancel_at_period_end = models.BooleanField(default=False)

    package_code = models.CharField(
        max_length=60,
        null=True,
        blank=True,
        db_index=True,
    )

    tier = models.CharField(
        max_length=20,
        null=True,
        blank=True,
    )

    billing_period = models.CharField(
        max_length=20,
        null=True,
        blank=True,
    )

    access_status = models.CharField(
        max_length=30,
        default="PENDING",
    )

    lifecycle_status = models.CharField(
        max_length=30,
        default="ACTIVE",
    )

    pending_action = models.CharField(
        max_length=40,
        default="NONE",
    )

    trial_start = models.DateTimeField(
        null=True,
        blank=True,
    )

    trial_end = models.DateTimeField(
        null=True,
        blank=True,
    )

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        indexes = [
            models.Index(
                fields=["user", "status"],
                name="idx_stripe_sub_user_status",
            ),
            models.Index(
                fields=["package_code", "status"],
                name="idx_stripe_sub_package",
            ),
        ]

    def __str__(self):
        return (
            f"{self.user_id} - "
            f"{self.stripe_subscription_id} - "
            f"{self.status}"
        )

class StripePurchase(models.Model):
    """Historial de compras / cobros (invoices / payment_intents / checkout)"""
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="stripe_purchases")

    stripe_checkout_session_id = models.CharField(max_length=255, blank=True, null=True, db_index=True)
    stripe_payment_intent_id = models.CharField(max_length=255, blank=True, null=True, db_index=True)
    stripe_invoice_id = models.CharField(max_length=255, blank=True, null=True, db_index=True)

    amount_total = models.IntegerField(default=0)     # centavos
    currency = models.CharField(max_length=10, default="usd")
    status = models.CharField(max_length=50, default="unknown")  # paid/open/void/etc

    description = models.CharField(max_length=500, blank=True, null=True)
    hosted_invoice_url = models.URLField(blank=True, null=True)
    invoice_pdf = models.URLField(blank=True, null=True)

    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]


class StripePaymentMethod(models.Model):
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="payment_methods"
    )

    stripe_customer_id = models.CharField(max_length=255)
    stripe_payment_method_id = models.CharField(
        max_length=255,
        unique=True
    )

    brand = models.CharField(max_length=50, null=True, blank=True)
    last4 = models.CharField(max_length=10, null=True, blank=True)

    exp_month = models.IntegerField(null=True, blank=True)
    exp_year = models.IntegerField(null=True, blank=True)

    is_default = models.BooleanField(default=False)

    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "StripePaymentMethod"

    def __str__(self):
        return f"{self.user.email} - {self.brand} ****{self.last4}"

class MxWebhookDeliveryLog(models.Model):
    event_id = models.CharField(max_length=255, unique=True)
    event_type = models.CharField(max_length=100)
    stripe_event_id = models.CharField(max_length=255, null=True, blank=True)
    stripe_object_id = models.CharField(max_length=255, null=True, blank=True)

    status = models.CharField(max_length=50, default="pending")
    http_status = models.IntegerField(null=True, blank=True)
    mx_status = models.CharField(max_length=50, null=True, blank=True)

    request_payload = models.JSONField(null=True, blank=True)
    response_body = models.JSONField(null=True, blank=True)
    error_message = models.TextField(null=True, blank=True)

    attempts = models.IntegerField(default=0)
    last_attempt_at = models.DateTimeField(null=True, blank=True)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "MxWebhookDeliveryLog"

    def __str__(self):
        return f"{self.event_id} - {self.status}"

class ExternalSyncState(models.Model):
    key = models.CharField(max_length=100, unique=True)
    cursor_value = models.CharField(max_length=200, blank=True, default="1")
    updated_at = models.DateTimeField(auto_now=True)

    # ✅ lock para cron
    running = models.BooleanField(default=False)
    locked_at = models.DateTimeField(null=True, blank=True)

    # ✅ tracking útil
    last_ok_at = models.DateTimeField(null=True, blank=True)
    last_error_at = models.DateTimeField(null=True, blank=True)
    last_error = models.TextField(blank=True, default="")

    def __str__(self):
        return f"{self.key} -> {self.cursor_value}"

# models.py
class ExternalSyncLog(models.Model):
    key = models.CharField(max_length=100, db_index=True)  # "courses_sync"
    run_id = models.CharField(max_length=64, db_index=True)

    page = models.IntegerField(default=1)
    page_size = models.IntegerField(default=50)

    ok = models.BooleanField(default=False)
    received = models.IntegerField(default=0)
    items_len = models.IntegerField(default=0)

    took_ms = models.IntegerField(default=0)

    error = models.CharField(max_length=200, blank=True, default="")
    detail = models.TextField(blank=True, default="")
    trace = models.TextField(blank=True, default="")

    created_at = models.DateTimeField(default=timezone.now)

    def __str__(self):
        return f"[{self.key}] page={self.page} ok={self.ok} at={self.created_at}"

class LearningRouteLead(models.Model):
    PACKAGE_CHOICES = [
        ("TOP_EDUCATION_FREE", "Top Education Free"),
        ("TOP_EDUCATION_BASIC_MONTHLY", "Top Education Basic mensual"),
        ("TOP_EDUCATION_BASIC_ANNUAL", "Top Education Basic anual"),
        ("TOP_EDUCATION_X_MONTHLY", "Top Education X mensual"),
        ("TOP_EDUCATION_X_ANNUAL", "Top Education X anual"),
        ("TOP_EDUCATION_PLUS_MONTHLY", "Top Education Plus mensual"),
        ("TOP_EDUCATION_PLUS_ANNUAL", "Top Education Plus anual"),
    ]

    TIER_CHOICES = [
        ("FREE", "Free"),
        ("BASIC", "Basic"),
        ("X", "X"),
        ("PLUS", "Plus"),
    ]

    BILLING_PERIOD_CHOICES = [
        ("MONTHLY", "Mensual"),
        ("ANNUAL", "Anual"),
    ]

    ACCESS_STATUS_CHOICES = [
        ("ALLOWED", "Permitido"),
        ("PENDING", "Pendiente"),
        ("BLOCKED", "Bloqueado"),
    ]

    LIFECYCLE_STATUS_CHOICES = [
        ("FREE", "Free"),
        ("TRIALING", "Trial"),
        ("ACTIVE", "Activo"),
        ("PAST_DUE", "Pago vencido"),
        ("CANCELED", "Cancelado"),
        ("EXPIRED", "Expirado"),
        ("REVOKED", "Revocado"),
    ]

    PENDING_ACTION_CHOICES = [
        ("NONE", "Ninguna"),
        ("CANCEL_AT_PERIOD_END", "Cancelar al final del periodo"),
        ("UPGRADE_PENDING", "Upgrade pendiente"),
        ("DOWNGRADE_PENDING", "Downgrade pendiente"),
        ("PAYMENT_RETRY", "Reintento de pago"),
    ]

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="learning_routes",
    )

    email = models.EmailField(db_index=True)
    first_name = models.CharField(max_length=120)
    last_name = models.CharField(max_length=120, blank=True, null=True)

    phone_country_code = models.CharField(
        max_length=10,
        blank=True,
        null=True,
    )
    phone_number = models.CharField(
        max_length=30,
        blank=True,
        null=True,
    )
    phone_e164 = models.CharField(
        max_length=40,
        blank=True,
        null=True,
    )

    topics = models.JSONField(default=list)
    goal = models.CharField(max_length=150)
    age = models.IntegerField(null=True, blank=True)
    gender = models.CharField(max_length=50, blank=True, default="")
    country = models.CharField(max_length=120, blank=True, default="")

    # =========================================================
    # Compatibilidad con el flujo anterior
    # =========================================================

    PLAN_CHOICES = [
        ("free", "Free"),
        ("basic", "Basic"),
        ("x", "X"),
        ("plus", "Plus"),
    ]

    PAID_PLAN_CHOICES = [
        ("monthly_basic", "Basic mensual"),
        ("yearly_basic", "Basic anual"),
        ("monthly_x", "X mensual"),
        ("yearly_x", "X anual"),
        ("monthly_plus", "Plus mensual"),
        ("yearly_plus", "Plus anual"),
    ]

    selected_plan = models.CharField(
        max_length=20,
        choices=PLAN_CHOICES,
        default="free",
        db_index=True,
    )

    selected_paid_plan = models.CharField(
        max_length=30,
        choices=PAID_PLAN_CHOICES,
        null=True,
        blank=True,
    )

    status = models.CharField(
        max_length=40,
        default="route_created",
        choices=[
            ("route_created", "Ruta creada"),
            ("free_pending_password", "Gratis pendiente contraseña"),
            ("free_active", "Gratis activo"),
            ("pro_checkout_started", "Checkout iniciado"),
            ("pro_trialing", "Trial activo"),
            ("pro_active", "Plan activo"),
            ("pro_payment_failed", "Pago fallido"),
            ("subscription_cancel_pending", "Cancelación pendiente"),
            ("subscription_expired", "Suscripción expirada"),
            ("access_revoked", "Acceso revocado"),
        ],
    )

    recommended_certifications = models.JSONField(
        default=list,
        blank=True,
    )

    # =========================================================
    # Estado canónico B2C 1.1
    # =========================================================

    package_code = models.CharField(
        max_length=60,
        choices=PACKAGE_CHOICES,
        default="TOP_EDUCATION_FREE",
        db_index=True,
    )

    tier = models.CharField(
        max_length=20,
        choices=TIER_CHOICES,
        default="FREE",
        db_index=True,
    )

    billing_period = models.CharField(
        max_length=20,
        choices=BILLING_PERIOD_CHOICES,
        null=True,
        blank=True,
    )

    access_status = models.CharField(
        max_length=30,
        choices=ACCESS_STATUS_CHOICES,
        default="ALLOWED",
        db_index=True,
    )

    lifecycle_status = models.CharField(
        max_length=30,
        choices=LIFECYCLE_STATUS_CHOICES,
        default="FREE",
        db_index=True,
    )

    pending_action = models.CharField(
        max_length=40,
        choices=PENDING_ACTION_CHOICES,
        default="NONE",
    )

    route_version = models.PositiveIntegerField(default=1)

    # =========================================================
    # México
    # =========================================================

    mx_user_id = models.CharField(
        max_length=255,
        null=True,
        blank=True,
    )

    mx_status = models.CharField(
        max_length=50,
        default="pending",
    )

    mx_response = models.JSONField(
        null=True,
        blank=True,
    )

    mx_magic_link = models.TextField(
        null=True,
        blank=True,
    )

    mx_event_id = models.CharField(
        max_length=255,
        null=True,
        blank=True,
        db_index=True,
    )

    mx_route_version = models.PositiveIntegerField(
        null=True,
        blank=True,
    )

    mx_entitlement_status = models.CharField(
        max_length=50,
        null=True,
        blank=True,
        db_index=True,
    )

    mx_last_sync_at = models.DateTimeField(
        null=True,
        blank=True,
    )

    # =========================================================
    # Stripe
    # =========================================================

    stripe_customer_id = models.CharField(
        max_length=255,
        blank=True,
        null=True,
    )

    stripe_subscription_id = models.CharField(
        max_length=255,
        blank=True,
        null=True,
    )

    trial_start = models.DateTimeField(
        blank=True,
        null=True,
    )

    trial_end = models.DateTimeField(
        blank=True,
        null=True,
    )

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "LearningRouteLead"
        indexes = [
            models.Index(
                fields=["email", "created_at"],
                name="idx_route_lead_email_created",
            ),
            models.Index(
                fields=["package_code", "lifecycle_status"],
                name="idx_route_lead_package_status",
            ),
        ]

    def __str__(self):
        return (
            f"{self.id} - {self.email} - "
            f"{self.package_code} - ruta v{self.route_version}"
        )

class LearningRouteSnapshot(models.Model):
    MODE_CHOICES = [
        ("SNAPSHOT", "Snapshot"),
    ]

    lead = models.ForeignKey(
        LearningRouteLead,
        on_delete=models.CASCADE,
        related_name="route_snapshots",
    )

    version = models.PositiveIntegerField()
    mode = models.CharField(
        max_length=20,
        choices=MODE_CHOICES,
        default="SNAPSHOT",
    )

    is_current = models.BooleanField(
        default=True,
        db_index=True,
    )

    source = models.CharField(
        max_length=50,
        default="COLOMBIA",
    )

    change_reason = models.CharField(
        max_length=150,
        blank=True,
        default="",
    )

    created_by_event_id = models.CharField(
        max_length=255,
        null=True,
        blank=True,
        db_index=True,
    )

    metadata = models.JSONField(
        default=dict,
        blank=True,
    )

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "learning_route_snapshot"
        ordering = ["-version"]
        constraints = [
            models.UniqueConstraint(
                fields=["lead", "version"],
                name="uq_learning_route_lead_version",
            ),
        ]
        indexes = [
            models.Index(
                fields=["lead", "is_current"],
                name="idx_route_snapshot_current",
            ),
        ]

    def __str__(self):
        return (
            f"Ruta {self.lead_id} "
            f"v{self.version} - {self.mode}"
        )

class LearningRouteItem(models.Model):
    route = models.ForeignKey(
        LearningRouteSnapshot,
        on_delete=models.CASCADE,
        related_name="courses",
    )

    certification = models.ForeignKey(
        Certificaciones,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="learning_route_items",
    )

    id_interno = models.CharField(
        max_length=255,
    )

    title = models.CharField(
        max_length=500,
        blank=True,
        default="",
    )

    provider = models.CharField(
        max_length=50,
        blank=True,
        default="",
        db_index=True,
    )

    language = models.CharField(
        max_length=50,
        blank=True,
        default="",
    )

    order = models.PositiveIntegerField(default=1)
    route_level = models.PositiveIntegerField(default=1)

    preview_type = models.CharField(
        max_length=50,
        null=True,
        blank=True,
    )

    preview_url = models.TextField(
        null=True,
        blank=True,
    )

    preview_validated_at = models.DateTimeField(
        null=True,
        blank=True,
    )

    preview_country_code = models.CharField(
        max_length=2,
        null=True,
        blank=True,
    )

    is_available = models.BooleanField(
        default=True,
        db_index=True,
    )

    raw_payload = models.JSONField(
        default=dict,
        blank=True,
    )

    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "learning_route_item"
        ordering = ["route_level", "order", "id"]
        constraints = [
            models.UniqueConstraint(
                fields=["route", "id_interno"],
                name="uq_route_item_id_interno",
            ),
            models.UniqueConstraint(
                fields=["route", "route_level", "order"],
                name="uq_route_level_order",
            ),
        ]
        indexes = [
            models.Index(
                fields=["route", "route_level", "order"],
                name="idx_route_item_order",
            ),
            models.Index(
                fields=["id_interno"],
                name="idx_route_item_internal_id",
            ),
        ]

    def __str__(self):
        return (
            f"{self.route_id} - "
            f"{self.route_level}.{self.order} - "
            f"{self.id_interno}"
        )

class FreePreviewCourse(models.Model):
    source_id = models.CharField(
        max_length=255,
        null=True,
        blank=True,
        db_index=True,
    )

    id_interno = models.CharField(
        max_length=255,
        unique=True,
    )

    title = models.CharField(max_length=500)

    provider = models.CharField(
        max_length=50,
        db_index=True,
    )

    language = models.CharField(
        max_length=50,
        blank=True,
        default="",
        db_index=True,
    )

    country_code = models.CharField(
        max_length=2,
        default="CO",
        db_index=True,
    )

    preview_type = models.CharField(
        max_length=50,
        default="AUDIT",
    )

    preview_url = models.TextField()

    preview_validated_at = models.DateTimeField(
        null=True,
        blank=True,
    )

    is_active = models.BooleanField(
        default=True,
        db_index=True,
    )

    first_seen_at = models.DateTimeField(auto_now_add=True)

    last_seen_at = models.DateTimeField(
        default=timezone.now,
    )

    last_sync_at = models.DateTimeField(
        default=timezone.now,
        db_index=True,
    )

    raw_payload = models.JSONField(
        default=dict,
        blank=True,
    )

    class Meta:
        db_table = "free_preview_course"
        ordering = ["provider", "title"]
        indexes = [
            models.Index(
                fields=[
                    "is_active",
                    "provider",
                    "country_code",
                ],
                name="idx_free_course_selection",
            ),
            models.Index(
                fields=["language", "is_active"],
                name="idx_free_course_language",
            ),
        ]

    def __str__(self):
        return f"{self.provider} - {self.title}"

class B2CTrialHistory(models.Model):
    STATUS_CHOICES = [
        ("STARTED", "Iniciado"),
        ("COMPLETED", "Completado"),
        ("CANCELED", "Cancelado"),
        ("REVOKED", "Revocado"),
    ]

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="b2c_trial_history",
    )

    email_normalized = models.EmailField(
        unique=True,
    )

    package_code = models.CharField(
        max_length=60,
    )

    tier = models.CharField(
        max_length=20,
    )

    stripe_customer_id = models.CharField(
        max_length=255,
        null=True,
        blank=True,
    )

    stripe_subscription_id = models.CharField(
        max_length=255,
        null=True,
        blank=True,
    )

    status = models.CharField(
        max_length=30,
        choices=STATUS_CHOICES,
        default="STARTED",
    )

    trial_days = models.PositiveSmallIntegerField(default=7)

    trial_start = models.DateTimeField()
    trial_end = models.DateTimeField()

    consumed_at = models.DateTimeField(
        default=timezone.now,
    )

    metadata = models.JSONField(
        default=dict,
        blank=True,
    )

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "b2c_trial_history"
        indexes = [
            models.Index(
                fields=["tier", "status"],
                name="idx_b2c_trial_tier_status",
            ),
        ]

    def save(self, *args, **kwargs):
        self.email_normalized = (
            str(self.email_normalized)
            .strip()
            .lower()
        )
        super().save(*args, **kwargs)

    def __str__(self):
        return (
            f"{self.email_normalized} - "
            f"{self.package_code}"
        )

class CVAnalysis(models.Model):
    user_email = models.EmailField(db_index=True)
    route_id = models.IntegerField(null=True, blank=True)

    filename = models.CharField(max_length=255, blank=True, default="")
    mime_type = models.CharField(max_length=120, blank=True, default="")
    language = models.CharField(max_length=50, default="es-CO")

    status = models.CharField(max_length=50, default="completed")
    score_value = models.DecimalField(max_digits=4, decimal_places=1, null=True, blank=True)
    score_percentage = models.IntegerField(null=True, blank=True)
    score_label = models.CharField(max_length=80, blank=True, default="")

    summary = models.TextField(blank=True, default="")
    recommendations = models.JSONField(default=list, blank=True)
    report = models.JSONField(default=dict, blank=True)
    raw_response = models.JSONField(default=dict, blank=True)

    analyzed_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "CVAnalysis"
        ordering = ["-created_at"]


class MxAccessEventLog(models.Model):
    class SendStatus(models.TextChoices):
        PENDING = "pending", "Pending"
        PROCESSING = "processing", "Processing"
        SENT = "sent", "Sent"
        FAILED = "failed", "Failed"

    event_uuid = models.UUIDField(
        default=uuid.uuid4,
        unique=True,
        editable=False,
    )

    event_id = models.CharField(
        max_length=255,
        unique=True,
        null=True,
        blank=True,
    )

    schema_version = models.CharField(
        max_length=20,
        default="1.1",
    )

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
    )

    learning_route = models.ForeignKey(
        LearningRouteLead,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
    )

    route_snapshot = models.ForeignKey(
        LearningRouteSnapshot,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="mx_events",
    )

    route_version = models.PositiveIntegerField(
        null=True,
        blank=True,
    )

    stripe_customer_id = models.CharField(
        max_length=255,
        blank=True,
        null=True,
    )

    stripe_subscription_id = models.CharField(
        max_length=255,
        blank=True,
        null=True,
    )

    stripe_invoice_id = models.CharField(
        max_length=255,
        blank=True,
        null=True,
    )

    stripe_event_id = models.CharField(
        max_length=255,
        unique=True,
        blank=True,
        null=True,
    )

    event_type = models.CharField(max_length=100)

    event_source = models.CharField(
        max_length=50,
        default="colombia_b2c",
    )

    payload_json = models.JSONField()
    raw_body = models.TextField(null=True, blank=True)

    payload_hash = models.CharField(
        max_length=64,
        null=True,
        blank=True,
        db_index=True,
    )

    response_json = models.JSONField(
        null=True,
        blank=True,
    )

    http_status = models.PositiveIntegerField(
        null=True,
        blank=True,
    )

    mx_user_id = models.CharField(
        max_length=255,
        null=True,
        blank=True,
    )

    magic_link = models.TextField(
        null=True,
        blank=True,
    )

    mx_status = models.CharField(
        max_length=50,
        null=True,
        blank=True,
    )

    entitlement_status = models.CharField(
        max_length=50,
        null=True,
        blank=True,
    )

    send_status = models.CharField(
        max_length=30,
        choices=SendStatus.choices,
        default=SendStatus.PENDING,
        db_index=True,
    )

    is_retryable = models.BooleanField(default=False)
    attempts = models.PositiveIntegerField(default=0)

    last_error = models.TextField(
        blank=True,
        null=True,
    )

    next_retry_at = models.DateTimeField(
        blank=True,
        null=True,
        db_index=True,
    )

    sent_at = models.DateTimeField(
        blank=True,
        null=True,
    )

    processed_at = models.DateTimeField(
        blank=True,
        null=True,
    )

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "mx_access_event_log"
        indexes = [
            models.Index(
                fields=["send_status", "next_retry_at"],
                name="idx_mx_event_retry",
            ),
            models.Index(
                fields=["learning_route", "route_version"],
                name="idx_mx_event_route_version",
            ),
            models.Index(
                fields=["event_type", "created_at"],
                name="idx_mx_event_type_created",
            ),
        ]

    def __str__(self):
        return (
            f"{self.event_id or self.stripe_event_id} - "
            f"{self.event_type} - {self.send_status}"
        )