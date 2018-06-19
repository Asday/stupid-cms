from django import forms
from django.core.exceptions import ValidationError

from .models import Block, Page, Reference, TextBlock


class PageForm(forms.ModelForm):

    class Meta:
        fields = ('parent', 'title', 'slug')
        model = Page


class MovePageForm(forms.ModelForm):

    class Meta:
        fields = ('parent', )
        model = Page


class BlockChoiceField(forms.ModelChoiceField):

    def label_from_instance(self, obj):
        return f'{obj.parent_page} - {obj}'


class MoveBlockForm(forms.ModelForm):
    after = BlockChoiceField(
        queryset=Block.objects.order_by('parent_page', 'position'),
        required=False,
    )

    class Meta:
        fields = ('parent_page', )
        model = Block

    def clean(self):
        cleaned_data = super().clean()

        after = cleaned_data['after']
        parent_page = cleaned_data['parent_page']
        if after is not None and after.parent_page != parent_page:
            raise ValidationError(
                f'Block {after} is not on the Page {parent_page}',
            )

        return cleaned_data

    def save(self, *args, **kwargs):
        after = self.cleaned_data['after']
        parent_page = self.cleaned_data['parent_page']

        position = parent_page.get_position_after(after)

        self.instance.position = position

        return super().save(*args, **kwargs)


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
