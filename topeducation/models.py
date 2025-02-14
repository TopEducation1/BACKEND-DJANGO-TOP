from django.db import models
from django.utils.text import slugify

class Habilidades (models.Model):
    nombre = models.CharField(max_length=250)
    def __str__(self):
        return self.nombre
    
    class Meta:
        db_table = 'Habilidades'
        

class Temas (models.Model):
    nombre = models.CharField(max_length=250)
    
    def __str__(self):
        return self.nombre
    
    
    class Meta:
        db_table = 'Temas'
        

class Regiones (models.Model):
    nombre = models.CharField(max_length=500)
    
    def __str__(self):
        return self.nombre
    
    class Meta:
        db_table = 'Regiones'
        
        
class Universidades (models.Model):
    nombre = models.CharField(max_length=500)
    region_universidad = models.ForeignKey(
        Regiones, 
        on_delete=models.SET_NULL,
        null = True,
    )
    
    def __str__(self):
        return self.nombre
    
    class Meta:
        db_table = 'Universidades'
        

class Empresas (models.Model):
    nombre = models.CharField(max_length=500)
    
    def __str__(self):
        return self.nombre
    
    class Meta:
        db_table = 'Empresas'
        
        
class Plataformas (models.Model):
    nombre = models.CharField(max_length=500)
    
    def __str__(self):
        return self.nombre
    
    class Meta:
        db_table = 'Plataformas'
        
        


class Certificaciones(models.Model):
    nombre = models.CharField(max_length=500)
    slug = models.SlugField(max_length=500, default="default-slug")
    tema_certificacion = models.ForeignKey(Temas, on_delete=models.SET_NULL, null=True)
    palabra_clave_certificacion = models.TextField()
    plataforma_certificacion = models.ForeignKey(Plataformas, on_delete=models.SET_NULL, null=True)
    url_certificacion_original = models.CharField(max_length=300, default="Null")
    metadescripcion_certificacion = models.TextField(default="NONE")
    instructores_certificacion = models.TextField(default="NONE")
    nivel_certificacion = models.TextField(default="NONE")
    tiempo_certificacion = models.TextField(default="NONE")
    lenguaje_certificacion = models.TextField(default="NONE")
    aprendizaje_certificacion = models.TextField(default="NONE")
    habilidades_certificacion = models.TextField(default="NONE")
    experiencia_certificacion = models.TextField(default="NONE")
    contenido_certificacion = models.TextField(default="NONE")
    modulos_certificacion = models.TextField(default="NONE")
    testimonios_certificacion = models.TextField(default="NONE")
    universidad_certificacion = models.ForeignKey(Universidades, on_delete=models.SET_NULL, null=True, blank=True)
    empresa_certificacion = models.CharField(max_length=300, default='No Aplica', blank=True, null=True)
    region_universidad_certificacion = models.ForeignKey(Regiones, on_delete=models.SET_NULL, null=True, blank=True)
    url_imagen_universidad_certificacion = models.TextField(blank=True, null=True)
    url_imagen_plataforma_certificacion = models.TextField(blank=True, null=True)
    url_imagen_empresa_certificacion = models.TextField(blank=True, null=True)
    imagen_final = models.TextField(blank=True, null=True)
    fecha_creado_cert = models.DateField(auto_now_add=True, null=False)
    video_certificacion = models.CharField(default='None', null = True, max_length=1000)
    
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
        return self.nombre
    
    class Meta:
        db_table = 'Certificaciones'
        

from django.db import models

class Autor(models.Model):
    nombre_autor = models.CharField(max_length=255)

    class Meta:
        managed = False  # Para evitar que Django gestione la tabla
        db_table = 'autores'

class CategoriaBlog(models.Model):
    nombre_categoria_blog = models.CharField(max_length=255)

    class Meta:
        managed = False
        db_table = 'categorias_blog'

class Blog(models.Model):
    nombre_blog = models.CharField(max_length=255)
    metadescripcion_blog = models.TextField()
    miniatura_blog = models.TextField()
    palabra_clave_blog = models.CharField(max_length=255)
    autor_blog = models.ForeignKey(Autor, on_delete=models.CASCADE, db_column='autor_blog_id')
    categoria_blog = models.ForeignKey(CategoriaBlog, on_delete=models.CASCADE, db_column='categoria_blog_id')
    objetivo_blog = models.TextField()
    contenido = models.TextField()
    slug = models.SlugField(max_length=500, default="default-slug")
    fecha_redaccion_blog = models.DateField(default='2025-01-01')
    url_img_autor = models.URLField()
    url_img_cta = models.URLField()
    
    def save(self, *args, **kwargs):
        if not self.slug or self.slug.startswith("slice") or self.slug == 'default-slug':  
            self.slug = slugify(self.nombre_blog) 
            base_slug = self.slug
            counter = 1
            while Blog.objects.filter(slug=self.slug).exists():
                self.slug = f"{base_slug}-{counter}"
                counter += 1
        super().save(*args, **kwargs)

    class Meta:
        managed = False
        db_table = 'blogs'