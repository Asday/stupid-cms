from django import forms

from .models import Page


class PageForm(forms.ModelForm):

    class Meta:
        fields = ('parent', 'title', 'slug')
        model = Page
