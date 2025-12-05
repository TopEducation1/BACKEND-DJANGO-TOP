from django import forms
from django.forms.models import BaseInlineFormSet, inlineformset_factory
from django_select2.forms import ModelSelect2Widget
from django.core.exceptions import ValidationError
from .models import Marca, MarcaPermisos
from .models import *

class UniSelect2(ModelSelect2Widget):
    model = Universidades
    search_fields = ['nombre__icontains']   # <--- el nombre del campo DEBE existir
    def get_queryset(self):
        # si filtras por estado, que existan registros así:
        return Universidades.objects.filter(univ_est='enabled')

class EmpSelect2(ModelSelect2Widget):
    model = Empresas
    search_fields = ['nombre__icontains']
    def get_queryset(self):
        return Empresas.objects.filter(empr_est='enabled')
    
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
        # Mejor lista explícita. Evitas incluir campos no editables/auto.
        fields = [
            "nombre_blog",
            "metadescripcion_blog",
            "slug",
            "palabra_clave_blog",
            "autor_blog",
            "categoria_blog",
            "objetivo_blog",
            "contenido",
            "miniatura_blog",   # ImageField
            "url_img_cta",      # ImageField/FileField si aplica
            #"fecha_redaccion_blog",
            # agrega los demás campos que SÍ edita el usuario
        ]
        widgets = {
            # Textarea para CKEditor/HTML
            "contenido": forms.Textarea(attrs={
                "id": "id_contenido",  # que coincida con tu ClassicEditor
                "rows": 10,
            }),
            #"fecha_redaccion_blog": forms.DateInput(attrs={"type": "date"}),
            # (Opcional) asegurarte de file input nativo
            # "miniatura_blog": forms.ClearableFileInput(),
            # "url_img_cta": forms.ClearableFileInput(),
        }


class UniversitiesForm(forms.ModelForm):
    class Meta:
        model = Universidades
        fields = '__all__'

class CompaniesForm(forms.ModelForm):
    class Meta:
        model = Empresas
        fields = '__all__'

class TopicsForm(forms.ModelForm):
    class Meta:
        model = Temas
        fields = '__all__'

class TagsForm(forms.ModelForm):
    class Meta:
        model = CategoriaBlog
        fields = '__all__'

class RankingsForm(forms.ModelForm):
    class Meta:
        model = Ranking
        fields = '__all__'
        widgets = {
            'image': forms.ClearableFileInput(attrs={
                'class': 'w-full border border-white bg-white text-neutral-950 rounded-lg px-4 py-1',
                'onchange': 'previewImage(event, this.id)'
            }),
        }    

class RankingEntryForm(forms.ModelForm):
    class Meta:
        model = RankingEntry
        # ¡No incluyas la FK al padre!
        exclude = ('ranking',)
        # Opcional: widgets si necesitas
        widgets = {
            'universidad': UniSelect2,
            'empresa': EmpSelect2,
            'posicion': forms.NumberInput(attrs={'min': 1}),
        }

    def clean(self):
        cleaned = super().clean()
        uni = cleaned.get('universidad')
        emp = cleaned.get('empresa')
        if not uni and not emp:
            raise forms.ValidationError('Debes seleccionar una universidad o una empresa.')
        return cleaned

class BaseRankingEntryFormSet(BaseInlineFormSet):
    def clean(self):
        super().clean()
        seen = set()
        for form in self.forms:
            if form.cleaned_data.get('DELETE') or form.errors or not form.cleaned_data:
                continue
            pos = form.cleaned_data.get('posicion')
            if pos is None:
                continue
            if pos in seen:
                form.add_error('posicion', 'Esta posición ya está usada en este ranking.')
            else:
                seen.add(pos)

RankingEntryFormSet = inlineformset_factory(
    Ranking,
    RankingEntry,
    form=RankingEntryForm,
    formset=BaseRankingEntryFormSet,
    extra=0,
    can_delete=True,
)

class OriginalsForm(forms.ModelForm):
    class Meta:
        model = Original
        fields = '__all__'

class OriginalCertForm(forms.ModelForm):
    class Meta:
        model = OriginalCertification
        fields = ['certification', 'title', 'posicion', 'hist', 'fondo']
        widgets = {
            'fondo': forms.ClearableFileInput(attrs={
                'class': 'w-full border border-white bg-white text-neutral-950 rounded-lg px-4 py-1',
                'onchange': 'previewImage(event, this.id)'
            }),
        }
