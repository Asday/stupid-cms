from uuid import uuid4

from django.core.exceptions import ValidationError
from django.db import models
from django.utils.text import slugify

from polymorphic.models import PolymorphicModel


"""
Pages are ordered in a hierarchy.  Each Page exists as a child of
 either another Page, or as a top level Page.

Pages contain Blocks, which can be of many types.

Blocks can contain References, which refer to a Page or Block.
"""


class Page(models.Model):
    uuid = models.UUIDField(default=uuid4, editable=False, unique=True)

    parent = models.ForeignKey(
        'self',
        related_name='children',
        on_delete=models.PROTECT,
        null=True,
    )
    denormalised_path = models.TextField(
        help_text=(
            'Ordered slash-separated list of parent `Page`s\' slugs,'
            ' starting from the top level `Page`.  This does not'
            ' include the current `Page`.'
        ),
        editable=False,
    )

    title = models.CharField(max_length=1024)
    slug = models.SlugField()

    class Meta:
        unique_together = ('denormalised_path', 'slug')

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        self._old_slug = self.slug

    def _denormalise_path(self):
        # Update own `denormalised_path`
        if self.parent:
            # Trigger parent's path denormalisation if needed.
            self.parent.save()

            self.denormalised_path = '/'.join([
                self.parent.denormalised_path,
                self.parent.slug,
            ])

        else:
            self.denormalised_path = ''

        self._redenormalise_children_paths()

    def _redenormalise_children_paths(self):
        for child in self.children:
            child.save(redenormalise_path=True)

    def _redenormalise_path_if_needed(self, force=False):
        redenormalise_path = force

        # Do we need to initialise the denormalised path?
        if not self.denormalised_path and self.parent is not None:
            redenormalise_path = True

        # If we've just been moved to the top level, we'll need to
        # blank `denormalised_path` and update our children anyway.
        if self.denormalised_path and self.parent is None:
            redenormalise_path = True

        # If our slug has changed...
        if self._old_slug != self.slug:
            redenormalise_path = True

        if redenormalise_path:
            self._denormalise_path()

    def save(self, *args, redenormalise_path=False, **kwargs):
        if not self.slug:
            self.slug = slugify(self.name, allow_unicode=True)

        self._redenormalise_path_if_needed(force=redenormalise_path)

        return super().save(*args, **kwargs)


class Block(PolymorphicModel):
    parent_page = models.ForeignKey(
        'cms.Page',
        related_name='blocks',
        on_delete=models.CASCADE,
    )


class TextBlock(Block):
    content = models.TextField()


class Reference(models.Model):
    containing_block = models.ForeignKey(
        'cms.Block',
        related_name='references',
        on_delete=models.CASCADE,
    )

    referenced_block = models.ForeignKey(
        'cms.Block',
        related_name='referees',
        on_delete=models.PROTECT,
        null=True,
        blank=True,
    )

    referenced_page = models.ForeignKey(
        'cms.Page',
        related_name='referees',
        on_delete=models.PROTECT,
        null=True,
        blank=True,
    )

    def save(self, *args, **kwargs):
        if self.referenced_block is None and self.referenced_page is None:
            raise ValidationError(
                '`Reference`s must refer to either a `Page` or a'
                ' `Block`.'
            )

        return super().save(*args, **kwargs)
