from django.core.exceptions import ValidationError
from django.db import models
from django.utils.text import slugify

from polymorphic.models import PolymorphicModel


"""
Sites are the top level object.  They have attributes that one would
 reasonably expect of a Site, such as a name.

Pages are ordered in a hierarchy.  Each Page exists as a child of
 either another Page, or a Site.

Pages contain Blocks, which can be of many types.

Blocks can contain References, which refer to a Page or Block.
"""


class Site(models.Model):
    name = models.CharField(max_length=255)
    slug = models.SlugField(unique=True)

    @property
    def children(self):
        return self._children.filter(parent_page=None)

    def save(self, *args, **kwargs):
        if not self.slug:
            self.slug = slugify(self.name, allow_unicode=True)

        return super().save(*args, **kwargs)


class Page(models.Model):
    parent_page = models.ForeignKey(
        'self',
        related_name='children',
        on_delete=models.PROTECT,
        null=True,
    )
    site = models.ForeignKey(
        'cms.Site',
        related_name='_children',
        on_delete=models.PROTECT,
    )

    title = models.CharField(max_length=1024)
    slug = models.SlugField(unique=True)

    def save(self, *args, **kwargs):
        if not self.slug:
            self.slug = slugify(self.name, allow_unicode=True)

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
