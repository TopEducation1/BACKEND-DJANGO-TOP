from django.db import models





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
    fecha_creado = models.DateField(auto_now_add=True, null=False)
    
    def __str__(self):
        
        return self.nombre
    
    class Meta:
        db_table = 'Certificaciones'
        

class Autor(models.Model):
    nombre_autor = models.CharField(max_length=250, null=False, blank=False)
    
    class Meta:
        db_table = "autor"
    
    def __str__(self):
        return self.nombre_autor
    
        
class Blog(models.Model):
    titulo_blog = models.CharField(max_length=300, default='titulo', blank=False, null=False)
    contenido_blog = models.TextField(blank=True, null=True)
    autor_blog = models.ForeignKey(Autor, on_delete=models.SET_NULL, null=True, blank=True)
    url_imagen_blog = models.TextField(blank=True, null=True)
    fecha_blog_redacccion = models.DateField(auto_now_add=True, null=False, blank=False)
    
    class Meta:
        db_table = "blog"
        ordering = ['-fecha_blog_redacccion'] # Ordenar por fecha de redaccion descendente
        verbose_name = "Blog"
        verbose_name_plural = "Blogs"
        
    def __str__(self):
        return self.titulo_blog