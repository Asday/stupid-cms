from django import forms

from .models import Page


class PageForm(forms.ModelForm):

    class Meta:
        fields = ('parent', 'title', 'slug')
        model = Page


class BlockTypeChoiceForm(forms.Form):
    blocktype = forms.ChoiceField(
        label='Choose the type of content you\'re creating:',
        choices=(
            ('TextBlock', 'Text'),
        ),
    )
