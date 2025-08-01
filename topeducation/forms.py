from django import forms
from .models import *

class UploadFileForm(forms.Form):
    file = forms.FileField()

class CertificationsForm(forms.ModelForm):
    class Meta:
        model = Certificaciones
        fields = '__all__'
        widgets = {
            'contenido_certificacion': forms.TextInput(attrs={'id':'editor'}),
            'modulos_certificacion': forms.TextInput(attrs={'id':'editor_2'})
        }

class BlogsForm(forms.ModelForm):
    class Meta:
        model = Blog
        fields = '__all__'
        widgets = {
            'contenido': forms.TextInput(attrs={'id':'editor'}),
            'fecha_redaccion_blog': forms.DateInput(attrs={'type':'date'})
        }

class UniversitiesForm(forms.ModelForm):
    class Meta:
        model = Universidades
        fields = '__all__'

class CompaniesForm(forms.ModelForm):
    class Meta:
        model = Empresas
        fields = '__all__'