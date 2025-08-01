from django.db import models
from django.utils.text import slugify
from django.utils import timezone
from ckeditor_uploader.fields import RichTextUploadingField


class Habilidades (models.Model):
    nombre = models.CharField(max_length=250)
    def __str__(self):
        return self.nombre
    
    class Meta:
        db_table = 'Habilidades'
        

class Temas (models.Model):
    nombre = models.CharField(max_length=250,null=True)
    tem_type = models.CharField(max_length=50,null=True)
    tem_col = models.CharField(max_length=10,null=True)
    tem_img = models.CharField(max_length=200,null=True)
    
    def __str__(self):
        return self.nombre
    
    
    class Meta:
        db_table = 'Temas'
        

class Regiones (models.Model):
    nombre = models.CharField(max_length=100,null=True)
    
    def __str__(self):
        return str(self.id) +" - "+ self.nombre
    
    class Meta:
        db_table = 'Regiones'
        
        
class Universidades (models.Model):
    nombre = models.CharField(max_length=500,null=False)
    region_universidad = models.ForeignKey(Regiones, on_delete=models.SET_NULL, null=True, related_name='universidades')
    univ_img = models.CharField(max_length=200,null=True)
    univ_fla = models.CharField(max_length=200,null=True)
    univ_ico = models.CharField(max_length=100,null=True)
    univ_est = models.CharField(max_length=50,null=True)
    univ_top = models.CharField(max_length=5,null=True)
    
    def __str__(self):
        return str(self.id) +" - "+ self.nombre
    
    class Meta:
        db_table = 'Universidades'
        

class Empresas (models.Model):
    nombre = models.CharField(max_length=500,null=False)
    empr_img = models.CharField(max_length=200,null=True)
    empr_ico = models.CharField(max_length=100,null=True)
    empr_est = models.CharField(max_length=50,null=True)
    empr_top = models.CharField(max_length=5,null=True)

    def __str__(self):
        return str(self.id) +" - "+ self.nombre
    
    class Meta:
        db_table = 'Empresas'
        
        
class Plataformas (models.Model):
    nombre = models.CharField(max_length=500,null=False)
    plat_img = models.CharField(max_length=200,null=True)
    plat_ico = models.CharField(max_length=100,null=True)
    
    def __str__(self):
        return self.nombre
    
    class Meta:
        db_table = 'Plataformas'
        
class Certificaciones(models.Model):
    nombre = models.CharField(max_length=500)
    slug = models.SlugField(max_length=500, default="default-slug")
    tema_certificacion = models.ForeignKey(Temas, on_delete=models.SET_NULL, null=True)
    
    palabra_clave_certificacion = models.TextField()    
    metadescripcion_certificacion = models.TextField(default="NONE")
    instructores_certificacion = models.TextField(default="NONE")
    nivel_certificacion = models.CharField(max_length=255,default="NONE")
    tiempo_certificacion = models.CharField(max_length=255,default="NONE")
    lenguaje_certificacion = models.CharField(max_length=255,default="NONE")
    aprendizaje_certificacion = models.TextField(default="NONE")
    habilidades_certificacion = models.TextField(default="NONE")
    experiencia_certificacion = models.TextField(default="NONE")
    testimonios_certificacion = models.TextField(default="NONE")
    contenido_certificacion = models.TextField(blank=True,verbose_name='Contenido',default="NONE")
    modulos_certificacion = models.TextField(default="NONE")
    
    universidad_certificacion = models.ForeignKey(Universidades, on_delete=models.SET_NULL, null=True, blank=True)
    empresa_certificacion = models.ForeignKey(Empresas, on_delete=models.SET_NULL, null=True, blank=True)
    plataforma_certificacion = models.ForeignKey(Plataformas, on_delete=models.CASCADE, null=True, blank=True)
    fecha_creado_cert = models.DateField(auto_now_add=True, null=False)
    url_certificacion_original = models.CharField(max_length=300, default="Null")
    video_certificacion = models.CharField(default='Null', null = True, max_length=1000)
    imagen_final = models.CharField(default='Null', null = True, max_length=255)
    cert_top = models.CharField(max_length=5,null=True)

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
        return str(self.id) +" - "+ self.nombre
    
    class Meta:
        db_table = 'Certificaciones'
        

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
    name = models.CharField(max_length=255)
    slug = models.CharField(max_length=150)
    image = models.ImageField(upload_to='authors/', null=True, blank=True)
    biog = models.TextField(blank=True, null=True)

    def __str__(self):
        return self.name
    
    class Meta:
        managed = False
        db_table = 'Original'


class OriginalCertification(models.Model):
    original = models.ForeignKey('Original', on_delete=models.CASCADE, related_name='certifications')
    certification = models.ForeignKey('Certificaciones', on_delete=models.CASCADE)
    title = models.CharField(max_length=255)
    hist = models.TextField()
    image = models.ImageField(upload_to='originals/autores/history/', null=True, blank=True)

    class Meta:
        unique_together = ('original', 'certification')
        db_table = 'Original_certification'
    def __str__(self):
        return f"{self.original.name} - {self.certification.nombre}"