class BaseOriginalCertFormSet(BaseInlineFormSet):
    def clean(self):
        super().clean()
        posiciones = []
        for form in self.forms:
            if form.cleaned_data and not form.cleaned_data.get('DELETE', False):
                pos = form.cleaned_data.get('posicion')
                if pos in posiciones:
                    raise ValidationError('No puede haber posiciones repetidas en un mismo ranking.')
                posiciones.append(pos)

OriginalCertFormSet = inlineformset_factory(
    Original,
    OriginalCertification,
    form=OriginalCertForm,
    formset=BaseOriginalCertFormSet,  # usa tu formset personalizado
    extra=1,
    can_delete=True,
)



class MarcaForm(forms.ModelForm):
    class Meta:
        model = Marca
        fields = [
            "nombre",
            "slug",
            "descripcion",
            "logo",
            "color_principal",
            "color_secundario",
            "phrase",
            "about_us",
            "banner",
            "estado",
        ]
        widgets = {
            "nombre": forms.TextInput(attrs={
                "class": "mt-1 block w-full rounded-md border border-gray-200 py-1 px-2 text-white shadow-sm text-sm focus:border-gray-200 focus:ring-gray-300"
            }),
            "slug": forms.TextInput(attrs={
                "class": "mt-1 block w-full rounded-md border border-gray-200 py-1 px-2 text-white shadow-sm text-sm focus:border-gray-200 focus:ring-gray-300"
            }),
            "descripcion": forms.Textarea(attrs={
                "rows": 3,
                "class": "mt-1 block w-full rounded-md border border-gray-200 py-1 px-2 text-white shadow-sm text-sm focus:border-gray-200 focus:ring-gray-300"
            }),
            "about_us": forms.Textarea(attrs={
                "rows": 3,
                "class": "mt-1 block w-full rounded-md border border-gray-200 py-1 px-2 text-white shadow-sm text-sm focus:border-gray-200 focus:ring-gray-300"
            }),
            "phrase": forms.TextInput(attrs={
                "class": "mt-1 block w-full rounded-md border border-gray-200 py-1 px-2 text-white shadow-sm text-sm focus:border-gray-200 focus:ring-gray-300"
            }),
            "banner": forms.ClearableFileInput(attrs={
                "class": "block w-full rounded-md border border-gray-200 py-1 px-2 text-sm text-gray-200 bg-white text-gray-950"
            }),
            "logo": forms.ClearableFileInput(attrs={
                "class": "block w-full rounded-md border border-gray-200 py-1 px-2 text-sm text-gray-200 bg-white text-gray-950"
            }),
            "color_principal": forms.TextInput(attrs={
                "class": "mt-1 block w-full rounded-md border border-gray-200 py-1 px-2 text-white shadow-sm text-sm focus:border-gray-200 focus:ring-gray-300"
            }),
            "color_secundario": forms.TextInput(attrs={
                "class": "mt-1 block w-full rounded-md border border-gray-200 py-1 px-2 text-white shadow-sm text-sm focus:border-gray-200 focus:ring-gray-300"
            }),
            "estado": forms.Select(attrs={
                "class": "mt-1 block w-full rounded-md border border-gray-200 py-1 px-2 text-white shadow-sm text-sm focus:border-gray-200 focus:ring-gray-300"
            }),
        }


class MarcaPermisosForm(forms.ModelForm):
    class Meta:
        model = MarcaPermisos
        fields = ["nombre_permiso", "visible", "orden"]
        widgets = {
            "nombre_permiso": forms.TextInput(attrs={
                "class": "block w-full rounded-md border-gray-200 py-1 px-2 text-white shadow-sm text-sm focus:border-gray-200 focus:ring-gray-300"
            }),
            "visible": forms.CheckboxInput(attrs={
                "class": "h-4 w-4 rounded border-gray-200 py-1 px-2 text-white text-indigo-600 focus:ring-gray-300"
            }),
            "orden": forms.NumberInput(attrs={
                "class": "w-20 rounded-md border-gray-200 py-1 px-2 text-white shadow-sm text-sm focus:border-gray-200 focus:ring-gray-300"
            }),
        }


MarcaPermisosFormSet = inlineformset_factory(
    Marca,
    MarcaPermisos,
    form=MarcaPermisosForm,
    extra=0,
    can_delete=True,
)
