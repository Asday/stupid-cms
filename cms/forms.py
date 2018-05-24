from django import forms

from .models import Page, TextBlock


class PageForm(forms.ModelForm):

    class Meta:
        fields = ('parent', 'title', 'slug')
        model = Page


class BlockTypeChoiceForm(forms.Form):
    blocktype = forms.ChoiceField(
        label='Choose the type of content you\'re creating:',
        choices=(
            ('textblock', 'Text'),
        ),
    )


class GenericBlockForm(forms.ModelForm):

    def clean(self):
        self.instance.validate_references(content=self.cleaned_data['content'])

        return super().clean()


class TextBlockForm(GenericBlockForm):

    class Meta:
        fields = ('content', )
        model = TextBlock
