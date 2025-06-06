from django import forms
from .models import Certificaciones
from .models import Blog

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
