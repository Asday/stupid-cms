from django import forms

from .models import Page, Reference, TextBlock


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


class ReferenceForm(forms.ModelForm):

    class Meta:
        fields = ('referenced_page', 'referenced_block')
        model = Reference

    def __init__(self, containing_block, **kwargs):
        super().__init__(**kwargs)

        self._containing_block = containing_block

    def save(self, *args, **kwargs):
        self.instance.containing_block = self._containing_block

        return super().save(*args, **kwargs)
