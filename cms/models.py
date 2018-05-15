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
        blank=True,
        null=True,
    )
    denormalised_path = models.TextField(
        help_text=(
            'Ordered slash-separated list of parent `Page`s\' slugs,'
            ' starting from the top level `Page`.  This does not'
            ' include the current `Page`.'
        ),
        editable=False,
        db_index=True,
    )

    title = models.CharField(max_length=1024)
    slug = models.SlugField(blank=True)

    class Meta:
        unique_together = ('denormalised_path', 'slug')

    def __str__(self):
        return f'Page "{self.title}"'

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        self._old_slug = self.slug
        self._old_parent_id = self.parent_id

        self._children_paths_redenormalisation_scheduled = False

    @property
    def _denormalised_path_parts(self):
        return [
            part for part in [self.parent.denormalised_path, self.parent.slug]
            if part
        ]

    def generate_denormalised_path(self):
        if self.parent:
            return '/'.join(self._denormalised_path_parts)

        return ''

    def _denormalise_path(self):
        # Update own `denormalised_path`
        self.denormalised_path = self.generate_denormalised_path()

        self._children_paths_redenormalisation_scheduled = True

    def _redenormalise_children_paths(self):
        for child in self.children.all():
            child.save(redenormalise_path=True)

    def _redenormalise_children_paths_if_needed(self):
        if self._children_paths_redenormalisation_scheduled:
            self._redenormalise_children_paths()

        self._children_paths_redenormalisation_scheduled = False

    @property
    def _path_needs_redenormalising(self):
        # Do we need to initialise the denormalised path?
        if not self.denormalised_path and self.parent is not None:
            return True

        # If we've just been moved to the top level, we'll need to
        # blank `denormalised_path` and update our children anyway.
        if self.denormalised_path and self.parent is None:
            return True

        # Has our slug changed?
        if self._old_slug != self.slug:
            return True

        # Have we been adopted?
        if self._old_parent_id != self.parent_id:
            return True

        return False

    def _redenormalise_path_if_needed(self, force=False):
        if force or self._path_needs_redenormalising:
            self._denormalise_path()

    def _validate_noncyclic_hierarchy(self):
        # If we've not been adopted, short-circuit.
        if self.pk is not None and self._old_parent_id == self.parent_id:
            return

        # If we've become a root, also short-circuit.
        if self.parent is None:
            return

        parent = self.parent
        while parent is not None:
            if parent.id == self.id:
                raise ValidationError(
                    'Pages cannot be descendants of themselves.'
                )

            parent = parent.parent

    def save(self, *args, redenormalise_path=False, **kwargs):
        if not self.slug:
            self.slug = slugify(self.title, allow_unicode=True)

        self._validate_noncyclic_hierarchy()

        self._redenormalise_path_if_needed(force=redenormalise_path)

        ret = super().save(*args, **kwargs)

        self._redenormalise_children_paths_if_needed()

        return ret


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
