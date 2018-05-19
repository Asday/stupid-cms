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
            ('TextBlock', 'Text'),
        ),
    )


class GenericBlockForm(forms.ModelForm):

    def __init__(self, *args, parent_page, position, **kwargs):
        self._parent_page = parent_page
        self._position = position

        super().__init__(*args, **kwargs)

    def save(self, commit=True):
        self.instance.parent_page = self._parent_page
        self.instance.position = self._position

        return super().save(commit)


class TextBlockForm(GenericBlockForm):

    class Meta:
        fields = ('content', )
        model = TextBlock


class EditTextBlockForm(forms.ModelForm):

    class Meta:
        fields = ('content', )
        model = TextBlock
