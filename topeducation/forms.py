from django import forms
from django.forms import inlineformset_factory
from django.forms.models import BaseInlineFormSet
from django.core.exceptions import ValidationError
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

class RankingEntryForm(forms.ModelForm):
    class Meta:
        model = RankingEntry
        fields = '__all__'

class BaseRankingEntryFormSet(BaseInlineFormSet):
    def clean(self):
        super().clean()
        posiciones = []
        for form in self.forms:
            if form.cleaned_data and not form.cleaned_data.get('DELETE', False):
                pos = form.cleaned_data.get('posicion')
                if pos in posiciones:
                    raise ValidationError('No puede haber posiciones repetidas en un mismo ranking.')
                posiciones.append(pos)

RankingEntryFormSet = inlineformset_factory(
    Ranking,
    RankingEntry,
    form=RankingEntryForm,
    formset=BaseRankingEntryFormSet,  # usa tu formset personalizado
    extra=1,
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