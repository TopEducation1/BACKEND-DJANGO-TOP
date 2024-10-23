from django.db import models

# Model of the certifications

        

class Skills (models.Model):
    hability_name = models.CharField(max_length=250)
    
    
    class Meta:
        db_table = 'Habilidades'
        

class Topics (models.Model):
    topic_name = models.CharField(max_length=250)
    
    
    class Meta:
        db_table = 'Temas'
        

class Regions (models.Model):
    region_name = models.CharField(max_length=500)
    
    class Meta:
        db_table = 'Regiones'
        
        
class Universities (models.Model):
    university_name = models.CharField(max_length=500)
    university_image = models.CharField(max_length=300, null=True, blank=True)
    university_region = models.ForeignKey(
        Regions, 
        on_delete=models.SET_NULL,
        null = True,
        related_name= 'Universidades'
    )
    
    class Meta:
        db_table = 'Universidades'
        

class Companies (models.Model):
    company_name = models.CharField(max_length=500)
    company_img = models.CharField(max_length=300, null=True, blank=True)
    
    class Meta:
        db_table = 'Empresas'
        
        
class Platforms (models.Model):
    platform_name = models.CharField(max_length=500)
    platform_img = models.CharField(max_length=300, null=True, blank=True)
    
    class Meta:
        db_table = 'Plataformas'
        
        
class Certification (models.Model):
    certification_name = models.CharField(max_length=500)
    certification_topic = models.ForeignKey(Topics, on_delete=models.SET_NULL, null=True, related_name='certification_topic')
    certification_keyword = models.TextField()
    certification_platform = models.ForeignKey(Platforms, on_delete=models.SET_NULL, null=True, related_name='certification_platform')
    certification_url_original = models.CharField(max_length=300, default="Null")
    certification_metadescription = models.TextField(default="NONE")
    certification_instructors = models.TextField(default="NONE")
    certification_level = models.TextField(default="NONE")
    certification_time = models.TextField(default="NONE")
    certification_language = models.TextField(default="NONE")
    certification_learnings = models.TextField(default="NONE")
    certification_skills = models.TextField(default="NONE")
    certification_experience = models.TextField(default="NONE")
    certification_content = models.TextField(default="NONE")
    certification_modules = models.TextField(default="NONE")
    certification_testimonials = models.TextField(default="NONE")
    certification_university = models.ForeignKey(Universities, on_delete=models.SET_NULL, null=True, related_name='certification_university', blank=True)
    certification_enterprise = models.CharField(max_length=300, default='No Aplica', blank=True)
    certification_university_region = models.ForeignKey(Regions, on_delete=models.SET_NULL, null=True, related_name='certification_university_region', blank=True)
    certification_university_url_img = models.TextField(null=True, blank=True)
    certification_platform_url_img = models.TextField(null=True, blank=True)
    
    class Meta:
        db_table = 'Certifications'
        
    def __str__(self):
        return self.certification_name